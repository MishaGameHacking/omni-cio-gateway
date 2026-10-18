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
    from .credit_evidence import Source
    from .volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, require_id, source, text_number, ZERO, financial_context
except ImportError:
    import app as backend
    import research_store
    from ai_budget import transaction
    from credit_evidence import Source
    from volume_contract import HTTP_ERRORS, decimal, digest, money, now_iso, require_id, source, text_number, ZERO, financial_context

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


@router.get("/strategy", responses=HTTP_ERRORS)
def get_strategy(user: Any = Depends(backend.current_user)) -> dict:
    return strategy_data(int(user["id"]))


def positions(snapshot: dict | None) -> list[dict]:
    return list((snapshot or {}).get("positions") or [])


def _identity(uid: str) -> dict | None:
    return research_store.latest_verified(backend.connect, "issuer_identity", uid, datetime.now(timezone.utc))


def _verified_identity(item: dict) -> dict:
    identity = item.get("verified_identity") or {}
    try:
        return identity if Source(**identity["source"]).valid(datetime.now(timezone.utc)) else {}
    except (KeyError, TypeError, ValueError):
        return {}


def _axis_identity(item: dict, axis: str) -> tuple:
    identity, metadata = _verified_identity(item), item.get("metadata") or {}
    uid, currency = str(item.get("instrument_uid") or ""), (item.get("value") or {}).get("currency")
    identities = {
        "position": (uid, item.get("title") or uid),
        "issuer": (identity.get("issuer_id"), identity.get("issuer_name") or identity.get("issuer_id")),
        "group": (identity.get("group_id"), identity.get("group_name") or identity.get("group_id")),
        "sector": (metadata.get("sector"), metadata.get("sector")), "currency": (currency, currency),
        "country": (metadata.get("country_of_risk"), metadata.get("country_of_risk_name") or metadata.get("country_of_risk")),
    }
    refs = list(item.get("source_ids", []))
    if axis in {"issuer", "group"}:
        refs.append(identity.get("source", {}).get("id"))
    if axis in {"sector", "country"}:
        refs.append((metadata.get("source") or {}).get("id"))
    return (*identities[axis], [ref for ref in refs if ref])


def _add_exposure(groups: dict, key: str, label: str, item: dict, value: Decimal, refs: list) -> None:
    bucket = groups.setdefault(key, {"id": key, "label": label, "amount": ZERO, "instrument_uids": [], "source_ids": []})
    bucket["amount"] += value
    if item["instrument_uid"] not in bucket["instrument_uids"]:
        bucket["instrument_uids"].append(item["instrument_uid"])
    for ref in refs:
        if ref not in bucket["source_ids"]:
            bucket["source_ids"].append(ref)


def _exposure_groups(rows: list, axis: str, currency: str) -> tuple:
    groups, unknown = {}, []
    known = not_applicable = 0
    for item in rows:
        if axis in {"issuer", "group", "sector", "country"} and item.get("instrument_type") == "cash":
            not_applicable += 1
            continue
        identifier, label, refs = _axis_identity(item, axis)
        value = decimal(item.get("value"))
        if not identifier or value is None or (item.get("value") or {}).get("currency") != currency:
            unknown.append(item["instrument_uid"])
            continue
        known += 1
        _add_exposure(groups, str(identifier), str(label), item, value, refs)
    return groups, unknown, known, not_applicable


def _concentration(bucket: dict, total: Decimal | None, limit: Decimal | None, currency: str) -> dict:
    share = bucket["amount"] / total * 100 if total is not None and total > 0 else None
    return {"id": bucket["id"], "label": bucket["label"], "instrument_uids": bucket["instrument_uids"], "source_ids": bucket["source_ids"],
            "value": money(bucket["amount"], currency), "share_percent": text_number(share), "limit_percent": text_number(limit),
            "breached": share > limit if share is not None and limit is not None else None}


def _coverage_state(complete: bool, known: int) -> str:
    if complete:
        return "available"
    return "partial" if known else "unavailable"


def _observation_age(at: str | None) -> int | None:
    if not at:
        return None
    return max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(at)).total_seconds()))


