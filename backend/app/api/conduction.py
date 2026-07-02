"""数据传导 API — config CRUD, connection tests, table listing, background transfer.

Independent router; mirrors transfer.py (async task + task-status) and
settings_api.py (connection tests). Does not touch existing modules.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services import conduction_config
from app.services import conduction_service
from app.services.conduction_config import CondConfig, CondEndpoint

router = APIRouter(prefix="/api/conduction", tags=["conduction"])


class StartRequest(BaseModel):
    source: CondEndpoint
    destination: CondEndpoint
    skip_import: bool = False


@router.get("/config")
async def get_config():
    return conduction_config.load().model_dump()


@router.put("/config")
async def put_config(cfg: CondConfig):
    # sanitize protects the built-in default group (always first, unmodifiable)
    conduction_config.save(conduction_config.sanitize(cfg))
    return {"success": True}


@router.post("/test-ssh")
async def test_ssh(ep: CondEndpoint):
    ok, msg = conduction_service.test_ssh(ep)
    return {"success": ok, "message": msg}


@router.post("/test-db")
async def test_db(ep: CondEndpoint):
    """Test DB connection; on success also return the table list."""
    ok, msg, tables = conduction_service.test_db(ep)
    return {"success": ok, "message": msg, "tables": tables}


@router.post("/refresh-tables")
async def refresh_tables(ep: CondEndpoint):
    """Re-fetch table names for the table-selection dialog's 刷新 button."""
    try:
        tables = conduction_service.fetch_tables(ep)
        return {"success": True, "tables": tables}
    except Exception as e:
        return {"success": False, "tables": [], "message": str(e)}


@router.post("/start")
async def start(req: StartRequest):
    src = req.source
    if not src.all_checked and not src.selected_tables:
        raise HTTPException(400, detail="请至少选择一张表，或勾选「全部」按整库备份")
    task_id = conduction_service.start_task(src, req.destination, req.skip_import)
    return {"task_id": task_id}


@router.get("/task-status")
async def task_status(task_id: str):
    result = conduction_service.get_task_status(task_id)
    if not result:
        raise HTTPException(404, detail="Task not found")
    return result


@router.get("/download")
async def download(task_id: str):
    res = conduction_service.get_tgz(task_id)
    if not res:
        raise HTTPException(404, detail="打包文件不存在或已被清理")
    path, name = res
    return FileResponse(path, filename=name, media_type="application/gzip")
