from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.investment_policy import (
    AccountPolicyType,
    InvestmentObjective,
    InvestmentPolicyStatementV1,
    LiquidityReserveV1,
    PolicyField,
    PolicyFieldProvenanceV1,
    PolicyLifecycle,
    PolicyReadinessBlocker,
    PolicyReadinessStatus,
    PolicySourceKind,
    RiskLevel,
    TaxConstraintStatus,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.policy import assess_investment_policy, policy_fingerprint_sha256


EFFECTIVE = datetime(2026, 1, 1, tzinfo=timezone.utc)
REVIEW_DUE = datetime(2026, 12, 31, tzinfo=timezone.utc)
ASSESS_AT = datetime(2026, 8, 3, tzinfo=timezone.utc)


_REQUIRED_PROVENANCE_FIELDS = (
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
    PolicyField.MINIMUM_CREDIT_QUALITY,
    PolicyField.ALLOWED_MARKETS,
    PolicyField.ALLOWED_INSTRUMENT_TYPES,
    PolicyField.PROHIBITED_INSTRUMENT_TYPES,
    PolicyField.TAX_STATUS,
    PolicyField.ACCOUNT_TYPE,
    PolicyField.REBALANCE_BAND,
)


def _provenance(
    fields: tuple[PolicyField, ...] = _REQUIRED_PROVENANCE_FIELDS,
    *,
    owner_confirmed: bool = True,
) -> tuple[PolicyFieldProvenanceV1, ...]:
    rows: list[PolicyFieldProvenanceV1] = []
    for field in fields:
        rows.append(
            PolicyFieldProvenanceV1(
                field=field,
                source_kind=(
                    PolicySourceKind.VERIFIED_ACCOUNT_DATA
                    if field is PolicyField.ACCOUNT_TYPE
                    else PolicySourceKind.OWNER_INPUT
                ),
                owner_confirmed=(
                    False if field is PolicyField.ACCOUNT_TYPE else owner_confirmed
                ),
                confirmed_at=EFFECTIVE,
                source_id=(
                    "masked-account-fact"
                    if field is PolicyField.ACCOUNT_TYPE
                    else f"owner-{field.value}"
                ),
            )
        )
    return tuple(rows)


def _complete_policy(**updates: object) -> InvestmentPolicyStatementV1:
    payload: dict[str, object] = {
        "policy_id": "ips_owner_v9",
        "version": "1",
        "lifecycle": PolicyLifecycle.ACTIVE,
        "created_at": EFFECTIVE,
        "effective_at": EFFECTIVE,
        "review_due_at": REVIEW_DUE,
        "base_currency": "rub",
        "objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
        "time_horizon_years": Decimal("10"),
        "liquidity_reserve": LiquidityReserveV1(
            amount=Decimal("100000"),
            currency="rub",
        ),
        "risk_willingness": RiskLevel.MODERATE,
        "risk_capacity": RiskLevel.MODERATE,
        "max_drawdown": Decimal("0.20"),
        "max_position_weight": Decimal("0.15"),
        "max_group_weight": Decimal("0.25"),
        "max_sector_weight": Decimal("0.35"),
        "max_currency_weight": Decimal("0.50"),
        "minimum_credit_rating": "A-",
        "credit_rating_scale": "AKRA_RU",
        "allowed_markets": ("moex",),
        "allowed_instrument_types": (
            InstrumentType.BOND,
            InstrumentType.SHARE,
            InstrumentType.ETF,
        ),
        "prohibited_instrument_types": (
            InstrumentType.FUTURE,
            InstrumentType.OPTION,
            InstrumentType.STRUCTURED_PRODUCT,
        ),
        "tax_constraint_status": TaxConstraintStatus.REVIEWED,
        "account_type": AccountPolicyType.BROKERAGE,
        "rebalance_band_weight": Decimal("0.05"),
        "provenance": _provenance(),
    }
    payload.update(updates)
    return InvestmentPolicyStatementV1.model_validate(payload)


def test_complete_owner_confirmed_policy_is_ready_for_personal_sizing() -> None:
    policy = _complete_policy()

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert assessment.status is PolicyReadinessStatus.READY
    assert assessment.ready_for_personal_sizing is True
    assert assessment.blockers == ()
    assert assessment.missing_fields == ()
    assert assessment.missing_provenance == ()
    assert assessment.invalid_provenance == ()
    assert assessment.unconfirmed_owner_fields == ()
    assert assessment.annual_review_required is False
    assert assessment.execution_permissions_unchanged is True


def test_missing_liquidity_reserve_is_not_inferred_as_zero() -> None:
    policy = _complete_policy(liquidity_reserve=None)

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert assessment.ready_for_personal_sizing is False
    assert PolicyField.LIQUIDITY_RESERVE in assessment.missing_fields
    assert PolicyReadinessBlocker.MISSING_REQUIRED_FIELD in assessment.blockers


def test_explicit_zero_reserve_is_distinct_from_missing_reserve() -> None:
    policy = _complete_policy(
        liquidity_reserve=LiquidityReserveV1(amount=Decimal("0"), currency="RUB")
    )

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.LIQUIDITY_RESERVE not in assessment.missing_fields
    assert assessment.ready_for_personal_sizing is True


def test_risk_willingness_and_capacity_are_distinct_required_inputs() -> None:
    policy = _complete_policy(risk_capacity=None)

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.RISK_CAPACITY in assessment.missing_fields
    assert PolicyField.RISK_WILLINGNESS not in assessment.missing_fields
    assert assessment.ready_for_personal_sizing is False


def test_owner_confirmation_is_required_for_personal_constraints() -> None:
    rows = list(_provenance())
    index = next(
        i for i, row in enumerate(rows) if row.field is PolicyField.MAX_DRAWDOWN
    )
    rows[index] = rows[index].model_copy(update={"owner_confirmed": False})
    policy = _complete_policy(provenance=tuple(rows))

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.MAX_DRAWDOWN in assessment.unconfirmed_owner_fields
    assert PolicyReadinessBlocker.OWNER_CONFIRMATION_REQUIRED in assessment.blockers
    assert assessment.ready_for_personal_sizing is False


def test_non_owner_provenance_cannot_assert_owner_confirmation() -> None:
    with pytest.raises(ValidationError, match="non-owner provenance"):
        PolicyFieldProvenanceV1(
            field=PolicyField.RISK_WILLINGNESS,
            source_kind=PolicySourceKind.SYSTEM_SAFE_DEFAULT,
            owner_confirmed=True,
            confirmed_at=EFFECTIVE,
            source_id="safe-default",
        )


def test_system_default_cannot_satisfy_personal_policy_provenance() -> None:
    rows = list(_provenance())
    index = next(
        i for i, row in enumerate(rows) if row.field is PolicyField.RISK_WILLINGNESS
    )
    rows[index] = PolicyFieldProvenanceV1(
        field=PolicyField.RISK_WILLINGNESS,
        source_kind=PolicySourceKind.SYSTEM_SAFE_DEFAULT,
        owner_confirmed=False,
        confirmed_at=EFFECTIVE,
        source_id="safe-default",
    )
    policy = _complete_policy(provenance=tuple(rows))

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.RISK_WILLINGNESS in assessment.invalid_provenance
    assert PolicyReadinessBlocker.INVALID_PROVENANCE in assessment.blockers
    assert assessment.ready_for_personal_sizing is False


def test_verified_account_type_does_not_require_duplicate_owner_confirmation() -> None:
    policy = _complete_policy()
    account_row = next(
        row for row in policy.provenance if row.field is PolicyField.ACCOUNT_TYPE
    )

    assert account_row.owner_confirmed is False
    assert assess_investment_policy(
        policy, assessed_at=ASSESS_AT
    ).ready_for_personal_sizing is True


def test_missing_provenance_blocks_sizing_even_when_value_exists() -> None:
    provenance = tuple(
        row for row in _provenance() if row.field is not PolicyField.TIME_HORIZON
    )
    policy = _complete_policy(provenance=provenance)

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.TIME_HORIZON in assessment.missing_provenance
    assert PolicyReadinessBlocker.MISSING_PROVENANCE in assessment.blockers


def test_bond_policy_requires_rating_and_scale() -> None:
    with pytest.raises(ValidationError, match="minimum credit rating"):
        _complete_policy(minimum_credit_rating=None, credit_rating_scale=None)


def test_non_bond_policy_does_not_require_credit_floor() -> None:
    provenance = tuple(
        row
        for row in _provenance()
        if row.field is not PolicyField.MINIMUM_CREDIT_QUALITY
    )
    policy = _complete_policy(
        allowed_instrument_types=(InstrumentType.SHARE, InstrumentType.ETF),
        minimum_credit_rating=None,
        credit_rating_scale=None,
        provenance=provenance,
    )

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert PolicyField.MINIMUM_CREDIT_QUALITY not in assessment.missing_fields
    assert assessment.ready_for_personal_sizing is True


def test_allowed_and_prohibited_instrument_types_cannot_overlap() -> None:
    with pytest.raises(ValidationError, match="both allowed and prohibited"):
        _complete_policy(prohibited_instrument_types=(InstrumentType.BOND,))


def test_allowed_and_prohibited_markets_cannot_overlap() -> None:
    with pytest.raises(ValidationError, match="market cannot be both allowed and prohibited"):
        _complete_policy(prohibited_markets=("moex",))


def test_material_deny_constraints_require_owner_provenance() -> None:
    policy = _complete_policy(prohibited_markets=("SPB",))
    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)
    assert PolicyField.PROHIBITED_MARKETS in assessment.missing_provenance
    assert assessment.ready_for_personal_sizing is False

    provenance = (*_provenance(), PolicyFieldProvenanceV1(
        field=PolicyField.PROHIBITED_MARKETS,
        source_kind=PolicySourceKind.OWNER_INPUT,
        owner_confirmed=True,
        confirmed_at=EFFECTIVE,
        source_id="owner-prohibited-markets",
    ))
    ready_policy = _complete_policy(prohibited_markets=("SPB",), provenance=provenance)
    assert assess_investment_policy(
        ready_policy, assessed_at=ASSESS_AT
    ).ready_for_personal_sizing is True


