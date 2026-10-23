"""Broker-sourced dashboard. No trading methods, invented history or currency conversion."""
from __future__ import annotations

import copy
import hashlib
import time
from collections import OrderedDict, defaultdict
from contextlib import closing
from datetime import date, datetime, time as day_time, timedelta, timezone
from decimal import Decimal
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from . import app as backend
    from . import tinvest_portfolio as portfolio
    from .volume_contract import decimal as strict_decimal
    from .ai_jobs import assert_current_owner_in
    from .monitoring_access import assert_monitoring_access_in, monitoring_active
except ImportError:
    import app as backend
    import tinvest_portfolio as portfolio
    from volume_contract import decimal as strict_decimal
    from ai_jobs import assert_current_owner_in
    from monitoring_access import assert_monitoring_access_in, monitoring_active

READ_ERRORS = {
    400: {"description": "Invalid date range"},
    401: {"description": "Session required or expired"},
    404: {"description": "Account unavailable to this user"},
    409: {"description": "T-Invest token not connected"},
    422: {"description": "Invalid request or broker access"},
    500: {"description": "Stored token unreadable"},
    502: {"description": "Invalid broker response"},
    503: {"description": "Broker temporarily unavailable"},
    504: {"description": "Broker timeout"},
}
router = APIRouter()
MOSCOW = ZoneInfo("Europe/Moscow")
BASE = "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1."
METHODS = {
    "accounts": "UsersService/GetAccounts",
    "portfolio": "OperationsService/GetPortfolio",
    "positions": "OperationsService/GetPositions",
    "withdraw": "OperationsService/GetWithdrawLimits",
    "operations": "OperationsService/GetOperationsByCursor",
    "orders": "OrdersService/GetOrders",
    "stops": "StopOrdersService/GetStopOrders",
    "instrument": "InstrumentsService/GetInstrumentBy",
    "coupons": "InstrumentsService/GetBondCoupons",
    "dividends": "InstrumentsService/GetDividends",
}
_cache: OrderedDict = OrderedDict()
_public_cache: OrderedDict = OrderedDict()
_cache_lock = RLock()
_request_locks = [RLock() for _ in range(32)]


def number(value: Any) -> Decimal | None:
    if not isinstance(value, dict):
        return None
    return strict_decimal({"units": value.get("units", 0), "nano": value.get("nano", 0)})

def money(value: Any) -> dict | None:
    amount = number(value)
    currency = str(value.get("currency", "")).upper() if isinstance(value, dict) else ""
    return portfolio._money_payload(amount, currency) if amount is not None and currency else None


def quote(value: Any) -> dict | None:
    amount = number(value)
    return portfolio._decimal_payload(amount) if amount is not None else None


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def identity(user: Any) -> tuple:
    encrypted = user["tinvest_token_encrypted"]
    if not encrypted:
        raise HTTPException(409, "tinvest_not_connected")
    return str(backend.DATABASE_PATH), int(user["id"]), hashlib.sha256(encrypted).hexdigest()


def cached(key: tuple, ttl: int, load):
    """Bounded, identity-scoped cache and single flight for concurrent refreshes."""
    lock = _request_locks[hash(key) % len(_request_locks)]
    with lock:
        with _cache_lock:
            existing = _cache.get(key)
            if existing and existing[0] > time.monotonic():
                _cache.move_to_end(key)
                return copy.deepcopy(existing[1])
        value = load()
        with _cache_lock:
            _cache[key] = time.monotonic() + ttl, copy.deepcopy(value)
            _cache.move_to_end(key)
            while len(_cache) > 256:
                _cache.popitem(last=False)
        return value


