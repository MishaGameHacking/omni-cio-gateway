from __future__ import annotations

import argparse
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
_NEON_PROJECT_ENV = "NEON_PROJECT_ID_VALUE"
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


def _cloudflare_states(environ: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return (
        (
            "CLOUDFLARE_API_TOKEN",
            "AVAILABLE"
            if _has_value(environ, _CLOUDFLARE_AUTHORITY_ENV)
            else "MISSING",
        ),
        (
            "CLOUDFLARE_ACCOUNT_ID",
            _valid_value(
                environ,
                _CLOUDFLARE_ACCOUNT_ENV,
                lambda value: _ACCOUNT_ID.fullmatch(value) is not None,
            ),
        ),
    )


def _neon_states(environ: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return (
        (
            "NEON_API_KEY",
            "AVAILABLE" if _has_value(environ, _NEON_AUTHORITY_ENV) else "MISSING",
        ),
        (
            "NEON_ORG_ID",
            _valid_value(
                environ,
                _NEON_ORGANIZATION_ENV,
                lambda value: _NEON_RESOURCE_ID.fullmatch(value) is not None,
            ),
        ),
        (
            "NEON_PROJECT_ID",
            _valid_value(
                environ,
                _NEON_PROJECT_ENV,
                lambda value: _NEON_RESOURCE_ID.fullmatch(value) is not None,
            ),
        ),
    )


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
    require_neon: bool = True,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output

    cloudflare_states = _cloudflare_states(environment)
    for label, state in cloudflare_states:
        _emit(destination, label, state)

    required_states = cloudflare_states
    if require_neon:
        neon_states = _neon_states(environment)
        for label, state in neon_states:
            _emit(destination, label, state)
        required_states += neon_states
    else:
        print("NEON_BOOTSTRAP_AUTHORITY=DEFERRED_UNTIL_REQUIRED", file=destination)

    if _container_engine_available():
        print("CLOUDFLARE_CONTAINER_ENGINE=AVAILABLE", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=DIRECT_WRANGLER_AVAILABLE", file=destination)
    else:
        print("CLOUDFLARE_CONTAINER_ENGINE=MISSING_OR_NOT_RUNNING", file=destination)
        print("CLOUDFLARE_DEPLOY_PATH=WORKERS_BUILDS", file=destination)

    if any(state != "AVAILABLE" for _, state in required_states):
        print("CLOUDFLARE_CF_C_PROVIDER_READINESS=BLOCKED", file=destination)
        return 78
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-neon",
        action="store_true",
        help="Require Neon bootstrap authority in addition to Cloudflare authority.",
    )
    args = parser.parse_args(argv)
    return check_provider_readiness(require_neon=args.require_neon)


if __name__ == "__main__":
    raise SystemExit(main())
