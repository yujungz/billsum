"""数据传导 — orchestration: export → tar → transfer → import, as a background
task with progressive, timestamped per-step/per-table logs.

Mirrors transfer_service.py's background-task shape but adds a `logs` list that
the poll endpoint returns live (transfer only returns final results).

Backup-mode semantics:
  * full (整库备份): `mysqldump --databases <src_db> --add-drop-database
    --routines --triggers --events`. Standard whole-DB dump — restores the DB
    under its SOURCE name on the destination (DROP+CREATE DATABASE in the dump,
    so import needs no target-db arg and dest db_name is ignored in full mode).
  * selective (选择备份): `mysqldump <src_db> <tables...>` (no --databases).
    Dump has no USE, so import targets the DEST db_name; tables overwrite via
    DROP TABLE IF EXISTS already in the dump.
"""

import asyncio
import logging
import os
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from app.services import conduction_commands as cc
from app.services import conduction_ssh
from app.services.conduction_config import CondConfig, CondEndpoint

log = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
COND_DIR = DATA_DIR / "conduction"

# Background task registry (separate from transfer_service._tasks)
_tasks: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
#  Task lifecycle
# --------------------------------------------------------------------------- #

def start_task(src: CondEndpoint, dst: CondEndpoint, skip_import: bool = False) -> str:
    task_id = uuid.uuid4().hex[:8]
    _tasks[task_id] = {
        "task_id": task_id,
        "status": "running",
        "logs": [],
        "start_time": time.time(),
        "end_time": None,
    }

    async def _run():
        try:
            await run_all(task_id, src, dst, skip_import)
        except Exception as e:
            log.exception("conduction task %s crashed", task_id)
            _append_log(task_id, "错误", False, str(e))
        finally:
            _tasks[task_id]["status"] = "done"
            _tasks[task_id]["end_time"] = time.time()

    asyncio.create_task(_run())
    return task_id


def get_task_status(task_id: str) -> dict | None:
    t = _tasks.get(task_id)
    if not t:
        return None
    elapsed = (t["end_time"] or time.time()) - t["start_time"]
    tgz_path = t.get("tgz_path")
    return {
        "task_id": task_id,
        "status": t["status"],
        "logs": t["logs"],
        "elapsed": round(elapsed, 1),
        "tgz_name": t.get("tgz_name", ""),
        "has_tgz": bool(tgz_path and os.path.exists(tgz_path)),
    }


def get_tgz(task_id: str) -> tuple[str, str] | None:
    """Return (path, filename) of the backup archive if it still exists on disk."""
    t = _tasks.get(task_id)
    if not t:
        return None
    path = t.get("tgz_path")
    if path and os.path.exists(path):
        return path, t.get("tgz_name", "backup.tgz")
    return None


def _append_log(task_id: str, step: str, success: bool, message: str = "") -> None:
    t = _tasks.get(task_id)
    if not t:
        return
    t["logs"].append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "step": step,
        "success": success,
        "message": message,
    })


# --------------------------------------------------------------------------- #
#  Connection tests / table listing (used by router + pipeline)
# --------------------------------------------------------------------------- #

def test_ssh(ep: CondEndpoint) -> tuple[bool, str]:
    if ep.deploy_type != "remote":
        return False, "本地端点无需测试 SSH"
    return conduction_ssh.test_connection(ep)


