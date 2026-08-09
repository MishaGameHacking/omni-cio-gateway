from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "docs" / "architecture" / "V10_WP9A_OPERATIONS_CONTRACT.json"
DEFAULT_FILE_NAME = "wp9a-operations.jsonl"
SAFE_CODE = re.compile(r"^[A-Z0-9_.:-]{1,64}$")
SAFE_CORRELATION = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
ZERO_HASH = "0" * 64


class OperationsLogError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise OperationsLogError("LOG_TIMESTAMP_NOT_TIMEZONE_AWARE")
    return parsed.astimezone(UTC)


def validate_event(event: dict[str, Any], policy: dict[str, Any]) -> None:
    logging_policy = policy["logging"]
    allowed = set(logging_policy["allowed_fields"])
    keys = set(event)
    unknown = sorted(keys - allowed)
    if unknown:
        raise OperationsLogError(f"LOG_FIELD_NOT_ALLOWED:{unknown[0]}")

    forbidden = {str(item).lower() for item in logging_policy["forbidden_fields"]}
    for key in keys:
        lowered = key.lower()
        if lowered in forbidden or any(token in lowered for token in forbidden):
            raise OperationsLogError(f"LOG_FORBIDDEN_FIELD:{key}")

    required = {
        "schema_version",
        "event_type",
        "severity",
        "component_class",
        "state",
        "observed_at_utc",
    }
    missing = sorted(required - keys)
    if missing:
        raise OperationsLogError(f"LOG_REQUIRED_FIELD_MISSING:{missing[0]}")
    if event["schema_version"] != "1":
        raise OperationsLogError("LOG_SCHEMA_VERSION_INVALID")

    for key in (
        "event_type",
        "severity",
        "component_class",
        "state",
        "reason_code",
        "version_class",
        "resource_band",
    ):
        if key not in event or event[key] is None:
            continue
        if not isinstance(event[key], str) or not SAFE_CODE.fullmatch(event[key]):
            raise OperationsLogError(f"LOG_SAFE_CODE_INVALID:{key}")

    if "correlation_id" in event and event["correlation_id"] is not None:
        value = event["correlation_id"]
        if not isinstance(value, str) or not SAFE_CORRELATION.fullmatch(value):
            raise OperationsLogError("LOG_CORRELATION_ID_INVALID")

    if "duration_ms" in event and event["duration_ms"] is not None:
        duration = event["duration_ms"]
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or duration < 0
        ):
            raise OperationsLogError("LOG_DURATION_INVALID")

    _parse_utc(str(event["observed_at_utc"]))


def _canonical_payload(event: dict[str, Any], previous_hash: str) -> bytes:
    payload = {**event, "previous_hash": previous_hash}
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _last_hash(path: Path) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return ZERO_HASH
    last = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last = line
    if not last:
        return ZERO_HASH
    try:
        payload = json.loads(last)
        value = str(payload["event_hash"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OperationsLogError("LOG_TAIL_INVALID") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise OperationsLogError("LOG_TAIL_HASH_INVALID")
    return value


def _rotate(log_path: Path, retained_files: int) -> None:
    if retained_files < 1:
        raise OperationsLogError("LOG_RETAINED_FILES_INVALID")
    oldest = log_path.with_name(f"{log_path.name}.{retained_files - 1}")
    if retained_files > 1 and oldest.exists():
        oldest.unlink()
    for index in range(retained_files - 2, 0, -1):
        source = log_path.with_name(f"{log_path.name}.{index}")
        target = log_path.with_name(f"{log_path.name}.{index + 1}")
        if source.exists():
            source.replace(target)
    if retained_files > 1 and log_path.exists():
        log_path.replace(log_path.with_name(f"{log_path.name}.1"))
    elif retained_files == 1 and log_path.exists():
        log_path.unlink()


def _delete_expired(
    log_dir: Path, file_name: str, retention_days: int, now: datetime
) -> None:
    cutoff = now - timedelta(days=retention_days)
    for path in log_dir.glob(f"{file_name}*"):
        if not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified < cutoff:
            path.unlink()


def write_event(
    log_dir: Path,
    event: dict[str, Any],
    policy: dict[str, Any],
    *,
    now: datetime | None = None,
) -> Path:
    validate_event(event, policy)
    logging_policy = policy["logging"]
    if logging_policy.get("local_only_by_default") is not True:
        raise OperationsLogError("LOG_LOCAL_ONLY_POLICY_MISSING")

    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_name = str(logging_policy.get("file_name", DEFAULT_FILE_NAME))
    log_path = log_dir / file_name
    retention_days = int(logging_policy["retention_days"])
    retained_files = int(logging_policy["retained_files"])
    max_bytes = int(float(logging_policy["max_file_mib"]) * 1024 * 1024)
    if max_bytes <= 0 or retention_days <= 0:
        raise OperationsLogError("LOG_RETENTION_POLICY_INVALID")

    _delete_expired(log_dir, file_name, retention_days, current_time)
    previous_hash = _last_hash(log_path)
    canonical = _canonical_payload(event, previous_hash)
    event_hash = hashlib.sha256(canonical).hexdigest()
    record = {
        **event,
        "previous_hash": previous_hash,
        "event_hash": event_hash,
    }
    encoded = (
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")

    if log_path.exists() and log_path.stat().st_size + len(encoded) > max_bytes:
        _rotate(log_path, retained_files)
        # Preserve the chain across rotation: the new active file points to the
        # last hash that is now stored in .1.
        record["previous_hash"] = previous_hash
        canonical = _canonical_payload(event, previous_hash)
        record["event_hash"] = hashlib.sha256(canonical).hexdigest()
        encoded = (
            json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n"
        ).encode("utf-8")

    with log_path.open("ab") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write one sanitized WP9A operations event"
    )
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--event-file", required=True, type=Path)
    args = parser.parse_args()
    event = json.loads(args.event_file.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise OperationsLogError("LOG_EVENT_NOT_OBJECT")
    write_event(args.log_dir, event, load_policy())
    print("WP9A operations event recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
