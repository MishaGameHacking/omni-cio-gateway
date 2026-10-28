"""Materialized financial workspace; all collection is an explicit durable job.

Screen reads do not poll the broker. Financial amounts stay in their original
currency; balance observations are never transformed into OHLC quotations.
"""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException

try:
    from . import app as backend, portfolio_details as details, research_store, volume_market as market
    from . import volume_state as state, volume_notifications as notifications
    from .ai_budget import MoneyLedger, transaction
    from .ai_guarded_client import GuardedAIClient, GuardError
    from .ai_policy import AnalysisTier
    from .volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, source, section, safe_section, date_range, text_number, ZERO, financial_context
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    import volume_market as market
    import volume_state as state
    import volume_notifications as notifications
    from ai_budget import MoneyLedger, transaction
    from ai_guarded_client import GuardedAIClient, GuardError
    from ai_policy import AnalysisTier
    from volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, source, section, safe_section, date_range, text_number, ZERO, financial_context

router = APIRouter(prefix="/workspace", tags=["Materialized workspace"])


def _position_identity(uid: str) -> tuple[dict | None, list]:
    try:
        identity = research_store.latest_verified(backend.connect, "issuer_identity", uid, datetime.now(timezone.utc))
    except (ValueError, TypeError, KeyError):
        identity = None
    if not identity:
        return None, []
    try:
        from .volume_contract import reviewed_source
    except ImportError:
        from volume_contract import reviewed_source
    ref = reviewed_source(identity["source"], provider="Reviewed issuer register", method="issuer_identity", subject=uid)
    return identity, [ref]


def _position_metadata(raw: dict, position: dict) -> dict:
    keys = {"sector": "sector", "country_of_risk": "countryOfRisk", "country_of_risk_name": "countryOfRiskName",
            "asset_uid": "assetUid", "lot": "lot", "exchange": "exchange", "isin": "isin",
            "instrument_currency": "currency"}
    result = {**{name: raw.get(key) or position.get(key) for name, key in keys.items()}, "source": raw.get("_source")}
    if raw.get("_exchange_source"):
        result["exchange_source"] = raw["_exchange_source"]
    currency = result["instrument_currency"]
    # Normalize the broker's spelling at ingestion, before the strict internal
    # contract is used by risk groups, scenarios and purchase limits.
    if isinstance(currency, str) and currency.isascii():
        result["instrument_currency"] = currency.upper()
    return result


def _workspace_position(account: dict, position: dict, raw: dict, ref: dict) -> tuple[dict, list]:
    uid = position["id"]
    identity, sources = _position_identity(uid)
    if raw.get("_source"):
        sources.append(raw["_source"])
    row = {"instrument_uid": uid, "account_id": account["id"], "account_name": account.get("name"),
           "title": raw.get("name") or position.get("title") or uid, "ticker": raw.get("ticker") or position.get("ticker"),
           "instrument_type": position.get("instrumentType"), "quantity": text_number(decimal(position.get("quantity"))),
           "value": money(position.get("currentValue")), "blocked": bool(position.get("blocked")),
           "blocked_quantity": text_number(decimal(position.get("blockedQuantity"))), "source_ids": [ref["id"]],
           "verified_identity": identity, "metadata": _position_metadata(raw, position)}
    return row, sources


def _capital(dashboard: dict, rows: list) -> dict:
    cash = defaultdict(Decimal)
    for row in rows:
        if row["instrument_type"] == "cash" and row["value"]:
            cash[row["value"]["currency"]] += decimal(row["value"])
    return {"total": money(dashboard.get("totalValue")), "cash": [money(v, c) for c, v in sorted(cash.items())],
            "blocked_positions_count": sum(p["blocked"] or (decimal(p.get("blocked_quantity")) or ZERO) != 0 for p in rows),
            "unvalued_positions_count": sum(p["value"] is None for p in rows)}


def _position_coverage(accounts: list) -> dict:
    loading = [account["id"] for account in accounts if account.get("limitsLoading")]
    virtual = sum(account.get("virtualPositionCount", len(account.get("virtualPositions", []))) for account in accounts)
    reasons = []
    if loading:
        reasons.append("broker_limits_loading")
    if virtual:
        reasons.append("virtual_positions_not_valued")
    return {"complete": not reasons, "incomplete_reasons": reasons, "loading_account_ids": loading, "virtual_position_count": virtual}


