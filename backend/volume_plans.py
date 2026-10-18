"""Manual broker handoff and evidence-based reconciliation; never sends orders."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import Field

try:
    from . import app as backend, portfolio_details as details, volume_state as state, volume_jobs as jobs
    from .ai_budget import transaction
    from .investment_links import instrument_link
    from .volume_contract import HTTP_ERRORS, decimal, money, now_iso, source, text_number, timestamp, ZERO, financial_context
except ImportError:
    import app as backend
    import portfolio_details as details
    import volume_state as state
    import volume_jobs as jobs
    from ai_budget import transaction
    from investment_links import instrument_link
    from volume_contract import HTTP_ERRORS, decimal, money, now_iso, source, text_number, timestamp, ZERO, financial_context

router = APIRouter(prefix="/workspace/plans", tags=["Manual broker reconciliation"])


def initialize() -> None:
    with closing(backend.connect()) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_plan_operations (
            user_id INTEGER NOT NULL,account_id TEXT NOT NULL,operation_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,payload_json TEXT NOT NULL,
            PRIMARY KEY(user_id,account_id,operation_id))""")
        db.commit()


def _plan(db, user_id: int, identifier: str) -> dict:
    row = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='manual_plan' AND id=?", (user_id, identifier)).fetchone()
    if not row:
        raise HTTPException(404, "manual_plan_not_found")
    return json.loads(row[0])


def _current(plan: dict, user_id: int, db=None) -> dict:
    active = state.active_strategy(user_id, db)
    if plan["state"] != "done" and plan["strategy_version"] != (active or {}).get("version", 0):
        return {**plan, "state": "obsolete", "reason": "strategy_version_changed"}
    return plan


@router.get("", responses=HTTP_ERRORS)
def plans(user: Any = Depends(backend.current_user)) -> dict:
    return {"items": [_current(p, int(user["id"])) for p in state.records(int(user["id"]), "manual_plan")], "orders_api_enabled": False}


class PlanCreate(state.RequestId):
    title: str = Field(min_length=1, max_length=160)
    instrument_uid: str = Field(min_length=1, max_length=160)
    account_id: str = Field(min_length=1, max_length=160)
    side: Literal["buy", "sell"]
    quantity: str = Field(max_length=40)
    strategy_version: int = Field(ge=0)


@router.post("", responses=HTTP_ERRORS)
def create(payload: PlanCreate, user: Any = Depends(backend.current_user)) -> dict:
    return _create(payload, user)


@financial_context
def _create(payload: PlanCreate, user: Any) -> dict:
    user_id, request = int(user["id"]), payload.model_dump()
    with closing(backend.connect()) as db:
        previous = state.receipt(db, user_id, payload.request_id, "manual_plan", request)
    if previous:
        return previous
    amount = decimal(payload.quantity)
    if amount is None or amount <= 0:
        raise HTTPException(422, "manual_plan_quantity_invalid")
    snapshot = state.saved_snapshot(user)
    position = next((p for p in state.positions(snapshot) if p["account_id"] == payload.account_id and p["instrument_uid"] == payload.instrument_uid), None)
    if not position:
        raise HTTPException(409, "manual_plan_verified_position_required")
    lot = decimal(position["metadata"].get("lot"))
    if lot is None or lot <= 0 or amount % lot != 0:
        raise HTTPException(422, "manual_plan_lot_unverified_or_fractional")
    held = decimal(position["quantity"])
    blocked = decimal(position.get("blocked_quantity"))
    if payload.side == "sell" and (held is None or blocked is None or position["blocked"] or amount > held - blocked):
        raise HTTPException(409, "manual_plan_sell_quantity_not_verified")
    url = instrument_link(position["instrument_type"], position.get("ticker"), position["metadata"].get("isin"))
    if not url:
        raise HTTPException(409, "manual_plan_official_link_unavailable")
    with transaction(backend.connect) as db:
        previous = state.receipt(db, user_id, payload.request_id, "manual_plan", request)
        if previous:
            return previous
        active = state.active_strategy(user_id, db)
        if payload.strategy_version != (active or {}).get("version", 0):
            raise HTTPException(409, "strategy_version_changed")
        result = {"id": uuid.uuid4().hex, "title": payload.title, "instrument_uid": payload.instrument_uid,
                  "account_id": payload.account_id, "side": payload.side, "quantity": text_number(amount), "lot": text_number(lot),
                  "state": "calculated", "created_at": now_iso(), "opened_at": None, "broker_url": url,
                  "snapshot_id": snapshot["snapshot_id"], "as_of": snapshot["as_of"], "strategy_version": payload.strategy_version,
                  "baseline_quantity": position["quantity"], "source_ids": position["source_ids"],
                  "executed_quantity": "0", "candidate_operations": [], "bound_operations": [],
                  "execution_state": "not_executed", "access_check": "broker_confirmation_required",
                  "calculation": {"quantity": text_number(amount), "lot": text_number(lot), "fees": None,
                                  "estimated_value": _estimated_position_value(position, held, amount),
                                  "price_basis": "observed_position_value_per_unit_not_order_quote"}}
        state.record(db, user_id, "manual_plan", result["id"], result)
        state.remember(db, user_id, payload.request_id, "manual_plan", request, result)
    return result


