"""Bounded public-source intake with immutable documents in the existing DB.

GLEIF is an identity source, never a credit rating or an order permission.
Only an exact, checksummed ISIN is sent; broker/user data never reaches it.
The result is deliberately separate from operator-reviewed issuer identities.
"""
from __future__ import annotations

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
import sqlite3
import time
from urllib.parse import urlencode
import uuid

import httpx

PROVIDER = "gleif"
PARSER_VERSION = "gleif-exact-isin-v1"
BASE_URL = "https://api.gleif.org/api/v1/lei-records"
MAX_BYTES = 262144
MAX_DATASET_AGE = timedelta(hours=48)
SUCCESS_TTL = timedelta(hours=6)
SOURCE_REGISTRY = {
    PROVIDER: {"purpose": "legal_entity_identity", "endpoint": BASE_URL,
        "documentation": "https://www.gleif.org/en/lei-data/gleif-api",
        "terms": "https://www.gleif.org/en/meta/lei-data-terms-of-use",
        "license": "CC0-1.0", "parser_version": PARSER_VERSION,
        "rating_source": False, "automatic_trade_permission": False}}


def snapshot_status(snapshot: dict | None, *, at: datetime | None = None) -> dict:
    """Expose current holdings' stored source status without network or DB writes."""
    now = _clock(at)
    saved = (snapshot or {}).get("public_sources") or {}
    selected, missing = {}, 0
    for row in (snapshot or {}).get("positions", []):
        if row.get("instrument_type") not in {"share", "bond"}:
            continue
        isin = normalized_isin((row.get("metadata") or {}).get("isin"))
        if isin:
            selected.setdefault(isin, set()).add(row["instrument_uid"])
        else:
            missing += 1
    observed = {item.get("isin"): item for item in saved.get("items", [])
                if isinstance(item, dict) and item.get("provider") == PROVIDER}
    items = []
    for isin, uids in sorted(selected.items()):
        value = deepcopy(observed.get(isin) or {"provider": PROVIDER, "isin": isin,
            "state": "pending", "identity": None, "reason": "source_not_collected"})
        value = _safe_result(value, now)
        value["instrument_uids"] = sorted(uids)
        items.append(value)
    mapped = sum(item.get("state") == "available" for item in items)
    status = "available" if items and mapped == len(items) and not missing else "partial"
    if not items and not missing:
        status = "not_applicable" if snapshot else "not_collected"
    return {"provider": PROVIDER, "state": status, "checked_at": saved.get("checked_at"),
        "items": items, "eligible_identifiers": len(items), "mapped_identifiers": mapped,
        "missing_identifiers": missing, "coverage_scope": "held_positions_only",
        "rating_sources_fetched": False, "automatic_trade_permission": False,
        "reviewed_issuer_identity_replaced": False, "source_registry": SOURCE_REGISTRY[PROVIDER]}


class SourceError(ValueError):
    """A sanitized source-contract error; never include a remote body."""


def _clock(value: datetime | None = None) -> datetime:
    value = datetime.now(timezone.utc) if value is None else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SourceError("source_clock_timezone_required")
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise SourceError("source_clock_invalid") from error


def _stamp(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise SourceError("source_timestamp_invalid")
    try:
        return _clock(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, OverflowError) as error:
        raise SourceError("source_timestamp_invalid") from error


def normalized_isin(value: object) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2}[A-Za-z0-9]{9}[0-9]", value):
        return None
    value = value.upper()
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    total = 0
    for offset, char in enumerate(reversed(digits)):
        part = int(char) * (2 if offset % 2 else 1)
        total += part // 10 + part % 10
    return value if total % 10 == 0 else None


def request_url(isin: str) -> str:
    if not isinstance(isin, str) or normalized_isin(isin) != isin:
        raise SourceError("source_isin_invalid")
    return BASE_URL + "?" + urlencode({"filter[isin]": isin, "page[size]": 2})


