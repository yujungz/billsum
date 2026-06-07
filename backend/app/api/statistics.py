"""Statistics API."""

import io

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel
import openpyxl
from openpyxl.styles import Font

from app.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


class StatsRequest(BaseModel):
    site: str
    table_name: str
    group_by: list[str] = []
    filters: dict | None = None
    show_zero: bool = True


@router.post("/query")
async def query_stats(req: StatsRequest):
    result = await stats_service.query_stats(
        req.site, req.table_name, req.group_by, req.filters, req.show_zero
    )
    return {"data": result}


@router.get("/distinct")
async def get_distinct(site: str = Query(...), table: str = Query(...), field: str = Query(...)):
    values = await stats_service.get_distinct_values(site, table, field)
    return {"values": values}


@router.post("/export")
async def export_stats(req: StatsRequest):
    result = await stats_service.query_stats(
        req.site, req.table_name, req.group_by, req.filters, req.show_zero
    )
    if not result:
        return Response(content=b"", status_code=204)

    # determine visible columns from data
    col_def = [
        ("period_month", "月份", 100),
        ("period_day", "日期", 110),
        ("user_id", "用户ID", 80),
        ("username", "用户名", 120),
        ("channel_id", "渠道ID", 80),
        ("channel_name", "渠道", 120),
        ("model_name", "模型", 160),
        ("call_count", "调用记录数", 100),
        ("input_tokens_m", "输入Token(M)", 130),
        ("input_cost", "输入费用", 110),
        ("output_tokens_m", "输出Token(M)", 130),
        ("output_cost", "输出费用", 110),
        ("cache_read_tokens_m", "读缓存Token(M)", 140),
        ("cache_read_cost", "读缓存费用", 110),
        ("cache_create_tokens_m", "创缓存Token(M)", 140),
        ("cache_create_cost", "创缓存费用", 110),
        ("cache_create_5m_tokens_m", "创缓存5M(M)", 120),
        ("cache_create_5m_cost", "创缓存5M费", 110),
        ("cache_use_tokens_m", "使用缓存Token(M)", 150),
        ("cache_total_cost", "缓存总费用", 110),
        ("total_tokens_m", "总消耗Token(M)", 140),
        ("total_cost", "消费额度", 110),
    ]
    visible = [(k, l, w) for k, l, w in col_def if any(r.get(k) is not None for r in result)]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stats"
    bold = Font(bold=True)
    for ci, (_, label, width) in enumerate(visible, 1):
        ws.cell(row=1, column=ci, value=label).font = bold
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = width
    for ri, row in enumerate(result, 2):
        for ci, (key, _, _) in enumerate(visible, 1):
            v = row.get(key)
            ws.cell(row=ri, column=ci, value=float(v) if v is not None and hasattr(v, "__float__") else v)

    buf = io.BytesIO()
    wb.save(buf)
    filename = f"{req.site}_{req.table_name}_stats.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
