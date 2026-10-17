"""Durable workspace state, explicit strategy confirmation and verified exposures.

No broker/model calls are made by the read endpoints in this module. Unknown
identities, valuations and limits remain unknown instead of becoming defaults.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import json
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

try:
    from . import app as backend, research_store
    from .ai_budget import transaction
    from .volume_contract import decimal, digest, money, now_iso, require_id, source, text_number, ZERO, financial_context
except ImportError:
    import app as backend
    import research_store
    from ai_budget import transaction
    from volume_contract import decimal, digest, money, now_iso, require_id, source, text_number, ZERO, financial_context

router = APIRouter(prefix="/workspace", tags=["Workspace state"])
AXES = (("position", "Позиции"), ("issuer", "Эмитенты"), ("group", "Экономические группы"),
        ("sector", "Отрасли"), ("currency", "Валюта оценки позиции"), ("country", "Страна основного риска"))


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def initialize() -> None:
    with closing(backend.connect()) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS workspace_snapshots (
                user_id INTEGER NOT NULL, currency TEXT NOT NULL, id TEXT NOT NULL,
                broker_key TEXT NOT NULL, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                PRIMARY KEY(user_id,currency));
            CREATE TABLE IF NOT EXISTS workspace_records (
                user_id INTEGER NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL,
                payload_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                PRIMARY KEY(user_id,kind,id));
            CREATE TABLE IF NOT EXISTS workspace_strategy_versions (
                user_id INTEGER NOT NULL, version INTEGER NOT NULL, config_json TEXT NOT NULL,
                snapshot_id TEXT NOT NULL, previous_version INTEGER NOT NULL,
                reason TEXT NOT NULL, request_id TEXT NOT NULL, confirmed_at INTEGER NOT NULL,
                PRIMARY KEY(user_id,version), UNIQUE(user_id,request_id));
            CREATE TABLE IF NOT EXISTS workspace_strategy_previews (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expected_version INTEGER NOT NULL,
                snapshot_id TEXT NOT NULL, config_json TEXT NOT NULL, impact_json TEXT NOT NULL,
                expires_at INTEGER NOT NULL, reason TEXT NOT NULL, consumed_at INTEGER);
            CREATE TABLE IF NOT EXISTS workspace_events (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
                snapshot_id TEXT, payload_json TEXT NOT NULL, created_at INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS workspace_events_user ON workspace_events(user_id,created_at);
            CREATE TABLE IF NOT EXISTS workspace_request_receipts (
                user_id INTEGER NOT NULL, request_id TEXT NOT NULL, kind TEXT NOT NULL,
                payload_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at INTEGER NOT NULL,
                PRIMARY KEY(user_id,request_id));
        """)
        db.commit()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestId(StrictModel):
    request_id: str = Field(min_length=8, max_length=120, pattern=r"^[A-Za-z0-9_.:\-]+$")


def receipt(db, user_id: int, request_id: str, kind: str, payload: dict) -> dict | None:
    row = db.execute("SELECT kind,payload_hash,result_json FROM workspace_request_receipts WHERE user_id=? AND request_id=?",
                     (user_id, request_id)).fetchone()
    if row is None:
        return None
    if row["kind"] != kind or row["payload_hash"] != digest(payload):
        raise HTTPException(409, "request_id_payload_conflict")
    return json.loads(row["result_json"])


def remember(db, user_id: int, request_id: str, kind: str, payload: dict, result: dict) -> None:
    db.execute("INSERT INTO workspace_request_receipts VALUES (?,?,?,?,?,?)",
               (user_id, request_id, kind, digest(payload), encode(result), int(time.time())))


def broker_key(user: Any) -> str:
    token = user["tinvest_token_encrypted"]
    return digest({"token_fingerprint": str(token)}) if token else "disconnected"


def saved_snapshot(user: Any, currency: str = "RUB") -> dict | None:
    with closing(backend.connect()) as db:
        row = db.execute("SELECT * FROM workspace_snapshots WHERE user_id=? AND currency=?",
                         (int(user["id"]), currency)).fetchone()
    if row is None or row["broker_key"] != broker_key(user):
        return None
    result = json.loads(row["payload_json"])
    result["snapshot_id"] = row["id"]
    return result