def initialize(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS public_source_documents_v1 (
        sha256 TEXT PRIMARY KEY, body BLOB NOT NULL, bytes INTEGER NOT NULL,
        first_received_at TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS public_source_observations_v1 (
        id TEXT PRIMARY KEY, provider TEXT NOT NULL, subject TEXT NOT NULL,
        url TEXT NOT NULL, document_sha256 TEXT, observed_at TEXT NOT NULL,
        state TEXT NOT NULL, payload TEXT NOT NULL)""")
    db.execute("""CREATE INDEX IF NOT EXISTS public_source_observation_subject
        ON public_source_observations_v1(provider,subject,observed_at)""")
    db.execute("""CREATE TABLE IF NOT EXISTS public_source_cache_v1 (
        provider TEXT NOT NULL, subject TEXT NOT NULL, result TEXT NOT NULL,
        next_check_at TEXT NOT NULL, etag TEXT, last_modified TEXT,
        document_sha256 TEXT, failures INTEGER NOT NULL DEFAULT 0,
        lease_token TEXT, lease_until TEXT,
        PRIMARY KEY(provider,subject))""")
    db.commit()


def _reject_nonfinite(_: str) -> None:
    raise SourceError("source_nonfinite_json")


def _json(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise SourceError("source_duplicate_json_key")
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise SourceError("source_json_invalid") from error
    if not isinstance(value, dict):
        raise SourceError("source_json_invalid")
    return value


def _text(value: object, limit: int = 240) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= limit
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise SourceError("source_identity_field_invalid")
    return value


def _lei(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9A-Z]{18}[0-9]{2}", value):
        raise SourceError("source_lei_invalid")
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in value)
    if int(digits) % 97 != 1:
        raise SourceError("source_lei_invalid")
    return value


def parse_gleif(raw: bytes, isin: str, at: datetime) -> dict:
    """Parse a response from the fixed exact-ISIN endpoint, not name search."""
    at = _clock(at)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or not isinstance(isin, str) or normalized_isin(isin) != isin:
        raise SourceError("source_input_invalid")
    data = _json(raw)
    try:
        meta, rows = data["meta"], data["data"]
        published = _stamp(meta["goldenCopy"]["publishDate"])
        total = meta["pagination"]["total"]
        page = meta["pagination"]["currentPage"]
        if (type(total) is not int or total < 0 or type(page) is not int or page != 1
                or not isinstance(rows, list) or len(rows) > 2 or len(rows) != min(total, 2)):
            raise SourceError("source_pagination_invalid")
        result = {"provider": PROVIDER, "isin": isin, "state": "missing",
            "reason": "no_exact_isin_mapping", "identity": None,
            "url": request_url(isin), "parser_version": PARSER_VERSION,
            "dataset_published_at": published.isoformat(), "checked_at": at.isoformat(),
            "document_sha256": hashlib.sha256(raw).hexdigest(),
            "rating_verified": False, "trade_permission": False}
        if published > at or at - published > MAX_DATASET_AGE:
            return {**result, "state": "stale", "reason": "dataset_time_outside_window"}
        if total == 0:
            return result
        if total != 1:
            return {**result, "state": "ambiguous", "reason": "multiple_exact_isin_mappings"}
        row = rows[0]
        attributes = row["attributes"]
        lei = _lei(attributes["lei"])
        if row["type"] != "lei-records" or row["id"] != lei:
            raise SourceError("source_lei_identity_mismatch")
        entity, registration = attributes["entity"], attributes["registration"]
        updated = _stamp(registration["lastUpdateDate"])
        renewed = _stamp(registration["nextRenewalDate"])
        if updated > published:
            raise SourceError("source_update_after_publication")
        result["entity_updated_at"] = updated.isoformat()
        if entity["status"] != "ACTIVE" or registration["status"] != "ISSUED" or renewed <= at:
            return {**result, "state": "inactive", "reason": "entity_or_registration_not_current"}
        identity = {"lei": lei, "name": _text(entity["legalName"]["name"]),
            "jurisdiction": _text(entity["jurisdiction"], 32),
            "registered_as": _text(entity["registeredAs"], 160),
            "registration_authority": _text(entity["registeredAt"]["id"], 40)}
        return {**result, "state": "available", "reason": None, "identity": identity,
            "fresh_until": min(published + MAX_DATASET_AGE, renewed, at + SUCCESS_TTL).isoformat(),
            "identity_basis": "GLEIF_exact_ISIN_filter"}
    except (KeyError, TypeError, AttributeError) as error:
        raise SourceError("source_schema_invalid") from error


def fetch_document(url: str, headers: dict) -> tuple[int, dict, bytes]:
    """One fixed-origin HTTPS request, no redirect, no credentials, no retry."""
    if not url.startswith(BASE_URL + "?"):
        raise SourceError("source_url_not_allowed")
    started = time.monotonic()
    with (
        httpx.Client(timeout=httpx.Timeout(2.5), follow_redirects=False, trust_env=False,
            headers={"Accept": "application/vnd.api+json, application/json",
                     "Accept-Encoding": "identity", "User-Agent": "AnalystAI-PublicIdentity/1"}) as client,
        client.stream("GET", url, headers=headers) as response,
    ):
        response_headers = {key.lower(): value for key, value in response.headers.items()
                            if key.lower() in {"etag", "last-modified", "retry-after", "content-type"}}
        if response.status_code != 200:
            return response.status_code, response_headers, b""
        if response_headers.get("content-type", "").split(";", 1)[0] not in {
                "application/json", "application/vnd.api+json"}:
            raise SourceError("source_content_type_invalid")
        if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
            raise SourceError("source_encoding_not_allowed")
        body = bytearray()
        for chunk in response.iter_raw():
            if time.monotonic() - started > 4 or len(body) + len(chunk) > MAX_BYTES:
                raise SourceError("source_response_limit")
            body.extend(chunk)
        return response.status_code, response_headers, bytes(body)


def _header(value: object) -> str | None:
    if isinstance(value, str) and 0 < len(value) <= 512 and all(32 <= ord(c) < 127 for c in value):
        return value
    return None


def _retry_delay(value: object, now: datetime, minimum: timedelta) -> timedelta:
    if not isinstance(value, str) or len(value) > 128:
        return minimum
    try:
        if value.isascii() and value.isdigit():
            seconds = int(value)
        else:
            seconds = (_clock(parsedate_to_datetime(value)) - now).total_seconds()
        maximum = (datetime.max.replace(tzinfo=timezone.utc) - now).total_seconds() - 1
        return timedelta(seconds=max(minimum.total_seconds(), min(maximum, max(0, seconds))))
    except (ValueError, TypeError, OverflowError):
        return minimum


def _safe_result(result: dict, at: datetime) -> dict:
    if not isinstance(result, dict):
        raise SourceError("source_cache_invalid")
    if result.get("state") == "available":
        try:
            if at >= _stamp(result.get("fresh_until")) or _stamp(result["checked_at"]) > at:
                return {**result, "state": "stale", "reason": "cached_identity_expired", "identity": None}
        except (SourceError, KeyError):
            return {"provider": PROVIDER, "state": "unavailable", "reason": "cache_invalid", "identity": None}
    return result


def _cached_json(value: str) -> dict:
    if not isinstance(value, str) or len(value) > 32768:
        raise SourceError("source_cache_invalid")
    try:
        result = json.loads(value)
    except (ValueError, TypeError) as error:
        raise SourceError("source_cache_invalid") from error
    if not isinstance(result, dict):
        raise SourceError("source_cache_invalid")
    return result


def cached_result(connect, isin: str, *, at: datetime | None = None) -> dict | None:
    now = _clock(at)
    with closing(connect()) as db:
        initialize(db)
        row = db.execute("SELECT result FROM public_source_cache_v1 WHERE provider=? AND subject=?",
            (PROVIDER, isin)).fetchone()
    return _safe_result(_cached_json(row[0]), now) if row else None


def refresh_isin(connect, isin: str, *, at: datetime | None = None, fetch=None) -> dict:
    now, url = _clock(at), request_url(isin)
    token = uuid.uuid4().hex
    with closing(connect()) as db:
        initialize(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT result,next_check_at,etag,last_modified,document_sha256,failures,lease_until "
                "FROM public_source_cache_v1 WHERE provider=? AND subject=?", (PROVIDER, isin)).fetchone()
            if row and (now < _stamp(row[1]) or row[6] and now < _stamp(row[6])):
                return _safe_result(_cached_json(row[0]), now)
            initial = {"provider": PROVIDER, "isin": isin, "state": "pending", "identity": None}
            db.execute("INSERT INTO public_source_cache_v1(provider,subject,result,next_check_at,lease_token,lease_until) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(provider,subject) DO UPDATE SET lease_token=excluded.lease_token, "
                "lease_until=excluded.lease_until", (PROVIDER, isin, json.dumps(initial), now.isoformat(), token,
                (now + timedelta(seconds=60)).isoformat()))
        old_body = None
        if row and row[4]:
            document = db.execute("SELECT body FROM public_source_documents_v1 WHERE sha256=?", (row[4],)).fetchone()
            old_body = bytes(document[0]) if document else None
            if old_body is not None and (len(old_body) > MAX_BYTES or hashlib.sha256(old_body).hexdigest() != row[4]):
                old_body = None
    headers = {}
    if row and old_body is not None:
        for name, value in (("If-None-Match", row[2]), ("If-Modified-Since", row[3])):
            if _header(value):
                headers[name] = value
    raw, response_headers, failures = None, {}, (row[5] if row else 0)
    try:
        status, response_headers, body = (fetch or fetch_document)(url, headers)
        if status == 304:
            if old_body is None:
                raise SourceError("source_304_without_document")
            raw = old_body
        elif status == 200:
            if not isinstance(body, bytes) or len(body) > MAX_BYTES:
                raise SourceError("source_response_limit")
            raw = body
        else:
            raise SourceError("source_http_" + str(status) if type(status) is int else "source_http_invalid")
        result = parse_gleif(raw, isin, now)
        failures = 0
        delay = SUCCESS_TTL
        if result.get("state") == "available":
            delay = min(delay, _stamp(result["fresh_until"]) - now)
    except (SourceError, httpx.HTTPError, OSError) as error:
        failures = min(failures + 1, 8)
        delay = timedelta(seconds=min(3600, 60 * 2 ** (failures - 1)))
        delay = _retry_delay(response_headers.get("retry-after", ""), now, delay)
        reason = str(error) if isinstance(error, SourceError) else "source_transport_unavailable"
        result = {"provider": PROVIDER, "isin": isin, "state": "unavailable", "reason": reason,
            "identity": None, "checked_at": now.isoformat(), "url": url, "parser_version": PARSER_VERSION,
            "rating_verified": False, "trade_permission": False}
    result["next_check_at"] = (now + delay).isoformat()
    body_sha = hashlib.sha256(raw).hexdigest() if raw is not None else None
    if body_sha:
        result["document_sha256"] = body_sha
    serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    observation_id = hashlib.sha256((url + now.isoformat() + serialized).encode()).hexdigest()
    with closing(connect()) as db:
        initialize(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT lease_token FROM public_source_cache_v1 WHERE provider=? AND subject=?",
                (PROVIDER, isin)).fetchone()
            if not current or current[0] != token:
                raise SourceError("source_lease_lost")
            if raw is not None:
                db.execute("INSERT OR IGNORE INTO public_source_documents_v1 VALUES (?,?,?,?)",
                    (body_sha, raw, len(raw), now.isoformat()))
            db.execute("INSERT OR IGNORE INTO public_source_observations_v1 VALUES (?,?,?,?,?,?,?,?)",
                (observation_id, PROVIDER, isin, url, body_sha, now.isoformat(), result["state"], serialized))
            db.execute("UPDATE public_source_cache_v1 SET result=?,next_check_at=?,etag=?,last_modified=?, "
                "document_sha256=?,failures=?,lease_token=NULL,lease_until=NULL WHERE provider=? AND subject=? AND lease_token=?",
                (serialized, result["next_check_at"], _header(response_headers.get("etag")),
                 _header(response_headers.get("last-modified")), body_sha, failures, PROVIDER, isin, token))
    return result


def _due_identifiers(connect, identifiers: list[str], now: datetime, cursor: str | None) -> tuple[dict, list[str]]:
    """Read persistent freshness once; a replaced snapshot cannot starve the tail."""
    results, stored, due = {}, {}, []
    try:
        with closing(connect()) as db:
            initialize(db)
            for offset in range(0, len(identifiers), 400):
                batch = identifiers[offset:offset + 400]
                placeholders = ",".join("?" for _ in batch)
                rows = db.execute("SELECT subject,result,next_check_at,lease_until FROM public_source_cache_v1 "
                    "WHERE provider=? AND subject IN (" + placeholders + ")", (PROVIDER, *batch))
                stored.update((row[0], row[1:]) for row in rows)
    except sqlite3.Error:
        return {isin: {"provider": PROVIDER, "isin": isin, "state": "unavailable",
            "reason": "source_store_unavailable", "identity": None} for isin in identifiers}, []
    index = next((i + 1 for i, value in enumerate(identifiers) if value == cursor), 0) % len(identifiers)
    ranked = identifiers[index:] + identifiers[:index]
    for rank, isin in enumerate(ranked):
        row = stored.get(isin)
        if row is None:
            results[isin] = {"provider": PROVIDER, "isin": isin, "state": "pending", "identity": None}
            due.append((0, now, rank, isin))
            continue
        try:
            results[isin] = _safe_result(_cached_json(row[0]), now)
            next_check = _stamp(row[1])
            leased = bool(row[2] and now < _stamp(row[2]))
            if now >= next_check and not leased:
                due.append((1, next_check, rank, isin))
        except SourceError:
            results[isin] = {"provider": PROVIDER, "isin": isin, "state": "unavailable",
                "reason": "source_store_unavailable", "identity": None}
    # Missing keys first, then oldest overdue observation. Fresh cache hits do
    # not consume the three network slots. Cursor only breaks equal-time ties.
    return results, [row[3] for row in sorted(due)]


def collect_snapshot_sources(connect, snapshot: dict, checkpoint: dict, progress, *,
                             at: datetime | None = None, fetch=None) -> dict:
    """A bounded sub-lane of the existing event job; failed sources stay explicit.

    It changes no positions, ratings, user data or investment rules. Three due
    identifiers at most; a 10-second scheduling budget stops new requests
    after slow responses. Individual requests retain their transport timeouts.
    """
    now, started = _clock(at), time.monotonic()
    selected, missing = {}, 0
    for position in snapshot.get("positions", []):
        if position.get("instrument_type") not in {"share", "bond"}:
            continue
        isin = normalized_isin((position.get("metadata") or {}).get("isin"))
        if isin:
            selected.setdefault(isin, []).append(position["instrument_uid"])
        else:
            missing += 1
    identifiers = sorted(selected)
    if not identifiers:
        return {"provider": PROVIDER, "checked_at": now.isoformat(), "state": "not_applicable" if not missing else "partial",
            "items": [], "eligible_identifiers": 0, "missing_identifiers": missing,
            "rating_sources_fetched": False, "coverage_scope": "held_positions_only"}
    cursor = checkpoint.get("public_source_cursor") or (snapshot.get("public_sources") or {}).get("cursor")
    results, due = _due_identifiers(connect, identifiers, now, cursor)
    visited = 0
    for isin in due[:3]:
        if time.monotonic() - started >= 10:
            break
        try:
            results[isin] = refresh_isin(connect, isin, at=now, fetch=fetch)
        except (SourceError, sqlite3.Error):
            results[isin] = {"provider": PROVIDER, "isin": isin, "state": "unavailable",
                "reason": "source_store_unavailable", "identity": None}
        checkpoint["public_source_cursor"] = isin
        visited += 1
        progress("collecting_public_identity", checkpoint)
    items = [{**results[isin], "instrument_uids": sorted(set(selected[isin]))} for isin in identifiers]
    mapped = sum(item["state"] == "available" for item in items)
    return {"provider": PROVIDER, "checked_at": now.isoformat(), "state": "available" if mapped == len(items) and not missing else "partial",
        "items": items, "eligible_identifiers": len(items), "mapped_identifiers": mapped,
        "missing_identifiers": missing, "identifiers_visited": visited, "cursor": checkpoint.get("public_source_cursor") or cursor,
        "coverage_scope": "held_positions_only", "rating_sources_fetched": False,
        "reviewed_issuer_identity_replaced": False, "automatic_trade_permission": False,
        "source_registry": SOURCE_REGISTRY[PROVIDER]}
