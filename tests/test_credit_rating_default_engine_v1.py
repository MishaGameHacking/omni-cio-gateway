from __future__ import annotations

from datetime import datetime, timezone

import pytest

from omni_cio.contracts.v1.credit import (
    CreditBlockerCode,
    CreditDefaultEventType,
    CreditDefaultEventV1,
    CreditEntityIdentityV1,
    CreditEntityKind,
    CreditEvidenceInputV1,
    CreditFloorBasis,
    CreditGuaranteeV1,
    CreditRatingAction,
    CreditRatingAgency,
    CreditRatingObservationV1,
    CreditRatingScale,
    CreditRatingSubject,
    CreditReanalysisTriggerCode,
    DebtIssueTermsV1,
    DebtSeniority,
    GuaranteeType,
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
from omni_cio.credit import CreditEngineError, build_credit_passport


NOW = datetime(2026, 8, 4, 8, 0, tzinfo=timezone.utc)
TARGET = ResearchTargetV1(
    funnel_sha256="1" * 64,
    candidate_id="uid:bond-1",
    instrument_uid="bond-1",
    instrument_type=InstrumentType.BOND,
)


def _source(source_class: EvidenceSourceClass, source_id: str) -> ResearchSourceV1:
    return ResearchSourceV1(
        provider="official-test",
        source_class=source_class,
        authority=SourceAuthority.OFFICIAL,
        source_id=source_id,
        retrieved_at=NOW,
    )


def _record(
    key: str,
    value: str,
    *,
    source_class: EvidenceSourceClass = EvidenceSourceClass.OFFICIAL_DISCLOSURE,
    use: EvidenceUse = EvidenceUse.DECISION_GRADE,
):
    return make_evidence_record(
        instrument_uid=TARGET.instrument_uid,
        fact_type=EvidenceFactType.MATERIAL_EVENT,
        fact_key=key,
        value=EvidenceValueV1(value_type=EvidenceValueType.TEXT, canonical_value=value),
        source=_source(source_class, f"src:{key}"),
        use=use,
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


def _policy(
    *,
    floor: str = "A-(RU)",
    scale: str = "ACRA",
) -> InvestmentPolicyStatementV1:
    return InvestmentPolicyStatementV1(
        policy_id="ips_test",
        version="1",
        lifecycle=PolicyLifecycle.ACTIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        review_due_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        minimum_credit_rating=floor,
        credit_rating_scale=scale,
    )


def _issuer(source_hash: str) -> CreditEntityIdentityV1:
    return CreditEntityIdentityV1(
        entity_id="credit_issuer_1",
        kind=CreditEntityKind.ISSUER,
        name="Issuer One",
        source_record_sha256s=(source_hash,),
    )


def _terms(source_hash: str, **updates) -> DebtIssueTermsV1:
    values = {
        "instrument_uid": TARGET.instrument_uid,
        "issuer_entity_id": "credit_issuer_1",
        "seniority": DebtSeniority.SENIOR_UNSECURED,
        "source_record_sha256s": (source_hash,),
    }
    values.update(updates)
    return DebtIssueTermsV1(**values)


def _rating(
    source_hash: str,
    *,
    observation_id: str = "rating_main",
    subject: CreditRatingSubject = CreditRatingSubject.ISSUE,
    subject_id: str = TARGET.instrument_uid,
    agency: CreditRatingAgency = CreditRatingAgency.ACRA,
    scale: CreditRatingScale = CreditRatingScale.ACRA_RU_NATIONAL,
    rating: str = "A(RU)",
    outlook: str | None = "stable",
    watch: str | None = None,
    action: CreditRatingAction = CreditRatingAction.ASSIGNED,
    effective_at: datetime = NOW,
) -> CreditRatingObservationV1:
    return CreditRatingObservationV1(
        observation_id=observation_id,
        subject=subject,
        subject_id=subject_id,
        agency=agency,
        scale=scale,
        rating=rating,
        outlook=outlook,
        watch=watch,
        action=action,
        effective_at=effective_at,
        source_record_sha256s=(source_hash,),
    )


def _evidence(dossier: ResearchDossierV1, source_hash: str, **updates) -> CreditEvidenceInputV1:
    values = {
        "dossier_sha256": dossier.dossier_sha256,
        "target": TARGET,
        "issuer": _issuer(source_hash),
        "guarantors": (),
        "issue_terms": _terms(source_hash),
        "ratings": (_rating(source_hash),),
        "default_events": (),
    }
    values.update(updates)
    return CreditEvidenceInputV1(**values)


def test_issue_rating_above_floor_is_ready() -> None:
    record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, record.record_sha256),
        assessed_at=NOW,
    )

    assert result.decision_ready is True
    assert result.strong_recommendation_allowed is True
    assert result.floor_assessment.meets_floor is True
    assert result.floor_assessment.basis is CreditFloorBasis.ISSUE
    assert result.trading_methods is False


