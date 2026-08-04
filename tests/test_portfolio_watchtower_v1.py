from __future__ import annotations

from datetime import timedelta

import pytest

from omni_cio.contracts.v1.credit import (
    CreditBlockerCode,
    CreditDefaultEventType,
    CreditDefaultEventV1,
    CreditEntityIdentityV1,
    CreditEntityKind,
    CreditFloorAssessmentV1,
    CreditFloorBasis,
    CreditPassportV1,
    CreditRatingAction,
    CreditRatingAgency,
    CreditRatingObservationV1,
    CreditRatingScale,
    CreditRatingSubject,
    CreditReanalysisTriggerCode,
    CreditReanalysisTriggerV1,
    DebtIssueTermsV1,
    DebtSeniority,
    credit_passport_sha256,
)
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import ResearchTargetV1
from omni_cio.contracts.v1.watchtower import (
    WatchtowerActionKind,
    WatchtowerInputV1,
    WatchtowerSignalKind,
    watchtower_input_sha256,
)
from omni_cio.watchtower import (
    InMemoryWatchtowerJournalV1,
    PortfolioWatchtowerV1,
    WatchtowerError,
)
from tests.v9_execution_fixture import NOW, build_execution_fixture


SOURCE_SHA = "d" * 64
TARGET = ResearchTargetV1(
    funnel_sha256="e" * 64,
    candidate_id="uid:watch-bond-1",
    instrument_uid="watch-bond-1",
    instrument_type=InstrumentType.BOND,
)


def _passport(*, active_default: bool = False) -> CreditPassportV1:
    fixture = build_execution_fixture()
    rating = CreditRatingObservationV1(
        observation_id="rating_watchtower_down_1",
        subject=CreditRatingSubject.ISSUE,
        subject_id=TARGET.instrument_uid,
        agency=CreditRatingAgency.ACRA,
        scale=CreditRatingScale.ACRA_RU_NATIONAL,
        rating="A-(RU)",
        outlook="negative",
        action=CreditRatingAction.DOWNGRADED,
        effective_at=NOW,
        source_record_sha256s=(SOURCE_SHA,),
    )
    default_events = (
        CreditDefaultEventV1(
            event_id="credit_event_watchtower_default_1",
            event_type=CreditDefaultEventType.DEFAULT,
            subject_id=TARGET.instrument_uid,
            occurred_at=NOW,
            source_record_sha256s=("f" * 64,),
        ),
    ) if active_default else ()
    blockers = (CreditBlockerCode.ACTIVE_DEFAULT_EVENT,) if active_default else ()
    reanalysis_codes = (
        CreditReanalysisTriggerCode.DEFAULT_EVENT_CHANGED
        if active_default
        else CreditReanalysisTriggerCode.RATING_CHANGED
    )
    values = {
        "schema_version": "1.0",
        "assessed_at": NOW,
        "dossier_sha256": "a" * 64,
        "target": TARGET,
        "policy_reference": fixture.risk.policy_reference,
        "issuer": CreditEntityIdentityV1(
            entity_id="credit_watch_issuer_1",
            kind=CreditEntityKind.ISSUER,
            name="Watch Issuer",
            source_record_sha256s=(SOURCE_SHA,),
        ),
        "guarantors": (),
        "issue_terms": DebtIssueTermsV1(
            instrument_uid=TARGET.instrument_uid,
            issuer_entity_id="credit_watch_issuer_1",
            seniority=DebtSeniority.SENIOR_UNSECURED,
            source_record_sha256s=(SOURCE_SHA,),
        ),
        "financial_metrics": (),
        "ratings": (rating,),
        "default_events": default_events,
        "floor_assessment": CreditFloorAssessmentV1(
            policy_scale=CreditRatingScale.ACRA_RU_NATIONAL,
            policy_floor="A-(RU)",
            basis=CreditFloorBasis.ISSUE,
            selected_observation_id=rating.observation_id,
            selected_rating=rating.rating,
            selected_subject_id=rating.subject_id,
            meets_floor=True,
        ),
        "reanalysis": CreditReanalysisTriggerV1(
            required=True,
            codes=(reanalysis_codes,),
        ),
        "blockers": blockers,
        "passport_sha256": "0" * 64,
        "decision_ready": not active_default,
        "strong_recommendation_allowed": not active_default,
        "trading_methods": False,
    }
    provisional = CreditPassportV1.model_construct(**values)
    values["passport_sha256"] = credit_passport_sha256(provisional)
    return CreditPassportV1.model_validate(values)


