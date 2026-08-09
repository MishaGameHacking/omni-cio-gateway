from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts.v10_wp9a_operations_log import (
    OperationsLogError,
    load_policy,
    validate_event,
    write_event,
)


def safe_event(index: int = 1) -> dict:
    return {
        "schema_version": "1",
        "event_type": "OPERATIONS_CHECK",
        "severity": "INFO",
        "component_class": "NODE",
        "state": "PASS",
        "reason_code": "WP9A_OK",
        "observed_at_utc": f"2026-08-09T04:00:{index:02d}+00:00",
        "duration_ms": 10,
        "version_class": "ACCEPTED",
        "resource_band": "NORMAL",
        "correlation_id": f"wp9a-{index}",
    }


def test_log_rejects_unknown_or_private_fields() -> None:
    policy = load_policy()
    event = safe_event()
    event["token"] = "never-allowed"
    with pytest.raises(OperationsLogError, match="LOG_FIELD_NOT_ALLOWED:token"):
        validate_event(event, policy)


def test_log_rejects_free_form_secret_like_content_surface() -> None:
    policy = load_policy()
    event = safe_event()
    event["reason_code"] = "contains spaces and free form data"
    with pytest.raises(OperationsLogError, match="LOG_SAFE_CODE_INVALID:reason_code"):
        validate_event(event, policy)


def test_log_writes_hash_chained_jsonl(tmp_path: Path) -> None:
    policy = load_policy()
    log_path = write_event(tmp_path, safe_event(1), policy)
    write_event(tmp_path, safe_event(2), policy)
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["previous_hash"] == "0" * 64
    assert records[1]["previous_hash"] == records[0]["event_hash"]
    assert len(records[0]["event_hash"]) == 64


def test_log_rotates_with_bounded_file_count(tmp_path: Path) -> None:
    policy = copy.deepcopy(load_policy())
    policy["logging"]["max_file_mib"] = 0.00035
    policy["logging"]["retained_files"] = 3
    for index in range(1, 10):
        write_event(tmp_path, safe_event(index), policy)
    files = sorted(tmp_path.glob("wp9a-operations.jsonl*"))
    assert len(files) <= 3
    assert (tmp_path / "wp9a-operations.jsonl").exists()


def test_log_removes_expired_rotated_files(tmp_path: Path) -> None:
    policy = copy.deepcopy(load_policy())
    policy["logging"]["retention_days"] = 30
    stale = tmp_path / "wp9a-operations.jsonl.1"
    stale.write_text("{}\n", encoding="utf-8")
    old = datetime(2026, 6, 1, tzinfo=UTC).timestamp()
    os.utime(stale, (old, old))
    write_event(
        tmp_path,
        safe_event(1),
        policy,
        now=datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert not stale.exists()


def test_log_keeps_recent_rotated_files(tmp_path: Path) -> None:
    policy = copy.deepcopy(load_policy())
    recent = tmp_path / "wp9a-operations.jsonl.1"
    recent.write_text("{}\n", encoding="utf-8")
    timestamp = (datetime(2026, 8, 9, tzinfo=UTC) - timedelta(days=1)).timestamp()
    os.utime(recent, (timestamp, timestamp))
    write_event(
        tmp_path,
        safe_event(1),
        policy,
        now=datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert recent.exists()
