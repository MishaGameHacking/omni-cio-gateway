"""Select one current reviewed fact without hiding equal-time contradictions."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
import json


def _moment(source: Mapping, name: str) -> datetime:
    value = source[name]
    if not isinstance(value, str):
        raise ValueError("invalid_evidence_time")
    instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("evidence_timezone_required")
    return instant.astimezone(timezone.utc)


def _material_record(record: Mapping) -> str:
    # Audit identifiers may differ for repeated observations of the same fact.
    # URL, dates, expiry, identity and financial values must still agree.
    value = dict(record)
    value["source"] = {key: item for key, item in record["source"].items()
                       if key not in {"id", "review_id"}}
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _record_time(record: Mapping) -> tuple[datetime, datetime]:
    if not isinstance(record, Mapping) or not isinstance(record.get("source"), Mapping):
        raise ValueError("invalid_evidence_record")
    source = record["source"]
    published = _moment(source, "published_at")
    checked = _moment(source, "checked_at")
    if published > checked:
        raise ValueError("checked_before_publication")
    return published, checked


def _latest_group(records: Iterable[Mapping], at: datetime) -> list[Mapping]:
    latest_time = None
    latest = []
    for record in records:
        moment = _record_time(record)
        if moment[0] > at or moment[1] > at:
            continue
        if latest_time is None or moment > latest_time:
            latest_time, latest = moment, [record]
        elif moment == latest_time:
            latest.append(record)
    return latest


def latest_unambiguous(records: Iterable[Mapping], *, at: datetime,
                       valid_source: Callable[[Mapping], bool]) -> dict | None:
    """Do not resurrect older facts when the newest one is invalid or ambiguous.

    Source truth/authorization is the caller's responsibility. The callback must
    validate every tied observation, not only the one that happened to arrive first.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("assessment_timezone_required")
    try:
        latest = _latest_group(records, at)
        if not latest or not all(valid_source(item["source"]) for item in latest):
            return None
        identities = {_material_record(item) for item in latest}
        if len(identities) != 1:
            return None
        # The same answer regardless of row/import order.
        chosen = min(latest, key=lambda item: (item["source"]["id"], item["source"]["review_id"]))
        return dict(chosen)
    except (ValueError, TypeError, KeyError, OverflowError):
        return None
