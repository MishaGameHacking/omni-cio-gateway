from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from .client_v1 import SandboxApiFailure, SandboxRestClientV1


DEFAULT_CONFIRMATION_TTL_SECONDS = 120
MAX_CONFIRMATION_TTL_SECONDS = 600
SANDBOX_CANCEL_CONFIRMATION = "ПОДТВЕРЖДАЮ ОТМЕНУ SANDBOX"
SANDBOX_FUND_CONFIRMATION = "ПОДТВЕРЖДАЮ ПОПОЛНЕНИЕ ПЕСОЧНИЦЫ"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def mask_account_id(account_id: str) -> str:
    value = str(account_id or "").strip()
    if not value:
        return "***"
    return f"***{value[-4:]}"


def _json_dump(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).replace("_", "").lower()
            if normalized == "accountid":
                result[str(key)] = mask_account_id(str(item or ""))
            else:
                result[str(key)] = _sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


def sanitized_json(payload: Any) -> str:
    return _json_dump(_sanitize_payload(payload))


def decimal_from_text(value: str) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise SandboxApiFailure(
            code="INVALID_DECIMAL",
            message="Decimal value is invalid.",
            http_status=400,
        ) from exc
    if not result.is_finite():
        raise SandboxApiFailure(
            code="INVALID_DECIMAL",
            message="Decimal value must be finite.",
            http_status=400,
        )
    return result


def decimal_to_quotation(value: Decimal) -> dict[str, Any]:
    if value <= 0:
        raise SandboxApiFailure(
            code="INVALID_PRICE",
            message="Price must be positive.",
            http_status=400,
        )
    quantized = value.quantize(Decimal("0.000000001"))
    units = int(quantized)
    nano = int((quantized - Decimal(units)) * Decimal("1000000000"))
    return {"units": str(units), "nano": nano}


def decimal_to_money(value: Decimal, currency: str = "RUB") -> dict[str, Any]:
    quotation = decimal_to_quotation(value)
    return {"currency": currency.upper(), **quotation}


def _enum_status(account: dict[str, Any]) -> str:
    return str(account.get("status") or "").upper()


def _account_id(account: dict[str, Any]) -> str:
    return str(account.get("id") or account.get("accountId") or "").strip()


def _integer_field(container: Any, field: str) -> int | None:
    if not isinstance(container, dict):
        return None
    value = container.get(field)
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class TradeProposalV1:
    proposal_id: str
    order_id: str
    account_id: str
    instrument_id: str
    direction: str
    quantity_lots: int
    order_type: str
    limit_price: str | None
    price_type: str
    rationale: str
    created_at: datetime
    expires_at: datetime
    confirmation_code: str
    state: str = "prepared"
    broker_response_json: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None

    @property
    def confirmation_phrase(self) -> str:
        return f"ПОДТВЕРЖДАЮ SANDBOX {self.confirmation_code}"


class ProposalStoreV1:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, TradeProposalV1] = {}

    def put(self, proposal: TradeProposalV1) -> None:
        with self._lock:
            if proposal.proposal_id in self._items:
                raise RuntimeError("duplicate proposal id")
            self._items[proposal.proposal_id] = proposal

    def get(self, proposal_id: str) -> TradeProposalV1:
        with self._lock:
            proposal = self._items.get(proposal_id)
            if proposal is None:
                raise SandboxApiFailure(
                    code="SANDBOX_PROPOSAL_NOT_FOUND",
                    message="Sandbox proposal was not found in this runtime.",
                    http_status=404,
                )
            return proposal

    def transition(
        self,
        proposal_id: str,
        *,
        allowed_from: frozenset[str],
        state: str,
        **changes: Any,
    ) -> TradeProposalV1:
        with self._lock:
            current = self._items.get(proposal_id)
            if current is None:
                raise SandboxApiFailure(
                    code="SANDBOX_PROPOSAL_NOT_FOUND",
                    message="Sandbox proposal was not found in this runtime.",
                    http_status=404,
                )
            if current.state not in allowed_from:
                raise SandboxApiFailure(
                    code="SANDBOX_PROPOSAL_STATE_CONFLICT",
                    message=f"Proposal state is {current.state}.",
                    http_status=409,
                )
            updated = replace(current, state=state, **changes)
            self._items[proposal_id] = updated
            return updated