@financial_context
def normalize_snapshot(user: Any, dashboard: dict, metadata: dict | None = None) -> dict:
    currency, observed = dashboard["currency"], dashboard["asOf"]
    sources, rows = [], []
    accounts = dashboard.get("accounts", [])
    for account in accounts:
        ref = source(dashboard.get("source_method", "GetPortfolio/GetPositions"), account["id"], observed, currency=currency, unit="money")
        sources.append(ref)
        for position in account.get("positions", []):
            row, refs = _workspace_position(account, position, (metadata or {}).get(position["id"]) or {}, ref)
            rows.append(row)
            sources.extend(refs)
    return {"currency": currency, "as_of": observed, "positions": rows, "sources": list({ref["id"]: ref for ref in sources}.values()),
            "accounts": [{"id": a["id"], "name": a.get("name"), "value": money(a.get("totalValue"))} for a in accounts],
            "capital": _capital(dashboard, rows), "position_coverage": _position_coverage(accounts)}


def _balance_interval(user_id: int, accounts: list[str], currency: str, begin: datetime, finish: datetime) -> tuple[dict | None, dict | None]:
    if not accounts:
        return None, None
    with closing(backend.connect()) as db:
        details.ensure_history(db)
        rows = db.execute("""SELECT account_id,observed_at,value FROM portfolio_value_history
            WHERE user_id=? AND currency=? AND observed_at>=? AND observed_at<=?
            GROUP BY account_id,observed_at ORDER BY observed_at""",
            (user_id, currency, begin.isoformat(), finish.isoformat())).fetchall()
    points = defaultdict(dict)
    for row in rows:
        if row["account_id"] in accounts:
            value = decimal(row["value"])
            if value is not None:
                points[row["observed_at"]][row["account_id"]] = value
    complete = [{"at": at, "value": sum(values.values(), ZERO)} for at, values in sorted(points.items()) if set(values) == set(accounts)]
    return (complete[0], complete[-1]) if len(complete) >= 2 else (None, None)


def _unique_flow_operations(operations: list[dict]) -> tuple[list, bool]:
    by_key, conflicts = {}, set()
    for row in operations:
        key = (row["account_id"], row["id"])
        if key in by_key and by_key[key] != row:
            conflicts.add(key)
        by_key[key] = row
    return [row for key, row in by_key.items() if key not in conflicts], not conflicts


def _attributed_flows(operations: list[dict], begin: datetime, finish: datetime, currency: str) -> tuple:
    try:
        from .volume_contract import timestamp
    except ImportError:
        from volume_contract import timestamp
    unique, complete = _unique_flow_operations(operations)
    sums, unknown_cash_flow = defaultdict(Decimal), False
    for row in unique:
        if row.get("state") != "OPERATION_STATE_EXECUTED":
            continue
        try:
            when = timestamp(row.get("date"))
        except ValueError:
            complete = False
            continue
        if not begin < when <= finish:
            continue
        amount = money(row.get("payment"))
        category = row["category"]
        if amount:
            sums[category, amount["currency"]] += decimal(amount)
        if category in {"deposits", "withdrawals", "other"} and (amount is None or amount["currency"] != currency or category == "other"):
            unknown_cash_flow = True
    return sums, complete and not unknown_cash_flow


@financial_context
def attribution(user: Any, snapshot: dict, operations: list[dict], complete: bool, begin: datetime, finish: datetime) -> dict:
    currency = snapshot["currency"]
    accounts = [a["id"] for a in snapshot["accounts"]]
    opening, closing = _balance_interval(int(user["id"]), accounts, currency, begin, finish)
    actual_begin = datetime.fromisoformat(opening["at"]) if opening else begin
    actual_end = datetime.fromisoformat(closing["at"]) if closing else finish
    sums, flows_known = _attributed_flows(operations, actual_begin, actual_end, currency)
    change = closing["value"] - opening["value"] if opening and closing else None
    exact = complete and flows_known and change is not None
    external = sums["deposits", currency] + sums["withdrawals", currency] if exact else None
    return {"start": actual_begin.isoformat(), "end": actual_end.isoformat(),
            "requested_start": begin.isoformat(), "requested_end": finish.isoformat(),
            "opening_value": money(opening["value"], currency) if opening else None,
            "closing_value": money(closing["value"], currency) if closing else None, "change": money(change, currency),
            "external_net_flow": money(external, currency), "residual_after_external_flows": money(change - external, currency) if exact else None,
            "flows": [{"category": category, "amount": money(value, code)} for (category, code), value in sorted(sums.items())],
            "complete": exact, "fx_component": None, "explanation":
                "Остаток после внешних потоков включает переоценку, выплаты, комиссии и валютные изменения; это не точная доходность. Валютная компонента отдельно не определена."
                if exact else "Для точного остатка нужны два синхронных снимка всех счетов и полная история внешних потоков в валюте оценки. Неизвестное не подменяется нулём."}


