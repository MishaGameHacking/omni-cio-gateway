"""Idempotent workspace jobs with durable checkpoints and honest paid states."""
from __future__ import annotations

from contextlib import closing, nullcontext
from contextvars import ContextVar
from datetime import date, datetime, timezone
import json
import time
import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import Field

try:
    from . import app as backend
    from .ai_budget import transaction
    from .schema_migrations import execute_schema
    from .ai_jobs import AnalysisQueue
    from .monitoring_access import monitoring_connection, assert_monitoring_access_in
    from .volume_contract import HTTP_ERRORS, digest, error_code, date_range
    from .volume_state import RequestId, StrictModel, encode
except ImportError:
    import app as backend
    from ai_budget import transaction
    from schema_migrations import execute_schema
    from ai_jobs import AnalysisQueue
    from monitoring_access import monitoring_connection, assert_monitoring_access_in
    from volume_contract import HTTP_ERRORS, digest, error_code, date_range
    from volume_state import RequestId, StrictModel, encode

router = APIRouter(prefix="/workspace", tags=["Durable workspace jobs"])
CURRENT_WORKSPACE_JOB: ContextVar[tuple[str, str, int] | None] = ContextVar("volume_current_job", default=None)
LEASE = 900
TERMINAL = {"completed", "cancelled", "failed", "uncertain"}
OWNED_JOB_SQL = "SELECT * FROM workspace_jobs WHERE id=? AND user_id=?"


class JobStopped(RuntimeError):
    code = "workspace_job_cancelled_or_lease_lost"


def initialize() -> None:
    # Keep request receipts and their job schema in the same startup transaction.
    # Initialization must not expire leases, replay work or clear checkpoints.
    with transaction(backend.connect) as db:
        execute_schema(db, """
            CREATE TABLE IF NOT EXISTS workspace_jobs (
                id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,request_id TEXT NOT NULL,
                kind TEXT NOT NULL,payload_json TEXT NOT NULL,payload_hash TEXT NOT NULL,
                state TEXT NOT NULL,stage TEXT NOT NULL,checkpoint_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT,error_code TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0,
                paid_started INTEGER NOT NULL DEFAULT 0,owner TEXT,expires_at INTEGER,
                created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspace_job_requests (
                user_id INTEGER NOT NULL,request_id TEXT NOT NULL,job_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,PRIMARY KEY(user_id,request_id));
            CREATE INDEX IF NOT EXISTS workspace_jobs_due ON workspace_jobs(state,created_at);
            CREATE INDEX IF NOT EXISTS workspace_jobs_user ON workspace_jobs(user_id,created_at);
        """)


def _iso(value: int | None) -> str | None:
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def _expire(db, now: int) -> None:
    # Collection may resume from an acknowledged checkpoint. Once dispatch could
    # have occurred, restart never repeats the paid request.
    db.execute("""UPDATE workspace_jobs SET state=CASE WHEN paid_started=1 THEN 'uncertain' WHEN cancel_requested=1 THEN 'cancelled' ELSE 'queued' END,
        stage=CASE WHEN paid_started=1 THEN 'reconciliation_required' ELSE stage END,
        error_code=CASE WHEN paid_started=1 THEN 'workspace_paid_outcome_unknown' ELSE NULL END,
        owner=NULL,expires_at=NULL,updated_at=? WHERE state='running' AND expires_at<=?""", (now, now))


def _analysis_job_override(value: dict, row, db) -> None:
    result = value["result"]
    if not result or not result.get("analysis_job_id") or db is None:
        return
    child = db.execute("SELECT * FROM ai_work_jobs WHERE id=? AND user_id=?", (result["analysis_job_id"], row["user_id"])).fetchone()
    if child is None:
        return
    cancelled = child["error_code"] == "analysis_cancelled"
    cancelling = "cancel_requested_at" in child.keys() and child["cancel_requested_at"] is not None and child["status"] == "running"
    child_state = child["status"]
    if cancelled:
        child_state = "cancelled"
    elif cancelling:
        child_state = "cancel_requested"
    value.update(state=child_state, stage="done" if child["status"] == "completed" else "analysis_monitor",
                 error_code=child["error_code"], cancel_requested=cancelled or cancelling,
                 updated_at=_iso(child["updated_at"]), can_retry=False)
    if child["result_json"]:
        value["result"] = {**result, **json.loads(child["result_json"])}