class SandboxTradingServiceV1:
    def __init__(
        self,
        *,
        token: str,
        gateway_secret: str,
        confirmation_ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS,
        client: SandboxRestClientV1 | None = None,
        store: ProposalStoreV1 | None = None,
    ) -> None:
        if not 30 <= confirmation_ttl_seconds <= MAX_CONFIRMATION_TTL_SECONDS:
            raise SandboxApiFailure(
                code="SANDBOX_CONFIRMATION_TTL_INVALID",
                message="Confirmation TTL must be between 30 and 600 seconds.",
                http_status=500,
            )
        secret = gateway_secret.strip()
        if not secret:
            raise SandboxApiFailure(
                code="GATEWAY_SECRET_NOT_CONFIGURED",
                message="GATEWAY_API_KEY is required for confirmation binding.",
                http_status=503,
            )
        self._client = client or SandboxRestClientV1(token)
        self._store = store or ProposalStoreV1()
        self._ttl = confirmation_ttl_seconds
        self._confirmation_key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-sandbox-confirmation-v1",
            hashlib.sha256,
        ).digest()

    def get_accounts(self) -> list[dict[str, Any]]:
        payload = self._client.post(
            "GetSandboxAccounts",
            {"status": "ACCOUNT_STATUS_OPEN"},
        )
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            raise SandboxApiFailure(
                code="SANDBOX_ACCOUNTS_RESPONSE_INVALID",
                message="Sandbox accounts response does not contain an accounts list.",
                http_status=502,
            )
        result = [item for item in accounts if isinstance(item, dict)]
        return [
            item
            for item in result
            if _enum_status(item) in {"", "ACCOUNT_STATUS_OPEN"}
        ]

    def resolve_single_account(self) -> tuple[str, dict[str, Any]]:
        accounts = self.get_accounts()
        if not accounts:
            raise SandboxApiFailure(
                code="NO_OPEN_SANDBOX_ACCOUNT",
                message="No open T-Invest Sandbox account is available.",
                http_status=404,
            )
        if len(accounts) != 1:
            raise SandboxApiFailure(
                code="MULTIPLE_OPEN_SANDBOX_ACCOUNTS",
                message=(
                    "Exactly one open Sandbox account is required for "
                    "autonomous routing."
                ),
                http_status=409,
            )
        account = accounts[0]
        account_id = _account_id(account)
        if not account_id:
            raise SandboxApiFailure(
                code="SANDBOX_ACCOUNT_ID_MISSING",
                message="Sandbox account response has no account id.",
                http_status=502,
            )
        return account_id, account

    def status(self) -> dict[str, Any]:
        accounts = self.get_accounts()
        return {
            "status": "ok",
            "mode": "sandbox",
            "real_money": False,
            "sandbox_host": self._client.base_url,
            "account_count": len(accounts),
            "accounts": [
                {
                    "masked_account": mask_account_id(_account_id(account)),
                    "name": str(account.get("name") or ""),
                    "status": str(account.get("status") or ""),
                }
                for account in accounts
            ],
        }

    def open_account(self, name: str) -> dict[str, Any]:
        existing = self.get_accounts()
        if existing:
            return {
                "status": "already_open",
                "masked_account": mask_account_id(_account_id(existing[0])),
                "account_count": len(existing),
            }
        payload = self._client.post(
            "OpenSandboxAccount",
            {"name": name[:100]},
        )
        account_id = str(
            payload.get("accountId") or payload.get("account_id") or ""
        )
        if not account_id:
            raise SandboxApiFailure(
                code="SANDBOX_OPEN_ACCOUNT_RESPONSE_INVALID",
                message="OpenSandboxAccount returned no account id.",
                http_status=502,
            )
        return {
            "status": "opened",
            "masked_account": mask_account_id(account_id),
            "account_count": 1,
        }

    def fund_account(self, amount_rub: Decimal) -> dict[str, Any]:
        if amount_rub <= 0 or amount_rub > Decimal("10000000"):
            raise SandboxApiFailure(
                code="SANDBOX_PAYIN_AMOUNT_INVALID",
                message=(
                    "Sandbox pay-in must be greater than 0 and at most "
                    "10,000,000 RUB."
                ),
                http_status=400,
            )
        account_id, _ = self.resolve_single_account()
        payload = self._client.post(
            "SandboxPayIn",
            {
                "accountId": account_id,
                "amount": decimal_to_money(amount_rub, "RUB"),
            },
        )
        return {
            "status": "funded",
            "masked_account": mask_account_id(account_id),
            "amount_rub": format(amount_rub, "f"),
            "broker_response_json": sanitized_json(payload),
        }

    def portfolio(self) -> dict[str, Any]:
        account_id, _ = self.resolve_single_account()
        portfolio = self._client.post(
            "GetSandboxPortfolio",
            {"accountId": account_id, "currency": "RUB"},
        )
        positions = self._client.post(
            "GetSandboxPositions",
            {"accountId": account_id},
        )
        return {
            "status": "ok",
            "masked_account": mask_account_id(account_id),
            "portfolio_json": sanitized_json(portfolio),
            "positions_json": sanitized_json(positions),
        }

    def _confirmation_code(self, canonical: str) -> str:
        digest = hmac.new(
            self._confirmation_key,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest[:10].upper()

    def _preflight(
        self,
        *,
        account_id: str,
        instrument_id: str,
        direction: str,
        quantity_lots: int,
        order_type: str,
        quotation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        max_lots_payload: dict[str, Any] = {
            "accountId": account_id,
            "instrumentId": instrument_id,
        }
        if quotation is not None:
            max_lots_payload["price"] = quotation
        max_lots = self._client.post("GetSandboxMaxLots", max_lots_payload)

        if direction == "BUY":
            buy_limits = max_lots.get("buyLimits")
            limit_field = (
                "buyMaxMarketLots" if order_type == "MARKET" else "buyMaxLots"
            )
            available_lots = _integer_field(buy_limits, limit_field)
            if available_lots is None and order_type == "MARKET":
                available_lots = _integer_field(buy_limits, "buyMaxLots")
        else:
            available_lots = _integer_field(
                max_lots.get("sellLimits"),
                "sellMaxLots",
            )

        if available_lots is None:
            raise SandboxApiFailure(
                code="SANDBOX_LIMITS_INCOMPLETE",
                message=(
                    "GetSandboxMaxLots did not return the required own-funds/"
                    "own-position limit. Submission is blocked."
                ),
                http_status=409,
            )
        if quantity_lots > available_lots:
            raise SandboxApiFailure(
                code="SANDBOX_QUANTITY_EXCEEDS_LIMIT",
                message=(
                    f"Requested {quantity_lots} lots but Sandbox reports only "
                    f"{available_lots} available without margin."
                ),
                http_status=409,
            )

        preview: dict[str, Any] | None = None
        if quotation is not None:
            preview = self._client.post(
                "GetSandboxOrderPrice",
                {
                    "accountId": account_id,
                    "instrumentId": instrument_id,
                    "price": quotation,
                    "direction": f"ORDER_DIRECTION_{direction}",
                    "quantity": str(quantity_lots),
                },
            )
        return {
            "available_lots": available_lots,
            "max_lots": _sanitize_payload(max_lots),
            "order_price": _sanitize_payload(preview) if preview is not None else None,
        }

    def prepare_trade(
        self,
        *,
        instrument_id: str,
        direction: str,
        quantity_lots: int,
        order_type: str,
        limit_price: str | None,
        price_type: str,
        rationale: str,
        now: datetime | None = None,
    ) -> TradeProposalV1:
        instrument_id = instrument_id.strip()
        if not instrument_id or len(instrument_id) > 120:
            raise SandboxApiFailure(
                code="SANDBOX_INSTRUMENT_ID_INVALID",
                message="instrument_id must contain 1..120 characters.",
                http_status=400,
            )
        direction = direction.upper()
        order_type = order_type.upper()
        price_type = price_type.upper()
        if direction not in {"BUY", "SELL"}:
            raise SandboxApiFailure(
                "SANDBOX_DIRECTION_INVALID",
                "Direction must be BUY or SELL.",
                400,
            )
        if order_type not in {"MARKET", "LIMIT"}:
            raise SandboxApiFailure(
                "SANDBOX_ORDER_TYPE_INVALID",
                "Order type must be MARKET or LIMIT.",
                400,
            )
        if price_type not in {"CURRENCY", "POINT"}:
            raise SandboxApiFailure(
                "SANDBOX_PRICE_TYPE_INVALID",
                "Price type must be CURRENCY or POINT.",
                400,
            )
        if quantity_lots < 1 or quantity_lots > 1_000_000:
            raise SandboxApiFailure(
                "SANDBOX_QUANTITY_INVALID",
                "Quantity lots is outside the allowed range.",
                400,
            )
        rationale = rationale.strip()
        if not rationale:
            raise SandboxApiFailure(
                "SANDBOX_RATIONALE_REQUIRED",
                "A short rationale is required before a trade can be proposed.",
                400,
            )
        if len(rationale) > 1500:
            raise SandboxApiFailure(
                "SANDBOX_RATIONALE_TOO_LONG",
                "Rationale is too long.",
                400,
            )

        quotation: dict[str, Any] | None = None
        normalized_price: str | None = None
        if order_type == "LIMIT":
            if limit_price is None:
                raise SandboxApiFailure(
                    "SANDBOX_LIMIT_PRICE_REQUIRED",
                    "Limit order requires limit_price.",
                    400,
                )
            parsed_price = decimal_from_text(limit_price)
            quotation = decimal_to_quotation(parsed_price)
            normalized_price = format(parsed_price, "f")
        elif limit_price is not None:
            raise SandboxApiFailure(
                "SANDBOX_MARKET_PRICE_FORBIDDEN",
                "Market order must not include limit_price.",
                400,
            )

        account_id, _ = self.resolve_single_account()
        preflight = self._preflight(
            account_id=account_id,
            instrument_id=instrument_id,
            direction=direction,
            quantity_lots=quantity_lots,
            order_type=order_type,
            quotation=quotation,
        )

        created_at = now or utc_now()
        if created_at.tzinfo is None:
            raise SandboxApiFailure(
                "SANDBOX_TIME_INVALID",
                "Timestamp must be timezone-aware.",
                500,
            )
        created_at = created_at.astimezone(timezone.utc)
        expires_at = created_at + timedelta(seconds=self._ttl)
        proposal_id = str(uuid4())
        order_id = str(uuid4())
        canonical = _json_dump(
            {
                "proposal_id": proposal_id,
                "order_id": order_id,
                "account_id": account_id,
                "instrument_id": instrument_id,
                "direction": direction,
                "quantity_lots": quantity_lots,
                "order_type": order_type,
                "limit_price": normalized_price,
                "price_type": price_type,
                "created_at": created_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        )
        proposal = TradeProposalV1(
            proposal_id=proposal_id,
            order_id=order_id,
            account_id=account_id,
            instrument_id=instrument_id,
            direction=direction,
            quantity_lots=quantity_lots,
            order_type=order_type,
            limit_price=normalized_price,
            price_type=price_type,
            rationale=rationale,
            created_at=created_at,
            expires_at=expires_at,
            confirmation_code=self._confirmation_code(canonical),
            broker_response_json=_json_dump(preflight),
        )
        self._store.put(proposal)
        return proposal

    def execute_trade(
        self,
        proposal_id: str,
        confirmation_phrase: str,
        *,
        now: datetime | None = None,
    ) -> tuple[TradeProposalV1, bool]:
        proposal = self._store.get(proposal_id)
        if proposal.state == "executed":
            return proposal, True
        if proposal.state in {"submitting", "unknown"}:
            raise SandboxApiFailure(
                code="SANDBOX_ORDER_SUBMISSION_UNCERTAIN",
                message=(
                    "Submission state is uncertain; query the order by request id "
                    "instead of resubmitting."
                ),
                http_status=409,
                ambiguous_submission=True,
            )
        if proposal.state != "prepared":
            raise SandboxApiFailure(
                code="SANDBOX_PROPOSAL_NOT_EXECUTABLE",
                message=f"Proposal state is {proposal.state}.",
                http_status=409,
            )

        current_time = now or utc_now()
        if current_time.tzinfo is None:
            raise SandboxApiFailure(
                "SANDBOX_TIME_INVALID",
                "Timestamp must be timezone-aware.",
                500,
            )
        current_time = current_time.astimezone(timezone.utc)
        if current_time > proposal.expires_at:
            self._store.transition(
                proposal_id,
                allowed_from=frozenset({"prepared"}),
                state="expired",
            )
            raise SandboxApiFailure(
                code="SANDBOX_CONFIRMATION_EXPIRED",
                message=(
                    "Proposal confirmation window has expired; prepare a fresh trade."
                ),
                http_status=409,
            )
        if not hmac.compare_digest(
            confirmation_phrase.strip().encode("utf-8"),
            proposal.confirmation_phrase.encode("utf-8"),
        ):
            raise SandboxApiFailure(
                code="SANDBOX_CONFIRMATION_MISMATCH",
                message="Exact confirmation phrase is required.",
                http_status=403,
            )

        quotation = (
            decimal_to_quotation(decimal_from_text(proposal.limit_price))
            if proposal.limit_price is not None
            else None
        )
        # Recheck broker limits and preliminary limit-order cost immediately
        # before crossing the submission boundary. A successful prepare call is
        # never treated as durable authorization to submit later.
        self._preflight(
            account_id=proposal.account_id,
            instrument_id=proposal.instrument_id,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            order_type=proposal.order_type,
            quotation=quotation,
        )

        self._store.transition(
            proposal_id,
            allowed_from=frozenset({"prepared"}),
            state="submitting",
        )
        payload: dict[str, Any] = {
            "accountId": proposal.account_id,
            "quantity": str(proposal.quantity_lots),
            "direction": f"ORDER_DIRECTION_{proposal.direction}",
            "orderType": f"ORDER_TYPE_{proposal.order_type}",
            "orderId": proposal.order_id,
            "instrumentId": proposal.instrument_id,
            "timeInForce": "TIME_IN_FORCE_DAY",
            "priceType": f"PRICE_TYPE_{proposal.price_type}",
            "confirmMarginTrade": False,
        }
        if quotation is not None:
            payload["price"] = quotation

        try:
            response = self._client.post("PostSandboxOrder", payload)
        except SandboxApiFailure as exc:
            target_state = "unknown" if exc.ambiguous_submission else "failed"
            self._store.transition(
                proposal_id,
                allowed_from=frozenset({"submitting"}),
                state=target_state,
                failure_code=exc.code,
                failure_message=exc.message,
            )
            raise

        completed = self._store.transition(
            proposal_id,
            allowed_from=frozenset({"submitting"}),
            state="executed",
            broker_response_json=sanitized_json(response),
        )
        return completed, False

    def order_state(self, order_id: str) -> dict[str, Any]:
        UUID(order_id)
        account_id, _ = self.resolve_single_account()
        payload = self._client.post(
            "GetSandboxOrderState",
            {
                "accountId": account_id,
                "orderId": order_id,
                "orderIdType": "ORDER_ID_TYPE_REQUEST",
            },
        )
        return {
            "status": "ok",
            "masked_account": mask_account_id(account_id),
            "order_id": order_id,
            "broker_response_json": sanitized_json(payload),
        }

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        UUID(order_id)
        account_id, _ = self.resolve_single_account()
        payload = self._client.post(
            "CancelSandboxOrder",
            {
                "accountId": account_id,
                "orderId": order_id,
                "orderIdType": "ORDER_ID_TYPE_REQUEST",
            },
        )
        return {
            "status": "cancel_requested",
            "masked_account": mask_account_id(account_id),
            "order_id": order_id,
            "broker_response_json": sanitized_json(payload),
        }