def _payout_row(item: dict, position: dict, ref: dict, now: datetime) -> dict | None:
    kind, uid = position["instrument_type"], position["instrument_uid"]
    when = item.get("couponDate") if kind == "bond" else item.get("paymentDate")
    if not when:
        return None
    per_unit = money(item.get("payOneBond") if kind == "bond" else item.get("dividendNet"))
    record_date = item.get("fixDate") if kind == "bond" else item.get("recordDate")
    unknown = not record_date or str(record_date)[:10] <= now.date().isoformat()
    quantity = decimal(position.get("quantity"))
    cancelled = str(item.get("dividendType", "")).lower() == "cancelled"
    amount, status = None, "announced"
    if cancelled:
        status = "cancelled"
    elif per_unit and quantity is not None and quantity > 0 and not unknown:
        amount = money(decimal(per_unit) * quantity, per_unit["currency"])
        status = "expected"
    return {"id": digest({"uid": uid, "account": position["account_id"], "event": item}), "instrument_uid": uid,
            "account_id": position["account_id"], "title": position["title"], "kind": "coupon" if kind == "bond" else "dividend",
            "date": when, "record_date": record_date, "status": status, "amount": amount, "per_unit": per_unit,
            "eligibility_unknown": unknown, "source_ids": [ref["id"]], "estimate_is_guaranteed": False}


def _read_payouts(reader, uid: str, kind: str, now: datetime, stored: dict) -> dict | None:
    if uid in stored:
        return stored[uid]
    method = "coupons" if kind == "bond" else "dividends"
    try:
        market.pace_instruments(reader.scope)
        raw = reader.read(method, {"instrumentId": uid, "from": (now - timedelta(days=365)).isoformat(), "to": (now + timedelta(days=365)).isoformat()})
    except HTTPException:
        return None
    stored[uid] = {"data": raw, "as_of": now_iso(), "method": method}
    return stored[uid]


def _instrument_payout_rows(held: list, raw: dict, now: datetime, ref: dict) -> tuple[list, bool]:
    rows, complete = [], True
    key = "events" if held[0]["instrument_type"] == "bond" else "dividends"
    for item in raw["data"].get(key, []):
        for position in held:
            row = _payout_row(item, position, ref, now)
            if row is None:
                complete = False
            else:
                rows.append(row)
    return rows, complete


@financial_context
def _payment_events(user: Any, snapshot: dict, checkpoint: dict, progress) -> tuple[list[dict], list[dict], bool]:
    rows, sources, complete = [], [], True
    by_uid = defaultdict(list)
    for position in snapshot["positions"]:
        if position["instrument_type"] in {"share", "bond"}:
            by_uid[position["instrument_uid"]].append(position)
    stored = checkpoint.setdefault("payments", {})
    now = datetime.fromisoformat(snapshot["as_of"])
    with details.BrokerReader(user) as reader:
        for index, (uid, held) in enumerate(by_uid.items()):
            progress("collecting_payouts", checkpoint, completed=index, total=len(by_uid))
            raw = _read_payouts(reader, uid, held[0]["instrument_type"], now, stored)
            if raw is None:
                complete = False
                continue
            progress("collecting_payouts", checkpoint, completed=index + 1, total=len(by_uid))
            ref = source(raw["method"], uid, raw["as_of"], ttl=3600)
            instrument_rows, instrument_complete = _instrument_payout_rows(held, raw, now, ref)
            rows.extend(instrument_rows)
            sources.append(ref)
            complete &= instrument_complete
    return rows, sources, complete


def _collect_metadata(user: Any, dashboard: dict, checkpoint: dict, progress) -> tuple:
    metadata = checkpoint.setdefault("metadata", {})
    all_positions = [p for a in dashboard["accounts"] for p in a["positions"]]
    market.portfolio_metadata(user, all_positions, metadata, progress, checkpoint)
    # Every position is retained. Identity metadata is resumable rather than
    # silently slicing a large portfolio at the first 100 instruments.
    unique = {p["id"]: p for p in all_positions if p.get("instrumentType") != "cash"}
    for index, uid in enumerate(unique):
        if uid not in metadata:
            progress("collecting_metadata", checkpoint, completed=index, total=len(unique))
            try:
                metadata[uid] = market.instrument(user, uid)
            except HTTPException:
                metadata[uid] = {"_unavailable": True}
            progress("collecting_metadata", checkpoint, completed=index + 1, total=len(unique))
    return metadata, len(all_positions), len(unique)


def _merge_operation_page(saved: dict, items: list) -> None:
    if not isinstance(items, list):
        raise HTTPException(502, "operations_response_invalid")
    seen = {item["id"]: item for item in saved["items"]}
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("id"):
            raise HTTPException(502, "operation_identity_missing")
        item = details.normalize_operation(raw)
        if item["id"] in seen and seen[item["id"]] != item:
            raise HTTPException(502, "operation_conflicting_observations")
        if item["id"] not in seen:
            saved["items"].append(item)
            seen[item["id"]] = item


