from __future__ import annotations

import logging
from copy import deepcopy

import pytest

import omni_cio.quality.portfolio_shadow as shadow_module
from omni_cio.quality import (
    PortfolioDataQualityGateError,
    PortfolioShadowStatus,
    require_portfolio_decision_ready,
    validate_portfolio_market_payload_in_shadow,
    wrap_portfolio_market_snapshot_with_shadow_validation,
)


def _payload() -> dict[str, object]:
    return {
        "status": "ok",
        "version": "3.9.1",
        "retrieved_at": "2026-07-28T17:00:00+00:00",
        "source_snapshot_retrieved_at": "2026-07-28T16:59:58+00:00",
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
                    "name": "Тестовая акция",
                    "ticker": "TEST",
                    "uid": "uid-share",
                    "instrument_kind": "INSTRUMENT_TYPE_SHARE",
                    "lot": 1,
                    "currency": "RUB",
                },
                "quantity_units": "2",
                "last_price": {
                    "status": "ok",
                    "price": "100",
                    "time": "2026-07-28T16:59:59+00:00",
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


def test_verified_snapshot_is_decision_ready_without_sensitive_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = _payload()
    logger = logging.getLogger("test.shadow.ready")
    caplog.set_level(logging.INFO, logger=logger.name)

    result = validate_portfolio_market_payload_in_shadow(payload, logger=logger)

    assert result.status == PortfolioShadowStatus.READY
    assert result.decision_ready is True
    assert result.position_count == 1
    assert result.cash_balance_count == 1
    assert result.currency_count == 1
    require_portfolio_decision_ready(result)

    logs = caplog.text
    for sensitive_value in ("***3118", "Тестовая акция", "uid-share", "1200"):
        assert sensitive_value not in logs


def test_partial_snapshot_is_observed_but_blocked_by_decision_gate() -> None:
    payload = _payload()
    payload["status"] = "partial"
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality["positions_without_valuation"] = 1
    positions = payload["portfolio_positions"]
    assert isinstance(positions, list)
    positions[0]["last_price"] = {"status": "unavailable"}
    positions[0]["valuation"] = {"status": "unavailable", "values": {}}
    payload["totals_by_currency"] = [
        {
            "currency": "RUB",
            "cash_reported": "1000",
            "securities_last_price": "0",
            "portfolio_last_price": "1000",
        }
    ]

    result = validate_portfolio_market_payload_in_shadow(
        payload,
        logger=logging.getLogger("test.shadow.partial"),
    )

    assert result.status == PortfolioShadowStatus.PARTIAL
    assert result.decision_ready is False
    assert result.issue_count == 1
    with pytest.raises(
        PortfolioDataQualityGateError,
        match="PORTFOLIO_SNAPSHOT_NOT_DECISION_READY",
    ):
        require_portfolio_decision_ready(result)


def test_rejected_snapshot_fails_closed_without_logging_raw_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = _payload()
    account = payload["account"]
    assert isinstance(account, dict)
    account["masked_id"] = "123456789"
    logger = logging.getLogger("test.shadow.rejected")
    caplog.set_level(logging.WARNING, logger=logger.name)

    result = validate_portfolio_market_payload_in_shadow(payload, logger=logger)

    assert result.status == PortfolioShadowStatus.REJECTED
    assert result.decision_ready is False
    assert result.error_code == "PORTFOLIO_CONTRACT_REJECTED"
    assert result.exception_type == "ValidationError"
    assert "123456789" not in caplog.text
    assert "account identifier must be masked" not in caplog.text
    with pytest.raises(
        PortfolioDataQualityGateError,
        match="PORTFOLIO_CONTRACT_REJECTED",
    ):
        require_portfolio_decision_ready(result)


def test_unexpected_validator_failure_is_contained_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_marker = "do-not-log-this-marker"

    def fail(_: object) -> object:
        raise RuntimeError(sensitive_marker)

    monkeypatch.setattr(
        shadow_module,
        "portfolio_snapshot_v1_from_market_payload",
        fail,
    )
    logger = logging.getLogger("test.shadow.internal")
    caplog.set_level(logging.WARNING, logger=logger.name)

    result = validate_portfolio_market_payload_in_shadow(_payload(), logger=logger)

    assert result.status == PortfolioShadowStatus.REJECTED
    assert result.exception_type == "RuntimeError"
    assert sensitive_marker not in caplog.text


def test_shadow_validation_does_not_mutate_source_payload() -> None:
    payload = _payload()
    original = deepcopy(payload)

    validate_portfolio_market_payload_in_shadow(
        payload,
        logger=logging.getLogger("test.shadow.immutable"),
    )

    assert payload == original


def test_runtime_wrapper_preserves_payload_identity_and_is_idempotent() -> None:
    payload = _payload()
    calls = 0

    def source_call(*, depth: int) -> dict[str, object]:
        nonlocal calls
        calls += 1
        assert depth == 1
        return payload

    wrapped = wrap_portfolio_market_snapshot_with_shadow_validation(
        source_call,
        logger=logging.getLogger("test.shadow.wrapper"),
    )
    wrapped_twice = wrap_portfolio_market_snapshot_with_shadow_validation(
        wrapped,
        logger=logging.getLogger("test.shadow.wrapper"),
    )

    result = wrapped_twice(depth=1)

    assert result is payload
    assert calls == 1
    assert wrapped_twice is wrapped
