"""Thin T-Invest REST adapter for owner broker read-only data."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
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
    opened_at: datetime | None = None
    access_level: str = ""


@dataclass(frozen=True, slots=True)
class TBankUserInfo:
    premium: bool
    qualified: bool
    qualified_for_work_with: tuple[str, ...]
    tariff: str
    risk_level_code: str


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
    current_nkd: TBankMoney | None = None
    blocked_lots: str = "0"


@dataclass(frozen=True, slots=True)
class TBankInstrumentMetadata:
    uid: str
    name: str
    ticker: str
    isin: str
    instrument_type: str
    sector: str
    country_of_risk: str
    for_qual_investor: bool | None
    figi: str = ""
    asset_uid: str = ""
    position_uid: str = ""
    currency: str = ""
    class_code: str = ""
    lot: int = 0
    for_iis: bool | None = None
    api_trade_available: bool | None = None
    buy_available: bool | None = None
    sell_available: bool | None = None
    required_tests: tuple[str, ...] = ()
    min_price_increment: str | None = None
    nominal: TBankMoney | None = None
    aci_value: TBankMoney | None = None
    maturity_date: datetime | None = None
    coupon_quantity_per_year: int | None = None
    floating_coupon: bool | None = None
    perpetual: bool | None = None
    amortization: bool | None = None
    subordinated: bool | None = None
    liquidity: bool | None = None
    exchange: str = ""
    real_exchange: str = ""
    tax_free: bool | None = None
    collateral: bool | None = None


@dataclass(frozen=True, slots=True)
class TBankMarketValue:
    instrument_uid: str
    price_currency: str
    last_price: str | None
    last_price_at: datetime | None
    yield_value: str | None
    yield_at: datetime | None


@dataclass(frozen=True, slots=True)
class TBankOrderPrice:
    lots_requested: int
    total_order_amount: TBankMoney
    initial_order_amount: TBankMoney
    executed_commission: TBankMoney | None
    service_commission: TBankMoney | None
    deal_commission: TBankMoney | None
    bond_aci: TBankMoney | None
    nominal_conversion_rate: str | None


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
class TBankOperationTrade:
    num: str
    date: datetime
    quantity: str
    price: TBankMoney | None


@dataclass(frozen=True, slots=True)
class TBankOperation:
    cursor: str
    broker_account_id: str
    id: str
    parent_operation_id: str
    name: str
    date: datetime
    operation_type: str
    description: str
    state: str
    instrument_uid: str
    figi: str
    instrument_type: str
    position_uid: str
    ticker: str
    class_code: str
    payment: TBankMoney | None
    price: TBankMoney | None
    commission: TBankMoney | None
    accrued_int: TBankMoney | None
    quantity: str
    quantity_rest: str
    quantity_done: str
    asset_uid: str
    trades: tuple[TBankOperationTrade, ...]


@dataclass(frozen=True, slots=True)
class TBankOperationsPage:
    has_next: bool
    next_cursor: str
    items: tuple[TBankOperation, ...]


@dataclass(frozen=True, slots=True)
class TBankDividend:
    instrument_uid: str
    dividend_net: TBankMoney
    payment_date: datetime | None
    declared_date: datetime | None
    last_buy_date: datetime | None
    record_date: datetime | None
    dividend_type: str
    regularity: str
    yield_value: str | None
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class TBankBondCoupon:
    instrument_uid: str
    coupon_date: datetime
    coupon_number: int
    fix_date: datetime | None
    pay_one_bond: TBankMoney
    coupon_type: str
    coupon_start_date: datetime | None
    coupon_end_date: datetime | None
    coupon_period_days: int


@dataclass(frozen=True, slots=True)
class TBankBondEvent:
    instrument_uid: str
    event_number: int
    event_date: datetime | None
    event_type: str
    default_date: datetime | None
    real_pay_date: datetime | None
    pay_date: datetime | None
    pay_one_bond: TBankMoney | None
    execution: str
    operation_type: str
    note: str


@dataclass(frozen=True, slots=True)
class TBankAssetReport:
    instrument_uid: str
    report_date: datetime
    period_year: int
    period_num: int
    period_type: str
    created_at: datetime | None


@dataclass(frozen=True, slots=True)
class TBankAssetFundamental:
    asset_uid: str
    currency: str
    revenue_ttm: str | None
    ebitda_ttm: str | None
    net_income_ttm: str | None
    free_cash_flow_ttm: str | None
    total_debt_mrq: str | None
    total_debt_to_equity_mrq: str | None
    total_debt_to_ebitda_mrq: str | None
    net_debt_to_ebitda: str | None
    current_ratio_mrq: str | None
    fixed_charge_coverage_ratio_fy: str | None
    net_interest_margin_mrq: str | None
    roe: str | None
    roa: str | None
    fiscal_period_start_date: datetime | None
    fiscal_period_end_date: datetime | None


@dataclass(frozen=True, slots=True)
class TBankInvestClient:
    timeout_seconds: int = 10

    def get_instrument_metadata(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_type: str,
    ) -> tuple[TBankInstrumentMetadata, ...]:
        methods = {"share": "Shares", "bond": "Bonds", "etf": "Etfs"}
        method = methods.get(instrument_type)
        if method is None:
            raise ValueError("unsupported metadata instrument type")

        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method=method,
            body={"instrumentStatus": "INSTRUMENT_STATUS_ALL"},
        )

        result: list[TBankInstrumentMetadata] = []
        seen: set[str] = set()
        for raw in _required_list(payload, "instruments"):
            item = _required_object(raw, "instrument metadata")
            uid = _text(item.get("uid")).strip()
            if not uid or uid in seen:
                raise TBankUnavailable("T-Invest metadata has missing or duplicate uid")
            seen.add(uid)

            lot_raw = item.get("lot", 0)
            if isinstance(lot_raw, bool):
                raise TBankUnavailable("T-Invest metadata has invalid lot size")
            try:
                lot = int(str(lot_raw))
            except ValueError as exc:
                raise TBankUnavailable("T-Invest metadata has invalid lot size") from exc
            if lot < 0:
                raise TBankUnavailable("T-Invest metadata has invalid lot size")

            required_tests = tuple(
                _text(value).strip()
                for value in _optional_list(item, "requiredTests")
                if _text(value).strip()
            )

            result.append(
                TBankInstrumentMetadata(
                    uid=uid,
                    name=_text(item.get("name")).strip(),
                    ticker=_text(item.get("ticker")).strip(),
                    isin=_text(item.get("isin")).strip(),
                    instrument_type=instrument_type,
                    sector=_text(item.get("sector")).strip(),
                    country_of_risk=_text(item.get("countryOfRisk")).strip().upper(),
                    for_qual_investor=_optional_bool(item, "forQualInvestorFlag"),
                    figi=_text(item.get("figi")).strip(),
                    asset_uid=_text(item.get("assetUid")).strip(),
                    position_uid=_text(item.get("positionUid")).strip(),
                    currency=_text(item.get("currency")).strip().upper(),
                    class_code=_text(item.get("classCode")).strip(),
                    lot=lot,
                    for_iis=_optional_bool(item, "forIisFlag"),
                    api_trade_available=_optional_bool(item, "apiTradeAvailableFlag"),
                    buy_available=_optional_bool(item, "buyAvailableFlag"),
                    sell_available=_optional_bool(item, "sellAvailableFlag"),
                    required_tests=required_tests,
                    min_price_increment=_quotation(item.get("minPriceIncrement")),
                    nominal=_money(item.get("nominal")),
                    aci_value=_money(item.get("aciValue")),
                    maturity_date=_optional_provider_timestamp(item.get("maturityDate")),
                    coupon_quantity_per_year=_optional_int(
                        item.get("couponQuantityPerYear"),
                        "coupon quantity per year",
                    ),
                    floating_coupon=_optional_bool(item, "floatingCouponFlag"),
                    perpetual=_optional_bool(item, "perpetualFlag"),
                    amortization=_optional_bool(item, "amortizationFlag"),
                    subordinated=_optional_bool(item, "subordinatedFlag"),
                    liquidity=_optional_bool(item, "liquidityFlag"),
                    exchange=_text(item.get("exchange")).strip(),
                    real_exchange=_text(item.get("realExchange")).strip(),
                    tax_free=_optional_bool(item, "taxFreeFlag"),
                    collateral=_optional_bool(item, "collateralFlag"),
                )
            )
        return tuple(result)

    def get_market_values(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankMarketValue, ...]:
        if not 1 <= len(instrument_uids) <= 100:
            raise ValueError("market value batch must contain 1 to 100 instruments")
        clean_uids = tuple(
            _validate_provider_id(uid, "instrument uid")
            for uid in instrument_uids
        )
        if len(set(clean_uids)) != len(clean_uids):
            raise ValueError("market value batch contains duplicate instruments")

        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetMarketValues",
            body={
                "instrumentId": list(clean_uids),
                "values": [
                    "INSTRUMENT_VALUE_LAST_PRICE",
                    "INSTRUMENT_VALUE_YIELD",
                ],
            },
        )
        requested = set(clean_uids)
        result: list[TBankMarketValue] = []
        seen: set[str] = set()
        for raw in _required_list(payload, "instruments"):
            item = _required_object(raw, "market value instrument")
            uid = _text(item.get("instrumentUid")).strip()
            if not uid or uid not in requested or uid in seen:
                raise TBankUnavailable(
                    "T-Invest market values contain an unexpected instrument"
                )
            seen.add(uid)

            last_price: str | None = None
            last_price_at: datetime | None = None
            yield_value: str | None = None
            yield_at: datetime | None = None
            for value_raw in _optional_list(item, "values"):
                value = _required_object(value_raw, "market value")
                value_type = _text(value.get("type")).strip()
                numeric = _quotation(value.get("value"))
                if numeric is None:
                    continue
                timestamp = _optional_provider_timestamp(value.get("time"))
                if timestamp is None:
                    raise TBankUnavailable("T-Invest market value has no timestamp")
                if value_type == "INSTRUMENT_VALUE_LAST_PRICE":
                    last_price = numeric
                    last_price_at = timestamp
                elif value_type == "INSTRUMENT_VALUE_YIELD":
                    yield_value = numeric
                    yield_at = timestamp

            price_currency = _text(item.get("priceCurrency")).strip().upper()
            if last_price is not None and not price_currency:
                raise TBankUnavailable(
                    "T-Invest market value price has no currency"
                )
            result.append(
                TBankMarketValue(
                    instrument_uid=uid,
                    price_currency=price_currency,
                    last_price=last_price,
                    last_price_at=last_price_at,
                    yield_value=yield_value,
                    yield_at=yield_at,
                )
            )
        return tuple(result)

    def get_order_price(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        instrument_uid: str,
        *,
        price: str,
        quantity_lots: int,
        direction: Literal["buy", "sell"],
    ) -> TBankOrderPrice:
        if quantity_lots <= 0:
            raise ValueError("order price quantity must be positive")
        clean_direction = {
            "buy": "ORDER_DIRECTION_BUY",
            "sell": "ORDER_DIRECTION_SELL",
        }.get(direction)
        if clean_direction is None:
            raise ValueError("order price direction is invalid")

        payload = self._post(
            token=token,
            environment=environment,
            service="OrdersService",
            method="GetOrderPrice",
            body={
                "accountId": _validate_account_id(account_id),
                "instrumentId": _validate_provider_id(
                    instrument_uid,
                    "instrument uid",
                ),
                "price": _quotation_payload(price),
                "direction": clean_direction,
                "quantity": str(quantity_lots),
            },
        )
        total = _money(payload.get("totalOrderAmount"))
        initial = _money(payload.get("initialOrderAmount"))
        if total is None or initial is None:
            raise TBankUnavailable(
                "T-Invest order price is missing required amounts"
            )
        lots_requested = _int_value(
            payload.get("lotsRequested"),
            "order price lots requested",
        )
        if lots_requested != quantity_lots:
            raise TBankUnavailable(
                "T-Invest order price lots do not match request"
            )
        extra_bond_raw = payload.get("extraBond")
        bond_aci: TBankMoney | None = None
        nominal_conversion_rate: str | None = None
        if extra_bond_raw is not None:
            extra_bond = _required_object(extra_bond_raw, "order price bond details")
            bond_aci = _money(extra_bond.get("aciValue"))
            nominal_conversion_rate = _quotation(
                extra_bond.get("nominalConversionRate")
            )
        return TBankOrderPrice(
            lots_requested=lots_requested,
            total_order_amount=total,
            initial_order_amount=initial,
            executed_commission=_money(payload.get("executedCommission")),
            service_commission=_money(payload.get("serviceCommission")),
            deal_commission=_money(payload.get("dealCommission")),
            bond_aci=bond_aci,
            nominal_conversion_rate=nominal_conversion_rate,
        )

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
                    opened_at=_optional_provider_timestamp(item.get("openedDate")),
                    access_level=_text(item.get("accessLevel")).strip(),
                )
            )
        return accounts

    def get_user_info(
        self,
        token: str,
        environment: TBankEnvironment,
    ) -> TBankUserInfo:
        payload = self._post(
            token=token,
            environment=environment,
            service="UsersService",
            method="GetInfo",
            body={},
        )
        premium = payload.get("premStatus")
        qualified = payload.get("qualStatus")
        if not isinstance(premium, bool) or not isinstance(qualified, bool):
            raise TBankUnavailable("T-Invest user info has invalid qualification flags")

        qualified_for = tuple(
            value
            for raw in _optional_list(payload, "qualifiedForWorkWith")
            if (value := _text(raw).strip())
        )
        return TBankUserInfo(
            premium=premium,
            qualified=qualified,
            qualified_for_work_with=qualified_for,
            tariff=_text(payload.get("tariff")).strip(),
            risk_level_code=_text(payload.get("riskLevelCode")).strip(),
        )

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
                    current_nkd=_money(position.get("currentNkd")),
                    blocked_lots=_quotation(position.get("blockedLots")) or "0",
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

    def get_operations_by_cursor(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        from_at: datetime,
        to_at: datetime,
        cursor: str = "",
        limit: int = 1000,
    ) -> TBankOperationsPage:
        if from_at.tzinfo is None or to_at.tzinfo is None:
            raise ValueError("operation history boundaries must be timezone-aware")
        if from_at > to_at:
            raise ValueError("operation history start must not be after end")
        if not 1 <= limit <= 1000:
            raise ValueError("operation history limit must be between 1 and 1000")
        if len(cursor) > 4096 or "\n" in cursor or "\r" in cursor:
            raise ValueError("operation history cursor is invalid")

        # The project selects the sandbox by host. T-Invest documents this as
        # the preferred sandbox mode, so the ordinary OperationsService method is
        # used on both hosts instead of mixing the sandbox host with SandboxService.
        service = "OperationsService"
        method = "GetOperationsByCursor"

        body: dict[str, object] = {
            "accountId": _validate_account_id(account_id),
            "from": _utc_timestamp(from_at),
            "to": _utc_timestamp(to_at),
            "limit": limit,
            "state": "OPERATION_STATE_UNSPECIFIED",
            "withoutCommissions": False,
            "withoutTrades": False,
            "withoutOvernights": False,
        }
        if cursor:
            body["cursor"] = cursor

        payload = self._post(
            token=token,
            environment=environment,
            service=service,
            method=method,
            body=body,
        )

        has_next = payload.get("hasNext", False)
        if not isinstance(has_next, bool):
            raise TBankUnavailable("T-Invest operation page has invalid hasNext flag")
        next_cursor = _text(payload.get("nextCursor")).strip()
        if has_next and not next_cursor:
            raise TBankUnavailable("T-Invest operation page is missing next cursor")

        operations: list[TBankOperation] = []
        for raw in _required_list(payload, "items"):
            item = _required_object(raw, "operation item")
            operation_date = _optional_provider_timestamp(item.get("date"))
            if operation_date is None:
                raise TBankUnavailable("T-Invest operation item has no date")

            trades_info = item.get("tradesInfo")
            trade_rows: list[object] = []
            if trades_info is not None:
                trade_rows = _optional_list(
                    _required_object(trades_info, "operation trades"),
                    "trades",
                )
            trades: list[TBankOperationTrade] = []
            for trade_raw in trade_rows:
                trade = _required_object(trade_raw, "operation trade")
                trade_date = _optional_provider_timestamp(trade.get("date"))
                if trade_date is None:
                    raise TBankUnavailable("T-Invest operation trade has no date")
                trades.append(
                    TBankOperationTrade(
                        num=_text(trade.get("num")).strip(),
                        date=trade_date,
                        quantity=_integer_text(trade.get("quantity")),
                        price=_money(trade.get("price")),
                    )
                )

            operations.append(
                TBankOperation(
                    cursor=_text(item.get("cursor")).strip(),
                    broker_account_id=_text(item.get("brokerAccountId")).strip(),
                    id=_text(item.get("id")).strip(),
                    parent_operation_id=_text(item.get("parentOperationId")).strip(),
                    name=_text(item.get("name")).strip(),
                    date=operation_date,
                    operation_type=_text(item.get("type")).strip(),
                    description=_text(item.get("description")).strip(),
                    state=_text(item.get("state")).strip(),
                    instrument_uid=_text(item.get("instrumentUid")).strip(),
                    figi=_text(item.get("figi")).strip(),
                    instrument_type=_text(item.get("instrumentType")).strip(),
                    position_uid=_text(item.get("positionUid")).strip(),
                    ticker=_text(item.get("ticker")).strip(),
                    class_code=_text(item.get("classCode")).strip(),
                    payment=_money(item.get("payment")),
                    price=_money(item.get("price")),
                    commission=_money(item.get("commission")),
                    accrued_int=_money(item.get("accruedInt")),
                    quantity=_integer_text(item.get("quantity")),
                    quantity_rest=_integer_text(item.get("quantityRest")),
                    quantity_done=_integer_text(item.get("quantityDone")),
                    asset_uid=_text(item.get("assetUid")).strip(),
                    trades=tuple(trades),
                )
            )

        return TBankOperationsPage(
            has_next=has_next,
            next_cursor=next_cursor,
            items=tuple(operations),
        )

    def get_dividends(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankDividend, ...]:
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetDividends",
            body=_instrument_window_body(instrument_uid, from_at, to_at),
        )
        result: list[TBankDividend] = []
        for raw in _required_list(payload, "dividends"):
            item = _required_object(raw, "dividend")
            payment = _money(item.get("dividendNet"))
            if payment is None:
                raise TBankUnavailable("T-Invest dividend has no payment amount")
            result.append(
                TBankDividend(
                    instrument_uid=instrument_uid,
                    dividend_net=payment,
                    payment_date=_optional_provider_timestamp(item.get("paymentDate")),
                    declared_date=_optional_provider_timestamp(item.get("declaredDate")),
                    last_buy_date=_optional_provider_timestamp(item.get("lastBuyDate")),
                    record_date=_optional_provider_timestamp(item.get("recordDate")),
                    dividend_type=_text(item.get("dividendType")).strip(),
                    regularity=_text(item.get("regularity")).strip(),
                    yield_value=_quotation(item.get("yieldValue")),
                    created_at=_optional_provider_timestamp(item.get("createdAt")),
                )
            )
        return tuple(result)

    def get_bond_coupons(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondCoupon, ...]:
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetBondCoupons",
            body=_instrument_window_body(instrument_uid, from_at, to_at),
        )
        result: list[TBankBondCoupon] = []
        for raw in _required_list(payload, "events"):
            item = _required_object(raw, "bond coupon")
            coupon_date = _optional_provider_timestamp(item.get("couponDate"))
            payment = _money(item.get("payOneBond"))
            if coupon_date is None or payment is None:
                raise TBankUnavailable("T-Invest bond coupon is missing required fields")
            result.append(
                TBankBondCoupon(
                    instrument_uid=instrument_uid,
                    coupon_date=coupon_date,
                    coupon_number=_int_value(item.get("couponNumber"), "coupon number"),
                    fix_date=_optional_provider_timestamp(item.get("fixDate")),
                    pay_one_bond=payment,
                    coupon_type=_text(item.get("couponType")).strip(),
                    coupon_start_date=_optional_provider_timestamp(item.get("couponStartDate")),
                    coupon_end_date=_optional_provider_timestamp(item.get("couponEndDate")),
                    coupon_period_days=_int_value(item.get("couponPeriod"), "coupon period"),
                )
            )
        return tuple(result)

    def get_bond_events(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankBondEvent, ...]:
        body = _instrument_window_body(instrument_uid, from_at, to_at)
        body["type"] = "EVENT_TYPE_UNSPECIFIED"
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetBondEvents",
            body=body,
        )
        result: list[TBankBondEvent] = []
        for raw in _required_list(payload, "events"):
            item = _required_object(raw, "bond event")
            returned_uid = _text(item.get("instrumentId")).strip()
            if returned_uid and returned_uid != instrument_uid:
                raise TBankUnavailable("T-Invest bond event instrument does not match request")
            result.append(
                TBankBondEvent(
                    instrument_uid=instrument_uid,
                    event_number=_int_value(item.get("eventNumber"), "bond event number"),
                    event_date=_optional_provider_timestamp(item.get("eventDate")),
                    event_type=_text(item.get("eventType")).strip(),
                    default_date=_optional_provider_timestamp(item.get("defaultDate")),
                    real_pay_date=_optional_provider_timestamp(item.get("realPayDate")),
                    pay_date=_optional_provider_timestamp(item.get("payDate")),
                    pay_one_bond=_money(item.get("payOneBond")),
                    execution=_text(item.get("execution")).strip(),
                    operation_type=_text(item.get("operationType")).strip(),
                    note=_text(item.get("note")).strip(),
                )
            )
        return tuple(result)

    def get_asset_reports(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankAssetReport, ...]:
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetAssetReports",
            body=_instrument_window_body(instrument_uid, from_at, to_at),
        )
        result: list[TBankAssetReport] = []
        for raw in _required_list(payload, "events"):
            item = _required_object(raw, "asset report")
            returned_uid = _text(item.get("instrumentId")).strip()
            if returned_uid and returned_uid != instrument_uid:
                raise TBankUnavailable("T-Invest asset report instrument does not match request")
            report_date = _optional_provider_timestamp(item.get("reportDate"))
            if report_date is None:
                raise TBankUnavailable("T-Invest asset report has no report date")
            result.append(
                TBankAssetReport(
                    instrument_uid=instrument_uid,
                    report_date=report_date,
                    period_year=_int_value(item.get("periodYear"), "report period year"),
                    period_num=_int_value(item.get("periodNum"), "report period number"),
                    period_type=_text(item.get("periodType")).strip(),
                    created_at=_optional_provider_timestamp(item.get("createdAt")),
                )
            )
        return tuple(result)

    def get_asset_fundamentals(
        self,
        token: str,
        environment: TBankEnvironment,
        asset_uids: tuple[str, ...],
    ) -> tuple[TBankAssetFundamental, ...]:
        clean = tuple(
            dict.fromkeys(_validate_provider_id(value, "asset uid") for value in asset_uids)
        )
        if not clean:
            return ()
        if len(clean) > 100:
            raise ValueError("T-Invest fundamentals request supports at most 100 assets")
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetAssetFundamentals",
            body={"assets": list(clean)},
        )
        requested = set(clean)
        seen: set[str] = set()
        result: list[TBankAssetFundamental] = []
        for raw in _required_list(payload, "fundamentals"):
            item = _required_object(raw, "asset fundamental")
            asset_uid = _text(item.get("assetUid")).strip()
            if not asset_uid or asset_uid not in requested or asset_uid in seen:
                raise TBankUnavailable("T-Invest fundamentals returned invalid asset uid")
            seen.add(asset_uid)
            result.append(
                TBankAssetFundamental(
                    asset_uid=asset_uid,
                    currency=_text(item.get("currency")).strip().upper(),
                    revenue_ttm=_double_text(item.get("revenueTtm")),
                    ebitda_ttm=_double_text(item.get("ebitdaTtm")),
                    net_income_ttm=_double_text(item.get("netIncomeTtm")),
                    free_cash_flow_ttm=_double_text(item.get("freeCashFlowTtm")),
                    total_debt_mrq=_double_text(item.get("totalDebtMrq")),
                    total_debt_to_equity_mrq=_double_text(item.get("totalDebtToEquityMrq")),
                    total_debt_to_ebitda_mrq=_double_text(item.get("totalDebtToEbitdaMrq")),
                    net_debt_to_ebitda=_double_text(item.get("netDebtToEbitda")),
                    current_ratio_mrq=_double_text(item.get("currentRatioMrq")),
                    fixed_charge_coverage_ratio_fy=_double_text(
                        item.get("fixedChargeCoverageRatioFy")
                    ),
                    net_interest_margin_mrq=_double_text(item.get("netInterestMarginMrq")),
                    roe=_double_text(item.get("roe")),
                    roa=_double_text(item.get("roa")),
                    fiscal_period_start_date=_optional_provider_timestamp(
                        item.get("fiscalPeriodStartDate")
                    ),
                    fiscal_period_end_date=_optional_provider_timestamp(
                        item.get("fiscalPeriodEndDate")
                    ),
                )
            )
        return tuple(result)

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


def _validate_provider_id(value: str, name: str) -> str:
    clean = value.strip()
    if not clean or len(clean) > 256 or "\n" in clean or "\r" in clean:
        raise ValueError(f"{name} is invalid")
    return clean


def _instrument_window_body(
    instrument_uid: str,
    from_at: datetime,
    to_at: datetime,
) -> dict[str, object]:
    if from_at.tzinfo is None or to_at.tzinfo is None:
        raise ValueError("evidence window boundaries must be timezone-aware")
    if from_at > to_at:
        raise ValueError("evidence window start must not be after end")
    return {
        "instrumentId": _validate_provider_id(instrument_uid, "instrument uid"),
        "from": _utc_timestamp(from_at),
        "to": _utc_timestamp(to_at),
    }


def _int_value(value: object, name: str) -> int:
    if isinstance(value, bool) or value is None:
        raise TBankUnavailable(f"T-Invest {name} is invalid")
    try:
        return int(str(value))
    except ValueError as exc:
        raise TBankUnavailable(f"T-Invest {name} is invalid") from exc


def _optional_int(value: object, name: str) -> int | None:
    if value is None:
        return None
    return _int_value(value, name)


def _quotation_payload(value: str) -> dict[str, object]:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("quotation must be a decimal number") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("quotation must be finite and positive")
    exponent = amount.as_tuple().exponent
    if exponent < -9:
        raise ValueError("quotation supports at most 9 decimal places")
    units = int(amount)
    nano = int((amount - Decimal(units)) * Decimal(1_000_000_000))
    return {"units": str(units), "nano": nano}


def _double_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TBankUnavailable("T-Invest API returned invalid double value")
    number = Decimal(str(value))
    if not number.is_finite():
        raise TBankUnavailable("T-Invest API returned non-finite double value")
    # T-Invest documents zero in GetAssetFundamentals as missing data.
    if number == 0:
        return None
    return format(number.normalize(), "f")


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
        raise TBankUnavailable("T-Invest value has no timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TBankUnavailable("T-Invest value has invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise TBankUnavailable("T-Invest timestamp has no timezone")
    return parsed.astimezone(UTC)


def _optional_provider_timestamp(value: object) -> datetime | None:
    text = _text(value).strip()
    return _provider_timestamp(text) if text else None


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _optional_bool(payload: dict[str, object], key: str) -> bool | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TBankUnavailable(f"T-Invest API returned invalid {key} flag")
    return value


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
    if not amount.is_finite():
        raise TBankUnavailable("T-Invest API returned non-finite numeric value")
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
