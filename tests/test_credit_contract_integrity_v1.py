from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from omni_cio.contracts.v1.credit import (
    CreditCouponType,
    CreditDefaultEventType,
    CreditDefaultEventV1,
    CreditEntityIdentityV1,
    CreditEntityKind,
    CreditEvidenceInputV1,
    CreditFinancialMetricV1,
    CreditMetricKind,
    CreditMetricUnit,
    CreditRatingAction,
    CreditRatingAgency,
    CreditRatingObservationV1,
    CreditRatingScale,
    CreditRatingSubject,
    CreditReanalysisTriggerCode,
    DebtIssueTermsV1,
    DebtSeniority,
)
from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyStatementV1,
    PolicyLifecycle,
)
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import (
    EvidenceFactType,
    EvidenceSourceClass,
    EvidenceUse,
    EvidenceValueType,
    EvidenceValueV1,
    ResearchDossierV1,
    ResearchSourceV1,
    ResearchTargetV1,
    make_evidence_record,
    research_dossier_sha256,
)
from omni_cio.credit import build_credit_passport


NOW = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
TARGET = ResearchTargetV1(
    funnel_sha256="1" * 64,
    candidate_id="uid:bond-1",
    instrument_uid="bond-1",
    instrument_type=InstrumentType.BOND,
)


def _source() -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="rating-agency-test",
        source_class=EvidenceSourceClass.RATING_AGENCY,
        authority=SourceAuthority.OFFICIAL,
        source_id="rating-source",
        retrieved_at=NOW,
    )


def _record(key: str, value: str):
    return make_evidence_record(
        instrument_uid=TARGET.instrument_uid,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=key,
        value=EvidenceValueV1(
            value_type=EvidenceValueType.TEXT,
            canonical_value=value,
        ),
        source=_source(),
        use=EvidenceUse.DECISION_GRADE,
        published_at=NOW,
        effective_at=NOW,
    )


def _dossier(*records) -> ResearchDossierV1:
    values = {
        "schema_version": "1.0",
        "target": TARGET,
        "assessed_at": NOW,
        "requirements": (),
        "probes": (),
        "records": tuple(records),
        "contradictions": (),
        "coverage_gaps": (),
        "duplicate_records_removed": 0,
        "dossier_sha256": "0" * 64,
        "decision_ready": True,
        "strong_recommendation_allowed": True,
        "raw_content_stored": False,
        "trading_methods": False,
    }
    provisional = ResearchDossierV1.model_construct(**values)
    values["dossier_sha256"] = research_dossier_sha256(provisional)
    return ResearchDossierV1.model_validate(values)


def _issuer(source_hash: str) -> CreditEntityIdentityV1:
    return CreditEntityIdentityV1(
        entity_id="credit_issuer_1",
        kind=CreditEntityKind.ISSUER,
        name="Issuer One",
        source_record_sha256s=(source_hash,),
    )


def _terms(source_hash: str) -> DebtIssueTermsV1:
    return DebtIssueTermsV1(
        instrument_uid=TARGET.instrument_uid,
        issuer_entity_id="credit_issuer_1",
        seniority=DebtSeniority.SENIOR_UNSECURED,
        source_record_sha256s=(source_hash,),
    )


def _rating(
    source_hash: str,
    *,
    observation_id: str,
    rating: str,
    effective_at: datetime,
    action: CreditRatingAction = CreditRatingAction.AFFIRMED,
    outlook: str | None = "stable",
) -> CreditRatingObservationV1:
    return CreditRatingObservationV1(
        observation_id=observation_id,
        subject=CreditRatingSubject.ISSUE,
        subject_id=TARGET.instrument_uid,
        agency=CreditRatingAgency.ACRA,
        scale=CreditRatingScale.ACRA_RU_NATIONAL,
        rating=rating,
        outlook=outlook,
        action=action,
        effective_at=effective_at,
        source_record_sha256s=(source_hash,),
    )