class BrokerReader:
    def __init__(self, user: Any):
        self.user = user
        self.scope = identity(user)
        self.client = None
        self.token = ""

    def __enter__(self):
        try:
            self.token = backend.FERNET.decrypt(self.user["tinvest_token_encrypted"]).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError):
            raise HTTPException(500, "tinvest_token_unreadable") from None
        self.client = backend.httpx.Client(timeout=backend.httpx.Timeout(12, connect=5),
                                          verify=backend.tinvest_ssl_context(), follow_redirects=False)
        return self

    def __exit__(self, *_):
        if self.client is not None:
            self.client.close()
        self.token = ""

    def read(self, method: str, body: dict) -> dict:
        previous_timeout = self.client.timeout
        if method in {"instrument", "coupons", "dividends"}:
            self.client.timeout = backend.httpx.Timeout(3, connect=2)
        try:
            return portfolio._post_tinvest(self.client, BASE + METHODS[method], self.token, body)
        finally:
            self.client.timeout = previous_timeout

    def accounts(self) -> list[dict]:
        result = self.read("accounts", {}).get("accounts")
        if not isinstance(result, list):
            raise HTTPException(502, "tinvest_invalid_response")
        return [item for item in result if isinstance(item, dict) and portfolio._is_readable_account(item)]

    def account(self, account_id: str) -> dict:
        # Never trust an account ID supplied by the Android client.
        account = next((a for a in self.accounts() if a.get("id") == account_id), None)
        if account is None:
            raise HTTPException(404, "account_not_available")
        return account

    def metadata(self, raw: dict, budget: list[int] | None = None) -> dict:
        identifier = raw.get("instrumentUid") or raw.get("figi")
        if not identifier:
            return {}
        kind = "INSTRUMENT_ID_TYPE_UID" if raw.get("instrumentUid") else "INSTRUMENT_ID_TYPE_FIGI"
        key = ("instrument", str(identifier))
        existing = public_lookup(key)
        if existing is not None:
            return existing
        if budget is not None:
            if budget[0] <= 0:
                return {}
            budget[0] -= 1
        try:
            value = self.read("instrument", {"idType": kind, "id": identifier}).get("instrument", {})
        except HTTPException:
            return {}
        # Instrument responses can also contain client-specific tests and
        # permissions. Only public identity fields enter this shared cache.
        value = {key: value[key] for key in ("uid", "figi", "ticker", "classCode", "isin", "name", "sector",
                 "assetUid", "exchange", "lot", "currency", "countryOfRisk", "countryOfRiskName", "instrumentType", "instrumentKind") if key in value}
        public_store(key, value, 86400)
        return value


def public_lookup(key: tuple) -> dict | None:
    # Never acquire another single-flight stripe while serving a dashboard stripe.
    with _cache_lock:
        row = _public_cache.get(key)
        return copy.deepcopy(row[1]) if row and row[0] > time.monotonic() else None


def public_store(key: tuple, value: dict, ttl: int) -> None:
    with _cache_lock:
        _public_cache[key] = time.monotonic() + ttl, copy.deepcopy(value)
        _public_cache.move_to_end(key)
        while len(_public_cache) > 2048:
            _public_cache.popitem(last=False)



def position_value(raw: dict) -> dict | None:
    kind = raw.get("instrumentType")
    price = money(raw.get("currentPrice"))
    quantity = number(raw.get("quantity"))
    if kind not in {"share", "bond", "etf", "currency", "dfa", "sp"} or price is None or quantity is None:
        return None
    value = number(raw["currentPrice"])
    if kind == "bond":
        accrued = money(raw.get("currentNkd"))
        if accrued is None or accrued["currency"] != price["currency"]:
            return None  # Do not silently omit accrued interest from a bond value.
        value += number(raw["currentNkd"])
    return portfolio._money_payload(value * quantity, price["currency"])


def normalize_position(raw: dict, metadata: dict) -> dict:
    identifier = str(raw.get("instrumentUid") or raw.get("positionUid") or raw.get("figi") or "")
    ticker = metadata.get("ticker") or raw.get("ticker") or raw.get("figi")
    price = money(raw.get("currentPrice"))
    profit = number(raw.get("expectedYield"))
    return {
        "id": identifier, "title": metadata.get("name") or ticker or "Инструмент",
        "ticker": ticker, "quantity": quote(raw.get("quantity")),
        "currentValue": position_value(raw), "expectedYieldPercent": None,
        "currentPrice": price, "averagePrice": money(raw.get("averagePositionPrice")),
        "expectedYieldAmount": portfolio._money_payload(profit, price["currency"]) if profit is not None and price else None,
        "dailyYieldAmount": money(raw.get("dailyYield")), "currentNkd": money(raw.get("currentNkd")),
        "instrumentType": raw.get("instrumentType", ""), "blocked": bool(raw.get("blocked")),
        "blockedQuantity": quote(raw.get("blockedLots")), "isin": metadata.get("isin"),
        "sector": metadata.get("sector"), "company": metadata.get("name"),
        "assetUid": metadata.get("assetUid"), "exchange": metadata.get("exchange"),
        "countryOfRisk": metadata.get("countryOfRisk"), "countryOfRiskName": metadata.get("countryOfRiskName"),
        "lot": metadata.get("lot"), "figi": raw.get("figi"), "classCode": metadata.get("classCode") or raw.get("classCode"),
    }


