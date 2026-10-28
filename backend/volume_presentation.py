"""Owner-scoped presentation preferences with transactional optimistic updates."""
from __future__ import annotations

from contextlib import closing
import json
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

try:
    from . import app as backend
    from .ai_budget import transaction
except ImportError:
    import app as backend
    from ai_budget import transaction

router = APIRouter(prefix="/presentation", tags=["Presentation preferences"])
DEFAULTS = {"accent": "AURORA", "density": "COMFORT", "depth": True,
            "hide_home_balance": False, "home_structure": True, "haptics": True,
            "motion": "LIVE", "bright_light": False, "screenshots_blocked": False}


def initialize(connect=None):
    with transaction(backend.connect if connect is None else connect) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS workspace_presentation_preferences (
            user_id INTEGER PRIMARY KEY, version INTEGER NOT NULL CHECK(version>=1),
            payload_json TEXT NOT NULL, updated_at INTEGER NOT NULL)""")


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accent: Literal["AURORA", "OCEAN", "IRIS"] | None = None
    density: Literal["COMFORT", "COMPACT"] | None = None
    depth: bool | None = None
    hide_home_balance: bool | None = None
    home_structure: bool | None = None
    haptics: bool | None = None
    motion: Literal["LIVE", "SUBDUED", "OFF"] | None = None
    bright_light: bool | None = None
    screenshots_blocked: bool | None = None

    @model_validator(mode="after")
    def require_values(self):
        values = self.model_dump(exclude_unset=True)
        if not values or any(value is None for value in values.values()):
            raise ValueError("At least one explicit non-null setting is required")
        return self


class Write(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=0, le=9007199254740991)
    changes: Changes


def read_in(db, user_id):
    row = db.execute("SELECT version,payload_json FROM workspace_presentation_preferences WHERE user_id=?",
                     (user_id,)).fetchone()
    return {"schema_version": 1, "version": row[0] if row else 0,
            "settings": {**DEFAULTS, **(json.loads(row[1]) if row else {})}}


def response(value):
    return JSONResponse(value, headers={"Cache-Control": "no-store, private"})


@router.get("")
def get(user: Annotated[Any, Depends(backend.current_user)]):
    with closing(backend.connect()) as db:
        return response(read_in(db, int(user["id"])))


@router.put("", responses={409: {"description": "Settings changed; reread before merging the pending fields."}})
def put(payload: Write, user: Annotated[Any, Depends(backend.current_user)]):
    user_id = int(user["id"])
    with transaction(backend.connect) as db:
        current = read_in(db, user_id)
        if payload.expected_version != current["version"]:
            raise HTTPException(409, "presentation_version_conflict")
        merged = {**current["settings"], **payload.changes.model_dump(exclude_unset=True)}
        if merged != current["settings"]:
            current = {**current, "version": current["version"] + 1, "settings": merged}
            db.execute("""INSERT INTO workspace_presentation_preferences VALUES (?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET version=excluded.version,
                payload_json=excluded.payload_json,updated_at=excluded.updated_at""",
                (user_id, current["version"], json.dumps(merged, sort_keys=True), int(time.time())))
        return response(current)
