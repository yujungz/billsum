"""SQL templates converted from old2new.sql and uptnew.sql, parameterized by table name."""


def sql_old2new(tbn_new: str) -> list[str]:
    """Generate SQL statements to create the processed log table from the raw orig table.
    Corresponds to old2new.sql logic."""
    tbn_old = f"{tbn_new}orig"
    stmts: list[str] = []

    stmts.append(f"DROP TABLE IF EXISTS `{tbn_new}`")

    stmts.append(f"""CREATE TABLE `{tbn_new}` AS SELECT l.id, l.user_id,l.username,l.created_at,
    DATE_FORMAT(FROM_UNIXTIME(l.created_at+28800), '%Y-%m-%d %H:%i:%s') AS `created__time`,
    l.type,l.token_id,l.token_name,l.model_name,l.quota,l.prompt_tokens,l.completion_tokens,l.use_time,
    channel_id,l.channel_name,l.`group`,0 as windup_type,
    0.000000 as prompt_price,0.000000 as completion_price,0.000000 as cache_price,
    0.000000 as cache_creation_price,0.000000 as cache_creation_5M_price,
    '' as us_salesperson, '' as us_salesperson1,'' as us_remark,0.000000 as us_discount,
    '' as cn_buyer,'' as cn_buyer1,'' as down_site,'' as cn_supplier,'' as cn_supplier1,
    0.000000 as cn_discount,0.000000 as cn_discount_orig,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_creation_tokens')) AS DECIMAL(18,6)) else 0 END,0) as cache_creation_tokens,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_creation_tokens_5m')) AS DECIMAL(18,6)) else 0 END,0) as cache_creation_tokens_5m,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_tokens')) AS DECIMAL(18,6)) else 0 END,0) as cache_tokens,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.model_ratio')) AS DECIMAL(18,6)) else 0 END,0) as model_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.group_ratio')) AS DECIMAL(18,6)) else 0 END,0) as group_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.completion_ratio')) AS DECIMAL(18,6)) else 0 END,0) as completion_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_ratio')) AS DECIMAL(18,6)) else 0 END,0) as cache_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_creation_ratio')) AS DECIMAL(18,6)) else 0 END,0) as cache_creation_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.cache_creation_ratio_5m')) AS DECIMAL(18,6)) else 0 END,0) as cache_creation_ratio_5m,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.user_group_ratio')) AS DECIMAL(18,6)) else 0 END,0) as user_group_ratio,
    IFNULL(CASE WHEN JSON_VALID(l.other) THEN JSON_UNQUOTE(JSON_EXTRACT(l.other, '$.expr_b64')) ELSE NULL END, NULL) as expr_b64
    FROM `{tbn_old}` l""")

    stmts.append(f"""ALTER TABLE `{tbn_new}`
    MODIFY COLUMN channel_name varchar(250) NULL,
    MODIFY COLUMN us_salesperson varchar(80) NULL,
    MODIFY COLUMN us_salesperson1 varchar(80) NULL,
    MODIFY COLUMN us_remark varchar(250) NULL,
    MODIFY COLUMN us_discount decimal(7,6) NULL,
    MODIFY COLUMN down_site varchar(80) NULL,
    MODIFY COLUMN cn_buyer varchar(80) NULL,
    MODIFY COLUMN cn_buyer1 varchar(80) NULL,
    MODIFY COLUMN cn_supplier varchar(80) NULL,
    MODIFY COLUMN cn_supplier1 varchar(80) NULL,
    MODIFY COLUMN cn_discount decimal(10,6) NULL,
    MODIFY COLUMN cn_discount_orig decimal(10,6) NULL,
    MODIFY COLUMN cache_creation_tokens decimal(21,0) NULL,
    MODIFY COLUMN cache_creation_tokens_5m decimal(21,0) NULL,
    MODIFY COLUMN cache_tokens decimal(21,0) NULL,
    MODIFY COLUMN prompt_price decimal(18,6) NULL,
    MODIFY COLUMN completion_price decimal(18,6) NULL,
    MODIFY COLUMN cache_price decimal(18,6) NULL,
    MODIFY COLUMN cache_creation_price decimal(18,6) NULL,
    MODIFY COLUMN cache_creation_5M_price decimal(18,6) NULL,
    MODIFY COLUMN model_ratio decimal(18,6) NULL,
    MODIFY COLUMN group_ratio decimal(18,6) NULL,
    MODIFY COLUMN completion_ratio decimal(18,6) NULL,
    MODIFY COLUMN cache_ratio decimal(18,6) NULL,
    MODIFY COLUMN cache_creation_ratio decimal(18,6) NULL,
    MODIFY COLUMN cache_creation_ratio_5m decimal(18,6) NULL,
    MODIFY COLUMN user_group_ratio decimal(18,6) NULL,
    MODIFY COLUMN expr_b64 text NULL""")

    # composite index for sorting
    idx_sort = f"{tbn_new}_idx_sort"
    stmts.append(f"CREATE INDEX `{idx_sort}` ON `{tbn_new}`(created_at DESC, id DESC)")

    # composite index for join queries
    idx_sum = f"{tbn_new}_idx_sum_join"
    stmts.append(f"CREATE INDEX `{idx_sum}` ON `{tbn_new}`(created_at,prompt_tokens,completion_tokens,use_time,quota)")

    # single field indexes
    for col in ["id", "user_id", "username", "token_id", "channel_id", "windup_type", "us_discount", "cn_discount", "token_name", "channel_name", "us_salesperson", "cn_buyer1", "cn_supplier1", "group"]:
        idx_name = f"{tbn_new}_idx_{col}"
        stmts.append(f"CREATE INDEX `{idx_name}` ON `{tbn_new}`(`{col}`)")

    return stmts


