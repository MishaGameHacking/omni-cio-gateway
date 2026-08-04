from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Iterable

from omni_cio.contracts.v1.credit import CreditRatingAction
from omni_cio.contracts.v1.market import CorporateEventType
from omni_cio.contracts.v1.observability import ObservabilitySeverity
from omni_cio.contracts.v1.portfolio_risk import RiskSeverity, RiskVectorKind
from omni_cio.contracts.v1.watchtower import (
    WatchtowerActionKind,
    WatchtowerAlertV1,
    WatchtowerEvaluationV1,
    WatchtowerInputV1,
    WatchtowerSignalKind,
    WatchtowerStateV1,
    watchtower_alert_id,
    watchtower_evaluation_sha256,
    watchtower_state_sha256,
)

from .journal_v1 import WatchtowerJournalConflict, WatchtowerJournalV1


_MATERIAL_CORPORATE_EVENTS = {
    CorporateEventType.MATURITY,
    CorporateEventType.OFFER,
    CorporateEventType.AMORTIZATION,
    CorporateEventType.DELISTING,
}
_MAX_DELIVERY_IDS = 256


class WatchtowerError(ValueError):
    pass


@dataclass(frozen=True)
class _Candidate:
    fingerprint_sha256: str
    kind: WatchtowerSignalKind
    severity: ObservabilitySeverity
    subject_key: str
    effective_at: datetime
    evidence_sha256s: tuple[str, ...]
    message_code: str
    requires_owner_attention: bool
    action: WatchtowerActionKind


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _model_sha(value: object) -> str:
    if hasattr(value, "model_dump"):
        return _sha(value.model_dump(mode="json"))
    return _sha(value)


def _watch_id(value: WatchtowerInputV1) -> str:
    identity = _sha({"policy_id": value.policy_reference.policy_id})[:32]
    return f"watch_{identity}"


def _candidate(
    *,
    kind: WatchtowerSignalKind,
    severity: ObservabilitySeverity,
    subject_key: str,
    effective_at: datetime,
    evidence_sha256s: Iterable[str],
    message_code: str,
    requires_owner_attention: bool,
    action: WatchtowerActionKind,
    semantic_identity: object,
) -> _Candidate:
    evidence = tuple(sorted(set(evidence_sha256s)))
    if not evidence:
        raise WatchtowerError("watchtower candidate requires evidence")
    fingerprint = _sha(
        {
            "kind": kind.value,
            "subject_key": subject_key,
            "semantic_identity": semantic_identity,
        }
    )
    return _Candidate(
        fingerprint_sha256=fingerprint,
        kind=kind,
        severity=severity,
        subject_key=subject_key,
        effective_at=effective_at,
        evidence_sha256s=evidence,
        message_code=message_code,
        requires_owner_attention=requires_owner_attention,
        action=action,
    )


def _alert(candidate: _Candidate) -> WatchtowerAlertV1:
    provisional = WatchtowerAlertV1.model_construct(
        alert_id="0" * 64,
        fingerprint_sha256=candidate.fingerprint_sha256,
        kind=candidate.kind,
        severity=candidate.severity,
        subject_key=candidate.subject_key,
        effective_at=candidate.effective_at,
        evidence_sha256s=candidate.evidence_sha256s,
        message_code=candidate.message_code,
        requires_owner_attention=candidate.requires_owner_attention,
        action=candidate.action,
        execution_authorized=False,
        trading_methods=False,
    )
    return WatchtowerAlertV1.model_validate(
        provisional.model_copy(update={"alert_id": watchtower_alert_id(provisional)}).model_dump(
            mode="python"
        )
    )


def _state(
    *,
    watch_id: str,
    revision: int,
    initialized_at: datetime,
    updated_at: datetime,
    value: WatchtowerInputV1,
    delivery_ids: Iterable[str],
    active_fingerprints: Iterable[str],
) -> WatchtowerStateV1:
    bounded_deliveries = tuple(sorted(set(delivery_ids)))[-_MAX_DELIVERY_IDS:]
    provisional = WatchtowerStateV1.model_construct(
        schema_version="1.0",
        watch_id=watch_id,
        revision=revision,
        initialized_at=initialized_at,
        updated_at=updated_at,
        policy_reference=value.policy_reference,
        last_portfolio_snapshot_sha256=value.portfolio_snapshot_sha256,
        last_risk_assessment_sha256=value.risk.assessment_sha256,
        last_input_sha256=value.input_sha256,
        seen_delivery_ids=bounded_deliveries,
        seen_fingerprints=tuple(sorted(set(active_fingerprints))),
        state_sha256="0" * 64,
        execution_authorized=False,
        trading_methods=False,
    )
    return WatchtowerStateV1.model_validate(
        provisional.model_copy(
            update={"state_sha256": watchtower_state_sha256(provisional)}
        ).model_dump(mode="python")
    )


