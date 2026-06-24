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


class CondConfig(BaseModel):
    source: CondEndpoint = CondEndpoint()
    destination: CondEndpoint = CondEndpoint()


# ---- defaults per the spec -------------------------------------------------

def _default_source() -> CondEndpoint:
    return CondEndpoint(
        deploy_type="local",
        run_mode="docker",
        os_type="windows",
        db=CondDB(password="123456", db_name="shadow_manager"),
    )


def _default_destination() -> CondEndpoint:
    return CondEndpoint(
        deploy_type="remote",
        run_mode="docker",
        os_type="linux",
        ssh=CondSSH(auth_method="key", user="root", port=22, remote_path="~/data/"),
        db=CondDB(password="burncloud123456qwe", db_name="shadow_manager"),
    )


def default_config() -> CondConfig:
    return CondConfig(source=_default_source(), destination=_default_destination())


# ---- load / save -----------------------------------------------------------

def load() -> CondConfig:
    """Load conduction config; fall back to defaults if missing/corrupt."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # merge over defaults so new fields are filled when schema grows
            base = default_config().model_dump()
            base.update(data or {})
            return CondConfig(**base)
        except Exception:
            # corrupt file → don't crash the whole feature; return defaults
            return default_config()
    return default_config()


def save(cfg: CondConfig) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg.model_dump(), f, ensure_ascii=False, indent=2)