def test_policy_collection_inputs_fail_closed_on_scalars() -> None:
    with pytest.raises(ValidationError, match="markets must be a collection"):
        _complete_policy(allowed_markets="MOEX")
    with pytest.raises(ValidationError, match="markets must be a collection"):
        _complete_policy(prohibited_markets=42)
    with pytest.raises(ValidationError, match="instrument types must be a collection"):
        _complete_policy(allowed_instrument_types="share")
    with pytest.raises(ValidationError, match="instrument types must be a collection"):
        _complete_policy(prohibited_instrument_types=42)


def test_group_and_sector_limits_cannot_be_below_position_limit() -> None:
    with pytest.raises(ValidationError, match="group limit"):
        _complete_policy(max_position_weight=Decimal("0.20"), max_group_weight=Decimal("0.10"))
    with pytest.raises(ValidationError, match="sector limit"):
        _complete_policy(max_position_weight=Decimal("0.20"), max_sector_weight=Decimal("0.10"))


def test_reserve_currency_must_match_policy_base_currency() -> None:
    with pytest.raises(ValidationError, match="reserve must use"):
        _complete_policy(
            liquidity_reserve=LiquidityReserveV1(
                amount=Decimal("1000"),
                currency="USD",
            )
        )


def test_annual_review_interval_cannot_exceed_one_year() -> None:
    with pytest.raises(ValidationError, match="cannot exceed one year"):
        _complete_policy(review_due_at=EFFECTIVE + timedelta(days=367))


