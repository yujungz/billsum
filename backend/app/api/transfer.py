"""Transfer API - remote export, download, import, fill, one-click."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import transfer_service

router = APIRouter(prefix="/api/transfer", tags=["transfer"])


class TransferRequest(BaseModel):
    site: str
    period_type: str  # "monthly" or "range"
    ym: str = ""
    date_start: str = ""
    date_end: str = ""
    tables: list[str] = ["logs", "channels", "tokens", "users"]
    table_name: str = ""


@router.post("/export")
async def export_remote(req: TransferRequest):
    result = await transfer_service.export_remote(
        req.site, req.period_type, req.ym, req.date_start, req.date_end, req.tables
    )
    if not result["success"]:
        raise HTTPException(400, detail=result.get("error", "Export failed"))
    return result


@router.post("/download")
async def download_remote(req: TransferRequest):
    result = await transfer_service.download_remote(
        req.site, req.period_type, req.ym, req.date_start, req.date_end, req.tables
    )
    if not result["success"]:
        raise HTTPException(400, detail=result.get("error", "Download failed"))
    return result


@router.post("/import")
async def import_local(req: TransferRequest):
    log_name = transfer_service._log_name(req.period_type, req.ym, req.date_start, req.date_end)
    result = await transfer_service.import_local(req.site, log_name, req.tables)
    if not result["success"]:
        raise HTTPException(400, detail=result.get("error", "Import failed"))
    return result


@router.post("/fill")
async def fill_local(req: TransferRequest):
    log_name = transfer_service._log_name(req.period_type, req.ym, req.date_start, req.date_end)
    result = await transfer_service.fill_local(req.site, log_name)
    if not result["success"]:
        raise HTTPException(400, detail=result.get("error", "Fill failed"))
    return result


@router.post("/all")
async def run_all(req: TransferRequest):
    results = await transfer_service.run_all(
        req.site, req.period_type, req.ym, req.date_start, req.date_end, req.tables
    )
    return {"results": results}


@router.post("/async-all")
async def async_all(req: TransferRequest):
    task_id = await transfer_service.start_task(
        req.site, req.period_type, req.ym, req.date_start, req.date_end, req.tables
    )
    return {"task_id": task_id}


@router.get("/task-status")
async def task_status(task_id: str):
    result = transfer_service.get_task_status(task_id)
    if not result:
        raise HTTPException(404, detail="Task not found")
    return result


@router.post("/uptcustomer")
async def uptcustomer(req: TransferRequest):
    result = await transfer_service.uptcustomer(req.site, req.table_name or None)
    if not result["success"]:
        raise HTTPException(400, detail=result.get("error", "Uptcustomer failed"))
    return result