def _collect_operation_pages(reader, account_id: str, saved: dict, begin: datetime, finish: datetime, checkpoint: dict, progress) -> None:
    while not saved["complete"] and saved["pages"] < 200:
        progress("collecting_operations", checkpoint, completed=saved["pages"], total=None)
        raw = reader.read("operations", {"accountId": account_id, "from": begin.isoformat(), "to": finish.isoformat(), "limit": 1000,
                                         "cursor": saved["cursor"], "withoutCommissions": False, "withoutTrades": False})
        _merge_operation_page(saved, raw.get("items", []))
        saved["pages"] += 1
        saved["as_of"] = now_iso()
        if not raw.get("hasNext"):
            saved["complete"] = True
        else:
            cursor = str(raw.get("nextCursor") or "")
            if not cursor or cursor == saved["cursor"]:
                raise HTTPException(502, "operations_cursor_invalid")
            saved["cursor"] = cursor
        progress("collecting_operations", checkpoint, completed=saved["pages"], total=None)


def _linked_operation(item: dict, account_id: str, ref: dict, held: set) -> dict:
    uid = item.get("instrumentUid")
    link = {"account_id": account_id, "instrument_uid": uid, "currently_held": (account_id, uid) in held} if uid else None
    return {**item, "account_id": account_id, "source_ids": [ref["id"]], "position_ref": link}


def _collect_operations(user: Any, snapshot: dict, begin: datetime, finish: datetime, checkpoint: dict, progress) -> tuple:
    operations, operation_sources, operations_complete = [], [], True
    stored_operations = checkpoint.setdefault("operations", {})
    held = {(p["account_id"], p["instrument_uid"]) for p in snapshot["positions"]}
    with details.BrokerReader(user) as reader:
        for account in snapshot["accounts"]:
            account_id = account["id"]
            saved = stored_operations.setdefault(account_id, {"items": [], "cursor": "", "complete": False, "pages": 0})
            _collect_operation_pages(reader, account_id, saved, begin, finish, checkpoint, progress)
            operations_complete &= saved["complete"]
            ref = source("GetOperationsByCursor", account_id, saved.get("as_of", snapshot["as_of"]), ttl=300)
            operation_sources.append(ref)
            operations.extend(_linked_operation(item, account_id, ref, held) for item in saved["items"])
    return operations, operation_sources, operations_complete


def _received_payout_events(operations: list) -> list:
    payout_rows = []
    for item in operations:
        if item.get("state") == "OPERATION_STATE_EXECUTED" and item.get("category") in {"coupons", "dividends"}:
            payout_rows.append({"id": "received:" + item["account_id"] + ":" + item["id"], "instrument_uid": item.get("instrumentUid"),
                                "account_id": item["account_id"], "title": item["title"], "kind": "coupon" if item["category"] == "coupons" else "dividend",
                                "date": item["date"], "status": "received", "amount": money(item.get("payment")), "per_unit": None,
                                "eligibility_unknown": False, "source_ids": item["source_ids"], "operation_id": item["id"]})
    return payout_rows


def _collect_market_events(user: Any, checkpoint: dict, progress) -> None:
    if "news" not in checkpoint:
        checkpoint["news"] = safe_section(lambda: details.cached(("workspace-news", *details.identity(user)), 600,
            lambda: market.load_news(user)), empty={"items": [], "complete": False})
        progress("collecting_news", checkpoint)
    if "calendar" not in checkpoint:
        def calendar_envelope():
            value = market.calendar(user)
            return section(value, as_of=value["as_of"], sources=[value["source"]])
        checkpoint["calendar"] = safe_section(calendar_envelope, empty={"exchanges": []})
        progress("collecting_calendar", checkpoint)


def _held_news(snapshot: dict, news: dict) -> list:
    held = defaultdict(list)
    for position in snapshot["positions"]:
        held[position["instrument_uid"]].append(position)
    events = []
    for item in news.get("data", {}).get("items", []):
        linked = [uid for uid in item.get("instrument_uids", []) if uid in held]
        if linked:
            events.append({**item, "kind": "news", "instrument_uids": linked, "relationship": "broker_link",
                           "held_positions": [{"instrument_uid": uid, "account_id": p["account_id"], "value": p["value"]} for uid in linked for p in held[uid]],
                           "impact_is_inference": True, "impact": None})
    return events


