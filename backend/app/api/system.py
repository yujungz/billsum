"""System API - binlog management and SQL execution."""

import asyncio
import os
import re
import subprocess
import tempfile

from fastapi import APIRouter, Query, UploadFile, File, HTTPException
from pydantic import BaseModel
from app import database as db
from app.config import AppConfig

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/binlog")
async def get_binlog_info():
    rows = await db.fetch_all("SHOW BINARY LOGS")
    return {"binlogs": rows}


class PurgeRequest(BaseModel):
    before: str = ""  # binlog name to purge up to


@router.post("/binlog/purge")
async def purge_binlog(req: PurgeRequest):
    if req.before:
        await db.execute(f"PURGE BINARY LOGS TO '{req.before}'")
    else:
        await db.execute("PURGE BINARY LOGS BEFORE NOW()")
    return {"success": True}


# ── undo tablespace management ──

@router.get("/undo")
async def get_undo_info():
    rows = await db.fetch_all(
        "SELECT NAME, STATE, ROUND(FILE_SIZE/1024/1024, 2) AS size_mb "
        "FROM information_schema.INNODB_TABLESPACES WHERE NAME LIKE '%undo%'"
    )
    return {"undo_logs": rows}


@router.post("/undo/purge")
async def purge_undo(body: dict):
    """清除(收缩) undo 表空间：关闭→轮询大小→激活。

    流程：SET INACTIVE → 每隔 3s 查 size_mb（最多 4 次：初次+3 次重试）；
    size_mb <= 18 视为已收缩到 ~16M，立即 SET ACTIVE 并返回；
    仍未达标也恢复 ACTIVE，避免 undo 表空间长期不可用。
    """
    name = (body.get("name") or "").strip()
    # 仅允许含 undo 的合法标识符（innodb_undo_002 / undo_003 等，防注入）
    if not (re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) and "undo" in name.lower()):
        raise HTTPException(400, detail="无效的 undo 表空间名")

    try:
        await db.execute(f"ALTER UNDO TABLESPACE {name} SET INACTIVE")
    except Exception as e:
        raise HTTPException(400, detail=f"关闭失败: {e}")

    size_mb = None
    shrunk = False
    for _ in range(4):
        await asyncio.sleep(3)
        row = await db.fetch_one(
            "SELECT ROUND(FILE_SIZE/1024/1024, 2) AS size_mb "
            "FROM information_schema.INNODB_TABLESPACES WHERE NAME=%s",
            (name,),
        )
        v = row.get("size_mb") if row else None
        size_mb = float(v) if v is not None else None
        if size_mb is not None and size_mb <= 18:
            shrunk = True
            break

    try:
        await db.execute(f"ALTER UNDO TABLESPACE {name} SET ACTIVE")
    except Exception as e:
        raise HTTPException(400, detail=f"激活失败: {e}")

    return {
        "success": True,
        "name": name,
        "size_mb": size_mb,
        "shrunk": shrunk,
        "message": f"已收缩到 {size_mb}M" if shrunk else f"未达目标，当前 {size_mb}M",
    }


@router.post("/execute-sql")
async def execute_sql(site: str = Query(...), file: UploadFile = File(...)):
    config = AppConfig.load()
    db_name = config.db_name(site)
    mc = config.mysql

    suffix = os.path.splitext(file.filename or "import.sql")[1] or ".sql"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cmd = [
            "mysql",
            f"--host={mc.host}", f"--port={mc.port}",
            f"--user={mc.user}", f"--password={mc.password}",
            "--default-character-set=utf8mb4", "--skip-ssl",
            db_name,
        ]
        with open(tmp_path, "r", encoding="utf-8") as f:
            proc = subprocess.run(cmd, stdin=f, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise HTTPException(400, detail=f"SQL执行失败: {proc.stderr[:500]}")
    finally:
        os.unlink(tmp_path)

    return {"success": True, "message": f"SQL文件已执行到数据库 {db_name}"}
