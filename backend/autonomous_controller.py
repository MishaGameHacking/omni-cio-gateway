"""Connection-bound, rules-first background work and concise status for Android.

This controller reads broker data and prepares research. It never places orders.
Status endpoints read persisted observations only: opening a screen cannot start
collection, run a model, spend money or turn stale evidence into a fresh result.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, StrictBool

try:
    from . import app as backend, volume_state as state, volume_jobs as jobs
    from . import volume_catalogue as catalogue, volume_market as market
    from . import portfolio_details as details, volume_purchases as purchases
    from .ai_budget import transaction, micro_rub, BudgetDenied
    from . import server_version
    from .schema_migrations import execute_schema
    from .ai_jobs import assert_current_owner_in
    from .ai_guarded_client import configured_route, GuardError
    from .ai_policy import AnalysisTier
    from .monitoring_access import assert_monitoring_access, assert_monitoring_access_in
    from .volume_contract import decimal, digest, error_code, financial_context, instrument_currency, now_iso, text_number, timestamp, ZERO
except ImportError:
    import app as backend
    import volume_state as state
    import volume_jobs as jobs
    import volume_catalogue as catalogue
    import volume_market as market
    import portfolio_details as details
    import volume_purchases as purchases
    from ai_budget import transaction, micro_rub, BudgetDenied
    import server_version
    from schema_migrations import execute_schema
    from ai_jobs import assert_current_owner_in
    from ai_guarded_client import configured_route, GuardError
    from ai_policy import AnalysisTier
    from monitoring_access import assert_monitoring_access, assert_monitoring_access_in
    from volume_contract import decimal, digest, error_code, financial_context, instrument_currency, now_iso, text_number, timestamp, ZERO

router = APIRouter(prefix="/automation", tags=["Autonomous read-only research"])
FULL_REFRESH_SECONDS = 900
DISCOVERY_INTERVAL_SECONDS = 900
MAX_REVIEWED_PER_CYCLE = 8
DISCOVERY_TIME_BUDGET_SECONDS = 120
LEASE_SECONDS = 900
AUTO_REQUEST_PREFIX = "auto.full."

_MESSAGES = {
    "automation_paused": "Автоматический анализ приостановлен в настройках.",
    "market_price_polling_paused": "Опрос цен ожидает торгового окна. Проверка событий продолжается.",
    "tinvest_not_connected": "Подключите T-Invest в настройках: сервер пока не получает данные счёта.",
    "analysis_scheduler_disabled": "Фоновый процесс на сервере ещё не включён.",
    "workspace_refresh_required": "Сервер ожидает первый снимок данных брокера.",
    "workspace_collection_delayed": "Полная проверка источников задерживается.",
    "workspace_collection_failed": "Последний сбор данных завершился ошибкой.",
    "strategy_required": "Сохраните стратегию и резерв в настройках, чтобы задать условия поиска.",
    "fresh_snapshot_required": "Для проверки кандидатов нужен свежий снимок счёта.",
    "portfolio_coverage_incomplete": "Брокер ещё не вернул полные данные счёта.",
    "observed_cash_not_above_reserve": "Подтверждённый остаток на счёте не превышает заданный резерв.",
    "catalogue_unavailable": "Каталог инструментов временно недоступен.",
    "catalogue_no_eligible_instruments": "В проверенном каталоге нет инструментов по заданным фильтрам.",
    "research_incomplete": "Кандидаты ещё требуют инвестиционного обоснования и проверки недостающих данных.",
    "discovery_stale": "Последние проверки кандидатов устарели; сервер выполнит новый цикл.",
    "strategy_changed": "Стратегия изменена; результаты прошлого поиска больше не применяются.",
    "discovery_failed": "Проверка кандидатов завершилась ошибкой источника.",
    "discovery_time_budget": "Часть каталога проверена; оставшиеся инструменты перейдут в следующий цикл.",
    "source_unavailable": "Источник временно недоступен.",
    "order_book_stale_or_undated": "Нет свежего времени стакана.",
    "order_book_not_consistent": "Брокер не подтвердил согласованность стакана.",
    "order_book_invalid": "Стакан не содержит проверяемого предложения.",
    "investment_thesis_and_valuation": "Нужно инвестиционное обоснование и оценка стоимости.",
    "loss_capacity_and_full_investment_profile": "Нужна полная оценка допустимых потерь и инвестиционного профиля.",
    "tax_and_settlement_effects": "Не проверены налоги и особенности расчётов.",
    "candidate_identity_unverified": "Нет проверенной связи инструмента с эмитентом и группой.",
    "issuer_rating_required": "Нет проверенного рейтинга эмитента.",
    "issue_rating_required": "Нет проверенного рейтинга выпуска.",
    "protected_reserve_would_be_spent": "Покупка затронула бы защищённый резерв.",
    "broker_purchase_unavailable": "Брокер не разрешает покупку этого инструмента.",
    "broker_qualification_required": "Не подтверждён необходимый статус инвестора.",
    "broker_tests_not_confirmed": "Не подтверждено прохождение необходимых тестов брокера.",
    "limit_trading_unavailable": "Лимитная торговля сейчас недоступна.",
    "insufficient_visible_liquidity_at_limit": "Недостаточно видимой ликвидности по проверенной цене.",
}


def reason(code: str) -> dict:
    return {"code": code, "message": _MESSAGES.get(code, "Нужна дополнительная проверка данных инструмента.")}


def initialize() -> None:
    # Keep all controller schema changes inside one write transaction. Startup
    # must preserve pauses, connection history, discovery cursors and leases.
    with transaction(backend.connect) as db:
        execute_schema(db, """
            CREATE TABLE IF NOT EXISTS automation_preferences (
                user_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
                version INTEGER NOT NULL, updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS automation_observations (
                user_id INTEGER NOT NULL, broker_key TEXT NOT NULL,
                first_observed_at INTEGER NOT NULL, first_snapshot_id TEXT NOT NULL,
                PRIMARY KEY(user_id,broker_key));
            CREATE TABLE IF NOT EXISTS automation_discovery (
                user_id INTEGER PRIMARY KEY, broker_key TEXT NOT NULL,
                snapshot_id TEXT, strategy_version INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL, result_json TEXT, updated_at INTEGER NOT NULL,
                attempted_at INTEGER NOT NULL, lease_owner TEXT, lease_until INTEGER,
                cursor INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS automation_events (
                user_id INTEGER NOT NULL, broker_key TEXT NOT NULL, id TEXT NOT NULL,
                kind TEXT NOT NULL, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                PRIMARY KEY(user_id,id));
            CREATE INDEX IF NOT EXISTS automation_events_user
                ON automation_events(user_id,created_at DESC);
        """)


def _preferences_in(db, user_id: int) -> dict:
    row = db.execute("SELECT enabled,version,updated_at FROM automation_preferences WHERE user_id=?", (user_id,)).fetchone()
    return {"enabled": bool(row["enabled"]) if row else True, "version": row["version"] if row else 0,
            "updated_at": _iso(row["updated_at"]) if row else None}


def preferences(user_id: int) -> dict:
    with closing(backend.connect()) as db:
        return _preferences_in(db, user_id)


def assert_enabled_in(db, user_id: int) -> None:
    if not _preferences_in(db, user_id)["enabled"]:
        raise HTTPException(409, "automation_paused")


def assert_enabled(user_id: int) -> None:
    with closing(backend.connect()) as db:
        assert_enabled_in(db, user_id)


class PreferenceUpdate(state.StrictModel):
    enabled: StrictBool
    expected_version: int = Field(ge=0, strict=True)


@router.put("/preferences")
def update_preferences(payload: PreferenceUpdate, user: Any = Depends(backend.current_user)) -> dict:
    user_id, now = int(user["id"]), int(time.time())
    with transaction(backend.connect) as db:
        current = _preferences_in(db, user_id)
        if payload.expected_version != current["version"]:
            raise HTTPException(409, "automation_preferences_changed")
        version = current["version"] + 1
        db.execute("""INSERT INTO automation_preferences VALUES (?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,
            version=excluded.version,updated_at=excluded.updated_at""",
            (user_id, int(payload.enabled), version, now))
        db.execute("UPDATE automation_discovery SET attempted_at=0,lease_owner=NULL,lease_until=NULL,state=? WHERE user_id=?",
                   ("waiting" if payload.enabled else "paused", user_id))
        if not payload.enabled:
            # Pause queued automatic collection and stop an active collector at
            # its next durable checkpoint. Explicit read-only refresh is separate.
            db.execute("""UPDATE workspace_jobs SET cancel_requested=1,
                state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END,
                error_code=CASE WHEN state='queued' THEN 'automation_paused' ELSE error_code END,
                updated_at=? WHERE user_id=? AND (request_id LIKE 'auto.full.%' OR request_id LIKE 'auto.events.%')
                AND state IN ('queued','running')""", (now, user_id))
            db.execute("""UPDATE ai_work_jobs SET cancel_requested_at=?,updated_at=?,
                status=CASE WHEN status='queued' THEN 'failed' ELSE status END,
                error_code=CASE WHEN status='queued' THEN 'analysis_cancelled' ELSE error_code END
                WHERE user_id=? AND status IN ('queued','running')""", (now, now, user_id))
        return _preferences_in(db, user_id)


def _iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def _age(value: str | None, now: float) -> float | None:
    try:
        age = now - timestamp(value).timestamp()
        return age if age >= 0 else None
    except (TypeError, ValueError):
        return None


def _user(user_id: int):
    with closing(backend.connect()) as db:
        return db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def _currency(user_id: int) -> str:
    active = state.active_strategy(user_id)
    return (active or {}).get("config", {}).get("reserve", {}).get("currency", "RUB")


class _PendingCollection(Exception):
    def __init__(self, job_id):
        self.job_id = job_id


def enqueue_collection(user: Any, *, now: float | None = None) -> dict:
    """Schedule one connection-bound full collection; no HTTP or paid work here."""
    now = time.time() if now is None else now
    user_id = int(user["id"])
    current = _user(user_id)
    if current is None or not current["tinvest_token_encrypted"]:
        return {"state": "not_connected"}
    if not preferences(user_id)["enabled"]:
        return {"state": "paused"}
    key, currency = state.broker_key(current), _currency(user_id)
    snapshot = state.saved_snapshot(current, currency)
    age = _age((snapshot or {}).get("collection", {}).get("finished_at"), now)
    if age is not None and age < FULL_REFRESH_SECONDS:
        return {"state": "current"}
    prefix = AUTO_REQUEST_PREFIX + key + "." + currency + "."
    request_id = prefix + str(int(now) // 300)

    def before_insert(db, _):
        assert_enabled_in(db, user_id)
        owner = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if owner is None or state.broker_key(owner) != key:
            raise HTTPException(409, "monitoring_connection_changed")
        pending = db.execute("""SELECT id FROM workspace_jobs WHERE user_id=?
            AND request_id LIKE ? AND state IN ('queued','running') AND cancel_requested=0
            ORDER BY created_at LIMIT 1""", (user_id, prefix + "%")).fetchone()
        if pending:
            raise _PendingCollection(pending["id"])

    try:
        return jobs.enqueue(user_id, request_id, "refresh", {"currency": currency},
                            before_insert=before_insert, checkpoint={"broker_key": key})
    except _PendingCollection as pending:
        return {"state": "coalesced", "job_id": pending.job_id}


def _event_in(db, user_id: int, key: str, kind: str, identity: str, title: str, summary: str, now: int) -> None:
    identifier = digest({"connection": key, "kind": kind, "identity": identity})
    value = {"id": identifier, "kind": kind, "at": _iso(now), "title": title, "summary": summary}
    db.execute("INSERT OR IGNORE INTO automation_events VALUES (?,?,?,?,?,?)",
               (user_id, key, identifier, kind, state.encode(value), now))
    db.execute("""DELETE FROM automation_events WHERE user_id=? AND id NOT IN
        (SELECT id FROM automation_events WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 100)""", (user_id, user_id))


def record_initial_observation(user: Any, snapshot: dict, now: int) -> None:
    user_id, key = int(user["id"]), state.broker_key(user)
    with transaction(backend.connect) as db:
        assert_monitoring_access_in(db)
        assert_current_owner_in(db)
        jobs.assert_current_in(db)
        assert_enabled_in(db, user_id)
        owner = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if owner is None or state.broker_key(owner) != key:
            raise HTTPException(409, "monitoring_connection_changed")
        try:
            from .decision_views import prune_obsolete_events
        except ImportError:
            from decision_views import prune_obsolete_events
        prune_obsolete_events(db, user_id, now)
        cursor = db.execute("INSERT OR IGNORE INTO automation_observations VALUES (?,?,?,?)",
                            (user_id, key, now, snapshot["snapshot_id"]))
        if cursor.rowcount:
            _event_in(db, user_id, key, "initial_observation", key, "Данные счёта получены",
                      "Сервер получил первый снимок брокера. Это исходная точка анализа; новая покупка или продажа не предполагается.", now)


def _empty_discovery(state_name: str = "waiting", codes: list[str] | None = None) -> dict:
    return {"state": state_name, "as_of": None, "snapshot_id": None, "strategy_version": None,
            "coverage": {"scanned": 0, "eligible": 0, "reviewed": 0, "scope": "shares_and_bonds_catalogues",
                         "market_wide_complete": False},
            "candidates": [], "reasons": [reason(code) for code in (codes or [])],
            "automatic_orders": False, "recommendation_complete": False, "sources": []}


def _claim_discovery(user: Any, now: int) -> tuple[str, int] | None:
    user_id, key, owner = int(user["id"]), state.broker_key(user), uuid.uuid4().hex
    active = state.active_strategy(user_id)
    version = (active or {}).get("version", 0)
    with transaction(backend.connect) as db:
        assert_monitoring_access_in(db)
        assert_current_owner_in(db)
        jobs.assert_current_in(db)
        assert_enabled_in(db, user_id)
        current = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if current is None or state.broker_key(current) != key:
            raise HTTPException(409, "monitoring_connection_changed")
        row = db.execute("SELECT * FROM automation_discovery WHERE user_id=?", (user_id,)).fetchone()
        same = row is not None and row["broker_key"] == key
        if same and row["lease_until"] and row["lease_until"] > now:
            return None
        if same and row["strategy_version"] == version and 0 <= now - row["attempted_at"] < DISCOVERY_INTERVAL_SECONDS:
            return None
        cursor = row["cursor"] if same else 0
        # The new strategy cannot inherit candidates calculated under old limits.
        previous = row["result_json"] if same and row["strategy_version"] == version else None
        db.execute("""INSERT INTO automation_discovery
            (user_id,broker_key,snapshot_id,strategy_version,state,result_json,updated_at,attempted_at,lease_owner,lease_until,cursor)
            VALUES (?,?,NULL,?,'running',?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET broker_key=excluded.broker_key,
            strategy_version=excluded.strategy_version,state='running',
            result_json=excluded.result_json,updated_at=excluded.updated_at,
            attempted_at=excluded.attempted_at,lease_owner=excluded.lease_owner,
            lease_until=excluded.lease_until,cursor=excluded.cursor""",
            (user_id, key, version, previous, now, now, owner, now + LEASE_SECONDS, cursor))
    return owner, cursor


@financial_context
def _catalogue_candidate(row: dict, config: dict) -> bool:
    exchange = {"REAL_EXCHANGE_MOEX": "MOEX", "REAL_EXCHANGE_RTS": "SPB"}.get(row.get("realExchange"))
    lot = decimal(row.get("lot"))
    mandate = config.get("mandate")
    permitted = {"bonds": {"bond"}, "shares": {"share"}, "mixed": {"bond", "share"}}
    if mandate and row.get("instrument_type") not in permitted[mandate["asset_mode"]]:
        return False
    return bool(exchange and ({exchange, "RU"} & set(config["allowed_markets"]))
                and str(row.get("currency", "")).upper() == config["reserve"]["currency"]
                and row.get("buyAvailableFlag") is True and row.get("apiTradeAvailableFlag") is True
                and row.get("blockedTcaFlag") is not True and lot is not None and lot > 0 and lot % 1 == 0
                and row.get("subordinatedFlag") is not True and row.get("perpetualFlag") is not True)


@financial_context
def _account_for_research(snapshot: dict, config: dict) -> str | None:
    currency = config["reserve"]["currency"]
    reserve = decimal(config["reserve"])
    if reserve is None:
        return None
    cash = {}
    for row in snapshot.get("positions", []):
        amount = decimal(row.get("value"))
        if (row.get("instrument_type") == "cash" and instrument_currency(row) == currency
                and not row.get("blocked") and (decimal(row.get("blocked_quantity")) or ZERO) == 0
                and amount is not None and amount > 0):
            account = row["account_id"]
            cash[account] = cash.get(account, ZERO) + amount
    selected = (config.get("mandate") or {}).get("account_id")
    eligible = [(amount, account) for account, amount in cash.items()
                if amount > reserve and (selected is None or account == selected)]
    return max(eligible)[1] if eligible else None


def _check_candidate(user: Any, item: dict, account: str, version: int) -> dict:
    uid = item["uid"]
    base = {"instrument_uid": uid, "ticker": item.get("ticker") or "", "name": item.get("name") or uid,
            "instrument_type": item["instrument_type"], "currency": str(item.get("currency") or "").upper(),
            "lot": int(decimal(item["lot"])), "lots_checked": 1, "constraints_passed": False,
            "as_of": None, "expires_at": None, "total_cost": None, "check_id": None,
            "snapshot_id": None, "strategy_version": version, "evidence_revision": None,
            "checks": [], "missing_evidence": [], "recommendation_complete": False}
    assert_enabled(int(user["id"]))
    assert_monitoring_access(backend.connect)
    try:
        with details.BrokerReader(user) as reader:
            book = market.broker_read(reader, "order_book", {"instrumentId": uid, "depth": 1})
        if book.get("instrumentUid") != uid:
            raise HTTPException(502, "purchase_market_identity_mismatch")
        # Unary GetOrderBookResponse has no isConsistent field; it belongs to
        # streamed OrderBook. Do not invent a positive flag or ignore a bad one.
        if "isConsistent" in book and book["isConsistent"] is not True:
            raise HTTPException(409, "order_book_not_consistent")
        if not purchases.policy.fresh(book.get("orderbookTs"), datetime.now(timezone.utc), 60):
            raise HTTPException(409, "order_book_stale_or_undated")
        asks = book.get("asks")
        if not isinstance(asks, list) or not asks or not isinstance(asks[0], dict):
            raise HTTPException(409, "order_book_invalid")
        price, quantity = decimal(asks[0].get("price")), decimal(asks[0].get("quantity"))
        if price is None or price <= 0 or quantity is None or quantity < 1 or quantity % 1:
            raise HTTPException(409, "order_book_invalid")
        assert_enabled(int(user["id"]))
        result = purchases._check_purchase(purchases.PurchaseCheck(
            account_id=account, instrument_uid=uid, lots=1, limit_price=text_number(price), strategy_version=version), user,
            archive=False)
        missing = sorted(set(result["reasons"] + result["remaining_checks"]))
        base.update(constraints_passed=bool(result["constraints_passed"]), as_of=result["as_of"],
                    expires_at=result["expires_at"], total_cost=result.get("total_cost"), check_id=result.get("check_id"),
                    missing_evidence=missing, snapshot_id=result.get("snapshot_id"),
                    strategy_version=result.get("strategy_version"), evidence_revision=result.get("evidence_revision"))
        base["checks"] = [{"code": "broker_constraints", "state": "passed" if result["constraints_passed"] else "blocked",
                           "message": "Ограничения проверены по данным брокера." if result["constraints_passed"] else "Покупка не прошла все проверки ограничений."}]
        base["checks"] += [{"code": code, "state": "unknown", "message": reason(code)["message"]} for code in missing]
    except HTTPException as error:
        code = error_code(error)
        if code in {"automation_paused", "monitoring_connection_changed"}:
            raise
        base["missing_evidence"] = [code]
        base["checks"] = [{"code": code, "state": "unknown", "message": reason(code)["message"]}]
    return base


def _collect_discovery(user: Any, cursor: int, now: int) -> tuple[dict, int]:
    user_id = int(user["id"])
    active = state.active_strategy(user_id)
    if not active:
        return _empty_discovery("blocked", ["strategy_required"]), cursor
    config, version = active["config"], active["version"]
    snapshot = state.saved_snapshot(user, config["reserve"]["currency"])
    if not snapshot or not purchases.policy.fresh(snapshot.get("as_of"), datetime.now(timezone.utc), 300):
        return _empty_discovery("blocked", ["fresh_snapshot_required"]), cursor
    if snapshot.get("position_coverage", {}).get("complete") is not True:
        return _empty_discovery("blocked", ["portfolio_coverage_incomplete"]), cursor
    account = _account_for_research(snapshot, config)
    if account is None:
        return _empty_discovery("blocked", ["observed_cash_not_above_reserve"]), cursor
    found, scanned, sources, errors = {}, 0, [], []
    deadline = time.monotonic() + DISCOVERY_TIME_BUDGET_SECONDS
    try:
        from .strategy_profiles import research_tuning
    except ImportError:
        from strategy_profiles import research_tuning
    tuning = research_tuning(config, snapshot)
    for kind in tuning["asset_classes"]:
        assert_enabled(user_id)
        assert_monitoring_access(backend.connect)
        try:
            observed = catalogue.load_catalogue(user, kind)
            scanned += len(observed["items"])
            sources.append(observed["source"])
            for item in observed["items"]:
                if _catalogue_candidate(item, config):
                    found[item["uid"]] = item
        except HTTPException as error:
            if error_code(error) in {"monitoring_connection_changed", "automation_paused"}:
                raise
            errors.append(error_code(error))
    ordered = [found[key] for key in sorted(found)]
    result = _empty_discovery("partial", ["research_incomplete"])
    result.update(as_of=now_iso(), snapshot_id=snapshot["snapshot_id"], strategy_version=version, sources=sources)
    result["coverage"].update(scanned=scanned, eligible=len(ordered), catalogue_classes_complete=not errors)
    if not ordered:
        result["state"] = "blocked"
        result["reasons"] = [reason("catalogue_unavailable" if errors else "catalogue_no_eligible_instruments")]
        return result, cursor
    batch = [ordered[(cursor + i) % len(ordered)] for i in range(min(MAX_REVIEWED_PER_CYCLE, tuning['candidate_batch'], len(ordered)))]
    for item in batch:
        if time.monotonic() >= deadline:
            errors.append("discovery_time_budget")
            break
        result["candidates"].append(_check_candidate(user, item, account, version))
    result["coverage"]["reviewed"] = len(result["candidates"])
    result["coverage"]["constraint_checks_passed"] = sum(item["constraints_passed"] for item in result["candidates"])
    result["reasons"] += [reason(code) for code in sorted(set(errors))]
    result["tuning"] = tuning
    current = state.active_strategy(user_id)
    if not current or current["version"] != version:
        raise HTTPException(409, "strategy_changed")
    return result, (cursor + len(result["candidates"])) % len(ordered)


def observe_and_discover(user: Any, snapshot: dict, current_time: datetime) -> None:
    now, user_id, key = int(time.time()), int(user["id"]), state.broker_key(user)
    record_initial_observation(user, snapshot, int(current_time.timestamp()))
    claim = _claim_discovery(user, now)
    if claim is None:
        return
    owner, cursor = claim
    try:
        result, next_cursor = _collect_discovery(user, cursor, now)
    except HTTPException as error:
        if error_code(error) in {"monitoring_connection_changed", "automation_paused"}:
            raise
        result, next_cursor = _empty_discovery("failed", [error_code(error)]), cursor
    except (ValueError, TypeError, KeyError, RuntimeError):
        # Persist a bounded diagnostic, never a provider response or credential.
        result, next_cursor = _empty_discovery("failed", ["discovery_failed"]), cursor
    result["as_of"] = result["as_of"] or _iso(now)
    with transaction(backend.connect) as db:
        assert_monitoring_access_in(db)
        assert_current_owner_in(db)
        jobs.assert_current_in(db)
        assert_enabled_in(db, user_id)
        current = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if current is None or state.broker_key(current) != key:
            raise HTTPException(409, "monitoring_connection_changed")
        changed = db.execute("""UPDATE automation_discovery SET snapshot_id=?,state=?,result_json=?,updated_at=?,
            lease_owner=NULL,lease_until=NULL,cursor=? WHERE user_id=? AND broker_key=? AND lease_owner=? AND lease_until>?""",
            (result["snapshot_id"], result["state"], state.encode(result), int(time.time()), next_cursor,
             user_id, key, owner, int(time.time())))
        if changed.rowcount != 1:
            raise HTTPException(409, "automation_discovery_lease_lost")
        reviewed = result["coverage"]["reviewed"]
        if reviewed:
            _event_in(db, user_id, key, "candidate_research", owner, "Проверка инструментов завершена",
                      f"Проверено инструментов: {reviewed}. Недостающие основания сохранены; торговые поручения не отправлялись.", now)


def _discovery(user: Any, active: dict | None, now: int) -> dict:
    with closing(backend.connect()) as db:
        row = db.execute("SELECT * FROM automation_discovery WHERE user_id=?", (int(user["id"]),)).fetchone()
    if row is None or row["broker_key"] != state.broker_key(user):
        return _empty_discovery()
    if row["strategy_version"] != (active or {}).get("version", 0):
        return _empty_discovery("blocked", ["strategy_changed"])
    value = json.loads(row["result_json"]) if row["result_json"] else _empty_discovery("running")
    if row["state"] == "running" and (row["lease_until"] or 0) > now:
        value["state"] = "running"
    elif now - row["updated_at"] >= DISCOVERY_INTERVAL_SECONDS:
        value["state"] = "stale"
        value["reasons"] = value["reasons"] + [reason("discovery_stale")]
    # A timestamp alone does not keep checks valid after inputs change.
    # read_revision deliberately avoids the mutating revision() initializer.
    current_snapshot, current_revision = None, None
    if value["candidates"] and active:
        current_snapshot = state.saved_snapshot(user, active["config"]["reserve"]["currency"])
        with closing(backend.connect()) as db:
            try:
                current_revision = asdict(purchases.research_store.read_revision(db))
            except purchases.research_store.RevisionUnavailable:
                pass
    current_snapshot_id = (current_snapshot or {}).get("snapshot_id")
    for item in value["candidates"]:
        try:
            item["evidence_current"] = bool(
                active and current_snapshot_id and current_revision is not None
                and value.get("strategy_version") == active["version"]
                and item.get("strategy_version") == active["version"]
                and value.get("snapshot_id") == current_snapshot_id
                and item.get("snapshot_id") == current_snapshot_id
                and item.get("evidence_revision") == current_revision
                and timestamp(item["expires_at"]).timestamp() > now
            )
        except (KeyError, TypeError, ValueError):
            item["evidence_current"] = False
    return value


def _ai_configuration() -> dict:
    """Pure configuration inspection; no ledger initialization or model request."""
    try:
        configured_route(AnalysisTier.FAST)
        if micro_rub(os.getenv("AI_USER_DAILY_RUB", "0")) <= 0 or micro_rub(os.getenv("AI_PROJECT_DAILY_RUB", "0")) <= 0:
            raise BudgetDenied("ai_ruble_budget_not_enabled")
        return {"available": True, "reason": None, "live_inference_verified": False}
    except (GuardError, BudgetDenied) as error:
        code = str(error)
        return {"available": False, "reason": code if code.isascii() and code.replace("_", "").isalnum() else "ai_not_configured",
                "live_inference_verified": False}


def _collection_status(enabled, connected, scheduler_enabled, job, snapshot, full, now):
    """Classify persisted collection state without changing any work."""
    if not enabled:
        return "paused", ["automation_paused"]
    if not connected:
        return "not_connected", ["tinvest_not_connected"]
    if not scheduler_enabled:
        return "disabled", ["analysis_scheduler_disabled"]
    if job and job["state"] in {"queued", "running"} and not job["cancel_requested"]:
        if job["state"] == "running" and (job["expires_at"] or 0) <= now:
            return "attention", ["workspace_collection_delayed"]
        return "collecting", []
    if snapshot is None:
        return "waiting", ["workspace_refresh_required"]
    if job and job["state"] == "failed":
        return "attention", ["workspace_collection_failed"]
    if _age(full, now) is None or _age(full, now) >= FULL_REFRESH_SECONDS * 2:
        return "attention", ["workspace_collection_delayed"]
    return "current", []


@router.get("/status")
def status(user: Any = Depends(backend.current_user), response: Response = None) -> dict:
    """Persisted status only. Do not initialize queues, expire leases or fetch data."""
    if response is not None:
        response.headers["Cache-Control"] = "no-store, private"
    try:
        from .autonomous_ai import SCHEDULER_ENABLED
        from . import osint_read
    except ImportError:
        from autonomous_ai import SCHEDULER_ENABLED
        import osint_read
    now, user_id, key = time.time(), int(user["id"]), state.broker_key(user)
    pref = preferences(user_id)
    active = state.active_strategy(user_id)
    currency = (active or {}).get("config", {}).get("reserve", {}).get("currency", "RUB")
    snapshot = state.saved_snapshot(user, currency)
    prefix = AUTO_REQUEST_PREFIX + key + "." + currency + "."
    with closing(backend.connect()) as db:
        initial = db.execute("SELECT * FROM automation_observations WHERE user_id=? AND broker_key=?", (user_id, key)).fetchone()
        job = db.execute("""SELECT state,stage,updated_at,error_code,cancel_requested,expires_at
            FROM workspace_jobs WHERE user_id=? AND request_id LIKE ? ORDER BY created_at DESC,id DESC LIMIT 1""",
            (user_id, prefix + "%")).fetchone()
    observed = (snapshot or {}).get("as_of")
    full = (snapshot or {}).get("collection", {}).get("finished_at")
    current_job = None if job is None else {"state": job["state"], "stage": job["stage"], "updated_at": _iso(job["updated_at"]),
                                           "error_code": job["error_code"], "cancel_requested": bool(job["cancel_requested"])}
    connected = bool(user["tinvest_token_encrypted"])
    state_name, codes = _collection_status(pref["enabled"], connected, SCHEDULER_ENABLED,
                                           job, snapshot, full, now)
    if connected and active is None:
        codes.append("strategy_required")
        if state_name == "current":
            state_name = "attention"
    discovery = _discovery(user, active, now)
    try:
        from .background_dispatch import schedule
    except ImportError:
        from background_dispatch import schedule
    dispatch = schedule(user, now=datetime.fromtimestamp(now, timezone.utc), snapshot=snapshot)
    events = dispatch["events"]
    event_age = _age(events.get("last_successful_at"), now)
    if (state_name == "attention" and codes == ["workspace_collection_delayed"]
            and not dispatch["regular_price_polling_allowed"] and events.get("complete") is True
            and event_age is not None and event_age < 1200):
        state_name, codes = "waiting", ["market_price_polling_paused"]
    return {"schema_version": 1, "server_version": server_version.current(),
            "enabled": pref["enabled"], "preference_version": pref["version"],
            "broker_connected": connected, "scheduler_enabled": SCHEDULER_ENABLED, "state": state_name,
            "blockers": [reason(code) for code in codes], "last_observation_at": observed, "last_full_collection_at": full,
            "current_job": current_job, "dispatch": dispatch, "osint": osint_read.status(backend.connect),
            "initial_observation": None if initial is None else {"at": _iso(initial["first_observed_at"]),
                "snapshot_id": initial["first_snapshot_id"], "summary": "Первый снимок счёта получен и сохранён."},
            "discovery": discovery, "execution": {"mode": "read_only", "real_orders_enabled": False},
            "ai": _ai_configuration()}


@router.get("/decisions")
def decisions(user: Any = Depends(backend.current_user)) -> dict:
    try:
        from .decision_views import project
    except ImportError:
        from decision_views import project
    user_id, key = int(user["id"]), state.broker_key(user)
    with closing(backend.connect()) as db:
        rows = db.execute("""SELECT payload_json FROM automation_events WHERE user_id=? AND broker_key=?
            ORDER BY created_at DESC,id DESC LIMIT 30""", (user_id, key)).fetchall()
    summary = status(user)
    views = project(summary["discovery"], [json.loads(row[0]) for row in rows], int(time.time()))
    return {"schema_version": 1, "views": views, "events": views["history"],
            "state": summary["state"], "blockers": summary["blockers"],
            "discovery": summary["discovery"], "execution": summary["execution"]}