def collect(user: Any, payload: dict, checkpoint: dict, progress) -> dict:
    currency = payload.get("currency", "RUB")
    begin, requested_finish = date_range(date.fromisoformat(payload["start"]) if payload.get("start") else None,
                                         date.fromisoformat(payload["end"]) if payload.get("end") else None)
    if checkpoint.get("broker_key") not in {None, state.broker_key(user)}:
        raise HTTPException(409, "workspace_broker_connection_changed")
    checkpoint["broker_key"] = state.broker_key(user)
    progress("collecting", checkpoint)
    if "dashboard" not in checkpoint:
        checkpoint["dashboard"] = details.load_dashboard(user, currency)
        progress("capital_collected", checkpoint)
    dashboard = checkpoint["dashboard"]
    metadata, position_count, metadata_count = _collect_metadata(user, dashboard, checkpoint, progress)
    snapshot = normalize_snapshot(user, dashboard, metadata)
    snapshot["snapshot_id"] = digest({key: snapshot[key] for key in ("capital", "as_of", "positions", "position_coverage")})
    finish = min(requested_finish, datetime.fromisoformat(snapshot["as_of"]))
    operations, operation_sources, operations_complete = _collect_operations(user, snapshot, begin, finish, checkpoint, progress)
    payout_rows, payout_sources, payouts_complete = _payment_events(user, snapshot, checkpoint, progress)
    payout_rows.extend(_received_payout_events(operations))
    _collect_market_events(user, checkpoint, progress)
    snapshot.update(attribution=attribution(user, snapshot, operations, operations_complete, begin, finish),
                    payouts={"items": sorted(payout_rows, key=lambda r: str(r.get("date")), reverse=True), "complete": payouts_complete and operations_complete,
                             "received_range": {"start": begin.isoformat(), "end": finish.isoformat()}, "announced_and_received_are_distinct": True},
                    operations={"items": operations, "complete": operations_complete, "start": begin.isoformat(), "end": finish.isoformat()},
                    events={"items": _held_news(snapshot, checkpoint["news"])}, news=checkpoint["news"], calendar=checkpoint["calendar"])
    snapshot["sources"] += operation_sources + payout_sources + checkpoint["news"].get("sources", []) + checkpoint["calendar"].get("sources", [])
    snapshot["collection"] = {"all_positions_retained": True, "total_positions": position_count,
                              "metadata_available": sum(not v.get("_unavailable") for v in metadata.values()),
                              "metadata_total": metadata_count, "finished_at": now_iso()}
    progress("persisting", checkpoint)
    persist(user, snapshot)
    return {"snapshot_id": snapshot["snapshot_id"], "currency": currency, "as_of": snapshot["as_of"], "collection": snapshot["collection"]}


def persist(user: Any, snapshot: dict, *, expected_snapshot: dict | None = None) -> None:
    user_id = int(user["id"])
    try:
        from . import volume_credit
    except ImportError:
        import volume_credit
    rating_observations = volume_credit.observations(snapshot)
    rating_signature = volume_credit.signature(rating_observations)
    if snapshot.get("rating_signature") != rating_signature:
        snapshot["snapshot_id"] = digest({"positions": snapshot.get("positions", []), "capital": snapshot.get("capital"),
                                          "as_of": snapshot["as_of"], "position_coverage": snapshot.get("position_coverage"),
                                          "rating_signature": rating_signature})
    snapshot["rating_signature"] = rating_signature
    snapshot["rating_observations"] = rating_observations
    snapshot["sources"] = list({r["id"]: r for r in snapshot.get("sources", []) +
                               [ref for observation in rating_observations.values() for ref in observation.get("sources", [])]}.values())
    active = state.active_strategy(user_id)
    current_risk = state.exposure_data(snapshot, (active or {}).get("config"))
    old = state.saved_snapshot(user, snapshot["currency"])
    old_risk = state.exposure_data(old, (active or {}).get("config"))
    old_breaches = {(r["direction"], r["id"]): r for r in (old or {}).get("risk_breaches", old_risk["concentrations"]) if r["breached"]}
    new_breaches = {(r["direction"], r["id"]): r for r in current_risk["concentrations"] if r["breached"]}
    all_current = {(r["direction"], r["id"]): r for r in current_risk["concentrations"]}
    complete_axes = {row["direction"] for row in current_risk["coverage"] if row["state"] == "available"}
    snapshot["risk_breaches"] = list(new_breaches.values())
    snapshot["applied_strategy_version"] = (active or {}).get("version", 0)
    with transaction(backend.connect) as db:
        try:
            from .volume_jobs import assert_current_in
            from .ai_jobs import assert_current_owner_in
            from .monitoring_access import assert_monitoring_access_in
        except ImportError:
            from volume_jobs import assert_current_in
            from ai_jobs import assert_current_owner_in
            from monitoring_access import assert_monitoring_access_in
        assert_current_in(db)
        assert_current_owner_in(db)
        assert_monitoring_access_in(db)
        if expected_snapshot is not None:
            current = db.execute("SELECT id,broker_key,payload_json FROM workspace_snapshots WHERE user_id=? AND currency=?",
                                 (user_id, snapshot["currency"])).fetchone()
            value = None if current is None else {**json.loads(current["payload_json"]), "snapshot_id": current["id"]}
            if current is None or current["broker_key"] != state.broker_key(user) or digest(value) != digest(expected_snapshot):
                raise HTTPException(409, "workspace_snapshot_changed")
        try:
            from . import operations_ledger
        except ImportError:
            import operations_ledger
        snapshot["cash_ledger"] = operations_ledger.record_snapshot_in(
            db, user_id=user_id, broker_key=state.broker_key(user), snapshot=snapshot)
        db.execute("""INSERT INTO workspace_snapshots VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id,currency) DO UPDATE SET id=excluded.id,broker_key=excluded.broker_key,payload_json=excluded.payload_json,created_at=excluded.created_at""",
            (user_id, snapshot["currency"], snapshot["snapshot_id"], state.broker_key(user), state.encode(snapshot), int(time.time())))
        _record_concentration_changes(db, user_id, snapshot, active, old_breaches, new_breaches, all_current, complete_axes)
        for item in snapshot.get("events", {}).get("items", []):
            state.event(db, user_id, "market_news", snapshot["snapshot_id"], item, item["id"])
        volume_credit.record_changes_in(db, user_id, snapshot, old)


