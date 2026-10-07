"""Private research inputs and immutable, reproducible historical runs.

An uploaded source URL is attribution, not proof that a source was verified.
All additional observations remain explicitly user-supplied and tenant-bound.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from .db import Database, live_execution_lock_key
from .portfolio_store import SettingsVersionConflict
from .strategy import document_hash

MAX_RESEARCH_RUN_PAGE = 200
MAX_ARCHIVE_DOCUMENT_BYTES = 32 * 1024 * 1024
MAX_EVIDENCE_DOCUMENT_BYTES = 16 * 1024 * 1024
_REQUEST_FIELDS = "id, status, run_id, error_code, created_at, updated_at, expires_at"
_REQUEST_SELECT = "SELECT " + _REQUEST_FIELDS
_REQUEST_LIMIT = 20000
_FACT_KEYS = frozenset(
    {
        "issuer_id",
        "group_id",
        "sector",
        "maturity_date",
        "perpetual",
        "floating_coupon",
        "rating",
        "cashflow_yield_percent",
        "net_yield_percent",
        "key_rate_percent",
        "roe_percent",
        "debt_to_ebitda",
        "free_cashflow_yield_percent",
        "dividend_yield_percent",
        "payout_ratio_percent",
        "dividend_declared",
        "expense_ratio_percent",
        "index_tracking",
        "growth_beta",
        "inflation_beta",
        "factor_observations",
        "coupon_formula_verified",
    }
)
_STRING_FACTS = {"issuer_id", "group_id", "sector", "maturity_date", "rating"}
_BOOL_FACTS = {
    "perpetual",
    "floating_coupon",
    "dividend_declared",
    "index_tracking",
    "coupon_formula_verified",
}


class ResearchNotFound(LookupError):
    """No research object exists in the authenticated tenant."""


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _object(value: object, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("research_evidence_fields_invalid")
    return value


def _text(value: object, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError("research_evidence_text_invalid")
    return value.strip()


def _source(value: object) -> str:
    text = _text(value, 2000)
    parsed = urlsplit(text)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("research_evidence_source_invalid")
    return text


def _time(value: object, now: datetime) -> str:
    if not isinstance(value, str):
        raise ValueError("research_evidence_time_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("research_evidence_time_invalid") from exc
    if parsed.tzinfo is None or parsed > now:
        raise ValueError("research_evidence_time_invalid")
    return parsed.astimezone(UTC).isoformat()


def _number(value: object, *, nonnegative: bool = False) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)) or len(str(value)) > 80:
        raise ValueError("research_evidence_number_invalid")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("research_evidence_number_invalid") from exc
    exponent = number.as_tuple().exponent
    if (
        not number.is_finite()
        or abs(number) > Decimal("1e15")
        or not isinstance(exponent, int)
        or exponent < -28
        or nonnegative
        and number < 0
    ):
        raise ValueError("research_evidence_number_invalid")
    return format(number, "f")


def _rows(value: object, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("research_evidence_rows_invalid")
    return value


def _fact_value(name: str, number: Any) -> Any:
    if name in _BOOL_FACTS:
        if type(number) is not bool:
            raise ValueError("research_evidence_boolean_invalid")
    elif name in _STRING_FACTS:
        number = _text(number)
        if name == "maturity_date":
            parsed = datetime.fromisoformat(number.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("research_evidence_time_invalid")
            number = parsed.astimezone(UTC).isoformat()
    else:
        number = _number(number)
    return number


def _facts(value: object, now: datetime) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value) <= _FACT_KEYS:
        raise ValueError("research_evidence_fact_invalid")
    result = {}
    for name, raw in value.items():
        row = _object(raw, {"value", "available_at", "source_url"})
        number = _fact_value(name, row["value"])
        result[name] = {
            "value": number,
            "available_at": _time(row["available_at"], now),
            "source_url": _source(row["source_url"]),
        }
    return result


def _constituents(value: object, now: datetime) -> list[dict[str, Any]]:
    result = []
    for raw in _rows(value, 1000):
        row = _object(
            raw, {"issuer_id", "group_id", "sector", "weight_percent", "available_at", "source_url"}
        )
        result.append(
            {
                **{key: _text(row[key]) for key in ("issuer_id", "group_id", "sector")},
                "weight_percent": _number(row["weight_percent"], nonnegative=True),
                "available_at": _time(row["available_at"], now),
                "source_url": _source(row["source_url"]),
            }
        )
    if result and sum(Decimal(row["weight_percent"]) for row in result) != 100:
        raise ValueError("research_fund_weights_must_total_100")
    return result


def _cashflows(value: object, now: datetime) -> list[dict[str, Any]]:
    result = []
    for raw in _rows(value, 1000):
        if isinstance(raw, dict):
            raw = {"kind": "income", **raw}
        row = _object(
            raw, {"entitlement_at", "paid_at", "amount_per_unit_rub", "source_url", "kind"}
        )
        if row["kind"] not in {"income", "principal"}:
            raise ValueError("research_cashflow_kind_invalid")
        entitlement, paid = _time(row["entitlement_at"], now), _time(row["paid_at"], now)
        if paid < entitlement:
            raise ValueError("research_cashflow_order_invalid")
        result.append(
            {
                "entitlement_at": entitlement,
                "paid_at": paid,
                "amount_per_unit_rub": _number(row["amount_per_unit_rub"], nonnegative=True),
                "source_url": _source(row["source_url"]),
                "kind": row["kind"],
            }
        )
    identities = [(row["entitlement_at"], row["paid_at"], row["kind"]) for row in result]
    if len(set(identities)) != len(result):
        raise ValueError("research_cashflow_duplicate")
    return result


def _coverage(value: object, now: datetime) -> dict[str, Any] | None:
    if value is None:
        return None
    row = _object(
        value,
        {
            "from",
            "to",
            "cashflows_complete",
            "corporate_actions_complete",
            "lot_history_complete",
            "source_url",
        },
    )
    begin, end = _time(row["from"], now), _time(row["to"], now)
    flags = {
        key: row[key]
        for key in ("cashflows_complete", "corporate_actions_complete", "lot_history_complete")
    }
    if begin >= end or any(type(value) is not bool for value in flags.values()):
        raise ValueError("research_coverage_invalid")
    return {"from": begin, "to": end, **flags, "source_url": _source(row["source_url"])}


def _factors(value: object, now: datetime) -> list[dict[str, Any]]:
    result = []
    for raw in _rows(value, 1100):
        row = _object(
            raw, {"time", "available_at", "growth_change", "inflation_change", "source_url"}
        )
        at, available = _time(row["time"], now), _time(row["available_at"], now)
        if available < at:
            raise ValueError("research_factor_availability_invalid")
        result.append(
            {
                "time": at,
                "available_at": available,
                "growth_change": _number(row["growth_change"]),
                "inflation_change": _number(row["inflation_change"]),
                "source_url": _source(row["source_url"]),
            }
        )
    if len({row["time"][:10] for row in result}) != len(result):
        raise ValueError("research_factor_date_duplicate")
    return result


def _splits(value: object, now: datetime) -> list[dict[str, Any]]:
    result = []
    for raw in _rows(value, 200):
        row = _object(raw, {"time", "ratio", "source_url"})
        ratio = _number(row["ratio"], nonnegative=True)
        if Decimal(ratio) == 0:
            raise ValueError("research_split_ratio_invalid")
        result.append(
            {
                "time": _time(row["time"], now),
                "ratio": ratio,
                "source_url": _source(row["source_url"]),
            }
        )
    if len({row["time"] for row in result}) != len(result):
        raise ValueError("research_split_duplicate")
    return sorted(result, key=lambda row: row["time"])


def _bond_valuations(value: object, now: datetime) -> list[dict[str, Any]]:
    result = []
    amounts = {"nominal_rub", "accrued_interest_open_rub", "accrued_interest_close_rub"}
    for raw in _rows(value, 1100):
        row = _object(raw, {"time", "source_url", *amounts})
        values = {key: _number(row[key], nonnegative=True) for key in amounts}
        if Decimal(values["nominal_rub"]) == 0:
            raise ValueError("research_bond_nominal_invalid")
        result.append(
            {"time": _time(row["time"], now), **values, "source_url": _source(row["source_url"])}
        )
    if len({row["time"][:10] for row in result}) != len(result):
        raise ValueError("research_bond_date_duplicate")
    return sorted(result, key=lambda row: row["time"])


def normalize_research_evidence(value: object, *, now: datetime | None = None) -> dict[str, Any]:
    """Strict import; past availability is a user assertion, receipt is recorded separately."""
    observed = now or datetime.now(UTC)
    document = _object(value, {"assets"})
    assets = []
    for raw in _rows(document["assets"], 100):
        if isinstance(raw, dict):
            raw = {"factors": [], "splits": [], "bond_valuations": [], **raw}
        row = _object(
            raw,
            {
                "instrument_uid",
                "facts",
                "constituents",
                "cashflows",
                "coverage",
                "corporate_action_dates",
                "factors",
                "splits",
                "bond_valuations",
            },
        )
        assets.append(
            {
                "instrument_uid": _text(row["instrument_uid"]),
                "facts": _facts(row["facts"], observed),
                "constituents": _constituents(row["constituents"], observed),
                "cashflows": _cashflows(row["cashflows"], observed),
                "coverage": _coverage(row["coverage"], observed),
                "corporate_action_dates": sorted(
                    {_time(item, observed) for item in _rows(row["corporate_action_dates"], 200)}
                ),
                "factors": _factors(row["factors"], observed),
                "splits": _splits(row["splits"], observed),
                "bond_valuations": _bond_valuations(row["bond_valuations"], observed),
            }
        )
    if len({row["instrument_uid"] for row in assets}) != len(assets):
        raise ValueError("research_evidence_duplicate_instrument")
    result = {"assets": assets}
    # Standard JSON separators include the same structural spaces as JSONB::text;
    # a document admitted here must also fit the database representation.
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_EVIDENCE_DOCUMENT_BYTES:
        raise ValueError("research_evidence_too_large")
    return result


class ResearchStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @contextmanager
    def _transaction(self, user_id: UUID) -> Iterator[Any]:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (live_execution_lock_key(user_id),),
            )
            cur.execute("SELECT set_config('omnicio.user_id', %s, true)", (str(user_id),))
            cur.execute(
                "SELECT id FROM users WHERE id = %s AND status = 'active' FOR SHARE", (user_id,)
            )
            if cur.fetchone() is None:
                raise ResearchNotFound("research_user_unavailable")
            yield cur

    @staticmethod
    def _evidence(cur: Any, user_id: UUID) -> dict[str, Any]:
        cur.execute(
            "SELECT version, document, received_at FROM strategy_research_evidence "
            "WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else {"version": 0, "document": {"assets": []}, "received_at": None}

    def evidence(self, user_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            return {
                **self._evidence(cur, user_id),
                "provenance": "user_supplied",
                "independently_verified": False,
            }

    def save_evidence(
        self, user_id: UUID, document: object, *, expected_version: int
    ) -> dict[str, Any]:
        normalized = normalize_research_evidence(document)
        with self._transaction(user_id) as cur:
            current = self._evidence(cur, user_id)
            if type(expected_version) is not int or expected_version != current["version"]:
                raise SettingsVersionConflict("settings_version_conflict")
            if current["document"] == normalized:
                return {**current, "provenance": "user_supplied", "independently_verified": False}
            cur.execute(
                "INSERT INTO strategy_research_evidence (user_id, version, document) "
                "VALUES (%s, %s, %s::jsonb) ON CONFLICT (user_id) DO UPDATE SET "
                "version = EXCLUDED.version, document = EXCLUDED.document, "
                "received_at = now() RETURNING version, document, received_at",
                (user_id, expected_version + 1, _json(normalized)),
            )
            return {
                **dict(cur.fetchone()),
                "provenance": "user_supplied",
                "independently_verified": False,
            }

    def save_run(
        self,
        user_id: UUID,
        *,
        result: Mapping[str, Any],
        inputs: Mapping[str, Any],
        account_id: str,
        environment: str,
        connection_verified_at: datetime,
        strategy_version: int,
        evidence_version: int,
        request_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Archive exactly the evaluated inputs; recheck mutable context under a short lock."""
        encoded_result, encoded_inputs = _json(result), _json(inputs)
        if any(
            len(value.encode()) > MAX_ARCHIVE_DOCUMENT_BYTES
            for value in (encoded_result, encoded_inputs)
        ):
            raise ValueError("research_archive_too_large")
        ident = uuid4()
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT account_id, environment, verified_at FROM tbank_connection "
                "WHERE user_id = %s FOR SHARE",
                (user_id,),
            )
            connection = cur.fetchone()
            cur.execute(
                "SELECT version, document FROM strategy_drafts WHERE user_id = %s FOR SHARE",
                (user_id,),
            )
            strategy = cur.fetchone()
            if (
                not connection
                or (connection["account_id"], connection["environment"])
                != (account_id, environment)
                or connection["verified_at"] != connection_verified_at
                or not strategy
                or strategy["version"] != strategy_version
                or document_hash(strategy["document"]) != result["strategy_hash"]
                or self._evidence(cur, user_id)["version"] != evidence_version
            ):
                raise SettingsVersionConflict("research_context_changed")
            capacity = self._capacity(cur, user_id)
            cur.execute(
                "SELECT octet_length(%s::jsonb::text) AS result_bytes, "
                "octet_length(%s::jsonb::text) AS input_bytes",
                (encoded_result, encoded_inputs),
            )
            sizes = cur.fetchone()
            if max(sizes.values()) > MAX_ARCHIVE_DOCUMENT_BYTES:
                raise ValueError("research_archive_too_large")
            if capacity["runs_used"] >= capacity["runs_limit"]:
                raise ValueError("research_archive_capacity")
            if (
                capacity["storage_used_bytes"] + sum(sizes.values())
                > capacity["storage_limit_bytes"]
            ):
                raise ValueError("research_archive_storage_capacity")
            cur.execute(
                "INSERT INTO strategy_research_runs (user_id, id, account_id, environment, "
                "strategy_version, evidence_version, data_hash, result, inputs) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb) "
                "RETURNING id, created_at",
                (
                    user_id,
                    ident,
                    account_id,
                    environment,
                    strategy_version,
                    evidence_version,
                    result["data_hash"],
                    encoded_result,
                    encoded_inputs,
                ),
            )
            saved = cur.fetchone()
            if request_id is not None:
                cur.execute(
                    "UPDATE strategy_research_requests SET status = 'completed', run_id = %s, "
                    "updated_at = clock_timestamp() WHERE user_id = %s AND id = %s "
                    "AND status = 'running' AND expires_at > clock_timestamp() RETURNING id",
                    (ident, user_id, request_id),
                )
                if cur.fetchone() is None:
                    raise SettingsVersionConflict("research_request_expired")
            return {
                "id": str(saved["id"]),
                "created_at": saved["created_at"],
                "data_hash": result["data_hash"],
                "replay_available": True,
            }

    @staticmethod
    def _capacity(cur: Any, user_id: UUID) -> dict[str, int]:
        from .billing import entitlement_limits

        limits = entitlement_limits(cur, user_id)
        cur.execute(
            "SELECT count(*) AS total, coalesce(sum(octet_length(result::text) "
            "+ octet_length(inputs::text)), 0) AS bytes "
            "FROM strategy_research_runs WHERE user_id = %s",
            (user_id,),
        )
        observed = cur.fetchone()
        return {
            "runs_used": int(observed["total"]),
            "runs_limit": limits["research_runs"],
            "storage_used_bytes": int(observed["bytes"]),
            "storage_limit_bytes": limits["research_storage_bytes"],
        }

    def capacity(self, user_id: UUID) -> dict[str, int]:
        """Expiry restricts new archive writes; reading/exporting/deleting stays available."""
        with self._transaction(user_id) as cur:
            return self._capacity(cur, user_id)

    @staticmethod
    def _expire_requests(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "UPDATE strategy_research_requests SET status = 'expired', "
            "error_code = 'research_request_expired', updated_at = clock_timestamp() "
            "WHERE user_id = %s AND status = 'running' AND expires_at <= clock_timestamp()",
            (user_id,),
        )

    def begin_request(self, user_id: UUID, request_id: UUID, input_hash: str) -> dict[str, Any]:
        """Deduplicate an attempt; terminal unlinked tombstones are kept for 30 days."""
        with self._transaction(user_id) as cur:
            self._expire_requests(cur, user_id)
            cur.execute(
                "DELETE FROM strategy_research_requests WHERE user_id = %s "
                "AND status IN ('failed', 'expired', 'deleted') AND run_id IS NULL "
                "AND updated_at < clock_timestamp() - interval '30 days'",
                (user_id,),
            )
            cur.execute(
                _REQUEST_SELECT + ", input_hash "
                "FROM strategy_research_requests WHERE user_id = %s AND id = %s",
                (user_id, request_id),
            )
            existing = cur.fetchone()
            if existing is not None:
                if existing["input_hash"] != input_hash:
                    raise SettingsVersionConflict("research_request_parameters_changed")
                return {key: value for key, value in existing.items() if key != "input_hash"}
            cur.execute(
                "SELECT count(*) AS count FROM strategy_research_requests WHERE user_id = %s",
                (user_id,),
            )
            if cur.fetchone()["count"] >= _REQUEST_LIMIT:
                raise ValueError("research_request_capacity")
            cur.execute(
                "INSERT INTO strategy_research_requests(user_id, id, input_hash, status) "
                "VALUES (%s, %s, %s, 'running') RETURNING " + _REQUEST_FIELDS,
                (user_id, request_id, input_hash),
            )
            return {**dict(cur.fetchone()), "created": True}

    def request(self, user_id: UUID, request_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            self._expire_requests(cur, user_id)
            cur.execute(
                _REQUEST_SELECT + " FROM strategy_research_requests WHERE user_id = %s AND id = %s",
                (user_id, request_id),
            )
            record = cur.fetchone()
            if record is None:
                raise ResearchNotFound("research_request_not_found")
            return dict(record)

    def fail_request(self, user_id: UUID, request_id: UUID, error_code: str) -> None:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE strategy_research_requests SET status = 'failed', error_code = %s, "
                "updated_at = clock_timestamp() WHERE user_id = %s AND id = %s "
                "AND status = 'running'",
                (error_code, user_id, request_id),
            )

    def runs(self, user_id: UUID, *, limit: int = 50) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self.runs_page(user_id, limit=limit)["items"])

    def runs_page(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
        cursor: UUID | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= MAX_RESEARCH_RUN_PAGE:
            raise ValueError("research_list_limit_invalid")
        with self._transaction(user_id) as cur:
            boundary = ""
            values: list[Any] = [user_id]
            if cursor is not None:
                cur.execute(
                    "SELECT created_at, id FROM strategy_research_runs "
                    "WHERE user_id = %s AND id = %s",
                    (user_id, cursor),
                )
                record = cur.fetchone()
                if record is None:
                    raise ResearchNotFound("research_cursor_not_found")
                boundary = "AND (created_at, id) < (%s, %s) "
                values.extend((record["created_at"], record["id"]))
            values.append(limit + 1)
            cur.execute(
                "SELECT id, account_id, environment, strategy_version, evidence_version, "
                "data_hash, created_at, result->>'status' AS status, "
                "result->'period' AS period, result->'metrics' AS metrics "
                "FROM strategy_research_runs WHERE user_id = %s "
                + boundary
                + "ORDER BY created_at DESC, id DESC LIMIT %s",
                values,
            )
            records = [dict(row) for row in cur.fetchall()]
            self._expire_requests(cur, user_id)
            cur.execute(
                _REQUEST_SELECT + " FROM strategy_research_requests "
                "WHERE user_id = %s ORDER BY (status = 'running') DESC, "
                "created_at DESC, id DESC LIMIT 1",
                (user_id,),
            )
            recent = cur.fetchone()
            return {
                "items": records[:limit],
                "next_cursor": str(records[limit - 1]["id"]) if len(records) > limit else None,
                "capacity": self._capacity(cur, user_id),
                "recent_request": dict(recent) if recent else None,
            }

    def observed_facts(
        self,
        user_id: UUID,
        *,
        account_id: str,
        environment: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Reuse only immutable automatically observed facts, at their actual receipt times."""
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT asset->'candidate'->>'instrument_uid' AS uid, "
                "asset->'provider_observations'->'facts' AS facts "
                "FROM strategy_research_runs, LATERAL jsonb_array_elements(inputs->'assets') asset "
                "WHERE user_id = %s AND account_id = %s AND environment = %s "
                "AND jsonb_typeof(asset->'provider_observations'->'facts') = 'object' "
                "ORDER BY created_at, id",
                (user_id, account_id, environment),
            )
            result: dict[str, dict[str, list[dict[str, Any]]]] = {}
            for record in cur.fetchall():
                history = result.setdefault(record["uid"], {})
                for name, fact in record["facts"].items():
                    observations = history.setdefault(name, [])
                    # Keep the first observed availability when a value repeats.
                    if not observations or (
                        observations[-1]["value"],
                        observations[-1]["source_url"],
                    ) != (fact["value"], fact["source_url"]):
                        observations.append(fact)
            return result

    def run(self, user_id: UUID, run_id: UUID) -> dict[str, Any]:
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, account_id, environment, strategy_version, evidence_version, "
                "data_hash, result, inputs, created_at FROM strategy_research_runs "
                "WHERE user_id = %s AND id = %s",
                (user_id, run_id),
            )
            row = cur.fetchone()
            if row is None:
                raise ResearchNotFound("research_run_not_found")
            return dict(row)

    def delete_run(self, user_id: UUID, run_id: UUID) -> None:
        with self._transaction(user_id) as cur:
            cur.execute(
                "UPDATE strategy_research_requests SET status = 'deleted', run_id = NULL, "
                "error_code = 'research_archive_deleted', updated_at = clock_timestamp() "
                "WHERE user_id = %s AND run_id = %s",
                (user_id, run_id),
            )
            cur.execute(
                "DELETE FROM strategy_research_runs WHERE user_id = %s AND id = %s RETURNING id",
                (user_id, run_id),
            )
            if cur.fetchone() is None:
                raise ResearchNotFound("research_run_not_found")