def test_review_due_policy_fails_closed_for_personal_sizing() -> None:
    policy = _complete_policy()

    assessment = assess_investment_policy(policy, assessed_at=REVIEW_DUE)

    assert assessment.status is PolicyReadinessStatus.REVIEW_DUE
    assert assessment.annual_review_required is True
    assert PolicyReadinessBlocker.POLICY_REVIEW_DUE in assessment.blockers
    assert assessment.ready_for_personal_sizing is False


def test_future_policy_is_not_effective() -> None:
    future = ASSESS_AT + timedelta(days=10)
    policy = _complete_policy(
        created_at=ASSESS_AT,
        effective_at=future,
        review_due_at=future + timedelta(days=365),
    )

    assessment = assess_investment_policy(policy, assessed_at=ASSESS_AT)

    assert assessment.status is PolicyReadinessStatus.NOT_EFFECTIVE
    assert PolicyReadinessBlocker.POLICY_NOT_EFFECTIVE in assessment.blockers


def test_draft_and_superseded_lifecycle_are_not_sizing_ready() -> None:
    draft = assess_investment_policy(
        _complete_policy(lifecycle=PolicyLifecycle.DRAFT),
        assessed_at=ASSESS_AT,
    )
    superseded = assess_investment_policy(
        _complete_policy(lifecycle=PolicyLifecycle.SUPERSEDED),
        assessed_at=ASSESS_AT,
    )

    assert PolicyReadinessBlocker.LIFECYCLE_NOT_ACTIVE in draft.blockers
    assert superseded.status is PolicyReadinessStatus.SUPERSEDED
    assert PolicyReadinessBlocker.POLICY_SUPERSEDED in superseded.blockers


