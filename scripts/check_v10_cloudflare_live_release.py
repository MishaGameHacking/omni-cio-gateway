from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
from typing import Any, Mapping


_MAX_BYTES = 65_536
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_ORIGIN_ENV = "OMNI_V10_CLOUDFLARE_ORIGIN"
_CUSTOM_HOST_ENV = "OMNI_V10_CLOUDFLARE_CUSTOM_HOST"


def _hostname(value: str) -> str:
    try:
        hostname = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID") from exc
    if len(hostname) > 253 or "." not in hostname:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    if any(_DNS_LABEL.fullmatch(label) is None for label in hostname.split(".")):
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    if hostname == "localhost" or hostname.endswith(
        (".localhost", ".local", ".internal", ".home.arpa")
    ):
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    return hostname


def _origin(value: str, *, allowed_custom_host: str = "") -> str:
    candidate = value.strip().rstrip("/")
    if not candidate.startswith("https://"):
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    authority = candidate.removeprefix("https://")
    if (
        not authority
        or "/" in authority
        or "?" in authority
        or "#" in authority
        or "@" in authority
        or ":" in authority
    ):
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    hostname = _hostname(authority)
    custom_host = _hostname(allowed_custom_host) if allowed_custom_host else ""
    if not hostname.endswith(".workers.dev") and hostname != custom_host:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_NOT_ALLOWED")
    return f"https://{hostname}"


def _configured_origin(env: Mapping[str, str]) -> str:
    raw_origin = env.get(_ORIGIN_ENV, "").strip()
    if not raw_origin:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_REQUIRED")
    return _origin(
        raw_origin,
        allowed_custom_host=env.get(_CUSTOM_HOST_ENV, "").strip(),
    )


def _stdin_json() -> dict[str, Any]:
    payload = sys.stdin.buffer.read(_MAX_BYTES + 1)
    if len(payload) > _MAX_BYTES:
        raise RuntimeError("CLOUDFLARE_RELEASE_RESPONSE_TOO_LARGE")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_JSON_INVALID") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("CLOUDFLARE_RELEASE_JSON_OBJECT_REQUIRED")
    return decoded


def _expected_sha(value: str) -> str:
    sha = value.strip().lower()
    if _SHA.fullmatch(sha) is None:
        raise RuntimeError("CLOUDFLARE_RELEASE_EXPECTED_SHA_INVALID")
    return sha


def verify_release(payload: Mapping[str, Any], expected_sha: str) -> None:
    sha = _expected_sha(expected_sha)
    expected = {
        "status": "ok",
        "platform": "cloudflare",
        "source_sha": sha,
        "backend": "container",
        "static_assets": True,
        "public_multi_user_enabled": False,
        "real_trading_enabled": False,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise RuntimeError(f"CLOUDFLARE_RELEASE_{key.upper()}_INVALID")


def verify_health(payload: Mapping[str, Any], expected_sha: str) -> None:
    sha = _expected_sha(expected_sha)
    if payload.get("status") != "ok":
        raise RuntimeError("CLOUDFLARE_RELEASE_HEALTH_INVALID")
    if payload.get("release_sha") != sha:
        raise RuntimeError("CLOUDFLARE_RELEASE_HEALTH_SHA_MISMATCH")
    if payload.get("database") != "READY":
        raise RuntimeError("CLOUDFLARE_RELEASE_DATABASE_NOT_READY")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        if args == ["origin"]:
            print(_configured_origin(os.environ))
            return 0
        if len(args) != 2 or args[0] not in {"release", "health"}:
            raise RuntimeError("CLOUDFLARE_RELEASE_USAGE_INVALID")
        payload = _stdin_json()
        if args[0] == "release":
            verify_release(payload, args[1])
        else:
            verify_health(payload, args[1])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Cloudflare {args[0]} payload accepted for {args[1].strip().lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