def _input(
    delivery_id: str,
    *,
    checked_offset_minutes: int = 1,
    passports: tuple[CreditPassportV1, ...] = (),
) -> WatchtowerInputV1:
    fixture = build_execution_fixture()
    values = {
        "schema_version": "1.0",
        "checked_at": NOW + timedelta(minutes=checked_offset_minutes),
        "delivery_id": delivery_id,
        "portfolio_snapshot_sha256": fixture.risk.portfolio_snapshot_sha256,
        "policy_reference": fixture.risk.policy_reference,
        "risk": fixture.risk,
        "credit_passports": passports,
        "market_bundles": (),
        "source_quality_codes": (),
        "input_sha256": "0" * 64,
        "execution_authorized": False,
        "trading_methods": False,
    }
    provisional = WatchtowerInputV1.model_construct(**values)
    values["input_sha256"] = watchtower_input_sha256(provisional)
    return WatchtowerInputV1.model_validate(values)


def _service() -> PortfolioWatchtowerV1:
    return PortfolioWatchtowerV1(
        journal=InMemoryWatchtowerJournalV1(),
        require_durable_journal=False,
    )


def test_clean_baseline_is_silent_and_duplicate_delivery_is_replay_safe() -> None:
    service = _service()
    first = service.evaluate(_input("delivery-clean-0001"))

    assert first.alerts == ()
    assert first.material_change is False
    assert first.should_notify is False
    assert first.proposed_action is WatchtowerActionKind.NONE
    assert first.execution_authorized is False
    assert first.trading_methods is False
    assert first.state.revision == 0

    replay = service.evaluate(_input("delivery-clean-0001"))
    assert replay.replay is True
    assert replay.alerts == ()
    assert replay.state.revision == 0


def test_new_rating_downgrade_alerts_once_and_then_deduplicates() -> None:
    service = _service()
    service.evaluate(_input("delivery-rating-0001"))

    changed = service.evaluate(
        _input(
            "delivery-rating-0002",
            checked_offset_minutes=2,
            passports=(_passport(),),
        )
    )
    assert len(changed.alerts) == 1
    assert changed.alerts[0].kind is WatchtowerSignalKind.RATING_DOWNGRADE
    assert changed.alerts[0].requires_owner_attention is True
    assert changed.proposed_action is WatchtowerActionKind.RECOMMENDATION
    assert changed.should_notify is True

    same_condition = service.evaluate(
        _input(
            "delivery-rating-0003",
            checked_offset_minutes=3,
            passports=(_passport(),),
        )
    )
    assert same_condition.alerts == ()
    assert same_condition.should_notify is False


def test_resolved_signal_can_alert_again_when_it_reappears() -> None:
    service = _service()
    service.evaluate(_input("delivery-cycle-0001"))
    first = service.evaluate(
        _input("delivery-cycle-0002", checked_offset_minutes=2, passports=(_passport(),))
    )
    assert len(first.alerts) == 1

    cleared = service.evaluate(_input("delivery-cycle-0003", checked_offset_minutes=3))
    assert cleared.alerts == ()

    repeated_after_clear = service.evaluate(
        _input("delivery-cycle-0004", checked_offset_minutes=4, passports=(_passport(),))
    )
    assert len(repeated_after_clear.alerts) == 1
    assert repeated_after_clear.alerts[0].kind is WatchtowerSignalKind.RATING_DOWNGRADE


def test_active_default_is_critical_even_on_initial_baseline() -> None:
    service = _service()
    result = service.evaluate(
        _input("delivery-default-0001", passports=(_passport(active_default=True),))
    )

    kinds = {row.kind for row in result.alerts}
    assert WatchtowerSignalKind.DEFAULT_EVENT in kinds
    default_alert = next(
        row for row in result.alerts if row.kind is WatchtowerSignalKind.DEFAULT_EVENT
    )
    assert default_alert.severity.value == "error"
    assert result.should_notify is True
    assert result.proposed_action is WatchtowerActionKind.REVIEW
    assert result.execution_authorized is False


def test_real_watchtower_requires_durable_journal_by_default() -> None:
    with pytest.raises(WatchtowerError, match="WATCHTOWER_DURABLE_JOURNAL_REQUIRED"):
        PortfolioWatchtowerV1(journal=InMemoryWatchtowerJournalV1())
