"""Provider-shaped dividend collisions retained without inventing payout identity."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from test_intelligence import _bundle
from test_observer import LEGAL_VERSIONS
from test_portfolio_refresh_postgres import owner
from test_workspace_postgres import notification_service, payout_position, user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.broker import BrokerEvidenceSnapshot, BrokerObservationBundle
from omnicio.db import Database
from omnicio.intelligence import EvidenceDocument, build_tbank_evidence
from omnicio.portfolio_store import PortfolioStore
from omnicio.tbank import TBankDividend, TBankInvestClient
from omnicio.workspace import default_preferences, event_id
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore

native_postgres = pytest.mark.skipif(
    not os.environ.get("OMNICIO_TEST_DATABASE_URL"), reason="ephemeral PostgreSQL is required",
)


def dividend_row(value: str, payment: datetime, **changes: Any) -> dict[str, Any]:
    return {
        "dividendNet": {"currency": "rub", "units": value, "nano": 0},
        "createdAt": "2026-09-25T12:00:00Z", "declaredDate": "2026-09-25T00:00:00Z",
        "recordDate": "2026-10-01T00:00:00Z", "lastBuyDate": "2026-09-30T00:00:00Z",
        "paymentDate": payment.isoformat(), "regularity": "Quarterly",
        "dividendType": "Regular", "yieldValue": {"units": "1", "nano": 0}, **changes,
    }


def parsed_dividends(uid: str, rows: list[dict[str, Any]]) -> tuple[TBankDividend, ...]:
    with patch.object(TBankInvestClient, "_post", return_value={"dividends": rows}):
        return TBankInvestClient().get_dividends(
            "synthetic-token", "prod", uid, from_at=datetime(2026, 1, 1, tzinfo=UTC),
            to_at=datetime(2027, 1, 1, tzinfo=UTC),
        )


def test_provider_accepts_distinct_keys_with_identical_distribution_anchors() -> None:
    uid, payment = str(uuid4()), datetime(2026, 10, 15, tzinfo=UTC)
    dividends = parsed_dividends(uid, [
        dividend_row("10", payment), dividend_row("12", payment + timedelta(days=1)),
    ])
    evidence = BrokerEvidenceSnapshot(
        refreshed_at=payment, dividends=dividends, coupons=(), bond_events=(), reports=(),
        fundamentals=(), sources=(),
    )
    documents, _ = build_tbank_evidence(_bundle(), evidence, assessed_at=payment)
    assert len(documents) == 2
    assert len({row.provider_key for row in documents}) == 2
    first, second = dividends
    assert first.created_at == second.created_at
    assert first.declared_date == second.declared_date
    assert first.record_date == second.record_date
    assert first.regularity == second.regularity
    assert first.dividend_net.currency == second.dividend_net.currency


@dataclass(frozen=True)
class PayoutObservation:
    database: Database
    owner: UUID
    bundle: BrokerObservationBundle
    job_id: UUID
    snapshot_id: UUID

    @property
    def uid(self) -> str:
        return self.bundle.portfolio.positions[0].instrument_uid

    def save(self, rows: list[dict[str, Any]], at: datetime) -> tuple[EvidenceDocument, ...]:
        evidence = BrokerEvidenceSnapshot(
            refreshed_at=at, dividends=parsed_dividends(self.uid, rows), coupons=(),
            bond_events=(), reports=(), fundamentals=(), sources=(),
        )
        documents, assessments = build_tbank_evidence(self.bundle, evidence, assessed_at=at)
        PortfolioStore(self.database).save_evidence(
            self.owner, job_run_id=self.job_id, snapshot_id=self.snapshot_id,
            documents=documents, assessments=assessments, retrieved_at=evidence.refreshed_at,
        )
        return documents

    def payouts(self) -> list[dict[str, Any]]:
        result = PortfolioStore(self.database).instrument_visualization(self.owner, self.uid)
        assert result is not None
        return result["payouts"]


def payout_observation(database: Database, at: datetime) -> PayoutObservation:
    ident, uid, original = owner(database), str(uuid4()), _bundle()
    position = replace(original.portfolio.positions[0], instrument_uid=uid,
                       figi=f"FIGI-{uid}", instrument_type="share")
    metadata = replace(original.metadata[0], uid=uid, figi=position.figi,
                       asset_uid=str(uuid4()), instrument_type="share")
    bundle = replace(original, account_id=str(ident), refreshed_at=at,
                     portfolio=replace(original.portfolio, positions=(position,)),
                     metadata=(metadata,))
    store = PortfolioStore(database)
    store.request_refresh(ident, LEGAL_VERSIONS)
    job = store.claim_refresh_job(ident, LEGAL_VERSIONS)
    assert job is not None
    snapshot = store.save_snapshot(ident, job_run_id=job.id, bundle=bundle)
    return PayoutObservation(database, ident, bundle, job.id, snapshot)


def payment_events(store: WorkspaceStore, ident: UUID) -> list[dict[str, Any]]:
    return store.events(ident, category="payments")["items"]


@native_postgres
def test_co_observed_dividends_remain_uncertain_across_correction_and_later_receipts(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    store = WorkspaceStore(database)
    payment = at + timedelta(days=2)
    first, second = dividend_row("10", payment), dividend_row("12", payment + timedelta(days=1))
    documents = observation.save([first, second], at)
    payouts = observation.payouts()
    assert {row["amount"] for row in payouts} == {Decimal("10"), Decimal("12")}
    assert len(payouts) == 2
    assert all(row["identity_status"] == "ambiguous" for row in payouts)
    assert all(row["identity_reason"] == "co_observed_anchor_collision" for row in payouts)
    assert all(row["retrieved_at"] == at for row in payouts)
    with store._transaction(observation.owner) as cur:
        cur.execute(
            "SELECT count(DISTINCT pe.provider_key) AS keys, count(DISTINCT sr.retrieved_at) "
            "AS observed_times FROM payout_events pe JOIN source_retrievals sr "
            "ON sr.source_document_id = pe.source_document_id WHERE pe.instrument_uid = %s",
            (observation.uid,),
        )
        assert cur.fetchone() == {"keys": 2, "observed_times": 1}
    warnings = payment_events(store, observation.owner)
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning["kind"] == "payout_identity_ambiguous"
    assert warning["severity"] == "warning"
    assert set(warning["source"]) == {
        "type", "provider", "instrument_uid", "event_type", "anchor_key", "identity_status",
        "identity_reason", "url",
    }
    assert warning["source"]["identity_status"] == "ambiguous"
    store.mark_events_read(observation.owner, [warning["id"]])
    read_warning = store.get_event(observation.owner, warning["id"])
    other = user(database, account=True)
    assert payment_events(store, other) == []
    assert PortfolioStore(database).instrument_visualization(other, observation.uid) is None
    with pytest.raises(WorkspaceNotFound):
        store.get_event(other, warning["id"])
    payout_position(store, other, observation.uid, at)
    shared_warning = payment_events(store, other)
    assert len(shared_warning) == 1
    assert shared_warning[0]["read_at"] is None
    assert store.get_event(observation.owner, warning["id"])["read_at"] == read_warning["read_at"]

    corrected = dividend_row("11", payment)
    for minute, rows, amounts in (
        (1, [corrected, second], {Decimal("11"), Decimal("12")}),
        (2, [corrected, second], {Decimal("11"), Decimal("12")}),
        (3, [corrected], {Decimal("11")}),
        (4, [second], {Decimal("12")}),
    ):
        received = at + timedelta(minutes=minute)
        observation.save(rows, received)
        current = observation.payouts()
        # Latest positive observations are explicitly uncertain, not a complete response proof.
        assert {row["amount"] for row in current} == amounts
        assert len(current) == len(amounts)
        assert all(row["identity_status"] == "ambiguous" for row in current)
        assert all(row["retrieved_at"] == received for row in current)
        assert payment_events(store, observation.owner) == [read_warning]
    with store._transaction(observation.owner) as cur:
        cur.execute("SELECT count(*) AS total FROM payout_events WHERE instrument_uid = %s",
                    (observation.uid,))
        assert cur.fetchone()["total"] == 3
        cur.execute("SELECT provider_key FROM payout_events WHERE instrument_uid = %s",
                    (observation.uid,))
        assert {doc.provider_key for doc in documents}.issubset(
            {row["provider_key"] for row in cur.fetchall()},
        )


@native_postgres
def test_multiple_versions_of_one_provider_key_do_not_make_identity_ambiguous(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    payment = at + timedelta(days=2)
    documents = observation.save([
        dividend_row("10", payment),
        dividend_row("10", payment, yieldValue={"units": "2", "nano": 0}),
    ], at)
    assert len(documents) == 2
    assert len({doc.provider_key for doc in documents}) == 1
    payouts = observation.payouts()
    assert len(payouts) == 1
    assert "identity_status" not in payouts[0]
    assert "identity_reason" not in payouts[0]
    events = payment_events(WorkspaceStore(database), observation.owner)
    assert len(events) == 1
    assert events[0]["kind"] == "payout_calendar"


@native_postgres
@pytest.mark.parametrize(("second_type", "statuses"), [
    ("Cancelled", {"scheduled", "cancelled"}),
    ("Return of Capital", {"scheduled"}),
])
def test_co_observed_material_conflicts_keep_both_rows_even_with_one_provider_key(
    workspace_database: tuple[Database, str, str], second_type: str, statuses: set[str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    payment = at + timedelta(days=2)
    documents = observation.save([
        dividend_row("10", payment), dividend_row("10", payment, dividendType=second_type),
    ], at)
    assert len({doc.provider_key for doc in documents}) == 1
    payouts = observation.payouts()
    assert len(payouts) == 2
    assert {row["status"] for row in payouts} == statuses
    assert all(row["identity_status"] == "ambiguous" for row in payouts)
    events = payment_events(WorkspaceStore(database), observation.owner)
    assert len(events) == 1
    assert events[0]["kind"] == "payout_identity_ambiguous"


@native_postgres
def test_ambiguous_anchor_groups_can_share_a_raw_provider_key_without_collapsing(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    payment = at + timedelta(days=2)
    observation.save([
        dividend_row("10", payment), dividend_row("12", payment + timedelta(days=1)),
        dividend_row("10", payment, regularity="Annual"),
        dividend_row("14", payment + timedelta(days=2), regularity="Annual"),
    ], at)
    payouts = observation.payouts()
    assert len(payouts) == 4
    assert sorted(row["amount"] for row in payouts) == list(map(Decimal, ("10", "10", "12", "14")))
    assert len({row["provider_key"] for row in payouts}) == 3
    assert all(row["identity_status"] == "ambiguous" for row in payouts)
    events = payment_events(WorkspaceStore(database), observation.owner)
    assert len(events) == 2
    assert all(row["kind"] == "payout_identity_ambiguous" for row in events)
    assert len({row["source"]["anchor_key"] for row in events}) == 2


@native_postgres
def test_existing_scheduled_payouts_cannot_starve_the_next_unprojected_distribution(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    store = WorkspaceStore(database)
    payment = at + timedelta(days=2)
    observation.save([
        dividend_row("10", payment, recordDate=(
            datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        ).isoformat()) for index in range(201)
    ], at)
    first = store.events(observation.owner, category="payments", limit=200)
    assert len(first["items"]) == 200
    assert all(row["kind"] == "payout_calendar" for row in first["items"])
    revisions = {row["id"]: row["revision"] for row in first["items"]}
    store.mark_all_events_read(observation.owner, through_revision=first["read_all_before"],
                               category="payments")
    following = store.events(observation.owner, category="payments", unread_only=True)
    assert len(following["items"]) == 1
    assert following["items"][0]["id"] not in revisions
    assert following["items"][0]["kind"] == "payout_calendar"
    with store._transaction(observation.owner) as cur:
        cur.execute("SELECT count(*) AS total FROM workspace_events WHERE user_id = %s "
                    "AND kind = 'payout_calendar'", (observation.owner,))
        assert cur.fetchone()["total"] == 201
        cur.execute("SELECT id, revision, read_at FROM workspace_events "
                    "WHERE user_id = %s AND id = ANY (%s)", (observation.owner, list(revisions)))
        retained = cur.fetchall()
        assert {row["id"]: row["revision"] for row in retained} == revisions
        assert all(row["read_at"] is not None for row in retained)


def insert_legacy_payout(
    store: WorkspaceStore, ident: UUID, document: EvidenceDocument, at: datetime,
) -> dict[str, Any]:
    with store._transaction(ident) as cur:
        cur.execute("SELECT * FROM payout_events WHERE instrument_uid = %s AND provider_key = %s "
                    "ORDER BY id DESC LIMIT 1", (document.subject_uid, document.provider_key))
        payout = cur.fetchone()
        identity = [document.subject_uid, "dividend", document.provider_key]
        store._insert_event(
            cur, ident, identity=identity, category="payments", kind="payout_calendar",
            title="Объявлены дивиденды", target="income", occurred_at=at,
            source={"type": "payout", "id": str(payout["id"]),
                    "instrument_uid": payout["instrument_uid"],
                    "expected_at": payout["expected_at"],
                    "amount_per_security": str(payout["amount"]), "currency": payout["currency"],
                    "status": payout["status"], "url": document.source_url},
        )
    return store.get_event(ident, event_id("payout_calendar", identity))


@native_postgres
def test_new_ambiguity_retires_consolidated_alerts_and_preserves_delivery_receipts(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, at = workspace_database[0], datetime.now(UTC) - timedelta(hours=1)
    observation = payout_observation(database, at)
    store = WorkspaceStore(database)
    service, transport, _ = notification_service(database)
    ident, payment = observation.owner, at + timedelta(days=2)
    preferences = default_preferences()
    preferences["digest_frequency"] = "off"
    preferences["quiet_hours"]["enabled"] = False
    store.save_preferences(ident, preferences, expected_version=0)
    with store._transaction(ident) as cur:
        channel = service._insert_channel(
            cur, ident, kind="email", destination={"email": "payout-test@example.org"},
            label="Synthetic payout test", status="active", now=at,
        )
    rows = [dividend_row("10", payment), dividend_row("12", payment + timedelta(days=1))]
    legacy = []
    for minute, raw in enumerate(rows):
        received = at + timedelta(minutes=minute)
        document, = observation.save([raw], received)
        event = insert_legacy_payout(store, ident, document, received)
        legacy.append(event)
        with store._transaction(ident) as cur:
            service._queue_event(cur, ident, channel, event, preferences, received)
            if minute == 0:
                cur.execute("UPDATE notification_outbox SET status = 'accepted', accepted_at = %s "
                            "WHERE user_id = %s AND message_key = %s",
                            (received, ident, f"event:{event['id']}:{event['revision']}"))
        if minute == 0:
            store.mark_events_read(ident, [event["id"]])
    prior = payment_events(store, ident)
    assert len(prior) == 1
    assert prior[0]["id"] == legacy[1]["id"]
    retained = {event["id"]: store.get_event(ident, event["id"]) for event in legacy}
    assert retained[legacy[0]["id"]]["source"]["superseded_by"] == legacy[1]["id"]
    with store._transaction(ident) as cur:
        cur.execute("SELECT id, status, accepted_at FROM notification_outbox WHERE user_id = %s",
                    (ident,))
        receipts = {row["id"]: dict(row) for row in cur.fetchall()}
    observation.save(rows, at + timedelta(minutes=2))
    events = payment_events(store, ident)
    assert len(events) == 1
    warning = events[0]
    assert warning["kind"] == "payout_identity_ambiguous"
    assert store.events_summary(ident)["categories"]["payments"] == 1
    for old in retained.values():
        current = store.get_event(ident, old["id"])
        assert current["revision"] == old["revision"]
        assert current["read_at"] == old["read_at"]
        assert current["source"]["id"] == old["source"]["id"]
        assert current["source"]["superseded_by"] == warning["id"]
        assert current["source"]["supersession_reason"] == "identity_ambiguous"
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(ident) is False
    transport.send_email.assert_not_called()
    with store._transaction(ident) as cur:
        cur.execute("SELECT id, status, accepted_at FROM notification_outbox WHERE user_id = %s",
                    (ident,))
        after = {row["id"]: dict(row) for row in cur.fetchall()}
        assert after.keys() == receipts.keys()
        for key, receipt in receipts.items():
            if receipt["status"] == "accepted":
                assert after[key] == receipt
            else:
                assert after[key]["status"] == "cancelled"
        cur.execute("SELECT event_id, event_revision FROM notification_outbox_events "
                    "WHERE user_id = %s", (ident,))
        assert {(row["event_id"], row["event_revision"]) for row in cur.fetchall()} == {
            (event["id"], event["revision"]) for event in legacy
        }
        service._queue_event(cur, ident, channel, warning, preferences, datetime.now(UTC))
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(ident) is True
    transport.send_email.assert_called_once()
    store.mark_events_read(ident, [warning["id"]])
    observation.save([dividend_row("11", payment), rows[1]], at + timedelta(minutes=3))
    current_warning, = payment_events(store, ident)
    assert current_warning["id"] == warning["id"]
    assert current_warning["revision"] == warning["revision"]
    assert current_warning["read_at"] is not None
    with store._transaction(ident) as cur:
        service._queue_event(cur, ident, channel, current_warning, preferences, datetime.now(UTC))
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(ident) is False
    transport.send_email.assert_called_once()