def test_fingerprint_is_stable_for_semantically_identical_ordering() -> None:
    first = _complete_policy(
        allowed_markets=("MOEX", "SPB"),
        allowed_instrument_types=(InstrumentType.SHARE, InstrumentType.BOND, InstrumentType.ETF),
        provenance=_provenance(),
    )
    second = _complete_policy(
        allowed_markets=("spb", "moex"),
        allowed_instrument_types=(InstrumentType.ETF, InstrumentType.BOND, InstrumentType.SHARE),
        provenance=tuple(reversed(_provenance())),
    )

    assert policy_fingerprint_sha256(first) == policy_fingerprint_sha256(second)


def test_fingerprint_changes_when_material_policy_changes() -> None:
    first = _complete_policy(max_position_weight=Decimal("0.15"))
    second = _complete_policy(max_position_weight=Decimal("0.16"))

    assert policy_fingerprint_sha256(first) != policy_fingerprint_sha256(second)


def test_version_supersession_must_be_monotonic() -> None:
    with pytest.raises(ValidationError, match="first IPS version"):
        _complete_policy(version="1", supersedes_version="1")
    with pytest.raises(ValidationError, match="older than version"):
        _complete_policy(version="2", supersedes_version="2")

    policy = _complete_policy(version="2", supersedes_version="1")
    assert policy.supersedes_version == "1"


def test_protected_execution_permissions_cannot_be_enabled_by_ips() -> None:
    for field in (
        "allow_margin",
        "allow_short_sales",
        "allow_withdrawals",
        "allow_transfers",
        "allow_autonomous_real_execution",
    ):
        with pytest.raises(ValidationError):
            _complete_policy(**{field: True})


def test_policy_rejects_raw_notes_and_full_numeric_source_identifiers() -> None:
    payload = _complete_policy().model_dump(mode="python")
    payload["notes"] = "private free text must not become policy configuration"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        InvestmentPolicyStatementV1.model_validate(payload)

    with pytest.raises(ValidationError, match="full account identifier"):
        PolicyFieldProvenanceV1(
            field=PolicyField.ACCOUNT_TYPE,
            source_kind=PolicySourceKind.VERIFIED_ACCOUNT_DATA,
            owner_confirmed=False,
            confirmed_at=EFFECTIVE,
            source_id="1234567890123456",
        )


def test_policy_timestamps_and_assessment_time_must_be_timezone_aware() -> None:
    naive = datetime(2026, 1, 1)
    with pytest.raises(ValidationError, match="timezone-aware"):
        _complete_policy(created_at=naive)

    with pytest.raises(ValueError, match="MUST_BE_AWARE"):
        assess_investment_policy(_complete_policy(), assessed_at=naive)
