"""数据传导 — pure command builders (no execution).

Two output shapes:
  * LOCAL  -> Python argv list[str]  (subprocess, no shell => passwords are safe)
  * REMOTE -> shell string           (run over SSH; redirects > < execute on the
                                      remote shell; values go through OS-aware quoting)

The service layer branches on `ep.deploy_type` and calls the matching builder.
All mysql/mysqldump commands include `--default-character-set=utf8mb4`.

Remote quoting notes:
  * linux   -> shlex.quote (POSIX single-quoting).
  * windows -> cmd.exe double-quoting (embedded " doubled).
  * Leading `~` in a path should be resolved to an absolute path by the caller
    (conduction_service.resolve_remote_path) BEFORE building commands, because
    quoting suppresses `~` expansion and SFTP does not expand `~` either. qpath
    still keeps a defensive `~` backstop for linux.
"""

import shlex

from app.services.conduction_config import CondEndpoint

CHARSET = "--default-character-set=utf8mb4"
MYSQL_BIN = "mysql"
DUMP_BIN = "mysqldump"


def _db(ep: CondEndpoint):
    return ep.db


def qval(ep: CondEndpoint, s) -> str:
    """Quote a value (user/password/host/port/db/table/SQL fragment) for the remote shell."""
    s = str(s)
    if ep.os_type == "windows":
        return '"' + s.replace('"', '""') + '"'
    return shlex.quote(s)


def qpath(ep: CondEndpoint, s) -> str:
    """Quote a filesystem path for the remote shell; preserve a leading ~ on linux."""
    s = str(s)
    if ep.os_type == "windows":
        return '"' + s.replace('"', '""') + '"'
    if s.startswith("~"):
        i = s.find("/")
        if i == -1:
            return s
        return s[:i + 1] + shlex.quote(s[i + 1:])
    return shlex.quote(s)


# ============================================================ LOCAL (argv) ===

def _local_client_argv(ep: CondEndpoint, tool: str) -> list[str]:
    """Prefix argv for a mysql/mysqldump client running where the backend runs.

    Both modes connect over TCP (the backend process has the mysql/mysqldump
    CLI but typically NOT the `docker` CLI — e.g. the billsum-app container —
    so we do NOT shell out to `docker exec`):
      docker mode -> host = container_name (resolves on the docker network,
                     same pattern the rest of the app uses via MYSQL_HOST).
      host mode   -> host = the configured 服务器, port = db.port.
    """
    db = _db(ep)
    host = db.container_name if ep.run_mode == "docker" else db.host
    return [
        tool, CHARSET,
        f"--host={host}", f"--port={db.port}",
        f"--user={db.user}", f"--password={db.password}",
        "--skip-ssl",
    ]


def local_dump_argv(ep: CondEndpoint, full: bool, tables: list[str]) -> list[str]:
    """mysqldump argv (stdout streamed by caller via Popen(stdout=f))."""
    argv = _local_client_argv(ep, DUMP_BIN)
    argv += ["--single-transaction", "--set-gtid-purged=OFF", "--no-tablespaces"]
    db = _db(ep)
    if full:
        argv += ["--routines", "--triggers", "--events",
                 "--add-drop-database", "--databases", db.db_name]
    else:
        argv += [db.db_name] + list(tables)
    return argv


def local_import_argv(ep: CondEndpoint, db_name: str, full: bool) -> list[str]:
    """mysql import argv (stdin streamed by caller via Popen(stdin=f)).

    full dump carries its own `USE`/`CREATE DATABASE`, so no positional db.
    selective dump has none, so the target db is passed positionally.
    """
    argv = _local_client_argv(ep, MYSQL_BIN)
    if not full:
        argv.append(db_name)
    return argv


def local_show_tables_argv(ep: CondEndpoint) -> list[str]:
    argv = _local_client_argv(ep, MYSQL_BIN)
    argv += ["-e", "SHOW TABLES", _db(ep).db_name]
    return argv