def _evaluation(
    *,
    value: WatchtowerInputV1,
    state: WatchtowerStateV1,
    replay: bool,
    alerts: tuple[WatchtowerAlertV1, ...],
) -> WatchtowerEvaluationV1:
    proposed_action = WatchtowerActionKind.NONE
    if alerts:
        if any(row.severity is ObservabilitySeverity.ERROR for row in alerts):
            proposed_action = WatchtowerActionKind.REVIEW
        elif any(row.requires_owner_attention for row in alerts):
            proposed_action = WatchtowerActionKind.RECOMMENDATION
        else:
            proposed_action = WatchtowerActionKind.REVIEW
    provisional = WatchtowerEvaluationV1.model_construct(
        schema_version="1.0",
        evaluated_at=value.checked_at,
        watch_id=state.watch_id,
        input_sha256=value.input_sha256,
        replay=replay,
        alerts=alerts,
        material_change=bool(alerts),
        should_notify=bool(alerts),
        proposed_action=proposed_action,
        state=state,
        evaluation_sha256="0" * 64,
        execution_authorized=False,
        trading_methods=False,
    )
    return WatchtowerEvaluationV1.model_validate(
        provisional.model_copy(
            update={"evaluation_sha256": watchtower_evaluation_sha256(provisional)}
        ).model_dump(mode="python")
    )


def _severity_from_risk(value: RiskSeverity) -> ObservabilitySeverity:
    if value is RiskSeverity.BREACH:
        return ObservabilitySeverity.ERROR
    if value in {RiskSeverity.HIGH, RiskSeverity.UNKNOWN}:
        return ObservabilitySeverity.WARNING
    return ObservabilitySeverity.INFO


def _credit_candidates(value: WatchtowerInputV1) -> list[_Candidate]:
    rows: list[_Candidate] = []
    for passport in value.credit_passports:
        subject = passport.target.instrument_uid
        for rating in passport.ratings:
            if rating.action is CreditRatingAction.DOWNGRADED:
                rows.append(
                    _candidate(
                        kind=WatchtowerSignalKind.RATING_DOWNGRADE,
                        severity=ObservabilitySeverity.WARNING,
                        subject_key=subject,
                        effective_at=rating.effective_at,
                        evidence_sha256s=rating.source_record_sha256s,
                        message_code="WATCHTOWER_RATING_DOWNGRADE",
                        requires_owner_attention=True,
                        action=WatchtowerActionKind.RECOMMENDATION,
                        semantic_identity={
                            "observation_id": rating.observation_id,
                            "rating": rating.rating,
                            "action": rating.action.value,
                        },
                    )
                )
            if rating.watch:
                rows.append(
                    _candidate(
                        kind=WatchtowerSignalKind.RATING_WATCH,
                        severity=ObservabilitySeverity.WARNING,
                        subject_key=subject,
                        effective_at=rating.effective_at,
                        evidence_sha256s=rating.source_record_sha256s,
                        message_code="WATCHTOWER_RATING_WATCH",
                        requires_owner_attention=True,
                        action=WatchtowerActionKind.RECOMMENDATION,
                        semantic_identity={
                            "observation_id": rating.observation_id,
                            "watch": rating.watch,
                        },
                    )
                )
        for event in passport.default_events:
            if event.active:
                rows.append(
                    _candidate(
                        kind=WatchtowerSignalKind.DEFAULT_EVENT,
                        severity=ObservabilitySeverity.ERROR,
                        subject_key=event.subject_id,
                        effective_at=event.occurred_at,
                        evidence_sha256s=event.source_record_sha256s,
                        message_code="WATCHTOWER_ACTIVE_DEFAULT_EVENT",
                        requires_owner_attention=True,
                        action=WatchtowerActionKind.REVIEW,
                        semantic_identity={
                            "event_id": event.event_id,
                            "event_type": event.event_type.value,
                        },
                    )
                )
    return rows