def ai_data(user: Any) -> dict:
    user_id = int(user["id"])
    with closing(backend.connect()) as db:
        row = db.execute("SELECT * FROM analysis_runs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 1", (user_id,)).fetchone()
        cards = db.execute("SELECT id,title,summary,actions_json,evidence_json,created_at FROM insight_cards WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 2", (user_id,)).fetchall()
        checked = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        check_rows = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_check' ORDER BY id DESC LIMIT 20", (user_id,)).fetchall()
        slot_rows = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='monitor_slot' ORDER BY id", (user_id,)).fetchall()
        monitor_jobs = db.execute("SELECT id,status,result_json,error_code,created_at,updated_at,cancel_requested_at FROM ai_work_jobs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 20", (user_id,)).fetchall()
    last_check = json.loads(checked[0]) if checked else None
    last = _last_analysis_run(row, last_check)
    diff = _analysis_difference(user_id, cards)
    try:
        GuardedAIClient(user_id, backend.connect).check_ready(AnalysisTier.FAST)
        readiness = {"available": True, "reason": None}
    except GuardError as error:
        readiness = {"available": False, "reason": error.code}
    try:
        from .volume_jobs import user_jobs
    except ImportError:
        from volume_jobs import user_jobs
    observed_jobs = [_monitor_job_record(row) for row in monitor_jobs]
    check_history = []
    for record in check_rows:
        item = json.loads(record[0])
        summary = {key: item.get(key) for key in ("check_id", "checked_at", "state", "reason", "tier", "card_id", "run_id", "error_code")}
        summary["observation_count"] = (item.get("trigger") or {}).get("coverage", {}).get("total", 0)
        check_history.append(summary)
    return {"last_run": last, "last_check": last_check, "check_history": check_history,
            "slot_checks": [json.loads(row[0]) for row in slot_rows], "monitor_jobs": observed_jobs,
            "next_runs": notifications.schedule_slots(user_id), "jobs": user_jobs(user_id),
            "budget": MoneyLedger(backend.connect).user_summary(user_id), "readiness": readiness, "analysis_diff": diff}


@router.get("/cash-ledger", responses=HTTP_ERRORS)
def cash_ledger_status(user: Annotated[Any, Depends(backend.current_user)],
                       currency: Literal["RUB", "USD", "EUR"] = "RUB") -> dict:
    snapshot = state.saved_snapshot(user, currency)
    receipt = (snapshot or {}).get("cash_ledger")
    if not isinstance(receipt, dict):
        return {"state": "unavailable", "reason": "cash_ledger_not_collected",
                "performance_calculated": False, "tax_liability_estimated": False}
    return {**receipt, "snapshot_id": snapshot["snapshot_id"],
            "operations_as_of": snapshot.get("section_as_of", {}).get("operations")}


@router.get("/public-sources", responses=HTTP_ERRORS)
def public_source_status(user: Annotated[Any, Depends(backend.current_user)],
                         currency: Literal["RUB", "USD", "EUR"] = "RUB") -> dict:
    """Read the existing materialized source state; opening a screen never fetches."""
    try:
        from . import public_sources
    except ImportError:
        import public_sources
    return public_sources.snapshot_status(state.saved_snapshot(user, currency))


@router.get("/system-readiness", responses=HTTP_ERRORS)
def system_readiness(user: Annotated[Any, Depends(backend.current_user)],
                     currency: Literal["RUB", "USD", "EUR"] = "RUB") -> dict:
    """Read only the authenticated current connection; never schedule work."""
    try:
        from .workspace_readiness import build_status
    except ImportError:
        from workspace_readiness import build_status
    return build_status(state.saved_snapshot(user, currency), state.active_strategy(int(user["id"])),
                        connected=bool(user["tinvest_token_encrypted"]))


