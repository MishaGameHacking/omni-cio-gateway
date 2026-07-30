from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from threading import Lock

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteCacheResultV1,
    MoexIssTqbrQuoteSnapshotV1,
    MoexQuoteCacheErrorCode,
    MoexQuoteCacheStatus,
)
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertDisposition,
    MoexQuoteAlertEvidenceV1,
    MoexQuoteAlertPolicyV1,
)
from omni_cio.observability.moex_iss_quote_alert_policy_v1 import (
    MoexQuoteAlertPolicyEvaluatorV1,
)
from omni_cio.observability.moex_iss_quote_operations_lifecycle_v1 import (
    MoexQuoteOperationsLifecycleError,
    MoexQuoteOperationsLifecycleV1,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
CORRELATION = "corr:moexoperationsevidence"


def _available_snapshot(*, retrieved_at: datetime = NOW) -> MoexIssTqbrQuoteSnapshotV1:
    source = MarketSourceV1(
        provider="Moscow Exchange ISS",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=retrieved_at,
        source_id="ISS.stock.shares.TQBR.marketdata",
    )
    return MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=retrieved_at,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=MarketQuoteV1(
            instrument_key="MOEX:TQBR:SBER",
            currency="RUB",
            as_of=retrieved_at - timedelta(minutes=15),
            source=source,
            last_price=Decimal("310.25"),
            best_bid=Decimal("310.20"),
            best_ask=Decimal("310.30"),
        ),
        short_name="Sberbank",
        lot_size=10,
        decimals=2,
    )


def _unavailable_snapshot(*, retrieved_at: datetime) -> MoexIssTqbrQuoteSnapshotV1:
    return MoexIssTqbrQuoteSnapshotV1(
        secid="SBER",
        retrieved_at=retrieved_at,
        status=MoexIssQuoteStatus.UNAVAILABLE,
        error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
    )


def _cache_result(status: str, *, checked_at: datetime) -> MoexIssTqbrQuoteCacheResultV1:
    snapshot = _available_snapshot()
    if status == "fresh":
        return MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=checked_at,
            status=MoexQuoteCacheStatus.FRESH,
            snapshot=snapshot,
            age_seconds=900,
            fresh_until=checked_at + timedelta(seconds=30),
            stale_until=checked_at + timedelta(seconds=300),
            served_from_cache=True,
            display_value_allowed=True,
        )
    if status == "stale":
        return MoexIssTqbrQuoteCacheResultV1(
            secid="SBER",
            checked_at=checked_at,
            status=MoexQuoteCacheStatus.STALE,
            snapshot=snapshot,
            age_seconds=961,
            fresh_until=checked_at - timedelta(seconds=1),
            stale_until=checked_at + timedelta(seconds=300),
            served_from_cache=True,
            stale_available=True,
            stale_value_exposed=True,
            refresh_attempted=True,
            refresh_succeeded=False,
            source_error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
            cache_error_code=MoexQuoteCacheErrorCode.REFRESH_FAILED,
            display_value_allowed=True,
        )
    return MoexIssTqbrQuoteCacheResultV1(
        secid="SBER",
        checked_at=checked_at,
        status=MoexQuoteCacheStatus.UNAVAILABLE,
        refresh_attempted=True,
        refresh_succeeded=False,
        source_error_code=MoexIssQuoteErrorCode.HTTP_ERROR,
        cache_error_code=MoexQuoteCacheErrorCode.EMPTY,
        display_value_allowed=False,
    )


def _evaluator(*, threshold: int = 2) -> MoexQuoteAlertPolicyEvaluatorV1:
    return MoexQuoteAlertPolicyEvaluatorV1(
        MoexQuoteAlertPolicyV1(
            source_unavailable_threshold=threshold,
            cache_unavailable_threshold=threshold,
            stale_value_threshold=threshold,
            refresh_failure_threshold=threshold,
            cooldown_seconds=60,
            state_retention_seconds=600,
        )
    )


def test_pending_does_not_create_evidence_but_fired_and_recovered_do() -> None:
    lifecycle = MoexQuoteOperationsLifecycleV1(evaluator=_evaluator())

    pending = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )
    fired = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )
    recovered = lifecycle.observe_source(
        _available_snapshot(retrieved_at=NOW + timedelta(seconds=2)),
        correlation_id=CORRELATION,
    )

    assert pending.evaluations[0].disposition is MoexQuoteAlertDisposition.PENDING
    assert pending.evidence == ()
    assert fired.evidence[0].disposition is MoexQuoteAlertDisposition.FIRED
    assert recovered.evidence[0].disposition is MoexQuoteAlertDisposition.RECOVERED
    assert lifecycle.evidence_count == 2
    assert lifecycle.evidence() == fired.evidence + recovered.evidence


def test_evidence_contract_rejects_non_terminal_dispositions() -> None:
    with pytest.raises(ValidationError):
        MoexQuoteAlertEvidenceV1(
            evidence_id="moex-alert-evidence:abcdefgh",
            recorded_at=NOW,
            correlation_id=CORRELATION,
            source_event_name="market.moex_iss_tqbr_quote.source",
            disposition=MoexQuoteAlertDisposition.PENDING,
            kind="source_unavailable",
            severity="error",
            consecutive_occurrences=1,
            threshold=2,
            error_code="MOEX_QUOTE_SOURCE_UNAVAILABLE",
        )


def test_event_sink_runs_before_evidence_sink_under_one_call() -> None:
    order: list[str] = []
    lifecycle = MoexQuoteOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=lambda event: order.append(f"event:{event.event_name}"),
        evidence_sink=lambda item: order.append(f"evidence:{item.disposition.value}"),
    )

    batch = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 0
    assert order == [
        "event:market.moex_iss_tqbr_quote.source",
        "evidence:fired",
    ]


