from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

from omni_cio.contracts.v1.investment_policy import (
    AccountPolicyType,
    InvestmentPolicyAssessmentV1,
    InvestmentPolicyStatementV1,
    PolicyField,
    PolicyLifecycle,
    PolicyReadinessBlocker,
    PolicyReadinessStatus,
    PolicyReferenceV1,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.portfolio import InstrumentType


_BASE_REQUIRED_FIELDS: tuple[PolicyField, ...] = (
    PolicyField.OBJECTIVE,
    PolicyField.TIME_HORIZON,
    PolicyField.LIQUIDITY_RESERVE,
    PolicyField.RISK_WILLINGNESS,
    PolicyField.RISK_CAPACITY,
    PolicyField.MAX_DRAWDOWN,
    PolicyField.MAX_POSITION_WEIGHT,
    PolicyField.MAX_GROUP_WEIGHT,
    PolicyField.MAX_SECTOR_WEIGHT,
    PolicyField.MAX_CURRENCY_WEIGHT,
    PolicyField.ALLOWED_MARKETS,
    PolicyField.ALLOWED_INSTRUMENT_TYPES,
    PolicyField.TAX_STATUS,
    PolicyField.ACCOUNT_TYPE,
    PolicyField.REBALANCE_BAND,
)

_OWNER_CONFIRMATION_FIELDS = frozenset(
    field for field in _BASE_REQUIRED_FIELDS if field is not PolicyField.ACCOUNT_TYPE
)


class InvestmentPolicyEvaluationError(ValueError):
    """The supplied IPS cannot be assessed safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise InvestmentPolicyEvaluationError(
            "IPS_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE"
        )
    return result.astimezone(timezone.utc)


def _canonical_payload(policy: InvestmentPolicyStatementV1) -> dict[str, object]:
    payload = policy.model_dump(mode="json")
    provenance = payload.get("provenance")
    if isinstance(provenance, list):
        payload["provenance"] = sorted(
            provenance,
            key=lambda row: str(row.get("field", "")) if isinstance(row, dict) else "",
        )
    return payload


def policy_fingerprint_sha256(policy: InvestmentPolicyStatementV1) -> str:
    """Return a deterministic fingerprint for the complete immutable policy payload."""

    serialized = json.dumps(
        _canonical_payload(policy),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def policy_reference(policy: InvestmentPolicyStatementV1) -> PolicyReferenceV1:
    return PolicyReferenceV1(
        policy_id=policy.policy_id,
        version=policy.version,
        fingerprint_sha256=policy_fingerprint_sha256(policy),
    )


def _required_fields(policy: InvestmentPolicyStatementV1) -> tuple[PolicyField, ...]:
    fields = list(_BASE_REQUIRED_FIELDS)
    if InstrumentType.BOND in policy.allowed_instrument_types:
        fields.append(PolicyField.MINIMUM_CREDIT_QUALITY)
    return tuple(fields)


def _field_is_present(policy: InvestmentPolicyStatementV1, field: PolicyField) -> bool:
    checks = {
        PolicyField.OBJECTIVE: policy.objective is not None,
        PolicyField.TIME_HORIZON: policy.time_horizon_years is not None,
        PolicyField.LIQUIDITY_RESERVE: policy.liquidity_reserve is not None,
        PolicyField.RISK_WILLINGNESS: policy.risk_willingness is not None,
        PolicyField.RISK_CAPACITY: policy.risk_capacity is not None,
        PolicyField.MAX_DRAWDOWN: policy.max_drawdown is not None,
        PolicyField.MAX_POSITION_WEIGHT: policy.max_position_weight is not None,
        PolicyField.MAX_GROUP_WEIGHT: policy.max_group_weight is not None,
        PolicyField.MAX_SECTOR_WEIGHT: policy.max_sector_weight is not None,
        PolicyField.MAX_CURRENCY_WEIGHT: policy.max_currency_weight is not None,
        PolicyField.MINIMUM_CREDIT_QUALITY: (
            policy.minimum_credit_rating is not None
            and policy.credit_rating_scale is not None
        ),
        PolicyField.ALLOWED_MARKETS: bool(policy.allowed_markets),
        PolicyField.ALLOWED_INSTRUMENT_TYPES: bool(
            policy.allowed_instrument_types
        ),
        PolicyField.TAX_STATUS: (
            policy.tax_constraint_status is not TaxConstraintStatus.UNKNOWN
        ),
        PolicyField.ACCOUNT_TYPE: (
            policy.account_type is not AccountPolicyType.UNKNOWN
        ),
        PolicyField.REBALANCE_BAND: policy.rebalance_band_weight is not None,
    }
    return checks[field]


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def assess_investment_policy(
    policy: InvestmentPolicyStatementV1,
    *,
    assessed_at: datetime | None = None,
) -> InvestmentPolicyAssessmentV1:
    """Evaluate IPS completeness and personal-sizing readiness without inference."""

    now = _aware_utc(assessed_at)
    required = _required_fields(policy)
    missing_fields = tuple(
        field for field in required if not _field_is_present(policy, field)
    )

    provenance_by_field = {row.field: row for row in policy.provenance}
    missing_provenance = tuple(
        field
        for field in required
        if field not in missing_fields and field not in provenance_by_field
    )

    owner_confirmation_fields = set(_OWNER_CONFIRMATION_FIELDS)
    if PolicyField.MINIMUM_CREDIT_QUALITY in required:
        owner_confirmation_fields.add(PolicyField.MINIMUM_CREDIT_QUALITY)
    unconfirmed_owner_fields = tuple(
        field
        for field in required
        if field not in missing_fields
        and field not in missing_provenance
        and field in owner_confirmation_fields
        and not provenance_by_field[field].owner_confirmed
    )

    blockers: list[PolicyReadinessBlocker] = []
    if policy.lifecycle is PolicyLifecycle.SUPERSEDED:
        _append_unique(blockers, PolicyReadinessBlocker.POLICY_SUPERSEDED)
    elif policy.lifecycle is not PolicyLifecycle.ACTIVE:
        _append_unique(blockers, PolicyReadinessBlocker.LIFECYCLE_NOT_ACTIVE)

    if now < policy.effective_at:
        _append_unique(blockers, PolicyReadinessBlocker.POLICY_NOT_EFFECTIVE)
    if now >= policy.review_due_at:
        _append_unique(blockers, PolicyReadinessBlocker.POLICY_REVIEW_DUE)
    if missing_fields:
        _append_unique(blockers, PolicyReadinessBlocker.MISSING_REQUIRED_FIELD)
    if missing_provenance:
        _append_unique(blockers, PolicyReadinessBlocker.MISSING_PROVENANCE)
    if unconfirmed_owner_fields:
        _append_unique(blockers, PolicyReadinessBlocker.OWNER_CONFIRMATION_REQUIRED)

    if not blockers:
        status = PolicyReadinessStatus.READY
    elif policy.lifecycle is PolicyLifecycle.SUPERSEDED:
        status = PolicyReadinessStatus.SUPERSEDED
    elif now < policy.effective_at:
        status = PolicyReadinessStatus.NOT_EFFECTIVE
    elif now >= policy.review_due_at:
        status = PolicyReadinessStatus.REVIEW_DUE
    else:
        status = PolicyReadinessStatus.DRAFT

    return InvestmentPolicyAssessmentV1(
        assessed_at=now,
        reference=policy_reference(policy),
        status=status,
        ready_for_personal_sizing=not blockers,
        missing_fields=missing_fields,
        missing_provenance=missing_provenance,
        unconfirmed_owner_fields=unconfirmed_owner_fields,
        blockers=tuple(blockers),
        annual_review_required=now >= policy.review_due_at,
    )