def cash_positions(payload: dict) -> list[dict]:
    blocked = {str(item.get("currency", "")).upper(): item for item in payload.get("blocked", [])}
    rows = []
    for item in payload.get("money", []):
        value = money(item)
        if value is None:
            continue
        currency = value["currency"]
        rows.append({"id": "cash:" + currency, "title": portfolio.CURRENCY_NAMES.get(currency, currency),
                     "ticker": currency, "instrumentType": "cash", "quantity": quote(item),
                     "currentValue": value, "expectedYieldPercent": None,
                     "blockedQuantity": quote(blocked.get(currency)), "blocked": False})
    return rows


def allocations(raw: dict) -> list[dict]:
    total = number(raw.get("totalAmountPortfolio"))
    currency = str(raw.get("totalAmountPortfolio", {}).get("currency", "")).upper()
    if total is None or total <= 0:
        return []
    rows = []
    for title, field in portfolio.ALLOCATION_FIELDS:
        value = money(raw.get(field))
        if value and value["currency"] == currency and number(raw[field]) > 0:
            rows.append({"title": title, "sharePercent": portfolio._decimal_payload(number(raw[field]) / total * 100)})
    return rows



def supplement_positions(reader: BrokerReader, rows: list[dict], balances: dict, budget: list[int]) -> list[dict]:
    """Do not drop exchange-blocked securities that GetPortfolio cannot value."""
    seen = {row["id"] for row in rows}
    extra = []
    for field, fallback_kind in (("securities", "security"), ("futures", "futures"), ("options", "option")):
        for item in balances.get(field, []):
            identifier = str(item.get("instrumentUid") or item.get("positionUid") or item.get("figi") or "")
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            blocked = Decimal(str(item.get("blocked", 0)))
            quantity = Decimal(str(item.get("balance", 0))) + blocked
            raw = {**item, "instrumentType": item.get("instrumentType", fallback_kind),
                   "quantity": portfolio._decimal_payload(quantity),
                   "blocked": bool(item.get("exchangeBlocked")), "blockedLots": portfolio._decimal_payload(blocked)}
            extra.append(normalize_position(raw, reader.metadata(raw, budget)))
    return extra


def read_account(reader: BrokerReader, account: dict, currency: str, meta_budget: list[int]) -> dict:
    account_id = str(account["id"])
    raw = reader.read("portfolio", {"accountId": account_id, "currency": currency})
    balances = reader.read("positions", {"accountId": account_id})
    total = money(raw.get("totalAmountPortfolio"))
    if total is None or total["currency"] != currency:
        raise HTTPException(502, "tinvest_invalid_response")
    rows = []
    for item in raw.get("positions", []):
        # GetPositions.money is authoritative for cash; do not show it twice.
        if item.get("instrumentType") == "currency" and "money" in balances:
            continue
        metadata = reader.metadata(item, meta_budget)
        rows.append(normalize_position(item, metadata))
    rows.extend(supplement_positions(reader, rows, balances, meta_budget))
    rows.extend(cash_positions(balances))
    return {"id": account_id, "name": portfolio._account_name(account), "totalValue": total,
            "expectedYieldPercent": quote(raw.get("expectedYield")), "positions": rows,
            "dailyYieldAmount": money(raw.get("dailyYield")), "dailyYieldPercent": quote(raw.get("dailyYieldRelative")),
            "allocations": allocations(raw), "openedAt": account.get("openedDate"),
            "accountType": account.get("type"), "limitsLoading": bool(balances.get("limitsLoadingInProgress")),
            "virtualPositions": [normalize_position(p, {}) for p in raw.get("virtualPositions", [])]}