def local_ping_argv(ep: CondEndpoint) -> list[str]:
    """Test server connectivity only — no db arg."""
    return _local_client_argv(ep, MYSQL_BIN) + ["-e", "SELECT 1"]


def local_show_databases_argv(ep: CondEndpoint) -> list[str]:
    """List databases on the server — no db arg."""
    return _local_client_argv(ep, MYSQL_BIN) + ["-e", "SHOW DATABASES"]


def local_create_db_argv(ep: CondEndpoint, db_name: str) -> list[str]:
    argv = _local_client_argv(ep, MYSQL_BIN)
    argv += ["-e", f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                   "CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"]
    return argv


# =========================================================== REMOTE (string) ==

def _remote_client_str(ep: CondEndpoint, tool: str, interactive: bool = False) -> str:
    """Shell-string prefix executed on the remote host via SSH."""
    db = _db(ep)
    if ep.run_mode == "docker":
        i = "-i " if interactive else ""
        return (f"docker exec {i}{qval(ep, db.container_name)} {tool} {CHARSET} "
                f"--user={qval(ep, db.user)} --password={qval(ep, db.password)}")
    return (f"{tool} {CHARSET} "
            f"--host={qval(ep, db.host)} --port={qval(ep, db.port)} "
            f"--user={qval(ep, db.user)} --password={qval(ep, db.password)} --skip-ssl")


def remote_dump_cmd(ep: CondEndpoint, full: bool, tables: list[str], out_file: str) -> str:
    base = _remote_client_str(ep, DUMP_BIN)
    flags = "--single-transaction --set-gtid-purged=OFF --no-tablespaces"
    db = _db(ep)
    if full:
        tail = (f"--routines --triggers --events --add-drop-database "
                f"--databases {qval(ep, db.db_name)}")
    else:
        tlist = " ".join(qval(ep, t) for t in tables)
        tail = (qval(ep, db.db_name) + " " + tlist).strip()
    return f"{base} {flags} {tail} > {qpath(ep, out_file)}"


def remote_import_cmd(ep: CondEndpoint, db_name: str, full: bool, in_file: str) -> str:
    base = _remote_client_str(ep, MYSQL_BIN, interactive=True)
    tail = "" if full else f" {qval(ep, db_name)}"
    return f"{base}{tail} < {qpath(ep, in_file)}"


def remote_show_tables_cmd(ep: CondEndpoint) -> str:
    base = _remote_client_str(ep, MYSQL_BIN)
    return f"{base} -e {qval(ep, 'SHOW TABLES')} {qval(ep, _db(ep).db_name)}"


def remote_ping_cmd(ep: CondEndpoint) -> str:
    """Test server connectivity only — no db arg."""
    return f"{_remote_client_str(ep, MYSQL_BIN)} -e {qval(ep, 'SELECT 1')}"


def remote_show_databases_cmd(ep: CondEndpoint) -> str:
    """List databases on the server — no db arg."""
    return f"{_remote_client_str(ep, MYSQL_BIN)} -e {qval(ep, 'SHOW DATABASES')}"


def remote_create_db_cmd(ep: CondEndpoint, db_name: str) -> str:
    base = _remote_client_str(ep, MYSQL_BIN)
    sql = f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
    return f"{base} -e {qval(ep, sql)}"


def remote_tar_create_cmd(ep: CondEndpoint, tgz_path: str, work_dir: str, filename: str) -> str:
    return f"tar -czf {qpath(ep, tgz_path)} -C {qpath(ep, work_dir)} {qval(ep, filename)}"


def remote_tar_extract_cmd(ep: CondEndpoint, tgz_path: str, work_dir: str) -> str:
    return f"tar -xzf {qpath(ep, tgz_path)} -C {qpath(ep, work_dir)}"


def remote_mkdir_cmd(ep: CondEndpoint, path: str) -> str:
    if ep.os_type == "windows":
        return f"if not exist {qpath(ep, path)} mkdir {qpath(ep, path)}"
    return f"mkdir -p {qpath(ep, path)}"
