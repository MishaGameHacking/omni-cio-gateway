from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.parse import unquote

import httpx
import pytest

from omni_cio.watchtower.qstash_v1 import (
    QStashScheduleClientV1,
    QStashScheduleError,
    QStashScheduleSpecV1,
    QStashSignatureError,
    QStashSignatureVerifierV1,
)


NOW = 1_786_000_000.0
CURRENT_KEY = "qstash-current-test-key"  # pragma: allowlist secret
NEXT_KEY = "qstash-next-test-key"  # pragma: allowlist secret
DESTINATION = "https://omni-cio-gateway.onrender.com/internal/watchtower/run"
CALLBACK = "https://omni-cio-gateway.onrender.com/internal/watchtower/callback"
FAILURE_CALLBACK = (
    "https://omni-cio-gateway.onrender.com/internal/watchtower/failure-callback"
)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signature(body: str, url: str, *, key: str = CURRENT_KEY) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body_hash = _b64(hashlib.sha256(body.encode()).digest())
    payload = _b64(
        json.dumps(
            {
                "iss": "Upstash",
                "sub": url,
                "exp": NOW + 60,
                "nbf": NOW - 1,
                "body": body_hash,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64(hmac.new(key.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def test_signature_verifies_exact_body_url_and_key_rotation() -> None:
    body = '{"job":"portfolio_watchtower","schema_version":"1.0"}'
    verifier = QStashSignatureVerifierV1(
        current_signing_key=CURRENT_KEY,
        next_signing_key=NEXT_KEY,
        now_provider=lambda: NOW,
    )
    verifier.verify(signature=_signature(body, DESTINATION), body=body, url=DESTINATION)
    verifier.verify(
        signature=_signature(body, DESTINATION, key=NEXT_KEY),
        body=body,
        url=DESTINATION,
    )

    with pytest.raises(QStashSignatureError):
        verifier.verify(
            signature=_signature(body, DESTINATION),
            body=body + " ",
            url=DESTINATION,
        )
    with pytest.raises(QStashSignatureError):
        verifier.verify(
            signature=_signature(body, DESTINATION),
            body=body,
            url=CALLBACK,
        )


def test_signature_rejects_expired_and_wrong_key_tokens() -> None:
    body = '{"job":"portfolio_watchtower","schema_version":"1.0"}'
    verifier = QStashSignatureVerifierV1(
        current_signing_key=CURRENT_KEY,
        next_signing_key=NEXT_KEY,
        now_provider=lambda: NOW + 3600,
    )
    with pytest.raises(QStashSignatureError, match="expired"):
        verifier.verify(signature=_signature(body, DESTINATION), body=body, url=DESTINATION)

    fresh = QStashSignatureVerifierV1(
        current_signing_key=CURRENT_KEY,
        next_signing_key=NEXT_KEY,
        now_provider=lambda: NOW,
    )
    with pytest.raises(QStashSignatureError, match="mismatch"):
        fresh.verify(
            signature=_signature(body, DESTINATION, key="unknown-test-key"),
            body=body,
            url=DESTINATION,
        )


def test_schedule_ensure_is_idempotent_bounded_and_observable() -> None:
    schedule_id = "omni-cio-watchtower-primary-v1"
    stored: dict[str, object] = {}
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-qstash-token"
        path = request.url.path
        if request.method == "POST" and path.startswith("/v2/schedules/"):
            destination = unquote(path.removeprefix("/v2/schedules/"))
            assert destination == DESTINATION
            assert request.headers["upstash-schedule-id"] == schedule_id
            assert request.headers["upstash-retries"] == "3"
            assert request.headers["upstash-callback-retries"] == "1"
            assert request.headers["upstash-failure-callback-retries"] == "1"
            assert request.headers["upstash-redact-fields"] == "body"
            stored.update(
                {
                    "scheduleId": schedule_id,
                    "cron": request.headers["upstash-cron"],
                    "destination": destination,
                    "method": request.headers["upstash-method"],
                    "isPaused": False,
                    "retries": int(request.headers["upstash-retries"]),
                    "callback": request.headers["upstash-callback"],
                    "failureCallback": request.headers["upstash-failure-callback"],
                    "lastScheduleTime": None,
                    "nextScheduleTime": 1_786_003_600_000,
                }
            )
            return httpx.Response(200, json={"scheduleId": schedule_id})
        if request.method == "GET" and path == f"/v2/schedules/{schedule_id}":
            return httpx.Response(200, json=stored)
        if request.method == "GET" and path == "/v2/schedules":
            return httpx.Response(200, json=[stored])
        raise AssertionError(f"unexpected request {request.method} {path}")

    client = QStashScheduleClientV1(
        "test-qstash-token",  # pragma: allowlist secret
        transport=httpx.MockTransport(handler),
    )
    spec = QStashScheduleSpecV1(
        schedule_id=schedule_id,
        cron="CRON_TZ=Europe/Moscow 0 * * * *",
        destination_url=DESTINATION,
        callback_url=CALLBACK,
        failure_callback_url=FAILURE_CALLBACK,
        retries=3,
    )
    status = client.ensure_schedule(spec)
    assert status.schedule_id == schedule_id
    assert status.destination == DESTINATION
    assert status.next_schedule_time_ms == 1_786_003_600_000
    assert client.list_schedules() == (status,)
    assert len(requests) == 3


def test_schedule_spec_rejects_unbounded_retry_or_callback_exfiltration() -> None:
    with pytest.raises(QStashScheduleError, match="bounded"):
        QStashScheduleSpecV1(
            schedule_id="omni-cio-watchtower-primary-v1",
            cron="0 * * * *",
            destination_url=DESTINATION,
            callback_url=CALLBACK,
            failure_callback_url=FAILURE_CALLBACK,
            retries=4,
        )
    with pytest.raises(QStashScheduleError, match="Gateway host"):
        QStashScheduleSpecV1(
            schedule_id="omni-cio-watchtower-primary-v1",
            cron="0 * * * *",
            destination_url=DESTINATION,
            callback_url="https://evil.example/callback",
            failure_callback_url=FAILURE_CALLBACK,
        )
