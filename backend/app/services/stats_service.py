"""Statistics service - calculates costs from log tables."""

from app import database as db
from app.config import AppConfig


async def query_stats(
    site: str,
    table_name: str,
    group_by: list[str] | None = None,
    filters: dict | None = None,
    show_zero: bool = True,
    show_channel_name: bool = True,
) -> list[dict]:
    """Query statistics from a log table.

    group_by options: "month", "day", "user", "channel", "model", "token", "group"
    filters: {user_id, channel_id, model_name, username, channel_name}
    show_zero: if False, filter out records with zero total_cost
    show_channel_name: if False, channel granularity skips channel_name column
    """
    config = AppConfig.load()
    db_name = config.db_name(site)

    # build group by fields
    group_fields = []
    select_fields = []
    if group_by:
        for g in group_by:
            if g == "month":
                group_fields.append("DATE_FORMAT(FROM_UNIXTIME(l.created_at+28800), '%%Y-%%m')")
                select_fields.append("DATE_FORMAT(FROM_UNIXTIME(l.created_at+28800), '%%Y-%%m') AS period_month")
            elif g == "day":
                group_fields.append("DATE_FORMAT(FROM_UNIXTIME(l.created_at+28800), '%%Y-%%m-%%d')")
                select_fields.append("DATE_FORMAT(FROM_UNIXTIME(l.created_at+28800), '%%Y-%%m-%%d') AS period_day")
            elif g == "user":
                group_fields.append("l.user_id")
                group_fields.append("l.username")
                select_fields.append("l.user_id")
                select_fields.append("l.username")
            elif g == "channel":
                group_fields.append("l.channel_id")
                select_fields.append("l.channel_id")
                if show_channel_name:
                    group_fields.append("l.channel_name")
                    select_fields.append("l.channel_name")
            elif g == "model":
                group_fields.append("l.model_name")
                select_fields.append("l.model_name")
            elif g == "token":
                group_fields.append("l.token_name")
                select_fields.append("l.token_name")
            elif g == "group":
                group_fields.append("l.`group`")
                select_fields.append("l.`group` AS group_name")
            elif g == "buyer":
                group_fields.append("l.cn_buyer1")
                select_fields.append("l.cn_buyer1 AS cn_buyer1")
            elif g == "supplier":
                group_fields.append("l.cn_supplier1")
                select_fields.append("l.cn_supplier1 AS cn_supplier1")
            elif g == "salesperson":
                group_fields.append("l.us_salesperson")
                select_fields.append("l.us_salesperson AS us_salesperson")

    group_clause = f"GROUP BY {', '.join(group_fields)}" if group_fields else ""

    select_part = ", ".join(select_fields) + ", " if select_fields else ""

    # 1H cache = cache_creation - cache_creation_5m (only positive part)
    _1H = "CASE WHEN l.cache_creation_tokens - l.cache_creation_tokens_5m > 0 THEN l.cache_creation_tokens - l.cache_creation_tokens_5m ELSE 0 END"

    sql = f"""SELECT
    {select_part}
    COUNT(*) AS call_count,
    SUM(l.prompt_tokens) AS input_tokens,
    ROUND(MAX(l.model_ratio)*2, 6) AS input_unit_price,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*l.prompt_tokens)/1000000, 6) AS input_cost,
    SUM(l.completion_tokens) AS output_tokens,
    ROUND(MAX(l.model_ratio*2*l.completion_ratio), 6) AS output_unit_price,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*l.completion_ratio*l.completion_tokens)/1000000, 6) AS output_cost,
    SUM(l.cache_tokens) AS cache_read_tokens,
    ROUND(MAX(l.model_ratio*2*l.cache_ratio), 6) AS cache_read_unit_price,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*l.cache_ratio*l.cache_tokens)/1000000, 6) AS cache_read_cost,
    SUM(l.cache_creation_tokens_5m) AS cache_create_5m_tokens,
    ROUND(MAX(l.model_ratio)*2*1.25, 6) AS cache_create_5m_unit_price,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*1.25*l.cache_creation_tokens_5m)/1000000, 6) AS cache_create_5m_cost,
    SUM({_1H}) AS cache_create_1h_tokens,
    ROUND(MAX(l.model_ratio)*2*2.00, 6) AS cache_create_1h_unit_price,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*2.00*{_1H})/1000000, 6) AS cache_create_1h_cost,
    SUM(GREATEST(l.cache_creation_tokens, l.cache_creation_tokens_5m)) AS cache_create_tokens,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*(1.25*l.cache_creation_tokens_5m
        + 2.00*{_1H}))/1000000, 6) AS cache_create_cost,
    SUM(GREATEST(l.cache_creation_tokens, l.cache_creation_tokens_5m) + l.cache_tokens) AS cache_total_tokens,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*(1.25*l.cache_creation_tokens_5m + l.cache_ratio*l.cache_tokens
        + 2.00*{_1H}))/1000000, 6) AS cache_total_cost,
    SUM(GREATEST(l.cache_creation_tokens, l.cache_creation_tokens_5m) + l.cache_tokens + l.completion_tokens + l.prompt_tokens) AS total_tokens,
    ROUND(SUM(l.group_ratio*l.model_ratio*2*(1.25*l.cache_creation_tokens_5m + l.cache_ratio*l.cache_tokens
        + l.completion_ratio*l.completion_tokens + l.prompt_tokens
        + 2.00*{_1H}))/1000000, 6) AS total_cost,
    SUM(l.quota)*2/1000000 AS platform_quota
    FROM `{table_name}` l"""

    # build where
    conditions = ["l.windup_type < 2"]
    params = []
    if filters:
        if filters.get("user_id"):
            conditions.append("l.user_id = %s")
            params.append(filters["user_id"])
        if filters.get("username"):
            conditions.append("l.username = %s")
            params.append(filters["username"])
        if filters.get("channel_id"):
            conditions.append("l.channel_id = %s")
            params.append(filters["channel_id"])
        if filters.get("channel_name"):
            conditions.append("l.channel_name = %s")
            params.append(filters["channel_name"])
        if filters.get("model_name"):
            conditions.append("l.model_name = %s")
            params.append(filters["model_name"])
        if filters.get("cn_buyer1"):
            conditions.append("l.cn_buyer1 = %s")
            params.append(filters["cn_buyer1"])
        if filters.get("cn_supplier1"):
            conditions.append("l.cn_supplier1 = %s")
            params.append(filters["cn_supplier1"])
        if filters.get("us_salesperson"):
            conditions.append("l.us_salesperson = %s")
            params.append(filters["us_salesperson"])
        if filters.get("date_start"):
            conditions.append("l.created_at >= UNIX_TIMESTAMP(%s) - 28800")
            params.append(f"{filters['date_start']} 00:00:00")
        if filters.get("date_end"):
            conditions.append("l.created_at <= UNIX_TIMESTAMP(%s) - 28800")
            params.append(f"{filters['date_end']} 23:59:59")

    # add HAVING clause for zero-cost filter at SQL level
    having_clause = ""
    if not show_zero:
        having_clause = "HAVING total_cost > 0"

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"{sql} {where_clause} {group_clause} {having_clause}"

    rows = await db.fetch_all(sql, params if params else None, db=db_name)

    # convert Decimal to float for JSON serialization
    result = []
    for row in rows:
        r = {}
        for k, v in row.items():
            if v is not None and hasattr(v, "__float__"):
                r[k] = float(v)
            else:
                r[k] = v
        result.append(r)

    return result


async def get_distinct_values(site: str, table_name: str, field: str) -> list:
    """Get distinct values for a field, used for filter dropdowns."""
    config = AppConfig.load()
    db_name = config.db_name(site)
    rows = await db.fetch_all(
        f"SELECT DISTINCT `{field}` FROM `{table_name}` WHERE `{field}` IS NOT NULL AND `{field}` != '' ORDER BY `{field}`",
        db=db_name,
    )
    return [r[field] for r in rows]
