"""Read-only source observability over the existing materialized workspace.

No source fetches, database writes, model calls or trading permissions. A new
HTTP response timestamp must never refresh the age of the underlying evidence.
An observation, publication, covered interval and investment valuation have
separate clocks. Missing or conflicting provenance is not a zero-risk result.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

MAX_SOURCE_ROWS = 10000
MAX_REFERENCE_NODES = 50000
MAX_REFERENCE_DEPTH = 24
LANES = (
    ("valuation", "Стоимость портфеля", 900),
    ("events", "Новости и события", 1200),
    ("operations", "Операции брокера", 1200),
    ("payouts", "Объявления и выплаты", 3600),
    ("calendar", "Календарь брокера", 900),
)


def mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def clock(value: datetime | None = None) -> datetime:
    result = value if value is not None else datetime.now(timezone.utc)
    if not isinstance(result, datetime) or result.utcoffset() is None:
        raise ValueError("observability_aware_clock_required")
    return result.astimezone(timezone.utc)


def instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    try:
        return clock(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def freshness(value: Any, *, now: datetime, max_age_seconds: int) -> dict:
    """Classify an evidence clock, not the time the status endpoint was read."""
    now = clock(now)
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 31536000:
        raise ValueError("observability_age_limit_invalid")
    observed = instant(value)
    result = {"as_of": observed.isoformat() if observed else None,
              "age_seconds": None, "max_age_seconds": max_age_seconds,
              "state": "missing" if value is None else "invalid", "current": False}
    if observed is None:
        return result
    age = (now - observed).total_seconds()
    result["age_seconds"] = int(age) if age >= 0 else None
    if age < 0:
        return {**result, "state": "future"}
    return {**result, "state": "fresh" if age < max_age_seconds else "stale",
            "current": age < max_age_seconds}


def _lane_basis(snapshot: Mapping, name: str) -> tuple[Any, Any, Any, Any]:
    times = mapping(snapshot.get("section_as_of"))
    monitor = mapping(snapshot.get("event_monitor"))
    if name == "valuation":
        return (snapshot.get("as_of"), mapping(snapshot.get("position_coverage")).get("complete"),
                None, None)
    if name == "calendar":
        calendar = mapping(snapshot.get("calendar"))
        raw = mapping(calendar.get("data"))
        complete = calendar.get("state") == "available" and isinstance(raw.get("exchanges"), list)
        return raw.get("as_of"), complete, monitor.get("calendar"), None
    section = mapping(snapshot.get(name))
    observed = times[name] if name in times else snapshot.get("as_of")
    coverage_end = section.get("end") if name == "operations" else None
    attempted = monitor.get({"events": "news", "operations": "operations", "payouts": "payout_announcements"}[name])
    return observed, section.get("complete"), attempted, coverage_end


def lane_inventory(snapshot: dict | None, *, now: datetime | None = None) -> list[dict]:
    now = clock(now)
    data = mapping(snapshot)
    result = []
    for name, title, maximum in LANES:
        observed, complete, attempt, covered_through = _lane_basis(data, name)
        quality = freshness(observed, now=now, max_age_seconds=maximum)
        exists = bool(data) and (name == "valuation" or name in data)
        if not exists:
            state = "not_collected"
        elif not quality["current"]:
            state = quality["state"]
        elif complete is not True:
            state = "incomplete"
        else:
            state = "current"
        result.append({"id": name, "title": title, "state": state,
            "freshness": quality, "coverage_complete": complete is True,
            "coverage_known": type(complete) is bool,
            "latest_attempt": attempt if attempt in {"available", "incomplete", "unavailable"} else None,
            "covered_through": covered_through if instant(covered_through) else None,
            "valuation_refreshed_by_status_read": False})
    return result


def _referenced_ids(snapshot: Mapping) -> tuple[set[str], set[str]]:
    """Bound traversal; exceeding the bound is explicit, not a partial success."""
    ids, issues, visited = set(), set(), 0
    stack = [(snapshot.get(key), 0) for key in ("positions", "events", "payouts", "operations")]
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > MAX_REFERENCE_NODES or depth > MAX_REFERENCE_DEPTH:
            return ids, issues | {"source_reference_resource_limit"}
        if isinstance(value, Mapping):
            references = value.get("source_ids")
            if references is not None:
                if not isinstance(references, list):
                    issues.add("source_reference_shape_invalid")
                else:
                    for identifier in references:
                        if isinstance(identifier, str) and 0 < len(identifier) <= 200:
                            ids.add(identifier)
                        else:
                            issues.add("source_reference_id_invalid")
            for key, child in value.items():
                if key != "source_ids" and isinstance(child, (Mapping, list)):
                    stack.append((child, depth + 1))
        elif isinstance(value, list):
            if len(value) > MAX_REFERENCE_NODES:
                return ids, issues | {"source_reference_resource_limit"}
            stack.extend((child, depth + 1) for child in value)
    return ids, issues


def provenance_inventory(snapshot: dict | None, *, now: datetime | None = None) -> dict:
    now, data = clock(now), mapping(snapshot)
    rows = data.get("sources", [])
    issues, indexed = set(), {}
    counts = {"current": 0, "stale": 0, "invalid": 0, "future": 0,
              "publication_time_unknown": 0, "conflicting_ids": 0}
    if not isinstance(rows, list) or len(rows) > MAX_SOURCE_ROWS:
        return {"state": "incomplete", "reasons": ["source_registry_shape_or_limit"],
                "reference_resolution_complete": False, "financial_facts_verified": False}
    conflicted = set()
    for row in rows:
        if not isinstance(row, dict):
            issues.add("source_record_invalid")
            counts["invalid"] += 1
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not 1 <= len(identifier) <= 200:
            issues.add("source_id_invalid")
            counts["invalid"] += 1
            continue
        if identifier in indexed and row != indexed[identifier]:
            conflicted.add(identifier)
        indexed[identifier] = row
    for identifier in conflicted:
        del indexed[identifier]
    counts["conflicting_ids"] = len(conflicted)
    if conflicted:
        issues.add("source_id_conflicting_versions")
    for row in indexed.values():
        observed, expires = instant(row.get("observed_at")), instant(row.get("expires_at"))
        published = instant(row.get("published_at"))
        if row.get("published_at") is None:
            counts["publication_time_unknown"] += 1
        if observed is None or expires is None or expires <= observed:
            counts["invalid"] += 1
        elif observed > now or published is not None and published > observed:
            counts["future"] += 1
        elif row.get("published_at") is not None and published is None:
            counts["invalid"] += 1
        elif expires <= now:
            counts["stale"] += 1
        else:
            counts["current"] += 1
    needed, reference_issues = _referenced_ids(data)
    issues.update(reference_issues)
    unresolved = needed - indexed.keys()
    if unresolved:
        issues.add("source_references_unresolved")
    if counts["invalid"]:
        issues.add("source_clocks_invalid")
    if counts["future"]:
        issues.add("source_clocks_in_future")
    if counts["stale"]:
        issues.add("some_source_observations_stale")
    return {"state": "not_collected" if not data else "incomplete" if issues else "observed",
            "source_count": len(indexed), "referenced_count": len(needed),
            "unresolved_reference_count": len(unresolved), "counts": counts,
            "reasons": sorted(issues), "reference_resolution_complete": not unresolved and not reference_issues and not conflicted,
            "financial_facts_verified": False,
            "scope": "provenance_and_clocks_only_not_truth_verification"}


def news_inventory(snapshot: dict | None, *, now: datetime | None = None) -> dict:
    now = clock(now)
    items = mapping(mapping(snapshot).get("events")).get("items", [])
    if not isinstance(items, list) or len(items) > MAX_SOURCE_ROWS:
        return {"state": "incomplete", "reason": "news_observation_shape_or_limit",
                "independent_confirmations": None}
    timestamps, seen, conflicting, malformed = [], {}, set(), 0
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            malformed += 1
            continue
        identifier = item["id"]
        if identifier in seen and seen[identifier] != item:
            conflicting.add(identifier)
        seen[identifier] = item
        when = instant(item.get("published_at"))
        if when is None or when > now:
            malformed += 1
        else:
            timestamps.append(when)
    return {"state": "incomplete" if malformed or conflicting else "observed",
            "event_groups": len(seen), "conflicting_event_ids": len(conflicting),
            "invalid_or_future_publications": malformed,
            "earliest_publication_at": min(timestamps).isoformat() if timestamps else None,
            "latest_publication_at": max(timestamps).isoformat() if timestamps else None,
            "independent_confirmations": None,
            "independence_reason": "publication_count_is_not_independent_confirmation",
            "headline_similarity_verifies_event": False,
            "instructions_in_source_are_data_only": True}
