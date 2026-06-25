"""数据传导 (DB→DB backup/transfer) — independent config store.

Persisted to DATA_DIR/conduction.json so the conduction feature does NOT touch
app/config.py, AppConfig, or the shared config.json used by the rest of the app.
"""

import json
import os
from pathlib import Path
from pydantic import BaseModel

# Reuse the same DATA_DIR location as the rest of the app, but a separate file.
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
CONFIG_FILE = DATA_DIR / "conduction.json"


class CondSSH(BaseModel):
    auth_method: str = "key"            # "key" | "password"
    password: str = ""                  # used when auth_method == "password"
    key_path: str = ""                  # path inside the backend host (used when auth_method == "key")
    user: str = "root"
    host: str = ""
    port: int = 22
    # temp dir on the remote for export files; default by os_type if left blank
    remote_path: str = ""


class CondDB(BaseModel):
    user: str = "root"
    password: str = ""
    db_name: str = "shadow_manager"
    container_name: str = ""            # docker run-mode
    host: str = ""                      # host run-mode ("服务器")
    port: int = 3306                    # host run-mode


class CondEndpoint(BaseModel):
    deploy_type: str = "local"          # "local" | "remote"
    run_mode: str = "docker"            # "docker" | "host"
    os_type: str = "linux"             # "linux" | "windows"
    ssh: CondSSH = CondSSH()
    db: CondDB = CondDB()
    # saved table selection + the "全部" flag from the picker dialog
    selected_tables: list[str] = []
    all_checked: bool = False


class CondGroup(BaseModel):
    name: str
    source: CondEndpoint
    destination: CondEndpoint


class CondConfig(BaseModel):
    groups: list[CondGroup] = []
    selected: str = "默认配置"


DEFAULT_GROUP_NAME = "默认配置"


def _host_segment(ep: CondEndpoint) -> str:
    """Hostname segment for group naming: local→localhost; remote→first dot-segment of ssh.host."""
    if ep.deploy_type == "local":
        return "localhost"
    h = (ep.ssh.host or "").strip()
    if not h:
        return "remote"
    return h.split(".")[0]


def group_name(source: CondEndpoint, destination: CondEndpoint) -> str:
    """Auto-name a config group from both endpoints: 'srcHost:srcDb → dstHost:dstDb'."""
    return f"{_host_segment(source)}:{source.db.db_name} → {_host_segment(destination)}:{destination.db.db_name}"


# ---- defaults per the spec -------------------------------------------------

def _default_source() -> CondEndpoint:
    return CondEndpoint(
        deploy_type="remote",
        run_mode="docker",
        os_type="linux",
        ssh=CondSSH(
            auth_method="key",
            user="root",
            host="shadowdev.burncloud.cn",
            port=22,
            remote_path="~/data/",
            key_path="/app/data/ssh_keys/host20260311",
        ),
        db=CondDB(
            user="root",
            password="burncloud123456qwe",
            db_name="shadow_manager",
            container_name="shadow-manager-dev-mysql",
            host="localhost",
        ),
    )


def _default_destination() -> CondEndpoint:
    return CondEndpoint(
        deploy_type="local",
        run_mode="host",
        os_type="windows",
        db=CondDB(
            user="root",
            password="123456",
            db_name="shadow_manager",
            host="172.20.0.3",
            port=3306,
        ),
    )


def default_config() -> CondConfig:
    g = CondGroup(name=DEFAULT_GROUP_NAME, source=_default_source(), destination=_default_destination())
    return CondConfig(groups=[g], selected=DEFAULT_GROUP_NAME)


# ---- load / save -----------------------------------------------------------

def sanitize(cfg: CondConfig) -> CondConfig:
    """Ensure the built-in default group is present, first, and unmodifiable;
    ensure `selected` refers to an existing group."""
    default_grp = default_config().groups[0]
    cfg.groups = [g for g in cfg.groups if g.name != DEFAULT_GROUP_NAME]
    cfg.groups.insert(0, default_grp)
    # drop duplicates (keep first occurrence) beyond the default
    seen = {DEFAULT_GROUP_NAME}
    uniq = [cfg.groups[0]]
    for g in cfg.groups[1:]:
        if g.name not in seen:
            seen.add(g.name)
            uniq.append(g)
    cfg.groups = uniq
    if not cfg.selected or not any(g.name == cfg.selected for g in cfg.groups):
        cfg.selected = DEFAULT_GROUP_NAME
    return cfg


def load() -> CondConfig:
    """Load conduction config; fall back to defaults if missing/corrupt."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return sanitize(CondConfig(**(data or {})))
        except Exception:
            # corrupt file → don't crash the whole feature; return defaults
            return default_config()
    return default_config()


def save(cfg: CondConfig) -> None:
    sanitize(cfg)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, ensure_ascii=False, indent=2)