def _run_client(ep: CondEndpoint, kind: str) -> str:
    """Run a mysql client command against an endpoint.
    kind: 'ping' | 'databases' | 'tables'. Returns stdout text or raises."""
    if ep.deploy_type == "remote":
        cmd = {
            "ping": cc.remote_ping_cmd,
            "databases": cc.remote_show_databases_cmd,
            "tables": cc.remote_show_tables_cmd,
        }[kind](ep)
        code, out, err = conduction_ssh.exec_remote(ep, cmd, timeout=60)
        if code != 0:
            raise RuntimeError((err or out).strip()[:300])
        return out
    argv = {
        "ping": cc.local_ping_argv,
        "databases": cc.local_show_databases_argv,
        "tables": cc.local_show_tables_argv,
    }[kind](ep)
    proc = subprocess.run(argv, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", "replace").strip()[:300])
    return proc.stdout.decode("utf-8", "replace")


def test_db(ep: CondEndpoint) -> tuple[bool, str, list[str]]:
    """Two-step DB test: (1) ping server without db name, (2) check db exists.
    A non-existing db is NOT an error — destination dbs may be created on import.
    """
    # step 1: server connectivity (no db arg)
    try:
        _run_client(ep, "ping")
    except Exception as e:
        return False, f"服务器连接失败: {e}", []
    # step 2: database existence
    try:
        dbs = _parse_list(_run_client(ep, "databases"))
    except Exception as e:
        return False, f"服务器连接成功，但获取数据库列表失败: {e}", []
    exists = ep.db.db_name in dbs
    msg = f"服务器连接成功；数据库 {ep.db.db_name} {'存在' if exists else '不存在'}"
    tables: list[str] = []
    if exists:
        try:
            tables = _parse_tables(_run_client(ep, "tables"))
        except Exception:
            tables = []
    return True, msg, tables


def fetch_tables(ep: CondEndpoint) -> list[str]:
    """Run SHOW TABLES against an endpoint (local subprocess or remote SSH)."""
    return _parse_tables(_run_client(ep, "tables"))


def _parse_tables(out: str) -> list[str]:
    """mysql -e 'SHOW TABLES' prints a `Tables_in_<db>` header row first."""
    tables = []
    for i, line in enumerate(out.strip().splitlines()):
        s = line.strip()
        if not s:
            continue
        if i == 0 and s.lower().startswith("tables_in_"):
            continue
        tables.append(s)
    return tables


def _parse_list(out: str) -> list[str]:
    """Parse SHOW DATABASES output (header row is 'Database')."""
    items = []
    for i, line in enumerate(out.strip().splitlines()):
        s = line.strip()
        if not s:
            continue
        if i == 0 and s.lower() == "database":
            continue
        items.append(s)
    return items


def _determine_full(ep: CondEndpoint, available: list[str]) -> tuple[bool, list[str]]:
    """full = 「全部」checked OR all available tables are selected."""
    available_set = set(available)
    if ep.all_checked:
        return True, sorted(available_set)
    selected = [t for t in ep.selected_tables if t in available_set]
    if available_set and set(selected) == available_set:
        return True, sorted(available_set)
    return False, selected


# --------------------------------------------------------------------------- #
#  Local sync primitives (run via run_in_executor)
# --------------------------------------------------------------------------- #

def _local_export(ep: CondEndpoint, full: bool, tables: list[str], out_sql: str) -> None:
    argv = cc.local_dump_argv(ep, full, tables)
    with open(out_sql, "wb") as f:
        proc = subprocess.Popen(argv, stdout=f, stderr=subprocess.PIPE)
        _, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"本地导出失败(exit {proc.returncode}): "
                           f"{err.decode('utf-8', 'replace').strip()[:500]}")


def _local_import(ep: CondEndpoint, db_name: str, full: bool, in_sql: str) -> None:
    argv = cc.local_import_argv(ep, db_name, full)
    with open(in_sql, "rb") as f:
        proc = subprocess.Popen(argv, stdin=f, stderr=subprocess.PIPE)
        _, err = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"本地导入失败(exit {proc.returncode}): "
                           f"{err.decode('utf-8', 'replace').strip()[:500]}")


def _local_create_db(ep: CondEndpoint, db_name: str) -> None:
    argv = cc.local_create_db_argv(ep, db_name)
    proc = subprocess.run(argv, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"建库失败: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}")


def _local_tar(sql_path: str, tgz_path: str) -> None:
    with tarfile.open(tgz_path, "w:gz") as tar:
        tar.add(sql_path, arcname=Path(sql_path).name)


def _local_untar(tgz_path: str, dest_dir: str) -> None:
    with tarfile.open(tgz_path, "r:gz") as tar:
        tar.extractall(dest_dir)


def _remote_export(ep: CondEndpoint, full: bool, tables: list[str], remote_sql: str) -> None:
    code, out, err = conduction_ssh.exec_remote(ep, cc.remote_dump_cmd(ep, full, tables, remote_sql), timeout=1800)
    if code != 0:
        raise RuntimeError(f"远程导出失败(exit {code}): {(err or out).strip()[:500]}")


# --------------------------------------------------------------------------- #
#  Path helpers for remotes (linux/windows aware)
# --------------------------------------------------------------------------- #

def _default_remote_path(ep: CondEndpoint) -> str:
    return "c:\\data" if ep.os_type == "windows" else "~/data/"


