"""Settings API - configuration management and connection testing."""

import os
import shutil
from pathlib import Path

import aiomysql
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.config import AppConfig, DATA_DIR, MySQLConfig, SSHRemoteConfig, RemoteDBConfig, SiteConfig, BusinessConfig, SITES
from app.services import ssh_service

router = APIRouter(prefix="/api/settings", tags=["settings"])

SSH_KEY_DIR = DATA_DIR / "ssh_keys"


class SiteConfigUpdate(BaseModel):
    ssh: SSHRemoteConfig
    remote_db: RemoteDBConfig
    uptnew_mode: str = "full"


class AppConfigUpdate(BaseModel):
    mysql: MySQLConfig
    sites: dict[str, SiteConfigUpdate] | None = None
    business: BusinessConfig | None = None


class MountKeyRequest(BaseModel):
    key_path: str


class RemoteDBTestRequest(BaseModel):
    ssh: SSHRemoteConfig
    remote_db: RemoteDBConfig


@router.get("")
async def get_settings():
    config = AppConfig.load()
    return config.model_dump()


@router.put("")
async def save_settings(body: AppConfigUpdate):
    config = AppConfig.load()
    config.mysql = body.mysql
    if body.sites:
        for site_name, site_upd in body.sites.items():
            if site_name in config.sites:
                config.sites[site_name].ssh = site_upd.ssh
                config.sites[site_name].remote_db = site_upd.remote_db
                config.sites[site_name].uptnew_mode = site_upd.uptnew_mode
    if body.business:
        config.business = body.business
    config.save()
    return {"success": True}


@router.post("/test-mysql")
async def test_mysql(body: MySQLConfig):
    try:
        conn = await aiomysql.connect(
            host=body.host, port=body.port,
            user=body.user, password=body.password,
            charset="utf8mb4",
        )
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
        conn.close()
        return {"success": True, "message": "MySQL connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/test-ssh")
async def test_ssh(body: SSHRemoteConfig):
    ok, msg = ssh_service.test_ssh_connection(body)
    return {"success": ok, "message": msg}


@router.post("/test-remote-db")
async def test_remote_db(body: RemoteDBTestRequest):
    cmd = (
        f"docker exec {body.remote_db.container_name} "
        f"mysql -uroot -p{body.remote_db.password} "
        f"-e 'SELECT 1' {body.remote_db.db_name}"
    )
    try:
        exit_code, out, err = ssh_service.exec_remote_command(body.ssh, cmd, timeout=30)
    except Exception as e:
        return {"success": False, "message": str(e)}
    if exit_code == 0:
        return {"success": True, "message": "远程数据库连接成功"}
    else:
        return {"success": False, "message": (err or out).strip()}


@router.post("/mount-key")
async def mount_key(file: UploadFile = File(...)):
    """Upload an SSH key file from the user's local machine to the container."""
    SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "ssh_key"
    dest = SSH_KEY_DIR / filename
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)
    os.chmod(dest, 0o600)
    return {"success": True, "container_path": str(dest), "filename": filename}


@router.post("/mount-key-from-path")
async def mount_key_from_path(body: MountKeyRequest):
    """Copy an SSH key file from a path already accessible inside the container."""
    src = Path(body.key_path)
    if not src.exists():
        return {"success": False, "message": f"File not found: {body.key_path}"}
    SSH_KEY_DIR.mkdir(parents=True, exist_ok=True)
    dest = SSH_KEY_DIR / src.name
    shutil.copy2(str(src), str(dest))
    os.chmod(dest, 0o600)
    return {"success": True, "container_path": str(dest), "filename": src.name}