def records(user_id: int, kind: str, *, limit: int = 1000) -> list[dict]:
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind=? ORDER BY created_at,id LIMIT ?",
                          (user_id, kind, limit)).fetchall()
    return [json.loads(row[0]) for row in rows]


def record(db, user_id: int, kind: str, identifier: str, payload: dict) -> None:
    now = int(time.time())
    db.execute("""INSERT INTO workspace_records VALUES (?,?,?,?,1,?,?)
        ON CONFLICT(user_id,kind,id) DO UPDATE SET payload_json=excluded.payload_json,
        version=workspace_records.version+1,updated_at=excluded.updated_at""",
        (user_id, kind, identifier, encode(payload), now, now))


def event(db, user_id: int, kind: str, snapshot_id: str | None, payload: dict, key: str | None = None) -> dict:
    identifier = digest({"user": user_id, "kind": kind, "key": key or payload})
    result = {"id": identifier, "kind": kind, "snapshot_id": snapshot_id, "occurred_at": now_iso(), **payload}
    db.execute("INSERT OR IGNORE INTO workspace_events VALUES (?,?,?,?,?,?)",
               (identifier, user_id, kind, snapshot_id, encode(result), int(time.time())))
    return result


def _version(row) -> dict | None:
    if row is None:
        return None
    return {"version": row["version"], "config": json.loads(row["config_json"]),
            "snapshot_id": row["snapshot_id"], "previous_version": row["previous_version"],
            "reason": row["reason"], "confirmed_at": datetime.fromtimestamp(row["confirmed_at"], timezone.utc).isoformat()}


def active_strategy(user_id: int, db=None) -> dict | None:
    def read(connection):
        return _version(connection.execute("SELECT * FROM workspace_strategy_versions WHERE user_id=? ORDER BY version DESC LIMIT 1", (user_id,)).fetchone())
    if db is not None:
        return read(db)
    with closing(backend.connect()) as connection:
        return read(connection)


def strategy_data(user_id: int) -> dict:
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT * FROM workspace_strategy_versions WHERE user_id=? ORDER BY version DESC LIMIT 100", (user_id,)).fetchall()
    active = _version(rows[0]) if rows else None
    return {"active": active, "draft": None, "history": [_version(row) for row in rows], "limits_applied": active is not None}


@router.get("/strategy")
def get_strategy(user: Any = Depends(backend.current_user)) -> dict:
    return strategy_data(int(user["id"]))


def positions(snapshot: dict | None) -> list[dict]:
    return list((snapshot or {}).get("positions") or [])


def _identity(uid: str) -> dict | None:
    return research_store.latest_verified(backend.connect, "issuer_identity", uid, datetime.now(timezone.utc))


