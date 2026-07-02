"""Data transfer service - orchestrates remote export, download, import, and fill."""

import asyncio
import base64
import os
import subprocess
import tarfile
import time
import uuid
import logging
from pathlib import Path

from app.config import AppConfig
from app import database as db
from app.services import ssh_service
from app.services.sql_templates import sql_old2new, sql_uptnew, sql_remote_export, sql_remote_export_base_tables, sql_remote_sed_rename
from app.services import expr_parser
from app.services.query_service import clear_columns_cache

log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))

# Background task management
_tasks: dict[str, dict] = {}


async def start_task(site, period_type, ym, date_start, date_end, tables):
    """Start a background run_all task, return task_id immediately."""
    task_id = uuid.uuid4().hex[:8]
    _tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "results": [],
        "start_time": time.time(),
        "end_time": None,
    }

    async def _run():
        try:
            results = await run_all(site, period_type, ym, date_start, date_end, tables)
            _tasks[task_id]["results"] = results
            _tasks[task_id]["status"] = "done"
        except Exception as e:
            log.error(f"Background task {task_id} failed: {e}")
            _tasks[task_id]["results"] = [{"success": False, "step": "error", "error": str(e)}]
            _tasks[task_id]["status"] = "done"
        finally:
            _tasks[task_id]["end_time"] = time.time()

    asyncio.create_task(_run())
    return task_id


def get_task_status(task_id: str) -> dict | None:
    t = _tasks.get(task_id)
    if not t:
        return None
    elapsed = ((t["end_time"] or time.time()) - t["start_time"])
    return {**t, "elapsed": round(elapsed, 1)}


def _log_name(period_type: str, ym: str = "", date_start: str = "", date_end: str = "") -> str:
    if period_type == "monthly":
        return f"logs{ym}"
    else:
        ds = date_start.replace("-", "")
        de = date_end.replace("-", "")
        return f"logs{ds}_{de}"


def _time_range(period_type: str, ym: str = "", date_start: str = "", date_end: str = "") -> tuple[str, str]:
    if period_type == "monthly":
        year = int(ym[:4])
        month = int(ym[4:6])
        if month == 12:
            last_day = 31
        else:
            import calendar
            last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-01 00:00:00", f"{year:04d}-{month:02d}-{last_day:02d} 23:59:59"
    else:
        return f"{date_start} 00:00:00", f"{date_end} 23:59:59"