def _market_candidates(value: WatchtowerInputV1) -> list[_Candidate]:
    rows: list[_Candidate] = []
    for bundle in value.market_bundles:
        for event in bundle.events:
            if event.event_type not in _MATERIAL_CORPORATE_EVENTS:
                continue
            severity = (
                ObservabilitySeverity.ERROR
                if event.event_type is CorporateEventType.DELISTING
                else ObservabilitySeverity.WARNING
            )
            rows.append(
                _candidate(
                    kind=WatchtowerSignalKind.CORPORATE_EVENT,
                    severity=severity,
                    subject_key=event.instrument_key,
                    effective_at=event.announced_at,
                    evidence_sha256s=(_model_sha(event),),
                    message_code=f"WATCHTOWER_CORPORATE_{event.event_type.value.upper()}",
                    requires_owner_attention=True,
                    action=WatchtowerActionKind.RECOMMENDATION,
                    semantic_identity={
                        "event_id": event.event_id,
                        "event_type": event.event_type.value,
                    },
                )
            )
    return rows


def _risk_candidates(value: WatchtowerInputV1) -> list[_Candidate]:
    rows: list[_Candidate] = []
    risk = value.risk.before

    if not risk.policy_compliant:
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.POLICY_DRIFT,
                severity=ObservabilitySeverity.ERROR,
                subject_key="portfolio:policy",
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code="WATCHTOWER_POLICY_BREACH",
                requires_owner_attention=True,
                action=WatchtowerActionKind.REVIEW,
                semantic_identity={
                    "policy": value.policy_reference.fingerprint_sha256,
                    "blockers": [row.value for row in risk.blockers],
                },
            )
        )

    breached_rows = [row for row in risk.concentration.rows if row.breached]
    for row in breached_rows:
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.CONCENTRATION_BREACH,
                severity=(
                    ObservabilitySeverity.ERROR
                    if row.hard_limit
                    else ObservabilitySeverity.WARNING
                ),
                subject_key=f"{row.dimension.value}:{row.bucket_key}",
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code="WATCHTOWER_CONCENTRATION_BREACH",
                requires_owner_attention=True,
                action=WatchtowerActionKind.RECOMMENDATION,
                semantic_identity={
                    "dimension": row.dimension.value,
                    "bucket": row.bucket_key,
                    "hard": row.hard_limit,
                },
            )
        )

    for row in risk.liquidity:
        if not (row.stale or row.unknown):
            continue
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.LIQUIDITY_DETERIORATION,
                severity=ObservabilitySeverity.WARNING,
                subject_key=row.stable_key,
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code=(
                    "WATCHTOWER_LIQUIDITY_UNKNOWN"
                    if row.unknown
                    else "WATCHTOWER_LIQUIDITY_STALE"
                ),
                requires_owner_attention=True,
                action=WatchtowerActionKind.RECOMMENDATION,
                semantic_identity={"stable_key": row.stable_key, "stale": row.stale, "unknown": row.unknown},
            )
        )

    vector_by_kind = {row.kind: row for row in risk.vectors}
    liquidity_vector = vector_by_kind[RiskVectorKind.LIQUIDITY]
    if (
        not any(row.kind is WatchtowerSignalKind.LIQUIDITY_DETERIORATION for row in rows)
        and liquidity_vector.severity in {RiskSeverity.HIGH, RiskSeverity.BREACH, RiskSeverity.UNKNOWN}
    ):
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.LIQUIDITY_DETERIORATION,
                severity=_severity_from_risk(liquidity_vector.severity),
                subject_key="portfolio:liquidity",
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code="WATCHTOWER_LIQUIDITY_RISK",
                requires_owner_attention=True,
                action=WatchtowerActionKind.RECOMMENDATION,
                semantic_identity={
                    "severity": liquidity_vector.severity.value,
                    "evidence_codes": list(liquidity_vector.evidence_codes),
                },
            )
        )

    concentration_vector = vector_by_kind[RiskVectorKind.CONCENTRATION]
    if not breached_rows and concentration_vector.severity in {
        RiskSeverity.HIGH,
        RiskSeverity.BREACH,
        RiskSeverity.UNKNOWN,
    }:
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.CONCENTRATION_BREACH,
                severity=_severity_from_risk(concentration_vector.severity),
                subject_key="portfolio:concentration",
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code="WATCHTOWER_CONCENTRATION_RISK",
                requires_owner_attention=True,
                action=WatchtowerActionKind.RECOMMENDATION,
                semantic_identity={
                    "severity": concentration_vector.severity.value,
                    "evidence_codes": list(concentration_vector.evidence_codes),
                },
            )
        )

    quality_vector = vector_by_kind[RiskVectorKind.DATA_QUALITY]
    quality_codes = tuple(sorted(set(value.source_quality_codes) | set(quality_vector.evidence_codes)))
    if quality_codes or quality_vector.severity in {RiskSeverity.HIGH, RiskSeverity.BREACH, RiskSeverity.UNKNOWN}:
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.DATA_QUALITY,
                severity=_severity_from_risk(quality_vector.severity),
                subject_key="portfolio:data_quality",
                effective_at=value.risk.assessed_at,
                evidence_sha256s=(value.risk.assessment_sha256,),
                message_code="WATCHTOWER_DATA_QUALITY",
                requires_owner_attention=quality_vector.severity is not RiskSeverity.LOW,
                action=(
                    WatchtowerActionKind.REVIEW
                    if quality_vector.severity is not RiskSeverity.LOW
                    else WatchtowerActionKind.NONE
                ),
                semantic_identity={
                    "severity": quality_vector.severity.value,
                    "codes": list(quality_codes),
                },
            )
        )
    return rows