def _policy() -> InvestmentPolicyStatementV1:
    return InvestmentPolicyStatementV1(
        policy_id="ips_test",
        version="1",
        lifecycle=PolicyLifecycle.ACTIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        review_due_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        minimum_credit_rating="A-(RU)",
        credit_rating_scale="ACRA",
    )


def _evidence(
    dossier: ResearchDossierV1,
    source_hash: str,
    ratings: tuple[CreditRatingObservationV1, ...],
    *,
    financial_metrics: tuple[CreditFinancialMetricV1, ...] = (),
) -> CreditEvidenceInputV1:
    return CreditEvidenceInputV1(
        dossier_sha256=dossier.dossier_sha256,
        target=TARGET,
        issuer=_issuer(source_hash),
        issue_terms=_terms(source_hash),
        financial_metrics=financial_metrics,
        ratings=ratings,
    )


def test_agency_scale_pair_must_be_compatible() -> None:
    with pytest.raises(ValueError, match="agency and scale"):
        CreditRatingObservationV1(
            observation_id="rating_bad_scale",
            subject=CreditRatingSubject.ISSUE,
            subject_id=TARGET.instrument_uid,
            agency=CreditRatingAgency.ACRA,
            scale=CreditRatingScale.EXPERT_RA_RU_NATIONAL,
            rating="A(RU)",
            action=CreditRatingAction.ASSIGNED,
            effective_at=NOW,
            source_record_sha256s=("a" * 64,),
        )


def test_rating_subject_outside_identity_graph_is_rejected() -> None:
    record = _record("credit.rating", "A(RU)")
    dossier = _dossier(record)
    bad_rating = CreditRatingObservationV1(
        observation_id="rating_bad_subject",
        subject=CreditRatingSubject.ISSUER,
        subject_id="credit_other_issuer",
        agency=CreditRatingAgency.ACRA,
        scale=CreditRatingScale.ACRA_RU_NATIONAL,
        rating="A(RU)",
        action=CreditRatingAction.ASSIGNED,
        effective_at=NOW,
        source_record_sha256s=(record.record_sha256,),
    )

    with pytest.raises(ValueError, match="issuer rating subject"):
        _evidence(dossier, record.record_sha256, (bad_rating,))


def test_credit_event_subject_outside_identity_graph_is_rejected() -> None:
    record = _record("credit.event", "delay")
    dossier = _dossier(record)
    rating = _rating(
        record.record_sha256,
        observation_id="rating_main",
        rating="A(RU)",
        effective_at=NOW,
    )
    event = CreditDefaultEventV1(
        event_id="credit_event_bad_subject",
        event_type=CreditDefaultEventType.PAYMENT_DELAY,
        subject_id="credit_unknown_subject",
        occurred_at=NOW,
        source_record_sha256s=(record.record_sha256,),
    )

    with pytest.raises(ValueError, match="credit event subject"):
        CreditEvidenceInputV1(
            dossier_sha256=dossier.dossier_sha256,
            target=TARGET,
            issuer=_issuer(record.record_sha256),
            issue_terms=_terms(record.record_sha256),
            ratings=(rating,),
            default_events=(event,),
        )


def test_duplicate_rating_observation_ids_are_rejected() -> None:
    record = _record("credit.rating", "history")
    dossier = _dossier(record)
    rows = (
        _rating(
            record.record_sha256,
            observation_id="rating_duplicate",
            rating="A-(RU)",
            effective_at=NOW - timedelta(days=1),
        ),
        _rating(
            record.record_sha256,
            observation_id="rating_duplicate",
            rating="A(RU)",
            effective_at=NOW,
        ),
    )

    with pytest.raises(ValueError, match="rating observation ids"):
        _evidence(dossier, record.record_sha256, rows)


def test_zero_coupon_terms_reject_positive_coupon_rate() -> None:
    with pytest.raises(ValueError, match="zero-coupon"):
        DebtIssueTermsV1(
            instrument_uid=TARGET.instrument_uid,
            issuer_entity_id="credit_issuer_1",
            seniority=DebtSeniority.SENIOR_UNSECURED,
            coupon_type=CreditCouponType.ZERO,
            coupon_rate_percent=Decimal("1"),
            source_record_sha256s=("a" * 64,),
        )


