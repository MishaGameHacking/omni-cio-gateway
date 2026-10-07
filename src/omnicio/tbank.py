"""Typed T-Invest REST reads and explicit, idempotent limit-order requests."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal, Never, cast
from urllib.parse import urlsplit
from uuid import UUID

TBankEnvironment = Literal["prod", "sandbox"]
TBankQuoteSource = Literal["exchange", "dealer"]

logger = logging.getLogger(__name__)

_REST_BASES: dict[TBankEnvironment, str] = {
    "prod": "https://invest-public-api.tbank.ru/rest/",
    "sandbox": "https://sandbox-invest-public-api.tbank.ru/rest/",
}
_API_PREFIX = "tinkoff.public.invest.api.contract.v1."
_INSTRUMENT_UID_FIELD = "instrument uid"


class TBankError(RuntimeError):
    """Base T-Invest provider failure that never contains the submitted token."""


class TBankTokenRejected(TBankError):
    """The provider rejected or cannot authorize the submitted token."""


class TBankUnavailable(TBankError):
    """The provider cannot be reached or returned an unusable response."""


class TBankNotFound(TBankUnavailable):
    """The requested provider object does not exist."""


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
class TBankRating:
    agency_name: str
    rating_level: str
    rating_date: datetime
    forecast: str
    is_under_watch: bool


@dataclass(frozen=True, slots=True)
class TBankHistoricCandle:
    instrument_uid: str
    close: str
    volume_lots: int
    time: datetime
    is_complete: bool
    source: str
    open: str | None = None
    high: str | None = None
    low: str | None = None


@dataclass(frozen=True, slots=True)
class TBankLastPrice:
    instrument_uid: str
    price: str
    time: datetime


@dataclass(frozen=True, slots=True)
class TBankLastPriceBatch:
    prices: tuple[TBankLastPrice, ...]
    unavailable_uids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TBankTradingStatus:
    instrument_uid: str
    trading_status: str
    limit_order_available: bool
    market_order_available: bool
    api_trade_available: bool
    best_price_order_available: bool
    only_best_price: bool


@dataclass(frozen=True, slots=True)
class TBankAccruedInterest:
    instrument_uid: str
    date: datetime
    value: str
    value_percent: str
    nominal: str


@dataclass(frozen=True, slots=True)
class TBankMarketYield:
    instrument_uid: str
    yield_percent: str
    time: datetime


@dataclass(frozen=True, slots=True)
class TBankOrderLevel:
    price: str
    quantity_lots: int


@dataclass(frozen=True, slots=True)
class TBankOrderBook:
    instrument_uid: str
    bids: tuple[TBankOrderLevel, ...]
    asks: tuple[TBankOrderLevel, ...]
    time: datetime | None
    is_consistent: bool


@dataclass(frozen=True, slots=True)
class TBankOrderState:
    order_id: str
    order_request_id: str
    instrument_uid: str
    execution_report_status: str
    lots_requested: int
    lots_executed: int
    total_order_amount: TBankMoney | None
    executed_commission: TBankMoney | None
    direction: str
    order_type: str


@dataclass(frozen=True, slots=True)
class TBankOrderEstimate:
    lots_requested: int
    total_order_amount: TBankMoney
    initial_order_amount: TBankMoney
    commission: TBankMoney


TBankSandboxOrderState = TBankOrderState


@dataclass(frozen=True, slots=True)
class TBankCancelResult:
    cancelled_at: datetime


TBankSandboxCancelResult = TBankCancelResult


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
    expected_yield_amount: str | None
    daily_yield: TBankMoney | None
    blocked: bool
    current_nkd: TBankMoney | None = None
    blocked_lots: str = "0"
    average_price_fifo: TBankMoney | None = None
    quantity_lots: str = "0"


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
    nominal: TBankMoney | None = None
    maturity_date: datetime | None = None
    floating_coupon: bool | None = None
    perpetual: bool | None = None
    amortization: bool | None = None
    subordinated: bool | None = None
    liquidity: bool | None = None
    exchange: str = ""
    first_1day_candle_date: datetime | None = None
    min_price_increment: str | None = None
    accrued_interest: TBankMoney | None = None


@dataclass(frozen=True, slots=True)
class TBankPortfolio:
    total: TBankMoney
    expected_yield_percent: str | None
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
    fix_date: datetime | None = None
    rate_date: datetime | None = None
    value: str | None = None


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
    market_capitalization: str | None = None
    pe_ratio_ttm: str | None = None
    price_to_sales_ttm: str | None = None
    price_to_book_ttm: str | None = None
    eps_ttm: str | None = None
    dividend_yield_daily_ttm: str | None = None
    forward_annual_dividend_yield: str | None = None
    dividend_payout_ratio_fy: str | None = None
    free_cash_flow_to_price: str | None = None


@dataclass(frozen=True, slots=True)
class TBankFundProfile:
    asset_uid: str
    total_expense_percent: str | None
    primary_index: str


@dataclass(frozen=True, slots=True)
class TBankNewsItem:
    id: str
    title: str
    summary: str
    content: str
    source: str
    source_url: str | None
    occurred_at: datetime
    instrument_uids: tuple[str, ...]
    priority: bool


@dataclass(frozen=True, slots=True)
class TBankNewsPage:
    items: tuple[TBankNewsItem, ...]
    next_cursor: str | None


def _market_value_quotes(
    item: dict[str, object],
) -> tuple[str | None, list[tuple[datetime, int, str, str, TBankQuoteSource]]]:
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
        quotes.append((parsed_time, source_priority, numeric, quote_time, source))
    return previous_close, quotes


def _ranked_usd_rub_quote(
    raw: object,
    candidate_by_uid: dict[str, TBankInstrument],
) -> tuple[datetime, int, TBankFxQuote] | None:
    item = _required_object(raw, "market value instrument")
    uid = _text(item.get("instrumentUid")).strip()
    instrument = candidate_by_uid.get(uid)
    if instrument is None:
        return None

    currency = _text(item.get("priceCurrency")).strip().upper()
    if currency != "RUB":
        return None

    previous_close, quotes = _market_value_quotes(item)
    if not quotes:
        return None

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
    return parsed_time, source_priority, quote


_INVALID_METADATA_LOT_ERROR = "T-Invest metadata has invalid lot size"


def _bond_rating(raw: object) -> TBankRating:
    item = _required_object(raw, "bond rating")
    agency = _text(item.get("agencyName")).strip()
    level = _text(item.get("ratingLevel")).strip()
    rating_date = _optional_provider_timestamp(item.get("ratingDate"))
    under_watch = _optional_bool(item, "isUnderWatch")
    if not agency or not level or rating_date is None or under_watch is None:
        raise TBankUnavailable("T-Invest bond rating is missing required fields")
    return TBankRating(
        agency_name=agency,
        rating_level=level,
        rating_date=rating_date,
        forecast=_text(item.get("forecast")).strip(),
        is_under_watch=under_watch,
    )


def _market_yield_value(
    item: dict[str, object],
) -> tuple[str, datetime] | None:
    for value_raw in _optional_list(item, "values"):
        value = _required_object(value_raw, "market value")
        if _text(value.get("type")).strip() != "INSTRUMENT_VALUE_YIELD":
            continue
        numeric = _quotation(value.get("value"))
        observed = _optional_provider_timestamp(value.get("time"))
        if numeric is None or observed is None:
            raise TBankUnavailable("T-Invest market yield is missing required fields")
        return numeric, observed
    return None


def _market_yield(
    raw: object,
    requested: set[str],
    seen: set[str],
) -> TBankMarketYield | None:
    item = _required_object(raw, "market value instrument")
    uid = _text(item.get("instrumentUid")).strip()
    if not uid or uid not in requested or uid in seen:
        raise TBankUnavailable(
            "T-Invest market values returned invalid instrument uid"
        )
    seen.add(uid)
    value = _market_yield_value(item)
    if value is None:
        return None
    yield_percent, observed = value
    return TBankMarketYield(
        instrument_uid=uid,
        yield_percent=yield_percent,
        time=observed,
    )


def _search_instrument(raw: object) -> TBankInstrument | None:
    item = _required_object(raw, "instrument")
    api_available = item.get("apiTradeAvailableFlag", False)
    if not isinstance(api_available, bool):
        raise TBankUnavailable(
            "T-Invest instrument has invalid API availability flag"
        )
    if not api_available:
        return None

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
    if not all(isinstance(value, bool) for value in (for_qual, for_iis, weekend)):
        raise TBankUnavailable("T-Invest instrument has invalid access flags")

    uid = _text(item.get("uid")).strip()
    ticker = _text(item.get("ticker")).strip()
    name = _text(item.get("name")).strip()
    if not uid or not ticker or not name:
        return None

    return TBankInstrument(
        uid=uid,
        figi=_text(item.get("figi")).strip(),
        ticker=ticker,
        name=name,
        instrument_type=_text(item.get("instrumentType")).strip(),
        class_code=_text(item.get("classCode")).strip(),
        lot=lot,
        for_qual_investor=cast(bool, for_qual),
        for_iis=cast(bool, for_iis),
        weekend_trading=cast(bool, weekend),
    )


def _operation_trade(raw: object) -> TBankOperationTrade:
    trade = _required_object(raw, "operation trade")
    trade_date = _optional_provider_timestamp(trade.get("date"))
    if trade_date is None:
        raise TBankUnavailable("T-Invest operation trade has no date")
    return TBankOperationTrade(
        num=_text(trade.get("num")).strip(),
        date=trade_date,
        quantity=_integer_text(trade.get("quantity")),
        price=_money(trade.get("price")),
    )


def _operation_trades(item: dict[str, object]) -> tuple[TBankOperationTrade, ...]:
    trades_info = item.get("tradesInfo")
    if trades_info is None:
        return ()
    rows = _optional_list(
        _required_object(trades_info, "operation trades"),
        "trades",
    )
    return tuple(_operation_trade(raw) for raw in rows)


def _operation(raw: object) -> TBankOperation:
    item = _required_object(raw, "operation item")
    operation_date = _optional_provider_timestamp(item.get("date"))
    if operation_date is None:
        raise TBankUnavailable("T-Invest operation item has no date")
    return TBankOperation(
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
        trades=_operation_trades(item),
    )


def _operation_page_cursor(payload: dict[str, object]) -> tuple[bool, str]:
    has_next = payload.get("hasNext", False)
    if not isinstance(has_next, bool):
        raise TBankUnavailable("T-Invest operation page has invalid hasNext flag")
    next_cursor = _text(payload.get("nextCursor")).strip()
    if has_next and not next_cursor:
        raise TBankUnavailable("T-Invest operation page is missing next cursor")
    return has_next, next_cursor


def _instrument_metadata(
    item: dict[str, object], instrument_type: str,
) -> TBankInstrumentMetadata:
    uid = _text(item.get("uid")).strip()
    if not uid:
        raise TBankUnavailable("T-Invest metadata has missing or duplicate uid")
    lot_raw = item.get("lot", 0)
    if isinstance(lot_raw, bool):
        raise TBankUnavailable(_INVALID_METADATA_LOT_ERROR)
    try:
        lot = int(str(lot_raw))
    except ValueError as exc:
        raise TBankUnavailable(_INVALID_METADATA_LOT_ERROR) from exc
    if lot < 0:
        raise TBankUnavailable(_INVALID_METADATA_LOT_ERROR)
    required_tests = tuple(
        _text(value).strip()
        for value in _optional_list(item, "requiredTests")
        if _text(value).strip()
    )
    return TBankInstrumentMetadata(
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
        nominal=_money(item.get("nominal")),
        maturity_date=_optional_provider_timestamp(item.get("maturityDate")),
        floating_coupon=_optional_bool(item, "floatingCouponFlag"),
        perpetual=_optional_bool(item, "perpetualFlag"),
        amortization=_optional_bool(item, "amortizationFlag"),
        subordinated=_optional_bool(item, "subordinatedFlag"),
        liquidity=_optional_bool(item, "liquidityFlag"),
        exchange=_text(item.get("exchange")).strip(),
        first_1day_candle_date=_optional_provider_timestamp(item.get("first1dayCandleDate")),
        min_price_increment=_quotation(item.get("minPriceIncrement")),
        accrued_interest=_money(item.get("aciValue")),
    )


def _asset_fundamental(
    raw: object,
    requested: set[str],
    seen: set[str],
) -> TBankAssetFundamental:
    item = _required_object(raw, "asset fundamental")
    asset_uid = _text(item.get("assetUid")).strip()
    if not asset_uid or asset_uid not in requested or asset_uid in seen:
        raise TBankUnavailable("T-Invest fundamentals returned invalid asset uid")
    seen.add(asset_uid)
    return TBankAssetFundamental(
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
        market_capitalization=_double_text(item.get("marketCapitalization")),
        pe_ratio_ttm=_double_text(item.get("peRatioTtm")),
        price_to_sales_ttm=_double_text(item.get("priceToSalesTtm")),
        price_to_book_ttm=_double_text(item.get("priceToBookTtm")),
        eps_ttm=_double_text(item.get("epsTtm")),
        dividend_yield_daily_ttm=_double_text(item.get("dividendYieldDailyTtm")),
        forward_annual_dividend_yield=_double_text(item.get("forwardAnnualDividendYield")),
        dividend_payout_ratio_fy=_double_text(item.get("dividendPayoutRatioFy")),
        free_cash_flow_to_price=_double_text(item.get("freeCashFlowToPrice")),
    )


def _validate_exchange_candle_window(
    from_at: datetime,
    to_at: datetime,
    interval: str,
) -> None:
    bounds = {
        "CANDLE_INTERVAL_5_MIN": (timedelta(minutes=5), timedelta(days=7)),
        "CANDLE_INTERVAL_30_MIN": (timedelta(minutes=30), timedelta(weeks=3)),
        "CANDLE_INTERVAL_HOUR": (timedelta(hours=1), timedelta(days=93)),
        "CANDLE_INTERVAL_4_HOUR": (timedelta(hours=4), timedelta(days=93)),
        "CANDLE_INTERVAL_DAY": (timedelta(days=1), timedelta(days=366 * 6)),
        "CANDLE_INTERVAL_MONTH": (timedelta(days=28), timedelta(days=366 * 10)),
    }.get(interval)
    if bounds is None:
        raise ValueError("unsupported candle interval")
    if from_at.tzinfo is None or to_at.tzinfo is None:
        raise ValueError("candle boundaries must be timezone-aware")
    if from_at > to_at:
        raise ValueError("candle start must not be after end")

    requested_window = to_at - from_at
    min_window, max_window = bounds
    if requested_window < min_window:
        raise ValueError("candle window must cover at least one candle interval")
    if requested_window > max_window:
        raise ValueError("candle window exceeds interval limit")


_HISTORIC_CANDLE_REQUIRED_FIELDS_ERROR = (
    "T-Invest historic candle is missing required fields"
)


def _required_historic_candle_price(
    item: dict[str, object],
    key: str,
) -> str:
    value = _quotation(item.get(key))
    if value is None:
        raise TBankUnavailable(_HISTORIC_CANDLE_REQUIRED_FIELDS_ERROR)
    return value


def _historic_candle_volume(value: object) -> int:
    if isinstance(value, bool):
        raise TBankUnavailable(_HISTORIC_CANDLE_REQUIRED_FIELDS_ERROR)
    try:
        volume = int(str(value))
    except ValueError as exc:
        raise TBankUnavailable("T-Invest historic candle has invalid volume") from exc
    if volume < 0:
        raise TBankUnavailable("T-Invest historic candle has negative volume")
    return volume


def _historic_exchange_candle(
    raw: object,
    instrument_uid: str,
) -> TBankHistoricCandle:
    item = _required_object(raw, "historic candle")
    open_value = _required_historic_candle_price(item, "open")
    high = _required_historic_candle_price(item, "high")
    low = _required_historic_candle_price(item, "low")
    close = _required_historic_candle_price(item, "close")
    candle_time = _optional_provider_timestamp(item.get("time"))
    complete = item.get("isComplete")
    if candle_time is None or not isinstance(complete, bool):
        raise TBankUnavailable(_HISTORIC_CANDLE_REQUIRED_FIELDS_ERROR)

    source_name = _text(item.get("candleSourceType")).strip()
    if source_name != "CANDLE_SOURCE_EXCHANGE":
        raise TBankUnavailable(
            "T-Invest historic candle is not confirmed exchange-sourced"
        )

    volume = _historic_candle_volume(item.get("volume"))
    open_decimal = Decimal(open_value)
    high_decimal = Decimal(high)
    low_decimal = Decimal(low)
    close_decimal = Decimal(close)
    if any(
        value <= 0
        for value in (open_decimal, high_decimal, low_decimal, close_decimal)
    ):
        raise TBankUnavailable("T-Invest historic candle has non-positive OHLC")
    if high_decimal < low_decimal:
        raise TBankUnavailable("T-Invest historic candle has invalid high/low")
    if not (
        low_decimal <= open_decimal <= high_decimal
        and low_decimal <= close_decimal <= high_decimal
    ):
        raise TBankUnavailable("T-Invest historic candle OHLC is inconsistent")

    return TBankHistoricCandle(
        instrument_uid=instrument_uid,
        close=close,
        volume_lots=volume,
        time=candle_time,
        is_complete=complete,
        source=source_name,
        open=open_value,
        high=high,
        low=low,
    )


def _news_item(raw: object) -> TBankNewsItem:
    item = _required_object(raw, "news item")
    ident, title = str(item.get("id", "")), _text(item.get("title")).strip()
    when = _optional_provider_timestamp(item.get("ts"))
    priority = item.get("priority", False)
    if (not ident.isdecimal() or len(ident) > 19 or not title or len(title) > 1000
            or when is None or type(priority) is not bool):
        raise TBankUnavailable("news item invalid")
    source = _text(item.get("source")).strip()
    try:
        parsed = urlsplit(source)
    except ValueError as exc:
        raise TBankUnavailable("news source invalid") from exc
    source_url = source if (parsed.scheme == "https" and parsed.hostname
                            and not parsed.username and not parsed.password) else None
    uids = []
    for raw_link in _optional_list(item, "instrumentId"):
        link = _required_object(raw_link, "news instrument link")
        instrument = _required_object(link.get("instrument"), "news instrument")
        uid = _text(instrument.get("instrumentUid")).strip()
        if not uid or len(uid) > 200:
            raise TBankUnavailable("news instrument identity invalid")
        uids.append(uid)
    summary, content = _text(item.get("summary")), _text(item.get("content"))
    if len(summary) > 20000 or len(content) > 200000 or len(source) > 2000 or len(uids) > 200:
        raise TBankUnavailable("news content exceeded limit")
    return TBankNewsItem(ident, title, summary, content, source, source_url, when,
                         tuple(dict.fromkeys(uids)), priority)


def _raise_tbank_http_error(
    method: str,
    exc: urllib.error.HTTPError,
) -> Never:
    tracking_id = exc.headers.get("x-tracking-id", "")
    logger.warning(
        "T-Invest request failed method=%s status=%s tracking_id=%s",
        method,
        exc.code,
        tracking_id or "-",
    )
    if exc.code in {401, 403}:
        raise TBankTokenRejected("T-Invest token was rejected") from exc
    if exc.code == 404:
        raise TBankNotFound("T-Invest object was not found") from exc
    if exc.code == 429 or exc.code >= 500:
        raise TBankUnavailable(
            f"T-Invest API unavailable: HTTP {exc.code}"
        ) from exc
    raise TBankUnavailable(
        f"T-Invest API rejected request: HTTP {exc.code}"
    ) from exc


def _raise_tbank_url_error(
    method: str,
    exc: urllib.error.URLError,
) -> Never:
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


def _read_tbank_response(
    request: urllib.request.Request,
    *,
    timeout_seconds: int,
    method: str,
) -> str:
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            raw = response.read()
            if not isinstance(raw, bytes):
                raise TBankUnavailable(
                    "T-Invest API returned invalid response body"
                )
            return raw.decode()
    except urllib.error.HTTPError as exc:
        _raise_tbank_http_error(method, exc)
    except urllib.error.URLError as exc:
        _raise_tbank_url_error(method, exc)
    except TimeoutError as exc:
        logger.warning("T-Invest request timed out method=%s", method)
        raise TBankUnavailable("T-Invest API request timed out") from exc


def _decode_tbank_response(raw: str) -> dict[str, object]:
    try:
        payload_raw = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TBankUnavailable("T-Invest API returned invalid JSON") from exc
    if not isinstance(payload_raw, dict):
        raise TBankUnavailable("T-Invest API returned invalid payload")
    return cast(dict[str, object], payload_raw)


@dataclass(frozen=True, slots=True)
class TBankInvestClient:
    timeout_seconds: int = 10

    def get_news(
        self, token: str, environment: TBankEnvironment, *, cursor: str | None = None,
        limit: int = 50,
    ) -> TBankNewsPage:
        if type(limit) is not int or not 1 <= limit <= 50 or (
            cursor is not None and (not isinstance(cursor, str) or not cursor.isdecimal()
                                   or len(cursor) > 19 or int(cursor) > 2**63 - 1)
        ):
            raise ValueError("news_page_parameters_invalid")
        body: dict[str, object] = {"limit": limit}
        if cursor is not None:
            body["cursor"] = cursor
        payload = self._post(token=token, environment=environment,
                             service="InstrumentsService", method="News", body=body)
        raw_items = _required_list(payload, "items")
        if len(raw_items) > limit:
            raise TBankUnavailable("news page exceeded requested limit")
        items = tuple(_news_item(raw) for raw in raw_items)
        if len({item.id for item in items}) != len(items):
            raise TBankUnavailable("duplicate news identity")
        next_cursor = str(payload.get("nextCursor", "0"))
        if not next_cursor.isdecimal() or len(next_cursor) > 19 or int(next_cursor) > 2**63 - 1:
            raise TBankUnavailable("news cursor invalid")
        if cursor is not None and next_cursor == cursor and items:
            raise TBankUnavailable("news cursor did not advance")
        return TBankNewsPage(items, next_cursor if next_cursor != "0" else None)

    def get_fund_profile(
        self, token: str, environment: TBankEnvironment, asset_uid: str,
    ) -> TBankFundProfile:
        """GetAssetBy's documented ETF fields; a name is never constituent evidence."""
        ident = _validate_provider_id(asset_uid, "asset uid")
        payload = self._post(token=token, environment=environment,
                             service="InstrumentsService", method="GetAssetBy", body={"id": ident})
        asset = _required_object(payload.get("asset"), "asset")
        if asset.get("uid") != ident:
            raise TBankUnavailable("fund profile identity mismatch")
        security = _required_object(asset.get("security"), "asset security")
        if security.get("type") != "etf":
            raise TBankUnavailable("fund profile type mismatch")
        fund = _required_object(security.get("etf"), "asset fund")
        expense = _quotation(fund.get("totalExpense"))
        if expense is not None and not 0 <= Decimal(expense) <= 100:
            raise TBankUnavailable("fund expenses invalid")
        return TBankFundProfile(ident, expense, _text(fund.get("primaryIndex")).strip())

    def get_instrument_metadata(
        self, token: str, environment: TBankEnvironment, instrument_type: str,
    ) -> tuple[TBankInstrumentMetadata, ...]:
        method = {"share": "Shares", "bond": "Bonds", "etf": "Etfs"}.get(instrument_type)
        if method is None:
            raise ValueError("unsupported metadata instrument type")
        payload = self._post(
            token=token, environment=environment, service="InstrumentsService", method=method,
            body={"instrumentStatus": "INSTRUMENT_STATUS_ALL"},
        )
        result, seen = [], set()
        for raw in _required_list(payload, "instruments"):
            item = _instrument_metadata(
                _required_object(raw, "instrument metadata"), instrument_type,
            )
            if item.uid in seen:
                raise TBankUnavailable("T-Invest metadata has missing or duplicate uid")
            seen.add(item.uid)
            result.append(item)
        return tuple(result)

    def _instrument_by(
        self, token: str, environment: TBankEnvironment, instrument_uid: str,
        *, method: str = "GetInstrumentBy",
    ) -> dict[str, object]:
        instrument = _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD)
        payload = self._post(
            token=token, environment=environment, service="InstrumentsService", method=method,
            body={"idType": "INSTRUMENT_ID_TYPE_UID", "id": instrument},
        )
        item = _required_object(payload.get("instrument"), "instrument metadata")
        if item.get("uid") != instrument:
            raise TBankUnavailable("instrument metadata identity mismatch")
        return item

    def get_instrument_overview(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
    ) -> TBankInstrumentMetadata:
        item = self._instrument_by(token, environment, instrument_uid)
        return _instrument_metadata(item, _text(item.get("instrumentType")).strip())

    def get_execution_instrument(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
    ) -> TBankInstrumentMetadata:
        value = self.get_instrument_overview(token, environment, instrument_uid)
        if value.instrument_type == "bond":
            value = _instrument_metadata(
                self._instrument_by(token, environment, instrument_uid, method="BondBy"), "bond"
            )
        return value

    def estimate_limit_order(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        instrument_uid: str,
        lots: int,
        price: Decimal,
        action: str,
    ) -> TBankOrderEstimate:
        body = _limit_order_body(account_id, instrument_uid, lots, price, action)
        payload = self._post(
            token=token,
            environment=environment,
            service="SandboxService" if environment == "sandbox" else "OrdersService",
            method="GetSandboxOrderPrice" if environment == "sandbox" else "GetOrderPrice",
            body=body,
        )
        total = _money(payload.get("totalOrderAmount"))
        initial = _money(payload.get("initialOrderAmount"))
        commission = _money(payload.get("executedCommission"))
        if _int_value(payload.get("lotsRequested"), "lotsRequested") != lots or any(
            value is None or value.currency.upper() != "RUB" or Decimal(value.value) < 0
            for value in (total, initial, commission)
        ):
            raise TBankUnavailable("order estimate is incomplete")
        assert total is not None and initial is not None and commission is not None
        return TBankOrderEstimate(lots, total, initial, commission)

    def submit_limit_order(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        instrument_uid: str,
        lots: int,
        price: Decimal,
        action: str,
        request_id: str,
    ) -> TBankOrderState:
        ident = str(UUID(request_id))
        body = _limit_order_body(account_id, instrument_uid, lots, price, action)
        body.update(
            {
                "orderId": ident,
                "orderType": "ORDER_TYPE_LIMIT",
                "priceType": "PRICE_TYPE_CURRENCY",
                "timeInForce": "TIME_IN_FORCE_FILL_AND_KILL",
                "confirmMarginTrade": False,
            }
        )
        payload = self._post(
            token=token,
            environment=environment,
            service="SandboxService" if environment == "sandbox" else "OrdersService",
            method="PostSandboxOrder" if environment == "sandbox" else "PostOrder",
            body=body,
        )
        return _order_state(payload, expected_request_id=ident)

    def get_bond_ratings(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
    ) -> tuple[TBankRating, ...]:
        instrument = _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD)
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="BondBy",
            body={
                "idType": "INSTRUMENT_ID_TYPE_UID",
                "id": instrument,
            },
        )
        raw_instrument = _required_object(payload.get("instrument"), "bond")
        returned_uid = _text(raw_instrument.get("uid")).strip()
        if returned_uid != instrument:
            raise TBankUnavailable(
                "T-Invest bond rating lookup returned a different instrument"
            )
        return tuple(
            _bond_rating(raw)
            for raw in _optional_list(raw_instrument, "ratings")
        )

    def first_daily_candle(
        self, token: str, environment: TBankEnvironment, instrument_uid: str,
    ) -> datetime | None:
        item = self._instrument_by(token, environment, instrument_uid)
        first = _optional_provider_timestamp(item.get("first1dayCandleDate"))
        if first is not None:
            return first
        method = {
            "share": "ShareBy", "bond": "BondBy", "etf": "EtfBy",
            "currency": "CurrencyBy", "futures": "FutureBy", "option": "OptionBy",
        }.get(str(item.get("instrumentType", "")))
        if method is None:
            return None
        item = self._instrument_by(token, environment, instrument_uid, method=method)
        return _optional_provider_timestamp(item.get("first1dayCandleDate"))

    def get_exchange_candles(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
        interval: str,
    ) -> tuple[TBankHistoricCandle, ...]:
        instrument = _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD)
        _validate_exchange_candle_window(from_at, to_at, interval)
        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetCandles",
            body={
                "instrumentId": instrument,
                "from": _utc_timestamp(from_at),
                "to": _utc_timestamp(to_at),
                "interval": interval,
                "candleSourceType": "CANDLE_SOURCE_EXCHANGE",
            },
        )

        result: list[TBankHistoricCandle] = []
        seen_times: set[datetime] = set()
        for raw in _required_list(payload, "candles"):
            candle = _historic_exchange_candle(raw, instrument)
            if candle.time in seen_times:
                raise TBankUnavailable(
                    "T-Invest historic candles contain duplicate timestamps"
                )
            seen_times.add(candle.time)
            result.append(candle)
        return tuple(result)

    def get_daily_exchange_candles(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankHistoricCandle, ...]:
        return self.get_exchange_candles(
            token,
            environment,
            instrument_uid,
            from_at=from_at,
            to_at=to_at,
            interval="CANDLE_INTERVAL_DAY",
        )

    def get_trading_status(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
    ) -> TBankTradingStatus:
        instrument = _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD)
        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetTradingStatus",
            body={"instrumentId": instrument},
        )
        returned_uid = _text(payload.get("instrumentUid")).strip()
        if returned_uid != instrument:
            raise TBankUnavailable(
                "T-Invest trading status returned a different instrument"
            )

        limit_order_available = _optional_bool(payload, "limitOrderAvailableFlag")
        market_order_available = _optional_bool(payload, "marketOrderAvailableFlag")
        api_trade_available = _optional_bool(payload, "apiTradeAvailableFlag")
        best_price_order_available = _optional_bool(
            payload,
            "bestpriceOrderAvailableFlag",
        )
        only_best_price = _optional_bool(payload, "onlyBestPrice")
        if (
            limit_order_available is None
            or market_order_available is None
            or api_trade_available is None
            or best_price_order_available is None
            or only_best_price is None
        ):
            raise TBankUnavailable("T-Invest trading status is missing availability flags")

        trading_status = _text(payload.get("tradingStatus")).strip()
        if not trading_status:
            raise TBankUnavailable("T-Invest trading status is missing")
        return TBankTradingStatus(
            instrument_uid=instrument,
            trading_status=trading_status,
            limit_order_available=limit_order_available,
            market_order_available=market_order_available,
            api_trade_available=api_trade_available,
            best_price_order_available=best_price_order_available,
            only_best_price=only_best_price,
        )

    def get_last_prices(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankLastPrice, ...]:
        batch = self.get_last_prices_batch(token, environment, instrument_uids)
        if batch.unavailable_uids:
            # Existing planning/execution readers require all returned evidence
            # to be valid. UI display has a separate, explicitly partial contract.
            raise TBankUnavailable("T-Invest last price is missing required fields")
        return batch.prices

    def get_last_prices_batch(
        self, token: str, environment: TBankEnvironment, instrument_uids: tuple[str, ...],
    ) -> TBankLastPriceBatch:
        clean = tuple(
            dict.fromkeys(
                _validate_provider_id(value, _INSTRUMENT_UID_FIELD)
                for value in instrument_uids
            )
        )
        if not clean:
            return TBankLastPriceBatch(())
        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetLastPrices",
            body={
                "instrumentId": list(clean),
                "lastPriceType": "LAST_PRICE_EXCHANGE",
                "instrumentStatus": "INSTRUMENT_STATUS_BASE",
            },
        )
        requested = set(clean)
        seen: set[str] = set()
        result: list[TBankLastPrice] = []
        unavailable: list[str] = []
        for raw in _required_list(payload, "lastPrices"):
            item = _required_object(raw, "last price")
            uid = _text(item.get("instrumentUid")).strip()
            if not uid or uid not in requested or uid in seen:
                raise TBankUnavailable("T-Invest last prices returned invalid instrument uid")
            seen.add(uid)
            try:
                price = _quotation(item.get("price"))
                quote_time = _optional_provider_timestamp(item.get("time"))
                if price is None or Decimal(price) <= 0 or quote_time is None:
                    raise TBankUnavailable("T-Invest last price is missing required fields")
            except TBankUnavailable:
                unavailable.append(uid)
                continue
            result.append(
                TBankLastPrice(
                    instrument_uid=uid,
                    price=price,
                    time=quote_time,
                )
            )
        return TBankLastPriceBatch(tuple(result), tuple(unavailable))

    def get_accrued_interests(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        from_at: datetime,
        to_at: datetime,
    ) -> tuple[TBankAccruedInterest, ...]:
        payload = self._post(
            token=token,
            environment=environment,
            service="InstrumentsService",
            method="GetAccruedInterests",
            body=_instrument_window_body(instrument_uid, from_at, to_at),
        )
        result: list[TBankAccruedInterest] = []
        seen: set[datetime] = set()
        for raw in _required_list(payload, "accruedInterests"):
            item = _required_object(raw, "accrued interest")
            date = _optional_provider_timestamp(item.get("date"))
            value = _quotation(item.get("value"))
            value_percent = _quotation(item.get("valuePercent"))
            nominal = _quotation(item.get("nominal"))
            if (
                date is None
                or value is None
                or value_percent is None
                or nominal is None
                or Decimal(nominal) <= 0
                or Decimal(value) < 0
                or Decimal(value_percent) < 0
                or date in seen
            ):
                raise TBankUnavailable("T-Invest accrued interest is missing required fields")
            seen.add(date)
            result.append(
                TBankAccruedInterest(
                    instrument_uid=instrument_uid,
                    date=date,
                    value=value,
                    value_percent=value_percent,
                    nominal=nominal,
                )
            )
        return tuple(result)

    def get_market_yields(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uids: tuple[str, ...],
    ) -> tuple[TBankMarketYield, ...]:
        clean = tuple(
            dict.fromkeys(
                _validate_provider_id(value, _INSTRUMENT_UID_FIELD)
                for value in instrument_uids
            )
        )
        if not clean:
            return ()
        if len(clean) > 100:
            raise ValueError("market yield batch must contain at most 100 instruments")
        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetMarketValues",
            body={
                "instrumentId": list(clean),
                "values": ["INSTRUMENT_VALUE_YIELD"],
            },
        )
        requested = set(clean)
        seen: set[str] = set()
        result = (
            _market_yield(raw, requested, seen)
            for raw in _required_list(payload, "instruments")
        )
        return tuple(item for item in result if item is not None)

    def get_order_book(
        self,
        token: str,
        environment: TBankEnvironment,
        instrument_uid: str,
        *,
        depth: int = 10,
    ) -> TBankOrderBook:
        instrument = _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD)
        if not 1 <= depth <= 50:
            raise ValueError("order book depth must be between 1 and 50")
        payload = self._post(
            token=token,
            environment=environment,
            service="MarketDataService",
            method="GetOrderBook",
            body={"instrumentId": instrument, "depth": depth},
        )
        bids = _order_levels(payload, "bids")
        asks = _order_levels(payload, "asks")
        consistent = payload.get("isConsistent", False)
        if not isinstance(consistent, bool):
            raise TBankUnavailable("T-Invest order book has invalid consistency flag")
        returned_uid = _text(payload.get("instrumentUid")).strip() or instrument
        if returned_uid != instrument:
            raise TBankUnavailable("T-Invest order book returned a different instrument")
        return TBankOrderBook(
            instrument_uid=instrument,
            bids=bids,
            asks=asks,
            time=_optional_provider_timestamp(payload.get("time")),
            is_consistent=consistent,
        )


    def get_order_state(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        request_id: str,
        price_type: Literal["point", "currency"],
    ) -> TBankOrderState:
        _require_prod(environment)
        return self._get_order_state(
            token,
            environment,
            service="OrdersService",
            method="GetOrderState",
            account_id=account_id,
            request_id=request_id,
            price_type=price_type,
        )

    def get_sandbox_order_state(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        request_id: str,
        price_type: Literal["point", "currency"],
    ) -> TBankOrderState:
        _require_sandbox(environment)
        return self._get_order_state(
            token,
            environment,
            service="SandboxService",
            method="GetSandboxOrderState",
            account_id=account_id,
            request_id=request_id,
            price_type=price_type,
        )

    def _get_order_state(
        self,
        token: str,
        environment: TBankEnvironment,
        *,
        service: str,
        method: str,
        account_id: str,
        request_id: str,
        price_type: Literal["point", "currency"],
    ) -> TBankOrderState:
        request_uuid = _validate_request_uuid(request_id)
        payload = self._post(
            token=token,
            environment=environment,
            service=service,
            method=method,
            body={
                "accountId": _validate_account_id(account_id),
                "orderId": request_uuid,
                "priceType": _provider_price_type(price_type),
                "orderIdType": "ORDER_ID_TYPE_REQUEST",
            },
        )
        return _order_state(payload, expected_request_id=request_uuid)

    def cancel_order(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        request_id: str,
    ) -> TBankCancelResult:
        _require_prod(environment)
        return self._cancel_order(
            token,
            environment,
            service="OrdersService",
            method="CancelOrder",
            account_id=account_id,
            request_id=request_id,
        )

    def cancel_sandbox_order(
        self,
        token: str,
        environment: TBankEnvironment,
        account_id: str,
        *,
        request_id: str,
    ) -> TBankCancelResult:
        _require_sandbox(environment)
        return self._cancel_order(
            token,
            environment,
            service="SandboxService",
            method="CancelSandboxOrder",
            account_id=account_id,
            request_id=request_id,
        )

    def _cancel_order(
        self,
        token: str,
        environment: TBankEnvironment,
        *,
        service: str,
        method: str,
        account_id: str,
        request_id: str,
    ) -> TBankCancelResult:
        request_uuid = _validate_request_uuid(request_id)
        payload = self._post(
            token=token,
            environment=environment,
            service=service,
            method=method,
            body={
                "accountId": _validate_account_id(account_id),
                "orderId": request_uuid,
                "orderIdType": "ORDER_ID_TYPE_REQUEST",
            },
        )
        cancelled_at = _optional_provider_timestamp(payload.get("time"))
        if cancelled_at is None:
            raise TBankUnavailable("T-Invest cancellation has no timestamp")
        return TBankCancelResult(cancelled_at=cancelled_at)


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
            instrument = _search_instrument(raw)
            if instrument is not None:
                instruments.append(instrument)
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
            ranked = _ranked_usd_rub_quote(raw, candidate_by_uid)
            if ranked is None:
                continue
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
                    expected_yield_amount=_quotation(position.get("expectedYield")),
                    daily_yield=_money(position.get("dailyYield")),
                    blocked=blocked_raw,
                    current_nkd=_money(position.get("currentNkd")),
                    blocked_lots=_quotation(position.get("blockedLots")) or "0",
                    average_price_fifo=_money(position.get("averagePositionPriceFifo")),
                    quantity_lots=_quotation(position.get("quantityLots")) or "0",
                )
            )

        return TBankPortfolio(
            total=total,
            expected_yield_percent=_quotation(payload.get("expectedYield")),
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
            service="OperationsService",
            method="GetOperationsByCursor",
            body=body,
        )
        has_next, next_cursor = _operation_page_cursor(payload)
        return TBankOperationsPage(
            has_next=has_next,
            next_cursor=next_cursor,
            items=tuple(
                _operation(raw)
                for raw in _required_list(payload, "items")
            ),
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
                    fix_date=_optional_provider_timestamp(item.get("fixDate")),
                    rate_date=_optional_provider_timestamp(item.get("rateDate")),
                    value=_quotation(item.get("value")),
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
            dict.fromkeys(
                _validate_provider_id(value, "asset uid")
                for value in asset_uids
            )
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
        return tuple(
            _asset_fundamental(raw, requested, seen)
            for raw in _required_list(payload, "fundamentals")
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
        raw = _read_tbank_response(
            request,
            timeout_seconds=self.timeout_seconds,
            method=method,
        )
        return _decode_tbank_response(raw)


def _require_prod(environment: TBankEnvironment) -> None:
    if environment != "prod":
        raise ValueError("production order requires production environment")


def _require_sandbox(environment: TBankEnvironment) -> None:
    if environment != "sandbox":
        raise ValueError("sandbox mutation requires sandbox environment")


def _validate_request_uuid(value: str) -> str:
    clean = value.strip()
    try:
        parsed = UUID(clean)
    except ValueError as exc:
        raise ValueError("order request id must be a UUID") from exc
    canonical = str(parsed)
    if clean.lower() != canonical:
        raise ValueError("order request id must use canonical UUID form")
    return canonical


def _provider_price_type(value: Literal["point", "currency"]) -> str:
    return {
        "point": "PRICE_TYPE_POINT",
        "currency": "PRICE_TYPE_CURRENCY",
    }[value]


def _limit_order_body(
    account_id: str, instrument_uid: str, lots: int, price: Decimal, action: str,
) -> dict[str, object]:
    if (type(lots) is not int or not 0 < lots <= 10**9 or action not in {"buy", "sell"}
            or not price.is_finite() or not 0 < price <= Decimal("1e12")
            or price * 10**9 != (price * 10**9).to_integral_value()):
        raise ValueError("limit_order_parameters_invalid")
    units = int(price)
    return {"accountId": _validate_provider_id(account_id, "account id"),
            "instrumentId": _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD),
            "quantity": str(lots), "price": {"units": str(units), "nano": int((price-units)*10**9)},
            "direction": "ORDER_DIRECTION_BUY" if action == "buy" else "ORDER_DIRECTION_SELL"}


def _order_state(
    payload: dict[str, object],
    *,
    expected_request_id: str,
) -> TBankOrderState:
    request_id = _text(payload.get("orderRequestId")).strip()
    order_id = _text(payload.get("orderId")).strip()
    instrument_uid = _text(payload.get("instrumentUid")).strip()
    execution_status = _text(payload.get("executionReportStatus")).strip()
    lots_requested = _int_value(
        payload.get("lotsRequested"),
        "lotsRequested",
    )
    lots_executed = _int_value(
        payload.get("lotsExecuted"),
        "lotsExecuted",
    )
    if request_id != expected_request_id:
        raise TBankUnavailable(
            "T-Invest order returned a different request id"
        )
    if not order_id or not instrument_uid or not execution_status:
        raise TBankUnavailable(
            "T-Invest order state is missing identity fields"
        )
    if (
        lots_requested <= 0
        or lots_executed < 0
        or lots_executed > lots_requested
    ):
        raise TBankUnavailable(
            "T-Invest order state has invalid lot counts"
        )
    return TBankOrderState(
        order_id=order_id,
        order_request_id=request_id,
        instrument_uid=instrument_uid,
        execution_report_status=execution_status,
        lots_requested=lots_requested,
        lots_executed=lots_executed,
        total_order_amount=_money(payload.get("totalOrderAmount")),
        executed_commission=_money(payload.get("executedCommission")),
        direction=_text(payload.get("direction")).strip(),
        order_type=_text(payload.get("orderType")).strip(),
    )


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
        "instrumentId": _validate_provider_id(instrument_uid, _INSTRUMENT_UID_FIELD),
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


_INVALID_INTEGER_VALUE_ERROR = "T-Invest API returned invalid integer value"


def _integer_text(value: object) -> str:
    if value is None:
        return "0"
    if isinstance(value, bool):
        raise TBankUnavailable(_INVALID_INTEGER_VALUE_ERROR)
    if isinstance(value, (str, int)):
        text = str(value)
        try:
            int(text)
        except ValueError as exc:
            raise TBankUnavailable(_INVALID_INTEGER_VALUE_ERROR) from exc
        return text
    raise TBankUnavailable(_INVALID_INTEGER_VALUE_ERROR)


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


def _order_levels(
    payload: dict[str, object],
    key: str,
) -> tuple[TBankOrderLevel, ...]:
    result: list[TBankOrderLevel] = []
    for raw in _optional_list(payload, key):
        item = _required_object(raw, f"order book {key} level")
        price = _quotation(item.get("price"))
        quantity_raw = item.get("quantity")
        if price is None or isinstance(quantity_raw, bool):
            raise TBankUnavailable("T-Invest order book has invalid level")
        try:
            quantity = int(str(quantity_raw))
        except ValueError as exc:
            raise TBankUnavailable("T-Invest order book has invalid quantity") from exc
        if Decimal(price) <= 0 or quantity <= 0:
            raise TBankUnavailable("T-Invest order book has non-positive level")
        result.append(TBankOrderLevel(price=price, quantity_lots=quantity))
    return tuple(result)


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