def _exposure_axis(snapshot: dict | None, axis: str, label: str, limits: dict) -> tuple:
    rows = positions(snapshot)
    currency = (snapshot or {}).get("currency", "RUB")
    groups, unknown, known, not_applicable = _exposure_groups(rows, axis, currency)
    total = decimal(((snapshot or {}).get("capital") or {}).get("total"))
    output = [_concentration(bucket, total, decimal(limits.get(axis + "_percent")), currency) for bucket in groups.values()]
    incomplete = (snapshot or {}).get("position_coverage", {}).get("incomplete_reasons", [])
    complete = bool(snapshot) and not unknown and not incomplete
    as_of = (snapshot or {}).get("as_of")
    result = {"id": axis, "label": label, "complete": complete, "unknown_count": len(unknown), "items": output}
    coverage = {"direction": axis, "state": _coverage_state(complete, known), "known_positions": known, "total_positions": len(rows),
                "missing_instrument_uids": sorted(set(unknown)), "not_applicable_positions": not_applicable, "as_of": as_of,
                "age_seconds": _observation_age(as_of), "incomplete_reasons": incomplete,
                "basis": "operator_reviewed_identity" if axis in {"issuer", "group"} else "broker_snapshot_no_fx_conversion"}
    return result, coverage


@financial_context
def exposure_data(snapshot: dict | None, config: dict | None = None) -> dict:
    axes, coverage, concentrations = [], [], []
    for axis, label in AXES:
        observation, completeness = _exposure_axis(snapshot, axis, label, (config or {}).get("limits", {}))
        axes.append(observation)
        coverage.append(completeness)
        concentrations.extend({"direction": axis, **row} for row in observation["items"])
    return {"axes": axes, "coverage": coverage, "concentrations": concentrations}


def _market_observation(position: dict, direction: str, snapshot: dict | None, market_rows: dict) -> dict:
    current = None
    if direction == "ratings":
        current = (snapshot or {}).get("rating_observations", {}).get(position["instrument_uid"])
    return current or market_rows.get(position["instrument_uid"], {}).get(direction, {})