def resolve_remote_path(ep: CondEndpoint, path: str) -> str:
    """Resolve a leading `~` to an absolute path via SSH.

    Necessary because quoting suppresses `~` expansion in shell commands and
    SFTP does not expand `~` at all. Best-effort: on failure returns the path
    unchanged.
    """
    if not path or not path.startswith("~"):
        return path
    try:
        if ep.os_type == "windows":
            code, out, _ = conduction_ssh.exec_remote(ep, "echo %USERPROFILE%", timeout=30)
        else:
            code, out, _ = conduction_ssh.exec_remote(ep, "echo $HOME", timeout=30)
        home = out.strip().strip('"') if code == 0 else ""
    except Exception:
        home = ""
    if not home:
        return path
    return path.replace("~", home, 1)


def _remote_join(ep: CondEndpoint, *parts: str) -> str:
    sep = "\\" if ep.os_type == "windows" else "/"
    cleaned = [p for p in parts if p]
    if not cleaned:
        return ""
    # preserve a leading separator (absolute path) from the first part —
    # stripping it would turn "/root/data" into the relative "root/data",
    # which then resolves under the SSH home dir and breaks the redirect.
    leading = sep if cleaned[0].startswith(sep) else ""
    return leading + sep.join(p.strip("/\\") for p in cleaned)


def _sftp_path(path: str) -> str:
    """paramiko SFTP uses forward-slash POSIX-style paths (even on Windows SSH)."""
    return path.replace("\\", "/")


def _log_export_tables(task_id, full, tables, db_name):
    if full:
        _append_log(task_id, "导出", True, f"整库 {db_name} 已导出（含过程/函数/触发器/事件）")
    else:
        for t in tables:
            _append_log(task_id, "导出", True, f"表 {t} 已导出")


def _log_import_tables(task_id, full, tables, db_name):
    if full:
        _append_log(task_id, "导入", True, f"整库 {db_name} 已导入并覆盖")
    else:
        for t in tables:
            _append_log(task_id, "导入", True, f"表 {t} 已导入")


# --------------------------------------------------------------------------- #
#  Phase wrappers (own logging; raise on failure)
# --------------------------------------------------------------------------- #

async def _phase_export(task_id, src, full, tables, local_sql, local_tgz):
    loop = asyncio.get_event_loop()
    db_name = src.db.db_name
    if src.deploy_type == "remote":
        rp = src.ssh.remote_path or _default_remote_path(src)
        rp = resolve_remote_path(src, rp)
        remote_sql = _remote_join(src, rp, local_sql.name)
        remote_tgz = _remote_join(src, rp, local_tgz.name)
        _append_log(task_id, "导出", True, f"远程导出 → {remote_sql}")
        await loop.run_in_executor(None, conduction_ssh.remote_mkdir, src, rp)
        await loop.run_in_executor(None, _remote_export, src, full, tables, remote_sql)
        _log_export_tables(task_id, full, tables, db_name)
        cmd = cc.remote_tar_create_cmd(src, remote_tgz, rp, local_sql.name)
        code, out, err = await loop.run_in_executor(None, conduction_ssh.exec_remote, src, cmd, 600)
        if code != 0:
            raise RuntimeError(f"远程打包失败: {(err or out).strip()[:300]}")
        _append_log(task_id, "打包", True, f"远程打包 → {remote_tgz}")
        _append_log(task_id, "下载", True, f"下载 {remote_tgz} → 本地")
        await loop.run_in_executor(None, conduction_ssh.sftp_download, src,
                                   _sftp_path(remote_tgz), str(local_tgz))
        _append_log(task_id, "下载", True, f"已下载 → {local_tgz.name}")
    else:
        _append_log(task_id, "导出", True, f"本地导出 → {local_sql.name}")
        await loop.run_in_executor(None, _local_export, src, full, tables, str(local_sql))
        _log_export_tables(task_id, full, tables, db_name)
        await loop.run_in_executor(None, _local_tar, str(local_sql), str(local_tgz))
        _append_log(task_id, "打包", True, f"已打包 → {local_tgz.name}")


