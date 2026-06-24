"""数据传导 — own paramiko transport.

Exists separately from ssh_service.py because:
  * ssh_service only supports key auth (raises if key missing) — we need password too;
  * ssh_service has no generic SFTP upload-to-arbitrary-path;
  * the feature must not modify existing modules.

Supports BOTH key and password auth. Uses connect(key_filename=...) for
format-agnostic key loading (RSA / Ed25519 / ECDSA), unlike RSAKey-only code.
"""

import os
from pathlib import Path

import paramiko

from app.services.conduction_config import CondEndpoint
from app.services import conduction_commands as cc


def create_client(ep: CondEndpoint) -> paramiko.SSHClient:
    """Open an SSH client to a REMOTE endpoint (caller must ensure deploy_type==remote)."""
    ssh = ep.ssh
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = {
        "hostname": ssh.host,
        "port": ssh.port,
        "username": ssh.user,
        "timeout": 30,
    }
    if ssh.auth_method == "password":
        if not ssh.password:
            raise ValueError("密码登录方式未配置密码")
        kwargs["password"] = ssh.password
    else:
        # key auth (default)
        if not ssh.key_path or not os.path.exists(ssh.key_path):
            raise FileNotFoundError(f"SSH 密钥未找到: {ssh.key_path}（请用「挂载」按钮上传）")
        kwargs["key_filename"] = ssh.key_path
    client.connect(**kwargs)
    return client


def test_connection(ep: CondEndpoint) -> tuple[bool, str]:
    try:
        client = create_client(ep)
        client.close()
        return True, "SSH 连接成功"
    except Exception as e:
        return False, str(e)


def exec_remote(ep: CondEndpoint, command: str, timeout: int = 600) -> tuple[int, str, str]:
    """Run a command on the remote host. Returns (exit_code, stdout, stderr).

    Reads stdout/stderr BEFORE recv_exit_status(): calling exit status first can
    return -1 for long-running commands that emit stderr (e.g. the mysql
    "Using a password on the command line" warning). Mirrors ssh_service.
    """
    client = create_client(ep)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, out, err
    finally:
        client.close()


def sftp_upload(ep: CondEndpoint, local_path: str, remote_path: str) -> None:
    client = create_client(ep)
    try:
        sftp = client.open_sftp()
        # ensure remote parent dir exists
        parent = str(Path(remote_path).parent)
        try:
            remote_mkdir(ep, parent)
        except Exception:
            pass  # best-effort; some shells/paths
        sftp.put(local_path, remote_path)
        sftp.close()
    finally:
        client.close()


def sftp_download(ep: CondEndpoint, remote_path: str, local_path: str) -> None:
    client = create_client(ep)
    try:
        sftp = client.open_sftp()
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        sftp.get(remote_path, local_path)
        sftp.close()
    finally:
        client.close()


def remote_mkdir(ep: CondEndpoint, path: str) -> None:
    """Ensure a directory exists on the remote host (linux/windows aware)."""
    if not path:
        return
    exec_remote(ep, cc.remote_mkdir_cmd(ep, path), timeout=60)