@router.get("", responses=HTTP_ERRORS)
def workspace(currency: Literal["RUB", "USD", "EUR"] = "RUB", start: date | None = None, end: date | None = None,
              *, user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    snapshot = state.saved_snapshot(user, currency)
    observed = (snapshot or {}).get("as_of")
    stale = observed is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(observed)).total_seconds() > 900
    missing = "workspace_refresh_required" if user["tinvest_token_encrypted"] else "tinvest_not_connected"
    base_state, reason = _snapshot_state(snapshot, stale, missing)
    sections = _snapshot_sections(snapshot, observed, base_state, reason)
    active = state.active_strategy(int(user["id"]))
    try:
        from .workspace_readiness import build_status
    except ImportError:
        from workspace_readiness import build_status
    sections["system"] = section(build_status(snapshot, active,
        connected=bool(user["tinvest_token_encrypted"])), as_of=observed)
    exposures = state.exposure_data(snapshot, (active or {}).get("config"))
    exposure_state = "partial" if snapshot and any(not axis["complete"] for axis in exposures["axes"]) else base_state
    sections["exposures"] = section({"axes": exposures["axes"]}, state=exposure_state, reason=reason or ("identity_or_valuation_coverage_incomplete" if exposure_state == "partial" else None), as_of=observed)
    sections["goals"] = section(state.goal_data(user), as_of=observed)
    sections["risks"] = section(state.risk_data(user, currency), state=base_state, reason=reason, as_of=observed)
    sections["ai"] = section(ai_data(user), as_of=now_iso())
    sections["strategy"] = section(state.strategy_data(int(user["id"])), state="available" if active else "not_configured", reason=None if active else "strategy_confirmation_required")
    sections["notifications"] = section(notifications.preferences_data(int(user["id"])), as_of=now_iso())
    return {"schema_version": 1, "snapshot_id": (snapshot or {}).get("snapshot_id"), "as_of": observed, "currency": currency,
            "sections": sections, "sources": (snapshot or {}).get("sources", []), "collection": (snapshot or {}).get("collection"),
            "capabilities": {"read_only_broker": True, "refresh_requires_explicit_job": True, "chat": True,
                             "strategy_confirmation": True, "notification_channel": "app_poll", "push_delivery": False,
                             "frame_network_requests": False, "public_sources": True, "cash_ledger": True,
                             "system_readiness": True}, "requested_range": {"start": str(start) if start else None, "end": str(end) if end else None}}


