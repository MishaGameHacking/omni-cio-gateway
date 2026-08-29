from __future__ import annotations

from collections.abc import Mapping
import os
import shutil
import subprocess
import sys
from typing import TextIO


_CLOUDFLARE_AUTHORITY_ENV = "CLOUDFLARE_API_" + "TOKEN_VALUE"
_CLOUDFLARE_ACCOUNT_PRIMARY_ENV = "CLOUDFLARE_ACCOUNT_ID_CREDENTIAL_VALUE"
_CLOUDFLARE_ACCOUNT_FALLBACK_ENV = "CLOUDFLARE_ACCOUNT_ID_VAR_VALUE"
_NEON_AUTHORITY_ENV = "NEON_API_" + "KEY_VALUE"
_NEON_ORGANIZATION_ENV = "NEON_ORG_ID_VALUE"
_DOCKER_TIMEOUT_SECONDS = 15.0


def _has_value(environ: Mapping[str, str], *names: str) -> bool:
    return any(environ.get(name, "").strip() for name in names)


def _emit(output: TextIO, label: str, available: bool) -> None:
    state = "AVAILABLE" if available else "MISSING"
    print(f"{label}={state}", file=output)


def _container_engine_available() -> bool:
    executable = shutil.which("docker")
    if executable is None:
        return False
    try:
        result = subprocess.run(
            [executable, "info"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_DOCKER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def check_provider_readiness(
    environ: Mapping[str, str] | None = None,
    *,
    output: TextIO | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    required = (
        (
            "CLOUDFLARE_API_TOKEN",
            _has_value(environment, _CLOUDFLARE_AUTHORITY_ENV),
        ),
        (
            "CLOUDFLARE_ACCOUNT_ID",
            _has_value(
                environment,
                _CLOUDFLARE_ACCOUNT_PRIMARY_ENV,
                _CLOUDFLARE_ACCOUNT_FALLBACK_ENV,
            ),
        ),
        ("NEON_API_KEY", _has_value(environment, _NEON_AUTHORITY_ENV)),
        ("NEON_ORG_ID", _has_value(environment, _NEON_ORGANIZATION_ENV)),
    )
    for label, available in required:
        _emit(destination, label, available)

    if _container_engine_available():
        print("CLOUDFLARE_CONTAINER_ENGINE=AVAILABLE", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=DIRECT_WRANGLER_AVAILABLE", file=destination)
    else:
        print("CLOUDFLARE_CONTAINER_ENGINE=MISSING_OR_NOT_RUNNING", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS", file=destination)

    if not all(available for _, available in required):
        print("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", file=destination)
        return 78
    return 0


def main() -> int:
    return check_provider_readiness()


if __name__ == "__main__":
    raise SystemExit(main())