def test_rating_below_policy_floor_blocks() -> None:
    record = _record("credit.rating", "BBB(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    evidence = _evidence(
        dossier,
        record.record_sha256,
        ratings=(_rating(record.record_sha256, rating="BBB(RU)"),),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.RATING_BELOW_FLOOR in result.blockers
    assert result.floor_assessment.meets_floor is False
    assert result.decision_ready is False


def test_incompatible_scale_is_not_averaged_or_crosswalked() -> None:
    record = _record("credit.rating", "ruAA", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    evidence = _evidence(
        dossier,
        record.record_sha256,
        ratings=(
            _rating(
                record.record_sha256,
                agency=CreditRatingAgency.EXPERT_RA,
                scale=CreditRatingScale.EXPERT_RA_RU_NATIONAL,
                rating="ruAA",
            ),
        ),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(scale="ACRA"),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.RATING_SCALE_INCOMPATIBLE in result.blockers
    assert result.floor_assessment.selected_rating is None


def test_issuer_rating_is_kept_distinct_as_proxy_basis() -> None:
    record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    evidence = _evidence(
        dossier,
        record.record_sha256,
        ratings=(
            _rating(
                record.record_sha256,
                subject=CreditRatingSubject.ISSUER,
                subject_id="credit_issuer_1",
            ),
        ),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert result.floor_assessment.basis is CreditFloorBasis.ISSUER_PROXY
    assert result.floor_assessment.selected_subject_id == "credit_issuer_1"


def test_full_eligible_guarantor_can_supply_explicit_credit_basis() -> None:
    identity_record = _record("credit.identity", "graph")
    rating_record = _record("credit.rating", "AA(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(identity_record, rating_record)
    guarantor = CreditEntityIdentityV1(
        entity_id="credit_guarantor_1",
        kind=CreditEntityKind.GUARANTOR,
        name="Guarantor One",
        source_record_sha256s=(identity_record.record_sha256,),
    )
    guarantee = CreditGuaranteeV1(
        guarantor_entity_id=guarantor.entity_id,
        guarantee_type=GuaranteeType.FULL_IRREVOCABLE_UNCONDITIONAL,
        credit_substitution_eligible=True,
        source_record_sha256s=(identity_record.record_sha256,),
    )
    evidence = _evidence(
        dossier,
        identity_record.record_sha256,
        guarantors=(guarantor,),
        issue_terms=_terms(identity_record.record_sha256, guarantees=(guarantee,)),
        ratings=(
            _rating(
                rating_record.record_sha256,
                subject=CreditRatingSubject.GUARANTOR,
                subject_id=guarantor.entity_id,
                rating="AA(RU)",
            ),
        ),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert result.floor_assessment.basis is CreditFloorBasis.ELIGIBLE_GUARANTOR
    assert result.floor_assessment.meets_floor is True


def test_limited_guarantee_cannot_claim_credit_substitution() -> None:
    with pytest.raises(ValueError, match="credit substitution"):
        CreditGuaranteeV1(
            guarantor_entity_id="credit_guarantor_1",
            guarantee_type=GuaranteeType.LIMITED,
            credit_substitution_eligible=True,
            source_record_sha256s=("a" * 64,),
        )


def test_active_payment_delay_blocks_strong_recommendation() -> None:
    rating_record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    event_record = _record("credit.default_event", "payment delay")
    dossier = _dossier(rating_record, event_record)
    event = CreditDefaultEventV1(
        event_id="credit_event_delay_1",
        event_type=CreditDefaultEventType.PAYMENT_DELAY,
        subject_id=TARGET.instrument_uid,
        occurred_at=NOW,
        source_record_sha256s=(event_record.record_sha256,),
    )
    evidence = _evidence(
        dossier,
        rating_record.record_sha256,
        default_events=(event,),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.ACTIVE_DEFAULT_EVENT in result.blockers
    assert result.strong_recommendation_allowed is False


def test_resolved_default_event_is_preserved_without_active_block() -> None:
    rating_record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    event_record = _record("credit.default_event", "resolved")
    dossier = _dossier(rating_record, event_record)
    event = CreditDefaultEventV1(
        event_id="credit_event_default_1",
        event_type=CreditDefaultEventType.DEFAULT,
        subject_id=TARGET.instrument_uid,
        occurred_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        resolved_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
        source_record_sha256s=(event_record.record_sha256,),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(
            dossier,
            rating_record.record_sha256,
            default_events=(event,),
        ),
        assessed_at=NOW,
    )

    assert CreditBlockerCode.ACTIVE_DEFAULT_EVENT not in result.blockers
    assert result.default_events[0].active is False


def test_same_timestamp_rating_contradiction_fails_closed() -> None:
    first = _record("credit.rating.a", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    second = _record("credit.rating.b", "BBB(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(first, second)
    evidence = _evidence(
        dossier,
        first.record_sha256,
        ratings=(
            _rating(first.record_sha256, observation_id="rating_a", rating="A(RU)"),
            _rating(second.record_sha256, observation_id="rating_b", rating="BBB(RU)"),
        ),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.RATING_CONTRADICTION in result.blockers
    assert result.decision_ready is False


def test_missing_provenance_hash_fails_closed() -> None:
    record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    evidence = _evidence(dossier, "f" * 64)
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.SOURCE_PROVENANCE_MISSING in result.blockers


def test_context_only_provenance_cannot_support_credit_passport() -> None:
    record = _record(
        "credit.context",
        "rumor",
        source_class=EvidenceSourceClass.MEDIA_CONTEXT,
        use=EvidenceUse.CONTEXT_ONLY,
    )
    dossier = _dossier(record)
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, record.record_sha256),
        assessed_at=NOW,
    )

    assert CreditBlockerCode.SOURCE_NOT_DECISION_GRADE in result.blockers


def test_unknown_seniority_fails_closed() -> None:
    record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    evidence = _evidence(
        dossier,
        record.record_sha256,
        issue_terms=_terms(record.record_sha256, seniority=DebtSeniority.UNKNOWN),
    )
    result = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=evidence,
        assessed_at=NOW,
    )

    assert CreditBlockerCode.SENIORITY_UNKNOWN in result.blockers


def test_source_order_does_not_change_passport_fingerprint() -> None:
    identity = _record("credit.identity", "identity")
    rating_a = _record("credit.rating.a", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    rating_b = _record("credit.rating.b", "AA(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(identity, rating_a, rating_b)
    rows = (
        _rating(rating_a.record_sha256, observation_id="rating_issue", rating="A(RU)"),
        _rating(
            rating_b.record_sha256,
            observation_id="rating_issuer",
            subject=CreditRatingSubject.ISSUER,
            subject_id="credit_issuer_1",
            rating="AA(RU)",
        ),
    )
    left = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, identity.record_sha256, ratings=rows),
        assessed_at=NOW,
    )
    right = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, identity.record_sha256, ratings=tuple(reversed(rows))),
        assessed_at=NOW,
    )

    assert left.passport_sha256 == right.passport_sha256
    assert left.ratings == right.ratings


def test_rating_and_outlook_change_trigger_reanalysis() -> None:
    rating_record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(rating_record)
    initial = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=_evidence(dossier, rating_record.record_sha256),
        assessed_at=NOW,
    )
    changed = _evidence(
        dossier,
        rating_record.record_sha256,
        ratings=(
            _rating(
                rating_record.record_sha256,
                rating="AA-(RU)",
                outlook="positive",
                action=CreditRatingAction.UPGRADED,
            ),
        ),
    )
    updated = build_credit_passport(
        dossier=dossier,
        policy=_policy(),
        evidence=changed,
        previous=initial,
        assessed_at=NOW,
    )

    assert updated.reanalysis.required is True
    assert CreditReanalysisTriggerCode.RATING_CHANGED in updated.reanalysis.codes
    assert CreditReanalysisTriggerCode.OUTLOOK_CHANGED in updated.reanalysis.codes


def test_non_bond_target_is_rejected() -> None:
    record = _record("credit.rating", "A(RU)", source_class=EvidenceSourceClass.RATING_AGENCY)
    dossier = _dossier(record)
    share_target = TARGET.model_copy(update={"instrument_type": InstrumentType.SHARE})
    evidence = _evidence(dossier, record.record_sha256).model_copy(update={"target": share_target})

    with pytest.raises(CreditEngineError, match="REQUIRES_BOND_TARGET"):
        build_credit_passport(
            dossier=dossier,
            policy=_policy(),
            evidence=evidence,
            assessed_at=NOW,
        )
