from __future__ import annotations

from collections.abc import Callable, Mapping
import os
import re
import shutil
import subprocess
import sys
from typing import TextIO


_CLOUDFLARE_AUTHORITY_ENV = "CLOUDFLARE_API_" + "TOKEN_VALUE"
_CLOUDFLARE_ACCOUNT_ENV = "CLOUDFLARE_ACCOUNT_ID_CREDENTIAL_VALUE"
_NEON_AUTHORITY_ENV = "NEON_API_" + "KEY_VALUE"
_NEON_ORGANIZATION_ENV = "NEON_ORG_ID_VALUE"
_ACCOUNT_ID = re.compile(r"^[0-9A-Fa-f]{32}$")
_NEON_RESOURCE_ID = re.compile(r"^[a-z0-9-]{1,60}$")
_DOCKER_TIMEOUT_SECONDS = 15.0


def _has_value(environ: Mapping[str, str], name: str) -> bool:
    return bool(environ.get(name, "").strip())


def _emit(output: TextIO, label: str, state: str) -> None:
    print(f"{label}={state}", file=output)


def _valid_value(
    environ: Mapping[str, str],
    name: str,
    validator: Callable[[str], bool],
) -> str:
    value = environ.get(name, "").strip()
    if not value:
        return "MISSING"
    return "AVAILABLE" if validator(value) else "INVALID"


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

    states = (
        (
            "CLOUDFLARE_API_TOKEN",
            "AVAILABLE"
            if _has_value(environment, _CLOUDFLARE_AUTHORITY_ENV)
            else "MISSING",
        ),
        (
            "CLOUDFLARE_ACCOUNT_ID",
            _valid_value(
                environment,
                _CLOUDFLARE_ACCOUNT_ENV,
                lambda value: _ACCOUNT_ID.fullmatch(value) is not None,
            ),
        ),
        (
            "NEON_API_KEY",
            "AVAILABLE" if _has_value(environment, _NEON_AUTHORITY_ENV) else "MISSING",
        ),
        (
            "NEON_ORG_ID",
            _valid_value(
                environment,
                _NEON_ORGANIZATION_ENV,
                lambda value: _NEON_RESOURCE_ID.fullmatch(value) is not None,
            ),
        ),
    )
    for label, state in states:
        _emit(destination, label, state)

    if _container_engine_available():
        print("CLOUDFLARE_CONTAINER_ENGINE=AVAILABLE", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=DIRECT_WRANGLER_AVAILABLE", file=destination)
    else:
        print("CLOUDFLARE_CONTAINER_ENGINE=MISSING_OR_NOT_RUNNING", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS", file=destination)

    if any(state != "AVAILABLE" for _, state in states):
        print("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", file=destination)
        return 78
    return 0


def main() -> int:
    return check_provider_readiness()


if __name__ == "__main__":
    raise SystemExit(main())
