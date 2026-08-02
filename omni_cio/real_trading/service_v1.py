from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from typing import Any, Callable, Literal, Protocol, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from .client_v1 import RealTradingApiFailure, RealTradingRestClientV1
from .journal_v1 import (
    JournalDailyCapExceeded,
    JournalStateConflict,
    RealExecutionJournalV1,
)
from .models_v1 import RealMarketContextV1, RealTradeProposalV1, RealTradingPolicyV1


MOSCOW = ZoneInfo("Europe/Moscow")


class RealBrokerClientV1(Protocol):
    @property
    def base_url(self) -> str: ...

    def post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]: ...


MarketContextProviderV1 = Callable[[str], RealMarketContextV1]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_now(value: datetime | None) -> datetime:
    current = value or utc_now()
    if current.tzinfo is None:
        raise RealTradingApiFailure(
            code="REAL_TIME_INVALID",
            message="Real-trading timestamps must be timezone-aware.",
            http_status=500,
        )
    return current.astimezone(timezone.utc)


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
            elif normalized in {"authorization", "token", "apitoken"}:
                result[str(key)] = "***REDACTED***"
            else:
                result[str(key)] = _sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    return value


def sanitized_json(payload: Any) -> str:
    return _json_dump(_sanitize_payload(payload))


def decimal_from_text(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RealTradingApiFailure(
            code="REAL_DECIMAL_INVALID",
            message="Decimal value is invalid.",
            http_status=400,
        ) from exc
    if not result.is_finite():
        raise RealTradingApiFailure(
            code="REAL_DECIMAL_INVALID",
            message="Decimal value must be finite.",
            http_status=400,
        )
    return result


def decimal_to_quotation(value: Decimal) -> dict[str, Any]:
    if value <= 0:
        raise RealTradingApiFailure(
            code="REAL_PRICE_INVALID",
            message="Limit price must be positive.",
            http_status=400,
        )
    quantized = value.quantize(Decimal("0.000000001"))
    units = int(quantized)
    nano = int((quantized - Decimal(units)) * Decimal("1000000000"))
    return {"units": str(units), "nano": nano}


def _money_value(payload: Any, *, field_name: str) -> tuple[Decimal, str]:
    if not isinstance(payload, dict):
        raise RealTradingApiFailure(
            code="REAL_PREFLIGHT_INCOMPLETE",
            message=f"{field_name} is missing from broker preview.",
            http_status=409,
        )
    units = payload.get("units", "0")
    nano = payload.get("nano", 0)
    currency = str(payload.get("currency") or "").upper()
    try:
        amount = Decimal(str(units)) + Decimal(str(nano)) / Decimal("1000000000")
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise RealTradingApiFailure(
            code="REAL_PREFLIGHT_INCOMPLETE",
            message=f"{field_name} is not a valid MoneyValue.",
            http_status=409,
        ) from exc
    if not amount.is_finite() or amount < 0:
        raise RealTradingApiFailure(
            code="REAL_PREFLIGHT_INCOMPLETE",
            message=f"{field_name} has an invalid amount.",
            http_status=409,
        )
    return amount, currency


def _field(payload: dict[str, Any], camel: str, snake: str) -> Any:
    if camel in payload:
        return payload[camel]
    return payload.get(snake)


def _integer_field(container: Any, camel: str, snake: str) -> int | None:
    if not isinstance(container, dict):
        return None
    value = _field(container, camel, snake)
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _account_id(account: dict[str, Any]) -> str:
    return str(account.get("id") or account.get("accountId") or "").strip()


def _account_status(account: dict[str, Any]) -> str:
    return str(account.get("status") or "").upper()


class RealTradingServiceV1:
    """Isolated core for the future real-money release.

    This class is deliberately not wired into FastAPI/OpenAPI. Production
    enable is forbidden unless a durable journal is provided.
    """

    def __init__(
        self,
        *,
        token: str,
        gateway_secret: str,
        expected_account_id: str,
        policy: RealTradingPolicyV1,
        journal: RealExecutionJournalV1,
        market_context_provider: MarketContextProviderV1,
        client: RealBrokerClientV1 | None = None,
        require_durable_journal: bool = True,
    ) -> None:
        try:
            policy.validate()
        except ValueError as exc:
            raise RealTradingApiFailure(
                code="REAL_TRADING_POLICY_INVALID",
                message=str(exc),
                http_status=503,
            ) from exc
        secret = gateway_secret.strip()
        if not secret:
            raise RealTradingApiFailure(
                code="GATEWAY_SECRET_NOT_CONFIGURED",
                message="Gateway secret is required for confirmation binding.",
                http_status=503,
            )
        account_id = expected_account_id.strip()
        if not account_id:
            raise RealTradingApiFailure(
                code="REAL_EXPECTED_ACCOUNT_REQUIRED",
                message="Expected production account binding is required.",
                http_status=503,
            )
        if require_durable_journal and not journal.durable:
            raise RealTradingApiFailure(
                code="REAL_DURABLE_JOURNAL_REQUIRED",
                message="Real trading requires a durable execution journal.",
                http_status=503,
            )

        self._client = client or RealTradingRestClientV1(token)
        self._expected_account_id = account_id
        self._policy = policy
        self._journal = journal
        self._market_context_provider = market_context_provider
        self._confirmation_key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-real-trading-confirmation-v1",
            hashlib.sha256,
        ).digest()

    def resolve_bound_account(self) -> tuple[str, dict[str, Any]]:
        payload = self._client.post("GetAccounts", {})
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            raise RealTradingApiFailure(
                code="REAL_ACCOUNTS_RESPONSE_INVALID",
                message="Trading token account response is invalid.",
                http_status=502,
            )
        open_accounts = [
            item
            for item in accounts
            if isinstance(item, dict)
            and _account_status(item) in {"", "ACCOUNT_STATUS_OPEN"}
        ]
        if len(open_accounts) != 1:
            raise RealTradingApiFailure(
                code="REAL_ACCOUNT_BINDING_AMBIGUOUS",
                message="Exactly one open account must be visible to the trading token.",
                http_status=409,
            )
        account = open_accounts[0]
        account_id = _account_id(account)
        if not account_id:
            raise RealTradingApiFailure(
                code="REAL_ACCOUNT_ID_MISSING",
                message="Trading token account response has no account id.",
                http_status=502,
            )
        if not hmac.compare_digest(account_id, self._expected_account_id):
            raise RealTradingApiFailure(
                code="REAL_ACCOUNT_BINDING_MISMATCH",
                message="Trading-token account does not match the read-only account.",
                http_status=409,
            )
        return account_id, account

    def _validate_market(
        self,
        instrument_uid: str,
        *,
        now: datetime,
    ) -> RealMarketContextV1:
        market = self._market_context_provider(instrument_uid)
        if market.instrument_uid != instrument_uid:
            raise RealTradingApiFailure(
                code="REAL_INSTRUMENT_IDENTITY_MISMATCH",
                message="Market context instrument identity does not match the request.",
                http_status=409,
            )
        if not market.complete:
            raise RealTradingApiFailure(
                code="REAL_MARKET_DATA_INCOMPLETE",
                message="Complete market context is required before real trading.",
                http_status=409,
            )
        if not market.api_trade_available or not market.limit_orders_available:
            raise RealTradingApiFailure(
                code="REAL_INSTRUMENT_NOT_TRADABLE",
                message="Instrument is not available for the required LIMIT order.",
                http_status=409,
            )
        if market.instrument_type.strip().lower() not in self._policy.allowed_instrument_types:
            raise RealTradingApiFailure(
                code="REAL_INSTRUMENT_TYPE_NOT_ALLOWED",
                message="Instrument type is outside the real-trading v1 allowlist.",
                http_status=409,
            )
        if market.currency.strip().upper() != "RUB":
            raise RealTradingApiFailure(
                code="REAL_CURRENCY_NOT_ALLOWED",
                message="Real-trading v1 is restricted to RUB cash securities.",
                http_status=409,
            )
        if market.lot < 1:
            raise RealTradingApiFailure(
                code="REAL_LOT_INVALID",
                message="Instrument lot size is invalid.",
                http_status=409,
            )
        if market.retrieved_at.tzinfo is None:
            raise RealTradingApiFailure(
                code="REAL_MARKET_TIME_INVALID",
                message="Market timestamp must be timezone-aware.",
                http_status=409,
            )
        age = (now - market.retrieved_at.astimezone(timezone.utc)).total_seconds()
        if age < -5 or age > self._policy.market_max_age_seconds:
            raise RealTradingApiFailure(
                code="REAL_MARKET_DATA_STALE",
                message="Fresh market context is required before real trading.",
                http_status=409,
            )
        return market

    def _preflight(
        self,
        *,
        account_id: str,
        instrument_uid: str,
        direction: str,
        quantity_lots: int,
        limit_price: Decimal,
    ) -> tuple[int, Decimal, Decimal, dict[str, Any], dict[str, Any]]:
        quotation = decimal_to_quotation(limit_price)
        limits = self._client.post(
            "GetMaxLots",
            {
                "accountId": account_id,
                "instrumentId": instrument_uid,
                "price": quotation,
            },
        )
        if direction == "BUY":
            available_lots = _integer_field(
                _field(limits, "buyLimits", "buy_limits"),
                "buyMaxLots",
                "buy_max_lots",
            )
        else:
            available_lots = _integer_field(
                _field(limits, "sellLimits", "sell_limits"),
                "sellMaxLots",
                "sell_max_lots",
            )
        if available_lots is None:
            raise RealTradingApiFailure(
                code="REAL_LIMITS_INCOMPLETE",
                message="Own-funds/own-position broker limit is missing.",
                http_status=409,
            )
        if quantity_lots > available_lots:
            raise RealTradingApiFailure(
                code="REAL_QUANTITY_EXCEEDS_LIMIT",
                message=(
                    f"Requested {quantity_lots} lots but only {available_lots} "
                    "are available without margin/shorting."
                ),
                http_status=409,
            )

        preview = self._client.post(
            "GetOrderPrice",
            {
                "accountId": account_id,
                "instrumentId": instrument_uid,
                "price": quotation,
                "direction": f"ORDER_DIRECTION_{direction}",
                "quantity": str(quantity_lots),
            },
        )
        total, total_currency = _money_value(
            _field(preview, "totalOrderAmount", "total_order_amount"),
            field_name="total_order_amount",
        )
        commission, commission_currency = _money_value(
            _field(preview, "executedCommissionRub", "executed_commission_rub"),
            field_name="executed_commission_rub",
        )
        if total_currency != "RUB" or commission_currency != "RUB":
            raise RealTradingApiFailure(
                code="REAL_PREFLIGHT_CURRENCY_MISMATCH",
                message="Broker preview must be denominated in RUB for v1.",
                http_status=409,
            )
        if total <= 0:
            raise RealTradingApiFailure(
                code="REAL_PREFLIGHT_INCOMPLETE",
                message="Broker preview returned a non-positive order total.",
                http_status=409,
            )
        if total > self._policy.max_order_rub:
            raise RealTradingApiFailure(
                code="REAL_ORDER_CAP_EXCEEDED",
                message="Order exceeds the server-side per-order hard cap.",
                http_status=409,
            )
        return available_lots, total, commission, limits, preview

    def _daily_budget_preview_check(self, *, total: Decimal, now: datetime) -> None:
        day = now.astimezone(MOSCOW).date()
        already = self._journal.submitted_notional_for_moscow_date(day)
        if already + total > self._policy.max_daily_rub:
            raise RealTradingApiFailure(
                code="REAL_DAILY_CAP_EXCEEDED",
                message="Order would exceed the server-side daily hard cap.",
                http_status=409,
            )

    def _confirmation_code(self, canonical: str) -> str:
        digest = hmac.new(
            self._confirmation_key,
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest[:10].upper()

    def prepare_trade(
        self,
        *,
        instrument_uid: str,
        direction: str,
        quantity_lots: int,
        limit_price: str,
        rationale: str,
        now: datetime | None = None,
    ) -> RealTradeProposalV1:
        current = _normalize_now(now)
        instrument_uid = instrument_uid.strip()
        if not instrument_uid or len(instrument_uid) > 120:
            raise RealTradingApiFailure(
                "REAL_INSTRUMENT_ID_INVALID",
                "instrument_uid must contain 1..120 characters.",
                400,
            )
        normalized_direction = direction.upper()
        if normalized_direction not in {"BUY", "SELL"}:
            raise RealTradingApiFailure(
                "REAL_DIRECTION_INVALID",
                "Direction must be BUY or SELL.",
                400,
            )
        typed_direction = cast(Literal["BUY", "SELL"], normalized_direction)
        if quantity_lots < 1 or quantity_lots > 1_000_000:
            raise RealTradingApiFailure(
                "REAL_QUANTITY_INVALID",
                "Quantity lots is outside the allowed range.",
                400,
            )
        rationale = rationale.strip()
        if not rationale or len(rationale) > 1500:
            raise RealTradingApiFailure(
                "REAL_RATIONALE_INVALID",
                "A rationale of 1..1500 characters is required.",
                400,
            )
        price = decimal_from_text(limit_price)
        if price <= 0:
            raise RealTradingApiFailure(
                "REAL_PRICE_INVALID",
                "Limit price must be positive.",
                400,
            )

        account_id, _ = self.resolve_bound_account()
        market = self._validate_market(instrument_uid, now=current)
        available, total, commission, limits, preview = self._preflight(
            account_id=account_id,
            instrument_uid=instrument_uid,
            direction=typed_direction,
            quantity_lots=quantity_lots,
            limit_price=price,
        )
        self._daily_budget_preview_check(total=total, now=current)

        proposal_id = str(uuid4())
        order_id = str(uuid4())
        expires_at = current + timedelta(
            seconds=self._policy.confirmation_ttl_seconds
        )
        canonical = _json_dump(
            {
                "proposal_id": proposal_id,
                "order_id": order_id,
                "account_id": account_id,
                "instrument_uid": instrument_uid,
                "ticker": market.ticker,
                "isin": market.isin,
                "direction": typed_direction,
                "quantity_lots": quantity_lots,
                "order_type": "LIMIT",
                "limit_price": format(price, "f"),
                "price_type": "CURRENCY",
                "time_in_force": "DAY",
                "preview_total_rub": format(total, "f"),
                "preview_commission_rub": format(commission, "f"),
                "available_lots": available,
                "market_retrieved_at": market.retrieved_at.isoformat(),
                "created_at": current.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        )
        proposal = RealTradeProposalV1(
            proposal_id=proposal_id,
            order_id=order_id,
            account_id=account_id,
            instrument_uid=instrument_uid,
            ticker=market.ticker,
            isin=market.isin,
            direction=typed_direction,
            quantity_lots=quantity_lots,
            limit_price=price,
            rationale=rationale,
            preview_total_rub=total,
            preview_commission_rub=commission,
            available_lots=available,
            market_retrieved_at=market.retrieved_at,
            created_at=current,
            expires_at=expires_at,
            confirmation_code=self._confirmation_code(canonical),
            broker_response_json=sanitized_json(
                {"limits": limits, "order_price": preview}
            ),
        )
        self._journal.put(proposal)
        return proposal

    def execute_trade(
        self,
        proposal_id: str,
        confirmation_phrase: str,
        *,
        now: datetime | None = None,
    ) -> tuple[RealTradeProposalV1, bool]:
        try:
            proposal = self._journal.get(proposal_id)
        except KeyError as exc:
            raise RealTradingApiFailure(
                code="REAL_PROPOSAL_NOT_FOUND",
                message="Real-trading proposal was not found.",
                http_status=404,
            ) from exc

        phrase_matches = hmac.compare_digest(
            confirmation_phrase.strip().encode("utf-8"),
            proposal.confirmation_phrase.encode("utf-8"),
        )
        if proposal.state == "executed":
            if not phrase_matches:
                raise RealTradingApiFailure(
                    code="REAL_CONFIRMATION_MISMATCH",
                    message="Exact real-trade confirmation phrase is required.",
                    http_status=403,
                )
            return proposal, True
        if proposal.state in {"submitting", "unknown"}:
            raise RealTradingApiFailure(
                code="REAL_ORDER_SUBMISSION_UNCERTAIN",
                message="Submission may have occurred; reconcile instead of resubmitting.",
                http_status=409,
                ambiguous_submission=True,
            )
        if proposal.state != "prepared":
            raise RealTradingApiFailure(
                code="REAL_PROPOSAL_NOT_EXECUTABLE",
                message=f"Proposal state is {proposal.state}.",
                http_status=409,
            )

        current = _normalize_now(now)
        if current > proposal.expires_at:
            self._journal.transition(
                proposal_id,
                allowed_from=frozenset({"prepared"}),
                state="expired",
            )
            raise RealTradingApiFailure(
                code="REAL_CONFIRMATION_EXPIRED",
                message="Confirmation expired; prepare a fresh real trade.",
                http_status=409,
            )
        if not phrase_matches:
            raise RealTradingApiFailure(
                code="REAL_CONFIRMATION_MISMATCH",
                message="Exact real-trade confirmation phrase is required.",
                http_status=403,
            )

        account_id, _ = self.resolve_bound_account()
        market = self._validate_market(proposal.instrument_uid, now=current)
        if market.ticker != proposal.ticker or market.isin != proposal.isin:
            raise RealTradingApiFailure(
                code="REAL_INSTRUMENT_IDENTITY_CHANGED",
                message="Instrument identity changed after confirmation.",
                http_status=409,
            )
        if market.retrieved_at <= proposal.market_retrieved_at:
            raise RealTradingApiFailure(
                code="REAL_MARKET_REVALIDATION_REQUIRED",
                message="A newer market snapshot is required immediately before submit.",
                http_status=409,
            )

        available, total, commission, _, _ = self._preflight(
            account_id=account_id,
            instrument_uid=proposal.instrument_uid,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            limit_price=proposal.limit_price,
        )
        if available < proposal.quantity_lots:
            raise RealTradingApiFailure(
                code="REAL_PREFLIGHT_CHANGED",
                message="Available lots decreased after confirmation.",
                http_status=409,
            )
        if total != proposal.preview_total_rub or commission != proposal.preview_commission_rub:
            raise RealTradingApiFailure(
                code="REAL_PREFLIGHT_CHANGED",
                message="Broker order preview changed; prepare and confirm a fresh proposal.",
                http_status=409,
            )

        try:
            self._journal.reserve_submission(
                proposal_id,
                submitted_at=current,
                max_daily_rub=self._policy.max_daily_rub,
            )
        except JournalDailyCapExceeded as exc:
            raise RealTradingApiFailure(
                code="REAL_DAILY_CAP_EXCEEDED",
                message="Order would exceed the atomic daily submission cap.",
                http_status=409,
            ) from exc
        except JournalStateConflict as exc:
            raise RealTradingApiFailure(
                code="REAL_PROPOSAL_STATE_CONFLICT",
                message="Proposal state changed concurrently.",
                http_status=409,
            ) from exc

        payload = {
            "accountId": proposal.account_id,
            "quantity": str(proposal.quantity_lots),
            "direction": f"ORDER_DIRECTION_{proposal.direction}",
            "orderType": "ORDER_TYPE_LIMIT",
            "orderId": proposal.order_id,
            "instrumentId": proposal.instrument_uid,
            "timeInForce": "TIME_IN_FORCE_DAY",
            "priceType": "PRICE_TYPE_CURRENCY",
            "confirmMarginTrade": False,
            "price": decimal_to_quotation(proposal.limit_price),
        }
        try:
            response = self._client.post("PostOrder", payload)
        except RealTradingApiFailure as exc:
            target_state = "unknown" if exc.ambiguous_submission else "failed"
            self._journal.transition(
                proposal_id,
                allowed_from=frozenset({"submitting"}),
                state=target_state,
                failure_code=exc.code,
                failure_message=exc.message,
            )
            raise

        completed = self._journal.transition(
            proposal_id,
            allowed_from=frozenset({"submitting"}),
            state="executed",
            broker_response_json=sanitized_json(response),
        )
        return completed, False

    def order_state(self, order_id: str) -> dict[str, Any]:
        try:
            UUID(order_id)
        except ValueError as exc:
            raise RealTradingApiFailure(
                code="REAL_ORDER_ID_INVALID",
                message="order_id must be a UUID request id.",
                http_status=400,
            ) from exc
        account_id, _ = self.resolve_bound_account()
        payload = self._client.post(
            "GetOrderState",
            {
                "accountId": account_id,
                "orderId": order_id,
                "orderIdType": "ORDER_ID_TYPE_REQUEST",
                "priceType": "PRICE_TYPE_CURRENCY",
            },
        )
        return {
            "status": "ok",
            "masked_account": mask_account_id(account_id),
            "order_id": order_id,
            "broker_response_json": sanitized_json(payload),
        }

    @property
    def production_enable_ready(self) -> bool:
        return bool(self._journal.durable)
