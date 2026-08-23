from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from scripts.check_v10_wp22a_phase4_public_acceptance import (
    AcceptanceFailure,
    main,
    probe_public_preview,
)


EXPECTED_SHA = "a" * 40
BASE_URL = "https://omni-cio-v10-web.onrender.com"


@dataclass
class FakeResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        return self.url

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def _opener(responses: list[FakeResponse]) -> Any:
    iterator: Iterator[FakeResponse] = iter(responses)

    def open_response(_request: object, *, timeout: float) -> FakeResponse:
        assert timeout > 0
        return next(iterator)

    return open_response


def _health_response(*, release_sha: str = EXPECTED_SHA) -> FakeResponse:
    body = (
        "{"
        '"status":"ok",'
        f'"release_sha":"{release_sha}",'
        '"database":"READY",'
        '"synthetic_preview":true'
        "}"
    ).encode()
    return FakeResponse(
        status=200,
        headers={
            "Cache-Control": "private, no-store",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Type": "application/json",
        },
        body=body,
        url=f"{BASE_URL}/healthz",
    )


def _root_response() -> FakeResponse:
    return FakeResponse(
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        body=(
            '<!doctype html><html><head><meta name="viewport" '
            'content="width=device-width, initial-scale=1.0" />'
            "<title>Omni-CIO Design System</title></head>"
            '<body><div id="root"></div></body></html>'
        ).encode(),
        url=f"{BASE_URL}/",
    )


def test_public_acceptance_happy_path() -> None:
    probe_public_preview(
        base_url=BASE_URL,
        expected_sha=EXPECTED_SHA,
        attempts=1,
        opener=_opener([_health_response(), _root_response()]),
        sleeper=lambda _: None,
    )


def test_public_acceptance_rejects_stale_release_sha() -> None:
    with pytest.raises(AcceptanceFailure) as exc_info:
        probe_public_preview(
            base_url=BASE_URL,
            expected_sha=EXPECTED_SHA,
            attempts=1,
            opener=_opener([_health_response(release_sha="0" * 40)]),
            sleeper=lambda _: None,
        )

    assert exc_info.value.code == "HEALTH_CONTRACT_MISMATCH"
    assert exc_info.value.detail == "release_sha"


def test_public_acceptance_rejects_untrusted_host() -> None:
    with pytest.raises(AcceptanceFailure) as exc_info:
        probe_public_preview(
            base_url="https://example.invalid",
            expected_sha=EXPECTED_SHA,
            attempts=1,
            opener=_opener([]),
            sleeper=lambda _: None,
        )

    assert exc_info.value.code == "UNEXPECTED_PREVIEW_HOST"


def test_public_acceptance_rejects_missing_private_cache_guard() -> None:
    health = _health_response()
    health.headers.pop("Cache-Control")

    with pytest.raises(AcceptanceFailure) as exc_info:
        probe_public_preview(
            base_url=BASE_URL,
            expected_sha=EXPECTED_SHA,
            attempts=1,
            opener=_opener([health]),
            sleeper=lambda _: None,
        )

    assert exc_info.value.code == "CACHE_CONTROL_NO_STORE_MISSING"


def test_public_acceptance_does_not_echo_invalid_health_body() -> None:
    private_marker = "PRIVATE_RESPONSE_MARKER_MUST_NOT_LEAK"
    health = FakeResponse(
        status=200,
        headers={
            "Cache-Control": "no-store",
            "Strict-Transport-Security": "max-age=31536000",
        },
        body=private_marker.encode(),
        url=f"{BASE_URL}/healthz",
    )

    with pytest.raises(AcceptanceFailure) as exc_info:
        probe_public_preview(
            base_url=BASE_URL,
            expected_sha=EXPECTED_SHA,
            attempts=1,
            opener=_opener([health]),
            sleeper=lambda _: None,
        )

    assert exc_info.value.code == "HEALTH_INVALID_JSON"
    assert private_marker not in str(exc_info.value)


def test_public_acceptance_main_reports_safe_failure_detail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_probe(**_kwargs: object) -> None:
        raise AcceptanceFailure("HEALTH_CONTRACT_MISMATCH", "release_sha")

    monkeypatch.setattr(
        "scripts.check_v10_wp22a_phase4_public_acceptance.probe_public_preview",
        fail_probe,
    )

    result = main(
        [
            "--base-url",
            BASE_URL,
            "--expected-sha",
            EXPECTED_SHA,
            "--attempts",
            "1",
        ]
    )
    output = capsys.readouterr().out

    assert result == 1
    assert (
        "PHASE4_PUBLIC_ACCEPTANCE=FAIL "
        "code=HEALTH_CONTRACT_MISMATCH detail=release_sha"
    ) in output
