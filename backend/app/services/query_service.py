"""Query service for listing and querying tables."""

import subprocess

from app import database as db
from app.config import AppConfig

# Fields that use LIKE (fuzzy) search
LIKE_FIELDS = {
    'name', 'group', 'base_url', 'models', 'username', 'token_name',
    'model_name', 'remark', 'buyer', 'supplier', 'seller', 'channel_name',
    'us_salesperson', 'cn_buyer1', 'cn_supplier1',
}

BASE_TABLES = ["channels", "users", "tokens"]
EX_TABLES = ["ex_channels", "ex_users", "ex_tokens"]

# Column metadata cache: { "db.table": columns_list }
_columns_cache: dict[str, list[dict]] = {}


async def list_raw_tables(site: str) -> list[dict]:
    """List raw/original tables for a site."""
    config = AppConfig.load()
    db_name = config.db_name(site)
    rows = await db.fetch_all(
        "SELECT TABLE_NAME as name, TABLE_ROWS as rows_count "
        "FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND "
        "(TABLE_NAME IN ('channels','users','tokens') OR TABLE_NAME LIKE 'logs%%orig') "
        "ORDER BY TABLE_NAME",
        (db_name,),
    )
    return rows


async def list_output_tables(site: str) -> list[dict]:
    """List output/processed tables for a site."""
    config = AppConfig.load()
    db_name = config.db_name(site)
    rows = await db.fetch_all(
        "SELECT TABLE_NAME as name, TABLE_ROWS as rows_count "
        "FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND "
        "(TABLE_NAME LIKE 'ex_%%' OR (TABLE_NAME LIKE 'logs%%' AND TABLE_NAME NOT LIKE '%%orig')) "
        "ORDER BY TABLE_NAME",
        (db_name,),
    )
    return rows


async def list_log_tables(site: str) -> list[dict]:
    """List all log tables (both orig and processed) for a site."""
    config = AppConfig.load()
    db_name = config.db_name(site)
    rows = await db.fetch_all(
        "SELECT TABLE_NAME as name, TABLE_ROWS as rows_count "
        "FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME LIKE 'logs%%' "
        "ORDER BY TABLE_NAME",
        (db_name,),
    )
    return rows


async def query_table(site: str, table_name: str, page: int = 1,
                       page_size: int = 50, filters: dict | None = None,
                       time_order: str = "desc") -> dict:
    """Paginated query on any table with optional filters."""
    config = AppConfig.load()
    db_name = config.db_name(site)

    # build where clause from filters
    where = ""
    params = []
    if filters:
        conditions = []
        for key, val in filters.items():
            if val is None or val == "":
                continue
            if key == 'created_at_start':
                conditions.append(
                    "created_at >= UNIX_TIMESTAMP(%s)-28800"
                )
                params.append(val)
            elif key == 'created_at_end':
                conditions.append(
                    "created_at <= UNIX_TIMESTAMP(%s)-28800"
                )
                params.append(val)
            elif key in LIKE_FIELDS:
                conditions.append(f"`{key}` LIKE %s")
                params.append(f"%{val}%")
            else:
                conditions.append(f"`{key}` = %s")
                params.append(val)
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

    # count - always use exact COUNT(*) (not estimated TABLE_ROWS)
    try:
        sql_count = f"SELECT COUNT(*) as total FROM `{table_name}`"
        if where:
            sql_count += f" {where}"
        count_row = await db.fetch_one(sql_count, params if where else None, db=db_name)
        total = count_row["total"] if count_row else 0
    except Exception:
        total = 0

    # data - use created_at order for logs tables, id order for others
    is_logs = table_name.startswith("logs")
    if is_logs:
        order_dir = "DESC" if time_order != "asc" else "ASC"
        order_clause = f"ORDER BY created_at {order_dir}, id {order_dir}"
    else:
        order_clause = "ORDER BY id DESC"
    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        f"SELECT * FROM `{table_name}` {where} {order_clause} LIMIT %s OFFSET %s",
        params + [page_size, offset],
        db=db_name,
    )

    return {"total": total, "page": page, "page_size": page_size, "data": rows}


async def get_table_columns(site: str, table_name: str) -> list[dict]:
    """Get column info for a table, with in-memory cache."""
    config = AppConfig.load()
    db_name = config.db_name(site)
    cache_key = f"{db_name}.{table_name}"

    cached = _columns_cache.get(cache_key)
    if cached is not None:
        return cached

    columns = await db.fetch_all(
        "SELECT COLUMN_NAME as name, DATA_TYPE as type, COLUMN_COMMENT as comment "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
        "ORDER BY ORDINAL_POSITION",
        (db_name, table_name),
    )
    _columns_cache[cache_key] = columns
    return columns


def clear_columns_cache(db_name: str = "", table_name: str = ""):
    """Clear column cache. If both args given, clear specific entry; otherwise clear all."""
    if db_name and table_name:
        _columns_cache.pop(f"{db_name}.{table_name}", None)
    else:
        _columns_cache.clear()


async def delete_table(site: str, table_name: str):
    config = AppConfig.load()
    db_name = config.db_name(site)
    await db.execute(f"DROP TABLE IF EXISTS `{table_name}`", db=db_name)
    _columns_cache.pop(f"{db_name}.{table_name}", None)


async def export_all_data(site: str, table_name: str, filters: dict | None = None) -> tuple:
    config = AppConfig.load()
    db_name = config.db_name(site)
    columns = await get_table_columns(site, table_name)

    where = ""
    params = []
    if filters:
        conditions = []
        for key, val in filters.items():
            if val is None or val == "":
                continue
            if key == 'created_at_start':
                conditions.append("created_at >= UNIX_TIMESTAMP(%s)-28800")
                params.append(val)
            elif key == 'created_at_end':
                conditions.append("created_at <= UNIX_TIMESTAMP(%s)-28800")
                params.append(val)
            elif key in LIKE_FIELDS:
                conditions.append(f"`{key}` LIKE %s")
                params.append(f"%{val}%")
            else:
                conditions.append(f"`{key}` = %s")
                params.append(val)
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

    rows = await db.fetch_all(f"SELECT * FROM `{table_name}` {where} LIMIT 1000000", params if params else None, db=db_name)
    return columns, rows


def export_table_sql(site: str, table_name: str) -> str:
    config = AppConfig.load()
    db_name = config.db_name(site)
    mc = config.mysql
    cmd = [
        "mysqldump",
        f"--host={mc.host}", f"--port={mc.port}",
        f"--user={mc.user}", f"--password={mc.password}",
        "--default-character-set=utf8mb4",
        "--skip-ssl",
        "--no-tablespaces",
        db_name, table_name,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"mysqldump failed: {proc.stderr[:500]}")
    return proc.stdout
