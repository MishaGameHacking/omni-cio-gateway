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
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from .db import Database, live_execution_lock_key
from .portfolio_store import SettingsVersionConflict
from .strategy import document_hash

MAX_SAVED_RUNS = 200
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


def _facts(value: object, now: datetime) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value) <= _FACT_KEYS:
        raise ValueError("research_evidence_fact_invalid")
    result = {}
    for name, raw in value.items():
        row = _object(raw, {"value", "available_at", "source_url"})
        number = row["value"]
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
    if len(_json(result).encode()) > 1_000_000:
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
    ) -> dict[str, Any]:
        """Archive exactly the evaluated inputs; recheck mutable context under a short lock."""
        if any(len(_json(value).encode()) > 4_000_000 for value in (result, inputs)):
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
            cur.execute(
                "SELECT count(*) AS total FROM strategy_research_runs WHERE user_id = %s",
                (user_id,),
            )
            if cur.fetchone()["total"] >= MAX_SAVED_RUNS:
                raise ValueError("research_archive_capacity")
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
                    _json(result),
                    _json(inputs),
                ),
            )
            saved = cur.fetchone()
            return {
                "id": str(saved["id"]),
                "created_at": saved["created_at"],
                "data_hash": result["data_hash"],
                "replay_available": True,
            }

    def runs(self, user_id: UUID, *, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= MAX_SAVED_RUNS:
            raise ValueError("research_list_limit_invalid")
        with self._transaction(user_id) as cur:
            cur.execute(
                "SELECT id, account_id, environment, strategy_version, evidence_version, "
                "data_hash, created_at, result->>'status' AS status, "
                "result->'period' AS period, result->'metrics' AS metrics "
                "FROM strategy_research_runs WHERE user_id = %s "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (user_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]

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
                "DELETE FROM strategy_research_runs WHERE user_id = %s AND id = %s RETURNING id",
                (user_id, run_id),
            )
            if cur.fetchone() is None:
                raise ResearchNotFound("research_run_not_found")