def sql_uptnew(tbn_new: str, mode: str = "full") -> list[str]:
    """Generate SQL to fill the processed log table with sales/buyer info.
    mode: 'full' (wzg/pinova/ai), 'simple' (csp), 'minimal' (qn/digitalcloud)"""
    stmts: list[str] = []

    if mode == "minimal":
        return stmts

    # index ex_users and ex_channels (and ex_tokens for full mode)
    for tbl in ["ex_users", "ex_channels"] + (["ex_tokens"] if mode == "full" else []):
        idx_name = f"{tbl}_idx_id"
        stmts.append(f"CREATE INDEX `{idx_name}` ON `{tbl}`(id)")

    t = tbn_new
    if mode == "full":
        stmts.append(f"""UPDATE `{t}`
            LEFT JOIN ex_users ON `{t}`.user_id = ex_users.id
            LEFT JOIN ex_tokens ON `{t}`.token_id = ex_tokens.id
            LEFT JOIN ex_channels ON `{t}`.channel_id = ex_channels.id
            LEFT JOIN channels ON `{t}`.channel_id = channels.id
            SET
            `{t}`.us_salesperson = ex_users.seller,
            `{t}`.us_salesperson1 = ex_users.seller,
            `{t}`.us_remark = ex_users.remark,
            `{t}`.us_discount = CASE WHEN ex_tokens.discount<1.0 THEN ex_tokens.discount ELSE ex_users.discount END,
            `{t}`.cn_buyer = ex_channels.buyer,
            `{t}`.cn_buyer1 = ex_channels.buyer,
            `{t}`.cn_supplier = ex_channels.supplier,
            `{t}`.cn_supplier1 = ex_channels.supplier,
            `{t}`.cn_discount = ex_channels.discount,
            `{t}`.cn_discount_orig = ex_channels.discount_orig,
            `{t}`.channel_name = COALESCE(ex_channels.name, channels.name),
            `{t}`.prompt_price = `{t}`.model_ratio * 2,
            `{t}`.completion_price = `{t}`.model_ratio * 2 * `{t}`.completion_ratio,
            `{t}`.cache_price = `{t}`.model_ratio * 2 * `{t}`.cache_ratio,
            `{t}`.cache_creation_price = `{t}`.model_ratio * 2 * `{t}`.cache_creation_ratio,
            `{t}`.cache_creation_5M_price = `{t}`.model_ratio * 2 * `{t}`.cache_creation_ratio_5m""")
    elif mode == "simple":
        stmts.append(f"""UPDATE `{t}`
            LEFT JOIN ex_users ON `{t}`.user_id = ex_users.id
            LEFT JOIN ex_channels ON `{t}`.channel_id = ex_channels.id
            LEFT JOIN channels ON `{t}`.channel_id = channels.id
            SET
            `{t}`.us_salesperson = ex_users.seller,
            `{t}`.us_salesperson1 = ex_users.seller,
            `{t}`.us_remark = ex_users.remark,
            `{t}`.us_discount = ex_users.discount,
            `{t}`.cn_buyer = ex_channels.buyer,
            `{t}`.cn_buyer1 = ex_channels.buyer,
            `{t}`.cn_supplier = ex_channels.supplier,
            `{t}`.cn_supplier1 = ex_channels.supplier,
            `{t}`.cn_discount = ex_channels.discount,
            `{t}`.cn_discount_orig = ex_channels.discount_orig,
            `{t}`.channel_name = COALESCE(ex_channels.name, channels.name),
            `{t}`.prompt_price = `{t}`.model_ratio * 2,
            `{t}`.completion_price = `{t}`.model_ratio * 2 * `{t}`.completion_ratio,
            `{t}`.cache_price = `{t}`.model_ratio * 2 * `{t}`.cache_ratio,
            `{t}`.cache_creation_price = `{t}`.model_ratio * 2 * `{t}`.cache_creation_ratio,
            `{t}`.cache_creation_5M_price = `{t}`.model_ratio * 2 * `{t}`.cache_creation_ratio_5m""")

    return stmts


def sql_remote_export(
    site: str,
    container_name: str,
    db_name: str,
    password: str,
    log_name: str,
    time_begin: str,
    time_end: str,
    backup: int = 1,
) -> str:
    """Generate the remote bash command for exporting data (outdata.sh logic).

    NOTE: Do NOT use pipe (e.g. | sed) — the remote SSH server drops the
    connection after docker exec + mysql commands, which kills the pipe and
    loses buffered data.  Write mysqldump output directly to a file, then
    run sed in-place as a separate step.
    """
    cmd = f"""docker exec {container_name} mysqldump -uroot -p{password} \
--single-transaction --set-gtid-purged=OFF {db_name} logs \
--where="type=2 and created_at+28800 BETWEEN UNIX_TIMESTAMP('{time_begin}') AND UNIX_TIMESTAMP('{time_end}')" \
> ~/data/{site}/{log_name}.sql"""
    return cmd


def sql_remote_sed_rename(site: str, log_name: str) -> str:
    """In-place sed to rename table `logs` -> `{log_name}orig` in the dump file."""
    return f"sed -i 's/`logs`/`{log_name}orig`/g' ~/data/{site}/{log_name}.sql"


def sql_remote_export_base_tables(
    container_name: str,
    db_name: str,
    password: str,
    site: str,
) -> list[str]:
    """Generate commands to export channels, users, tokens."""
    cmds = []
    for tbl in ["channels", "users", "tokens"]:
        cmds.append(
            f"docker exec {container_name} mysqldump -uroot -p{password} "
            f"--single-transaction --set-gtid-purged=OFF {db_name} {tbl} "
            f"> ~/data/{site}/{tbl}.sql"
        )
    return cmds