def test_sink_exceptions_are_reduced_to_count_without_exception_text() -> None:
    def broken_event_sink(_event) -> None:
        raise RuntimeError("private upstream text")

    def broken_evidence_sink(_evidence) -> None:
        raise RuntimeError("private evidence text")

    lifecycle = MoexQuoteOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=broken_event_sink,
        evidence_sink=broken_evidence_sink,
    )
    batch = lifecycle.observe_cache(
        _cache_result("unavailable", checked_at=NOW),
        correlation_id=CORRELATION,
    )

    assert batch.sink_failure_count == 2
    serialized = json.dumps(
        {
            "event": batch.event.model_dump(mode="json"),
            "evaluations": [item.model_dump(mode="json") for item in batch.evaluations],
            "evidence": [item.model_dump(mode="json") for item in batch.evidence],
            "sink_failure_count": batch.sink_failure_count,
        },
        sort_keys=True,
    )
    assert "private upstream text" not in serialized
    assert "private evidence text" not in serialized


def test_cache_fired_and_recovered_evidence_use_global_scope() -> None:
    lifecycle = MoexQuoteOperationsLifecycleV1(evaluator=_evaluator(threshold=1))
    fired = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    )
    recovered = lifecycle.observe_cache(
        _cache_result("fresh", checked_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )

    assert fired.evidence[0].scope == "global_moex_tqbr_feed"
    assert recovered.evidence[0].scope == "global_moex_tqbr_feed"
    assert fired.evidence[0].instrument_identity_present is False
    assert fired.evidence[0].financial_values_present is False
    assert fired.evidence[0].external_notification_sent is False


def test_retention_pruning_capacity_eviction_and_clear() -> None:
    lifecycle = MoexQuoteOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        retention_seconds=60,
        capacity=2,
    )
    first = lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    lifecycle.observe_source(
        _available_snapshot(retrieved_at=NOW + timedelta(seconds=1)),
        correlation_id=CORRELATION,
    )
    lifecycle.observe_source(
        _unavailable_snapshot(retrieved_at=NOW + timedelta(seconds=61)),
        correlation_id=CORRELATION,
    )

    retained = lifecycle.evidence(checked_at=NOW + timedelta(seconds=61))
    assert len(retained) <= 2
    assert first.evidence_id not in {item.evidence_id for item in retained}

    lifecycle.clear()
    assert lifecycle.evidence_count == 0
    assert lifecycle.evidence(checked_at=NOW + timedelta(seconds=62)) == ()


def test_invalid_configuration_fails_closed() -> None:
    with pytest.raises(MoexQuoteOperationsLifecycleError):
        MoexQuoteOperationsLifecycleV1(retention_seconds=59)
    with pytest.raises(MoexQuoteOperationsLifecycleError):
        MoexQuoteOperationsLifecycleV1(capacity=0)
    with pytest.raises(MoexQuoteOperationsLifecycleError):
        MoexQuoteOperationsLifecycleV1(event_sink="not-callable")  # type: ignore[arg-type]
    with pytest.raises(MoexQuoteOperationsLifecycleError):
        MoexQuoteOperationsLifecycleV1(evidence_sink=object())  # type: ignore[arg-type]


def test_evidence_serialization_excludes_market_identity_and_values() -> None:
    lifecycle = MoexQuoteOperationsLifecycleV1(evaluator=_evaluator(threshold=1))
    item = lifecycle.observe_cache(
        _cache_result("stale", checked_at=NOW),
        correlation_id=CORRELATION,
    ).evidence[0]
    serialized = json.dumps(item.model_dump(mode="json"), sort_keys=True)

    for forbidden in (
        "SBER",
        "310.25",
        "310.20",
        "310.30",
        "secid",
        "instrument_key",
        "last_price",
        "best_bid",
        "best_ask",
        "as_of",
        "account",
        "raw_json",
        "exception",
    ):
        assert forbidden not in serialized
    assert item.contains_sensitive_payload is False
    assert item.trading_methods is False


def test_concurrent_calls_preserve_event_then_evidence_pair_order() -> None:
    order: list[str] = []
    order_lock = Lock()

    def event_sink(event) -> None:
        with order_lock:
            order.append(f"event:{event.correlation_id}")

    def evidence_sink(evidence) -> None:
        with order_lock:
            order.append(f"evidence:{evidence.correlation_id}")

    lifecycle = MoexQuoteOperationsLifecycleV1(
        evaluator=_evaluator(threshold=1),
        event_sink=event_sink,
        evidence_sink=evidence_sink,
        capacity=64,
    )
    correlations = [f"corr:moexoperation{letter}" for letter in "abcdefgh"]

    def observe(correlation: str) -> None:
        lifecycle.observe_source(
            _unavailable_snapshot(retrieved_at=NOW),
            correlation_id=correlation,
        )
        lifecycle.observe_source(
            _available_snapshot(retrieved_at=NOW),
            correlation_id=correlation,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(observe, correlations))

    for index, entry in enumerate(order):
        if entry.startswith("evidence:"):
            correlation = entry.removeprefix("evidence:")
            assert index > 0
            assert order[index - 1] == f"event:{correlation}"


def test_module_has_no_route_notification_or_write_surface() -> None:
    import omni_cio.observability.moex_iss_quote_operations_lifecycle_v1 as module

    for forbidden in (
        "app",
        "router",
        "webhook",
        "send_email",
        "telegram",
        "pager",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