@financial_context
def exposure_data(snapshot: dict | None, config: dict | None = None) -> dict:
    rows = positions(snapshot)
    currency = (snapshot or {}).get("currency", "RUB")
    total = decimal(((snapshot or {}).get("capital") or {}).get("total"))
    limits = (config or {}).get("limits", {})
    axes, coverage, concentrations = [], [], []
    for axis, label in AXES:
        groups: dict[str, dict] = {}
        unknown = []
        known = 0
        not_applicable = 0
        for item in rows:
            if axis in {"issuer", "group", "sector", "country"} and item.get("instrument_type") == "cash":
                not_applicable += 1
                continue
            uid = str(item.get("instrument_uid") or "")
            identity = item.get("verified_identity") or {}
            metadata = item.get("metadata") or {}
            if identity:
                try:
                    from .credit_evidence import Source
                except ImportError:
                    from credit_evidence import Source
                try:
                    if not Source(**identity["source"]).valid(datetime.now(timezone.utc)):
                        identity = {}
                except (KeyError, TypeError, ValueError):
                    identity = {}
            identities = {
                "position": (uid, item.get("title") or uid),
                "issuer": (identity.get("issuer_id"), identity.get("issuer_name") or identity.get("issuer_id")),
                "group": (identity.get("group_id"), identity.get("group_name") or identity.get("group_id")),
                "sector": (metadata.get("sector"), metadata.get("sector")),
                "currency": ((item.get("value") or {}).get("currency"), (item.get("value") or {}).get("currency")),
                "country": (metadata.get("country_of_risk"), metadata.get("country_of_risk_name") or metadata.get("country_of_risk")),
            }
            identifier, name = identities[axis]
            value = decimal(item.get("value"))
            if not identifier or value is None or (item.get("value") or {}).get("currency") != currency:
                unknown.append(uid)
                continue
            known += 1
            key = str(identifier)
            bucket = groups.setdefault(key, {"id": key, "label": str(name), "amount": ZERO, "instrument_uids": [], "source_ids": []})
            bucket["amount"] += value
            if uid not in bucket["instrument_uids"]:
                bucket["instrument_uids"].append(uid)
            refs = identity.get("source", {}) if axis in {"issuer", "group"} else {}
            metadata_ref = (metadata.get("source") or {}).get("id") if axis in {"sector", "country"} else None
            for ref in [refs.get("id"), metadata_ref, *item.get("source_ids", [])]:
                if ref and ref not in bucket["source_ids"]:
                    bucket["source_ids"].append(ref)
        output = []
        for bucket in groups.values():
            amount = bucket.pop("amount")
            share = amount / total * 100 if total is not None and total > 0 else None
            limit = decimal(limits.get(axis + "_percent"))
            normalized = {**bucket, "value": money(amount, currency), "share_percent": text_number(share),
                          "limit_percent": text_number(limit), "breached": share > limit if share is not None and limit is not None else None}
            output.append(normalized)
            concentrations.append({"direction": axis, **normalized})
        complete = bool(snapshot) and not unknown
        axes.append({"id": axis, "label": label, "complete": complete, "unknown_count": len(unknown), "items": output})
        coverage.append({"direction": axis, "state": "available" if complete else "partial" if known else "unavailable",
                         "known_positions": known, "total_positions": len(rows), "missing_instrument_uids": sorted(set(unknown)),
                         "not_applicable_positions": not_applicable, "as_of": (snapshot or {}).get("as_of"),
                         "age_seconds": max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(snapshot["as_of"])).total_seconds())) if snapshot and snapshot.get("as_of") else None,
                         "basis": "operator_reviewed_identity" if axis in {"issuer", "group"} else "broker_snapshot_no_fx_conversion"})
    return {"axes": axes, "coverage": coverage, "concentrations": concentrations}


