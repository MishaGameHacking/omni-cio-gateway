"""Hosted payments: fixed hosts, authentic states, idempotency, cents and tenant isolation."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.errors import CheckViolation
from test_workspace_api import HEADERS, OTHER, OWNER
from test_workspace_api import workspace_http as workspace_http
from test_workspace_postgres import DATABASE_URL, user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.billing import (
    BillingConfig,
    BillingOrderNotFound,
    BillingService,
    BillingUnavailable,
    PaymentClient,
    _public,
    checkout_url,
    entitlement_limits,
    payment_token,
)
from omnicio.db import Database
from omnicio.main import app
from omnicio.workspace_store import WorkspaceNotFound


def config() -> BillingConfig:
    return BillingConfig(
        True,
        "synthetic-merchant",
        "test-password",
        12345,
        30,
        "test-offer",
        "Synthetic test period",
        "usn_income",
        "none",
    )


def test_notification_token_hashes_the_documented_field_order_and_boolean_encoding() -> None:
    payload = {
        "TerminalKey": "TBankTest",
        "OrderId": "000000",
        "Success": True,
        "Status": "AUTHORIZED",
        "PaymentId": "0000000",
        "ErrorCode": "0",
        "Amount": "1111",
        "CardId": "000000",
        "Pan": "200000******0000",
        "ExpDate": "1111",
        "RebillId": "000000",
    }
    # Independently hashed documented concatenation, including literal "true".
    assert payment_token(payload, "11111111111") == (
        "10e85f0b78c8f2085881fe689fc47a17fbd528369a3b1d4a5d67422404d88abe"
    )
    assert payment_token(
        {**payload, "Token": "ignored", "Receipt": {"Amount": 4}}, "11111111111"
    ) == payment_token(payload, "11111111111")


def test_offer_version_changes_with_price_and_tax_even_if_operator_label_does_not() -> None:
    cfg = config()
    assert cfg.configured
    assert cfg.offer_key != replace(cfg, amount_kopecks=12346).offer_key
    assert cfg.offer_key != replace(cfg, tax="vat22").offer_key
    assert not BillingConfig().configured
    assert not replace(cfg, tax="").configured


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/checkout",
        "https://securepayments.tinkoff.ru.evil.test/checkout",
        "https://securepayments.tinkoff.ru@evil.test/checkout",
        "http://securepay.tinkoff.ru/pay",
        "https://securepay.tinkoff.ru:444/pay",
        "https://securepay.tinkoff.ru:invalid/pay",
        "https://securepay.tinkoff.ru/a\nb",
        None,
    ],
)
def test_payment_url_cannot_redirect_to_an_untrusted_destination(url: object) -> None:
    with pytest.raises(BillingUnavailable):
        checkout_url(url)


def test_client_uses_signed_bounded_tls_request_and_never_follows_redirect() -> None:
    cfg = config()
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = 200
    response.read.return_value = b'{"Success":true,"Status":"CONFIRMED"}'
    with patch("omnicio.billing.http.client.HTTPSConnection", return_value=connection) as build:
        result = PaymentClient(cfg).call("GetState", {"PaymentId": "42"})
    assert result["Status"] == "CONFIRMED"
    assert build.call_args.args == ("securepay.tinkoff.ru",)
    assert connection.request.call_args.args == ("POST", "/v2/GetState")
    body = json.loads(connection.request.call_args.kwargs["body"])
    assert body["Token"] == payment_token(body, cfg.password)
    assert "Password" not in body
    response.status = 302
    client = PaymentClient(cfg)
    with (
        patch("omnicio.billing.http.client.HTTPSConnection", return_value=connection),
        pytest.raises(BillingUnavailable, match="unknown"),
    ):
        client.call("Init", {"OrderId": "test"})
    disabled = PaymentClient(BillingConfig())
    with pytest.raises(BillingUnavailable, match="not_configured"):
        disabled.call("Init", {})


def test_only_documented_not_found_with_exact_order_identity_is_recoverable_absence() -> None:
    cfg = config()
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = 200
    payload = {"Success": False, "ErrorCode": "63", "OrderId": "synthetic-order",
               "TerminalKey": cfg.terminal_key}
    response.read.return_value = json.dumps(payload).encode()
    client = PaymentClient(cfg)
    with patch("omnicio.billing.http.client.HTTPSConnection", return_value=connection):
        with pytest.raises(BillingOrderNotFound):
            client.call("CheckOrder", {"OrderId": "synthetic-order"})
        for method, document in (("Init", {"OrderId": "synthetic-order"}),
                                 ("CheckOrder", {"OrderId": "other-order"})):
            with pytest.raises(BillingUnavailable) as error:
                client.call(method, document)
            assert not isinstance(error.value, BillingOrderNotFound)
        response.read.return_value = json.dumps({**payload, "ErrorCode": "3"}).encode()
        with pytest.raises(BillingUnavailable) as error:
            client.call("CheckOrder", {"OrderId": "synthetic-order"})
        assert not isinstance(error.value, BillingOrderNotFound)


def test_forged_callbacks_are_rejected_before_tenant_lookup() -> None:
    database = Mock(spec=Database)
    database.pool = Mock()
    service = BillingService(database, config())
    with pytest.raises(PermissionError):
        service.notification(
            {"Token": "a" * 64, "Success": True, "OrderId": "000000501-" + "b" * 32}
        )
    database.pool.connection.assert_not_called()


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_payment_entitlement_needs_exact_provider_confirmation_and_cannot_double_extend(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, _, _ = workspace_database
    owner, other = user(database), user(database)
    cfg = config()
    client = Mock(spec=PaymentClient)
    source: dict[str, Any] = {}

    def provider(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if method == "Init":
            source.update(
                {
                    "TerminalKey": cfg.terminal_key,
                    "OrderId": payload["OrderId"],
                    "Amount": payload["Amount"],
                    "PaymentId": "501",
                    "Success": True,
                }
            )
            assert payload["Receipt"]["Items"][0]["Amount"] == 12345
            assert payload["PayType"] == "O"
            assert "Recurrent" not in payload
            return {
                **source,
                "PaymentURL": "https://securepayments.tinkoff.ru/test",
                "Status": "NEW",
            }
        return {**source, "Status": "CONFIRMED"}

    client.call.side_effect = provider
    service = BillingService(database, cfg, client=client)
    ident = uuid4()
    first = service.checkout(
        owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com"
    )
    second = service.checkout(
        owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com"
    )
    assert first == second
    client.call.assert_called_once()
    assert service.status(owner)["plan"] == "personal"
    assert service.status(other)["payments"] == []
    with pytest.raises(WorkspaceNotFound):
        service.reconcile(other, ident)
    with pytest.raises(ValueError, match="active_or_recent"):
        service.checkout(
            owner, uuid4(), expected_offer=cfg.offer_key, receipt_email="test@example.com"
        )
    service._apply_provider_state(owner, ident, {**source, "Status": "AUTHORIZED"})
    assert service.status(owner)["plan"] == "personal"
    with pytest.raises(BillingUnavailable, match="amount_mismatch"):
        service._apply_provider_state(owner, ident, {**source, "Status": "CONFIRMED", "Amount": 1})
    paid = service.reconcile(owner, ident)
    assert paid["status"] == "paid"
    assert service.status(owner)["plan"] == "premium"
    repeated = service.reconcile(owner, ident)
    assert repeated["entitlement_until"] == paid["entitlement_until"]
    assert (
        paid["entitlement_until"].astimezone(UTC) - paid["entitlement_from"].astimezone(UTC)
    ) == timedelta(days=30)
    source["Status"] = "REFUNDED"
    source["Token"] = payment_token(source, cfg.password)
    service.notification(source)
    assert service.status(owner)["plan"] == "personal"
    service._apply_provider_state(owner, ident, {**source, "Status": "CONFIRMED"})
    assert service.status(owner)["payments"][0]["status"] == "refunded"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_ambiguous_checkout_is_recorded_and_not_automatically_retried(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, _, _ = workspace_database
    owner = user(database)
    client = Mock(spec=PaymentClient)
    client.call.side_effect = BillingUnavailable("billing_provider_outcome_unknown")
    cfg = config()
    service = BillingService(database, cfg, client=client)
    ident = uuid4()
    with pytest.raises(BillingUnavailable):
        service.checkout(
            owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com"
        )
    saved = service.checkout(
        owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com"
    )
    assert saved["status"] == "uncertain"
    assert saved["checkout_url"] is None
    client.call.assert_called_once()


@pytest.mark.parametrize("token", ["я" * 64, "f" * 63, "F" * 64, None, 123])
def test_malformed_signature_cannot_touch_database_or_raise_unicode_error(token: object) -> None:
    database = Mock(spec=Database)
    service = BillingService(database, config())
    with pytest.raises(PermissionError):
        service.notification({"Token": token})
    assert database.mock_calls == []


def test_billing_http_enforces_origin_owner_and_consent_and_discards_late_payload(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, auth, _, database = workspace_http
    billing = Mock(spec=BillingService)
    billing.status.return_value = {"plan": "personal", "payments": []}
    ident = uuid4()
    body = {
        "request_id": str(ident),
        "expected_offer": "a" * 64,
        "receipt_email": "test@example.com",
    }
    with patch.object(app.state, "billing_service", billing, create=True):
        assert client.get("/api/billing?user_id=" + str(OTHER.id)).status_code == 200
        billing.status.assert_called_once_with(OWNER.id)
        for headers, code in (
            ({}, 403),
            ({"origin": HEADERS["origin"]}, 409),
            ({**HEADERS, "X-Omnicio-Profile": "000000502"}, 409),
        ):
            assert (
                client.post("/api/billing/checkout", json=body, headers=headers).status_code == code
            )
        database.has_legal_versions.return_value = False
        assert client.post("/api/billing/checkout", json=body, headers=HEADERS).status_code == 409
        billing.checkout.assert_not_called()
        database.has_legal_versions.return_value = True

        def create(*args: object, **kwargs: object) -> dict[str, str]:
            auth.refresh_session.side_effect = None
            auth.refresh_session.return_value = OTHER
            return {"private_payment": "discard-after-profile-switch"}

        billing.checkout.side_effect = create
        response = client.post("/api/billing/checkout", json=body, headers=HEADERS)
        assert response.status_code == 409
        assert "private_payment" not in response.text
        billing.checkout.assert_called_once_with(
            OWNER.id,
            ident,
            expected_offer="a" * 64,
            receipt_email="test@example.com",
        )


def test_bank_callback_is_bounded_and_signature_authorized_without_browser_session(
    workspace_http: tuple[TestClient, Mock, Mock, Mock],
) -> None:
    client, _, _, _ = workspace_http
    client.cookies.clear()
    billing = Mock(spec=BillingService)
    with patch.object(app.state, "billing_service", billing, create=True):
        assert client.post("/api/billing/notification", content=b"x" * 65537).status_code == 413
        assert client.post("/api/billing/notification", content=b"[").status_code == 422
        billing.notification.assert_not_called()
        billing.notification.side_effect = PermissionError("untrusted-data")
        rejected = client.post("/api/billing/notification", json={"Token": "bad"})
        assert rejected.status_code == 403
        assert "untrusted-data" not in rejected.text
        billing.notification.side_effect = None
        confirmed = client.post("/api/billing/notification", json={"Token": "fixture"})
        assert confirmed.status_code == 200
        assert confirmed.text == "OK"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_out_of_order_partial_refund_never_becomes_a_new_full_entitlement(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, _, _ = workspace_database
    owner = user(database)
    client = Mock(spec=PaymentClient)
    client.call.side_effect = BillingUnavailable("ambiguous")
    cfg = config()
    service = BillingService(database, cfg, client=client)
    ident = uuid4()
    with pytest.raises(BillingUnavailable):
        service.checkout(
            owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com"
        )
    with service.workspace._transaction(owner) as cur:
        cur.execute(
            "SELECT order_id FROM billing_payments WHERE user_id=%s AND id=%s", (owner, ident)
        )
        order = cur.fetchone()["order_id"]
    source = {
        "TerminalKey": cfg.terminal_key,
        "OrderId": order,
        "PaymentId": str(ident.int % 10**15),
        "Amount": 100,
        "Status": "PARTIAL_REFUNDED",
    }
    service._apply_provider_state(owner, ident, source)
    assert service.status(owner)["plan"] == "personal"
    late = service._apply_provider_state(
        owner,
        ident,
        {
            **source,
            "Status": "CONFIRMED",
            "Amount": cfg.amount_kopecks,
        },
    )
    assert late["status"] == "partial_refund"
    assert late["entitlement_until"] is None
    service._apply_provider_state(owner, ident, {**source, "Status": "REFUNDED", "Amount": 0})
    repeated = service._apply_provider_state(owner, ident, source)
    assert repeated["status"] == "refunded"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_lost_cancel_response_is_durable_and_retries_only_reconcile(workspace_database) -> None:
    database = workspace_database[0]
    owner, other = user(database), user(database)
    cfg, ident = config(), uuid4()
    client = Mock(spec=PaymentClient)
    service = BillingService(database, cfg, client=client)
    source = {
        "TerminalKey": cfg.terminal_key,
        "PaymentId": str(ident.int % 10**15),
        "Amount": cfg.amount_kopecks,
        "Status": "NEW",
        "Success": True,
    }
    calls = []

    def provider(method, payload):
        calls.append(method)
        if method == "Init":
            source["OrderId"] = payload["OrderId"]
            return {**source, "PaymentURL": "https://securepayments.tinkoff.ru/test"}
        if method == "Cancel":
            # This second real transaction must observe a committed receipt
            # before transport starts, not an in-memory flag or uncommitted row.
            with service.workspace._transaction(owner) as cur:
                cur.execute(
                    "SELECT cancel_attempted_at, status FROM billing_payments "
                    "WHERE user_id=%s AND id=%s",
                    (owner, ident),
                )
                row = cur.fetchone()
                assert row["cancel_attempted_at"] is not None
                assert row["status"] == "uncertain"
            raise BillingUnavailable("billing_provider_outcome_unknown")
        assert method == "GetState"
        return dict(source)

    client.call.side_effect = provider
    service.checkout(owner, ident, expected_offer=cfg.offer_key, receipt_email="test@example.com")
    with pytest.raises(WorkspaceNotFound):
        service.cancel(other, ident)
    assert calls == ["Init"]
    with pytest.raises(BillingUnavailable, match="unknown"):
        service.cancel(owner, ident)
    uncertain = service.status(owner)["payments"][0]
    assert uncertain["cancel_attempted_at"] is not None
    for _ in range(2):
        pending = service.cancel(owner, ident)
        assert pending["status"] == "pending"
        assert pending["cancel_attempted_at"] == uncertain["cancel_attempted_at"]
    assert calls.count("Cancel") == 1
    source["Status"] = "CANCELED"
    assert service.cancel(owner, ident)["status"] == "cancelled"
    assert calls.count("Cancel") == 1
    # Nullable SQL comparisons must not accept an incomplete entitlement.
    with pytest.raises(CheckViolation), service.workspace._transaction(owner) as cur:
        cur.execute(
            "UPDATE billing_payments SET entitlement_from = now(), "
            "entitlement_until = NULL WHERE user_id=%s AND id=%s",
            (owner, ident),
        )


def test_expired_and_uncertain_payment_links_are_not_offered_for_payment() -> None:
    now = datetime.now(UTC)
    row = {"status": "pending", "checkout_url": "https://securepayments.tinkoff.ru/test",
           "checkout_expires_at": now - timedelta(seconds=1)}
    assert _public(row)["checkout_url"] is None
    row["checkout_expires_at"] = now + timedelta(minutes=10)
    assert _public(row)["checkout_url"] == row["checkout_url"]
    row["status"] = "uncertain"
    assert _public(row)["checkout_url"] is None


@pytest.mark.parametrize("explicit_not_found", [False, True])
def test_absence_observation_uses_check_order_request_start(explicit_not_found: bool) -> None:
    owner, ident, cfg = uuid4(), uuid4(), config()
    remote = Mock(spec=PaymentClient)
    billing = BillingService(Mock(spec=Database), cfg, client=remote)
    cur = Mock()
    cur.fetchone.return_value = {
        "status": "uncertain", "resolution": None, "init_started_at": datetime.now(UTC),
        "provider_payment_id": None, "terminal_key": cfg.terminal_key, "order_id": "test-order",
    }
    started = datetime(2026, 10, 7, 10, tzinfo=UTC)
    with (
        patch.object(billing.workspace, "_transaction", return_value=nullcontext(cur)),
        patch.object(billing, "_reconcile_absent_order", return_value={"status": "uncertain"})
        as absent,
        patch("omnicio.billing.datetime") as clock,
    ):
        clock.now.return_value = started

        def delayed_response(method: str, payload: dict[str, Any]) -> dict[str, Any]:
            assert method == "CheckOrder"
            clock.now.return_value = started + timedelta(minutes=2)
            if explicit_not_found:
                raise BillingOrderNotFound("billing_order_not_found")
            return {"TerminalKey": cfg.terminal_key, "OrderId": payload["OrderId"],
                    "Success": True, "Payments": []}

        remote.call.side_effect = delayed_response
        assert billing.reconcile(owner, ident) == {"status": "uncertain"}
        absent.assert_called_once_with(owner, ident, request_started_at=started)


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_process_stopped_before_init_can_close_without_bank_io_and_cannot_resume_sender(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, other = user(database), user(database)
    cfg, ident = config(), uuid4()
    remote = Mock(spec=PaymentClient)
    billing = BillingService(database, cfg, client=remote)
    with (
        patch.object(billing, "_claim_initialization", side_effect=SystemExit("synthetic-crash")),
        pytest.raises(SystemExit),
    ):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    remote.call.assert_not_called()
    with pytest.raises(WorkspaceNotFound):
        billing.reconcile(other, ident)
    closed = billing.reconcile(owner, ident)
    assert closed["status"] == "cancelled"
    assert closed["resolution"] == "initialization_not_started"
    assert closed["init_started_at"] is None
    # A suspended original request resumes after this independent reconciliation.
    _, should_send = billing._claim_initialization(owner, ident)
    assert should_send is False
    assert billing.cancel(owner, ident) == closed
    assert billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                            receipt_email="test@example.com") == closed
    remote.call.assert_not_called()


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_ambiguous_init_recovers_only_after_expired_link_and_repeated_empty_bank_observation(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, cfg, ident = user(database), config(), uuid4()
    calls: list[str] = []
    bank_order: dict[str, Any] = {}
    billing = BillingService(database, cfg, client=Mock(spec=PaymentClient))

    def remote(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(method)
        if method == "Init":
            bank_order.update(OrderId=payload["OrderId"], TerminalKey=cfg.terminal_key)
            # The receipt is durable before the transport starts.
            with billing.workspace._transaction(owner) as cur:
                cur.execute("SELECT init_started_at, checkout_expires_at FROM billing_payments "
                            "WHERE user_id=%s AND id=%s", (owner, ident))
                row = cur.fetchone()
            assert row["init_started_at"] is not None
            assert datetime.fromisoformat(payload["RedirectDueDate"]) <= row["checkout_expires_at"]
            raise BillingUnavailable("synthetic-ambiguous-init")
        assert method == "CheckOrder"
        return {**bank_order, "Success": True, "ErrorCode": "0", "Payments": []}

    billing.client.call.side_effect = remote
    with pytest.raises(BillingUnavailable):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    pending = billing.reconcile(owner, ident)
    assert pending["status"] == "uncertain"
    assert pending["resolution"] is None
    assert pending["recovery_not_before"] is not None
    with pytest.raises(ValueError, match="active_or_recent"):
        billing.checkout(owner, uuid4(), expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    with billing.workspace._transaction(owner) as cur:
        cur.execute("UPDATE billing_payments SET created_at=now()-interval '2 hours', "
                    "checkout_expires_at=now()-interval '1 minute' WHERE user_id=%s AND id=%s",
                    (owner, ident))
    first = billing.reconcile(owner, ident)
    assert first["status"] == "uncertain"
    assert first["recovery_not_before"] > datetime.now(UTC)
    assert billing.reconcile(owner, ident)["status"] == "uncertain"
    with billing.workspace._transaction(owner) as cur:
        cur.execute("UPDATE billing_payments SET absence_checked_at=now()-interval '61 seconds' "
                    "WHERE user_id=%s AND id=%s", (owner, ident))
    closed = billing.cancel(owner, ident)
    assert closed["status"] == "cancelled"
    assert closed["resolution"] == "provider_order_absent"
    assert calls.count("Init") == 1
    assert "Cancel" not in calls
    assert billing.status(owner)["plan"] == "personal"

    def next_order(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert method == "Init"
        return {"Success": True, "TerminalKey": cfg.terminal_key, "OrderId": payload["OrderId"],
                "Amount": cfg.amount_kopecks, "PaymentId": "91234567", "Status": "NEW",
                "PaymentURL": "https://securepayments.tinkoff.ru/test"}

    billing.client.call.side_effect = next_order
    assert billing.checkout(owner, uuid4(), expected_offer=cfg.offer_key,
                            receipt_email="test@example.com")["status"] == "pending"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_empty_order_read_cannot_override_a_concurrent_confirmed_payment(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, cfg, ident = user(database), config(), uuid4()
    remote = Mock(spec=PaymentClient)
    remote.call.side_effect = BillingUnavailable("synthetic-timeout")
    billing = BillingService(database, cfg, client=remote)
    with pytest.raises(BillingUnavailable):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")

    def confirmed_during_read(method: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert method == "CheckOrder"
        state = {"TerminalKey": cfg.terminal_key, "OrderId": payload["OrderId"], "Success": True,
                 "PaymentId": "9812345", "Amount": cfg.amount_kopecks, "Status": "CONFIRMED"}
        billing._apply_provider_state(owner, ident, state)
        return {"TerminalKey": cfg.terminal_key, "OrderId": payload["OrderId"],
                "Success": True, "Payments": []}

    remote.call.side_effect = confirmed_during_read
    assert billing.reconcile(owner, ident)["status"] == "paid"
    assert billing.status(owner)["entitlements"]["research_runs"] == 400


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_wrong_order_empty_response_is_not_absence_proof(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, cfg, ident = user(database), config(), uuid4()
    remote = Mock(spec=PaymentClient)
    remote.call.side_effect = BillingUnavailable("synthetic-timeout")
    billing = BillingService(database, cfg, client=remote)
    with pytest.raises(BillingUnavailable):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    remote.call.side_effect = None
    remote.call.return_value = {"TerminalKey": cfg.terminal_key, "OrderId": "wrong-order",
                                "Success": True, "Payments": []}
    with pytest.raises(BillingUnavailable, match="identity_invalid"):
        billing.reconcile(owner, ident)
    assert billing.status(owner)["payments"][0]["status"] == "uncertain"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_recovery_migration_reapply_preserves_new_unsent_intents_and_old_writer_defaults(
    workspace_database: tuple[Database, str, str],
) -> None:
    database, dsn, schema = workspace_database
    owner, cfg, ident = user(database), config(), uuid4()
    billing = BillingService(database, cfg, client=Mock(spec=PaymentClient))
    with (
        patch.object(billing, "_claim_initialization", side_effect=SystemExit("synthetic-crash")),
        pytest.raises(SystemExit),
    ):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    migration = Path(__file__).resolve().parents[1] / "migrations" / "0025_billing_recovery.sql"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
        admin.execute(migration.read_text())
    assert billing.status(owner)["payments"][0]["init_started_at"] is None
    legacy = uuid4()
    with billing.workspace._transaction(owner) as cur:
        cur.execute("SELECT order_id FROM billing_payments WHERE user_id=%s AND id=%s",
                    (owner, ident))
        order = cur.fetchone()["order_id"][:10] + legacy.hex
        # Exact pre-1.2 insert shape must remain conservatively classified.
        cur.execute("INSERT INTO billing_payments (user_id,id,order_id,terminal_key,"
                    "amount_kopecks,period_days,offer_version,status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,'creating') RETURNING init_started_at",
                    (owner, legacy, order, cfg.terminal_key, 12345, 30, cfg.offer_key))
        assert cur.fetchone()["init_started_at"] is not None


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_populated_billing_upgrade_obeys_force_rls_for_active_and_inactive_tenants(
    workspace_database: tuple[Database, str, str],
) -> None:
    _, dsn, _ = workspace_database
    schema = "billing_upgrade_" + uuid4().hex[:12]
    role = schema + "_owner"
    root = Path(__file__).resolve().parents[1]
    tenants = [uuid4(), uuid4()]
    old_rows: dict[Any, tuple[Any, Any, int]] = {}
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        admin.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                              "NOREPLICATION NOBYPASSRLS").format(sql.Identifier(role)))
        try:
            admin.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            for migration in sorted((root / "migrations").glob("*.sql")):
                if migration.name[:4] <= "0024":
                    admin.execute(migration.read_text())
            for tenant, status in zip(tenants, ("active", "blocked"), strict=True):
                public_id = admin.execute(
                    "INSERT INTO users(id,status) VALUES(%s,%s) RETURNING public_id",
                    (tenant, status),
                ).fetchone()[0]
                ident = uuid4()
                created = admin.execute(
                    "INSERT INTO billing_payments(user_id,id,order_id,terminal_key,amount_kopecks,"
                    "period_days,offer_version,status) "
                    "VALUES(%s,%s,%s,'test',12345,30,%s,'creating') "
                    "RETURNING created_at",
                    (tenant, ident, f"{public_id:09d}-{ident.hex}", "a" * 64),
                ).fetchone()[0]
                old_rows[tenant] = (ident, created, public_id)
            admin.execute(sql.SQL("GRANT USAGE,CREATE ON SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(role)))
            admin.execute(sql.SQL("GRANT SELECT ON users TO {}").format(sql.Identifier(role)))
            admin.execute(sql.SQL("ALTER TABLE billing_payments OWNER TO {}").format(
                sql.Identifier(role)))
            admin.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            assert admin.execute("SELECT rolsuper,rolbypassrls FROM pg_roles "
                                 "WHERE rolname=current_user").fetchone() == (False, False)
            admin.execute("SELECT set_config('omnicio.user_id','',false)")
            assert admin.execute("SELECT count(*) FROM billing_payments").fetchone()[0] == 0
            migration = (root / "migrations" / "0025_billing_recovery.sql").read_text()
            admin.execute(migration)
            for tenant, (ident, created, _) in old_rows.items():
                admin.execute("SELECT set_config('omnicio.user_id',%s,false)", (str(tenant),))
                observed = admin.execute(
                    "SELECT init_started_at,checkout_expires_at FROM billing_payments WHERE id=%s",
                    (ident,),
                ).fetchone()
                assert observed == (created, created + timedelta(days=90))
            tenant = tenants[0]
            admin.execute("SELECT set_config('omnicio.user_id',%s,false)", (str(tenant),))
            new = uuid4()
            admin.execute(
                "INSERT INTO billing_payments(user_id,id,order_id,terminal_key,amount_kopecks,"
                "period_days,offer_version,status,init_started_at) "
                "VALUES(%s,%s,%s,'test',12345,30,%s,'creating',NULL)",
                (tenant, new, f"{old_rows[tenant][2]:09d}-{new.hex}", "a" * 64),
            )
            admin.execute(migration)
            assert admin.execute("SELECT init_started_at FROM billing_payments WHERE id=%s",
                                 (new,)).fetchone()[0] is None
        finally:
            if admin.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                admin.execute("ROLLBACK")
            admin.execute("RESET ROLE")
            admin.execute("SELECT set_config('omnicio.user_id','',false)")
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_paid_archive_capacity_expires_and_refund_revokes_only_extra_capacity(
    workspace_database: tuple[Database, str, str],
) -> None:
    from omnicio.research_store import ResearchStore

    database = workspace_database[0]
    owner, other, cfg, ident = user(database), user(database), config(), uuid4()
    remote = Mock(spec=PaymentClient)
    remote.call.side_effect = BillingUnavailable("synthetic-timeout")
    billing = BillingService(database, cfg, client=remote)
    with pytest.raises(BillingUnavailable):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    with billing.workspace._transaction(owner) as cur:
        cur.execute("SELECT order_id FROM billing_payments WHERE user_id=%s AND id=%s",
                    (owner, ident))
        order = cur.fetchone()["order_id"]
    state = {"TerminalKey": cfg.terminal_key, "OrderId": order, "PaymentId": "31231234",
             "Amount": cfg.amount_kopecks, "Status": "CONFIRMED"}
    billing._apply_provider_state(owner, ident, state)
    archive = ResearchStore(database)
    assert archive.capacity(owner)["runs_limit"] == 400
    assert archive.capacity(owner)["storage_limit_bytes"] == 512 * 1024 * 1024
    assert archive.capacity(other)["runs_limit"] == 200
    with billing.workspace._transaction(owner) as cur:
        cur.execute("UPDATE billing_payments SET entitlement_from=now()-interval '31 days', "
                    "entitlement_until=now()-interval '1 hour' WHERE user_id=%s AND id=%s",
                    (owner, ident))
    assert archive.capacity(owner)["runs_limit"] == 200
    # A delayed repeated paid state never extends the already granted period.
    billing._apply_provider_state(owner, ident, state)
    assert archive.capacity(owner)["runs_limit"] == 200
    billing._apply_provider_state(owner, ident, {**state, "Status": "REFUNDED", "Amount": 0})
    assert billing.status(owner)["entitlements"]["plan"] == "personal"


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_stale_inflight_empty_read_cannot_supply_post_deadline_or_second_confirmation(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, cfg, ident = user(database), config(), uuid4()
    remote = Mock(spec=PaymentClient)
    remote.call.side_effect = BillingUnavailable("synthetic-timeout")
    billing = BillingService(database, cfg, client=remote)
    with pytest.raises(BillingUnavailable):
        billing.checkout(owner, ident, expected_offer=cfg.offer_key,
                         receipt_email="test@example.com")
    now = datetime.now(UTC)
    with billing.workspace._transaction(owner) as cur:
        cur.execute("UPDATE billing_payments SET created_at=%s, checkout_expires_at=%s "
                    "WHERE user_id=%s AND id=%s",
                    (now - timedelta(hours=2), now - timedelta(minutes=3), owner, ident))
    billing._reconcile_absent_order(
        owner, ident, request_started_at=now - timedelta(minutes=4),
    )
    with billing.workspace._transaction(owner) as cur:
        cur.execute("SELECT absence_checked_at FROM billing_payments WHERE user_id=%s AND id=%s",
                    (owner, ident))
        assert cur.fetchone()["absence_checked_at"] is None
        cur.execute("UPDATE billing_payments SET absence_checked_at=%s WHERE user_id=%s AND id=%s",
                    (now - timedelta(seconds=61), owner, ident))
    delayed = billing._reconcile_absent_order(
        owner, ident, request_started_at=now - timedelta(minutes=2),
    )
    assert delayed["status"] == "uncertain"
    assert delayed["resolution"] is None
    fresh = billing._reconcile_absent_order(owner, ident, request_started_at=datetime.now(UTC))
    assert fresh["status"] == "cancelled"
    assert fresh["resolution"] == "provider_order_absent"
    assert remote.call.call_count == 1


@pytest.mark.skipif(not DATABASE_URL, reason="ephemeral PostgreSQL is required")
def test_entitlement_expired_during_transaction_wait_does_not_grant_extra_capacity(
    workspace_database: tuple[Database, str, str],
) -> None:
    database = workspace_database[0]
    owner, cfg, ident = user(database), config(), uuid4()
    billing = BillingService(database, cfg, client=Mock(spec=PaymentClient))
    with billing.workspace._transaction(owner) as cur:
        # PostgreSQL now() remains at transaction start, including owner-lock waits.
        cur.execute("SELECT now(), pg_sleep(0.02)")
        cur.execute("SELECT public_id FROM users WHERE id=%s", (owner,))
        order = f"{cur.fetchone()['public_id']:09d}-{ident.hex}"
        cur.execute(
            "INSERT INTO billing_payments(user_id,id,order_id,terminal_key,amount_kopecks,"
            "period_days,offer_version,status,entitlement_from,entitlement_until) "
            "VALUES(%s,%s,%s,%s,12345,30,%s,'paid',now()-interval '1 day',"
            "clock_timestamp()-interval '1 millisecond') "
            "RETURNING now() < entitlement_until AS was_active, "
            "clock_timestamp() > entitlement_until AS is_expired",
            (owner, ident, order, cfg.terminal_key, cfg.offer_key),
        )
        assert cur.fetchone() == {"was_active": True, "is_expired": True}
        assert entitlement_limits(cur, owner)["plan"] == "personal"
