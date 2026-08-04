from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
from typing import Iterable

from omni_cio.contracts.v1.credit import (
    CreditBlockerCode,
    CreditEvidenceInputV1,
    CreditFloorAssessmentV1,
    CreditFloorBasis,
    CreditPassportV1,
    CreditRatingAction,
    CreditRatingObservationV1,
    CreditRatingScale,
    CreditRatingSubject,
    CreditReanalysisTriggerCode,
    CreditReanalysisTriggerV1,
    DebtSeniority,
    credit_passport_sha256,
)
from omni_cio.contracts.v1.investment_policy import (
    InvestmentPolicyStatementV1,
    PolicyReferenceV1,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import EvidenceUse, ResearchDossierV1
from omni_cio.policy import policy_reference


class CreditEngineError(ValueError):
    """Credit inputs cannot be evaluated safely."""


_SCALE_ALIASES = {
    "ACRA": CreditRatingScale.ACRA_RU_NATIONAL,
    "ACRA_RU": CreditRatingScale.ACRA_RU_NATIONAL,
    "ACRA_RU_NATIONAL": CreditRatingScale.ACRA_RU_NATIONAL,
    "АКРА": CreditRatingScale.ACRA_RU_NATIONAL,
    "EXPERT_RA": CreditRatingScale.EXPERT_RA_RU_NATIONAL,
    "EXPERT_RA_RU": CreditRatingScale.EXPERT_RA_RU_NATIONAL,
    "EXPERT_RA_RU_NATIONAL": CreditRatingScale.EXPERT_RA_RU_NATIONAL,
    "ЭКСПЕРТ_РА": CreditRatingScale.EXPERT_RA_RU_NATIONAL,
    "NKR": CreditRatingScale.NKR_RU_NATIONAL,
    "NKR_RU": CreditRatingScale.NKR_RU_NATIONAL,
    "NKR_RU_NATIONAL": CreditRatingScale.NKR_RU_NATIONAL,
    "НКР": CreditRatingScale.NKR_RU_NATIONAL,
    "NRA": CreditRatingScale.NRA_RU_NATIONAL,
    "NRA_RU": CreditRatingScale.NRA_RU_NATIONAL,
    "NRA_RU_NATIONAL": CreditRatingScale.NRA_RU_NATIONAL,
    "НРА": CreditRatingScale.NRA_RU_NATIONAL,
}

_GRADE_RANK = {
    "D": 0,
    "SD": 0,
    "RD": 0,
    "C": 1,
    "CC": 2,
    "CCC": 3,
    "B-": 4,
    "B": 5,
    "B+": 6,
    "BB-": 7,
    "BB": 8,
    "BB+": 9,
    "BBB-": 10,
    "BBB": 11,
    "BBB+": 12,
    "A-": 13,
    "A": 14,
    "A+": 15,
    "AA-": 16,
    "AA": 17,
    "AA+": 18,
    "AAA": 19,
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CreditEngineError("CREDIT_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _normalize_policy_scale(value: str | None) -> CreditRatingScale | None:
    if value is None:
        return None
    key = re.sub(r"[\s.-]+", "_", value.strip().upper())
    return _SCALE_ALIASES.get(key)


def _canonical_grade(scale: CreditRatingScale, value: str) -> str | None:
    text = value.strip().upper().replace(" ", "")
    if scale is CreditRatingScale.ACRA_RU_NATIONAL:
        if not text.endswith("(RU)"):
            return None
        text = text[:-4]
    elif scale is CreditRatingScale.EXPERT_RA_RU_NATIONAL:
        if not text.startswith("RU"):
            return None
        text = text[2:]
    elif scale is CreditRatingScale.NKR_RU_NATIONAL:
        if not text.endswith(".RU"):
            return None
        text = text[:-3]
    elif scale is CreditRatingScale.NRA_RU_NATIONAL:
        if not text.endswith("|RU|"):
            return None
        text = text[:-4]
    return text if text in _GRADE_RANK else None


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _source_hashes(evidence: CreditEvidenceInputV1) -> tuple[str, ...]:
    hashes: set[str] = set(evidence.issuer.source_record_sha256s)
    hashes.update(evidence.issue_terms.source_record_sha256s)
    for guarantor in evidence.guarantors:
        hashes.update(guarantor.source_record_sha256s)
    for guarantee in evidence.issue_terms.guarantees:
        hashes.update(guarantee.source_record_sha256s)
    for metric in evidence.financial_metrics:
        hashes.update(metric.source_record_sha256s)
    for rating in evidence.ratings:
        hashes.update(rating.source_record_sha256s)
    for event in evidence.default_events:
        hashes.update(event.source_record_sha256s)
    return tuple(sorted(hashes))


def _validate_provenance(
    dossier: ResearchDossierV1,
    evidence: CreditEvidenceInputV1,
) -> tuple[CreditBlockerCode, ...]:
    records = {row.record_sha256: row for row in dossier.records}
    blockers: list[CreditBlockerCode] = []
    for source_hash in _source_hashes(evidence):
        record = records.get(source_hash)
        if record is None:
            _append_unique(blockers, CreditBlockerCode.SOURCE_PROVENANCE_MISSING)
            continue
        if record.use is not EvidenceUse.DECISION_GRADE:
            _append_unique(blockers, CreditBlockerCode.SOURCE_NOT_DECISION_GRADE)
    return tuple(sorted(blockers, key=str))


def _rating_identity_blockers(
    evidence: CreditEvidenceInputV1,
) -> tuple[CreditBlockerCode, ...]:
    guarantor_ids = {row.entity_id for row in evidence.guarantors}
    blockers: list[CreditBlockerCode] = []
    for rating in evidence.ratings:
        if rating.subject is CreditRatingSubject.ISSUE:
            valid = rating.subject_id == evidence.target.instrument_uid
        elif rating.subject is CreditRatingSubject.ISSUER:
            valid = rating.subject_id == evidence.issuer.entity_id
        else:
            valid = rating.subject_id in guarantor_ids
        if not valid:
            _append_unique(blockers, CreditBlockerCode.RATING_IDENTITY_CONFLICT)
    return tuple(sorted(blockers, key=str))


def _current_ratings(
    ratings: Iterable[CreditRatingObservationV1],
) -> tuple[tuple[CreditRatingObservationV1, ...], bool]:
    groups: dict[
        tuple[CreditRatingSubject, str, object, CreditRatingScale],
        list[CreditRatingObservationV1],
    ] = defaultdict(list)
    for row in ratings:
        groups[(row.subject, row.subject_id, row.agency, row.scale)].append(row)

    current: list[CreditRatingObservationV1] = []
    contradiction = False
    for rows in groups.values():
        latest_at = max(row.effective_at for row in rows)
        latest = [row for row in rows if row.effective_at == latest_at]
        states = {(row.rating, row.outlook, row.watch, row.action) for row in latest}
        if len(states) > 1:
            contradiction = True
            continue
        selected = sorted(latest, key=lambda row: row.observation_id)[0]
        if selected.action is not CreditRatingAction.WITHDRAWN:
            current.append(selected)
    current.sort(
        key=lambda row: (
            row.subject.value,
            row.subject_id,
            row.scale.value,
            row.agency.value,
            row.observation_id,
        )
    )
    return tuple(current), contradiction


def _current_rating_map(
    ratings: Iterable[CreditRatingObservationV1],
) -> dict[tuple[object, ...], CreditRatingObservationV1]:
    current, _ = _current_ratings(ratings)
    return {
        (row.subject, row.subject_id, row.agency, row.scale): row
        for row in current
    }


def _eligible_guarantor_ids(evidence: CreditEvidenceInputV1) -> set[str]:
    return {
        row.guarantor_entity_id
        for row in evidence.issue_terms.guarantees
        if row.credit_substitution_eligible
    }


def _select_floor_rating(
    *,
    current: tuple[CreditRatingObservationV1, ...],
    evidence: CreditEvidenceInputV1,
    policy_scale: CreditRatingScale,
) -> tuple[CreditRatingObservationV1 | None, CreditFloorBasis, bool]:
    compatible = [row for row in current if row.scale is policy_scale]
    incompatible_exists = bool(current) and not compatible

    issue = [
        row
        for row in compatible
        if row.subject is CreditRatingSubject.ISSUE
        and row.subject_id == evidence.target.instrument_uid
    ]
    if issue:
        return issue[0], CreditFloorBasis.ISSUE, incompatible_exists

    issuer = [
        row
        for row in compatible
        if row.subject is CreditRatingSubject.ISSUER
        and row.subject_id == evidence.issuer.entity_id
    ]
    if issuer:
        return issuer[0], CreditFloorBasis.ISSUER_PROXY, incompatible_exists

    eligible_guarantors = _eligible_guarantor_ids(evidence)
    guarantor = [
        row
        for row in compatible
        if row.subject is CreditRatingSubject.GUARANTOR
        and row.subject_id in eligible_guarantors
    ]
    if guarantor:
        guarantor.sort(key=lambda row: row.subject_id)
        return guarantor[0], CreditFloorBasis.ELIGIBLE_GUARANTOR, incompatible_exists
    return None, CreditFloorBasis.NONE, incompatible_exists


def _assess_floor(
    *,
    policy: InvestmentPolicyStatementV1,
    evidence: CreditEvidenceInputV1,
    current: tuple[CreditRatingObservationV1, ...],
) -> CreditFloorAssessmentV1:
    blockers: list[CreditBlockerCode] = []
    policy_scale = _normalize_policy_scale(policy.credit_rating_scale)
    floor = policy.minimum_credit_rating
    if floor is None or policy.credit_rating_scale is None:
        blockers.append(CreditBlockerCode.POLICY_CREDIT_FLOOR_MISSING)
        return CreditFloorAssessmentV1(
            policy_scale=policy_scale,
            policy_floor=floor,
            basis=CreditFloorBasis.NONE,
            meets_floor=False,
            blockers=tuple(blockers),
        )
    if policy_scale is None:
        blockers.append(CreditBlockerCode.POLICY_SCALE_UNSUPPORTED)
        return CreditFloorAssessmentV1(
            policy_scale=None,
            policy_floor=floor,
            basis=CreditFloorBasis.NONE,
            meets_floor=False,
            blockers=tuple(blockers),
        )

    floor_grade = _canonical_grade(policy_scale, floor)
    selected, basis, incompatible_exists = _select_floor_rating(
        current=current,
        evidence=evidence,
        policy_scale=policy_scale,
    )
    if floor_grade is None:
        blockers.append(CreditBlockerCode.RATING_SYMBOL_UNRECOGNIZED)
    if selected is None:
        blockers.append(
            CreditBlockerCode.RATING_SCALE_INCOMPATIBLE
            if incompatible_exists
            else CreditBlockerCode.CURRENT_RATING_MISSING
        )
        return CreditFloorAssessmentV1(
            policy_scale=policy_scale,
            policy_floor=floor,
            basis=basis,
            meets_floor=False,
            blockers=tuple(blockers),
        )

    selected_grade = _canonical_grade(policy_scale, selected.rating)
    if selected_grade is None:
        blockers.append(CreditBlockerCode.RATING_SYMBOL_UNRECOGNIZED)
    elif (
        floor_grade is not None
        and _GRADE_RANK[selected_grade] < _GRADE_RANK[floor_grade]
    ):
        blockers.append(CreditBlockerCode.RATING_BELOW_FLOOR)

    return CreditFloorAssessmentV1(
        policy_scale=policy_scale,
        policy_floor=floor,
        basis=basis,
        selected_observation_id=selected.observation_id,
        selected_rating=selected.rating,
        selected_subject_id=selected.subject_id,
        meets_floor=not blockers,
        blockers=tuple(blockers),
    )


def _reanalysis_trigger(
    *,
    previous: CreditPassportV1 | None,
    dossier: ResearchDossierV1,
    policy_ref: PolicyReferenceV1,
    evidence: CreditEvidenceInputV1,
) -> CreditReanalysisTriggerV1:
    if previous is None:
        return CreditReanalysisTriggerV1(required=False, codes=())

    codes: list[CreditReanalysisTriggerCode] = []
    if previous.dossier_sha256 != dossier.dossier_sha256:
        codes.append(CreditReanalysisTriggerCode.DOSSIER_CHANGED)
    if previous.policy_reference != policy_ref:
        codes.append(CreditReanalysisTriggerCode.POLICY_CHANGED)
    if previous.issue_terms != evidence.issue_terms:
        codes.append(CreditReanalysisTriggerCode.ISSUE_TERMS_CHANGED)

    canonical_metrics = tuple(
        sorted(evidence.financial_metrics, key=lambda row: row.metric_id)
    )
    if previous.financial_metrics != canonical_metrics:
        codes.append(CreditReanalysisTriggerCode.FINANCIAL_METRICS_CHANGED)

    canonical_events = tuple(
        sorted(evidence.default_events, key=lambda row: row.event_id)
    )
    if previous.default_events != canonical_events:
        codes.append(CreditReanalysisTriggerCode.DEFAULT_EVENT_CHANGED)

    previous_by_key = _current_rating_map(previous.ratings)
    current_by_key = _current_rating_map(evidence.ratings)
    keys = set(previous_by_key) | set(current_by_key)
    for key in keys:
        old = previous_by_key.get(key)
        new = current_by_key.get(key)
        if (
            old is None
            or new is None
            or old.rating != new.rating
            or old.action != new.action
        ):
            _append_unique(codes, CreditReanalysisTriggerCode.RATING_CHANGED)
        if old is None or new is None or old.outlook != new.outlook:
            _append_unique(codes, CreditReanalysisTriggerCode.OUTLOOK_CHANGED)
        if old is None or new is None or old.watch != new.watch:
            _append_unique(codes, CreditReanalysisTriggerCode.WATCH_CHANGED)

    return CreditReanalysisTriggerV1(required=bool(codes), codes=tuple(codes))


def build_credit_passport(
    *,
    dossier: ResearchDossierV1,
    policy: InvestmentPolicyStatementV1,
    evidence: CreditEvidenceInputV1,
    previous: CreditPassportV1 | None = None,
    assessed_at: datetime | None = None,
) -> CreditPassportV1:
    """Build a deterministic credit passport without external calls or execution authority."""
    evaluation_time = _aware_utc(assessed_at)
    if evidence.target.instrument_type is not InstrumentType.BOND:
        raise CreditEngineError("CREDIT_ENGINE_REQUIRES_BOND_TARGET")

    blockers: list[CreditBlockerCode] = []
    if (
        dossier.target != evidence.target
        or dossier.dossier_sha256 != evidence.dossier_sha256
    ):
        blockers.append(CreditBlockerCode.DOSSIER_BINDING_MISMATCH)
    if not dossier.decision_ready:
        blockers.append(CreditBlockerCode.DOSSIER_NOT_READY)
    blockers.extend(_validate_provenance(dossier, evidence))
    blockers.extend(_rating_identity_blockers(evidence))
    if evidence.issue_terms.seniority is DebtSeniority.UNKNOWN:
        blockers.append(CreditBlockerCode.SENIORITY_UNKNOWN)

    current, contradiction = _current_ratings(evidence.ratings)
    if contradiction:
        blockers.append(CreditBlockerCode.RATING_CONTRADICTION)

    floor = _assess_floor(policy=policy, evidence=evidence, current=current)
    blockers.extend(floor.blockers)
    if any(event.active for event in evidence.default_events):
        blockers.append(CreditBlockerCode.ACTIVE_DEFAULT_EVENT)

    canonical_metrics = tuple(
        sorted(evidence.financial_metrics, key=lambda row: row.metric_id)
    )
    canonical_ratings = tuple(
        sorted(evidence.ratings, key=lambda row: row.observation_id)
    )
    canonical_events = tuple(
        sorted(evidence.default_events, key=lambda row: row.event_id)
    )
    canonical_guarantors = tuple(
        sorted(evidence.guarantors, key=lambda row: row.entity_id)
    )
    policy_ref = policy_reference(policy)
    reanalysis = _reanalysis_trigger(
        previous=previous,
        dossier=dossier,
        policy_ref=policy_ref,
        evidence=evidence,
    )
    canonical_blockers = tuple(sorted(set(blockers), key=str))

    values = {
        "schema_version": "1.0",
        "assessed_at": evaluation_time,
        "dossier_sha256": dossier.dossier_sha256,
        "target": evidence.target,
        "policy_reference": policy_ref,
        "issuer": evidence.issuer,
        "guarantors": canonical_guarantors,
        "issue_terms": evidence.issue_terms,
        "financial_metrics": canonical_metrics,
        "ratings": canonical_ratings,
        "default_events": canonical_events,
        "floor_assessment": floor,
        "reanalysis": reanalysis,
        "blockers": canonical_blockers,
        "passport_sha256": "0" * 64,
        "decision_ready": not canonical_blockers,
        "strong_recommendation_allowed": (
            not canonical_blockers
            and floor.meets_floor
            and not any(event.active for event in canonical_events)
        ),
        "trading_methods": False,
    }
    provisional = CreditPassportV1.model_construct(**values)
    values["passport_sha256"] = credit_passport_sha256(provisional)
    return CreditPassportV1.model_validate(values)