def ensure_history(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS portfolio_value_history (
        user_id INTEGER NOT NULL, account_id TEXT NOT NULL, currency TEXT NOT NULL,
        resolution TEXT NOT NULL, bucket INTEGER NOT NULL, observed_at TEXT NOT NULL,
        value TEXT NOT NULL, PRIMARY KEY(user_id, account_id, currency, resolution, bucket))""")


def record_history(user_id: int, accounts: list[dict], observed: str) -> None:
    if not monitoring_active():
        backend.client_updates.assert_user_can_run(backend.connect, user_id)
    stamp = int(datetime.fromisoformat(observed).timestamp())
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        ensure_history(db)
        for account in accounts:
            value = str(number(account["totalValue"]["value"]))
            for resolution, seconds in (("intraday", 300), ("hour", 3600), ("day", 86400)):
                db.execute("""INSERT INTO portfolio_value_history VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id,account_id,currency,resolution,bucket)
                    DO UPDATE SET observed_at=excluded.observed_at,value=excluded.value
                    WHERE excluded.observed_at >= portfolio_value_history.observed_at""",
                    (user_id, account["id"], account["totalValue"]["currency"], resolution,
                     stamp // seconds * seconds, observed, value))
        db.execute("DELETE FROM portfolio_value_history WHERE user_id=? AND resolution='intraday' AND bucket<?", (user_id, stamp - 7 * 86400))
        db.execute("DELETE FROM portfolio_value_history WHERE user_id=? AND resolution='hour' AND bucket<?", (user_id, stamp - 90 * 86400))
        db.commit()


def load_dashboard(user: Any, currency: str) -> dict:
    with BrokerReader(user) as reader:
        metadata_budget = [4]
        accounts = [read_account(reader, a, currency, metadata_budget) for a in reader.accounts()]
    total = sum((number(a["totalValue"]["value"]) for a in accounts), Decimal(0))
    buckets = defaultdict(Decimal)
    for account in accounts:
        value = number(account["totalValue"]["value"])
        for row in account["allocations"]:
            buckets[row["title"]] += value * number(row["sharePercent"]) / 100
    as_of = iso_now()
    record_history(int(user["id"]), accounts, as_of)
    warnings = []
    if any(not p.get("company") and p.get("instrumentType") != "cash" for a in accounts for p in a["positions"]):
        warnings.append("Часть названий инструментов ещё не уточнена; все полученные позиции показаны.")
    return {"currency": currency, "totalValue": portfolio._money_payload(total, currency),
            "expectedYieldAmount": None,
            "expectedYieldPercent": accounts[0]["expectedYieldPercent"] if len(accounts) == 1 else None,
            "accounts": accounts, "asOf": as_of, "warnings": warnings,
            "allocations": [{"title": key, "sharePercent": portfolio._decimal_payload(value / total * 100)}
                            for key, value in buckets.items()] if total > 0 else []}


@router.get("/tinvest/dashboard", responses=READ_ERRORS)
def dashboard(currency: str = Query("RUB", pattern="^(RUB|USD|EUR)$"), user: Any = Depends(backend.current_user)) -> dict:
    return cached(("dashboard", *identity(user), currency), 10, lambda: load_dashboard(user, currency))


def period_bounds(start: date | None, end: date | None, account: dict) -> tuple[str, str]:
    today = datetime.now(MOSCOW).date()
    opened = str(account.get("openedDate") or "2000-01-01")[:10]
    first = start or date.fromisoformat(opened)
    last = end or today
    if first > last or last > today or first < date(1970, 1, 1):
        raise HTTPException(400, "invalid_date_range")
    begin = datetime.combine(first, day_time.min, MOSCOW).astimezone(timezone.utc)
    finish = min(datetime.combine(last + timedelta(days=1), day_time.min, MOSCOW).astimezone(timezone.utc), datetime.now(timezone.utc))
    return begin.isoformat(), finish.isoformat()


def operation_group(kind: str) -> str:
    suffix = kind.removeprefix("OPERATION_TYPE_")
    if "TAX" in suffix:
        return "tax"
    if "FEE" in suffix or suffix in {"OVER_COM", "OUT_STAMP_DUTY"}:
        return "fees"
    if "DIVIDEND" in suffix or suffix == "DIV_EXT":
        return "dividends"
    if suffix == "COUPON":
        return "coupons"
    if "VARMARGIN" in suffix:
        return "margin"
    if "REPAYMENT" in suffix or suffix == "DFA_REDEMPTION":
        return "redemptions"
    if suffix in {"INPUT", "INPUT_SWIFT", "INPUT_ACQUIRING", "INP_MULTI"}:
        return "deposits"
    if suffix in {"OUTPUT", "OUTPUT_SWIFT", "OUTPUT_ACQUIRING", "OUT_MULTI"}:
        return "withdrawals"
    if suffix.startswith(("BUY", "SELL", "DELIVERY_BUY", "DELIVERY_SELL")):
        return "trades"
    return "other"


def normalize_operation(raw: dict) -> dict:
    kind = str(raw.get("type") or raw.get("operationType") or "")
    return {"id": str(raw.get("id") or ""), "date": raw.get("date"), "type": kind,
            "category": operation_group(kind), "title": raw.get("name") or raw.get("description") or kind,
            "description": raw.get("description"), "state": raw.get("state"), "payment": money(raw.get("payment")),
            "price": money(raw.get("price")), "quantity": raw.get("quantity"),
            "commission": money(raw.get("commission")), "instrumentUid": raw.get("instrumentUid"),
            "ticker": raw.get("ticker"), "yield": money(raw.get("yield"))}


@router.get("/tinvest/accounts/{account_id}/operations", responses=READ_ERRORS)
def operations(account_id: str, start: date | None = None, end: date | None = None,
               cursor: str = Query("", max_length=2048), user: Any = Depends(backend.current_user)) -> dict:
    with BrokerReader(user) as reader:
        account = reader.account(account_id)
        begin, finish = period_bounds(start, end, account)
        raw = reader.read("operations", {"accountId": account_id, "from": begin, "to": finish,
                          "cursor": cursor, "limit": 100, "withoutCommissions": False, "withoutTrades": False})
    return {"items": [normalize_operation(item) for item in raw.get("items", [])],
            "hasNext": bool(raw.get("hasNext")), "nextCursor": raw.get("nextCursor", ""), "asOf": iso_now()}


@router.get("/tinvest/accounts/{account_id}/orders", responses=READ_ERRORS)
def orders(account_id: str, user: Any = Depends(backend.current_user)) -> dict:
    with BrokerReader(user) as reader:
        reader.account(account_id)
        sections = {}
        for method, field in (("orders", "orders"), ("stops", "stopOrders"), ("withdraw", "withdrawLimits")):
            try:
                data = reader.read(method, {"accountId": account_id})
                sections[field] = {"available": True, "data": data}
            except HTTPException as error:
                sections[field] = {"available": False, "reason": str(error.detail)}
    return {**sections, "asOf": iso_now()}


def summarize_operations(items: list[dict]) -> list[dict]:
    totals = defaultdict(Decimal)
    seen = set()
    for item in items:
        identifier = item.get("id")
        if not identifier or identifier in seen or item.get("state") != "OPERATION_STATE_EXECUTED":
            continue
        seen.add(identifier)
        payment = money(item.get("payment"))
        if payment is None:
            continue
        kind = str(item.get("type") or item.get("operationType") or "")
        group = operation_group(kind)
        amount = number(item["payment"])
        totals[group, payment["currency"]] += abs(amount) if group == "trades" else amount
    return [{"category": group, "amount": portfolio._money_payload(amount, currency)}
            for (group, currency), amount in sorted(totals.items())]


def load_analytics(user: Any, account_id: str, start: date | None, end: date | None, currency: str,
                   history_resolution: str | None = None) -> dict:
    if history_resolution not in {None, "intraday", "hour", "day"}:
        raise HTTPException(422, "invalid_history_resolution")
    with BrokerReader(user) as reader:
        account = reader.account(account_id)
        begin, finish = period_bounds(start, end, account)
        items, cursor, complete = [], "", False
        deadline = time.monotonic() + 20
        for _ in range(20):
            raw = reader.read("operations", {"accountId": account_id, "from": begin, "to": finish,
                              "cursor": cursor, "limit": 1000, "state": "OPERATION_STATE_EXECUTED", "withoutCommissions": False})
            items.extend(raw.get("items", []))
            if not raw.get("hasNext"):
                complete = True
                break
            next_cursor = str(raw.get("nextCursor") or "")
            if not next_cursor or next_cursor == cursor or time.monotonic() >= deadline:
                break
            cursor = next_cursor
    span = datetime.fromisoformat(finish) - datetime.fromisoformat(begin)
    resolution = "day"
    if span <= timedelta(days=2):
        resolution = "intraday"
    elif span <= timedelta(days=32):
        resolution = "hour"
    resolution = history_resolution or resolution
    with closing(backend.connect()) as db:
        ensure_history(db)
        rows = db.execute("""SELECT observed_at,value FROM portfolio_value_history
            WHERE user_id=? AND account_id=? AND currency=? AND resolution=?
            AND observed_at>=? AND observed_at<=? ORDER BY observed_at LIMIT 2001""",
            (int(user["id"]), account_id, currency, resolution, begin, finish)).fetchall()
    return {"summary": summarize_operations(items), "complete": complete, "operationCount": len(items),
            "history": [{"date": row["observed_at"], "value": row["value"]} for row in rows[:2000]], "historyTruncated": len(rows) > 2000,
            "currency": currency, "historyResolution": resolution, "historySource": "Analyst AI: сохранённые снимки T‑Invest",
            "totalIncome": None, "asOf": iso_now(),
            "note": "История стоимости начинается с фактического сбора данных. Денежные потоки не равны инвестиционной прибыли. Суммы операций показаны в исходных валютах."}


@router.get("/tinvest/accounts/{account_id}/analytics", responses=READ_ERRORS)
def analytics(account_id: str, start: date | None = None, end: date | None = None,
              currency: str = Query("RUB", pattern="^(RUB|USD|EUR)$"), user: Any = Depends(backend.current_user),
              history_resolution: str | None = None) -> dict:
    return cached(("analytics", *identity(user), account_id, start, end, currency, history_resolution), 60,
                  lambda: load_analytics(user, account_id, start, end, currency, history_resolution))


def payment_rows(raw: dict, position: dict, kind: str, now: datetime) -> list[dict]:
    result = []
    for event in raw.get("events" if kind == "bond" else "dividends", []):
        row = payment_row(event, position, kind, now)
        if row is not None:
            result.append(row)
    return result


def payment_estimate(per_unit: dict | None, quantity: Decimal | None, unknown: bool, payment_date: str | None) -> dict | None:
    if per_unit is None or quantity is None or quantity <= 0 or unknown or not payment_date:
        return None
    return portfolio._money_payload(number(per_unit["value"]) * quantity, per_unit["currency"])


def payment_row(event: dict, position: dict, kind: str, now: datetime) -> dict | None:
    if str(event.get("dividendType", "")).lower() == "cancelled":
        return None
    amount_field, date_field, record_field = "dividendNet", "paymentDate", "recordDate"
    if kind == "bond":
        amount_field, date_field, record_field = "payOneBond", "couponDate", "fixDate"
    per_unit = money(event.get(amount_field))
    payment_date = event.get(date_field)
    record_date = event.get(record_field)
    display_date = payment_date or record_date
    if not display_date or display_date[:10] < now.date().isoformat():
        return None
    eligibility_unknown = not record_date or record_date[:10] <= now.date().isoformat()
    estimate = payment_estimate(per_unit, number(position.get("quantity")), eligibility_unknown, payment_date)
    return {"instrumentUid": position.get("instrumentUid"), "title": position.get("ticker") or position.get("figi"),
            "kind": "coupon" if kind == "bond" else "dividend", "date": display_date,
            "recordDate": record_date, "perUnit": per_unit, "estimate": estimate,
            "dateUnknown": not bool(payment_date), "eligibilityUnknown": eligibility_unknown}


def load_payments(user: Any, account_id: str) -> dict:
    now = datetime.now(timezone.utc)
    items, missing = [], 0
    budget = 4
    with BrokerReader(user) as reader:
        reader.account(account_id)
        raw = reader.read("portfolio", {"accountId": account_id, "currency": "RUB"})
        holdings = [p for p in raw.get("positions", []) if p.get("instrumentType") in {"share", "bond"}]
        for position in holdings:
            kind = position["instrumentType"]
            identifier = position.get("instrumentUid") or position.get("figi")
            key = ("payments", kind, identifier, now.date().isoformat())
            response = public_lookup(key)
            if response is None and budget > 0:
                budget -= 1
                body = {"instrumentId": identifier, "from": (now - timedelta(days=45)).isoformat(),
                        "to": (now + timedelta(days=365)).isoformat()}
                try:
                    response = reader.read("coupons" if kind == "bond" else "dividends", body)
                    public_store(key, response, 3600)
                except HTTPException:
                    response = None
            if response is None:
                missing += 1
            else:
                items.extend(payment_rows(response, position, kind, now))
    return {"items": sorted(items, key=lambda item: item["date"]), "complete": missing == 0,
            "asOf": iso_now(), "note": "Календарь опубликованных событий по текущим позициям. Оценка по количеству бумаг не гарантирует выплату. Право зависит от реестра, расчетов и будущих сделок. Сумма налога не прогнозируется."}


@router.get("/tinvest/accounts/{account_id}/payments", responses=READ_ERRORS)
def payments(account_id: str, user: Any = Depends(backend.current_user)) -> dict:
    return cached(("payments", *identity(user), account_id), 60, lambda: load_payments(user, account_id))
