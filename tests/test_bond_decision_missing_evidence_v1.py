from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.bond_decision import BondDecisionEvidenceV1
from omni_cio.contracts.v1.decision import DecisionEvidenceKind


def test_missing_duration_evidence_can_retain_policy_limit() -> None:
    evidence = BondDecisionEvidenceV1(
        evidence_id="bond.credit.missing_duration",
        kind=DecisionEvidenceKind.MISSING_DATA,
        statement="Bond duration is unavailable.",
        source_schema="bond_credit_risk_assessment",
        source_id="uid:bond-a",
        observed_value=None,
        limit_value=Decimal("5"),
        instrument_key="uid:bond-a",
    )

    assert evidence.observed_value is None
    assert evidence.limit_value == Decimal("5")


def test_non_missing_evidence_still_requires_observed_value_for_limit() -> None:
    with pytest.raises(ValidationError, match="requires observed value"):
        BondDecisionEvidenceV1(
            evidence_id="bond.credit.invalid_duration",
            kind=DecisionEvidenceKind.FACT,
            statement="Bond duration was expected but is absent.",
            source_schema="bond_credit_risk_assessment",
            source_id="uid:bond-a",
            observed_value=None,
            limit_value=Decimal("5"),
            instrument_key="uid:bond-a",
        )