def risk_data(user: Any, currency: str = "RUB", *, config: dict | None = None, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if snapshot is not None else saved_snapshot(user, currency)
    active = active_strategy(int(user["id"]))
    values = exposure_data(snapshot, config if config is not None else (active or {}).get("config"))
    market_rows = {row["instrument_uid"]: row for row in records(int(user["id"]), "instrument_market", limit=10000) if row.get("broker_key") == broker_key(user)}
    scoped = [p for p in positions(snapshot) if p.get("instrument_type") != "cash"]
    for direction in ("trading", "liquidity", "ratings"):
        known, missing, dates = 0, [], []
        for position in scoped:
            item = market_rows.get(position["instrument_uid"], {}).get(direction, {})
            refs = item.get("sources", [])
            if direction == "ratings":
                # Historical expired ratings remain inspectable but do not make
                # a newer, valid current assessment disappear.
                current_ids = {r.get("source", {}).get("id") for r in item.get("data", {}).get("items", [])}
                refs = [ref for ref in refs if ref.get("id") in current_ids]
            fresh = refs and all(datetime.fromisoformat(ref["expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc) for ref in refs)
            if item.get("state") == "available" and fresh:
                known += 1
                if item.get("as_of"):
                    dates.append(item["as_of"])
            else:
                missing.append(position["instrument_uid"])
        values["coverage"].append({"direction": direction, "state": "available" if known == len(scoped) and bool(snapshot) else "partial" if known else "unavailable",
            "known_positions": known, "total_positions": len(scoped), "not_applicable_positions": len(positions(snapshot)) - len(scoped),
            "missing_instrument_uids": sorted(set(missing)), "as_of": min(dates) if dates else None,
            "age_seconds": max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(min(dates))).total_seconds())) if dates else None,
            "basis": "verified_dossier_observations_with_expiry_not_a_safety_guarantee"})
    with closing(backend.connect()) as db:
        history = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND kind LIKE 'risk_%' ORDER BY created_at DESC,id LIMIT 100", (int(user["id"]),)).fetchall()
    return {"snapshot_id": (snapshot or {}).get("snapshot_id"), "as_of": (snapshot or {}).get("as_of"),
            "coverage": values["coverage"], "concentrations": values["concentrations"],
            "events": [json.loads(row[0]) for row in history], "strategy_version": (active or {}).get("version", 0),
            "coverage_is_not_probability_of_loss": True}


@router.get("/risks")
def get_risks(currency: Literal["RUB", "USD", "EUR"] = "RUB", user: Any = Depends(backend.current_user)) -> dict:
    return risk_data(user, currency)


class MoneyInput(StrictModel):
    amount: str = Field(max_length=40)
    currency: Literal["RUB", "USD", "EUR"]


class Limits(StrictModel):
    position_percent: str
    issuer_percent: str
    group_percent: str
    sector_percent: str
    currency_percent: str


class StrategyConfig(StrictModel):
    goal: Literal["preservation", "income", "growth"]
    horizon_months: int = Field(ge=1, le=600)
    reserve: MoneyInput
    limits: Limits
    risk_level: Literal["conservative", "moderate", "aggressive"]
    allowed_markets: list[Literal["MOEX", "SPB", "RU"]] = Field(min_length=1, max_length=3)


def validate_config(config: StrategyConfig | dict) -> dict:
    value = config.model_dump() if isinstance(config, BaseModel) else StrategyConfig.model_validate(config).model_dump()
    reserve = decimal(value["reserve"]["amount"])
    if reserve is None or reserve < 0:
        raise HTTPException(422, "strategy_reserve_invalid")
    value["reserve"]["amount"] = text_number(reserve)
    for axis, raw in value["limits"].items():
        limit = decimal(raw)
        if limit is None or not 0 < limit <= 100:
            raise HTTPException(422, "strategy_limit_invalid")
        value["limits"][axis] = text_number(limit)
    value["allowed_markets"] = sorted(set(value["allowed_markets"]))
    return value


class StrategyPreview(StrictModel):
    expected_version: int = Field(ge=0)
    config: StrategyConfig | None = None
    rollback_to_version: int | None = Field(default=None, ge=1)


@router.post("/strategy/preview")
def preview_strategy(payload: StrategyPreview, user: Any = Depends(backend.current_user)) -> dict:
    return _preview_strategy(payload, user)


@financial_context
def _preview_strategy(payload: StrategyPreview, user: Any) -> dict:
    user_id = int(user["id"])
    active = active_strategy(user_id)
    if payload.expected_version != (active or {}).get("version", 0):
        raise HTTPException(409, "strategy_version_changed")
    if (payload.config is None) == (payload.rollback_to_version is None):
        raise HTTPException(422, "strategy_config_or_rollback_required")
    if payload.rollback_to_version is not None:
        with closing(backend.connect()) as db:
            row = db.execute("SELECT config_json FROM workspace_strategy_versions WHERE user_id=? AND version=?", (user_id, payload.rollback_to_version)).fetchone()
        if row is None:
            raise HTTPException(404, "strategy_version_not_found")
        config = validate_config(json.loads(row[0]))
    else:
        config = validate_config(payload.config)
    snapshot = saved_snapshot(user, config["reserve"]["currency"])
    if not snapshot:
        raise HTTPException(409, "workspace_refresh_required")
    created = int(datetime.fromisoformat(snapshot["as_of"]).timestamp())
    if int(time.time()) - created > 900:
        raise HTTPException(409, "strategy_fresh_snapshot_required")
    risk = risk_data(user, config=config, snapshot=snapshot)
    total = decimal(snapshot.get("capital", {}).get("total"))
    reserve = decimal(config["reserve"])
    warnings = ["Лимиты применяются к проверяемым данным; неполное покрытие не означает отсутствие риска."]
    cash = sum((decimal(v) or ZERO for v in snapshot.get("capital", {}).get("cash", []) if v.get("currency") == config["reserve"]["currency"]), ZERO)
    impact = {"coverage": risk["coverage"], "breaches": [v for v in risk["concentrations"] if v["breached"]],
              "reserve_gap": money(max(ZERO, reserve - cash), config["reserve"]["currency"]) if total is not None else None,
              "reserve_gap_basis": "observed_cash_balance_before_withdrawal_restrictions",
              "withdrawable_cash": None,
              "warnings": warnings, "execution_state": "not_executed"}
    warnings.append("Сравнение резерва использует денежный остаток, включая возможные ограничения вывода; доступная к выводу сумма отдельно не установлена.")
    identifier, expiry = uuid.uuid4().hex, int(time.time()) + 300
    reason = "rollback:" + str(payload.rollback_to_version) if payload.rollback_to_version else "confirmed_edit"
    with transaction(backend.connect) as db:
        db.execute("INSERT INTO workspace_strategy_previews VALUES (?,?,?,?,?,?,?,?,NULL)",
                   (identifier, user_id, payload.expected_version, snapshot["snapshot_id"], encode(config), encode(impact), expiry, reason))
    return {"preview_id": identifier, "expected_version": payload.expected_version, "snapshot_id": snapshot["snapshot_id"],
            "expires_at": datetime.fromtimestamp(expiry, timezone.utc).isoformat(), "config": config, "impact": impact, "can_confirm": True}


class StrategyConfirm(RequestId):
    preview_id: str
    expected_version: int = Field(ge=0)


@router.post("/strategy/confirm")
def confirm_strategy(payload: StrategyConfirm, user: Any = Depends(backend.current_user)) -> dict:
    user_id, now = int(user["id"]), int(time.time())
    request = payload.model_dump()
    with transaction(backend.connect) as db:
        prior = receipt(db, user_id, payload.request_id, "strategy_confirm", request)
        if prior:
            return prior
        active = active_strategy(user_id, db)
        if payload.expected_version != (active or {}).get("version", 0):
            raise HTTPException(409, "strategy_version_changed")
        preview = db.execute("SELECT * FROM workspace_strategy_previews WHERE id=? AND user_id=?", (payload.preview_id, user_id)).fetchone()
        if preview is None or preview["consumed_at"] is not None or preview["expires_at"] < now or preview["expected_version"] != payload.expected_version:
            raise HTTPException(409, "strategy_preview_expired_or_changed")
        config = validate_config(json.loads(preview["config_json"]))
        current = db.execute("SELECT id,broker_key FROM workspace_snapshots WHERE user_id=? AND currency=?", (user_id, config["reserve"]["currency"])).fetchone()
        if current is None or current["id"] != preview["snapshot_id"] or current["broker_key"] != broker_key(user):
            raise HTTPException(409, "strategy_snapshot_changed")
        version = payload.expected_version + 1
        db.execute("INSERT INTO workspace_strategy_versions VALUES (?,?,?,?,?,?,?,?)", (user_id, version, encode(config), preview["snapshot_id"], payload.expected_version, preview["reason"], payload.request_id, now))
        db.execute("UPDATE workspace_strategy_previews SET consumed_at=? WHERE id=?", (now, payload.preview_id))
        # The existing monitor reads these common rules; Volume also applies all
        # confirmed issuer/group/sector/currency limits through risk_data.
        horizon = "short" if config["horizon_months"] < 12 else "medium" if config["horizon_months"] < 60 else "long"
        try:
            from .volume_notifications import _preferences
        except ImportError:
            from volume_notifications import _preferences
        preferences, _, _ = _preferences(db, user_id)
        db.execute("""INSERT INTO analysis_profiles(user_id,risk_level,horizon,allowed_markets_json,max_position_percent,min_cash_percent,notify_critical,notify_briefs,configured,updated_at)
            VALUES (?,?,?,?,?,0,?,?,1,?) ON CONFLICT(user_id) DO UPDATE SET risk_level=excluded.risk_level,
            horizon=excluded.horizon,allowed_markets_json=excluded.allowed_markets_json,max_position_percent=excluded.max_position_percent,configured=1,updated_at=excluded.updated_at""",
            (user_id, config["risk_level"], horizon, encode(config["allowed_markets"]), float(config["limits"]["position_percent"]),
             int(preferences["enabled"] and preferences["critical_enabled"]), int(preferences["enabled"] and preferences["briefs_enabled"]), now))
        result = {"active": active_strategy(user_id, db), "confirmed": True}
        remember(db, user_id, payload.request_id, "strategy_confirm", request, result)
        event(db, user_id, "strategy_confirmed", preview["snapshot_id"], {"title": "Стратегия подтверждена", "details": {"version": version, "previous_version": payload.expected_version}, "source_ids": []}, payload.request_id)
    return result


class GoalWrite(RequestId):
    id: str | None = None
    title: str = Field(min_length=1, max_length=120)
    target: MoneyInput
    reserve: MoneyInput


@financial_context
def goal_data(user: Any) -> dict:
    result = []
    for goal in records(int(user["id"]), "goal"):
        snapshot = saved_snapshot(user, goal["target"]["currency"])
        total = decimal((snapshot or {}).get("capital", {}).get("total"))
        reserve, target = decimal(goal["reserve"]), decimal(goal["target"])
        current = max(ZERO, total - reserve) if total is not None else None
        result.append({**goal, "current": money(current, goal["target"]["currency"]),
                       "progress_percent": text_number(current / target * 100) if current is not None and target > 0 else None,
                       "as_of": (snapshot or {}).get("as_of"), "basis": "observed_capital_less_user_reserve_no_forecast"})
    return {"items": result}


@router.get("/goals")
def goals(user: Any = Depends(backend.current_user)) -> dict:
    return goal_data(user)


@router.post("/goals")
def save_goal(payload: GoalWrite, user: Any = Depends(backend.current_user)) -> dict:
    target, reserve = decimal(payload.target.amount), decimal(payload.reserve.amount)
    if target is None or target <= 0 or reserve is None or reserve < 0 or payload.target.currency != payload.reserve.currency:
        raise HTTPException(422, "goal_amounts_invalid")
    request, user_id = payload.model_dump(), int(user["id"])
    with transaction(backend.connect) as db:
        prior = receipt(db, user_id, payload.request_id, "goal", request)
        if prior:
            return prior
        identifier = require_id(payload.id) if payload.id else uuid.uuid4().hex
        result = {"id": identifier, "title": payload.title.strip(), "target": money(target, payload.target.currency), "reserve": money(reserve, payload.reserve.currency)}
        record(db, user_id, "goal", identifier, result)
        remember(db, user_id, payload.request_id, "goal", request, result)
    return result


@router.delete("/goals/{identifier}")
def delete_goal(identifier: str, user: Any = Depends(backend.current_user)) -> dict:
    with transaction(backend.connect) as db:
        db.execute("DELETE FROM workspace_records WHERE user_id=? AND kind='goal' AND id=?", (int(user["id"]), identifier))
    return {"id": identifier, "deleted": True}


class Shock(StrictModel):
    axis: Literal["instrument", "sector", "currency", "country", "all"]
    id: str = Field(max_length=160)
    percent: str = Field(max_length=40)


class Scenario(StrictModel):
    currency: Literal["RUB", "USD", "EUR"] = "RUB"
    shocks: list[Shock] = Field(min_length=1, max_length=100)


@router.post("/risks/scenario")
def scenario(payload: Scenario, user: Any = Depends(backend.current_user)) -> dict:
    return _scenario(payload, user)


@financial_context
def _scenario(payload: Scenario, user: Any) -> dict:
    snapshot = saved_snapshot(user, payload.currency)
    if snapshot is None:
        raise HTTPException(409, "workspace_refresh_required")
    assumptions, selectors = [], set()
    for shock in payload.shocks:
        value = decimal(shock.percent)
        if value is None or not -100 <= value <= 1000 or (shock.axis, shock.id) in selectors:
            raise HTTPException(422, "scenario_shock_invalid_or_duplicate")
        selectors.add((shock.axis, shock.id))
        assumptions.append({**shock.model_dump(), "percent": text_number(value)})
    output, unknown, total_change, matched_selectors = [], [], ZERO, set()
    for item in positions(snapshot):
        uid = item["instrument_uid"]
        value = decimal(item.get("value"))
        metadata = item.get("metadata") or {}
        identities = {
            "instrument": uid, "sector": metadata.get("sector"), "country": metadata.get("country_of_risk"),
            "currency": (item.get("value") or {}).get("currency")}
        matches = [shock for shock in assumptions if shock["axis"] == "all" or shock["id"] == identities.get(shock["axis"])]
        matched_selectors.update((shock["axis"], shock["id"]) for shock in matches)
        unknown_membership = any(shock["axis"] != "all" and identities.get(shock["axis"]) is None and
                                 not (item.get("instrument_type") == "cash" and shock["axis"] in {"sector", "country"}) for shock in assumptions)
        # Overlapping shocks have no implicit composition rule. Require the user
        # to choose an unambiguous scenario instead of silently adding losses.
        if len(matches) > 1:
            raise HTTPException(422, "scenario_overlapping_shocks")
        if unknown_membership:
            unknown.append(uid)
            continue
        if not matches:
            continue
        if value is None or item["value"]["currency"] != payload.currency or item.get("instrument_type") in {"futures", "option"}:
            unknown.append(uid)
            continue
        shock = decimal(matches[0]["percent"])
        change = value * shock / 100
        total_change += change
        output.append({"instrument_uid": uid, "before": money(value, payload.currency), "shock_percent": text_number(shock), "estimated_change": money(change, payload.currency)})
    if selectors - matched_selectors:
        raise HTTPException(422, "scenario_selector_not_in_verified_positions")
    baseline = decimal(snapshot.get("capital", {}).get("total"))
    return {"snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "assumptions": assumptions,
            "baseline": money(baseline, payload.currency), "estimated_change": money(total_change, payload.currency),
            "estimated_after": money(baseline + total_change, payload.currency) if baseline is not None and not unknown else None,
            "covered_positions": len(output), "total_positions": len(positions(snapshot)), "uncovered_instrument_uids": sorted(set(unknown)),
            "positions": output, "is_forecast": False, "basis": "user_shocks_linear_valuation_no_fx_or_derivative_model", "complete": not unknown}


class CheckCreate(RequestId):
    event_id: str | None = None
    instrument_uids: list[str] = Field(default_factory=list, max_length=2000)
    title: str = Field(min_length=1, max_length=160)


class CheckUpdate(StrictModel):
    step_id: str
    state: Literal["pending", "reviewed"]


@router.get("/risks/checks")
def get_checks(user: Any = Depends(backend.current_user)) -> dict:
    return {"items": records(int(user["id"]), "risk_check")}


@router.post("/risks/checks")
def create_check(payload: CheckCreate, user: Any = Depends(backend.current_user)) -> dict:
    user_id, request = int(user["id"]), payload.model_dump()
    snapshot = saved_snapshot(user)
    held = {p["instrument_uid"] for p in positions(snapshot)}
    if any(uid not in held for uid in payload.instrument_uids):
        raise HTTPException(422, "risk_check_instrument_not_in_snapshot")
    with transaction(backend.connect) as db:
        prior = receipt(db, user_id, payload.request_id, "risk_check", request)
        if prior:
            return prior
        if payload.event_id and not db.execute("SELECT 1 FROM workspace_events WHERE id=? AND user_id=?", (payload.event_id, user_id)).fetchone():
            raise HTTPException(404, "risk_event_not_found")
        identifier = uuid.uuid4().hex
        result = {"id": identifier, "title": payload.title, "state": "to_review", "created_at": now_iso(),
                  "snapshot_id": (snapshot or {}).get("snapshot_id"), "instrument_uids": payload.instrument_uids, "event_id": payload.event_id,
                  "steps": [{"id": key, "title": title, "state": "pending", "source_ids": []} for key, title in (
                      ("sources", "Проверить источники и дату данных"), ("limits", "Сопоставить риск с подтверждёнными лимитами"),
                      ("decision", "Записать решение после проверки"))], "execution_state": "not_executed"}
        record(db, user_id, "risk_check", identifier, result)
        remember(db, user_id, payload.request_id, "risk_check", request, result)
    return result


@router.patch("/risks/checks/{identifier}")
def update_check(identifier: str, payload: CheckUpdate, user: Any = Depends(backend.current_user)) -> dict:
    with transaction(backend.connect) as db:
        row = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='risk_check' AND id=?", (int(user["id"]), identifier)).fetchone()
        if not row:
            raise HTTPException(404, "risk_check_not_found")
        result = json.loads(row[0])
        selected = next((s for s in result["steps"] if s["id"] == payload.step_id), None)
        if selected is None:
            raise HTTPException(404, "risk_check_step_not_found")
        selected["state"] = payload.state
        result["state"] = "reviewed" if all(s["state"] == "reviewed" for s in result["steps"]) else "to_review"
        record(db, int(user["id"]), "risk_check", identifier, result)
    return result


@router.get("/risks/events")
def risk_events(limit: int = 100, user: Any = Depends(backend.current_user)) -> dict:
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND kind LIKE 'risk_%' ORDER BY created_at DESC,id LIMIT ?", (int(user["id"]), min(max(limit, 1), 500))).fetchall()
    return {"items": [json.loads(row[0]) for row in rows]}