@router.post("/{identifier}/open-broker", responses=HTTP_ERRORS)
def opened(identifier: str, payload: state.RequestId, user: Any = Depends(backend.current_user)) -> dict:
    request = {"id": identifier, **payload.model_dump()}
    with transaction(backend.connect) as db:
        previous = state.receipt(db, int(user["id"]), payload.request_id, "plan_open", request)
        if previous:
            return previous
        result = _current(_plan(db, int(user["id"]), identifier), int(user["id"]), db)
        if result["state"] in {"obsolete", "done"}:
            raise HTTPException(409, "manual_plan_not_openable")
        result.update(state="open_broker", opened_at=result.get("opened_at") or now_iso(), execution_state="not_confirmed")
        state.record(db, int(user["id"]), "manual_plan", identifier, result)
        state.remember(db, int(user["id"]), payload.request_id, "plan_open", request, result)
    return result


class Reconcile(state.RequestId):
    operation_ids: list[str] = Field(default_factory=list, max_length=1000)


@router.post("/{identifier}/reconcile", status_code=202, responses=HTTP_ERRORS)
def reconcile(identifier: str, payload: Reconcile, tasks: BackgroundTasks, user: Any = Depends(backend.current_user)) -> dict:
    def validate_plan(db, _job_id):
        plan = _current(_plan(db, int(user["id"]), identifier), int(user["id"]), db)
        if plan["state"] == "obsolete" or not plan.get("opened_at"):
            raise HTTPException(409, "manual_plan_handoff_required_or_obsolete")
    result = jobs.enqueue(int(user["id"]), payload.request_id, "reconcile",
                          {"plan_id": identifier, "operation_ids": sorted(set(payload.operation_ids))}, before_insert=validate_plan)
    tasks.add_task(jobs.run_job, result["job_id"])
    return result


def _candidate_operation(raw: dict, plan: dict, after: datetime, until: datetime) -> dict | None:
    item = details.normalize_operation(raw)
    kind = item["type"].removeprefix("OPERATION_TYPE_")
    allowed = {"BUY", "BUY_CARD", "DELIVERY_BUY"} if plan["side"] == "buy" else {"SELL", "DELIVERY_SELL"}
    quantity = decimal(item.get("quantity"))
    if kind not in allowed or item.get("instrumentUid") != plan["instrument_uid"] or item.get("state") != "OPERATION_STATE_EXECUTED":
        return None
    if not item["id"] or quantity is None or quantity <= 0:
        return None
    try:
        when = timestamp(item["date"])
    except ValueError:
        return None
    if not after <= when <= until:
        return None
    return {"id": item["id"], "date": item["date"], "quantity": text_number(quantity), "payment": money(item.get("payment")),
            "instrument_uid": item["instrumentUid"], "account_id": plan["account_id"], "side": plan["side"]}