def _mysql_import(sql_file: str, db_name: str, config: AppConfig):
    """Import a SQL dump file using mysql CLI client (handles large dumps)."""
    mc = config.mysql
    cmd = [
        "mysql",
        f"--host={mc.host}",
        f"--port={mc.port}",
        f"--user={mc.user}",
        f"--password={mc.password}",
        "--default-character-set=utf8mb4",
        "--skip-ssl",
        db_name,
    ]
    with open(sql_file, "r", encoding="utf-8") as f:
        proc = subprocess.run(cmd, stdin=f, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError(f"MySQL import failed: {proc.stderr[:500]}")
    log.info(f"Imported {sql_file} into {db_name}")


async def register_log_name(log_name: str, site: str):
    await db.execute(
        """CREATE TABLE IF NOT EXISTS sum_all.logs_name (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            create_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            tbn VARCHAR(80) NULL,
            stn VARCHAR(80) NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    )
    await db.execute(
        "INSERT INTO sum_all.logs_name(tbn, stn) VALUES(%s, %s)",
        (log_name, site),
    )


def _background_export_logs(ssh_cfg, site: str, log_name: str, dump_cmd: str,
                             rdb=None, time_begin=None, time_end=None,
                             max_wait: int = 1800) -> dict:
    """Run the remote mysqldump DETACHED (nohup) and poll for completion over fresh
    SSH connections. Survives SSH drops: the dump is not a child of any one session,
    and each status poll reconnects. Also verifies data presence (INSERT rows > 0).

    Returns an export-result dict. Runs blocking I/O — call via run_in_executor.
    """
    sh_dir = f"~/data/{site}"
    script_path = f"{sh_dir}/.export.sh"
    sql_file = f"{sh_dir}/{log_name}.sql"
    done = f"{sh_dir}/.export.done"
    exitf = f"{sh_dir}/.export.exit"
    errf = f"{sh_dir}/.export.err"

    # build a remote script (avoids shell-quoting the dump command, which contains
    # both single and double quotes). Upload via base64 to sidestep all quoting.
    script = (
        "#!/bin/bash\n"
        f"{dump_cmd} 2> {errf}\n"
        f"echo $? > {exitf}\n"
        f"touch {done}\n"
    )
    b64 = base64.b64encode(script.encode("utf-8")).decode()
    c, _, e = ssh_service.exec_remote_command(
        ssh_cfg, f"printf '%s' {b64} | base64 -d > {script_path}", timeout=60)
    if c != 0:
        return {"success": False, "step": "export", "error": f"写入远程导出脚本失败: {e}"}

    # clean stale markers, then launch detached
    ssh_service.exec_remote_command(ssh_cfg, f"rm -f {done} {exitf} {errf}", timeout=60)
    ssh_service.exec_remote_command(
        ssh_cfg, f"nohup bash {script_path} >/dev/null 2>&1 &", timeout=60)

    # poll for completion (fresh connection each iteration; reconnect on drop)
    deadline = time.time() + max_wait
    finished = False
    while time.time() < deadline:
        time.sleep(5)
        try:
            c, o, _ = ssh_service.exec_remote_command(
                ssh_cfg, f"test -f {done} && echo ok", timeout=60)
            if c == 0 and "ok" in o:
                finished = True
                break
        except Exception as ex:
            log.warning("poll export status failed (will reconnect & retry): %s", ex)
    if not finished:
        return {"success": False, "step": "export", "error": f"远程导出超时（{max_wait}s）"}

    # dump exit code + stderr
    _, o, _ = ssh_service.exec_remote_command(ssh_cfg, f"cat {exitf} 2>/dev/null", timeout=60)
    try:
        dump_exit = int((o or "0").strip().split()[0])
    except (ValueError, IndexError):
        dump_exit = -1
    _, errout, _ = ssh_service.exec_remote_command(ssh_cfg, f"cat {errf} 2>/dev/null", timeout=60)
    if dump_exit != 0:
        return {"success": False, "step": "export",
                "error": f"mysqldump 失败(exit {dump_exit}): {(errout or '').strip()[:300]}"}

    # size check
    _, o, _ = ssh_service.exec_remote_command(ssh_cfg, f"wc -c {sql_file}", timeout=120)
    try:
        size = int(o.strip().split()[0])
    except (ValueError, IndexError):
        size = 0
    if size == 0:
        return {"success": False, "step": "export", "error": "导出文件为空"}

    # data-presence check: must contain at least one INSERT row
    _, o, _ = ssh_service.exec_remote_command(
        ssh_cfg, f"grep -c '^INSERT INTO' {sql_file}", timeout=120)
    try:
        inserts = int((o or "0").strip().split()[0])
    except (ValueError, IndexError):
        inserts = 0
    if inserts == 0:
        return {"success": False, "step": "export",
                "error": "导出数据为空（0 行 INSERT）。可能是该时间范围内无 type=2 记录，或导出被中断"}

    # sed rename `logs` → `{log_name}orig`
    sed_cmd = sql_remote_sed_rename(site, log_name)
    sed_code, _, sed_err = ssh_service.exec_remote_command(ssh_cfg, sed_cmd, timeout=300)
    if sed_code not in (0, -1):
        return {"success": False, "step": "export", "error": f"sed rename failed: {sed_err}"}

    # tar
    tar_file = f"{site}_{log_name}.tgz"
    ssh_service.exec_remote_command(
        ssh_cfg,
        f"cd {sh_dir} && rm -f {tar_file} && tar -czf {tar_file} {log_name}.sql && rm -f {log_name}.sql",
        timeout=300,
    )

    # Query actual row count for the success log
    row_count = 0
    if rdb and time_begin and time_end:
        try:
            tbl_exp = rf"\`{rdb.db_name}\`.logs"
            cc = (
                f"docker exec {rdb.container_name} mysql -uroot -p{rdb.password} -N "
                f"-e \"SELECT COUNT(*) FROM {tbl_exp} WHERE type=2 "
                f"AND created_at+28800 BETWEEN UNIX_TIMESTAMP('{time_begin}') "
                f"AND UNIX_TIMESTAMP('{time_end}')\""
            )
            c, out, _ = ssh_service.exec_remote_command(ssh_cfg, cc, timeout=120)
            if c == 0:
                row_count = int(out.strip())
        except Exception:
            pass
    return {"success": True, "step": "export", "log_name": log_name, "count": row_count}


async def export_remote(site: str, period_type: str, ym: str = "",
                         date_start: str = "", date_end: str = "",
                         tables: list[str] | None = None) -> dict:
    """Step 1: Remote export - SSH to remote, execute mysqldump, compress."""
    if tables is None:
        tables = ["logs", "channels", "tokens", "users"]
    config = AppConfig.load()
    site_cfg = config.get_site(site)
    ssh_cfg = site_cfg.ssh
    rdb = site_cfg.remote_db

    log_name = _log_name(period_type, ym, date_start, date_end)
    time_begin, time_end = _time_range(period_type, ym, date_start, date_end)

    # ensure remote directory
    ssh_service.exec_remote_command(ssh_cfg, f"mkdir -p ~/data/{site}")

    # export logs if selected — detached background dump + poll (survives SSH drops)
    if "logs" in tables:
        # pre-check: count matching rows, to surface "无数据" clearly before the dump
        tbl_expr = "\\`" + rdb.db_name + "\\`.logs"
        count_cmd = (
            f"docker exec {rdb.container_name} mysql -uroot -p{rdb.password} -N "
            f"-e \"SELECT COUNT(*) FROM {tbl_expr} WHERE type=2 "
            f"AND created_at+28800 BETWEEN UNIX_TIMESTAMP('{time_begin}') "
            f"AND UNIX_TIMESTAMP('{time_end}')\""
        )
        ck_code, ck_out, ck_err = ssh_service.exec_remote_command(
            ssh_cfg, count_cmd, timeout=120)
        if ck_code == 0:
            try:
                row_count = int(ck_out.strip())
            except (ValueError, IndexError):
                row_count = -1
            if row_count == 0:
                return {"success": False, "step": "export",
                        "error": f"远程数据库 {rdb.db_name}.logs 中"
                                 f"无符合条件的数据（{time_begin} ~ {time_end}，type=2）"}
            log.info("导出前预检查: %s.%s 匹配 %d 行数据", rdb.db_name, "logs", row_count)
        elif ck_code > 0:
            log.warning("预检查查询失败(exit %d): %s，将继续尝试导出", ck_code, ck_err)

        export_cmd = sql_remote_export(
            site=site,
            container_name=rdb.container_name,
            db_name=rdb.db_name,
            password=rdb.password,
            log_name=log_name,
            time_begin=time_begin,
            time_end=time_end,
            backup=ssh_cfg.backup,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, _background_export_logs, ssh_cfg, site, log_name, export_cmd,
            rdb, time_begin, time_end
        )
        if not result["success"]:
            return result

    # export selected base tables
    base_tables = [t for t in ["channels", "users", "tokens"] if t in tables]
    if base_tables:
        for tbl in base_tables:
            cmd = (
                f"docker exec {rdb.container_name} mysqldump -uroot -p{rdb.password} "
                f"--single-transaction --set-gtid-purged=OFF {rdb.db_name} {tbl} "
                f"> ~/data/{site}/{tbl}.sql"
            )
            ssh_service.exec_remote_command(ssh_cfg, cmd, timeout=300)

        for tbl in base_tables:
            tf = f"{site}_{tbl}.tgz"
            ssh_service.exec_remote_command(
                ssh_cfg,
                f"cd ~/data/{site} && rm -f {tf} && tar -czvf {tf} {tbl}.sql",
            )
        ssh_service.exec_remote_command(
            ssh_cfg, f"cd ~/data/{site} && rm -f {' '.join(f'{t}.sql' for t in base_tables)}"
        )

    return {"success": True, "step": "export", "log_name": log_name}


async def download_remote(site: str, period_type: str, ym: str = "",
                           date_start: str = "", date_end: str = "",
                           tables: list[str] | None = None) -> dict:
    """Step 2: Download remote files via SFTP, decompress locally."""
    if tables is None:
        tables = ["logs", "channels", "tokens", "users"]
    config = AppConfig.load()
    site_cfg = config.get_site(site)
    ssh_cfg = site_cfg.ssh

    log_name = _log_name(period_type, ym, date_start, date_end)
    local_dir = DATA_DIR / site / "remote"
    local_dir.mkdir(parents=True, exist_ok=True)

    # download log archive
    if "logs" in tables:
        tar_file = f"{site}_{log_name}.tgz"
        local_tar = local_dir / tar_file
        ssh_service.sftp_download(ssh_cfg, f"/root/data/{site}/{tar_file}", str(local_tar))

        with tarfile.open(local_tar, "r:gz") as tar:
            tar.extractall(local_dir)

    # download selected base tables
    base_tables = [t for t in ["channels", "users", "tokens"] if t in tables]
    for tbl in base_tables:
        tf = f"{site}_{tbl}.tgz"
        local_base_tar = local_dir / tf
        try:
            ssh_service.sftp_download(ssh_cfg, f"/root/data/{site}/{tf}", str(local_base_tar))
            with tarfile.open(local_base_tar, "r:gz") as tar:
                tar.extractall(local_dir)
        except Exception:
            log.warning(f"Base table {tbl} not available for {site}")

    return {"success": True, "step": "download", "log_name": log_name, "local_dir": str(local_dir)}


async def import_local(site: str, log_name: str,
                       tables: list[str] | None = None) -> dict:
    """Step 3: Import SQL files into local MySQL using mysql CLI."""
    if tables is None:
        tables = ["logs", "channels", "tokens", "users"]
    config = AppConfig.load()
    local_dir = DATA_DIR / site / "remote"
    db_name = config.db_name(site)

    # import logs if selected
    if "logs" in tables:
        await register_log_name(log_name, site)
        log_sql_file = local_dir / f"{log_name}.sql"
        orig_table = f"{log_name}orig"
        if log_sql_file.exists():
            _mysql_import(str(log_sql_file), db_name, config)
        # verify orig table was created, if not fetch structure from remote
        check = await db.fetch_one(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (db_name, orig_table),
        )
        if not check:
            log.info(f"Table {orig_table} not found locally, fetching structure from remote")
            site_cfg = config.get_site(site)
            ssh_cfg = site_cfg.ssh
            rdb = site_cfg.remote_db
            struct_cmd = (
                f"docker exec {rdb.container_name} mysqldump -uroot -p{rdb.password} "
                f"--no-data --single-transaction --set-gtid-purged=OFF {rdb.db_name} logs"
            )
            exit_code, out, err = ssh_service.exec_remote_command(ssh_cfg, struct_cmd, timeout=60)
            if exit_code == 0 and out.strip():
                sql = out.replace('`logs`', f'`{orig_table}`')
                struct_file = local_dir / f"{orig_table}_struct.sql"
                with open(struct_file, "w", encoding="utf-8") as f:
                    f.write(sql)
                _mysql_import(str(struct_file), db_name, config)
                struct_file.unlink()
                log.info(f"Created {orig_table} from remote structure")
            else:
                return {"success": False, "step": "import", "error": f"无法从远程获取表结构: {err or 'empty response'}"}

    # import selected base tables
    base_tables = [t for t in ["channels", "users", "tokens"] if t in tables]
    for tbl in base_tables:
        sql_file = local_dir / f"{tbl}.sql"
        if sql_file.exists():
            _mysql_import(str(sql_file), db_name, config)

    return {"success": True, "step": "import", "log_name": log_name}


async def _index_exists(table: str, index_name: str, db_name: str) -> bool:
    """Check if an index exists on a table."""
    row = await db.fetch_one(
        "SELECT COUNT(*) as cnt FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s",
        (db_name, table, index_name),
    )
    return row is not None and row["cnt"] > 0


async def fill_local(site: str, log_name: str) -> dict:
    """Step 4: Generate processed table and fill with sales/buyer info."""
    config = AppConfig.load()
    site_cfg = config.get_site(site)
    db_name = config.db_name(site)

    try:
        # old2new: create processed table from orig (non-index statements)
        stmts = sql_old2new(log_name)
        # invalidate columns cache since table is being recreated
        clear_columns_cache(db_name, log_name)
        idx_stmt_indices = []
        for i, stmt in enumerate(stmts):
            if stmt.startswith("CREATE INDEX"):
                idx_stmt_indices.append(i)
                continue
            await db.execute(stmt, db=db_name)

        # create indexes with existence check
        for i in idx_stmt_indices:
            stmt = stmts[i]
            # extract index name: CREATE INDEX `xxx` ON ...
            parts = stmt.split("`")
            idx_name = parts[1] if len(parts) >= 2 else ""
            tbl_name = parts[3] if len(parts) >= 4 else ""
            if idx_name and tbl_name and not await _index_exists(tbl_name, idx_name, db_name):
                await db.execute(stmt, db=db_name)

        # uptnew: fill sales/buyer info (skip ex_ tables gracefully if missing)
        stmts = sql_uptnew(log_name, mode=site_cfg.uptnew_mode)
        for stmt in stmts:
            if stmt.startswith("CREATE INDEX"):
                parts = stmt.split("`")
                idx_name = parts[1] if len(parts) >= 2 else ""
                tbl_name = parts[3] if len(parts) >= 4 else ""
                if idx_name and tbl_name and await _index_exists(tbl_name, idx_name, db_name):
                    continue
            try:
                await db.execute(stmt, db=db_name)
            except Exception as ex:
                err_str = str(ex)
                # 1146 = table not found; common when ex_users/ex_tokens/ex_channels don't exist
                if "1146" in err_str:
                    log.warning("skip uptnew step (ex_ table missing): %s — %s", stmt[:60], err_str[:100])
                else:
                    raise

        # fill_expr_pricing: apply expr_b64-based pricing for rows that have it
        await fill_expr_pricing(site, log_name)

    except Exception as e:
        log.error(f"fill_local failed for {site}/{log_name}: {e}")
        return {"success": False, "step": "fill", "error": str(e)}

    return {"success": True, "step": "fill", "log_name": log_name}


async def fill_expr_pricing(site: str, log_name: str):
    """Apply expr_b64-based pricing for rows that have a non-empty expr_b64.

    For each distinct expr_b64 value, decode the formula and generate a
    single UPDATE SQL that sets the price/ratio fields for all matching rows.

    This runs after uptnew so that rows without expr_b64 keep the old logic.
    """
    config = AppConfig.load()
    db_name = config.db_name(site)
    table = log_name

    # Get distinct non-empty expr_b64 values
    rows = await db.fetch_all(
        f"SELECT DISTINCT expr_b64 FROM `{table}` "
        "WHERE expr_b64 IS NOT NULL AND expr_b64 != ''",
        db=db_name,
    )
    if not rows:
        return

    for row in rows:
        b64 = row["expr_b64"]
        try:
            formula = expr_parser.parse(b64)
            sql = expr_parser.generate_update_sql(table, b64, formula)
            if not sql:
                continue
            log.info(
                "fill_expr_pricing: %s / %s  b64=%.40s…  "
                "tiered=%s  tiers=%d  currency=%s",
                site, table, b64,
                formula.is_tiered, len(formula.tiers), formula.currency,
            )
            await db.execute(sql, (b64,), db=db_name)
            log.info("fill_expr_pricing: updated rows for expr_b64=%.40s…", b64)
        except Exception as e:
            log.error(
                "fill_expr_pricing failed for %s/%s b64=%.40s… : %s",
                site, table, b64, e,
            )


async def run_all(site: str, period_type: str, ym: str = "",
                  date_start: str = "", date_end: str = "",
                  tables: list[str] | None = None) -> list[dict]:
    """Execute all steps in sequence."""
    if tables is None:
        tables = ["logs", "channels", "tokens", "users"]
    results = []
    log_name = _log_name(period_type, ym, date_start, date_end)

    # Step 1: Export
    try:
        r = await export_remote(site, period_type, ym, date_start, date_end, tables)
    except Exception as e:
        log.error(f"export_remote failed for {site}: {e}")
        r = {"success": False, "step": "export", "error": str(e)}
    results.append(r)
    if not r["success"]:
        return results

    # Step 2: Download
    try:
        r = await download_remote(site, period_type, ym, date_start, date_end, tables)
    except Exception as e:
        log.error(f"download_remote failed for {site}: {e}")
        r = {"success": False, "step": "download", "error": str(e)}
    results.append(r)
    if not r["success"]:
        return results

    # Step 3: Import
    try:
        r = await import_local(site, log_name, tables)
    except Exception as e:
        log.error(f"import_local failed for {site}/{log_name}: {e}")
        r = {"success": False, "step": "import", "error": str(e)}
    results.append(r)
    if not r["success"]:
        return results

    # Step 4: Fill (only when logs is selected)
    if "logs" in tables:
        r = await fill_local(site, log_name)
        results.append(r)

    return results


async def uptcustomer(site: str, table_name: str | None = None) -> dict:
    """Sync upstream customer/discount info across sites for the latest log table."""
    db_name = f"sum_{site}"

    # resolve target log table name
    if table_name:
        tbn = table_name
    else:
        row = await db.fetch_one(
            "SELECT tbn FROM sum_all.logs_name WHERE %s = CONCAT('sum_', stn) ORDER BY id DESC LIMIT 1",
            (site,),
        )
        if row:
            tbn = row["tbn"]
        else:
            from datetime import datetime
            tbn = f"logs{datetime.now().strftime('%Y%m')}"

    # verify the table exists
    check = await db.fetch_one(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
        (db_name, tbn),
    )
    if not check:
        return {"success": False, "step": "uptcustomer", "error": f"表 {tbn} 不存在"}

    # load upstream sites from sum_all.site_dbn
    sites = await db.fetch_all("SELECT dbn, url, name FROM sum_all.site_dbn")
    if not sites:
        return {"success": False, "step": "uptcustomer", "error": "sum_all.site_dbn 无数据"}

    details = []
    for s in sites:
        v_dbn = s["dbn"]
        v_url = s["url"]
        v_name = s["name"]
        if v_dbn == db_name:
            continue

        # check upstream table exists
        up_check = await db.fetch_one(
            "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (v_dbn, tbn),
        )
        if not up_check:
            details.append(f"{v_name}: 表 {tbn} 不存在，跳过")
            continue

        # check matching records
        cnt_row = await db.fetch_one(
            f"SELECT COUNT(*) as cnt FROM `{tbn}` l "
            f"INNER JOIN channels c ON l.channel_id = c.id "
            f"WHERE c.base_url LIKE CONCAT('%%', %s, '%%') AND l.quota > 0",
            (v_url,), db=db_name,
        )
        match_count = cnt_row["cnt"] if cnt_row else 0

        if match_count == 0:
            details.append(f"{v_name}: 无匹配记录，跳过")
            continue

        # cross-database update
        update_sql = (
            f"UPDATE `{tbn}` l "
            f"INNER JOIN channels c ON l.channel_id = c.id "
            f"INNER JOIN `{v_dbn}`.`{tbn}` ls "
            f"  ON l.created_at = ls.created_at "
            f"  AND l.prompt_tokens = ls.prompt_tokens "
            f"  AND l.completion_tokens = ls.completion_tokens "
            f"  AND l.use_time = ls.use_time "
            f"  AND l.quota = ls.quota "
            f"SET l.windup_type = 1, "
            f"    ls.windup_type = 2, "
            f"    ls.down_site = %s, "
            f"    l.us_salesperson1 = ls.us_salesperson, "
            f"    l.cn_buyer1 = ls.cn_buyer, "
            f"    l.cn_supplier1 = ls.cn_supplier, "
            f"    l.cn_discount_orig = ls.cn_discount "
            f"WHERE c.base_url LIKE CONCAT('%%', %s, '%%') "
            f"AND l.quota > 0 "
            f"AND ls.us_salesperson IS NOT NULL"
        )
        await db.execute(update_sql, (db_name, v_url), db=db_name)
        details.append(f"{v_name}: {match_count} 条匹配")

    return {"success": True, "step": "uptcustomer", "log_name": tbn, "details": details}
