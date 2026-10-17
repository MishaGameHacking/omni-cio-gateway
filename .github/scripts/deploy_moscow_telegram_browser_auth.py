"""Deploy the reviewed backend and verify login/workspace on the exact Moscow host.

The deployment verifies the existing Timeweb server, uses a short-lived SSH key,
stages and preflights the checked-in backend, switches only the systemd Uvicorn
entry point, and invokes an audited rollback if any local or public check fails.
The SQLite database, environment file, TLS proxy, and APK release files are never
replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

import diagnose_moscow_telegram as cloud


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
TELEGRAM_JWKS_FILENAME = "telegram_jwks.json"
TELEGRAM_JWKS = BACKEND / TELEGRAM_JWKS_FILENAME
REMOTE_SOURCE = ROOT / ".github/scripts/deploy_moscow_telegram_browser_auth_remote.sh"
PUBLIC_URL = "https://176.98.178.81.sslip.io"
LOGIN_SCRIPT = "https://oauth.telegram.org/js/telegram-login.js?3"
REMOTE_DEPLOY_ROOT = "/root/analyst-ai-deploy"
REMOTE_ARCHIVE_FILENAME = "backend.tgz"
REMOTE_SCRIPT_FILENAME = "deploy.sh"
MAX_PUBLIC_RESPONSE = 256_000
DEPLOY_USER_AGENT = "Analyst-AI-deploy-check/1"
WORKSPACE_READ_PATHS = (
    "/workspace", "/workspace/strategy", "/workspace/risks", "/workspace/chat/threads",
    "/workspace/notifications/preferences", "/workspace/devices",
    "/workspace/analysis/checks/release-verification",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_jwks(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("Pinned Telegram JWKS is missing or linked")
    raw = path.read_bytes()
    if not raw or len(raw) > 65_536:
        raise RuntimeError("Pinned Telegram JWKS has an invalid size")
    payload = json.loads(raw.decode("utf-8"))
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        raise RuntimeError("Pinned Telegram JWKS has no key list")
    rs256 = [
        key
        for key in keys
        if isinstance(key, dict)
        and key.get("alg") == "RS256"
        and key.get("kty") == "RSA"
        and isinstance(key.get("kid"), str)
        and isinstance(key.get("n"), str)
        and isinstance(key.get("e"), str)
        and ("key_ops" not in key or "verify" in key.get("key_ops", []))
    ]
    if len(rs256) != 1:
        raise RuntimeError("Pinned Telegram JWKS must contain one RS256 verification key")
    return rs256[0]


def validate_remote_readonly_assignments(source: str) -> None:
    """Reject any assignment made after a shell variable becomes readonly."""
    readonly_names: set[str] = set()
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("readonly "):
            declaration = stripped.removeprefix("readonly ")
            readonly_names.update(
                match.group(1)
                for match in re.finditer(
                    r"(?:^|\s)([A-Z][A-Z0-9_]*)(?==|\s|$)",
                    declaration,
                )
            )
            continue
        for name in readonly_names:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}=", line):
                raise RuntimeError(
                    f"Remote deployment reassigns readonly shell constant {name} "
                    f"on line {line_number}"
                )


def validate_source() -> dict[str, str]:
    required = (
        BACKEND / "app.py",
        BACKEND / "telegram_browser_app.py",
        TELEGRAM_JWKS,
        BACKEND / "requirements.txt",
        REMOTE_SOURCE,
    )
    for path in required:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Required deployment source is missing: {path.relative_to(ROOT)}")
    key = validate_jwks(TELEGRAM_JWKS)
    if key["kid"] != "oidc-1":
        raise RuntimeError("Pinned Telegram RS256 key id is not the reviewed oidc-1 key")
    source = (BACKEND / "telegram_browser_app.py").read_text(encoding="utf-8")
    for required_text in (
        "telegram_browser_app:app",
        LOGIN_SCRIPT,
        "/auth/telegram/complete",
        "same-origin-allow-popups",
        "verify_browser_id_token",
    ):
        if required_text not in source:
            raise RuntimeError(f"Telegram browser-login invariant is missing: {required_text}")
    remote = REMOTE_SOURCE.read_text(encoding="utf-8")
    validate_remote_readonly_assignments(remote)
    for required_text in (
        "TELEGRAM_AUTH_DEPLOYMENT=passed",
        "TELEGRAM_AUTH_EXTERNAL_ROLLBACK=passed",
        "telegram_browser_app:app",
        "analyst-ai-backend.service",
        REMOTE_DEPLOY_ROOT,
    ):
        if required_text not in remote:
            raise RuntimeError(f"Telegram deployment invariant is missing: {required_text}")
    return {
        "jwks_sha256": sha256_file(TELEGRAM_JWKS),
        "requirements_sha256": sha256_file(BACKEND / "requirements.txt"),
    }


def create_archive(destination: Path) -> None:
    with tarfile.open(destination, mode="w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(BACKEND.rglob("*")):
            relative = path.relative_to(ROOT)
            if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            if path.is_symlink():
                raise RuntimeError(f"Refusing to archive symbolic link: {relative}")
            archive.add(path, arcname=relative.as_posix(), recursive=False)
    if destination.stat().st_size <= 0:
        raise RuntimeError("Backend archive is empty")


def retry(command: list[str], *, attempts: int = 5, delay: float = 5.0) -> None:
    last: subprocess.CompletedProcess[bytes] | None = None
    for attempt in range(1, attempts + 1):
        last = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if last.returncode == 0:
            return
        if attempt < attempts:
            time.sleep(delay)
    stderr = b"" if last is None else last.stderr[-2000:]
    raise RuntimeError(
        f"Command failed after {attempts} attempts: {command[0]}: "
        + stderr.decode("utf-8", errors="replace")
    )


def verify_public_endpoint() -> None:
    health_request = urllib.request.Request(
        PUBLIC_URL + "/health",
        headers={"Accept": "application/json", "User-Agent": DEPLOY_USER_AGENT},
    )
    with urllib.request.urlopen(health_request, timeout=20) as response:
        health = json.loads(response.read(MAX_PUBLIC_RESPONSE).decode("utf-8"))
    if health != {"status": "ok"}:
        raise RuntimeError("Public backend health response is invalid")

    login_request = urllib.request.Request(
        PUBLIC_URL + "/auth/telegram/start",
        headers={"Accept": "text/html", "User-Agent": DEPLOY_USER_AGENT},
    )
    with urllib.request.urlopen(login_request, timeout=20) as response:
        body = response.read(MAX_PUBLIC_RESPONSE + 1)
        headers = {name.lower(): value for name, value in response.headers.items()}
        status = response.status
    if status != 200 or len(body) > MAX_PUBLIC_RESPONSE:
        raise RuntimeError("Public Telegram login page response is invalid")
    page = body.decode("utf-8")
    for required in (LOGIN_SCRIPT, "Продолжить в Telegram", "/auth/telegram/complete"):
        if required not in page:
            raise RuntimeError(f"Public Telegram login page is missing {required}")
    if headers.get("cross-origin-opener-policy") != "same-origin-allow-popups":
        raise RuntimeError("Public Telegram popup policy is missing")
    if "no-store" not in headers.get("cache-control", ""):
        raise RuntimeError("Public Telegram login page may be cached")
    verify_workspace_authentication()


def verify_workspace_authentication() -> None:
    """A missing route or an unauthenticated successful read blocks deployment.

    These probes send no credentials, invoke no model, and do not create records.
    Authorized user workflows are covered by the backend integration suite.
    """
    for path in WORKSPACE_READ_PATHS:
        request = urllib.request.Request(
            PUBLIC_URL + path,
            headers={"Accept": "application/json", "User-Agent": DEPLOY_USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
        if status != 401:
            raise RuntimeError(f"Workspace authentication probe failed for {path}: HTTP {status}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument(
        "--check",
        action="store_true",
        help="validate and archive the exact source without cloud access",
    )
    return result


def deployment_identifier() -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    if re.fullmatch(r"[A-Za-z0-9-]{1,60}", run_id) is None:
        raise RuntimeError("Invalid run identifier")
    if re.fullmatch(r"[1-9]\d{0,8}", attempt) is None:
        raise RuntimeError("Invalid run attempt")
    return f"{run_id}-{attempt}"


def remove_remote_directory(
    ssh: str,
    options: list[str],
    host: str,
    remote_root: str,
) -> None:
    subprocess.run(
        [ssh, *options, host, "rm", "-rf", "--", remote_root],
        check=False,
        timeout=45,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    metadata = validate_source()
    deployment_id = deployment_identifier()

    with tempfile.TemporaryDirectory(prefix="analyst-ai-telegram-auth-deploy-") as temporary:
        work = Path(temporary)
        archive = work / f"analyst-ai-telegram-auth-{deployment_id}.tgz"
        remote = work / f"analyst-ai-telegram-auth-{deployment_id}.sh"
        private_key = work / "deployment-key"
        known_hosts = work / "known-hosts"

        create_archive(archive)
        archive_sha = sha256_file(archive)
        remote.write_bytes(REMOTE_SOURCE.read_bytes())
        remote.chmod(0o700)
        if args.check:
            bash = shutil.which("bash")
            if bash:
                subprocess.run([bash, "-n", str(remote)], check=True)
            print("TELEGRAM_AUTH_DEPLOYMENT_CHECK=passed", flush=True)
            return 0

        token = os.environ.get("TIMEWEB_CLOUD_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TIMEWEB_CLOUD_TOKEN is required")
        cloud.verify_server(token)
        ssh = cloud.command_path("ssh")
        scp = cloud.command_path("scp")
        ssh_keygen = cloud.command_path("ssh-keygen")
        key_id: int | None = None

        subprocess.run(
            [
                ssh_keygen,
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(private_key),
                "-C",
                f"analyst-ai-telegram-auth-{deployment_id}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            public_key = private_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
            created = cloud.request(
                token,
                "POST",
                "/ssh-keys",
                {
                    "name": f"analyst-ai-telegram-auth-{deployment_id}",
                    "body": public_key,
                    "is_default": False,
                },
            )
            key_id = cloud.numeric_id(created)
            cloud.request(
                token,
                "POST",
                f"/servers/{cloud.SERVER_ID}/ssh-keys",
                {"ssh_key_ids": [key_id]},
            )

            options = [
                "-i",
                str(private_key),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "ConnectionAttempts=2",
                "-o",
                "ServerAliveInterval=10",
                "-o",
                "ServerAliveCountMax=3",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                f"UserKnownHostsFile={known_hosts}",
            ]
            host = f"root@{cloud.EXPECTED_IP}"
            ready = False
            for _ in range(36):
                probe = subprocess.run(
                    [ssh, *options, host, "echo ready"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=25,
                )
                if probe.returncode == 0:
                    ready = True
                    break
                time.sleep(10)
            if not ready:
                raise RuntimeError("Verified Moscow server SSH did not become ready")

            remote_root = f"{REMOTE_DEPLOY_ROOT}/{deployment_id}"
            remote_archive = f"{remote_root}/{REMOTE_ARCHIVE_FILENAME}"
            remote_script_path = f"{remote_root}/{REMOTE_SCRIPT_FILENAME}"
            preserve_remote = False
            retry([ssh, *options, host, "install", "-d", "-m", "0700", "--", remote_root])
            try:
                retry([scp, *options, str(archive), f"{host}:{remote_archive}"])
                retry([scp, *options, str(remote), f"{host}:{remote_script_path}"])
                deployment_args = [
                    deployment_id,
                    archive_sha,
                    metadata["jwks_sha256"],
                    metadata["requirements_sha256"],
                ]
                try:
                    completed = subprocess.run(
                        [
                            ssh,
                            *options,
                            host,
                            "bash",
                            remote_script_path,
                            *deployment_args,
                        ],
                        check=False,
                        timeout=480,
                    )
                except subprocess.TimeoutExpired as error:
                    preserve_remote = True
                    raise RuntimeError("Moscow Telegram-auth deployment timed out") from error
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"Moscow Telegram-auth deployment failed with exit {completed.returncode}"
                    )
                try:
                    verify_public_endpoint()
                except Exception:
                    rollback = subprocess.run(
                        [
                            ssh,
                            *options,
                            host,
                            "bash",
                            remote_script_path,
                            "--rollback-after-public-check",
                            deployment_id,
                        ],
                        check=False,
                        timeout=180,
                    )
                    if rollback.returncode != 0:
                        preserve_remote = True
                        raise RuntimeError(
                            "Public verification failed and the audited rollback also failed"
                        )
                    raise
                print("TELEGRAM_AUTH_PUBLIC_VERIFICATION=passed", flush=True)
                return 0
            finally:
                if not preserve_remote:
                    remove_remote_directory(ssh, options, host, remote_root)
        finally:
            cloud.cleanup_key(token, key_id)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(
            f"TELEGRAM_AUTH_DEPLOYMENT=failed type={type(error).__name__}",
            file=sys.stderr,
            flush=True,
        )
        raise
