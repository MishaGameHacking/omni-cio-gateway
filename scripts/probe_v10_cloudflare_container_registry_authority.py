from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from typing import TextIO


_REPO_ROOT = Path(__file__).resolve().parents[1]
_WRANGLER_CLI = _REPO_ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"
_ACCOUNT_ID = re.compile(r"^[0-9a-f]{32}$")
_PROBE_TIMEOUT_SECONDS = 45.0
_PROVIDER_BLOCKED = 78


class RegistryAuthorityStopped(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _required_environment(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RegistryAuthorityStopped(f"{name}_REQUIRED")
    return value


def _validated_account_id(environment: Mapping[str, str]) -> str:
    account_id = _required_environment(environment, "CLOUDFLARE_ACCOUNT_ID").lower()
    if _ACCOUNT_ID.fullmatch(account_id) is None:
        raise RegistryAuthorityStopped("CLOUDFLARE_ACCOUNT_ID_INVALID")
    return account_id


def _node_executable(explicit: Path | None = None) -> Path:
    candidate = explicit
    if candidate is None:
        discovered = shutil.which("node")
        if not discovered:
            raise RegistryAuthorityStopped("CLOUDFLARE_CONTAINER_PROBE_NODE_UNAVAILABLE")
        candidate = Path(discovered)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        raise RegistryAuthorityStopped(
            "CLOUDFLARE_CONTAINER_PROBE_NODE_UNAVAILABLE"
        ) from None
    if not resolved.is_file():
        raise RegistryAuthorityStopped("CLOUDFLARE_CONTAINER_PROBE_NODE_UNAVAILABLE")
    return resolved


def _wrangler_cli(explicit: Path | None = None) -> Path:
    candidate = _WRANGLER_CLI if explicit is None else explicit
    if candidate.is_symlink():
        raise RegistryAuthorityStopped("CLOUDFLARE_CONTAINER_PROBE_WRANGLER_INVALID")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to((_REPO_ROOT / "node_modules").resolve(strict=True))
    except (OSError, ValueError):
        raise RegistryAuthorityStopped(
            "CLOUDFLARE_CONTAINER_PROBE_WRANGLER_UNAVAILABLE"
        ) from None
    if not resolved.is_file():
        raise RegistryAuthorityStopped(
            "CLOUDFLARE_CONTAINER_PROBE_WRANGLER_UNAVAILABLE"
        )
    return resolved


def _probe_command(node: Path, wrangler: Path) -> tuple[str, ...]:
    return (
        str(node),
        str(wrangler),
        "containers",
        "images",
        "list",
        "--json",
    )


def probe_container_registry_authority(
    environment: Mapping[str, str] = os.environ,
    *,
    output: TextIO = sys.stdout,
    node_executable: Path | None = None,
    wrangler_cli: Path | None = None,
) -> int:
    _required_environment(environment, "CLOUDFLARE_API_TOKEN")
    _validated_account_id(environment)
    node = _node_executable(node_executable)
    wrangler = _wrangler_cli(wrangler_cli)

    try:
        completed = subprocess.run(
            _probe_command(node, wrangler),
            cwd=_REPO_ROOT,
            env=dict(environment),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            "CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED "
            "code=CLOUDFLARE_CONTAINERS_REGISTRY_PROBE_TIMEOUT",
            file=output,
        )
        return _PROVIDER_BLOCKED
    except OSError:
        print(
            "CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED "
            "code=CLOUDFLARE_CONTAINERS_REGISTRY_PROBE_UNAVAILABLE",
            file=output,
        )
        return _PROVIDER_BLOCKED

    if completed.returncode != 0:
        print(
            "CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED "
            "code=CLOUDFLARE_CONTAINERS_REGISTRY_AUTHORITY_REQUIRED",
            file=output,
        )
        return _PROVIDER_BLOCKED

    print("CLOUDFLARE_CONTAINERS_REGISTRY_READ=READY", file=output)
    return 0


def main() -> int:
    try:
        return probe_container_registry_authority()
    except RegistryAuthorityStopped as exc:
        print(
            f"CLOUDFLARE_CONTAINERS_REGISTRY_READ=BLOCKED code={exc.code}",
            file=sys.stderr,
        )
        return _PROVIDER_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
