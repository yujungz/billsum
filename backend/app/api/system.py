"""System API - binlog management and SQL execution."""

import os
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
