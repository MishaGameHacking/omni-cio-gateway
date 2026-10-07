"""Hosted payments: fixed hosts, authentic states, idempotency, cents and tenant isolation."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import CheckViolation
from test_workspace_api import HEADERS, OTHER, OWNER
from test_workspace_api import workspace_http as workspace_http
from test_workspace_postgres import DATABASE_URL, user
from test_workspace_postgres import workspace_database as workspace_database

from omnicio.billing import (
    BillingConfig,
    BillingService,
    BillingUnavailable,
    PaymentClient,
    checkout_url,
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
    with (
        patch("omnicio.billing.http.client.HTTPSConnection", return_value=connection),
        pytest.raises(BillingUnavailable, match="unknown"),
    ):
        PaymentClient(cfg).call("Init", {"OrderId": "test"})
    with pytest.raises(BillingUnavailable, match="not_configured"):
        PaymentClient(BillingConfig()).call("Init", {})


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
            assert payload["PayType"] == "O" and "Recurrent" not in payload
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
    assert (paid["entitlement_until"] - paid["entitlement_from"]).days == 30
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
    assert saved["status"] == "uncertain" and saved["checkout_url"] is None
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
        assert rejected.status_code == 403 and "untrusted-data" not in rejected.text
        billing.notification.side_effect = None
        confirmed = client.post("/api/billing/notification", json={"Token": "fixture"})
        assert confirmed.status_code == 200 and confirmed.text == "OK"


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
    assert late["status"] == "partial_refund" and late["entitlement_until"] is None
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
