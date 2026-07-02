import json
import os
import time
from pathlib import Path
from pydantic import BaseModel


DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
CONFIG_FILE = DATA_DIR / "config.json"

SITES = ["ai", "csp", "pinova", "wzg", "qn", "digitalcloud", "wshk"]

DEFAULT_SSH_HOST = "shadow.burncloud.com"
DEFAULT_REMOTE_PASSWORD = "burncloud123456!qwf"
DEFAULT_KEY_PATH = "/ssh_keys/host20260311"

SITE_DEFAULTS = {
    "ai": {
        "ssh": {"host": DEFAULT_SSH_HOST, "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "backup_198.11.179.205-ai", "db_name": "new-api", "password": DEFAULT_REMOTE_PASSWORD},
        "uptnew_mode": "full",
    },
    "csp": {
        "ssh": {"host": DEFAULT_SSH_HOST, "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "backup_198.11.179.205-csp", "db_name": "new-api", "password": DEFAULT_REMOTE_PASSWORD},
        "uptnew_mode": "simple",
    },
    "pinova": {
        "ssh": {"host": DEFAULT_SSH_HOST, "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "backup_198.11.179.205-pinova", "db_name": "new-api", "password": DEFAULT_REMOTE_PASSWORD},
        "uptnew_mode": "full",
    },
    "wzg": {
        "ssh": {"host": DEFAULT_SSH_HOST, "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "backup_48.211.172.173-wzg", "db_name": "new-api", "password": DEFAULT_REMOTE_PASSWORD},
        "uptnew_mode": "full",
    },
    "qn": {
        "ssh": {"host": "120.26.136.61", "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "burncloud-mysql", "db_name": "new-api", "password": "abc123"},
        "uptnew_mode": "minimal",
    },
    "digitalcloud": {
        "ssh": {"host": DEFAULT_SSH_HOST, "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "backup_198.11.182.119-digitalcloud", "db_name": "new-api", "password": "abc123"},
        "uptnew_mode": "minimal",
    },
    "wshk": {
        "ssh": {"host": "wshk.burncloud.com", "user": "root", "key_path": DEFAULT_KEY_PATH},
        "remote_db": {"container_name": "main01-mysql", "db_name": "new-api", "password": "burncloud123456qwe"},
        "uptnew_mode": "full",
    },
}


class MySQLConfig(BaseModel):
    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "123456")
    container_name: str = os.getenv("MYSQL_CONTAINER", "test-mysql8")


class SSHRemoteConfig(BaseModel):
    host: str = ""
    port: int = 22
    user: str = "root"
    key_path: str = ""
    remote_path: str = "~/data/"
    backup: int = 1


class RemoteDBConfig(BaseModel):
    container_name: str = ""
    db_name: str = "new-api"
    password: str = ""


class BusinessConfig(BaseModel):
    purchase_commission_rate: float = 0.3
    sales_commission_rate: float = 0.3
    us_cny_rate: float = 6.91


class SiteConfig(BaseModel):
    name: str
    ssh: SSHRemoteConfig = SSHRemoteConfig()
    remote_db: RemoteDBConfig = RemoteDBConfig()
    uptnew_mode: str = "full"
    # uptnew_mode:
    #   "full"    - JOIN ex_users + ex_tokens + ex_channels (wzg/pinova/ai)
    #   "simple"  - JOIN ex_users + ex_channels, no ex_tokens (csp)
    #   "minimal" - only register table name (qn/digitalcloud)


class AppConfig(BaseModel):
    mysql: MySQLConfig = MySQLConfig()
    sites: dict[str, SiteConfig] = {}
    business: BusinessConfig = BusinessConfig()

    # class-level config cache
    _cache: "AppConfig | None" = None
    _cache_mtime: float = 0.0

    @classmethod
    def load(cls) -> "AppConfig":
        if CONFIG_FILE.exists():
            mtime = CONFIG_FILE.stat().st_mtime
            if cls._cache is not None and mtime == cls._cache_mtime:
                return cls._cache
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = cls(**data)
            # merge any missing sites (e.g. newly added code sites) into saved config
            for site in SITES:
                if site not in cfg.sites:
                    d = SITE_DEFAULTS.get(site, {})
                    cfg.sites[site] = SiteConfig(
                        name=site,
                        ssh=SSHRemoteConfig(**d.get("ssh", {})),
                        remote_db=RemoteDBConfig(**d.get("remote_db", {})),
                        uptnew_mode=d.get("uptnew_mode", "full"),
                    )
            cls._cache = cfg
            cls._cache_mtime = mtime
            return cfg
        cfg = cls()
        for site in SITES:
            d = SITE_DEFAULTS.get(site, {})
            cfg.sites[site] = SiteConfig(
                name=site,
                ssh=SSHRemoteConfig(**d.get("ssh", {})),
                remote_db=RemoteDBConfig(**d.get("remote_db", {})),
                uptnew_mode=d.get("uptnew_mode", "full"),
            )
        return cfg

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, ensure_ascii=False, indent=2)
        # update cache after save
        AppConfig._cache = self
        AppConfig._cache_mtime = CONFIG_FILE.stat().st_mtime

    def get_site(self, site: str) -> SiteConfig:
        if site not in self.sites:
            raise ValueError(f"Unknown site: {site}")
        return self.sites[site]

    def db_name(self, site: str) -> str:
        return f"sum_{site}"