def _job(row, db=None) -> dict:
    result = json.loads(row["result_json"]) if row["result_json"] else None
    value = {"job_id": row["id"], "request_id": row["request_id"], "kind": row["kind"],
             "state": "cancel_requested" if row["cancel_requested"] and row["state"] == "running" else row["state"],
             "stage": row["stage"], "created_at": _iso(row["created_at"]), "updated_at": _iso(row["updated_at"]),
             "result": result, "error_code": row["error_code"], "cancel_requested": bool(row["cancel_requested"]),
             "can_retry": row["state"] in {"failed", "cancelled"} and not row["paid_started"]}
    progress = json.loads(row["checkpoint_json"]).get("_progress")
    if progress:
        value["progress"] = progress
    if row["kind"] == "analysis":
        _analysis_job_override(value, row, db)
    return value


def get_job(user_id: int, identifier: str) -> dict:
    with transaction(backend.connect) as db:
        _expire(db, int(time.time()))
        row = db.execute(OWNED_JOB_SQL, (identifier, user_id)).fetchone()
        if row is None:
            raise HTTPException(404, "workspace_job_not_found")
        return _job(row, db)


def user_jobs(user_id: int, limit: int = 20) -> list[dict]:
    with transaction(backend.connect) as db:
        _expire(db, int(time.time()))
        rows = db.execute("SELECT * FROM workspace_jobs WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT ?", (user_id, limit)).fetchall()
        return [_job(row, db) for row in rows]


def enqueue(user_id: int, request_id: str, kind: str, payload: dict, *, before_insert=None, checkpoint: dict | None = None) -> dict:
    now = int(time.time())
    hashed = digest({"kind": kind, "payload": payload})
    with transaction(backend.connect) as db:
        _expire(db, now)
        prior = db.execute("SELECT job_id,payload_hash FROM workspace_job_requests WHERE user_id=? AND request_id=?", (user_id, request_id)).fetchone()
        if prior:
            if prior["payload_hash"] != hashed:
                raise HTTPException(409, "request_id_payload_conflict")
            return _job(db.execute("SELECT * FROM workspace_jobs WHERE id=?", (prior["job_id"],)).fetchone(), db)
        if db.execute("SELECT COUNT(*) FROM workspace_jobs WHERE user_id=? AND state IN ('queued','running')", (user_id,)).fetchone()[0] >= 5:
            raise HTTPException(429, "workspace_too_many_pending_jobs")
        identifier = uuid.uuid4().hex
        if before_insert:
            before_insert(db, identifier)
        db.execute("""INSERT INTO workspace_jobs
            (id,user_id,request_id,kind,payload_json,payload_hash,state,stage,checkpoint_json,created_at,updated_at)
            VALUES (?,?,?,?,?,?,'queued','queued',?,?,?)""",
            (identifier, user_id, request_id, kind, encode(payload), hashed, encode(checkpoint or {}), now, now))
        db.execute("INSERT INTO workspace_job_requests VALUES (?,?,?,?)", (user_id, request_id, identifier, hashed))
        return _job(db.execute("SELECT * FROM workspace_jobs WHERE id=?", (identifier,)).fetchone(), db)


def assert_current_in(db, *, allow_cancel: bool = False) -> None:
    context = CURRENT_WORKSPACE_JOB.get()
    if context is None:
        return
    identifier, owner, user_id = context
    row = db.execute("SELECT state,cancel_requested,expires_at FROM workspace_jobs WHERE id=? AND owner=? AND user_id=?", (identifier, owner, user_id)).fetchone()
    if row is None or row["state"] != "running" or row["expires_at"] <= int(time.time()) or (row["cancel_requested"] and not allow_cancel):
        raise JobStopped()
    assert_monitoring_access_in(db)


