from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, cast

import pytest

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyError,
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_source_event,
)


NOW = datetime(2026, 8, 1, 8, 30, tzinfo=timezone.utc)
CORRELATION = "corr:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _unavailable_source_event(*, duration_ms: Decimal | None = None):
    snapshot = ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
    )
    return build_expert_ra_rating_actions_source_event(
        snapshot,
        occurred_at=NOW,
        duration_ms=duration_ms,
        correlation_id=CORRELATION,
    )


def test_falsy_wrong_type_policy_does_not_silently_select_default() -> None:
    with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
        ExpertRaRatingActionsAlertPolicyEvaluatorV1(cast(Any, {}))


def test_known_source_event_rejects_forged_domain_error_code() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1()
    forged = _unavailable_source_event().model_copy(
        update={"error_code": "FORGED_ERROR_CODE"}
    )

    with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
        evaluator.evaluate(forged)
    assert evaluator.state_count == 0


def test_known_event_requires_canonical_external_latency_projection() -> None:
    evaluator = ExpertRaRatingActionsAlertPolicyEvaluatorV1()
    valid = _unavailable_source_event(duration_ms=Decimal("5"))
    assert valid.external_call is not None
    forged_call = valid.external_call.model_copy(
        update={"latency_ms": Decimal("6")}
    )
    forged = valid.model_copy(update={"external_call": forged_call})

    with pytest.raises(ExpertRaRatingActionsAlertPolicyError):
        evaluator.evaluate(forged)
    assert evaluator.state_count == 0