def test_currency_metric_requires_currency_and_nonnegative_value() -> None:
    with pytest.raises(ValueError, match="requires currency"):
        CreditFinancialMetricV1(
            metric_id="credit_metric_liquidity",
            kind=CreditMetricKind.AVAILABLE_LIQUIDITY,
            value=Decimal("100"),
            unit=CreditMetricUnit.CURRENCY,
            as_of=NOW.date(),
            source_record_sha256s=("a" * 64,),
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        CreditFinancialMetricV1(
            metric_id="credit_metric_debt",
            kind=CreditMetricKind.TOTAL_DEBT,
            value=Decimal("-1"),
            unit=CreditMetricUnit.CURRENCY,
            currency="RUB",
            as_of=NOW.date(),
            source_record_sha256s=("a" * 64,),
        )


def test_ratio_metric_rejects_currency_unit() -> None:
    with pytest.raises(ValueError, match="ratio credit metric"):
        CreditFinancialMetricV1(
            metric_id="credit_metric_leverage",
            kind=CreditMetricKind.NET_DEBT_TO_EBITDA,
            value=Decimal("2.1"),
            unit=CreditMetricUnit.CURRENCY,
            currency="RUB",
            as_of=NOW.date(),
            source_record_sha256s=("a" * 64,),
        )


def test_reanalysis_uses_latest_effective_rating_not_observation_id_order() -> None:
    record = _record("credit.rating", "history")
    dossier = _dossier(record)
    old = _rating(
        record.record_sha256,
        observation_id="rating_z_old",
        rating="BBB(RU)",
        effective_at=NOW - timedelta(days=30),
    )
    current = _rating(
        record.record_sha256,
        observation_id="rating_a_current",
        rating="A(RU)",
        effective_at=NOW - timedelta(days=1),
    )
    initial = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, record.record_sha256, (old, current)),
        assessed_at=NOW,
    )

    same_current_new_history_order = _evidence(
        dossier,
        record.record_sha256,
        (
            _rating(
                record.record_sha256,
                observation_id="rating_0_very_old",
                rating="BB(RU)",
                effective_at=NOW - timedelta(days=60),
            ),
            current,
            old,
        ),
    )
    updated = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=same_current_new_history_order,
        previous=initial,
        assessed_at=NOW,
    )

    assert CreditReanalysisTriggerCode.RATING_CHANGED not in updated.reanalysis.codes
    assert CreditReanalysisTriggerCode.OUTLOOK_CHANGED not in updated.reanalysis.codes
    assert CreditReanalysisTriggerCode.WATCH_CHANGED not in updated.reanalysis.codes


def test_financial_metric_change_triggers_reanalysis_and_is_fingerprinted() -> None:
    rating_record = _record("credit.rating", "A(RU)")
    metric_record = _record("credit.metric", "net debt / EBITDA")
    dossier = _dossier(rating_record, metric_record)
    rating = _rating(
        rating_record.record_sha256,
        observation_id="rating_main",
        rating="A(RU)",
        effective_at=NOW,
    )
    first_metric = CreditFinancialMetricV1(
        metric_id="credit_metric_leverage",
        kind=CreditMetricKind.NET_DEBT_TO_EBITDA,
        value=Decimal("2.0"),
        unit=CreditMetricUnit.RATIO,
        as_of=NOW.date(),
        source_record_sha256s=(metric_record.record_sha256,),
    )
    initial = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(
            dossier,
            rating_record.record_sha256,
            (rating,),
            financial_metrics=(first_metric,),
        ),
        assessed_at=NOW,
    )
    second_metric = first_metric.model_copy(update={"value": Decimal("2.4")})
    updated = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(
            dossier,
            rating_record.record_sha256,
            (rating,),
            financial_metrics=(second_metric,),
        ),
        previous=initial,
        assessed_at=NOW,
    )

    assert CreditReanalysisTriggerCode.FINANCIAL_METRICS_CHANGED in updated.reanalysis.codes
    assert updated.passport_sha256 != initial.passport_sha256
