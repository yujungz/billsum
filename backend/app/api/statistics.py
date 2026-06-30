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


def _col_width(label: str) -> float:
    """Compute a reasonable column width for the label text.
    Chinese chars ≈ 2× Latin char width in openpyxl units."""
    w = len(label) * 1.8 + 2
    return max(w, 8)


@router.post("/export")
async def export_stats(req: StatsRequest):
    result = await stats_service.query_stats(
        req.site, req.table_name, req.group_by, req.filters, req.show_zero
    )
    if not result:
        return Response(content=b"", status_code=204)

    # determine visible columns from data
    col_def = [
        ("period_month", "月份"),
        ("period_day", "日期"),
        ("user_id", "用户ID"),
        ("username", "用户名"),
        ("channel_id", "渠道ID"),
        ("channel_name", "渠道"),
        ("model_name", "模型"),
        ("call_count", "调用记录数"),
        ("input_tokens_m", "输入Token(M)"),
        ("input_cost", "输入费用"),
        ("output_tokens_m", "输出Token(M)"),
        ("output_cost", "输出费用"),
        ("cache_read_tokens_m", "读缓存Token(M)"),
        ("cache_read_cost", "读缓存费用"),
        ("cache_create_tokens_m", "创缓存Token(M)"),
        ("cache_create_cost", "创缓存费用"),
        ("cache_create_5m_tokens_m", "创缓存5M(M)"),
        ("cache_create_5m_cost", "创缓存5M费"),
        ("cache_use_tokens_m", "使用缓存Token(M)"),
        ("cache_total_cost", "缓存总费用"),
        ("total_tokens_m", "总消耗Token(M)"),
        ("total_cost", "消费额度"),
    ]
    visible = [(k, l) for k, l in col_def if any(r.get(k) is not None for r in result)]
    visible_keys = [k for k, _ in visible]

    # sort by date column descending
    if req.group_by:
        date_col = "period_day" if "day" in req.group_by else "period_month"
        result.sort(key=lambda r: (r.get(date_col) or ""), reverse=True)

    # columns that should NOT be summed (IDs, names, dates)
    no_sum = {"period_month", "period_day", "user_id", "username",
              "channel_id", "channel_name", "model_name"}
    sum_cols = [(ik, k) for ik, (k, l) in enumerate(visible) if k not in no_sum]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stats"
    bold = Font(bold=True)
    for ci, (_, label) in enumerate(visible, 1):
        ws.cell(row=1, column=ci, value=label).font = bold
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = _col_width(label)
    for ri, row in enumerate(result, 2):
        for ci, (key, _) in enumerate(visible, 1):
            v = row.get(key)
            ws.cell(row=ri, column=ci, value=float(v) if v is not None and hasattr(v, "__float__") else v)

    # total row
    last_data_row = len(result) + 1
    total_row = ["合计"] + [""] * (len(visible) - 1)
    for ci, key in sum_cols:
        total = 0
        for row in result:
            v = row.get(key)
            if v is not None and hasattr(v, "__float__"):
                total += float(v)
        if total:
            total_row[ci] = total
    ws.append([])
    ws.append(total_row)

    buf = io.BytesIO()
    wb.save(buf)
    filename = f"{req.site}_{req.table_name}_stats.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
