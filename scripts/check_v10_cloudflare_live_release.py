from __future__ import annotations

import json
import re
import ssl
import sys
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener


_MAX_BYTES = 65_536
_SHA = re.compile(r"^[0-9a-f]{40}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


def _origin(value: str) -> str:
    candidate = value.strip().rstrip("/")
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("CLOUDFLARE_RELEASE_ORIGIN_INVALID")
    return f"https://{parsed.hostname.lower().rstrip('.')}"


def _json(origin: str, path: str) -> dict[str, Any]:
    opener = build_opener(
        _NoRedirect(), HTTPSHandler(context=ssl.create_default_context())
    )
    request = Request(origin + path, headers={"Accept": "application/json"})
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("CLOUDFLARE_RELEASE_HTTP_INVALID")
            content_type = response.headers.get_content_type()
            if content_type != "application/json":
                raise RuntimeError("CLOUDFLARE_RELEASE_CONTENT_TYPE_INVALID")
            payload = response.read(_MAX_BYTES + 1)
    except HTTPError as exc:
        raise RuntimeError(f"CLOUDFLARE_RELEASE_HTTP_{exc.code}") from None
    except OSError as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_UNAVAILABLE") from exc
    if len(payload) > _MAX_BYTES:
        raise RuntimeError("CLOUDFLARE_RELEASE_RESPONSE_TOO_LARGE")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("CLOUDFLARE_RELEASE_JSON_INVALID") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("CLOUDFLARE_RELEASE_JSON_OBJECT_REQUIRED")
    return decoded


def verify(origin: str, expected_sha: str) -> None:
    canonical_origin = _origin(origin)
    sha = expected_sha.strip().lower()
    if _SHA.fullmatch(sha) is None:
        raise RuntimeError("CLOUDFLARE_RELEASE_EXPECTED_SHA_INVALID")

    release = _json(canonical_origin, "/api/v10/release")
    expected_release = {
        "status": "ok",
        "platform": "cloudflare",
        "source_sha": sha,
        "backend": "container",
        "static_assets": True,
        "public_multi_user_enabled": False,
        "real_trading_enabled": False,
    }
    for key, expected in expected_release.items():
        if release.get(key) != expected:
            raise RuntimeError(f"CLOUDFLARE_RELEASE_{key.upper()}_INVALID")

    health = _json(canonical_origin, "/healthz")
    if health.get("status") != "ok":
        raise RuntimeError("CLOUDFLARE_RELEASE_HEALTH_INVALID")
    if health.get("release_sha") != sha:
        raise RuntimeError("CLOUDFLARE_RELEASE_HEALTH_SHA_MISMATCH")
    if health.get("database") != "READY":
        raise RuntimeError("CLOUDFLARE_RELEASE_DATABASE_NOT_READY")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print(
            "usage: check_v10_cloudflare_live_release.py <origin> <sha>",
            file=sys.stderr,
        )
        return 2
    try:
        verify(args[0], args[1])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Cloudflare live release accepted: {_origin(args[0])}")
    print(f"Exact source SHA: {args[1].strip().lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
