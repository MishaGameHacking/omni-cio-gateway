from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import re
import sys
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


CANONICAL_PREVIEW_ORIGIN = "https://omni-cio-v10-web.onrender.com"
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_TRANSIENT_STATUSES = frozenset({408, 429, 502, 503, 504})
_RETRY_DELAYS_SECONDS = (5.0, 15.0)
_HTTP_TIMEOUT_SECONDS = 75.0


class HttpResponse(Protocol):
    status: int

    def __enter__(self) -> "HttpResponse": ...

    def __exit__(self, *args: object) -> None: ...

    def read(self) -> bytes: ...


OpenUrl = Callable[..., HttpResponse]
Sleep = Callable[[float], None]


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


class AlignmentStopped(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        status: int | None = None,
        expected_sha: str | None = None,
        observed_sha: str | None = None,
    ) -> None:
        self.code = code
        self.status = status
        self.expected_sha = expected_sha
        self.observed_sha = observed_sha
        super().__init__(code)


def _release_sha(value: object, code: str) -> str:
    if not isinstance(value, str) or _SHA_PATTERN.fullmatch(value) is None:
        raise AlignmentStopped(code)
    return value


def _health_url(origin: str = CANONICAL_PREVIEW_ORIGIN) -> str:
    if origin != CANONICAL_PREVIEW_ORIGIN:
        raise AlignmentStopped("PREVIEW_ORIGIN_DRIFT")
    return f"{CANONICAL_PREVIEW_ORIGIN}/healthz"


def _decode_payload(raw: bytes) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AlignmentStopped("PREVIEW_HEALTH_RESPONSE_INVALID") from None
    if not isinstance(value, dict):
        raise AlignmentStopped("PREVIEW_HEALTH_RESPONSE_INVALID")
    return value


def _read_health_payload(
    *,
    opener: OpenUrl | None = None,
    sleep: Sleep = time.sleep,
) -> dict[str, object]:
    open_url = _NO_REDIRECT_OPENER.open if opener is None else opener
    attempts = len(_RETRY_DELAYS_SECONDS) + 1
    for attempt in range(attempts):
        request = Request(
            _health_url(),
            headers={
                "Accept": "application/json",
                "User-Agent": "omni-cio-v10-hosted-release-alignment",
            },
            method="GET",
        )
        try:
            with open_url(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as exc:
            status = int(exc.code)
            if 300 <= status < 400:
                raise AlignmentStopped(
                    "PREVIEW_HEALTH_REDIRECT_FORBIDDEN",
                    status=status,
                ) from None
            if status in _TRANSIENT_STATUSES and attempt + 1 < attempts:
                sleep(_RETRY_DELAYS_SECONDS[attempt])
                continue
            raise AlignmentStopped(
                "PREVIEW_HEALTH_HTTP_ERROR",
                status=status,
            ) from None
        except (URLError, TimeoutError, OSError):
            if attempt + 1 < attempts:
                sleep(_RETRY_DELAYS_SECONDS[attempt])
                continue
            raise AlignmentStopped("PREVIEW_HEALTH_NETWORK_ERROR") from None

        if status in _TRANSIENT_STATUSES and attempt + 1 < attempts:
            sleep(_RETRY_DELAYS_SECONDS[attempt])
            continue
        if status != 200:
            raise AlignmentStopped(
                "PREVIEW_HEALTH_UNEXPECTED_STATUS",
                status=status,
            )
        return _decode_payload(raw)

    raise AssertionError("hosted release alignment retry loop exhausted")


def verify_hosted_release_alignment(
    expected_sha: str,
    *,
    opener: OpenUrl | None = None,
    sleep: Sleep = time.sleep,
) -> None:
    expected = _release_sha(expected_sha, "EXPECTED_MAIN_SHA_INVALID")
    payload = _read_health_payload(opener=opener, sleep=sleep)

    observed = _release_sha(
        payload.get("release_sha"),
        "PREVIEW_RELEASE_SHA_INVALID",
    )
    if payload.get("status") != "ok":
        raise AlignmentStopped("PREVIEW_HEALTH_NOT_OK")
    if payload.get("database") != "READY":
        raise AlignmentStopped("PREVIEW_DATABASE_NOT_READY")
    if payload.get("synthetic_preview") is not True:
        raise AlignmentStopped("PREVIEW_SYNTHETIC_BOUNDARY_INVALID")
    if observed != expected:
        raise AlignmentStopped(
            "PREVIEW_RELEASE_SHA_DRIFT",
            expected_sha=expected,
            observed_sha=observed,
        )

    print(f"PREVIEW_RELEASE_ALIGNMENT=PASS release_sha={observed}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the canonical hosted V10 technical preview matches main."
    )
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()

    try:
        verify_hosted_release_alignment(args.expected_sha)
    except AlignmentStopped as exc:
        if (
            exc.code == "PREVIEW_RELEASE_SHA_DRIFT"
            and exc.expected_sha is not None
            and exc.observed_sha is not None
        ):
            print(
                "::error::PREVIEW_RELEASE_SHA_DRIFT "
                f"expected={exc.expected_sha} observed={exc.observed_sha}",
                file=sys.stderr,
            )
        elif exc.status is not None:
            print(f"::error::{exc.code} status={exc.status}", file=sys.stderr)
        else:
            print(f"::error::{exc.code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
