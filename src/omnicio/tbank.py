"""Thin T-Invest REST adapter for owner broker read-only data."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

TBankEnvironment = Literal["prod", "sandbox"]
TBankQuoteSource = Literal["exchange", "dealer"]

logger = logging.getLogger(__name__)

_REST_BASES: dict[TBankEnvironment, str] = {
    "prod": "https://invest-public-api.tbank.ru/rest/",
    "sandbox": "https://sandbox-invest-public-api.tbank.ru/rest/",
}
_API_PREFIX = "tinkoff.public.invest.api.contract.v1."


class TBankError(RuntimeError):
    """Base T-Invest provider failure that never contains the submitted token."""


class TBankTokenRejected(TBankError):
    """The provider rejected or cannot authorize the submitted token."""


class TBankUnavailable(TBankError):
    """The provider cannot be reached or returned an unusable response."""


@dataclass(frozen=True, slots=True)
class TBankAccount:
    id: str
    name: str
    type: str
    status: str


@dataclass(frozen=True, slots=True)
class TBankInstrument:
    uid: str
    figi: str
    ticker: str
    name: str
    instrument_type: str
    class_code: str
    lot: int
    for_qual_investor: bool
    for_iis: bool
    weekend_trading: bool


@dataclass(frozen=True, slots=True)
class TBankFxQuote:
    instrument_uid: str
    ticker: str
    name: str
    class_code: str
    price: str
    currency: str
    quote_time: str
    source: TBankQuoteSource
    previous_close: str | None


@dataclass(frozen=True, slots=True)
class TBankMoney:
    currency: str
    value: str


@dataclass(frozen=True, slots=True)
class TBankAssetTotal:
    kind: str
    money: TBankMoney


@dataclass(frozen=True, slots=True)
class TBankPortfolioPosition:
    ticker: str
    figi: str
    instrument_uid: str
    instrument_type: str
    quantity: str
    current_price: TBankMoney | None
    average_price: TBankMoney | None
    expected_yield_percent: str
    daily_yield: TBankMoney | None
    blocked: bool


@dataclass(frozen=True, slots=True)
class TBankPortfolio:
    total: TBankMoney
    expected_yield_percent: str
    daily_yield: TBankMoney | None
    daily_yield_percent: str
    asset_totals: tuple[TBankAssetTotal, ...]
    positions: tuple[TBankPortfolioPosition, ...]


@dataclass(frozen=True, slots=True)
class TBankPositions:
    money: tuple[TBankMoney, ...]
    blocked_money: tuple[TBankMoney, ...]
    limits_loading_in_progress: bool


@dataclass(frozen=True, slots=True)
class TBankInvestClient:
    timeout_seconds: int = 10

    def get_accounts(
        self,
        token: str,
        environment: TBankEnvironment,
    ) -> list[TBankAccount]:
        payload = self._post(
            token=token,
            environment=environment,
            service="UsersService",
            method="GetAccounts",
            body={"status": "ACCOUNT_STATUS_OPEN"},
        )
        items = _required_list(payload, "accounts")

        accounts: list[TBankAccount] = []
        for item_raw in items:
            item = _required_object(item_raw, "account")
            account_id = _text(item.get("id")).strip()
            if not account_id:
                raise TBankUnavailable("T-Invest API returned account without id")
            accounts.append(
                TBankAccount(
                    id=account_id,
                    name=_text(item.get("name")).strip(),
                    type=_text(item.get("type")).strip(),
                    status=_text(item.get("status")).strip(),
                )
            )
        return accounts

    def find_instruments(
        self,
        token: str,
        environment: TBankEnvironment,
        query: str,
        *,
        limit: int = 20,
        instrument_kind: str = "INSTRUMENT_TYPE_UNSPECIFIED",
    ) -> tuple[TBankInstrument, ...]:
        clean_query = query.strip()
        if not 1 <= len(clean_query) <= 64 or "\n" in clean_query or "\r" in clean_query:
            raise ValueError("instrument search query must contain 1 to 64 characters")
        if not 1 <= limit <= 50:
            raise ValueError("instrument search limit must be between 1 and 50")

        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="FindInstrument",
            body={
                "query": clean_query,
                "instrumentKind": instrument_kind,
                "apiTradeAvailableFlag": True,
            },
        )

        instruments: list[TBankInstrument] = []
        for raw in _optional_list(payload, "instruments"):
            item = _required_object(raw, "instrument")
            api_available = item.get("apiTradeAvailableFlag", False)
            if not isinstance(api_available, bool):
                raise TBankUnavailable("T-Invest instrument has invalid API availability flag")
            if not api_available:
                continue

            lot_raw = item.get("lot", 0)
            if isinstance(lot_raw, bool):
                raise TBankUnavailable("T-Invest instrument has invalid lot size")
            try:
                lot = int(str(lot_raw))
            except ValueError as exc:
                raise TBankUnavailable("T-Invest instrument has invalid lot size") from exc

            for_qual = item.get("forQualInvestorFlag", False)
            for_iis = item.get("forIisFlag", False)
            weekend = item.get("weekendFlag", False)
            if (
                not isinstance(for_qual, bool)
                or not isinstance(for_iis, bool)
                or not isinstance(weekend, bool)
            ):
                raise TBankUnavailable("T-Invest instrument has invalid access flags")

            uid = _text(item.get("uid")).strip()
            ticker = _text(item.get("ticker")).strip()
            name = _text(item.get("name")).strip()
            if not uid or not ticker or not name:
                continue

            instruments.append(
                TBankInstrument(
                    uid=uid,
                    figi=_text(item.get("figi")).strip(),
                    ticker=ticker,
                    name=name,
                    instrument_type=_text(item.get("instrumentType")).strip(),
                    class_code=_text(item.get("classCode")).strip(),
                    lot=lot,
                    for_qual_investor=for_qual,
                    for_iis=for_iis,
                    weekend_trading=weekend,
                )
            )
            if len(instruments) >= limit:
                break

        return tuple(instruments)

    def get_usd_rub_quote(
        self,
        token: str,
        environment: TBankEnvironment,
    ) -> TBankFxQuote:
        candidates = tuple(
            instrument
            for instrument in self.find_instruments(
                token,
                environment,
                "USD",
                limit=50,
                instrument_kind="INSTRUMENT_TYPE_CURRENCY",
            )
            if (
                instrument.ticker.upper().startswith("USD")
                or "доллар" in instrument.name.lower()
                or "dollar" in instrument.name.lower()
            )
        )
        if not candidates:
            raise TBankUnavailable("T-Invest has no USD currency instruments")

        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetMarketValues",
            body={
                "instrumentId": [instrument.uid for instrument in candidates],
                "values": [
                    "INSTRUMENT_VALUE_LAST_PRICE",
                    "INSTRUMENT_VALUE_LAST_PRICE_DEALER",
                    "INSTRUMENT_VALUE_CLOSE_PRICE",
                ],
            },
        )
        candidate_by_uid = {instrument.uid: instrument for instrument in candidates}

        best: tuple[datetime, int, TBankFxQuote] | None = None
        for raw in _optional_list(payload, "instruments"):
            item = _required_object(raw, "market value instrument")
            uid = _text(item.get("instrumentUid")).strip()
            instrument = candidate_by_uid.get(uid)
            if instrument is None:
                continue

            currency = _text(item.get("priceCurrency")).strip().upper()
            if currency != "RUB":
                continue

            previous_close: str | None = None
            quotes: list[tuple[datetime, int, str, str, TBankQuoteSource]] = []
            for value_raw in _optional_list(item, "values"):
                value = _required_object(value_raw, "market value")
                value_type = _text(value.get("type")).strip()
                numeric = _quotation(value.get("value"))
                if numeric is None:
                    continue

                if value_type == "INSTRUMENT_VALUE_CLOSE_PRICE":
                    previous_close = numeric
                    continue
                if value_type not in {
                    "INSTRUMENT_VALUE_LAST_PRICE",
                    "INSTRUMENT_VALUE_LAST_PRICE_DEALER",
                }:
                    continue

                quote_time = _text(value.get("time")).strip()
                parsed_time = _provider_timestamp(quote_time)
                if value_type == "INSTRUMENT_VALUE_LAST_PRICE_DEALER":
                    source: TBankQuoteSource = "dealer"
                    source_priority = 0
                else:
                    source = "exchange"
                    source_priority = 1
                quotes.append(
                    (parsed_time, source_priority, numeric, quote_time, source)
                )

            if not quotes:
                continue

            parsed_time, source_priority, price, quote_time, source = max(
                quotes,
                key=lambda quote: (quote[0], quote[1]),
            )
            quote = TBankFxQuote(
                instrument_uid=instrument.uid,
                ticker=instrument.ticker,
                name=instrument.name,
                class_code=instrument.class_code,
                price=price,
                currency=currency,
                quote_time=quote_time,
                source=source,
                previous_close=previous_close,
            )
            ranked = (parsed_time, source_priority, quote)
            if best is None or ranked[:2] > best[:2]:
                best = ranked

        if best is None:
            raise TBankUnavailable("T-Invest has no current USD/RUB quote")
        return best[2]

    def get_portfolio(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
    ) -> TBankPortfolio:
        payload = self._post(
            token=token,
            environment=environment,
            service="OperationsService",
            method="GetPortfolio",
            body={"accountId": _validate_account_id(account_id), "currency": "RUB"},
        )
        total = _money(payload.get("totalAmountPortfolio"))
        if total is None:
            raise TBankUnavailable("T-Invest portfolio has no total amount")

        asset_keys = (
            ("shares", "totalAmountShares"),
            ("bonds", "totalAmountBonds"),
            ("funds", "totalAmountEtf"),
            ("currencies", "totalAmountCurrencies"),
            ("futures", "totalAmountFutures"),
            ("options", "totalAmountOptions"),
            ("structured_products", "totalAmountSp"),
            ("dfa", "totalAmountDfa"),
        )
        asset_totals: list[TBankAssetTotal] = []
        for kind, key in asset_keys:
            money = _money(payload.get(key))
            if money is not None:
                asset_totals.append(TBankAssetTotal(kind=kind, money=money))

        positions: list[TBankPortfolioPosition] = []
        for position_raw in _optional_list(payload, "positions"):
            position = _required_object(position_raw, "portfolio position")
            blocked_raw = position.get("blocked", False)
            if not isinstance(blocked_raw, bool):
                raise TBankUnavailable("T-Invest portfolio position has invalid blocked flag")
            positions.append(
                TBankPortfolioPosition(
                    ticker=_text(position.get("ticker")).strip(),
                    figi=_text(position.get("figi")).strip(),
                    instrument_uid=_text(position.get("instrumentUid")).strip(),
                    instrument_type=_text(position.get("instrumentType")).strip(),
                    quantity=_quotation(position.get("quantity")) or "0",
                    current_price=_money(position.get("currentPrice")),
                    average_price=_money(position.get("averagePositionPrice")),
                    expected_yield_percent=_quotation(position.get("expectedYield")) or "0",
                    daily_yield=_money(position.get("dailyYield")),
                    blocked=blocked_raw,
                )
            )

        return TBankPortfolio(
            total=total,
            expected_yield_percent=_quotation(payload.get("expectedYield")) or "0",
            daily_yield=_money(payload.get("dailyYield")),
            daily_yield_percent=_quotation(payload.get("dailyYieldRelative")) or "0",
            asset_totals=tuple(asset_totals),
            positions=tuple(positions),
        )

    def get_positions(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
    ) -> TBankPositions:
        payload = self._post(
            token=token,
            environment=environment,
            service="OperationsService",
            method="GetPositions",
            body={"accountId": _validate_account_id(account_id)},
        )
        money = tuple(
            parsed
            for item in _optional_list(payload, "money")
            if (parsed := _money(item)) is not None
        )
        blocked_money = tuple(
            parsed
            for item in _optional_list(payload, "blocked")
            if (parsed := _money(item)) is not None
        )
        loading = payload.get("limitsLoadingInProgress", False)
        if not isinstance(loading, bool):
            raise TBankUnavailable("T-Invest positions has invalid loading flag")
        return TBankPositions(
            money=money,
            blocked_money=blocked_money,
            limits_loading_in_progress=loading,
        )

    def _post(
        self,
        *,
        token: str,
        environment: TBankEnvironment,
        service: str,
        method: str,
        body: dict[str, object],
    ) -> dict[str, object]:
        clean_token = _validate_token(token)
        base = _REST_BASES.get(environment)
        if base is None:
            raise TBankUnavailable("unsupported T-Invest environment")
        endpoint = f"{base}{_API_PREFIX}{service}/{method}"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {clean_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            tracking_id = exc.headers.get("x-tracking-id", "")
            logger.warning(
                "T-Invest request failed method=%s status=%s tracking_id=%s",
                method,
                exc.code,
                tracking_id or "-",
            )
            if exc.code in {401, 403}:
                raise TBankTokenRejected("T-Invest token was rejected") from exc
            if exc.code == 429 or exc.code >= 500:
                raise TBankUnavailable(
                    f"T-Invest API unavailable: HTTP {exc.code}"
                ) from exc
            raise TBankUnavailable(
                f"T-Invest API rejected request: HTTP {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            reason_name = type(reason).__name__
            logger.warning(
                "T-Invest network failure method=%s reason=%s",
                method,
                reason_name,
            )
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise TBankUnavailable(
                    "T-Invest TLS certificate verification failed"
                ) from exc
            raise TBankUnavailable(
                f"T-Invest API unavailable: {reason_name}"
            ) from exc
        except TimeoutError as exc:
            logger.warning("T-Invest request timed out method=%s", method)
            raise TBankUnavailable("T-Invest API request timed out") from exc

        try:
            payload_raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TBankUnavailable("T-Invest API returned invalid JSON") from exc
        if not isinstance(payload_raw, dict):
            raise TBankUnavailable("T-Invest API returned invalid payload")
        return cast(dict[str, object], payload_raw)


def _validate_token(token: str) -> str:
    clean = token.strip()
    if not 20 <= len(clean) <= 4096:
        raise TBankTokenRejected("T-Invest token has invalid length")
    if "\n" in clean or "\r" in clean:
        raise TBankTokenRejected("T-Invest token contains an invalid newline")
    return clean


def _validate_account_id(account_id: str) -> str:
    clean = account_id.strip()
    if not clean or len(clean) > 128 or "\n" in clean or "\r" in clean:
        raise TBankUnavailable("invalid T-Invest account id")
    return clean


def _provider_timestamp(value: str) -> datetime:
    if not value:
        raise TBankUnavailable("T-Invest market value has no timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TBankUnavailable("T-Invest market value has invalid timestamp") from exc


def _required_object(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TBankUnavailable(f"T-Invest API returned malformed {name}")
    return cast(dict[str, object], value)


def _required_list(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise TBankUnavailable(f"T-Invest API response has no {key} list")
    return cast(list[object], value)


def _optional_list(payload: dict[str, object], key: str) -> list[object]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise TBankUnavailable(f"T-Invest API response has malformed {key} list")
    return cast(list[object], value)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int)):
        return str(value)
    raise TBankUnavailable("T-Invest API returned invalid text value")


def _integer_text(value: object) -> str:
    if value is None:
        return "0"
    if isinstance(value, bool):
        raise TBankUnavailable("T-Invest API returned invalid integer value")
    if isinstance(value, (str, int)):
        text = str(value)
        try:
            int(text)
        except ValueError as exc:
            raise TBankUnavailable("T-Invest API returned invalid integer value") from exc
        return text
    raise TBankUnavailable("T-Invest API returned invalid integer value")


def _quotation(value: object) -> str | None:
    if value is None:
        return None
    data = _required_object(value, "numeric value")
    units = data.get("units", 0)
    nano = data.get("nano", 0)
    if isinstance(units, bool) or isinstance(nano, bool):
        raise TBankUnavailable("T-Invest API returned invalid numeric value")
    try:
        amount = Decimal(str(units)) + Decimal(str(nano)) / Decimal(1_000_000_000)
    except (InvalidOperation, ValueError) as exc:
        raise TBankUnavailable("T-Invest API returned invalid numeric value") from exc
    if amount == 0:
        return "0"
    return format(amount.normalize(), "f")


def _money(value: object) -> TBankMoney | None:
    if value is None:
        return None
    data = _required_object(value, "money value")
    currency = _text(data.get("currency")).strip().upper()
    if not currency:
        raise TBankUnavailable("T-Invest API returned money without currency")
    return TBankMoney(
        currency=currency,
        value=_quotation(data) or "0",
    )