async def _phase_import(task_id, dst, full, tables, local_tgz, sql_name, work):
    loop = asyncio.get_event_loop()
    db_name = dst.db.db_name
    if dst.deploy_type == "remote":
        rp = dst.ssh.remote_path or _default_remote_path(dst)
        rp = resolve_remote_path(dst, rp)
        remote_tgz = _remote_join(dst, rp, local_tgz.name)
        remote_sql = _remote_join(dst, rp, sql_name)
        await loop.run_in_executor(None, conduction_ssh.remote_mkdir, dst, rp)
        _append_log(task_id, "上传", True, f"上传 → {remote_tgz}")
        await loop.run_in_executor(None, conduction_ssh.sftp_upload, dst,
                                   str(local_tgz), _sftp_path(remote_tgz))
        cmd = cc.remote_tar_extract_cmd(dst, remote_tgz, rp)
        code, out, err = await loop.run_in_executor(None, conduction_ssh.exec_remote, dst, cmd, 600)
        if code != 0:
            raise RuntimeError(f"远程解压失败: {(err or out).strip()[:300]}")
        _append_log(task_id, "解压", True, f"远程解压 → {sql_name}")
        if not full:
            cmd = cc.remote_create_db_cmd(dst, db_name)
            code, out, err = await loop.run_in_executor(None, conduction_ssh.exec_remote, dst, cmd, 120)
            lvl = "建库"
            if code != 0:
                _append_log(task_id, lvl, False, f"建库警告: {(err or out).strip()[:200]}")
            else:
                _append_log(task_id, lvl, True, f"CREATE DATABASE IF NOT EXISTS {db_name}")
        cmd = cc.remote_import_cmd(dst, db_name, full, remote_sql)
        code, out, err = await loop.run_in_executor(None, conduction_ssh.exec_remote, dst, cmd, 3600)
        if code != 0:
            raise RuntimeError(f"远程导入失败(exit {code}): {(err or out).strip()[:500]}")
        _log_import_tables(task_id, full, tables, db_name)
    else:
        await loop.run_in_executor(None, _local_untar, str(local_tgz), str(work))
        local_sql = work / sql_name
        if not local_sql.exists():
            raise RuntimeError(f"解压后未找到 {sql_name}")
        _append_log(task_id, "解压", True, f"已解压 → {sql_name}")
        if not full:
            await loop.run_in_executor(None, _local_create_db, dst, db_name)
            _append_log(task_id, "建库", True, f"CREATE DATABASE IF NOT EXISTS {db_name}")
        await loop.run_in_executor(None, _local_import, dst, db_name, full, str(local_sql))
        _log_import_tables(task_id, full, tables, db_name)


# --------------------------------------------------------------------------- #
#  Pipeline
# --------------------------------------------------------------------------- #

async def run_all(task_id: str, src: CondEndpoint, dst: CondEndpoint, skip_import: bool = False):
    work = COND_DIR / task_id
    work.mkdir(parents=True, exist_ok=True)

    src_db = src.db.db_name or "dump"
    sql_name = f"{src_db}.sql"
    tgz_name = f"{src_db}.tgz"
    local_sql = work / sql_name
    local_tgz = work / tgz_name
    _tasks[task_id]["tgz_path"] = str(local_tgz)
    _tasks[task_id]["tgz_name"] = tgz_name

    # Step 0: resolve full mode + tables from the SOURCE (re-fetch, don't trust client)
    _append_log(task_id, "准备", True, "获取源库表清单...")
    try:
        loop = asyncio.get_event_loop()
        available = await loop.run_in_executor(None, fetch_tables, src)
    except Exception as e:
        _append_log(task_id, "获取表清单", False, str(e))
        return
    full, tables = _determine_full(src, available)
    if not full and not tables:
        _append_log(task_id, "校验", False, "未选择任何表且未勾选「全部」，请至少选择一张表")
        return
    _append_log(task_id, "模式", True,
                ("整库备份: " + src_db) if full else (f"选择备份: {len(tables)} 张表 → {', '.join(tables)}"))

    # Step 1-3: export → local tgz
    try:
        await _phase_export(task_id, src, full, tables, local_sql, local_tgz)
    except Exception as e:
        _append_log(task_id, "导出", False, str(e))
        return

    # Step 4-5: import local tgz → destination (skipped when only download requested)
    if skip_import:
        _append_log(task_id, "完成", True, "远程文件已下载完成")
    else:
        try:
            await _phase_import(task_id, dst, full, tables, local_tgz, sql_name, work)
        except Exception as e:
            _append_log(task_id, "导入", False, str(e))
            return
        _append_log(task_id, "完成", True, "数据传导完成")