def _candidates(value: WatchtowerInputV1, previous: WatchtowerStateV1 | None) -> tuple[_Candidate, ...]:
    rows = _credit_candidates(value) + _market_candidates(value) + _risk_candidates(value)
    if previous is not None and previous.policy_reference != value.policy_reference:
        rows.append(
            _candidate(
                kind=WatchtowerSignalKind.POLICY_DRIFT,
                severity=ObservabilitySeverity.ERROR,
                subject_key="portfolio:policy_identity",
                effective_at=value.checked_at,
                evidence_sha256s=(value.policy_reference.fingerprint_sha256,),
                message_code="WATCHTOWER_POLICY_IDENTITY_CHANGED",
                requires_owner_attention=True,
                action=WatchtowerActionKind.REVIEW,
                semantic_identity={
                    "from": previous.policy_reference.model_dump(mode="json"),
                    "to": value.policy_reference.model_dump(mode="json"),
                },
            )
        )
    unique = {row.fingerprint_sha256: row for row in rows}
    return tuple(sorted(unique.values(), key=lambda row: (row.kind.value, row.subject_key, row.fingerprint_sha256)))


class PortfolioWatchtowerV1:
    """Read-only deterministic reducer over canonical WP6/WP8/market evidence."""

    def __init__(
        self,
        *,
        journal: WatchtowerJournalV1,
        require_durable_journal: bool = True,
    ) -> None:
        if require_durable_journal and not journal.durable:
            raise WatchtowerError("WATCHTOWER_DURABLE_JOURNAL_REQUIRED")
        self._journal = journal

    def evaluate(self, value: WatchtowerInputV1) -> WatchtowerEvaluationV1:
        canonical = WatchtowerInputV1.model_validate(value.model_dump(mode="python"))
        watch_id = _watch_id(canonical)
        previous = self._journal.get(watch_id)
        if previous is not None and canonical.delivery_id in previous.seen_delivery_ids:
            return _evaluation(value=canonical, state=previous, replay=True, alerts=())

        candidates = _candidates(canonical, previous)
        candidate_fingerprints = tuple(row.fingerprint_sha256 for row in candidates)
        previous_fingerprints = set(previous.seen_fingerprints if previous is not None else ())

        if previous is None:
            emit = tuple(
                row
                for row in candidates
                if row.severity in {ObservabilitySeverity.WARNING, ObservabilitySeverity.ERROR}
            )
            state = _state(
                watch_id=watch_id,
                revision=0,
                initialized_at=canonical.checked_at,
                updated_at=canonical.checked_at,
                value=canonical,
                delivery_ids=(canonical.delivery_id,),
                active_fingerprints=candidate_fingerprints,
            )
            try:
                committed = self._journal.put(state)
            except WatchtowerJournalConflict as exc:
                raise WatchtowerError("WATCHTOWER_JOURNAL_CONFLICT") from exc
        else:
            emit = tuple(row for row in candidates if row.fingerprint_sha256 not in previous_fingerprints)
            state = _state(
                watch_id=watch_id,
                revision=previous.revision + 1,
                initialized_at=previous.initialized_at,
                updated_at=canonical.checked_at,
                value=canonical,
                delivery_ids=(*previous.seen_delivery_ids, canonical.delivery_id),
                active_fingerprints=candidate_fingerprints,
            )
            try:
                committed = self._journal.compare_and_swap(
                    watch_id,
                    expected_revision=previous.revision,
                    updated=state,
                )
            except WatchtowerJournalConflict as exc:
                raise WatchtowerError("WATCHTOWER_JOURNAL_CONFLICT") from exc

        alerts = tuple(_alert(row) for row in emit)
        return _evaluation(value=canonical, state=committed, replay=False, alerts=alerts)