@router.get("/operations/{account_id}/{operation_id}/position", responses=HTTP_ERRORS)
def operation_position(account_id: str, operation_id: str, user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    snapshot = state.saved_snapshot(user)
    operation = next((row for row in (snapshot or {}).get("operations", {}).get("items", []) if row["account_id"] == account_id and row["id"] == operation_id), None)
    if operation is None:
        raise HTTPException(404, "operation_not_in_workspace")
    uid = operation.get("instrumentUid")
    held = [p for p in (snapshot or {}).get("positions", []) if p["account_id"] == account_id and p["instrument_uid"] == uid]
    return {"operation": operation, "position_ref": operation["position_ref"], "positions": held,
            "relationship": "broker_instrument_uid", "as_of": (snapshot or {}).get("as_of")}


def _record_concentration_changes(db, user_id, snapshot, active, old_breaches, new_breaches, all_current, complete_axes):
    for key in new_breaches.keys() | old_breaches.keys():
        before, after = old_breaches.get(key), new_breaches.get(key)
        if before is not None and after is not None and before["share_percent"] == after["share_percent"]:
            continue
        details_row = after or before
        # An incomplete aggregate may fall below its limit only because a
        # position lost its valuation/identity. That is not risk resolution.
        missing_basis = after is None and (key[0] not in complete_axes or
            key in all_current and all_current[key]["breached"] is None or
            decimal(snapshot.get("capital", {}).get("total")) in {None, ZERO})
        kind, title_prefix = _risk_change_label(after, missing_basis)
        risk_event = state.event(db, user_id, kind, snapshot["snapshot_id"],
            {"title": title_prefix + details_row["label"],
             "details": {"before": before, "after": after, "strategy_version": (active or {}).get("version", 0)},
             "instrument_uids": details_row["instrument_uids"], "source_ids": details_row["source_ids"]},
            snapshot["snapshot_id"] + ":" + ":".join(key))
        notifications.enqueue_in(db, user_id, kind="risk", title=risk_event["title"],
                                 body="Проверьте подтверждённый лимит и актуальность источника; это не выполненная сделка.", event_id=risk_event["id"])


def _risk_change_label(after, missing_basis):
    if after:
        return "risk_limit_observed", "Превышение лимита: "
    if missing_basis:
        return "risk_data_stale", "Основание риска требует обновления: "
    return "risk_limit_resolved", "Лимит восстановлен: "


def _last_analysis_run(row, last_check):
    if not row:
        return None
    card_id = last_check.get("card_id") if last_check and last_check.get("run_id") == row["id"] else None
    return {"id": row["id"], "created_at": datetime.fromtimestamp(row["created_at"], timezone.utc).isoformat(),
            "state": row["state"], "reason": row["reason"], "tier": row["tier"], "card_id": card_id}


def _analysis_difference(user_id, cards):
    current = {"title": cards[0]["title"], "summary": cards[0]["summary"], "actions": json.loads(cards[0]["actions_json"])} if cards else {}
    previous = {"title": cards[1]["title"], "summary": cards[1]["summary"], "actions": json.loads(cards[1]["actions_json"])} if len(cards) > 1 else {}
    diff = {"previous_card_id": cards[1]["id"] if len(cards) > 1 else None, "current_card_id": cards[0]["id"] if cards else None,
            "added": [{"field": k, "value": v} for k, v in current.items() if k not in previous],
            "removed": [{"field": k, "value": v} for k, v in previous.items() if k not in current],
            "changed": [{"field": k, "before": previous[k], "after": v, "source_ids": []} for k, v in current.items() if k in previous and previous[k] != v],
            "unchanged": [{"field": k, "value": v, "source_ids": []} for k, v in current.items() if k in previous and previous[k] == v],
            "scope": "stored_report_fields_and_evidence_records", "fact_comparison_available": False,
            "comparison_limit": "Historical cards do not bind every sentence to stable structured fact IDs; text equality is not proof of unchanged underlying facts."}
    diff["evidence_diff"] = _evidence_difference(cards)
    try:
        from .volume_analysis import comparison
    except ImportError:
        from volume_analysis import comparison
    structured = comparison(user_id, diff["current_card_id"], diff["previous_card_id"])
    diff["structured_facts"] = structured
    diff["fact_comparison_available"] = structured["available"]
    return diff


def _evidence_difference(cards):
    evidence_current = json.loads(cards[0]["evidence_json"]) if cards else []
    evidence_previous = json.loads(cards[1]["evidence_json"]) if len(cards) > 1 else []
    return {
        "added": [row for row in evidence_current if row not in evidence_previous],
        "removed": [row for row in evidence_previous if row not in evidence_current],
        "unchanged": [row for row in evidence_current if row in evidence_previous],
        "current_source_ids": sorted({row["source_id"] for row in evidence_current if row.get("source_id")}),
        "previous_source_ids": sorted({row["source_id"] for row in evidence_previous if row.get("source_id")})}


def _monitor_job_record(row):
    status = row["status"]
    if row["error_code"] == "analysis_cancelled":
        status = "cancelled"
    elif row["cancel_requested_at"] and status == "running":
        status = "cancel_requested"
    return {"job_id": row["id"], "state": status,
            "result": json.loads(row["result_json"]) if row["result_json"] else None, "error_code": row["error_code"],
            "created_at": datetime.fromtimestamp(row["created_at"], timezone.utc).isoformat(),
            "updated_at": datetime.fromtimestamp(row["updated_at"], timezone.utc).isoformat(), "kind": "scheduled_monitor"}


def _snapshot_sections(snapshot, observed, base_state, reason):
    sections = {}
    for key, empty in (("capital", {"total": None, "cash": []}), ("attribution", {}), ("payouts", {"items": [], "complete": False}), ("events", {"items": []})):
        data = (snapshot or {}).get(key, empty)
        item_state = "partial" if snapshot and data.get("complete") is False else base_state
        section_observed = (snapshot or {}).get("section_as_of", {}).get(key, observed)
        section_stale = section_observed is not None and (datetime.now(timezone.utc) - datetime.fromisoformat(section_observed)).total_seconds() > 900
        if section_stale:
            item_state = "partial"
        item_reason = reason
        if key in {"payouts", "events"} and key in (snapshot or {}).get("section_as_of", {}):
            # Event freshness is independent of an intentionally old valuation.
            item_state = "partial" if section_stale or section_observed is None or data.get("complete") is False else "available"
            item_reason = None
        sections[key] = section(data, state=item_state, reason=_section_reason(section_stale, item_reason, item_state), as_of=section_observed, sources=(snapshot or {}).get("sources", []))
    return sections


def _snapshot_state(snapshot, stale, missing):
    if stale:
        return "partial", "snapshot_stale"
    if snapshot:
        return "available", None
    return "unavailable", missing


def _section_reason(stale, reason, state):
    if stale:
        return "snapshot_stale"
    if reason:
        return reason
    return "source_coverage_incomplete" if state == "partial" else None