def progress(stage: str, checkpoint: dict | None = None, *, completed: int | None = None, total: int | None = None) -> None:
    context = CURRENT_WORKSPACE_JOB.get()
    if not context:
        return
    if checkpoint is not None and completed is not None:
        checkpoint["_progress"] = {"completed": completed, "total": total}
    with transaction(backend.connect) as db:
        assert_current_in(db)
        if checkpoint is not None:
            db.execute("UPDATE workspace_jobs SET stage=?,checkpoint_json=?,updated_at=?,expires_at=? WHERE id=? AND owner=?",
                       (stage, encode(checkpoint), int(time.time()), int(time.time()) + LEASE, context[0], context[1]))
        else:
            db.execute("UPDATE workspace_jobs SET stage=?,updated_at=?,expires_at=? WHERE id=? AND owner=?",
                       (stage, int(time.time()), int(time.time()) + LEASE, context[0], context[1]))


def before_model_send() -> None:
    with transaction(backend.connect) as db:
        assert_current_in(db)
        context = CURRENT_WORKSPACE_JOB.get()
        if context:
            db.execute("UPDATE workspace_jobs SET paid_started=1,stage='model_running',updated_at=? WHERE id=? AND owner=?", (int(time.time()), context[0], context[1]))


def after_model_response() -> None:
    progress("validating")


def _claim(identifier: str | None = None) -> dict | None:
    now = int(time.time())
    with transaction(backend.connect) as db:
        _expire(db, now)
        query = """SELECT * FROM workspace_jobs q WHERE q.state='queued'
            AND NOT EXISTS(SELECT 1 FROM workspace_jobs busy WHERE busy.user_id=q.user_id AND busy.state='running')""" + (" AND q.id=?" if identifier else "") + """ ORDER BY CASE WHEN q.kind='reconcile' THEN 0 ELSE MAX(1,
            CASE WHEN q.kind='events' THEN 1
                 WHEN q.kind='chat' THEN 2
                 WHEN q.kind='refresh' AND q.request_id NOT LIKE 'auto.full.%' THEN 2 ELSE 3 END
            - CAST(MAX(0, ? - q.created_at) / 300 AS INTEGER)) END, q.created_at,q.id LIMIT 1"""
        # Each five minutes of waiting promotes one level. Even catalogue/full
        # work eventually reaches the front; existing per-user leases still win.
        row = db.execute(query, ((identifier,) if identifier else ()) + (now,)).fetchone()
        if not row:
            return None
        owner = uuid.uuid4().hex
        # One collecting/model worker per user; independent users remain eligible.
        if db.execute("SELECT 1 FROM workspace_jobs WHERE user_id=? AND state='running'", (row["user_id"],)).fetchone():
            return None
        db.execute("UPDATE workspace_jobs SET state='running',owner=?,expires_at=?,updated_at=? WHERE id=?", (owner, now + LEASE, now, row["id"]))
        return {**dict(row), "owner": owner}


def _enqueue_analysis(job: dict) -> dict:
    progress("analysis_queued")
    with transaction(backend.connect) as db:
        assert_current_in(db)
        result = {"analysis_job_id": AnalysisQueue(backend.connect).enqueue_in(db, job["user_id"])["job_id"]}
        try:
            from .background_dispatch import mark_manual_in
        except ImportError:
            from background_dispatch import mark_manual_in
        mark_manual_in(db, job["user_id"], result["analysis_job_id"])
        db.execute("UPDATE workspace_jobs SET result_json=? WHERE id=? AND owner=?", (encode(result), job["id"], job["owner"]))
    return result


