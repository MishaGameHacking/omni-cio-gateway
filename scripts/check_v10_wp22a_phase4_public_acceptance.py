from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import re
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


EXPECTED_HOST = "omni-cio-v10-web.onrender.com"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class ResponseLike(Protocol):
    status: int
    headers: Any

    def read(self) -> bytes: ...

    def geturl(self) -> str: ...

    def __enter__(self) -> ResponseLike: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


Opener = Callable[..., ResponseLike]
Sleeper = Callable[[float], None]


class AcceptanceFailure(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code if not detail else f"{code}:{detail}")
        self.code = code
        self.detail = detail


def _normalize_base_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise AcceptanceFailure("UNSAFE_PREVIEW_URL_SCHEME")
    if parsed.hostname != EXPECTED_HOST or parsed.port is not None:
        raise AcceptanceFailure("UNEXPECTED_PREVIEW_HOST")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AcceptanceFailure("UNSAFE_PREVIEW_URL_COMPONENT")
    if parsed.path not in {"", "/"}:
        raise AcceptanceFailure("UNEXPECTED_PREVIEW_URL_PATH")
    return f"https://{EXPECTED_HOST}"


def _safe_fetch(
    url: str,
    *,
    timeout_seconds: float,
    opener: Opener,
) -> tuple[int, dict[str, str], bytes, str]:
    request = Request(
        url,
        headers={
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.1",
            "Accept-Encoding": "identity",
            "User-Agent": "omni-cio-v10-phase4-public-acceptance/1",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            status = int(response.status)
            headers = {
                str(key).lower(): str(value) for key, value in response.headers.items()
            }
            body = response.read()
            final_url = response.geturl()
    except HTTPError as exc:
        raise AcceptanceFailure("HTTP_ERROR", str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise AcceptanceFailure("NETWORK_OR_TLS_ERROR") from None

    final = urlparse(final_url)
    if final.scheme != "https" or final.hostname != EXPECTED_HOST:
        raise AcceptanceFailure("UNEXPECTED_REDIRECT_TARGET")
    return status, headers, body, final_url


def _validate_health(
    base_url: str,
    expected_sha: str,
    *,
    timeout_seconds: float,
    opener: Opener,
) -> None:
    status, headers, body, _ = _safe_fetch(
        f"{base_url}/healthz",
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
    if status != 200:
        raise AcceptanceFailure("HEALTH_HTTP_STATUS", str(status))

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AcceptanceFailure("HEALTH_INVALID_JSON") from None
    if not isinstance(payload, dict):
        raise AcceptanceFailure("HEALTH_INVALID_PAYLOAD")

    required = {
        "status": "ok",
        "release_sha": expected_sha,
        "database": "READY",
        "synthetic_preview": True,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise AcceptanceFailure("HEALTH_CONTRACT_MISMATCH", key)

    cache_control = headers.get("cache-control", "").casefold()
    if "no-store" not in cache_control:
        raise AcceptanceFailure("CACHE_CONTROL_NO_STORE_MISSING")

    hsts = headers.get("strict-transport-security", "").casefold()
    if "max-age=31536000" not in hsts:
        raise AcceptanceFailure("HSTS_REQUIRED_MAX_AGE_MISSING")


def _validate_root(
    base_url: str,
    *,
    timeout_seconds: float,
    opener: Opener,
) -> None:
    status, headers, body, _ = _safe_fetch(
        f"{base_url}/",
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
    if status != 200:
        raise AcceptanceFailure("ROOT_HTTP_STATUS", str(status))

    content_type = headers.get("content-type", "").casefold()
    if "text/html" not in content_type:
        raise AcceptanceFailure("ROOT_CONTENT_TYPE_MISMATCH")

    try:
        html = body.decode("utf-8")
    except UnicodeDecodeError:
        raise AcceptanceFailure("ROOT_INVALID_UTF8") from None

    for marker in (
        '<div id="root"></div>',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0"',
        "Omni-CIO",
    ):
        if marker not in html:
            raise AcceptanceFailure("ROOT_SHELL_MARKER_MISSING")


def probe_public_preview(
    *,
    base_url: str,
    expected_sha: str,
    attempts: int = 8,
    delay_seconds: float = 10.0,
    timeout_seconds: float = 20.0,
    opener: Opener = urlopen,
    sleeper: Sleeper = time.sleep,
) -> None:
    normalized_url = _normalize_base_url(base_url)
    normalized_sha = expected_sha.strip().lower()
    if not SHA_PATTERN.fullmatch(normalized_sha):
        raise AcceptanceFailure("INVALID_EXPECTED_SHA")
    if attempts < 1 or attempts > 30:
        raise AcceptanceFailure("INVALID_ATTEMPT_COUNT")
    if delay_seconds < 0 or delay_seconds > 60:
        raise AcceptanceFailure("INVALID_RETRY_DELAY")
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise AcceptanceFailure("INVALID_TIMEOUT")

    last_failure: AcceptanceFailure | None = None
    for attempt in range(1, attempts + 1):
        try:
            _validate_health(
                normalized_url,
                normalized_sha,
                timeout_seconds=timeout_seconds,
                opener=opener,
            )
            _validate_root(
                normalized_url,
                timeout_seconds=timeout_seconds,
                opener=opener,
            )
            return
        except AcceptanceFailure as exc:
            last_failure = exc
            print(
                f"PHASE4_PUBLIC_ACCEPTANCE=RETRY attempt={attempt}/{attempts} "
                f"code={exc.code}"
            )
            if attempt < attempts:
                sleeper(delay_seconds)

    assert last_failure is not None
    raise last_failure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only public acceptance probe for the WP22A Phase-4 Render/Neon "
            "synthetic preview."
        )
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--delay-seconds", type=float, default=10.0)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        probe_public_preview(
            base_url=args.base_url,
            expected_sha=args.expected_sha,
            attempts=args.attempts,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
        )
    except AcceptanceFailure as exc:
        detail = f" detail={exc.detail}" if exc.detail else ""
        print(f"PHASE4_PUBLIC_ACCEPTANCE=FAIL code={exc.code}{detail}")
        return 1

    print("PHASE4_PUBLIC_ACCEPTANCE=PASS")
    print(f"PHASE4_RELEASE_SHA={args.expected_sha.strip().lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
