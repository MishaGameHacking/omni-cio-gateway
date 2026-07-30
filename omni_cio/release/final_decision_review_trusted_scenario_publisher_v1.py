from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from threading import RLock

from omni_cio.contracts.v1.capacity import OrderSide
from omni_cio.contracts.v1.common import AccountReference, SourceReference
from omni_cio.contracts.v1.decision_capacity_pretrade import (
    CapacityPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.decision_capacity_sell_pretrade import (
    CapacitySellPreTradeDecisionGateV1,
)
from omni_cio.contracts.v1.final_decision_review_trusted_scenario import (
    TrustedScenarioPublicationDisposition,
    TrustedScenarioPublicationResultV1,
)
from omni_cio.contracts.v1.risk import RiskPolicyEvaluationV1
from omni_cio.release.final_decision_review_production_sources_v1 import (
    FinalDecisionReviewScenarioSourceStoreV1,
)


_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{2,127}$")


class FinalDecisionReviewTrustedScenarioPublisherError(ValueError):
    """A scenario bundle cannot cross the trusted publication boundary safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _safe_identifier(value: str, *, code: str) -> str:
    result = value.strip()
    if _SAFE_IDENTIFIER.fullmatch(result) is None:
        raise FinalDecisionReviewTrustedScenarioPublisherError(code)
    return result


def _gate_account_and_instruments(
    gate: CapacityPreTradeDecisionGateV1 | CapacitySellPreTradeDecisionGateV1,
    *,
    direction: OrderSide,
) -> tuple[AccountReference, tuple[str, ...]]:
    requests = gate.base_intent_gate.request.expected_capacity_requests
    if not requests:
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_REQUESTS_EMPTY"
        )
    if any(request.side is not direction for request in requests):
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_DIRECTION_MISMATCH"
        )
    instrument_keys = tuple(request.instrument_key for request in requests)
    if len(set(instrument_keys)) != len(instrument_keys):
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_INSTRUMENTS_DUPLICATE"
        )

    if not gate.coverage:
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_ACCOUNT_UNAVAILABLE"
        )
    accounts = tuple(row.preview.metadata.account for row in gate.coverage)
    account = accounts[0]
    if any(candidate != account for candidate in accounts):
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_GATE_ACCOUNT_MISMATCH"
        )
    coverage_keys = tuple(row.instrument_key for row in gate.coverage)
    if set(coverage_keys) != set(instrument_keys):
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_COVERAGE_MISMATCH"
        )
    return account, instrument_keys


def _validate_safety_flags(
    gate: CapacityPreTradeDecisionGateV1 | CapacitySellPreTradeDecisionGateV1,
    pro_forma_risk: RiskPolicyEvaluationV1,
) -> None:
    if gate.order_created or gate.execution_ready or gate.trading_methods:
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_GATE_NOT_READ_ONLY"
        )
    policy = pro_forma_risk.policy
    if any(
        (
            policy.allow_margin,
            policy.allow_short_sales,
            policy.allow_derivatives,
            policy.allow_currency_operations,
        )
    ):
        raise FinalDecisionReviewTrustedScenarioPublisherError(
            "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_RISK_POLICY_UNSAFE"
        )


class FinalDecisionReviewTrustedScenarioPublisherV1:
    """Trusted internal publisher for exact typed scenario source artifacts."""

    def __init__(
        self,
        *,
        source_store: FinalDecisionReviewScenarioSourceStoreV1,
        max_source_age_seconds: int = 900,
        future_tolerance_seconds: int = 60,
    ) -> None:
        if not 1 <= max_source_age_seconds <= 86_400:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_MAX_AGE_INVALID"
            )
        if not 0 <= future_tolerance_seconds <= 3_600:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_FUTURE_TOLERANCE_INVALID"
            )
        self._source_store = source_store
        self._max_source_age_seconds = max_source_age_seconds
        self._future_tolerance_seconds = future_tolerance_seconds
        self._lock = RLock()

    @property
    def source_store(self) -> FinalDecisionReviewScenarioSourceStoreV1:
        return self._source_store

    def publish(
        self,
        *,
        scenario_id: str,
        pro_forma_risk: RiskPolicyEvaluationV1,
        purchase_gate: CapacityPreTradeDecisionGateV1 | None = None,
        sell_gate: CapacitySellPreTradeDecisionGateV1 | None = None,
        provider: str,
        operation: str,
        published_at: datetime | None = None,
    ) -> TrustedScenarioPublicationResultV1:
        key = _safe_identifier(
            scenario_id,
            code="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_ID_INVALID",
        )
        safe_provider = _safe_identifier(
            provider,
            code="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_PROVIDER_INVALID",
        )
        safe_operation = _safe_identifier(
            operation,
            code="FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_OPERATION_INVALID",
        )
        now = _aware_utc(published_at)

        direction_count = int(purchase_gate is not None) + int(sell_gate is not None)
        if direction_count != 1:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_DIRECTION_INVALID"
            )
        if not isinstance(pro_forma_risk, RiskPolicyEvaluationV1):
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_PRO_FORMA_TYPE_INVALID"
            )

        if purchase_gate is not None:
            if not isinstance(purchase_gate, CapacityPreTradeDecisionGateV1):
                raise FinalDecisionReviewTrustedScenarioPublisherError(
                    "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_PURCHASE_GATE_TYPE_INVALID"
                )
            gate = purchase_gate
            direction = OrderSide.BUY
        else:
            if not isinstance(sell_gate, CapacitySellPreTradeDecisionGateV1):
                raise FinalDecisionReviewTrustedScenarioPublisherError(
                    "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_SELL_GATE_TYPE_INVALID"
                )
            gate = sell_gate
            direction = OrderSide.SELL

        gate_time = _aware_utc(gate.assessed_at)
        risk_time = _aware_utc(pro_forma_risk.metadata.retrieved_at)
        if gate_time != risk_time:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_TIMESTAMP_MISMATCH"
            )
        age_seconds = (now - gate_time).total_seconds()
        if age_seconds > self._max_source_age_seconds:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_STALE"
            )
        if age_seconds < -self._future_tolerance_seconds:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_FROM_FUTURE"
            )

        account, instrument_keys = _gate_account_and_instruments(
            gate,
            direction=direction,
        )
        if pro_forma_risk.metadata.account != account:
            raise FinalDecisionReviewTrustedScenarioPublisherError(
                "FINAL_DECISION_REVIEW_TRUSTED_SCENARIO_RISK_ACCOUNT_MISMATCH"
            )
        _validate_safety_flags(gate, pro_forma_risk)

        with self._lock:
            publication = self._source_store.publish(
                scenario_id=key,
                purchase_gate=purchase_gate,
                sell_gate=sell_gate,
                pro_forma_risk=pro_forma_risk,
                published_at=now,
            )

        disposition = (
            TrustedScenarioPublicationDisposition.REPLACED
            if publication.replaced
            else TrustedScenarioPublicationDisposition.PUBLISHED
        )
        return TrustedScenarioPublicationResultV1(
            disposition=disposition,
            scenario_id=key,
            direction=direction,
            account=account,
            gate_assessed_at=gate_time,
            pro_forma_retrieved_at=risk_time,
            published_at=publication.published_at,
            expires_at=publication.published_at
            + timedelta(seconds=self._source_store.ttl_seconds),
            source=SourceReference(
                provider=safe_provider,
                operation=safe_operation,
                retrieved_at=gate_time,
            ),
            instrument_count=len(instrument_keys),
            gate_ready=gate.gate_ready,
            pro_forma_decision_ready=pro_forma_risk.decision_ready,
            source_replaced=publication.replaced,
            source_evicted=publication.evicted,
            active_bundle_count=publication.active_bundle_count,
        )