def _perform_job(job: dict, user: Any, payload: dict, checkpoint: dict) -> dict:
    try:
        from .volume_workspace import collect
        from .volume_chat import run_message
        from .volume_plans import reconcile_plan
    except ImportError:
        from volume_workspace import collect
        from volume_chat import run_message
        from volume_plans import reconcile_plan
    if job["kind"] == "events":
        try:
            from .event_monitor import collect_events
        except ImportError:
            from event_monitor import collect_events
        return collect_events(user, payload, checkpoint, progress)
    if job["kind"] == "refresh":
        if job["request_id"].startswith("auto.full."):
            try:
                from .background_dispatch import automatic_collection_gate
            except ImportError:
                from background_dispatch import automatic_collection_gate
            waiting = automatic_collection_gate(user, payload, checkpoint)
            if waiting is not None:
                return waiting
        return collect(user, payload, checkpoint, progress)
    if job["kind"] == "chat":
        return run_message(user, job, payload)
    if job["kind"] == "analysis":
        return _enqueue_analysis(job)
    if job["kind"] == "reconcile":
        return reconcile_plan(user, payload, progress)
    raise HTTPException(422, "workspace_job_kind_invalid")


def _failure_state(row, error: Exception, pending_money) -> tuple[str, str]:
    if row["paid_started"] and pending_money:
        return "uncertain", "workspace_paid_outcome_unknown"
    if row["cancel_requested"] or isinstance(error, JobStopped):
        return "cancelled", "workspace_job_cancelled"
    return "failed", error_code(error)


def _fail_job(job: dict, error: Exception) -> None:
    # Paid outcome may be settled even when model JSON is invalid. The job is
    # still not replayable; a new intentional message is a new operation.
    with transaction(backend.connect) as db:
        row = db.execute("SELECT * FROM workspace_jobs WHERE id=? AND owner=? AND state='running'", (job["id"], job["owner"])).fetchone()
        if row is None:
            return
        pending_money = db.execute("SELECT 1 FROM ai_money_reservations WHERE user_id=? AND state IN ('reserved','uncertain') AND created_at>=?", (job["user_id"], row["created_at"])).fetchone()
        status, code = _failure_state(row, error, pending_money)
        db.execute("UPDATE workspace_jobs SET state=?,error_code=?,updated_at=? WHERE id=? AND owner=?", (status, code, int(time.time()), job["id"], job["owner"]))


def _public_collection(user, payload, checkpoint):
    try:
        from .osint_worker import collect
    except ImportError:
        from osint_worker import collect
    return collect(user, payload, checkpoint, progress)


def run_job(identifier: str | None = None) -> None:
    job = _claim(identifier)
    if job is None:
        return
    token = CURRENT_WORKSPACE_JOB.set((job["id"], job["owner"], job["user_id"]))
    try:
        with closing(backend.connect()) as db:
            user = db.execute("SELECT * FROM users WHERE id=?", (job["user_id"],)).fetchone()
        if user is None or (job["kind"] != "osint" and not user["tinvest_token_encrypted"]):
            raise HTTPException(409, "tinvest_not_connected")
        payload, checkpoint = json.loads(job["payload_json"]), json.loads(job["checkpoint_json"])
        access = nullcontext() if job["kind"] == "osint" else monitoring_connection(job["user_id"], user["tinvest_token_encrypted"])
        with access:
            result = (_public_collection(user, payload, checkpoint) if job["kind"] == "osint"
                      else _perform_job(job, user, payload, checkpoint))
            with transaction(backend.connect) as db:
                assert_current_in(db)
                db.execute("UPDATE workspace_jobs SET state='completed',stage='done',result_json=?,checkpoint_json='{}',updated_at=? WHERE id=? AND owner=?", (encode(result), int(time.time()), job["id"], job["owner"]))
    except Exception as error:
        _fail_job(job, error)
    finally:
        CURRENT_WORKSPACE_JOB.reset(token)


def drain(limit: int = 5) -> None:
    # A restart can leave only expired running rows. Recover those leases before
    # checking for queued work, even when no client is polling the workspace.
    with transaction(backend.connect) as db:
        _expire(db, int(time.time()))
    for _ in range(limit):
        with closing(backend.connect()) as db:
            row = db.execute("SELECT id FROM workspace_jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1").fetchone()
        if row is None:
            return
        run_job()


