from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any


SYNTHETIC_TENANT_ID = "tenant:v1:synthetic_preview"
SYNTHETIC_USER_ID = "user:v1:synthetic_preview"
SYNTHETIC_CREATED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)


def record_sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_synthetic_scope(connection: Any) -> None:
    """Verify the fixed technical fixture without granting product authority."""

    user_payload: dict[str, object] = {
        "schema_version": "1.0",
        "identity_version": 1,
        "user_id": SYNTHETIC_USER_ID,
        "tenant_id": SYNTHETIC_TENANT_ID,
        "role": "user",
        "created_at": SYNTHETIC_CREATED_AT.isoformat(),
    }
    row = connection.execute(
        "SELECT tenant_id, schema_version, identity_version, role, record_sha256 "
        "FROM omni_cio_v10.users WHERE user_id = %s",
        (SYNTHETIC_USER_ID,),
    ).fetchone()
    expected = (
        SYNTHETIC_TENANT_ID,
        "1.0",
        1,
        "user",
        record_sha256(user_payload),
    )
    if row != expected:
        raise RuntimeError("HOSTED_PREVIEW_SYNTHETIC_SCOPE_DRIFT")