def _candidate_rows(response: dict, plan: dict, after: datetime, until: datetime, candidates: dict) -> None:
    rows = response.get("items", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise HTTPException(502, "operations_response_invalid")
    for raw in rows:
        item = _candidate_operation(raw, plan, after, until)
        if item is None:
            continue
        if item["id"] in candidates and candidates[item["id"]] != item:
            raise HTTPException(502, "operation_conflicting_observations")
        candidates[item["id"]] = item


def _collect_candidates(reader, plan: dict, progress) -> tuple[dict, bool]:
    cursor, candidates, complete = "", {}, False
    after, until = timestamp(plan["opened_at"]), datetime.now(timezone.utc)
    for page in range(100):
        progress("reconciling", completed=page, total=None)
        response = reader.read("operations", {"accountId": plan["account_id"], "from": plan["opened_at"], "to": until.isoformat(),
                                               "cursor": cursor, "limit": 1000, "state": "OPERATION_STATE_EXECUTED", "withoutTrades": False})
        _candidate_rows(response, plan, after, until, candidates)
        if not response.get("hasNext"):
            complete = True
            break
        following = str(response.get("nextCursor") or "")
        if not following or following == cursor:
            raise HTTPException(502, "operations_cursor_invalid")
        cursor = following
    return candidates, complete


def _read_reconciliation(user: Any, plan: dict, progress) -> tuple:
    with details.BrokerReader(user) as reader:
        reader.account(plan["account_id"])
        account = reader.read("portfolio", {"accountId": plan["account_id"], "currency": "RUB"})
        observed_position = next((p for p in account.get("positions", []) if p.get("instrumentUid") == plan["instrument_uid"]), None)
        candidates, complete = _collect_candidates(reader, plan, progress)
    observed = now_iso()
    ref = source("GetOperationsByCursor/GetPortfolio", plan["account_id"], observed)
    for item in candidates.values():
        item["source_ids"] = [ref["id"]]
    return observed_position, candidates, complete, ref


def _bind_operations(db, user_id: int, identifier: str, account_id: str, selected: list, candidates: dict) -> list:
    for operation_id in selected:
        existing = db.execute("SELECT plan_id FROM workspace_plan_operations WHERE user_id=? AND account_id=? AND operation_id=?", (user_id, account_id, operation_id)).fetchone()
        if existing and existing[0] != identifier:
            raise HTTPException(409, "operation_already_bound_to_other_plan")
        db.execute("INSERT OR IGNORE INTO workspace_plan_operations VALUES (?,?,?,?,?)", (user_id, account_id, operation_id, identifier, state.encode(candidates[operation_id])))
    bound = db.execute("SELECT payload_json FROM workspace_plan_operations WHERE user_id=? AND plan_id=?", (user_id, identifier)).fetchall()
    linked = [json.loads(row[0]) for row in bound]
    # Source corrections retain association but replace the quantity/payment.
    for row in linked:
        if row["id"] in candidates:
            db.execute("UPDATE workspace_plan_operations SET payload_json=? WHERE user_id=? AND account_id=? AND operation_id=? AND plan_id=?",
                (state.encode(candidates[row["id"]]), user_id, account_id, row["id"], identifier))
    return [candidates.get(row["id"], row) for row in linked]


def _reconciliation_state(complete: bool, stale_links: list, amount, goal) -> str:
    if complete and not stale_links and amount >= goal:
        return "done"
    if amount > 0:
        return "partial"
    return "pending"


@financial_context
def reconcile_plan(user: Any, payload: dict, progress) -> dict:
    user_id, identifier = int(user["id"]), payload["plan_id"]
    with closing(backend.connect()) as db:
        plan = _current(_plan(db, user_id, identifier), user_id, db)
    if plan["state"] == "obsolete":
        raise HTTPException(409, "strategy_version_changed")
    if not plan.get("opened_at"):
        raise HTTPException(409, "manual_plan_handoff_required")
    progress("reconciling")
    observed_position, candidates, complete, ref = _read_reconciliation(user, plan, progress)
    selected = payload.get("operation_ids", [])
    if any(value not in candidates for value in selected):
        raise HTTPException(409, "selected_operation_not_verified")
    with transaction(backend.connect) as db:
        jobs.assert_current_in(db)
        current = _current(_plan(db, user_id, identifier), user_id, db)
        if current["state"] == "obsolete":
            raise HTTPException(409, "strategy_version_changed")
        linked = _bind_operations(db, user_id, identifier, plan["account_id"], selected, candidates)
        # A later reversal or missing row prevents a completed claim. Never keep
        # old execution proof when the current complete source contradicts it.
        stale_links = [row["id"] for row in linked if row["id"] not in candidates]
        amount = sum((decimal(row["quantity"]) for row in linked if row["id"] in candidates), ZERO)
        goal = decimal(plan["quantity"])
        new_state = _reconciliation_state(complete, stale_links, amount, goal)
        current.update(state=new_state, reconciled_at=ref["observed_at"], candidate_operations=list(candidates.values()), bound_operations=linked,
                       executed_quantity=text_number(amount), observed_quantity=text_number(decimal((observed_position or {}).get("quantity"))),
                       execution_state="observed_executed_operations" if amount > 0 else "not_confirmed", source_ids=[ref["id"]],
                       sources=[ref], reconciliation_complete=complete, stale_operation_links=stale_links,
                       association_basis="user_selected_broker_operations", automatic_order_execution=False)
        state.record(db, user_id, "manual_plan", identifier, current)
    return current


def _estimated_position_value(position, held, amount):
    if not position.get("value") or held is None or held <= 0:
        return None
    value = decimal(position["value"])
    if value is None:
        return None
    return money(value / held * amount, position["value"]["currency"])