class Refresh(RequestId):
    currency: Literal["RUB", "USD", "EUR"] = "RUB"
    start: date | None = None
    end: date | None = None


class AnalysisRequest(RequestId):
    reason: Literal["manual"] = "manual"


@router.post("/refresh", status_code=202, responses=HTTP_ERRORS)
def refresh(payload: Refresh, tasks: BackgroundTasks, user: Any = Depends(backend.current_user)) -> dict:
    date_range(payload.start, payload.end)
    if not user["tinvest_token_encrypted"]:
        raise HTTPException(409, "tinvest_not_connected")
    result = enqueue(int(user["id"]), payload.request_id, "refresh", payload.model_dump(mode="json", exclude={"request_id"}))
    tasks.add_task(run_job, result["job_id"])
    return result


@router.post("/analysis", status_code=202, responses=HTTP_ERRORS)
def analysis(payload: AnalysisRequest, tasks: BackgroundTasks, user: Any = Depends(backend.current_user)) -> dict:
    result = enqueue(int(user["id"]), payload.request_id, "analysis", {"reason": payload.reason})
    tasks.add_task(run_job, result["job_id"])
    return result


@router.get("/jobs/by-request/{request_id}", responses=HTTP_ERRORS)
def job_by_request(request_id: str, user: Any = Depends(backend.current_user)) -> dict:
    with closing(backend.connect()) as db:
        row = db.execute("SELECT job_id FROM workspace_job_requests WHERE user_id=? AND request_id=?", (int(user["id"]), request_id)).fetchone()
    if row is None:
        raise HTTPException(404, "workspace_request_not_found")
    return get_job(int(user["id"]), row[0])


@router.get("/jobs/{identifier}", responses=HTTP_ERRORS)
def job_status(identifier: str, user: Any = Depends(backend.current_user)) -> dict:
    return get_job(int(user["id"]), identifier)


@router.post("/jobs/{identifier}/cancel", responses=HTTP_ERRORS)
def cancel(identifier: str, user: Any = Depends(backend.current_user)) -> dict:
    with transaction(backend.connect) as db:
        row = db.execute(OWNED_JOB_SQL, (identifier, int(user["id"]))).fetchone()
        if not row:
            raise HTTPException(404, "workspace_job_not_found")
        result = json.loads(row["result_json"]) if row["result_json"] else {}
        if row["state"] not in TERMINAL:
            status = "cancelled" if row["state"] == "queued" else row["state"]
            db.execute("UPDATE workspace_jobs SET cancel_requested=1,state=?,updated_at=? WHERE id=?", (status, int(time.time()), identifier))
    if row["kind"] == "analysis" and result.get("analysis_job_id"):
        AnalysisQueue(backend.connect).cancel(int(user["id"]), result["analysis_job_id"])
    return get_job(int(user["id"]), identifier)


@router.post("/jobs/{identifier}/retry", status_code=202, responses=HTTP_ERRORS)
def retry(identifier: str, payload: RequestId, tasks: BackgroundTasks, user: Any = Depends(backend.current_user)) -> dict:
    status = get_job(int(user["id"]), identifier)
    if not status["can_retry"]:
        raise HTTPException(409, "workspace_job_not_safely_retryable")
    with closing(backend.connect()) as db:
        row = db.execute(OWNED_JOB_SQL, (identifier, int(user["id"]))).fetchone()
    request = json.loads(row["payload_json"])
    checkpoint = json.loads(row["checkpoint_json"])
    if row["kind"] == "chat":
        # Retrying before any model dispatch is safe, but reuse the existing user
        # message and replace its worker link to keep one conversational turn.
        def relink(db, new_job):
            db.execute("UPDATE workspace_chat_messages SET job_id=? WHERE job_id=? AND user_id=? AND role='user'", (new_job, identifier, int(user["id"])))
    else:
        relink = None
    result = enqueue(int(user["id"]), payload.request_id, row["kind"], request, checkpoint=checkpoint, before_insert=relink)
    tasks.add_task(run_job, result["job_id"])
    return result
