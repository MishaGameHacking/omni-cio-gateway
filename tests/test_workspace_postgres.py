"""Workspace contracts exercised with an isolated schema and a non-bypass role."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest
from cryptography.fernet import Fernet
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database
from omnicio.notifications import (
    DeliveryResult,
    NotificationConfig,
    NotificationConflict,
    NotificationRateLimited,
    NotificationService,
    NotificationTransport,
    push_public_key,
    vapid_authorization,
)
from omnicio.portfolio_store import (
    PortfolioStore,
    SettingsVersionConflict,
    _save_operation_observation,
)
from omnicio.tbank import TBankMoney, TBankOperation
from omnicio.workspace import cashflow_summary, default_preferences
from omnicio.workspace_store import WorkspaceNotFound, WorkspaceStore

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def workspace_database() -> Iterator[tuple[Database, str, str]]:
    config = conninfo_to_dict(DATABASE_URL)
    assert config.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert config.get("dbname", "").endswith("_test")
    name = "workspace_test_" + secrets.token_hex(6)
    role = name + "_role"
    password = secrets.token_urlsafe(32)
    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(name)))
        for path in sorted((ROOT / "migrations").glob("*.sql")):
            admin.execute(path.read_text(encoding="utf-8"))
        # The unreleased additive migration has a deterministic retry contract.
        admin.execute((ROOT / "migrations" / "0014_workspace.sql").read_text(encoding="utf-8"))
        admin.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB "
                "NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(
                sql.Identifier(role),
                sql.Literal(password),
            )
        )
        admin.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(name),
                sql.Identifier(role),
            )
        )
        admin.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(
                sql.Identifier(name), sql.Identifier(role)
            )
        )
        admin.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(
                sql.Identifier(name),
                sql.Identifier(role),
            )
        )
    config.update(user=role, password=password, options=f"-c search_path={name},public")
    database = Database(make_conninfo(**config))
    database.open()
    try:
        yield database, DATABASE_URL, name
    finally:
        database.close()
        with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def user(database: Database, *, account: bool = False) -> UUID:
    ident = uuid4()
    with database.pool.connection() as conn:
        conn.execute("INSERT INTO users (id) VALUES (%s)", (ident,))
        if account:
            conn.execute(
                "INSERT INTO tbank_connection (user_id, environment, account_id, account_name, "
                "token_ciphertext) VALUES (%s, 'prod', %s, 'Test account', %s)",
                (ident, str(ident), b"test-only-encrypted-placeholder"),
            )
    return ident


def goal_document(**changes: Any) -> dict[str, Any]:
    return {
        "title": "Цель пользователя",
        "kind": "capital",
        "target_amount_rub": "100000",
        "start_date": "2026-01-01",
        "target_date": None,
        "progress_source": "manual",
        "allocation_percent": None,
        "manual_amount_rub": "15000",
        "status": "active",
        **changes,
    }


def insert_notification_event(
    store: WorkspaceStore, owner: UUID, number: int, *, at: datetime | None = None,
    source: dict[str, Any] | None = None,
) -> str:
    with store._transaction(owner) as cur:
        store._insert_event(
            cur, owner, identity=number, category="system", kind="test_event",
            title=f"Confirmed event {number}", occurred_at=at or datetime.now(UTC),
            target="settings", source=source or {"type": "test", "number": number},
        )
    return hashlib.sha256(json.dumps(
        ["test_event", number], sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()


def notification_service(database: Database) -> tuple[NotificationService, Mock, dict[str, Any]]:
    private = base64.urlsafe_b64encode(bytes([1]) * 32).decode().rstrip("=")
    config = NotificationConfig(
        crypto_key=Fernet.generate_key().decode(), enabled=True, email_enabled=True,
        vapid_private_key=private, vapid_subject="mailto:operator@example.org",
        smtp_host="smtp.example.org", smtp_sender="operator@example.org",
    )
    transport = Mock(spec=NotificationTransport)
    transport.send_push.return_value = DeliveryResult("accepted", "push_provider_accepted")
    transport.send_email.return_value = DeliveryResult("accepted", "email_provider_accepted")
    service = NotificationService(database, config, legal_versions={"terms": "test"},
                                  transport=transport)
    subscription = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/" + secrets.token_urlsafe(20),
        "keys": {"p256dh": push_public_key(private),
                 "auth": base64.urlsafe_b64encode(bytes([2]) * 16).decode().rstrip("=")},
    }
    return service, transport, subscription


def notification_session(database: Database, owner: UUID, *, name: str = "primary") -> bytes:
    digest = hashlib.sha256(f"notification-fixture:{owner}:{name}".encode()).digest()
    with database.pool.connection() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token_digest, client_ip_hash, expires_at) "
            "VALUES (%s, %s, %s, now() + interval '400 days') "
            "ON CONFLICT (token_digest) DO NOTHING", (owner, digest, b"i" * 32),
        )
    return digest


def subscribe_device(
    service: NotificationService, owner: UUID, subscription: dict[str, Any],
) -> dict[str, Any]:
    return service.subscribe_push(
        owner, subscription, session_digest=notification_session(service.database, owner),
    )


def last_delivery_payload(service: NotificationService, owner: UUID) -> dict[str, Any]:
    """Assert financial/event membership in custody, not in a lock-screen payload."""
    with service.workspace._transaction(owner) as cur:
        cur.execute(
            "SELECT payload_ciphertext FROM notification_outbox WHERE user_id = %s "
            "AND status = 'accepted' ORDER BY accepted_at DESC, created_at DESC LIMIT 1",
            (owner,),
        )
        return service._open(cur.fetchone()["payload_ciphertext"])


def test_push_binding_is_session_owned_idempotent_and_respects_explicit_opt_out(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database), user(database)
    service, _, subscription = notification_service(database)
    digest = notification_session(database, owner)
    foreign_digest = notification_session(database, other)
    with pytest.raises(PermissionError, match="session_expired"):
        service.subscribe_push(owner, subscription, session_digest=foreign_digest)
    first = service.subscribe_push(owner, subscription, session_digest=digest)
    assert first["status"] == "active"
    assert first["current_session"] is True
    assert service.subscribe_push(owner, subscription, session_digest=digest,
                                  intent="sync") == first
    status = service.status(owner, session_digest=digest)["channels"][0]
    assert status["binding_id"] == UUID(first["binding_id"])
    assert status["current_session"] is True
    assert "session_id" not in status
    assert "session_id" not in service.status(owner)["channels"][0]
    renewed = notification_session(database, owner, name="renewed")
    rebound = service.subscribe_push(owner, subscription, session_digest=renewed, intent="sync")
    assert rebound["id"] == first["id"]
    assert rebound["binding_id"] != first["binding_id"]
    assert not service.status(owner, session_digest=digest)["channels"][0]["current_session"]
    service.revoke_channel(owner, UUID(first["id"]))
    revoked = service.subscribe_push(owner, subscription, session_digest=renewed, intent="sync")
    assert revoked["status"] == "revoked"
    assert revoked["binding_id"] == rebound["binding_id"]
    enabled = service.subscribe_push(owner, subscription, session_digest=renewed, intent="enable")
    assert enabled["status"] == "active"
    assert enabled["binding_id"] != rebound["binding_id"]


@pytest.mark.parametrize("authority_alias", [False, True])
def test_competing_push_owners_cannot_share_an_active_endpoint_under_rls(
    workspace_database: tuple[Database, str, str], authority_alias: bool,
) -> None:
    database = workspace_database[0]
    owners = [user(database), user(database)]
    service, _, subscription = notification_service(database)
    digests = {owner: notification_session(database, owner) for owner in owners}

    def bind(owner: UUID) -> tuple[UUID, str]:
        selected = subscription
        if authority_alias and owner == owners[1]:
            selected = {**subscription, "endpoint": subscription["endpoint"].replace(
                "fcm.googleapis.com", "FCM.GOOGLEAPIS.COM:443",
            )}
        try:
            result = service.subscribe_push(owner, selected, session_digest=digests[owner])
        except NotificationConflict as exc:
            return owner, str(exc)
        return owner, result["status"]

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = dict(workers.map(bind, owners))
    assert sorted(outcomes.values()) == ["active", "notification_device_conflict"]
    winner = next(owner for owner, value in outcomes.items() if value == "active")
    loser = next(owner for owner in owners if owner != winner)
    assert service.status(loser)["channels"] == []
    old = service.status(winner)["channels"][0]
    service.revoke_channel(winner, old["id"])
    result = service.subscribe_push(loser, subscription, session_digest=digests[loser])
    assert result["status"] == "active"
    assert service.status(winner)["channels"][0]["status"] == "revoked"
    # The FK itself also rejects a valid session UUID belonging to another owner.
    with database.pool.connection() as conn:
        foreign_session = conn.execute("SELECT id FROM sessions WHERE token_digest = %s",
                                       (digests[winner],)).fetchone()["id"]
    with service.workspace._transaction(loser) as cur, \
            pytest.raises(psycopg.errors.ForeignKeyViolation):
        cur.execute("UPDATE notification_channels SET session_id = %s WHERE user_id = %s",
                    (foreign_session, loser))


@pytest.mark.parametrize("ending", ["logout", "expiry", "pruned"])
def test_session_end_cancels_pending_push_and_preserves_receipt_history(
    workspace_database: tuple[Database, str, str], ending: str,
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    digest = notification_session(database, owner)
    first = service.subscribe_push(owner, subscription, session_digest=digest)
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
    insert_notification_event(service.workspace, owner, 2)
    service.queue_events(owner)
    with database.pool.connection() as conn:
        if ending == "logout":
            database.revoke_session(digest)
        elif ending == "expiry":
            conn.execute("UPDATE sessions SET created_at = now() - interval '2 days', "
                         "expires_at = now() - interval '1 second' "
                         "WHERE token_digest = %s", (digest,))
        else:
            conn.execute("DELETE FROM sessions WHERE token_digest = %s", (digest,))
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner)
    state = service.status(owner)
    assert state["channels"][0]["id"] == UUID(first["id"])
    assert state["channels"][0]["status"] == "expired"
    assert {row["status"] for row in state["deliveries"]} == {"accepted", "cancelled"}
    assert transport.send_push.call_count == 1
    insert_notification_event(service.workspace, owner, 3)
    service.queue_events(owner)
    assert len(service.status(owner)["deliveries"]) == 2


@pytest.mark.parametrize("provider_result", [
    DeliveryResult("failed", "push_subscription_expired", expired=True),
    DeliveryResult("queued", "push_rate_limited", 60),
])
def test_old_push_result_cannot_expire_or_retry_a_rebound_device(
    workspace_database: tuple[Database, str, str], provider_result: DeliveryResult,
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    digest = notification_session(database, owner)
    first = service.subscribe_push(owner, subscription, session_digest=digest)
    insert_notification_event(service.workspace, owner, 1)
    insert_notification_event(service.workspace, owner, 2)
    service.queue_events(owner)
    changed = {**subscription, "keys": {**subscription["keys"],
               "auth": base64.urlsafe_b64encode(b"n" * 16).decode().rstrip("=")}}
    rebound: dict[str, Any] = {}

    def returned(*args: Any, **kwargs: Any) -> DeliveryResult:
        rebound.update(service.subscribe_push(owner, changed, session_digest=digest, intent="sync"))
        return provider_result

    transport.send_push.side_effect = returned
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
        assert not service.deliver_one(owner, now=datetime.now(UTC) + timedelta(minutes=2))
    assert rebound["id"] == first["id"]
    assert rebound["binding_id"] != first["binding_id"]
    current = service.status(owner)["channels"][0]
    assert current["status"] == "active"
    assert str(current["binding_id"]) == rebound["binding_id"]
    assert all(row["status"] in {"failed", "cancelled"}
               for row in service.status(owner)["deliveries"])
    assert transport.send_push.call_count == 1
    payload = transport.send_push.call_args.args[1]
    assert payload["binding_id"] == first["binding_id"]
    assert set(payload) == {"title", "body", "url", "tag", "binding_id", "kind"}


def test_explicit_push_test_is_current_device_only_rate_limited_and_immediate(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database), user(database)
    service, transport, subscription = notification_service(database)
    digest = notification_session(database, owner)
    different_device = notification_session(database, owner, name="different-browser")
    foreign = notification_session(database, other)
    channel = UUID(service.subscribe_push(owner, subscription, session_digest=digest)["id"])
    with pytest.raises(WorkspaceNotFound):
        service.test_push(owner, channel, session_digest=different_device)
    with pytest.raises(WorkspaceNotFound):
        service.test_push(other, channel, session_digest=foreign)
    now = datetime.now(UTC)
    prefs = default_preferences()
    prefs["quiet_hours"].update(enabled=True, timezone="UTC", start=now.strftime("%H:%M"),
                                end=(now + timedelta(hours=1)).strftime("%H:%M"))
    service.workspace.save_preferences(owner, prefs, expected_version=0)

    def queue(_: int) -> str:
        try:
            return service.test_push(owner, channel, session_digest=digest)["status"]
        except NotificationRateLimited as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(queue, [0, 1])) == ["notification_test_rate_limited", "queued"]
    created = service.status(owner)["deliveries"][0]["created_at"]
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=created + timedelta(minutes=2))
    assert transport.send_push.call_count == 1
    assert transport.send_push.call_args.kwargs["ttl_seconds"] == 180
    assert transport.send_push.call_args.args[1]["kind"] == "test"
    assert service.status(owner)["deliveries"][0]["status"] == "accepted"
    service.revoke_channel(owner, channel)
    with pytest.raises(NotificationConflict, match="notification_channel_inactive"):
        service.test_push(owner, channel, session_digest=digest)


def test_push_test_expires_after_five_minutes_without_a_provider_request(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    digest = notification_session(database, owner)
    channel = UUID(service.subscribe_push(owner, subscription, session_digest=digest)["id"])
    service.test_push(owner, channel, session_digest=digest)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=datetime.now(UTC) + timedelta(minutes=5))
    assert service.status(owner)["deliveries"][0]["last_error"] == "delivery_expired"
    transport.send_push.assert_not_called()


def test_disabled_email_retains_history_and_cancels_queue_without_new_messages(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    with patch("omnicio.notifications.secrets.randbelow", return_value=123456):
        requested = service.request_email_verification(owner, "person@example.org")
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
    service.verify_email(owner, UUID(requested["id"]), "123456")
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    service.config = replace(service.config, email_enabled=False)
    service.queue_events(owner)
    insert_notification_event(service.workspace, owner, 2)
    service.queue_events(owner)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
        assert service.deliver_one(owner)
        assert not service.deliver_one(owner)
    state = service.status(owner)
    assert not state["email_configured"]
    email = [row for row in state["deliveries"] if row["channel"]["kind"] == "email"]
    assert {row["status"] for row in email} == {"accepted", "cancelled"}
    assert len(email) == 2
    assert transport.send_email.call_count == 1
    assert transport.send_push.call_count == 2


def test_push_status_is_bounded_but_sync_finds_an_old_explicit_opt_out(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, _, subscription = notification_service(database)
    digest = notification_session(database, owner)
    first = service.subscribe_push(owner, subscription, session_digest=digest)
    service.revoke_channel(owner, UUID(first["id"]))
    for number in range(34):
        another = {**subscription, "endpoint": subscription["endpoint"] + str(number)}
        item = service.subscribe_push(owner, another, session_digest=digest)
        service.revoke_channel(owner, UUID(item["id"]))
    active = service.subscribe_push(owner, {**subscription, "endpoint": subscription["endpoint"]
                                           + "active"}, session_digest=digest)
    channels = service.status(owner)["channels"]
    assert len(channels) == 32
    assert channels[0]["id"] == UUID(active["id"])
    assert all(str(channel["id"]) != first["id"] for channel in channels)
    assert service.subscribe_push(owner, subscription, session_digest=digest,
                                  intent="sync")["status"] == "revoked"


@pytest.mark.parametrize("identity_change", ["key", "subject"])
def test_vapid_jwt_is_shared_across_workers_restart_and_bound_to_server_identity(
    workspace_database: tuple[Database, str, str], identity_change: str,
) -> None:
    database = workspace_database[0]
    original, _, _ = notification_service(database)
    config = original.config
    with database.pool.connection() as conn:
        conn.execute("DELETE FROM notification_push_authorizations")
    services = [NotificationService(database, config, legal_versions={}) for _ in range(2)]
    assert all(service.transport.database is database for service in services)
    endpoint = "https://web.push.apple.com/synthetic-device"
    # The database clock, not either worker's supplied wall time, owns JWT validity.
    arbitrary_clock = datetime(2000, 1, 1, tzinfo=UTC)

    def issue(number: int) -> str | None:
        return services[number % 2].transport._authorization(endpoint, arbitrary_clock)

    with patch("omnicio.notifications.vapid_authorization", wraps=vapid_authorization) as sign:
        with ThreadPoolExecutor(max_workers=8) as workers:
            tokens = list(workers.map(issue, range(24)))
        assert len(set(tokens)) == 1
        assert tokens[0] is not None
        assert sign.call_count == 1
        restarted = NotificationService(database, config, legal_versions={})
        assert restarted.transport._authorization(endpoint, arbitrary_clock) == tokens[0]
        assert sign.call_count == 1
    with database.pool.connection() as conn:
        stored = conn.execute("SELECT * FROM notification_push_authorizations").fetchone()
        assert stored["origin"] == "https://web.push.apple.com"
        assert "user_id" not in stored
        assert tokens[0].encode() not in bytes(stored["authorization_ciphertext"])
        assert stored["issued_at"] < stored["expires_at"] <= (
            stored["issued_at"] + timedelta(hours=2)
        )
        assert stored["issued_at"] > datetime.now(UTC) - timedelta(minutes=1)
    changed = (replace(config, vapid_private_key=base64.urlsafe_b64encode(b"k" * 32).decode())
               if identity_change == "key" else replace(config, vapid_subject="https://example.org"))
    different_identity = NotificationService(database, changed, legal_versions={})
    assert different_identity.transport._authorization(endpoint, arbitrary_clock) != tokens[0]
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS total FROM notification_push_authorizations"
                            ).fetchone()["total"] == 2
        conn.execute("UPDATE notification_push_authorizations SET "
                     "issued_at = now() - interval '2 hours', "
                     "expires_at = now() - interval '1 hour'")
    renewed = services[0].transport._authorization(endpoint, arbitrary_clock)
    assert renewed is not None
    assert renewed != tokens[0]
    jwt = renewed.split("t=", 1)[1].split(",", 1)[0]
    claims = jwt.split(".")[1]
    payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
    assert datetime.now(UTC).timestamp() < payload["exp"] <= (
        datetime.now(UTC) + timedelta(hours=2)
    ).timestamp()


def test_shared_vapid_origin_bound_recovers_after_expiry_without_token_churn(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    original, _, _ = notification_service(database)
    service = NotificationService(database, original.config, legal_versions={})
    now = datetime.now(UTC)
    with database.pool.connection() as conn:
        conn.execute("DELETE FROM notification_push_authorizations")
    first = service.transport._authorization("https://node-0.push.apple.com/path", now)
    for number in range(1, 128):
        assert service.transport._authorization(f"https://node-{number}.push.apple.com/path", now)
    assert service.transport._authorization("https://extra.push.apple.com/path", now) is None
    assert service.transport._authorization("https://node-0.push.apple.com/other", now) == first
    with database.pool.connection() as conn:
        conn.execute("UPDATE notification_push_authorizations SET "
                     "issued_at = now() - interval '1 hour'")
    assert service.transport._authorization("https://extra.push.apple.com/path", now)
    with database.pool.connection() as conn:
        assert conn.execute("SELECT count(*) AS total FROM notification_push_authorizations"
                            ).fetchone()["total"] == 1


def test_corrupted_shared_authorization_stays_queued_without_unknown_provider_outcome(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    original, _, subscription = notification_service(database)
    service = NotificationService(database, original.config, legal_versions={})
    owner = user(database)
    digest = notification_session(database, owner)
    with database.pool.connection() as conn:
        conn.execute("DELETE FROM notification_push_authorizations")
    assert service.transport._authorization(subscription["endpoint"], datetime.now(UTC))
    with database.pool.connection() as conn:
        conn.execute("UPDATE notification_push_authorizations SET authorization_ciphertext = %s",
                     (b"private-corrupted-ciphertext-marker",))
    channel = UUID(service.subscribe_push(owner, subscription, session_digest=digest)["id"])
    service.test_push(owner, channel, session_digest=digest)
    with patch.object(database, "has_legal_versions", return_value=True), \
            patch("omnicio.notifications._public_address") as dns, \
            patch("omnicio.notifications._PinnedHTTPSConnection") as connect:
        assert service.deliver_one(owner)
    delivery = service.status(owner)["deliveries"][0]
    assert delivery["status"] == "queued"
    assert delivery["last_error"] == "push_authorization_unavailable"
    assert delivery["attempts"] == 1
    assert delivery["error"]["retryable"]
    assert "private-corrupted-ciphertext-marker" not in json.dumps(delivery, default=str)
    dns.assert_not_called()
    connect.assert_not_called()


def test_disabling_legacy_email_frees_channel_capacity_without_erasing_history(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    now = datetime.now(UTC)
    with service.workspace._transaction(owner) as cur:
        for number in range(8):
            channel = service._insert_channel(
                cur, owner, kind="email", destination={"email": f"old-{number}@example.org"},
                label="Legacy email", status="pending", now=now, code="123456",
            )
            service._enqueue(cur, owner, channel, "old-verification", "verification",
                             {"title": "Legacy code", "body": "Synthetic"}, now)
    service.config = replace(service.config, email_enabled=False)
    result = subscribe_device(service, owner, subscription)
    assert result["status"] == "active"
    status = service.status(owner)
    assert len(status["channels"]) == 9
    assert all(channel["status"] == "expired" for channel in status["channels"]
               if channel["kind"] == "email")
    assert len(status["deliveries"]) == 8
    assert all(row["status"] == "cancelled" for row in status["deliveries"])
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT verification_digest FROM notification_channels WHERE user_id = %s "
                    "AND kind = 'email'", (owner,))
        assert all(row["verification_digest"] is None for row in cur.fetchall())
    transport.send_email.assert_not_called()


def midnight_notification_preferences(timezone: str = "Europe/Moscow") -> dict[str, Any]:
    """Keep receipt/retry fixtures independent of the new configurable default schedule."""
    preferences = default_preferences()
    preferences.update(digest_time="00:00", digest_timezone=timezone)
    preferences["quiet_hours"]["timezone"] = timezone
    return preferences


def test_event_pagination_search_and_read_all_cover_more_than_fifty(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner, other = user(database), user(database)
    at = datetime.now(UTC) - timedelta(hours=1)
    expected = {insert_notification_event(store, owner, number, at=at) for number in range(115)}
    first = store.events(owner)
    assert len(first["items"]) == 50
    assert first["unread_count"] == 115
    seen = {item["id"] for item in first["items"]}
    cursor = first["next_cursor"]
    while cursor:
        page = store.events(owner, cursor=cursor)
        assert not seen.intersection(item["id"] for item in page["items"])
        seen.update(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert seen == expected
    assert store.events(owner, query="event 114")["items"][0]["title"] == "Confirmed event 114"
    assert store.events(other)["items"] == []
    foreign_event_id = next(iter(expected))
    with pytest.raises(WorkspaceNotFound):
        store.get_event(other, foreign_event_id)
    # New data with an older occurrence date is still beyond the revision cutoff.
    added = insert_notification_event(store, owner, 116, at=at - timedelta(days=1))
    refreshed = store.mark_all_events_read(owner, through_revision=first["read_all_before"])
    assert refreshed["unread_count"] == 1
    assert store.get_event(owner, added)["read_at"] is None
    assert store.events(owner, unread_only=True)["items"][0]["id"] == added
    with pytest.raises(ValueError):
        store.mark_all_events_read(owner, through_revision=2**62)


def test_concurrent_event_correction_survives_old_read_all_cutoff_and_preserves_details(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    store = WorkspaceStore(database)
    source = {"type": "payout", "instrument_uid": "instrument-real-contract",
              "amount_per_security": "12.34", "currency": "RUB",
              "expected_at": "2026-12-01T00:00:00+00:00", "url": "https://example.org/source"}
    ident = insert_notification_event(store, owner, 1, source=source)
    before = store.events(owner)
    with ThreadPoolExecutor(max_workers=2) as workers:
        write = workers.submit(insert_notification_event, store, owner, 1,
                               source={**source, "amount_per_security": "13.45"})
        read = workers.submit(store.mark_all_events_read, owner,
                              through_revision=before["read_all_before"])
        write.result()
        read.result()
    event = store.get_event(owner, ident)
    assert event["read_at"] is None
    assert event["revision"] > before["read_all_before"]
    assert event["source"]["amount_per_security"] == "13.45"
    assert event["source"]["expected_at"] == source["expected_at"]
    assert event["destination"] == {"view": "asset", "uid": "instrument-real-contract"}


def test_notification_queue_deduplicates_and_retries_only_definite_failure(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    channel = subscribe_device(service, owner, subscription)
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    service.queue_events(owner)
    assert len(service.status(owner)["deliveries"]) == 1
    now = datetime.now(UTC) + timedelta(seconds=1)
    transport.send_push.side_effect = [DeliveryResult("queued", "push_rate_limited", 120),
                                       DeliveryResult("accepted", "push_provider_accepted")]
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=now)
        assert not service.deliver_one(owner, now=now + timedelta(seconds=60))
        assert service.deliver_one(owner, now=now + timedelta(seconds=121))
        assert not service.deliver_one(owner, now=now + timedelta(seconds=122))
    assert transport.send_push.call_count == 2
    assert transport.send_push.call_args_list[0].args == transport.send_push.call_args_list[1].args
    state = service.status(owner)["deliveries"][0]
    assert state["status"] == "accepted"
    assert state["attempts"] == 2
    assert "destination_ciphertext" not in service.status(owner)["channels"][0]
    assert "payload_ciphertext" not in state
    assert state["channel_id"] == UUID(channel["id"])


@pytest.mark.parametrize("replacement_operator", [False, True])
def test_pending_operational_alert_is_cancelled_when_operator_authority_changes(
    workspace_database: tuple[Database, str, str], replacement_operator: bool,
) -> None:
    database = workspace_database[0]
    operator, ordinary = user(database), user(database)
    service, transport, subscription = notification_service(database)
    service.config = replace(service.config, operator_user_id=operator)
    subscribe_device(service, operator, subscription)
    service.queue_operator_alert(ordinary, "health-test", "Operational test")
    assert service.status(ordinary)["deliveries"] == []
    service.queue_operator_alert(operator, "health-test", "Operational test")
    assert service.status(operator)["deliveries"][0]["status"] == "queued"
    # Recreate the worker as after a restart with operator identity disabled or changed.
    restarted = NotificationService(
        database,
        replace(service.config, operator_user_id=ordinary if replacement_operator else None),
        legal_versions=service.legal_versions, transport=transport,
    )
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not restarted.deliver_one(operator, now=datetime.now(UTC) + timedelta(days=1))
    assert restarted.status(operator)["deliveries"][0]["status"] == "cancelled"
    transport.send_push.assert_not_called()
    transport.send_email.assert_not_called()


def test_notification_ambiguous_result_is_not_retried_and_revocation_is_tenant_scoped(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database), user(database)
    service, transport, subscription = notification_service(database)
    channel = UUID(subscribe_device(service, owner, subscription)["id"])
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    transport.send_push.return_value = DeliveryResult("uncertain", "push_result_unknown")
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
        assert not service.deliver_one(owner, now=datetime.now(UTC) + timedelta(days=1))
    assert service.status(owner)["deliveries"][0]["status"] == "uncertain"
    assert transport.send_push.call_count == 1
    with pytest.raises(WorkspaceNotFound):
        service.revoke_channel(other, channel)
    insert_notification_event(service.workspace, owner, 2)
    service.queue_events(owner)
    service.revoke_channel(owner, channel)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner)
    assert {row["status"] for row in service.status(owner)["deliveries"]} == {
        "cancelled", "uncertain",
    }


def test_notification_claim_concurrency_and_crash_never_duplicate_delivery(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    with patch.object(database, "has_legal_versions", return_value=True):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(service.deliver_one, [owner, owner]))
        assert sorted(results) == [False, True]
        assert transport.send_push.call_count == 1
        insert_notification_event(service.workspace, owner, 2)
        service.queue_events(owner)
        now = datetime.now(UTC)
        assert service._claim(owner, now) is not None
        # A process can disappear after the request was sent but before its
        # acknowledgment was persisted. A lease timeout cannot justify resend.
        assert not service.deliver_one(owner, now=now + timedelta(minutes=3))
    assert transport.send_push.call_count == 1
    assert {row["status"] for row in service.status(owner)["deliveries"]} == {
        "accepted", "uncertain",
    }


def test_queued_delivery_rechecks_read_state_preferences_and_retry_budget(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    first = insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    service.workspace.mark_events_read(owner, [first])
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner)
    transport.send_push.assert_not_called()
    second = insert_notification_event(service.workspace, owner, 2)
    service.queue_events(owner)
    prefs = midnight_notification_preferences()
    prefs["digest_frequency"] = "daily"
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner)
    transport.send_push.assert_not_called()
    prefs["digest_frequency"] = "off"
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    service.queue_events(owner)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner)
    assert last_delivery_payload(service, owner)["event_id"] == second
    insert_notification_event(service.workspace, owner, 3)
    service.queue_events(owner)
    transport.send_push.return_value = DeliveryResult("queued", "push_rate_limited", 120)
    with patch.object(database, "has_legal_versions", return_value=True):
        now = datetime.now(UTC)
        for attempt in range(6):
            assert service.deliver_one(owner, now=now + timedelta(hours=attempt))
        assert not service.deliver_one(owner, now=now + timedelta(hours=7))
    assert transport.send_push.call_count == 7
    assert next(row for row in service.status(owner)["deliveries"]
                if row["attempts"] == 6)["status"] == "failed"


def test_email_verification_is_encrypted_expiring_rate_limited_and_attempt_bounded(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, _ = notification_service(database)
    with patch("omnicio.notifications.secrets.randbelow", return_value=123456):
        result = service.request_email_verification(owner, "person@example.org")
    assert "code" not in result
    channel = UUID(result["id"])
    with pytest.raises(ValueError, match="rate_limited"):
        service.request_email_verification(owner, "person@example.org")
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT destination_ciphertext, verification_digest "
                    "FROM notification_channels WHERE user_id = %s", (owner,))
        stored = cur.fetchone()
        assert b"person@example.org" not in bytes(stored["destination_ciphertext"])
        assert b"123456" not in bytes(stored["verification_digest"])
    for _ in range(5):
        with pytest.raises(ValueError, match="verification_invalid"):
            service.verify_email(owner, channel, "000000")
    with pytest.raises(ValueError, match="verification_invalid"):
        service.verify_email(owner, channel, "123456")
    transport.send_email.assert_not_called()


def test_email_code_is_bound_to_channel_expires_and_can_be_reissued(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, _ = notification_service(database)
    with patch("omnicio.notifications.secrets.randbelow", return_value=123456):
        first = UUID(service.request_email_verification(owner, "first@example.org")["id"])
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_outbox SET created_at = now() - interval '3 minutes' "
                    "WHERE user_id = %s", (owner,))
        cur.execute("SELECT verification_digest FROM notification_channels "
                    "WHERE user_id = %s AND id = %s", (owner, first))
        first_digest = cur.fetchone()["verification_digest"]
    with patch("omnicio.notifications.secrets.randbelow", return_value=654321):
        second = UUID(service.request_email_verification(owner, "second@example.org")["id"])
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verification_digest = %s "
                    "WHERE user_id = %s AND id = %s", (first_digest, owner, second))
    with pytest.raises(ValueError, match="verification_invalid"):
        service.verify_email(owner, second, "123456")
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verification_expires_at = "
                    "now() - interval '1 second' WHERE user_id = %s AND id = %s", (owner, first))
    with pytest.raises(ValueError, match="verification_invalid"):
        service.verify_email(owner, first, "123456")
    assert next(row for row in service.status(owner)["channels"]
                if row["id"] == first)["status"] == "expired"
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_outbox SET created_at = now() - interval '3 minutes' "
                    "WHERE user_id = %s", (owner,))
    with patch("omnicio.notifications.secrets.randbelow", return_value=345678):
        reissued = service.request_email_verification(owner, "first@example.org")
    assert reissued["id"] == str(first)
    with pytest.raises(ValueError, match="verification_invalid"):
        service.verify_email(owner, first, "123456")
    assert service.verify_email(owner, first, "345678")["status"] == "active"
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT verification_digest FROM notification_channels "
                    "WHERE user_id = %s AND id = %s", (owner, first))
        assert cur.fetchone()["verification_digest"] is None
    transport.send_email.assert_not_called()


def test_quiet_hours_and_digest_schedule_have_durable_deduplication(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    channel = UUID(subscribe_device(service, owner, subscription)["id"])
    prefs = midnight_notification_preferences()
    prefs["quiet_hours"]["enabled"] = True
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    now = datetime(2026, 10, 8, 20, tzinfo=UTC)
    insert_notification_event(service.workspace, owner, 1, at=now)
    service.queue_events(owner, now=now)
    queued = service.status(owner)["deliveries"][0]
    assert queued["next_attempt_at"] == datetime(2026, 10, 9, 5, tzinfo=UTC)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=now)
    transport.send_push.assert_not_called()
    # A daily digest covers a completed day once, including events collected while
    # the browser was closed. Older disabled subscriptions are not backfilled.
    prefs["digest_frequency"] = "daily"
    prefs["quiet_hours"]["enabled"] = False
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verified_at = %s "
                    "WHERE user_id = %s AND id = %s", (now - timedelta(days=3), owner, channel))
    service.queue_events(owner, now=now + timedelta(days=1))
    service.queue_events(owner, now=now + timedelta(days=1))
    digests = [row for row in service.status(owner)["deliveries"] if row["kind"] == "digest"]
    assert len(digests) == 1


def test_digest_includes_late_imports_corrections_and_days_missed_during_worker_downtime(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    channel = UUID(subscribe_device(service, owner, subscription)["id"])
    prefs = midnight_notification_preferences("UTC")
    prefs["digest_frequency"] = "daily"
    prefs["quiet_hours"]["timezone"] = "UTC"
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    start = datetime(2026, 10, 2, tzinfo=UTC)
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verified_at = %s, digest_cursor_at = %s "
                    "WHERE user_id = %s AND id = %s", (start, start, owner, channel))
    service.queue_events(owner, now=start + timedelta(days=1, minutes=1))
    assert service.status(owner)["deliveries"] == []
    # The actual financial event belongs to the already-closed source day, but
    # only becomes known to the server at the following 06:15 import.
    late = insert_notification_event(service.workspace, owner, 7,
                                     at=start + timedelta(hours=18))
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE workspace_events SET updated_at = %s WHERE user_id = %s AND id = %s",
                    (start + timedelta(days=1, hours=6, minutes=15), owner, late))
    service.queue_events(owner, now=start + timedelta(days=1, hours=6, minutes=16))
    assert service.status(owner)["deliveries"] == []
    next_digest = start + timedelta(days=2, minutes=1)
    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(lambda _: service.queue_events(owner, now=next_digest), range(3)))
    assert len(service.status(owner)["deliveries"]) == 1
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=next_digest)
    first_payload = last_delivery_payload(service, owner)
    assert first_payload["period_basis"] == "available_at"
    assert datetime.fromisoformat(first_payload["from"]) == start + timedelta(days=1)
    assert "событий: 1" in first_payload["body"]
    event = next(row for row in service.workspace.events(owner)["items"] if row["id"] == late)
    assert event["occurred_at"] == start + timedelta(hours=18)
    # A later correction receives its own availability time. It and both new
    # days must survive three days without a running notification worker.
    insert_notification_event(service.workspace, owner, 7, at=start + timedelta(hours=18),
                              source={"type": "test", "revision": "corrected"})
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE workspace_events SET updated_at = %s WHERE user_id = %s AND id = %s",
                    (start + timedelta(days=2, hours=6), owner, late))
    for day in (3, 4):
        ident = insert_notification_event(service.workspace, owner, day,
                                          at=start - timedelta(days=10))
        with service.workspace._transaction(owner) as cur:
            cur.execute("UPDATE workspace_events SET updated_at = %s "
                        "WHERE user_id = %s AND id = %s",
                        (start + timedelta(days=day, hours=6), owner, ident))
    resumed = start + timedelta(days=5, minutes=1)
    service.queue_events(owner, now=resumed)
    service.queue_events(owner, now=resumed)
    assert len(service.status(owner)["deliveries"]) == 2
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=resumed)
        assert not service.deliver_one(owner, now=resumed)
    assert transport.send_push.call_count == 2
    payload = last_delivery_payload(service, owner)
    assert datetime.fromisoformat(payload["from"]) == start + timedelta(days=2)
    assert datetime.fromisoformat(payload["to"]) == start + timedelta(days=5)
    assert "событий: 3" in payload["body"]


def test_digest_cursor_and_outbox_commit_together_after_interrupted_enqueue(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, _, subscription = notification_service(database)
    channel = UUID(subscribe_device(service, owner, subscription)["id"])
    prefs = midnight_notification_preferences("UTC")
    prefs["digest_frequency"] = "daily"
    prefs["quiet_hours"]["timezone"] = "UTC"
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    start = datetime(2026, 10, 2, tzinfo=UTC)
    ident = insert_notification_event(service.workspace, owner, 1, at=start)
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verified_at = %s, digest_cursor_at = %s "
                    "WHERE user_id = %s AND id = %s", (start, start, owner, channel))
        cur.execute("UPDATE workspace_events SET updated_at = %s WHERE user_id = %s AND id = %s",
                    (start + timedelta(hours=1), owner, ident))
    enqueue = service._enqueue

    def interrupted(*args: Any, **kwargs: Any) -> None:
        enqueue(*args, **kwargs)
        raise RuntimeError("synthetic interruption before cursor commit")

    due = start + timedelta(days=1, minutes=1)
    with patch.object(service, "_enqueue", side_effect=interrupted), \
            pytest.raises(RuntimeError, match="synthetic interruption"):
        service.queue_events(owner, now=due)
    assert service.status(owner)["deliveries"] == []
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT digest_cursor_at FROM notification_channels "
                    "WHERE user_id = %s AND id = %s", (owner, channel))
        assert cur.fetchone()["digest_cursor_at"] == start
    service.queue_events(owner, now=start + timedelta(days=1, minutes=1))
    assert len(service.status(owner)["deliveries"]) == 1


def pending_digest(
    database: Database,
) -> tuple[UUID, NotificationService, Mock, dict[str, Any], datetime, str]:
    owner = user(database)
    service, transport, subscription = notification_service(database)
    channel = UUID(subscribe_device(service, owner, subscription)["id"])
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    start -= timedelta(days=2)
    prefs = midnight_notification_preferences("UTC")
    prefs["digest_frequency"] = "daily"
    prefs["quiet_hours"].update(enabled=True, timezone="UTC")
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    event = insert_notification_event(service.workspace, owner, 101, at=start - timedelta(days=4))
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_channels SET verified_at = %s, digest_cursor_at = %s "
                    "WHERE user_id = %s AND id = %s", (start, start, owner, channel))
        cur.execute("UPDATE workspace_events SET updated_at = %s WHERE user_id = %s AND id = %s",
                    (start + timedelta(hours=6), owner, event))
    now = start + timedelta(days=1, minutes=1)
    service.queue_events(owner, now=now)
    assert len(service.status(owner)["deliveries"]) == 1
    return owner, service, transport, prefs, now, event


@pytest.mark.parametrize("frequency", ["off", "weekly"])
def test_pending_digest_changes_frequency_without_losing_or_replaying_its_revision(
    workspace_database: tuple[Database, str, str], frequency: str,
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, event = pending_digest(database)
    prefs["digest_frequency"] = frequency
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    # A preference can change after queue_events and before the actual claim.
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=now)
        transport.send_push.assert_not_called()
        pending = [row for row in service.status(owner)["deliveries"]
                   if row["status"] == "queued"]
        assert len(pending) == 1
        assert pending[0]["kind"] == ("event" if frequency == "off" else "digest")
        due = pending[0]["next_attempt_at"]
        assert due > now
        assert service.deliver_one(owner, now=due)
        assert not service.deliver_one(owner, now=due + timedelta(minutes=1))
    payload = last_delivery_payload(service, owner)
    if frequency == "off":
        assert payload["event_id"] == event
    else:
        assert payload["frequency"] == "weekly"
        assert "событий: 1" in payload["body"]
    # A later mode change cannot reassign accepted membership to a new message.
    prefs["digest_frequency"] = "daily"
    service.workspace.save_preferences(owner, prefs, expected_version=2)
    service.queue_events(owner, now=due + timedelta(days=1))
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=due + timedelta(days=1))
    assert transport.send_push.call_count == 1


def test_digest_handoff_rolls_back_atomically_and_survives_repeated_settings_and_restart(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, _ = pending_digest(database)
    original = service.status(owner)["deliveries"][0]["id"]
    prefs["digest_frequency"] = "off"
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    with patch.object(service, "_bind_members", side_effect=RuntimeError("synthetic handoff")), \
            pytest.raises(RuntimeError, match="synthetic handoff"):
        service.queue_events(owner, now=now)
    state = service.status(owner)["deliveries"]
    assert [row["id"] for row in state] == [original]
    assert state[0]["status"] == "queued"
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT outbox_id FROM notification_outbox_events WHERE user_id = %s",
                    (owner,))
        assert [row["outbox_id"] for row in cur.fetchall()] == [original]
    service = NotificationService(database, service.config, legal_versions=service.legal_versions,
                                  transport=transport)
    for frequency in ("off", "daily", "weekly", "off"):
        prefs["digest_frequency"] = frequency
        saved = service.workspace.preferences(owner)
        service.workspace.save_preferences(owner, prefs, expected_version=saved["version"])
        service.queue_events(owner, now=now)
        with service.workspace._transaction(owner) as cur:
            cur.execute("SELECT o.kind, o.status FROM notification_outbox_events m "
                        "JOIN notification_outbox o ON o.user_id = m.user_id "
                        "AND o.channel_id = m.channel_id AND o.id = m.outbox_id "
                        "WHERE m.user_id = %s", (owner,))
            bindings = cur.fetchall()
        assert len(bindings) == 1
        assert bindings[0]["status"] == "queued"
        assert bindings[0]["kind"] == ("event" if frequency == "off" else "digest")
    pending = next(row for row in service.status(owner)["deliveries"] if row["status"] == "queued")
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=pending["next_attempt_at"])
        assert not service.deliver_one(owner, now=pending["next_attempt_at"])
    assert transport.send_push.call_count == 1


def test_disabling_quiet_hours_releases_unsubmitted_digest_without_bypassing_provider_backoff(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, _ = pending_digest(database)
    prefs["quiet_hours"]["enabled"] = False
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    transport.send_push.side_effect = [DeliveryResult("queued", "push_rate_limited", 120),
                                       DeliveryResult("accepted", "push_provider_accepted")]
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=now)
        assert not service.deliver_one(owner, now=now + timedelta(seconds=60))
        assert service.deliver_one(owner, now=now + timedelta(seconds=121))
        assert not service.deliver_one(owner, now=now + timedelta(seconds=122))
    assert transport.send_push.call_count == 2
    assert transport.send_push.call_args_list[0].args == transport.send_push.call_args_list[1].args


def test_unsubmitted_weekly_digest_recomputes_its_calendar_boundary_after_timezone_change(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    insert_notification_event(service.workspace, owner, 201)
    service.queue_events(owner)
    prefs = midnight_notification_preferences("UTC")
    prefs["digest_frequency"] = "weekly"
    prefs["quiet_hours"]["timezone"] = "UTC"
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    now = datetime.now(UTC)
    service.queue_events(owner, now=now)
    queued = next(row for row in service.status(owner)["deliveries"] if row["status"] == "queued")
    assert queued["next_attempt_at"] > now
    prefs["quiet_hours"]["timezone"] = "Europe/Moscow"
    prefs["digest_timezone"] = "Europe/Moscow"
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=now)
    updated = next(row for row in service.status(owner)["deliveries"]
                   if row["status"] == "queued")
    local = now.astimezone(ZoneInfo("Europe/Moscow"))
    monday = local.date() + timedelta(days=7 - local.weekday())
    expected = datetime(monday.year, monday.month, monday.day, tzinfo=ZoneInfo("Europe/Moscow"))
    assert updated["next_attempt_at"] == expected
    assert updated["next_attempt_at"] != queued["next_attempt_at"]
    assert updated["id"] == queued["id"]
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT count(*) AS total FROM notification_outbox_events WHERE user_id = %s",
                    (owner,))
        assert cur.fetchone()["total"] == 1
    transport.send_push.assert_not_called()


@pytest.mark.parametrize("timezone", ["UTC", "Europe/Berlin"])
@pytest.mark.parametrize("final_outcome", ["accepted", "expired"])
def test_weekly_handoff_ttl_starts_after_period_close_and_never_slides_on_retry(
    workspace_database: tuple[Database, str, str], timezone: str, final_outcome: str,
) -> None:
    database = workspace_database[0]
    owner = user(database)
    service, transport, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    # Berlin crosses the autumn DST boundary during this exact weekly period.
    zone = ZoneInfo(timezone)
    now = datetime(2026, 10, 19, 0, 1, tzinfo=zone).astimezone(UTC)
    boundary = datetime(2026, 10, 26, tzinfo=zone).astimezone(UTC)
    due = datetime(2026, 10, 26, 8, tzinfo=zone).astimezone(UTC)
    event = insert_notification_event(service.workspace, owner, 301,
                                      at=now - timedelta(seconds=30))
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE workspace_events SET updated_at = %s WHERE user_id = %s AND id = %s",
                    (now - timedelta(seconds=30), owner, event))
    prefs = midnight_notification_preferences(timezone)
    prefs["quiet_hours"].update(enabled=True, timezone=timezone, start="22:00", end="08:00")
    service.workspace.save_preferences(owner, prefs, expected_version=0)
    service.queue_events(owner, now=now)
    prefs["digest_frequency"] = "weekly"
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    service.queue_events(owner, now=now)
    with service.workspace._transaction(owner) as cur:
        # Simulate creation at this fixed clock, independently of the CI date.
        cur.execute("UPDATE notification_outbox SET created_at = %s WHERE user_id = %s",
                    (now, owner))
    queued = next(row for row in service.status(owner)["deliveries"] if row["status"] == "queued")
    assert queued["kind"] == "digest"
    assert queued["next_attempt_at"] == due
    assert due > now + timedelta(days=7)
    transport.send_push.side_effect = [DeliveryResult("queued", "push_rate_limited", 120),
                                       DeliveryResult("accepted", "push_provider_accepted")]
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=due)
        assert not service.deliver_one(owner, now=due + timedelta(seconds=60))
        restarted = NotificationService(database, service.config,
                                        legal_versions=service.legal_versions, transport=transport)
        if final_outcome == "accepted":
            assert restarted.deliver_one(owner, now=due + timedelta(seconds=121))
            assert not restarted.deliver_one(owner, now=due + timedelta(seconds=122))
        else:
            assert not restarted.deliver_one(owner, now=boundary + timedelta(days=7, seconds=1))
    record = next(row for row in service.status(owner)["deliveries"] if row["id"] == queued["id"])
    if final_outcome == "accepted":
        assert record["status"] == "accepted"
        assert record["attempts"] == 2
        assert transport.send_push.call_count == 2
        assert (transport.send_push.call_args_list[0].args
                == transport.send_push.call_args_list[1].args)
    else:
        assert record["status"] == "cancelled"
        assert record["last_error"] == "delivery_expired"
        assert record["attempts"] == 1
        assert transport.send_push.call_count == 1


@pytest.mark.parametrize("receipt", ["accepted", "sending", "uncertain"])
def test_digest_membership_preserves_receipts_but_a_real_source_correction_can_notify(
    workspace_database: tuple[Database, str, str], receipt: str,
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, event = pending_digest(database)
    with service.workspace._transaction(owner) as cur:
        cur.execute("UPDATE notification_outbox SET status = %s, accepted_at = %s, "
                    "lease_until = %s WHERE user_id = %s",
                    (receipt, now if receipt == "accepted" else None,
                     now + timedelta(days=1), owner))
    prefs["digest_frequency"] = "off"
    prefs["quiet_hours"]["enabled"] = False
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    service.queue_events(owner, now=now)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=now)
    transport.send_push.assert_not_called()
    assert insert_notification_event(service.workspace, owner, 101, at=now,
                                     source={"type": "test", "correction": 2}) == event
    service.queue_events(owner, now=now)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=now)
        assert not service.deliver_one(owner, now=now)
    assert transport.send_push.call_count == 1
    assert last_delivery_payload(service, owner)["event_id"] == event
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT count(*) AS total FROM notification_outbox_events "
                    "WHERE user_id = %s AND event_id = %s", (owner, event))
        assert cur.fetchone()["total"] == 2


def test_legacy_queued_digest_is_adopted_without_inventing_an_accepted_receipt(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, event = pending_digest(database)
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT id, payload_ciphertext FROM notification_outbox WHERE user_id = %s",
                    (owner,))
        row = cur.fetchone()
        legacy = service._open(row["payload_ciphertext"])
        legacy.pop("membership_version")
        cur.execute("DELETE FROM notification_outbox_events WHERE user_id = %s", (owner,))
        cur.execute("UPDATE notification_outbox SET payload_ciphertext = %s WHERE user_id = %s",
                    (service._seal(legacy), owner))
    prefs["digest_frequency"] = "off"
    prefs["quiet_hours"]["enabled"] = False
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert service.deliver_one(owner, now=now)
        assert not service.deliver_one(owner, now=now)
    assert last_delivery_payload(service, owner)["event_id"] == event
    assert transport.send_push.call_count == 1


def test_legacy_aggregate_overlap_is_explicitly_uncertain_instead_of_replayed(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, service, transport, prefs, now, _ = pending_digest(database)
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT payload_ciphertext, channel_id FROM notification_outbox "
                    "WHERE user_id = %s", (owner,))
        row = cur.fetchone()
        legacy = service._open(row["payload_ciphertext"])
        legacy.pop("membership_version")
        cur.execute("DELETE FROM notification_outbox_events WHERE user_id = %s", (owner,))
        cur.execute("UPDATE notification_outbox SET payload_ciphertext = %s WHERE user_id = %s",
                    (service._seal(legacy), owner))
        service._enqueue(cur, owner, row["channel_id"], "legacy-accepted", "digest", legacy, now)
        cur.execute("UPDATE notification_outbox SET status = 'accepted', accepted_at = %s "
                    "WHERE user_id = %s AND message_key = 'legacy-accepted'", (now, owner))
    prefs["digest_frequency"] = "off"
    prefs["quiet_hours"]["enabled"] = False
    service.workspace.save_preferences(owner, prefs, expected_version=1)
    with patch.object(database, "has_legal_versions", return_value=True):
        assert not service.deliver_one(owner, now=now)
    states = service.status(owner)["deliveries"]
    assert {row["status"] for row in states} == {"accepted", "uncertain"}
    assert any(row["last_error"] == "legacy_digest_membership_unknown" for row in states)
    transport.send_push.assert_not_called()


def test_delivery_membership_cannot_reference_another_owner_or_channel(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, service, _, _, _, event = pending_digest(database)
    other = user(database)
    with service.workspace._transaction(owner) as cur:
        cur.execute("SELECT channel_id, outbox_id, event_revision "
                    "FROM notification_outbox_events WHERE user_id = %s", (owner,))
        member = cur.fetchone()
    with service.workspace._transaction(other) as cur:
        cur.execute("SELECT * FROM notification_outbox_events WHERE user_id = %s", (owner,))
        assert cur.fetchall() == []
    values = (other, member["channel_id"], event, member["event_revision"], member["outbox_id"])
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute("INSERT INTO notification_outbox_events "
                         "(user_id, channel_id, event_id, event_revision, outbox_id) "
                         "VALUES (%s, %s, %s, %s, %s)", values)
        conn.rollback()
    owner_values = (owner, uuid4(), event, member["event_revision"], member["outbox_id"])
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            conn.execute("INSERT INTO notification_outbox_events "
                         "(user_id, channel_id, event_id, event_revision, outbox_id) "
                         "VALUES (%s, %s, %s, %s, %s)", owner_values)
        conn.rollback()


def test_completed_heartbeat_failure_survives_a_live_attempt_until_its_success(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    database.record_worker_heartbeat("notifications", status="attention")
    before = database.collect_operational_metrics()["workers"]["notifications"]
    database.record_worker_heartbeat("notifications", status="running")
    during = database.collect_operational_metrics()["workers"]["notifications"]
    assert during["status"] == "attention"
    assert during["completed_at"] == before["completed_at"]
    assert during["checked_at"] >= before["checked_at"]
    database.record_worker_heartbeat("notifications")
    after = database.collect_operational_metrics()["workers"]["notifications"]
    assert after["status"] == "ok"
    assert after["completed_at"] >= during["completed_at"]


def test_operational_monitor_detects_degraded_observations_outbox_delay_and_dead_worker(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    service, _, subscription = notification_service(database)
    subscribe_device(service, owner, subscription)
    insert_notification_event(service.workspace, owner, 1)
    service.queue_events(owner)
    with service.workspace._transaction(owner) as cur:
        cur.execute("INSERT INTO job_runs (user_id, job_type, scheduled_for, status, finished_at, "
                    "details) VALUES (%s, 'portfolio_daily', current_date, 'degraded', now(), "
                    "'{\"snapshot_saved\": false, \"stage_error\": \"TBankUnavailable\"}'::jsonb)",
                    (owner,))
        cur.execute("UPDATE notification_outbox SET "
                    "next_attempt_at = now() - interval '16 minutes' "
                    "WHERE user_id = %s", (owner,))
        cur.execute("UPDATE tbank_connection SET verified_at = now() - interval '37 hours' "
                    "WHERE user_id = %s", (owner,))
    for worker in ("notifications", "portfolio_refresh", "portfolio_daily"):
        database.record_worker_heartbeat(worker)
    with database.pool.connection() as conn:
        conn.execute("UPDATE worker_heartbeats SET checked_at = now() - interval '6 minutes' "
                     "WHERE worker_name = 'notifications'")
    metrics = database.collect_operational_metrics()
    assert metrics["status"] == "attention"
    assert metrics["observer"]["degraded_24h"] >= 1
    assert metrics["observer"]["stale_success_accounts"] >= 1
    assert metrics["notifications"]["stale"] >= 1
    assert metrics["workers"]["notifications"]["status"] == "stale"
    assert {"observer_degraded_24h", "observer_stale_success_accounts", "notifications_stale",
            "notifications_worker_stale"}.issubset(metrics["issues"])
    assert str(owner) not in str(metrics)
    assert subscription["endpoint"] not in str(metrics)
    database.record_worker_heartbeat("notifications")


def test_preference_versions_and_goal_crud_are_tenant_isolated(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner, other = user(database), user(database)
    initial = store.preferences(owner)
    assert initial == {"version": 0, "document": default_preferences()}
    edited = {**initial["document"], "display_name": "Имя владельца", "mask_balances": True}
    saved = store.save_preferences(owner, edited, expected_version=0)
    assert saved["version"] == 1
    assert store.save_preferences(owner, edited, expected_version=1) == saved
    with pytest.raises(SettingsVersionConflict):
        store.save_preferences(owner, initial["document"], expected_version=0)
    assert store.preferences(other)["version"] == 0

    created = store.create_goal(owner, goal_document())
    ident = UUID(created["id"])
    assert created["progress"]["amount_rub"] == "15000.00000000"
    assert store.goals(other)["items"] == []
    document = goal_document()
    with pytest.raises(WorkspaceNotFound):
        store.update_goal(other, ident, document, expected_version=1)
    with pytest.raises(SettingsVersionConflict):
        store.update_goal(owner, ident, document, expected_version=0)
    updated = store.update_goal(owner, ident, goal_document(title="Изменено"), expected_version=1)
    assert updated["version"] == 2
    with pytest.raises(SettingsVersionConflict):
        store.delete_goal(owner, ident, expected_version=1)
    assert store.delete_goal(owner, ident, expected_version=2)
    assert store.goals(owner)["items"] == []


def test_allocation_cannot_double_count_even_under_concurrent_writes(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner = user(database, account=True)
    linked = goal_document(
        progress_source="portfolio", allocation_percent="60", manual_amount_rub=None
    )

    def save(index: int) -> dict[str, Any] | str:
        try:
            return store.create_goal(owner, {**linked, "title": f"Цель {index}"})
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(save, (1, 2)))
    assert sum(isinstance(item, dict) for item in results) == 1
    assert "workspace_goal_allocation_exceeds_available" in results
    goal = store.goals(owner)["items"][0]
    assert goal["progress"]["amount_rub"] is None
    assert goal["account_id"] == str(owner)
    with database.pool.connection() as conn:
        conn.execute(
            "UPDATE tbank_connection SET account_id = 'replacement' WHERE user_id = %s", (owner,)
        )
    # An unrelated edit cannot assign the stored capital to a different account.
    edited = store.update_goal(
        owner, UUID(goal["id"]), {**linked, "title": "Новое название"}, expected_version=1
    )
    assert edited["account_id"] == str(owner)
    assert edited["progress"]["reason"] == "linked_account_unavailable"


def test_events_deduplicate_and_read_state_survives_refresh_and_cross_tenant_attempts(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    store = WorkspaceStore(database)
    owner, other = user(database), user(database)
    store.create_goal(owner, goal_document(manual_amount_rub="100000"))
    with database.pool.connection() as conn:
        conn.execute(
            "INSERT INTO audit_events (user_id, event_type) VALUES (%s, 'login_succeeded')",
            (owner,),
        )
    first = store.events(owner)
    second = store.events(owner)
    assert first["unread_count"] == second["unread_count"] == 2
    assert {row["id"] for row in first["items"]} == {row["id"] for row in second["items"]}
    ids = [item["id"] for item in first["items"]]
    with pytest.raises(WorkspaceNotFound):
        store.mark_events_read(other, ids)
    marked = store.mark_events_read(owner, ids)
    assert marked["unread_count"] == 0
    assert store.events(owner, unread_only=True)["items"] == []
    assert store.mark_events_read(owner, ids, read=False)["unread_count"] == 2
    preferences = default_preferences()
    preferences["notifications"]["system"] = False
    store.save_preferences(owner, preferences, expected_version=0)
    filtered = store.events(owner)
    assert filtered["unread_count"] == 1
    assert all(item["category"] == "goals" for item in filtered["items"])
    assert store.dashboard(other)["overview"]["nav_rub"] is None


def test_workspace_database_rls_and_user_cascade_are_enforced(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, admin_url, schema = workspace_database
    owner, other = user(database), user(database)
    store = WorkspaceStore(database)
    store.save_preferences(owner, default_preferences(), expected_version=0)
    store.create_goal(owner, goal_document(manual_amount_rub="100000"))
    store.events(owner)
    with database.pool.connection() as conn:
        for table in ("workspace_preferences", "investment_goals", "workspace_events"):
            assert (
                conn.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table),
                    ),
                    (owner,),
                ).fetchone()["count"]
                == 0
            )
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(other),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO workspace_preferences (user_id, version, document) "
                "VALUES (%s, 1, '{}'::jsonb)",
                (owner,),
            )
        conn.rollback()
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        enforced = admin.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relnamespace = %s::regnamespace AND relname = ANY (%s)",
            (schema, ["workspace_preferences", "investment_goals", "workspace_events"]),
        ).fetchall()
        assert len(enforced) == 3
        for enabled, forced in enforced:
            assert enabled
            assert forced
        admin.execute("DELETE FROM users WHERE id = %s", (owner,))
        for table in ("workspace_preferences", "investment_goals", "workspace_events"):
            assert (
                admin.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table),
                    ),
                    (owner,),
                ).fetchone()[0]
                == 0
            )


def test_dashboard_uses_latest_operation_correction_and_complete_ledger(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    now = datetime.now(UTC)
    begin, end = now - timedelta(days=3), now - timedelta(days=1)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        for at, nav in ((begin, "10000"), (end, "10500")):
            conn.execute(
                "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
                "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
                "limits_loading_in_progress, evidence) "
                "VALUES (%s, %s, 'prod', %s, 'observed', %s, %s, 0, %s, false, "
                "jsonb_build_object('analysis', '{}'::jsonb, 'account', "
                "jsonb_build_object('opened_at', %s::text)))",
                (owner, str(owner), at, nav, nav, nav, (begin - timedelta(days=10)).isoformat()),
            )
        conn.execute(
            "INSERT INTO broker_sync_state (user_id, account_id, last_complete_watermark) "
            "VALUES (%s, %s, %s)",
            (owner, str(owner), now),
        )
        for index, state in enumerate(("OPERATION_STATE_EXECUTED", "OPERATION_STATE_CANCELED")):
            conn.execute(
                "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
                "semantic_hash, provider_operation_id, operation_date, operation_type, "
                "operation_state, payment_value, payment_currency, normalized, observed_at) "
                "VALUES (%s, %s, %s, %s, 'same-provider-id', %s, 'OPERATION_TYPE_INPUT', %s, "
                "1000, 'RUB', '{}'::jsonb, %s)",
                (
                    owner,
                    str(owner),
                    bytes([index + 1]) * 32,
                    bytes([index + 1]) * 32,
                    begin + timedelta(days=1),
                    state,
                    end + timedelta(minutes=index),
                ),
            )
    dashboard = WorkspaceStore(database).dashboard(owner)
    assert dashboard["performance"]["status"] == "available"
    assert dashboard["performance"]["net_contributions_rub"] == "0"
    assert Decimal(dashboard["performance"]["investment_result_rub"]) == 500
    assert Decimal(dashboard["performance"]["return_percent"]) == 5
    assert dashboard["performance"]["return_method"] == "modified_dietz"
    assert dashboard["income"]["total_rub"] == "0"

    def insert_coupon(state: str, byte: int) -> None:
        with database.pool.connection() as conn:
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute(
                "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
                "semantic_hash, provider_operation_id, operation_date, operation_type, "
                "operation_state, payment_value, payment_currency, normalized, observed_at) "
                "VALUES (%s, %s, %s, %s, 'corrected-coupon', %s, 'OPERATION_TYPE_COUPON', %s, "
                "300, 'RUB', '{}'::jsonb, %s)",
                (
                    owner,
                    str(owner),
                    bytes([byte]) * 32,
                    bytes([byte]) * 32,
                    begin + timedelta(days=1),
                    state,
                    now - timedelta(minutes=10 - byte),
                ),
            )

    store = WorkspaceStore(database)
    insert_coupon("OPERATION_STATE_EXECUTED", 3)
    paid = next(
        item for item in store.events(owner)["items"] if item["kind"] == "payment_operation"
    )
    store.mark_events_read(owner, [paid["id"]])
    insert_coupon("OPERATION_STATE_CANCELED", 4)
    corrected = [
        item for item in store.events(owner)["items"] if item["kind"] == "payment_operation"
    ]
    assert len(corrected) == 1
    assert corrected[0]["id"] == paid["id"]
    assert corrected[0]["read_at"] is None
    assert corrected[0]["source"]["state"] == "OPERATION_STATE_CANCELED"
    assert store.dashboard(owner)["income"]["total_rub"] == "0"


def test_risk_alerts_survive_unchanged_snapshots_and_notify_actual_state_changes(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    store = WorkspaceStore(database)
    start = datetime.now(UTC) - timedelta(days=1)

    def observe(state: str, minute: int) -> list[dict[str, Any]]:
        snapshot_id = uuid4()
        at = start + timedelta(minutes=minute)
        with database.pool.connection() as conn:
            conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
            conn.execute(
                "INSERT INTO portfolio_snapshots (id, user_id, account_id, environment, "
                "captured_at, analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, "
                "rub_cash_unblocked, limits_loading_in_progress, evidence) "
                "VALUES (%s, %s, %s, 'prod', %s, 'observed', 1000, 0, 0, 0, false, '{}'::jsonb)",
                (snapshot_id, owner, str(owner), at),
            )
            conn.execute(
                "INSERT INTO portfolio_snapshot_positions (snapshot_id, user_id, instrument_uid, "
                "ticker, instrument_type, quantity, blocked, blocked_lots) "
                "VALUES (%s, %s, 'risk-instrument', 'TEST', 'bond', 1, false, 0)",
                (snapshot_id, owner),
            )
            conn.execute(
                "INSERT INTO portfolio_risk_assessments (user_id, snapshot_id, instrument_uid, "
                "state, rating_status, fundamental_status, source_status, reasons, evidence, "
                "assessed_at) VALUES (%s, %s, 'risk-instrument', %s, 'received', "
                "'not_applicable', 'received', '[]'::jsonb, '{}'::jsonb, %s)",
                (owner, snapshot_id, state, at),
            )
        return [item for item in store.events(owner)["items"] if item["kind"] == "instrument_risk"]

    assert observe("normal", 0) == []
    first = observe("watch", 1)[0]
    store.mark_events_read(owner, [first["id"]])
    unchanged = observe("watch", 2)
    assert len(unchanged) == 1
    assert unchanged[0]["id"] == first["id"]
    assert unchanged[0]["read_at"] is not None
    assert unchanged[0]["occurred_at"] == first["occurred_at"]
    for index, state in enumerate(("critical", "normal", "critical"), start=3):
        changed = observe(state, index)
        assert len(changed) == 1
        assert changed[0]["id"] == first["id"]
        assert changed[0]["read_at"] is None
        assert changed[0]["source"]["state"] == state
        store.mark_events_read(owner, [first["id"]])


def _long_history(database: Database, owner: UUID, begin: datetime) -> None:
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
            "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
            "limits_loading_in_progress, evidence) "
            "SELECT %s, %s, 'prod', %s::timestamptz + n * interval '12 hours', "
            "CASE WHEN n = 0 THEN 'partial' ELSE 'observed' END, "
            "10000 + n * 10, 0, 0, 0, false, "
            "jsonb_build_object('account', jsonb_build_object('opened_at', %s::text)) "
            "FROM generate_series(0, 999) AS history(n)",
            (owner, str(owner), begin, (begin - timedelta(days=1)).isoformat()),
        )
        conn.execute(
            "INSERT INTO broker_sync_state (user_id, account_id, last_complete_watermark) "
            "VALUES (%s, %s, %s)",
            (owner, str(owner), begin + timedelta(hours=800 * 12)),
        )
        for number, kind, value, offset in (
            (1, "COUPON", "250", 400), (2, "INPUT", "3000", 500),
        ):
            conn.execute(
                "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
                "semantic_hash, provider_operation_id, operation_date, operation_type, "
                "operation_state, payment_value, payment_currency, normalized, observed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'OPERATION_STATE_EXECUTED', "
                "%s, 'RUB', '{}'::jsonb, %s)",
                (owner, str(owner), bytes([number]) * 32, bytes([number]) * 32, str(number),
                 begin + timedelta(hours=offset * 12), "OPERATION_TYPE_" + kind, value,
                 datetime.now(UTC)),
            )


def test_full_range_nav_sampling_keeps_exact_covered_performance_endpoints(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    begin = datetime.now(UTC) - timedelta(days=500) + timedelta(hours=6)
    _long_history(database, owner, begin)
    store = WorkspaceStore(database)
    result = store.dashboard(owner)
    history, coverage = result["overview"]["history"], result["overview"]["history_coverage"]
    assert coverage["status"] == "sampled"
    assert coverage["period"] == "all"
    assert coverage["sampling"] == "time_bucket_last"
    assert coverage["total_stored_observations"] == 1000
    assert coverage["total_observations"] == 1000
    assert len(history) >= 2
    assert len(history) <= 366
    assert coverage["max_points"] == 366
    assert coverage["returned_observations"] == len(history)
    assert datetime.fromisoformat(coverage["returned_from"]) == begin
    assert datetime.fromisoformat(coverage["returned_to"]) == begin + timedelta(hours=999 * 12)
    assert datetime.fromisoformat(coverage["available_from"]) == begin
    expected = {(begin + timedelta(hours=n * 12), Decimal(10000 + n * 10)) for n in range(1000)}
    actual = {(datetime.fromisoformat(row["captured_at"]), Decimal(row["nav_rub"]))
              for row in history}
    assert actual <= expected
    assert len(actual) == len(history)
    # Both covered endpoints lie between sampled points. P&L must come from the
    # full underlying observations, not whichever chart points survived sampling.
    performance = result["performance"]
    assert datetime.fromisoformat(performance["from"]) == begin + timedelta(hours=12)
    assert datetime.fromisoformat(performance["to"]) == begin + timedelta(hours=800 * 12)
    assert datetime.fromisoformat(performance["from"]) not in {point[0] for point in actual}
    assert datetime.fromisoformat(performance["to"]) not in {point[0] for point in actual}
    assert Decimal(performance["investment_result_rub"]) == 4990
    assert Decimal(performance["net_contributions_rub"]) == 3000
    assert Decimal(result["overview"]["nav_rub"]) == 19990
    assert Decimal(result["income"]["total_rub"]) == 250

    yearly = store.dashboard(owner, history_period="1y")
    year_coverage = yearly["overview"]["history_coverage"]
    assert year_coverage["status"] == "sampled"
    assert year_coverage["total_observations"] == 730
    assert year_coverage["total_stored_observations"] == 1000
    year_begin = begin + timedelta(hours=270 * 12)
    assert datetime.fromisoformat(year_coverage["returned_from"]) == year_begin
    assert datetime.fromisoformat(yearly["performance"]["from"]) == year_begin
    assert Decimal(yearly["performance"]["investment_result_rub"]) == 2300
    assert Decimal(yearly["income"]["total_rub"]) == 250

    daily = store.dashboard(owner, history_period="1d")
    day_coverage = daily["overview"]["history_coverage"]
    assert day_coverage["status"] == "complete"
    assert day_coverage["total_observations"] == 2
    assert day_coverage["returned_observations"] == 2
    assert datetime.fromisoformat(day_coverage["requested_to"]) == datetime.fromisoformat(
        daily["generated_at"]
    )
    assert daily["performance"]["reason"] == "insufficient_covered_snapshots"
    assert daily["performance"]["investment_result_rub"] is None
    assert daily["income"]["total_rub"] is None
    assert daily["income"]["reason"] == "history_incomplete"

    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "UPDATE broker_sync_state SET pending_cursor = 'unread-page', "
            "history_window_from = %s, history_window_to = %s WHERE user_id = %s",
            (begin, datetime.now(UTC), owner),
        )
    partial = store.dashboard(owner)
    assert partial["overview"]["history_coverage"]["status"] == "sampled"
    # A new pending window does not erase the independently completed watermark.
    assert partial["performance"]["status"] == "available"
    assert partial["performance"]["investment_result_rub"] == performance["investment_result_rub"]
    assert partial["income"]["total_rub"] == result["income"]["total_rub"]


def test_nav_history_empty_single_zero_and_replaced_account_are_explicit(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    store = WorkspaceStore(database)
    empty = store.dashboard(owner, history_period="1d")
    assert empty["overview"]["history_coverage"]["status"] == "empty"
    assert empty["overview"]["history_coverage"]["available_from"] is None
    assert empty["overview"]["nav_rub"] is None
    at = datetime.now(UTC) - timedelta(minutes=1)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
            "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
            "limits_loading_in_progress, evidence) "
            "VALUES (%s, %s, 'prod', %s, 'observed', 0, 0, 0, 0, false, '{}'::jsonb)",
            (owner, str(owner), at),
        )
    single = store.dashboard(owner)
    assert single["overview"]["history_coverage"]["status"] == "complete"
    assert single["overview"]["history_coverage"]["total_observations"] == 1
    assert Decimal(single["overview"]["nav_rub"]) == 0
    assert single["performance"]["investment_result_rub"] is None
    assert single["income"]["total_rub"] is None
    with database.pool.connection() as conn:
        conn.execute(
            "UPDATE tbank_connection SET account_id = 'other' WHERE user_id = %s", (owner,),
        )
    switched = store.dashboard(owner)
    assert switched["overview"]["history"] == []
    assert switched["overview"]["history_coverage"]["total_stored_observations"] == 0
    assert switched["overview"]["nav_rub"] is None
    assert switched["performance"]["investment_result_rub"] is None


def _ledger_fact(
    database: Database, owner: UUID, ident: str, at: datetime, *, observed: datetime | None = None,
    kind: str = "INPUT", value: str = "100",
) -> None:
    operation_type = "OPERATION_TYPE_" + kind
    payload = {"provider_operation_id": ident, "operation_type": operation_type,
               "state": "OPERATION_STATE_EXECUTED", "name": ident,
               "payment": {"value": value, "currency": "RUB"}}
    digest = hashlib.sha256(f"{ident}:{at}:{kind}:{value}".encode()).digest()
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO operation_observations (user_id, account_id, observation_hash, "
            "semantic_hash, provider_operation_id, operation_date, operation_type, "
            "operation_state, "
            "payment_value, payment_currency, normalized, observed_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, 'OPERATION_STATE_EXECUTED', "
            "%s, 'RUB', %s::jsonb, %s)",
            (owner, str(owner), digest, digest, ident, at, operation_type, value,
             json.dumps(payload), observed or datetime.now(UTC)),
        )


def test_parent_trade_and_fee_keep_distinct_lineages_in_totals_and_paginated_history(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database, account=True), user(database, account=True)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    at = now - timedelta(hours=1)
    _ledger_fact(database, owner, "shared-parent", at, kind="BUY", value="-5000")
    _ledger_fact(database, owner, "shared-parent", at, kind="BROKER_FEE", value="-10")
    _ledger_fact(database, owner, "shared-parent", at, kind="BROKER_FEE", value="-12")
    _ledger_fact(database, owner, "contribution", at, value="1000")
    # ID-less observations use their own semantic identity. A literal provider
    # ID equal to that digest must not share the fallback's namespace.
    _ledger_fact(database, owner, "", at, kind="COUPON", value="100")
    _ledger_fact(database, owner, "", at, kind="COUPON", value="200")
    fallback_hash = hashlib.sha256(f":{at}:COUPON:100".encode()).hexdigest()
    _ledger_fact(database, owner, fallback_hash, at, kind="COUPON", value="300")
    _ledger_fact(database, other, "shared-parent", at, kind="BROKER_FEE", value="-999")
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO broker_sync_state(user_id, account_id, last_complete_watermark) "
            "VALUES(%s, %s, %s)", (owner, str(owner), now),
        )
    with store._transaction(owner) as cur:
        basis = store._basis(cur, owner)
    assert basis.complete
    assert len(basis.operations) == 6
    flow = cashflow_summary(basis.operations, from_at=at - timedelta(seconds=1),
                            to_at=now, complete=basis.complete)
    assert Decimal(flow["net_contributions_rub"]) == Decimal("1000")
    assert Decimal(flow["fees_rub"]) == Decimal("12")
    assert Decimal(flow["income"]["total_rub"]) == Decimal("600")
    rows: list[dict[str, Any]] = []
    cursor = None
    for _ in range(3):
        page = store.operations(owner, limit=2, cursor=cursor)
        rows.extend(page["items"])
        cursor = page["next_cursor"]
    assert cursor is None
    assert len({row["id"] for row in rows}) == 6
    fees = [row for row in rows if row["category"] == "fee"]
    assert len(fees) == 1
    assert fees[0]["payment"]["value"] == "-12"
    assert sum(row["category"] == "internal" for row in rows) == 1


def test_reconfirmed_prior_operation_changes_current_totals_and_invalidates_old_page(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database, account=True), user(database, account=True)
    store = WorkspaceStore(database)
    began = datetime.now(UTC) - timedelta(seconds=20)
    source_at = began - timedelta(hours=1)
    original = TBankOperation(
        cursor="", broker_account_id=str(owner), id="fee", parent_operation_id="trade",
        name="Broker fee", date=source_at, operation_type="OPERATION_TYPE_BROKER_FEE",
        description="", state="OPERATION_STATE_EXECUTED", instrument_uid="", figi="",
        instrument_type="", position_uid="", ticker="", class_code="",
        payment=TBankMoney("RUB", "-10"), price=None, commission=None, accrued_int=None,
        quantity="0", quantity_rest="0", quantity_done="0", asset_uid="", trades=(),
    )

    def observe(tenant: UUID, value: str, second: int, *, ident: str = "fee") -> bool:
        item = replace(original, broker_account_id=str(tenant), id=ident,
                       payment=TBankMoney("RUB", value))
        with store._transaction(tenant) as cur:
            return _save_operation_observation(
                cur, user_id=tenant, account_id=str(tenant), operation=item,
                observed_at=began + timedelta(seconds=second),
            )

    assert observe(owner, "-10", 0)
    assert observe(other, "-12", 0)
    _ledger_fact(database, owner, "deposit", source_at, observed=began)
    assert observe(owner, "-12", 1)
    with patch("omnicio.workspace_store.datetime") as clock:
        clock.now.return_value = began + timedelta(seconds=2)
        first = store.operations(owner, limit=1)
        assert first["items"][0]["payment"]["value"] == "-12"
        assert first["next_cursor"] is not None
        # Re-reading the already-current fact does not move its timestamp or
        # invalidate an otherwise consistent page snapshot.
        assert not observe(owner, "-12", 3)
        clock.now.return_value = began + timedelta(seconds=4)
        second = store.operations(owner, limit=1, cursor=first["next_cursor"])
        assert second["items"][0]["category"] == "contribution"
        assert second["next_cursor"] is None
        assert not observe(owner, "-10", 5)
        # A delayed older read must not undo the newer confirmation.
        assert not observe(owner, "-12", 4)
        clock.now.return_value = began + timedelta(seconds=6)
        with pytest.raises(ValueError, match="workspace_operation_history_changed"):
            store.operations(owner, limit=1, cursor=first["next_cursor"])
        fresh = store.operations(owner)
        fees = [row for row in fresh["items"] if row["category"] == "fee"]
        assert len(fees) == 1
        assert fees[0]["payment"]["value"] == "-10"
        assert fees[0]["operation_date"] == source_at.isoformat()
        assert fees[0]["observed_at"] == (began + timedelta(seconds=5)).isoformat()
        assert store.operations(other)["items"][0]["payment"]["value"] == "-12"
    # An exact semantic replay after a provider-ID rotation remains idempotent;
    # this does not infer a relation between different financial facts.
    assert not observe(owner, "-10", 7, ident="renamed-provider-id")
    with store._transaction(owner) as cur:
        basis = store._basis(cur, owner)
        cur.execute("SELECT count(*) AS count FROM operation_observations WHERE user_id = %s",
                    (owner,))
        assert cur.fetchone()["count"] == 3
    totals = cashflow_summary(basis.operations, from_at=source_at - timedelta(seconds=1),
                              to_at=began, complete=True)
    assert Decimal(totals["fees_rub"]) == Decimal("10")


def test_operations_pages_freeze_ingestion_and_bind_account_filters(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database, account=True), user(database, account=True)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    _ledger_fact(database, owner, "alpha", now - timedelta(hours=36),
                 observed=now - timedelta(hours=2))
    _ledger_fact(database, owner, "beta", now - timedelta(hours=24),
                 observed=now - timedelta(hours=2))
    _ledger_fact(database, owner, "gamma", now - timedelta(hours=6),
                 observed=now - timedelta(hours=2))
    lower = now - timedelta(days=2)
    first = store.operations(owner, limit=1, from_at=lower)
    assert first["items"][0]["provider_operation_id"] == "gamma"
    assert first["items"][0]["category"] == "contribution"
    _ledger_fact(database, owner, "beta", now - timedelta(days=10),
                 observed=now - timedelta(hours=1))
    second = store.operations(owner, limit=1, from_at=lower, cursor=first["next_cursor"])
    assert second["items"][0]["provider_operation_id"] == "beta"
    third = store.operations(owner, limit=1, from_at=lower, cursor=second["next_cursor"])
    assert third["items"][0]["provider_operation_id"] == "alpha"
    assert third["next_cursor"] is None
    # A fresh read sees the corrected date outside the selected interval.
    assert {item["provider_operation_id"] for item in store.operations(
        owner, from_at=lower,
    )["items"]} == {"alpha", "gamma"}
    with pytest.raises(ValueError, match="cursor_invalid"):
        store.operations(other, from_at=lower, cursor=first["next_cursor"])
    changed_lower = lower - timedelta(days=1)
    with pytest.raises(ValueError, match="cursor_invalid"):
        store.operations(owner, from_at=changed_lower, cursor=first["next_cursor"])


def test_selected_history_limit_is_applied_after_corrections_and_before_old_lifetime_rows(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    for index in range(5):
        _ledger_fact(database, owner, str(index), now - timedelta(days=10 + index))
    _ledger_fact(database, owner, "moved", now - timedelta(hours=12))
    _ledger_fact(database, owner, "moved", now - timedelta(days=20))
    _ledger_fact(database, owner, "current", now - timedelta(minutes=10))
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        conn.execute(
            "INSERT INTO broker_sync_state(user_id, account_id, last_complete_watermark) "
            "VALUES(%s, %s, %s)", (owner, str(owner), now),
        )
    with patch("omnicio.workspace_store._MAX_OPERATIONS", 2), store._transaction(owner) as cur:
        all_time = store._basis(cur, owner)
        selected = store._basis(cur, owner, operations_from=now - timedelta(days=1))
    assert not all_time.complete
    assert selected.complete
    assert [row["provider_operation_id"] for row in selected.operations] == ["current"]


def test_income_goals_keep_separate_corrected_periods_before_history_limit(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, another = user(database, account=True), user(database, account=True)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    for index in range(5):
        _ledger_fact(database, owner, str(index), now - timedelta(days=10 + index), kind="COUPON")
    _ledger_fact(database, owner, "moved", now - timedelta(minutes=20), kind="COUPON")
    _ledger_fact(database, owner, "moved", now - timedelta(days=20), kind="COUPON")
    _ledger_fact(database, owner, "current", now - timedelta(minutes=10), kind="COUPON")
    _ledger_fact(database, another, "other", now - timedelta(minutes=10), kind="COUPON")
    with store._transaction(owner) as cur:
        cur.execute(
            "INSERT INTO broker_sync_state(user_id, account_id, last_complete_watermark) "
            "VALUES(%s, %s, %s)", (owner, str(owner), now),
        )
    with patch("omnicio.workspace_store._MAX_OPERATIONS", 2):
        earlier = store.create_goal(owner, goal_document(
            title="Earlier income", kind="income", progress_source="income",
            allocation_percent="50", manual_amount_rub=None,
            start_date=(now - timedelta(days=40)).date().isoformat(),
        ))
        recent = store.create_goal(owner, goal_document(
            title="Recent income", kind="income", progress_source="income",
            allocation_percent="50", manual_amount_rub=None,
            start_date=(now - timedelta(days=1)).date().isoformat(),
        ))
        assert earlier["progress"]["status"] == "unavailable"
        assert recent["progress"]["status"] == "available"
        assert Decimal(recent["progress"]["amount_rub"]) == 50
        for result in (store.goals(owner), store.dashboard(owner)["goals"]):
            progress = {row["id"]: row["progress"] for row in result["items"]}
            assert progress[earlier["id"]]["status"] == "unavailable"
            assert Decimal(progress[recent["id"]]["amount_rub"]) == 50


def test_fund_nav_coverage_enables_intraday_return_and_goal_without_sector_guess(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        for at, nav in ((now - timedelta(hours=2), "1000"), (now - timedelta(minutes=1), "1100")):
            evidence = {"analysis": {"valuation_status": "complete", "sector_status": "partial"},
                        "account": {"opened_at": (now - timedelta(days=30)).isoformat()}}
            conn.execute(
                "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
                "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
                "limits_loading_in_progress, evidence) "
                "VALUES(%s, %s, 'prod', %s, 'partial', %s, 0, 0, 0, false, %s::jsonb)",
                (owner, str(owner), at, nav, json.dumps(evidence)),
            )
        conn.execute(
            "INSERT INTO broker_sync_state(user_id, account_id, last_complete_watermark) "
            "VALUES(%s, %s, %s)", (owner, str(owner), now),
        )
    goal = store.create_goal(owner, goal_document(
        progress_source="portfolio", allocation_percent="100", manual_amount_rub=None,
    ))
    result = store.dashboard(owner, history_period="1d")
    assert result["overview"]["status"] == "observed"
    assert result["overview"]["sector_status"] == "partial"
    assert len(result["overview"]["history"]) == 2
    assert Decimal(result["performance"]["return_percent"]) == 10
    assert Decimal(goal["progress"]["amount_rub"]) == 1100


def test_event_important_assets_filters_apply_before_pagination_and_summary_has_no_page_limit(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database)
    store = WorkspaceStore(database)
    now = datetime.now(UTC)
    with store._transaction(owner) as cur:
        for number in range(80):
            store._insert_event(
                cur, owner, identity=number, category="system", kind="fixture_info",
                title=f"Info {number}", occurred_at=now - timedelta(seconds=number),
                target="settings", source={},
            )
        for number, category in enumerate(("portfolio", "payments")):
            store._insert_event(
                cur, owner, identity=number, category=category, kind="fixture_important",
                title=f"Important {number}", occurred_at=now - timedelta(days=1),
                target="portfolio", source={}, severity="warning",
            )
    first = store.events(owner, important_only=True, category="assets", limit=1)
    assert len(first["items"]) == 1
    assert first["items"][0]["severity"] == "warning"
    second = store.events(owner, important_only=True, category="assets", limit=1,
                          cursor=first["next_cursor"])
    assert len(second["items"]) == 1
    assert second["items"][0]["id"] != first["items"][0]["id"]
    with pytest.raises(ValueError, match="cursor_filter_changed"):
        store.events(owner, cursor=first["next_cursor"])
    summary = store.events_summary(owner)
    assert summary["unread_total"] == 82
    assert summary["categories"] == {"system": 80, "portfolio": 1, "payments": 1, "goals": 0}
    store.mark_all_events_read(owner, category="assets", through_revision=summary["max_revision"])
    assert store.events_summary(owner)["unread_total"] == 80


def test_new_nav_snapshot_keeps_original_risk_time_and_closed_position_is_not_current(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner = user(database, account=True)
    now = datetime.now(UTC)
    old = now - timedelta(days=3)
    ids = []
    with database.pool.connection() as conn:
        conn.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(owner),))
        for at in (old, now - timedelta(minutes=1)):
            row = conn.execute(
                "INSERT INTO portfolio_snapshots (user_id, account_id, environment, captured_at, "
                "analysis_status, nav_rub, rub_cash_total, rub_cash_blocked, rub_cash_unblocked, "
                "limits_loading_in_progress, evidence) "
                "VALUES(%s, %s, 'prod', %s, 'observed', 1000, 0, 0, 0, false, '{}'::jsonb) "
                "RETURNING id", (owner, str(owner), at),
            ).fetchone()
            ids.append(row["id"])
            conn.execute(
                "INSERT INTO portfolio_snapshot_positions (snapshot_id, user_id, instrument_uid, "
                "ticker, instrument_type, quantity, current_price_value, current_price_currency, "
                "blocked, blocked_lots, value_rub) VALUES "
                "(%s, %s, 'held', 'HELD', 'share', 10, 100, 'RUB', false, 0, 1000)",
                (row["id"], owner),
            )
        conn.execute(
            "INSERT INTO portfolio_snapshot_positions (snapshot_id, user_id, instrument_uid, "
            "ticker, instrument_type, quantity, current_price_value, current_price_currency, "
            "blocked, blocked_lots, value_rub) VALUES "
            "(%s, %s, 'sold', 'SOLD', 'share', 1, 100, 'RUB', false, 0, 100)", (ids[0], owner),
        )
        conn.execute(
            "INSERT INTO portfolio_risk_assessments (user_id, snapshot_id, instrument_uid, state, "
            "rating_status, fundamental_status, source_status, reasons, evidence, assessed_at) "
            "VALUES(%s, %s, 'held', 'watch', 'data_missing', 'data_missing', 'partial', "
            "'[]'::jsonb, '{}'::jsonb, %s)", (owner, ids[0], old),
        )
    store = PortfolioStore(database)
    positions = store.portfolio_visualization(owner, now=now)["latest"]["positions"]
    assert positions[0]["risk_state"] == "watch"
    assert positions[0]["assessed_at"] == old
    assert positions[0]["assessment_freshness"] == "stale"
    held = store.instrument_visualization(owner, "held", now=now)
    assert held["latest"]["assessed_at"] == old
    assert held["current_holding"]["status"] == "held"
    sold = store.instrument_visualization(owner, "sold", now=now)
    assert sold["latest"]["quantity"] == 1
    assert sold["current_holding"]["status"] == "not_held"
    assert sold["current_holding"]["quantity"] == "0"
    assert len(sold["history"]) == 1  # No manufactured zero-price history point.