def _fresh_market_observation(item: dict, direction: str) -> bool:
    refs = item.get("sources", [])
    if direction == "ratings":
        # Expired history remains inspectable independently of current proof.
        current_ids = {row.get("source", {}).get("id") for row in item.get("data", {}).get("items", [])}
        refs = [ref for ref in refs if ref.get("id") in current_ids]
    if item.get("state") != "available" or not refs:
        return False
    try:
        return all(datetime.fromisoformat(ref["expires_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc) for ref in refs)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _market_coverage(snapshot: dict | None, direction: str, market_rows: dict) -> dict:
    scoped = [p for p in positions(snapshot) if p.get("instrument_type") != "cash"]
    known, missing, dates = 0, [], []
    for position in scoped:
        item = _market_observation(position, direction, snapshot, market_rows)
        if not _fresh_market_observation(item, direction):
            missing.append(position["instrument_uid"])
            continue
        known += 1
        if item.get("as_of"):
            dates.append(item["as_of"])
    at = min(dates) if dates else None
    complete = known == len(scoped) and bool(snapshot) and not (snapshot or {}).get("position_coverage", {}).get("incomplete_reasons")
    return {"direction": direction, "state": _coverage_state(complete, known), "known_positions": known, "total_positions": len(scoped),
            "not_applicable_positions": len(positions(snapshot)) - len(scoped), "missing_instrument_uids": sorted(set(missing)),
            "as_of": at, "age_seconds": _observation_age(at), "basis": "verified_dossier_observations_with_expiry_not_a_safety_guarantee"}


def risk_data(user: Any, currency: str = "RUB", *, config: dict | None = None, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if snapshot is not None else saved_snapshot(user, currency)
    active = active_strategy(int(user["id"]))
    values = exposure_data(snapshot, config if config is not None else (active or {}).get("config"))
    market_rows = {row["instrument_uid"]: row for row in records(int(user["id"]), "instrument_market", limit=10000) if row.get("broker_key") == broker_key(user)}
    values["coverage"].extend(_market_coverage(snapshot, direction, market_rows) for direction in ("trading", "liquidity", "ratings"))
    with closing(backend.connect()) as db:
        history = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND kind LIKE 'risk_%' ORDER BY created_at DESC,id LIMIT 100", (int(user["id"]),)).fetchall()
    return {"snapshot_id": (snapshot or {}).get("snapshot_id"), "as_of": (snapshot or {}).get("as_of"),
            "coverage": values["coverage"], "concentrations": values["concentrations"],
            "events": [json.loads(row[0]) for row in history], "strategy_version": (active or {}).get("version", 0),
            "coverage_is_not_probability_of_loss": True}


@router.get("/risks", responses=HTTP_ERRORS)
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


@router.post("/strategy/preview", responses=HTTP_ERRORS)
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


def _legacy_horizon(months: int) -> str:
    if months < 12:
        return "short"
    if months < 60:
        return "medium"
    return "long"


@router.post("/strategy/confirm", responses=HTTP_ERRORS)
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
        horizon = _legacy_horizon(config["horizon_months"])
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


@router.get("/goals", responses=HTTP_ERRORS)
def goals(user: Any = Depends(backend.current_user)) -> dict:
    return goal_data(user)


@router.post("/goals", responses=HTTP_ERRORS)
def save_goal(payload: GoalWrite, user: Any = Depends(backend.current_user)) -> dict:
    target, reserve = decimal(payload.target.amount), decimal(payload.reserve.amount)
    if target is None or target <= 0 or reserve is None or reserve < 0 or payload.target.currency != payload.reserve.currency:
        raise HTTPException(422, "goal_amounts_invalid")
    title = payload.title.strip()
    if not title:
        raise HTTPException(422, "goal_title_empty")
    request, user_id = payload.model_dump(), int(user["id"])
    with transaction(backend.connect) as db:
        prior = receipt(db, user_id, payload.request_id, "goal", request)
        if prior:
            return prior
        identifier = require_id(payload.id) if payload.id else uuid.uuid4().hex
        if payload.id and not db.execute(
            "SELECT 1 FROM workspace_records WHERE user_id=? AND kind='goal' AND id=?",
            (user_id, identifier),
        ).fetchone():
            raise HTTPException(404, "goal_not_found")
        result = {"id": identifier, "title": title, "target": money(target, payload.target.currency), "reserve": money(reserve, payload.reserve.currency)}
        record(db, user_id, "goal", identifier, result)
        remember(db, user_id, payload.request_id, "goal", request, result)
    return result


@router.delete("/goals/{identifier}", responses=HTTP_ERRORS)
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


@router.post("/risks/scenario", responses=HTTP_ERRORS)
def scenario(payload: Scenario, user: Any = Depends(backend.current_user)) -> dict:
    return _scenario(payload, user)


def _scenario_assumptions(shocks: list[Shock]) -> tuple[list, set]:
    assumptions, selectors = [], set()
    for shock in shocks:
        value = decimal(shock.percent)
        if value is None or not -100 <= value <= 1000 or (shock.axis, shock.id) in selectors:
            raise HTTPException(422, "scenario_shock_invalid_or_duplicate")
        selectors.add((shock.axis, shock.id))
        assumptions.append({**shock.model_dump(), "percent": text_number(value)})
    return assumptions, selectors


def _scenario_position(item: dict, assumptions: list, currency: str) -> tuple:
    uid = item["instrument_uid"]
    value = decimal(item.get("value"))
    metadata = item.get("metadata") or {}
    identities = {"instrument": uid, "sector": metadata.get("sector"), "country": metadata.get("country_of_risk"),
                  "currency": (item.get("value") or {}).get("currency")}
    matches = [shock for shock in assumptions if shock["axis"] == "all" or shock["id"] == identities.get(shock["axis"])]
    matched = {(shock["axis"], shock["id"]) for shock in matches}
    unknown_membership = any(shock["axis"] != "all" and identities.get(shock["axis"]) is None and
                             not (item.get("instrument_type") == "cash" and shock["axis"] in {"sector", "country"}) for shock in assumptions)
    # A scenario has no implicit rule for composing overlapping shocks.
    if len(matches) > 1:
        raise HTTPException(422, "scenario_overlapping_shocks")
    if unknown_membership:
        return None, matched, True
    if not matches:
        return None, matched, False
    if value is None or item["value"]["currency"] != currency or item.get("instrument_type") in {"futures", "option"}:
        return None, matched, True
    shock = decimal(matches[0]["percent"])
    result = {"instrument_uid": uid, "account_id": item["account_id"], "before": money(value, currency),
              "shock_percent": text_number(shock), "estimated_change": money(value * shock / 100, currency)}
    return result, matched, False


@financial_context
def _scenario(payload: Scenario, user: Any, snapshot: dict | None = None) -> dict:
    snapshot = snapshot if snapshot is not None else saved_snapshot(user, payload.currency)
    if snapshot is None:
        raise HTTPException(409, "workspace_refresh_required")
    assumptions, selectors = _scenario_assumptions(payload.shocks)
    output, unknown, total_change, matched_selectors = [], [], ZERO, set()
    for item in positions(snapshot):
        result, matched, uncovered = _scenario_position(item, assumptions, payload.currency)
        matched_selectors.update(matched)
        if uncovered:
            unknown.append(item["instrument_uid"])
        if result is not None:
            total_change += decimal(result["estimated_change"])
            output.append(result)
    if selectors - matched_selectors:
        raise HTTPException(422, "scenario_selector_not_in_verified_positions")
    baseline = decimal(snapshot.get("capital", {}).get("total"))
    incomplete = list(snapshot.get("position_coverage", {}).get("incomplete_reasons", []))
    if baseline is None:
        incomplete.append("capital_valuation_unavailable")
    complete = not unknown and not incomplete
    return {"snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "assumptions": assumptions,
            "baseline": money(baseline, payload.currency), "estimated_change": money(total_change, payload.currency),
            "estimated_after": money(baseline + total_change, payload.currency) if baseline is not None and complete else None,
            "covered_positions": len(output), "total_positions": len(positions(snapshot)), "uncovered_instrument_uids": sorted(set(unknown)),
            "positions": output, "is_forecast": False, "basis": "user_shocks_linear_valuation_no_fx_or_derivative_model",
            "complete": complete, "incomplete_reasons": incomplete, "estimated_change_basis": "covered_positions_only"}


class ScenarioVariant(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    shocks: list[Shock] = Field(min_length=1, max_length=100)


class ScenarioComparison(StrictModel):
    currency: Literal["RUB", "USD", "EUR"] = "RUB"
    scenarios: list[ScenarioVariant] = Field(min_length=2, max_length=4)


@router.post("/risks/scenarios/compare", responses=HTTP_ERRORS)
def compare_scenarios(payload: ScenarioComparison, user: Any = Depends(backend.current_user)) -> dict:
    if len({row.id for row in payload.scenarios}) != len(payload.scenarios):
        raise HTTPException(422, "scenario_comparison_duplicate_id")
    snapshot = saved_snapshot(user, payload.currency)
    if snapshot is None:
        raise HTTPException(409, "workspace_refresh_required")
    results = [{"id": row.id, "title": row.title,
                "result": _scenario(Scenario(currency=payload.currency, shocks=row.shocks), user, snapshot)} for row in payload.scenarios]
    return {"snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "currency": payload.currency,
            "scenarios": results, "comparison_basis": "same_observed_snapshot_same_currency", "assumptions_are_user_defined": True}


class CheckCreate(RequestId):
    event_id: str | None = None
    instrument_uids: list[str] = Field(default_factory=list, max_length=2000)
    title: str = Field(min_length=1, max_length=160)


class CheckUpdate(StrictModel):
    step_id: str
    state: Literal["pending", "reviewed"]


@router.get("/risks/checks", responses=HTTP_ERRORS)
def get_checks(user: Any = Depends(backend.current_user)) -> dict:
    return {"items": records(int(user["id"]), "risk_check")}


@router.post("/risks/checks", responses=HTTP_ERRORS)
def create_check(payload: CheckCreate, user: Any = Depends(backend.current_user)) -> dict:
    user_id, request = int(user["id"]), payload.model_dump()
    snapshot = saved_snapshot(user)
    with transaction(backend.connect) as db:
        prior = receipt(db, user_id, payload.request_id, "risk_check", request)
        if prior:
            return prior
        event = None
        if payload.event_id:
            row = db.execute("SELECT payload_json FROM workspace_events WHERE id=? AND user_id=? AND kind LIKE 'risk_%'", (payload.event_id, user_id)).fetchone()
            if row is None:
                raise HTTPException(404, "risk_event_not_found")
            event = json.loads(row[0])
        if snapshot is None and event is None:
            raise HTTPException(409, "risk_check_basis_unavailable")
        selected_uids, selected_positions, checked_sources, linked_source_ids = _risk_check_scope(snapshot, event, payload)
        strategy = db.execute("SELECT version,config_json,confirmed_at FROM workspace_strategy_versions WHERE user_id=? ORDER BY version DESC LIMIT 1", (user_id,)).fetchone()
        identifier = uuid.uuid4().hex
        result = {"id": identifier, "title": payload.title, "state": "to_review", "created_at": now_iso(),
                  "snapshot_id": (snapshot or {}).get("snapshot_id"), "instrument_uids": selected_uids, "event_id": payload.event_id,
                  "basis": {"snapshot_id": (snapshot or {}).get("snapshot_id"), "as_of": (snapshot or {}).get("as_of"),
                            "positions": selected_positions, "event": event, "strategy_version": strategy[0] if strategy else 0,
                            "confirmed_strategy": {"version": strategy[0], "config": json.loads(strategy[1]),
                                "confirmed_at": datetime.fromtimestamp(strategy[2], timezone.utc).isoformat()} if strategy else None,
                            "closed_instrument_uids": sorted(set(selected_uids) - {p["instrument_uid"] for p in selected_positions})},
                  "sources": checked_sources,
                  "steps": [{"id": key, "title": title, "state": "pending", "source_ids": linked_source_ids} for key, title in (
                      ("sources", "Проверить источники и дату данных"), ("limits", "Сопоставить риск с подтверждёнными лимитами"),
                      ("decision", "Записать решение после проверки"))], "execution_state": "not_executed"}
        record(db, user_id, "risk_check", identifier, result)
        remember(db, user_id, payload.request_id, "risk_check", request, result)
    return result


@router.patch("/risks/checks/{identifier}", responses=HTTP_ERRORS)
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


@router.get("/risks/events", responses=HTTP_ERRORS)
def risk_events(limit: int = 100, user: Any = Depends(backend.current_user)) -> dict:
    with closing(backend.connect()) as db:
        rows = db.execute("SELECT payload_json FROM workspace_events WHERE user_id=? AND kind LIKE 'risk_%' ORDER BY created_at DESC,id LIMIT ?", (int(user["id"]), min(max(limit, 1), 500))).fetchall()
    return {"items": [json.loads(row[0]) for row in rows]}


def _risk_check_scope(snapshot, event, payload):
    owned = {p["instrument_uid"] for p in positions(snapshot)} | set((event or {}).get("instrument_uids", []))
    selected_uids = sorted(set(payload.instrument_uids) or set((event or {}).get("instrument_uids", [])) or owned)
    if any(uid not in owned for uid in selected_uids):
        raise HTTPException(422, "risk_check_instrument_not_in_snapshot_or_owned_event")
    selected_positions = [{key: p.get(key) for key in ("instrument_uid", "account_id", "title", "quantity", "value", "source_ids")}
                          for p in positions(snapshot) if not selected_uids or p["instrument_uid"] in selected_uids]
    source_ids = set((event or {}).get("source_ids", [])) | {ref for p in selected_positions for ref in p.get("source_ids", [])}
    all_sources = (snapshot or {}).get("sources", []) + (event or {}).get("sources", [])
    checked_sources = list({ref["id"]: ref for ref in all_sources if ref.get("id") in source_ids}.values())
    linked_source_ids = sorted({ref["id"] for ref in checked_sources})
    return selected_uids, selected_positions, checked_sources, linked_source_ids
