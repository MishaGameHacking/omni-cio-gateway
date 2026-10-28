"""Authenticated OSINT controls; reads never start collection or paid analysis."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response

try:
    from . import app as backend, osint_read
    from .volume_jobs import RequestId, HTTP_ERRORS
except ImportError:
    import app as backend
    import osint_read
    from volume_jobs import RequestId, HTTP_ERRORS

router = APIRouter(prefix="/osint", tags=["Public investment research"])


def private(response: Response):
    response.headers["Cache-Control"] = "no-store, private"


@router.get("/status", responses=HTTP_ERRORS)
def status(response: Response, _user: Any = Depends(backend.current_user)):
    private(response)
    return osint_read.status(backend.connect)


@router.get("/sources", responses=HTTP_ERRORS)
def sources(response: Response, _user: Any = Depends(backend.current_user)):
    private(response)
    return {"sources": osint_read.sources()}


@router.get("/documents", responses=HTTP_ERRORS)
def documents(response: Response, limit: int = Query(25, ge=1, le=50),
              before_id: int | None = Query(None, ge=1),
              source_id: str | None = Query(None, max_length=64),
              q: str | None = Query(None, max_length=160),
              _user: Any = Depends(backend.current_user)):
    private(response)
    return osint_read.documents(backend.connect, limit=limit, before_id=before_id, source_id=source_id, query=q)


@router.get("/documents/{identifier}", responses=HTTP_ERRORS)
def document(identifier: int, response: Response, _user: Any = Depends(backend.current_user)):
    private(response)
    result = osint_read.document(backend.connect, identifier)
    if result is None:
        raise HTTPException(404, "osint_document_not_found")
    return result


@router.post("/refresh", status_code=202, responses=HTTP_ERRORS)
def refresh(payload: RequestId, tasks: BackgroundTasks, response: Response,
            user: Any = Depends(backend.current_user)):
    try:
        from .osint_worker import enqueue_cycle
        from .volume_jobs import run_job
    except ImportError:
        from osint_worker import enqueue_cycle
        from volume_jobs import run_job
    private(response)
    job = enqueue_cycle(user, payload.request_id)
    tasks.add_task(run_job, job["job_id"])
    return job
