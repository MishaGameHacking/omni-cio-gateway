from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from omni_cio.contracts.v1.research_evidence import (
    ContradictionSeverity,
    CoverageGapReason,
    EvidenceContradictionV1,
    EvidenceCoverageGapV1,
    EvidenceCoverageProbeV1,
    EvidenceRecordV1,
    EvidenceRequirementV1,
    EvidenceSourceClass,
    EvidenceUse,
    RequirementImportance,
    ResearchDossierV1,
    ResearchTargetV1,
    research_dossier_sha256,
)


_FUTURE_TOLERANCE_SECONDS = 60
_SOURCE_PRIORITY = {
    EvidenceSourceClass.BROKER: 0,
    EvidenceSourceClass.EXCHANGE: 1,
    EvidenceSourceClass.ISSUER: 2,
    EvidenceSourceClass.OFFICIAL_DISCLOSURE: 3,
    EvidenceSourceClass.REGULATOR: 4,
    EvidenceSourceClass.RATING_AGENCY: 5,
    EvidenceSourceClass.MEDIA_CONTEXT: 6,
}


class ResearchEvidenceError(ValueError):
    """Research evidence cannot be assembled safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ResearchEvidenceError("RESEARCH_ASSESSMENT_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _record_effective_time(record: EvidenceRecordV1) -> datetime:
    return record.published_at or record.effective_at or record.source.retrieved_at


def _is_fresh(value_at: datetime, *, assessed_at: datetime, max_age_seconds: int) -> bool:
    age = (assessed_at - value_at).total_seconds()
    return -_FUTURE_TOLERANCE_SECONDS <= age <= max_age_seconds


def _record_sort_key(record: EvidenceRecordV1) -> tuple[object, ...]:
    return (
        record.fact_type.value,
        record.fact_key,
        _SOURCE_PRIORITY[record.source.source_class],
        record.source.provider.lower(),
        record.source.source_id,
        record.source_record_id or "",
        record.effective_at.isoformat() if record.effective_at else "",
        record.published_at.isoformat() if record.published_at else "",
        record.record_sha256,
    )


def _stable_source_record_key(record: EvidenceRecordV1) -> tuple[object, ...]:
    return (
        record.instrument_uid,
        record.fact_type.value,
        record.fact_key,
        record.source.source_class.value,
        record.source.provider.lower(),
        record.source.source_id,
        record.source_record_id or "",
        record.effective_at.isoformat() if record.effective_at else "",
        record.published_at.isoformat() if record.published_at else "",
    )


def _deduplicate_records(
    records: Iterable[EvidenceRecordV1],
) -> tuple[tuple[EvidenceRecordV1, ...], int]:
    grouped: dict[tuple[object, ...], list[EvidenceRecordV1]] = defaultdict(list)
    total = 0
    for record in records:
        total += 1
        grouped[_stable_source_record_key(record)].append(record)

    selected: list[EvidenceRecordV1] = []
    for rows in grouped.values():
        selected.append(
            max(
                rows,
                key=lambda row: (
                    row.source.retrieved_at,
                    row.record_sha256,
                ),
            )
        )
    selected.sort(key=_record_sort_key)
    return tuple(selected), total - len(selected)


def _matches_fact_identity(
    record: EvidenceRecordV1,
    requirement: EvidenceRequirementV1,
) -> bool:
    if record.fact_type is not requirement.fact_type:
        return False
    if requirement.fact_key_prefix is not None and not record.fact_key.startswith(
        requirement.fact_key_prefix
    ):
        return False
    return True


def _matches_requirement(
    record: EvidenceRecordV1,
    requirement: EvidenceRequirementV1,
) -> bool:
    if not _matches_fact_identity(record, requirement):
        return False
    if record.source.source_class not in requirement.source_classes:
        return False
    return True


def _matching_probes(
    probes: tuple[EvidenceCoverageProbeV1, ...],
    requirement: EvidenceRequirementV1,
) -> tuple[EvidenceCoverageProbeV1, ...]:
    return tuple(
        probe
        for probe in probes
        if probe.fact_type is requirement.fact_type
        and probe.source_class in requirement.source_classes
    )


def _coverage_gap(
    *,
    requirement: EvidenceRequirementV1,
    records: tuple[EvidenceRecordV1, ...],
    probes: tuple[EvidenceCoverageProbeV1, ...],
    assessed_at: datetime,
) -> EvidenceCoverageGapV1 | None:
    observed = tuple(
        row for row in records if _matches_fact_identity(row, requirement)
    )
    matching = tuple(row for row in observed if _matches_requirement(row, requirement))
    decision_grade = tuple(
        row for row in matching if row.use is EvidenceUse.DECISION_GRADE
    )
    fresh = tuple(
        row
        for row in decision_grade
        if _is_fresh(
            _record_effective_time(row),
            assessed_at=assessed_at,
            max_age_seconds=requirement.max_age_seconds,
        )
    )

    if len(fresh) >= requirement.minimum_decision_grade_records:
        if requirement.minimum_decision_grade_records > 0:
            return None
        if not requirement.allow_empty_after_successful_probe:
            return None

    requirement_probes = _matching_probes(probes, requirement)
    fresh_successful_probes = tuple(
        probe
        for probe in requirement_probes
        if probe.success
        and _is_fresh(
            probe.checked_at,
            assessed_at=assessed_at,
            max_age_seconds=requirement.max_age_seconds,
        )
    )
    if requirement.allow_empty_after_successful_probe and fresh_successful_probes:
        return None

    if decision_grade and not fresh:
        reason = CoverageGapReason.STALE_RECORD
    elif requirement_probes and not fresh_successful_probes:
        if any(not probe.success for probe in requirement_probes):
            reason = CoverageGapReason.SOURCE_UNAVAILABLE
        else:
            reason = CoverageGapReason.PROBE_STALE
    elif requirement.allow_empty_after_successful_probe and not requirement_probes:
        reason = CoverageGapReason.PROBE_MISSING
    elif observed and not decision_grade:
        reason = CoverageGapReason.NO_DECISION_GRADE_RECORD
    elif requirement.minimum_decision_grade_records > 0:
        reason = CoverageGapReason.INSUFFICIENT_RECORDS
    else:
        reason = CoverageGapReason.PROBE_MISSING

    return EvidenceCoverageGapV1(
        requirement_id=requirement.requirement_id,
        fact_type=requirement.fact_type,
        importance=requirement.importance,
        reason=reason,
    )


def _comparison_period(record: EvidenceRecordV1) -> str | None:
    value = record.effective_at or record.published_at
    if value is None:
        return None
    return value.isoformat()


def _requirement_importance_for_record(
    record: EvidenceRecordV1,
    requirements: tuple[EvidenceRequirementV1, ...],
) -> RequirementImportance:
    matches = [
        item.importance
        for item in requirements
        if _matches_requirement(record, item)
    ]
    if RequirementImportance.CRITICAL in matches:
        return RequirementImportance.CRITICAL
    if RequirementImportance.MATERIAL in matches:
        return RequirementImportance.MATERIAL
    return RequirementImportance.CONTEXT


def _contradictions(
    records: tuple[EvidenceRecordV1, ...],
    requirements: tuple[EvidenceRequirementV1, ...],
) -> tuple[EvidenceContradictionV1, ...]:
    grouped: dict[tuple[str, str | None], list[EvidenceRecordV1]] = defaultdict(list)
    for record in records:
        if record.use is not EvidenceUse.DECISION_GRADE:
            continue
        grouped[(record.fact_key, _comparison_period(record))].append(record)

    conflicts: list[EvidenceContradictionV1] = []
    for (fact_key, comparison_period), rows in grouped.items():
        values = {
            f"{row.value.value_type.value}:{row.value.canonical_value}:{row.value.currency or ''}"
            for row in rows
        }
        if len(values) < 2:
            continue
        importance = max(
            (_requirement_importance_for_record(row, requirements) for row in rows),
            key=lambda item: {
                RequirementImportance.CONTEXT: 0,
                RequirementImportance.MATERIAL: 1,
                RequirementImportance.CRITICAL: 2,
            }[item],
        )
        severity = {
            RequirementImportance.CRITICAL: ContradictionSeverity.CRITICAL,
            RequirementImportance.MATERIAL: ContradictionSeverity.MATERIAL,
            RequirementImportance.CONTEXT: ContradictionSeverity.MINOR,
        }[importance]
        conflicts.append(
            EvidenceContradictionV1(
                fact_key=fact_key,
                comparison_period=comparison_period,
                severity=severity,
                record_sha256s=tuple(row.record_sha256 for row in rows),
                distinct_values=tuple(values),
                unresolved=True,
            )
        )
    return tuple(
        sorted(
            conflicts,
            key=lambda row: (
                row.fact_key,
                row.comparison_period or "",
                row.severity.value,
            ),
        )
    )


def _probe_sort_key(probe: EvidenceCoverageProbeV1) -> tuple[object, ...]:
    return (
        probe.fact_type.value,
        _SOURCE_PRIORITY[probe.source_class],
        probe.checked_at,
        probe.success,
        probe.record_count,
        probe.source_error or "",
    )


def _requirement_sort_key(requirement: EvidenceRequirementV1) -> tuple[object, ...]:
    return (
        requirement.importance.value,
        requirement.fact_type.value,
        requirement.fact_key_prefix or "",
        requirement.requirement_id,
    )


def build_research_dossier(
    *,
    target: ResearchTargetV1,
    records: tuple[EvidenceRecordV1, ...],
    probes: tuple[EvidenceCoverageProbeV1, ...],
    requirements: tuple[EvidenceRequirementV1, ...],
    assessed_at: datetime | None = None,
) -> ResearchDossierV1:
    """Build a deterministic, fail-closed research dossier from normalized evidence."""

    now = _aware_utc(assessed_at)
    if any(record.instrument_uid != target.instrument_uid for record in records):
        raise ResearchEvidenceError("RESEARCH_RECORD_INSTRUMENT_UID_MISMATCH")
    if any(probe.instrument_uid != target.instrument_uid for probe in probes):
        raise ResearchEvidenceError("RESEARCH_PROBE_INSTRUMENT_UID_MISMATCH")

    unique_requirements = {row.requirement_id for row in requirements}
    if len(unique_requirements) != len(requirements):
        raise ResearchEvidenceError("RESEARCH_REQUIREMENT_ID_DUPLICATE")

    normalized_records, duplicates_removed = _deduplicate_records(records)
    normalized_probes = tuple(sorted(probes, key=_probe_sort_key))
    normalized_requirements = tuple(sorted(requirements, key=_requirement_sort_key))
    coverage_gaps = tuple(
        gap
        for requirement in normalized_requirements
        if (
            gap := _coverage_gap(
                requirement=requirement,
                records=normalized_records,
                probes=normalized_probes,
                assessed_at=now,
            )
        )
        is not None
    )
    contradictions = _contradictions(normalized_records, normalized_requirements)
    decision_ready = not any(
        gap.importance in {RequirementImportance.CRITICAL, RequirementImportance.MATERIAL}
        for gap in coverage_gaps
    )
    strong_recommendation_allowed = decision_ready and not any(
        row.severity is ContradictionSeverity.CRITICAL and row.unresolved
        for row in contradictions
    )

    provisional = ResearchDossierV1.model_construct(
        target=target,
        assessed_at=now,
        requirements=normalized_requirements,
        probes=normalized_probes,
        records=normalized_records,
        contradictions=contradictions,
        coverage_gaps=coverage_gaps,
        duplicate_records_removed=duplicates_removed,
        dossier_sha256="0" * 64,
        decision_ready=decision_ready,
        strong_recommendation_allowed=strong_recommendation_allowed,
        raw_content_stored=False,
        trading_methods=False,
    )
    dossier_sha256 = research_dossier_sha256(provisional)
    payload = provisional.model_dump(mode="json")
    payload["dossier_sha256"] = dossier_sha256
    return ResearchDossierV1.model_validate(payload)
