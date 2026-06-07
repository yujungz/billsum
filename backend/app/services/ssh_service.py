import os
import paramiko
from pathlib import Path
from app.config import AppConfig, SiteConfig, SSHRemoteConfig


def _create_ssh_client(ssh_cfg: SSHRemoteConfig) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {
        "hostname": ssh_cfg.host,
        "port": ssh_cfg.port,
        "username": ssh_cfg.user,
    }
    if ssh_cfg.key_path and os.path.exists(ssh_cfg.key_path):
        kwargs["pkey"] = paramiko.RSAKey.from_private_key_file(ssh_cfg.key_path)
    else:
        raise FileNotFoundError(f"SSH key not found: {ssh_cfg.key_path}")
    client.connect(**kwargs)
    return client


def test_ssh_connection(ssh_cfg: SSHRemoteConfig) -> tuple[bool, str]:
    try:
        client = _create_ssh_client(ssh_cfg)
        client.close()
        return True, "SSH connection successful"
    except Exception as e:
        return False, str(e)


def exec_remote_command(ssh_cfg: SSHRemoteConfig, command: str, timeout: int = 300) -> tuple[int, str, str]:
    client = _create_ssh_client(ssh_cfg)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err
    finally:
        client.close()


def sftp_download(ssh_cfg: SSHRemoteConfig, remote_path: str, local_path: str):
    client = _create_ssh_client(ssh_cfg)
    try:
        sftp = client.open_sftp()
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        sftp.get(remote_path, local_path)
        sftp.close()
    finally:
        client.close()


def upload_script(ssh_cfg: SSHRemoteConfig, local_script_path: str, remote_path: str):
    client = _create_ssh_client(ssh_cfg)
    try:
        sftp = client.open_sftp()
        sftp.put(local_script_path, remote_path)
        sftp.close()
    finally:
        client.close()
