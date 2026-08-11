from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    DataQuality,
)
from omni_cio.contracts.v1.observability import (
    CircuitBreakerState,
    ExternalCallStatus,
    ExternalCallTelemetryV1,
    FreshnessTelemetry,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)
from omni_cio.observability import build_safe_event, emit_safe_event, new_trace_id
from omni_cio.quality import validate_portfolio_market_payload_in_shadow


NOW = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)


def _portfolio_payload() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": "2026-07-29T12:00:00+00:00",
        "source_snapshot_retrieved_at": "2026-07-29T11:59:58+00:00",
        "account": {"masked_id": "***3118", "name": "ИИС"},
        "cash_balances": [
            {
                "currency": "RUB",
                "reported_money": "1000",
                "reported_blocked": "100",
            }
        ],
        "portfolio_positions": [
            {
                "instrument": {
                    "name": "Секретная тестовая позиция",
                    "ticker": "TEST",
                    "uid": "uid-sensitive-position",
                    "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                    "lot": 1,
                    "currency": "RUB",
                },
                "quantity_units": "2",
                "last_price": {
                    "status": "ok",
                    "price": "100",
                    "time": "2026-07-29T11:59:59+00:00",
                },
                "valuation": {
                    "status": "ok",
                    "currency": "RUB",
                    "values": {"last_price": "200"},
                },
            }
        ],
        "totals_by_currency": [
            {
                "currency": "RUB",
                "cash_reported": "1000",
                "securities_last_price": "200",
                "portfolio_last_price": "1200",
            }
        ],
        "quality": {
            "missing_uid_positions": 0,
            "market_instruments_skipped_by_limit": 0,
            "positions_without_valuation": 0,
            "component_errors": 0,
            "duplicate_uid_occurrences": 0,
        },
        "trading_methods": False,
        "warnings": ["Read-only snapshot."],
    }


def test_safe_event_contains_only_allowlisted_metadata() -> None:
    event = build_safe_event(
        event_name="broker.market.call",
        component="market_data",
        outcome=ObservabilityOutcome.SUCCESS,
        occurred_at=NOW,
        correlation_id="corr:12345678",
        request_id="req:12345678",
        action_id="action:12345678",
        account=AccountReference(masked_id="***3118", account_type="ИИС"),
        duration_ms=Decimal("12.5"),
        external_call=ExternalCallTelemetryV1(
            provider="t-invest",
            operation="GetOrderBook",
            status=ExternalCallStatus.SUCCESS,
            latency_ms=Decimal("10.5"),
            retry_count=1,
            rate_limit_remaining=99,
            circuit_breaker_state=CircuitBreakerState.CLOSED,
            freshness=FreshnessTelemetry.FRESH,
        ),
        quality=DataQuality.VERIFIED,
        completeness=Completeness.COMPLETE,
        metrics=(SafeCountMetricV1(name="items.count", value=3),),
    )
    payload = event.model_dump(mode="json")

    assert payload["contains_sensitive_payload"] is False
    assert payload["trading_methods"] is False
    assert set(payload) == {
        "occurred_at",
        "event_name",
        "severity",
        "component",
        "outcome",
        "correlation_id",
        "request_id",
        "action_id",
        "account",
        "duration_ms",
        "external_call",
        "quality",
        "completeness",
        "error_code",
        "exception_type",
        "metrics",
        "contains_sensitive_payload",
        "trading_methods",
    }
    forbidden = {
        "payload",
        "token",
        "authorization",
        "positions",
        "holdings",
        "amount",
        "document",
        "content",
        "message",
    }
    assert set(payload).isdisjoint(forbidden)


def test_full_account_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="account identifier must be masked"):
        build_safe_event(
            event_name="broker.market.call",
            component="market_data",
            outcome=ObservabilityOutcome.SUCCESS,
            occurred_at=NOW,
            account=AccountReference(masked_id="123456789"),
        )


def test_arbitrary_sensitive_fields_are_forbidden_by_contract() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ObservabilityEventV1.model_validate(
            {
                "occurred_at": NOW,
                "event_name": "broker.market.call",
                "severity": "info",
                "component": "market_data",
                "outcome": "success",
                "correlation_id": "corr:12345678",
                "payload": {"token": "secret"},
            }
        )


