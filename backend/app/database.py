import logging
import aiomysql
from app.config import AppConfig

log = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None


async def init_pool(config: AppConfig | None = None):
    global _pool
    if config is None:
        config = AppConfig.load()
    mc = config.mysql
    _pool = await aiomysql.create_pool(
        host=mc.host,
        port=mc.port,
        user=mc.user,
        password=mc.password,
        charset="utf8mb4",
        autocommit=True,
        maxsize=10,
        minsize=1,
    )


async def close_pool():
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


async def _ensure_pool():
    global _pool
    if _pool is None:
        log.info("Database pool not ready, initializing...")
        await init_pool()


async def execute(sql: str, params=None, db: str | None = None):
    await _ensure_pool()
    async with _pool.acquire() as conn:
        if db:
            await conn.select_db(db)
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            return cur.lastrowid


async def execute_many(sql: str, params_list, db: str | None = None):
    await _ensure_pool()
    async with _pool.acquire() as conn:
        if db:
            await conn.select_db(db)
        async with conn.cursor() as cur:
            await cur.executemany(sql, params_list)


async def fetch_one(sql: str, params=None, db: str | None = None):
    await _ensure_pool()
    async with _pool.acquire() as conn:
        if db:
            await conn.select_db(db)
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params)
            return await cur.fetchone()


async def fetch_all(sql: str, params=None, db: str | None = None):
    await _ensure_pool()
    async with _pool.acquire() as conn:
        if db:
            await conn.select_db(db)
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()


async def execute_script(sql_text: str, db: str | None = None):
    """Execute multi-statement SQL script."""
    await _ensure_pool()
    async with _pool.acquire() as conn:
        if db:
            await conn.select_db(db)
        async with conn.cursor() as cur:
            for stmt in conn.escape(sql_text).split(";"):
                stmt = stmt.strip()
                if stmt:
                    await cur.execute(stmt)
