"""Explicit hosted checkout and verified subscription periods; no automatic debits.

Protocol: https://developer.tbank.ru/eacq/api/init and
https://developer.tbank.ru/eacq/intro/developer/notification . The browser return
URL never grants an entitlement. Only a verified provider state can do that.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import re
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID

from .db import Database
from .notifications import normalize_email
from .security import format_public_id
from .workspace_store import WorkspaceNotFound, WorkspaceStore

_ORIGIN = "https://omnicio.ru"
_HOST = "securepay.tinkoff.ru"
_CHECKOUT_HOSTS = {"securepayments.tinkoff.ru", _HOST}
_TAXES = {"none", "vat0", "vat5", "vat7", "vat10", "vat22",
          "vat105", "vat107", "vat110", "vat122"}
_PUBLIC_PAYMENT_FIELDS = (
    "id", "amount_kopecks", "period_days", "offer_version", "status", "checkout_url",
    "created_at", "updated_at", "entitlement_from", "entitlement_until",
    "cancel_attempted_at",
)


class BillingUnavailable(RuntimeError):
    """Payment is disabled, unconfigured or has an unconfirmed provider outcome."""


@dataclass(frozen=True, slots=True)
class BillingConfig:
    enabled: bool = False
    terminal_key: str = ""
    password: str = ""
    amount_kopecks: int = 0
    period_days: int = 30
    offer_version: str = ""
    description: str = ""
    taxation: str = ""
    tax: str = ""

    @property
    def configured(self) -> bool:
        return bool(
            self.enabled and 1 <= len(self.terminal_key) <= 64 and self.password
            and 1 <= self.amount_kopecks <= 100_000_000 and 1 <= self.period_days <= 366
            and 1 <= len(self.offer_version) <= 64 and 1 <= len(self.description) <= 140
            and self.taxation in {"osn", "usn_income", "usn_income_outcome", "esn", "patent"}
            and self.tax in _TAXES
        )

    @property
    def offer_key(self) -> str:
        payload = [self.offer_version, self.amount_kopecks, self.period_days, self.description,
                   self.terminal_key, self.taxation, self.tax, "RUB"]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def payment_token(payload: Mapping[str, Any], password: str) -> str:
    """Sign primitive root fields in lexical key order, as the provider specifies."""
    values = {key: value for key, value in payload.items()
              if key not in {"Token", "Password"} and value is not None
              and isinstance(value, (str, int, bool))}
    values["Password"] = password
    joined = "".join((str(value).lower() if type(value) is bool else str(value))
                     for _, value in sorted(values.items()))
    return hashlib.sha256(joined.encode()).hexdigest()


def checkout_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2000:
        raise BillingUnavailable("billing_checkout_invalid")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname in _CHECKOUT_HOSTS
                 and not parsed.username and not parsed.password and parsed.port in {None, 443}
                 and not any(ord(char) < 33 for char in value))
    except ValueError as exc:
        raise BillingUnavailable("billing_checkout_invalid") from exc
    if not valid:
        raise BillingUnavailable("billing_checkout_invalid")
    return value


class PaymentClient:
    def __init__(self, config: BillingConfig) -> None:
        self.config = config

    def call(self, method: str, document: Mapping[str, Any]) -> dict[str, Any]:
        if not self.config.configured:
            raise BillingUnavailable("billing_not_configured")
        if method not in {"Init", "GetState", "CheckOrder", "Cancel"}:
            raise ValueError("billing_method_invalid")
        payload = {**document, "TerminalKey": self.config.terminal_key}
        payload["Token"] = payment_token(payload, self.config.password)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        try:
            with closing(http.client.HTTPSConnection(_HOST, timeout=20)) as conn:
                conn.request("POST", "/v2/" + method, body=body,
                             headers={"Content-Type": "application/json"})
                response = conn.getresponse()
                raw = response.read(65_537)
        except (OSError, http.client.HTTPException) as exc:
            raise BillingUnavailable("billing_provider_outcome_unknown") from exc
        if response.status != 200 or len(raw) > 65_536:
            raise BillingUnavailable("billing_provider_outcome_unknown")
        try:
            result = json.loads(raw)
        except ValueError as exc:
            raise BillingUnavailable("billing_provider_outcome_unknown") from exc
        if not isinstance(result, dict) or result.get("Success") is not True:
            raise BillingUnavailable("billing_provider_rejected")
        return result


def _payment_id(value: object) -> str:
    if type(value) not in {str, int} or re.fullmatch(r"\d{1,50}", str(value), re.ASCII) is None:
        raise BillingUnavailable("billing_provider_identity_invalid")
    return str(value)


def _public(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in _PUBLIC_PAYMENT_FIELDS}


def _provider_status(current: str, status: object) -> str:
    """Preserve refund precedence when signed provider observations arrive late."""
    if status in {"REFUNDED", "REVERSED"}:
        return "refunded"
    if status == "PARTIAL_REFUNDED" and current != "refunded":
        return "partial_refund"
    if status == "CONFIRMED" and current not in {"refunded", "partial_refund"}:
        return "paid"
    if (status in {"CANCELED", "REJECTED", "DEADLINE_EXPIRED"}
            and current not in {"paid", "partial_refund", "refunded"}):
        return "cancelled"
    return "pending" if current in {"creating", "uncertain"} else current


class BillingService:
    def __init__(
        self, database: Database, config: BillingConfig, *, client: PaymentClient | None = None,
    ) -> None:
        self.database = database
        self.workspace = WorkspaceStore(database)
        self.config = config
        self.client = client or PaymentClient(config)

    def status(self, user_id: UUID) -> dict[str, Any]:
        with self.workspace._transaction(user_id) as cur:
            cur.execute("SELECT * FROM billing_payments WHERE user_id = %s "
                        "ORDER BY created_at DESC LIMIT 100", (user_id,))
            payments = [dict(row) for row in cur.fetchall()]
        now = datetime.now(UTC)
        active = [row for row in payments if row["status"] in {"paid", "partial_refund"}
                  and row["entitlement_from"] is not None and row["entitlement_until"] is not None
                  and row["entitlement_from"] <= now < row["entitlement_until"]]
        return {
            "configured": self.config.configured, "provider": "tbank_hosted_checkout",
            "plan": "premium" if active else "personal", "automatic_renewal": False,
            "valid_until": max(row["entitlement_until"] for row in active) if active else None,
            "offer": {"version": self.config.offer_key, "description": self.config.description,
                      "amount_kopecks": self.config.amount_kopecks, "currency": "RUB",
                      "period_days": self.config.period_days} if self.config.configured else None,
            "payments": [_public(row) for row in payments],
        }

    def checkout(
        self, user_id: UUID, request_id: UUID, *, expected_offer: str, receipt_email: str,
    ) -> dict[str, Any]:
        if not self.config.configured:
            raise BillingUnavailable("billing_not_configured")
        if expected_offer != self.config.offer_key:
            raise ValueError("billing_offer_changed")
        email = normalize_email(receipt_email)
        with self.workspace._transaction(user_id) as cur:
            cur.execute("SELECT * FROM billing_payments WHERE user_id = %s AND id = %s",
                        (user_id, request_id))
            existing = cur.fetchone()
            if existing is not None:
                return _public(existing)
            cur.execute("SELECT id FROM billing_payments WHERE user_id = %s AND "
                        "((status IN ('paid', 'partial_refund') AND entitlement_until > now()) "
                        "OR status IN ('creating', 'pending', 'uncertain') "
                        "OR created_at > now() - interval '1 minute') LIMIT 1", (user_id,))
            if cur.fetchone() is not None:
                raise ValueError("billing_active_or_recent_payment")
            cur.execute("SELECT public_id FROM users WHERE id = %s", (user_id,))
            order = format_public_id(cur.fetchone()["public_id"]) + "-" + request_id.hex
            cur.execute("INSERT INTO billing_payments (user_id, id, order_id, terminal_key, "
                        "amount_kopecks, period_days, offer_version, status) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,'creating')",
                        (user_id, request_id, order, self.config.terminal_key,
                         self.config.amount_kopecks, self.config.period_days, expected_offer))
        try:
            result = self.client.call("Init", {
                "OrderId": order, "Amount": self.config.amount_kopecks,
                "Description": self.config.description, "PayType": "O",
                "NotificationURL": _ORIGIN + "/api/billing/notification",
                "SuccessURL": _ORIGIN + "/#profile", "FailURL": _ORIGIN + "/#profile",
                "DATA": {"OperationInitiatorType": "0"},
                "Receipt": {"Email": email, "Taxation": self.config.taxation, "Items": [{
                    "Name": self.config.description, "Price": self.config.amount_kopecks,
                    "Quantity": 1, "Amount": self.config.amount_kopecks, "Tax": self.config.tax,
                    "PaymentMethod": "full_payment", "PaymentObject": "service",
                    "MeasurementUnit": "шт",
                }]},
            })
            provider_id = _payment_id(result.get("PaymentId"))
            url = checkout_url(result.get("PaymentURL"))
            if (result.get("OrderId") != order or result.get("Amount") != self.config.amount_kopecks
                    or result.get("TerminalKey") != self.config.terminal_key):
                raise BillingUnavailable("billing_provider_identity_invalid")
        except BillingUnavailable:
            with self.workspace._transaction(user_id) as cur:
                cur.execute("UPDATE billing_payments SET status = 'uncertain', updated_at = now() "
                            "WHERE user_id = %s AND id = %s AND status = 'creating'",
                            (user_id, request_id))
            raise
        with self.workspace._transaction(user_id) as cur:
            cur.execute("UPDATE billing_payments SET provider_payment_id = %s, checkout_url = %s, "
                        "status = CASE WHEN status = 'creating' THEN 'pending' ELSE status END, "
                        "updated_at = now() WHERE user_id = %s AND id = %s "
                        "AND (provider_payment_id IS NULL OR provider_payment_id = %s) RETURNING *",
                        (provider_id, url, user_id, request_id, provider_id))
            row = cur.fetchone()
            if row is None:
                raise BillingUnavailable("billing_provider_identity_invalid")
            return _public(row)

    def _apply_provider_state(
        self, user_id: UUID, ident: UUID, payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        provider_id = _payment_id(payload.get("PaymentId"))
        status = payload.get("Status")
        with self.workspace._transaction(user_id) as cur:
            cur.execute("SELECT * FROM billing_payments WHERE user_id = %s AND id = %s FOR UPDATE",
                        (user_id, ident))
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("billing_payment_not_found")
            if (row["terminal_key"] != self.config.terminal_key
                    or row["provider_payment_id"] not in {None, provider_id}
                    or payload.get("OrderId") != row["order_id"]
                    or payload.get("TerminalKey") != row["terminal_key"]
                    or type(payload.get("Amount")) is not int):
                raise BillingUnavailable("billing_provider_identity_invalid")
            amount = payload["Amount"]
            refunded = status in {"REFUNDED", "REVERSED", "PARTIAL_REFUNDED"}
            if (not refunded and amount != row["amount_kopecks"]
                    or refunded and not 0 <= amount <= row["amount_kopecks"]):
                raise BillingUnavailable("billing_provider_amount_mismatch")
            new = _provider_status(row["status"], status)
            start, end = row["entitlement_from"], row["entitlement_until"]
            if new == "paid" and start is None:
                start = datetime.now(UTC)
                end = start + timedelta(days=row["period_days"])
            cur.execute("UPDATE billing_payments SET provider_payment_id = %s, status = %s, "
                        "entitlement_from = %s, entitlement_until = %s, updated_at = now() "
                        "WHERE user_id = %s AND id = %s RETURNING *",
                        (provider_id, new, start, end, user_id, ident))
            return _public(cur.fetchone())

    def reconcile(self, user_id: UUID, ident: UUID) -> dict[str, Any]:
        with self.workspace._transaction(user_id) as cur:
            cur.execute("SELECT * FROM billing_payments WHERE user_id = %s AND id = %s",
                        (user_id, ident))
            row = cur.fetchone()
            if row is None:
                raise WorkspaceNotFound("billing_payment_not_found")
        if row["provider_payment_id"]:
            result = self.client.call("GetState", {"PaymentId": row["provider_payment_id"]})
        else:
            result = self.client.call("CheckOrder", {"OrderId": row["order_id"]})
            payments = result.get("Payments")
            if (not isinstance(payments, list) or len(payments) != 1
                    or not isinstance(payments[0], dict)):
                raise BillingUnavailable("billing_order_outcome_unknown")
            result = {**payments[0], "OrderId": result.get("OrderId"),
                      "TerminalKey": result.get("TerminalKey")}
        return self._apply_provider_state(user_id, ident, result)

    def cancel(self, user_id: UUID, ident: UUID) -> dict[str, Any]:
        current = self.reconcile(user_id, ident)
        if current["status"] in {"paid", "partial_refund", "refunded"}:
            raise ValueError("billing_payment_already_settled")
        if current["status"] == "cancelled":
            return current
        with self.workspace._transaction(user_id) as cur:
            cur.execute("SELECT * FROM billing_payments "
                        "WHERE user_id = %s AND id = %s FOR UPDATE", (user_id, ident))
            row = cur.fetchone()
            if row is None or row["provider_payment_id"] is None:
                raise BillingUnavailable("billing_order_outcome_unknown")
            # A callback may settle the payment after the preceding provider read.
            if row["status"] in {"paid", "partial_refund", "refunded"}:
                raise ValueError("billing_payment_already_settled")
            if row["status"] == "cancelled" or row["cancel_attempted_at"] is not None:
                # Prior financial I/O is only reconciled, never repeated after an
                # ambiguous transport outcome, even if GetState still says NEW.
                return _public(row)
            provider_id = row["provider_payment_id"]
            cur.execute("UPDATE billing_payments SET cancel_attempted_at = now(), "
                        "status = 'uncertain', updated_at = now() "
                        "WHERE user_id = %s AND id = %s", (user_id, ident))
        # The durable receipt commits before the external financial request.
        self.client.call("Cancel", {"PaymentId": provider_id})
        return self.reconcile(user_id, ident)

    def notification(self, payload: Mapping[str, Any]) -> None:
        if not self.config.configured:
            raise BillingUnavailable("billing_not_configured")
        token = payload.get("Token")
        if (not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{64}", token) is None
                or not hmac.compare_digest(
                token, payment_token(payload, self.config.password))
                or payload.get("TerminalKey") != self.config.terminal_key
                or type(payload.get("Success")) is not bool
                or payload.get("Success") is False and payload.get("Status")
                not in {"CANCELED", "REJECTED", "DEADLINE_EXPIRED"}):
            raise PermissionError("billing_notification_invalid")
        order = payload.get("OrderId")
        if (not isinstance(order, str)
                or re.fullmatch(r"\d{9}-[0-9a-f]{32}", order, re.ASCII) is None):
            raise PermissionError("billing_notification_invalid")
        # The signed merchant order selects a tenant only after signature validation.
        # A browser request never chooses its tenant using this route.
        with self.database.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE public_id = %s AND status = 'active'",
                        (int(order[:9]),))
            user = cast(dict[str, Any] | None, cur.fetchone())
        if user is not None:
            self._apply_provider_state(user["id"], UUID(hex=order[10:]), payload)