def test_rejected_event_requires_code_and_exception_never_contains_message() -> None:
    with pytest.raises(ValidationError, match="requires an error code"):
        build_safe_event(
            event_name="portfolio.shadow.validation",
            component="portfolio_shadow",
            severity=ObservabilitySeverity.WARNING,
            outcome=ObservabilityOutcome.REJECTED,
            occurred_at=NOW,
        )

    event = build_safe_event(
        event_name="portfolio.shadow.validation",
        component="portfolio_shadow",
        severity=ObservabilitySeverity.WARNING,
        outcome=ObservabilityOutcome.REJECTED,
        occurred_at=NOW,
        error_code="PORTFOLIO_CONTRACT_REJECTED",
        exception_type="RuntimeError",
    )
    serialized = event.model_dump_json()
    assert "RuntimeError" in serialized
    assert "do-not-log-this-secret-message" not in serialized


def test_external_not_called_rejects_activity_fields() -> None:
    with pytest.raises(ValidationError, match="cannot have activity"):
        ExternalCallTelemetryV1(
            provider="t-invest",
            operation="GetPortfolio",
            status=ExternalCallStatus.NOT_CALLED,
            latency_ms=Decimal("1"),
        )


def test_metric_names_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="metric names must be unique"):
        build_safe_event(
            event_name="portfolio.shadow.validation",
            component="portfolio_shadow",
            outcome=ObservabilityOutcome.SUCCESS,
            occurred_at=NOW,
            metrics=(
                SafeCountMetricV1(name="items.count", value=1),
                SafeCountMetricV1(name="items.count", value=2),
            ),
        )


def test_trace_ids_are_opaque_and_prefixed() -> None:
    first = new_trace_id("Request ID")
    second = new_trace_id("Request ID")
    assert first.startswith("requestid:")
    assert second.startswith("requestid:")
    assert first != second
    assert len(first) < 128


def test_emit_safe_event_uses_canonical_json_and_requested_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test.observability.emit")
    caplog.set_level(logging.WARNING, logger=logger.name)
    event = build_safe_event(
        event_name="portfolio.shadow.validation",
        component="portfolio_shadow",
        severity=ObservabilitySeverity.WARNING,
        outcome=ObservabilityOutcome.DEGRADED,
        occurred_at=NOW,
        correlation_id="corr:12345678",
        quality=DataQuality.PARTIAL,
        completeness=Completeness.PARTIAL,
    )

    emit_safe_event(logger, event)

    assert len(caplog.records) == 1
    parsed = json.loads(caplog.records[0].message)
    assert parsed["event_name"] == "portfolio.shadow.validation"
    assert parsed["severity"] == "warning"
    assert parsed["correlation_id"] == "corr:12345678"


def test_portfolio_shadow_emits_structured_redacted_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test.observability.shadow")
    caplog.set_level(logging.INFO, logger=logger.name)

    result = validate_portfolio_market_payload_in_shadow(
        _portfolio_payload(),
        logger=logger,
    )

    assert result.decision_ready is True
    assert len(caplog.records) == 1
    parsed = json.loads(caplog.records[0].message)
    assert parsed["event_name"] == "portfolio.shadow.validation"
    assert parsed["outcome"] == "success"
    assert parsed["account"] is None
    assert parsed["metrics"] == [
        {"name": "issues.count", "value": 0},
        {"name": "warnings.count", "value": 1},
        {"name": "positions.count", "value": 1},
        {"name": "cash_balances.count", "value": 1},
        {"name": "currencies.count", "value": 1},
    ]
    payload_derived = {
        key: value
        for key, value in parsed.items()
        if key not in {"occurred_at", "correlation_id", "request_id", "action_id"}
    }
    serialized = json.dumps(
        payload_derived,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    for sensitive in (
        "***3118",
        "Секретная тестовая позиция",
        "uid-sensitive-position",
        "1200",
        "1000",
    ):
        assert sensitive not in serialized


def test_rejected_shadow_event_logs_type_not_exception_text(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import omni_cio.quality.portfolio_shadow as shadow_module

    def fail(_: object) -> object:
        raise RuntimeError("secret exception body")

    monkeypatch.setattr(
        shadow_module,
        "portfolio_snapshot_v1_from_market_payload",
        fail,
    )
    logger = logging.getLogger("test.observability.rejected")
    caplog.set_level(logging.WARNING, logger=logger.name)

    validate_portfolio_market_payload_in_shadow(
        _portfolio_payload(),
        logger=logger,
    )

    parsed = json.loads(caplog.records[0].message)
    assert parsed["outcome"] == "rejected"
    assert parsed["error_code"] == "PORTFOLIO_CONTRACT_REJECTED"
    assert parsed["exception_type"] == "RuntimeError"
    assert "secret exception body" not in caplog.records[0].message
