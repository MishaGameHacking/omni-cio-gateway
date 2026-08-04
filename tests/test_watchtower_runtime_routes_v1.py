from __future__ import annotations

import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from omni_cio.contracts.v1.watchtower import WatchtowerInputV1, watchtower_input_sha256
from omni_cio.watchtower import (
    InMemoryWatchtowerJournalV1,
    PortfolioWatchtowerV1,
    QStashSignatureVerifierV1,
    WatchtowerCallbackVerifierV1,
    WatchtowerEvidenceProviderRegistryV1,
    WatchtowerRuntimeError,
    WatchtowerScheduledRequestV1,
    WatchtowerScheduledRunnerV1,
)
from omni_cio.watchtower.routes_v1 import (
    WatchtowerRouteConfigurationError,
    WatchtowerRouteSettingsV1,
    register_watchtower_routes,
)
from tests.v9_execution_fixture import NOW, build_execution_fixture


KEY = "watchtower-qstash-runtime-key"  # pragma: allowlist secret
NEXT_KEY = "watchtower-qstash-runtime-next-key"  # pragma: allowlist secret
RUN_URL = "https://omni-cio-gateway.onrender.com/internal/watchtower/run"
SCHEDULE_ID = "omni-cio-watchtower-primary-v1"
BODY = '{"job":"portfolio_watchtower","schema_version":"1.0"}'


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signature(body: str, url: str) -> str:
    now = int(NOW.timestamp())
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64(
        json.dumps(
            {
                "iss": "Upstash",
                "sub": url,
                "exp": now + 60,
                "nbf": now - 1,
                "body": _b64(hashlib.sha256(body.encode()).digest()),
            },
            separators=(",", ":"),
        ).encode()
    )
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = _b64(hmac.new(KEY.encode(), unsigned, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


class FixtureProvider:
    def build_input(
        self,
        *,
        delivery_id: str,
        checked_at: datetime,
    ) -> WatchtowerInputV1:
        fixture = build_execution_fixture()
        values = {
            "schema_version": "1.0",
            "checked_at": checked_at,
            "delivery_id": delivery_id,
            "portfolio_snapshot_sha256": fixture.risk.portfolio_snapshot_sha256,
            "policy_reference": fixture.risk.policy_reference,
            "risk": fixture.risk,
            "credit_passports": (),
            "market_bundles": (),
            "source_quality_codes": (),
            "input_sha256": "0" * 64,
            "execution_authorized": False,
            "trading_methods": False,
        }
        provisional = WatchtowerInputV1.model_construct(**values)
        values["input_sha256"] = watchtower_input_sha256(provisional)
        return WatchtowerInputV1.model_validate(values)


def test_signed_runner_is_read_only_and_duplicate_delivery_is_replay_safe() -> None:
    registry = WatchtowerEvidenceProviderRegistryV1()
    registry.register(FixtureProvider())
    verifier = QStashSignatureVerifierV1(
        current_signing_key=KEY,
        next_signing_key=NEXT_KEY,
        now_provider=lambda: NOW.timestamp(),
    )
    runner = WatchtowerScheduledRunnerV1(
        verifier=verifier,
        watchtower=PortfolioWatchtowerV1(
            journal=InMemoryWatchtowerJournalV1(),
            require_durable_journal=False,
        ),
        provider_registry=registry,
        expected_schedule_id=SCHEDULE_ID,
        now_provider=lambda: NOW + timedelta(minutes=1),
    )
    request = WatchtowerScheduledRequestV1(
        raw_body=BODY,
        signature=_signature(BODY, RUN_URL),
        destination_url=RUN_URL,
        message_id="qstash-message-0001",
        schedule_id=SCHEDULE_ID,
        retried=0,
    )
    first = runner.run(request)
    assert first["status"] == "ok"
    assert first["should_notify"] is False
    assert first["execution_authorized"] is False
    assert first["trading_methods"] is False

    replay = runner.run(request)
    assert replay["replay"] is True
    assert replay["alerts"] == []
    assert replay["state_revision"] == 0

    with pytest.raises(WatchtowerRuntimeError, match="SCHEDULE_ID_MISMATCH"):
        runner.run(
            WatchtowerScheduledRequestV1(
                raw_body=BODY,
                signature=_signature(BODY, RUN_URL),
                destination_url=RUN_URL,
                message_id="qstash-message-0002",
                schedule_id="omni-cio-watchtower-other-v1",
                retried=0,
            )
        )


def test_callback_ack_is_signed_and_persists_no_source_payload() -> None:
    verifier = QStashSignatureVerifierV1(
        current_signing_key=KEY,
        next_signing_key=NEXT_KEY,
        now_provider=lambda: NOW.timestamp(),
    )
    callback = WatchtowerCallbackVerifierV1(verifier)
    url = "https://omni-cio-gateway.onrender.com/internal/watchtower/callback"
    body = '{"status":"finished","body":"sensitive-upstream-response"}'
    result = callback.acknowledge(
        raw_body=body,
        signature=_signature(body, url),
        destination_url=url,
        message_id="callback-message-0001",
    )
    assert result["status"] == "accepted"
    assert "sensitive-upstream-response" not in json.dumps(result)
    assert result["execution_authorized"] is False
    assert result["trading_methods"] is False


def test_routes_are_hidden_and_disabled_by_default() -> None:
    app = FastAPI()
    registry = WatchtowerEvidenceProviderRegistryV1()
    registration = register_watchtower_routes(
        app,
        provider_registry=registry,
        environment={"WATCHTOWER_ENABLED": "false"},
    )
    schema = app.openapi()
    assert registration.include_in_schema is False
    assert all("/internal/watchtower" not in path for path in schema.get("paths", {}))

    response = TestClient(app).post("/internal/watchtower/run")
    assert response.status_code == 404
    assert response.json()["detail"] == "WATCHTOWER_DISABLED"


def test_enabled_route_settings_fail_closed_on_missing_or_bad_configuration() -> None:
    with pytest.raises(WatchtowerRouteConfigurationError, match="BARE_HTTPS"):
        WatchtowerRouteSettingsV1.from_environment(
            {
                "WATCHTOWER_ENABLED": "true",
                "WATCHTOWER_PUBLIC_BASE_URL": "http://localhost:8000",
            }
        )
    with pytest.raises(WatchtowerRouteConfigurationError, match="SECRET_MISSING"):
        WatchtowerRouteSettingsV1.from_environment(
            {
                "WATCHTOWER_ENABLED": "true",
                "WATCHTOWER_PUBLIC_BASE_URL": "https://omni-cio-gateway.onrender.com",
            }
        )


def test_provider_clock_must_remain_timezone_aware() -> None:
    registry = WatchtowerEvidenceProviderRegistryV1()
    registry.register(FixtureProvider())
    runner = WatchtowerScheduledRunnerV1(
        verifier=QStashSignatureVerifierV1(
            current_signing_key=KEY,
            next_signing_key=NEXT_KEY,
            now_provider=lambda: NOW.timestamp(),
        ),
        watchtower=PortfolioWatchtowerV1(
            journal=InMemoryWatchtowerJournalV1(),
            require_durable_journal=False,
        ),
        provider_registry=registry,
        expected_schedule_id=SCHEDULE_ID,
        now_provider=lambda: datetime(2026, 8, 4, 12, 0),
    )
    with pytest.raises(WatchtowerRuntimeError, match="CLOCK_INVALID"):
        runner.run(
            WatchtowerScheduledRequestV1(
                raw_body=BODY,
                signature=_signature(BODY, RUN_URL),
                destination_url=RUN_URL,
                message_id="qstash-message-clock-0001",
                schedule_id=SCHEDULE_ID,
                retried=0,
            )
        )
