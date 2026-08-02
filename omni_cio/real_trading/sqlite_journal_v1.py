from __future__ import annotations

from dataclasses import asdict, replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from typing import Any, cast

from .journal_v1 import (
    JournalDailyCapExceeded,
    JournalStateConflict,
    MOSCOW,
)
from .models_v1 import ProposalState, RealTradeProposalV1


SCHEMA_VERSION = 1


class JournalIntegrityError(RuntimeError):
    """Raised when durable journal content fails its authenticated integrity check."""


class JournalStorageError(RuntimeError):
    """Raised when the durable journal cannot be initialized or used safely."""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise JournalIntegrityError(f"invalid journal datetime field: {field}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise JournalIntegrityError(f"invalid journal datetime field: {field}") from exc
    if parsed.tzinfo is None:
        raise JournalIntegrityError(f"journal datetime must be timezone-aware: {field}")
    return parsed


def _parse_optional_datetime(value: Any, *, field: str) -> datetime | None:
    if value is None:
        return None
    return _parse_datetime(value, field=field)


def _serialize(proposal: RealTradeProposalV1) -> str:
    payload = {
        "proposal_id": proposal.proposal_id,
        "order_id": proposal.order_id,
        "account_id": proposal.account_id,
        "instrument_uid": proposal.instrument_uid,
        "ticker": proposal.ticker,
        "isin": proposal.isin,
        "direction": proposal.direction,
        "quantity_lots": proposal.quantity_lots,
        "limit_price": format(proposal.limit_price, "f"),
        "rationale": proposal.rationale,
        "preview_total_rub": format(proposal.preview_total_rub, "f"),
        "preview_commission_rub": format(proposal.preview_commission_rub, "f"),
        "available_lots": proposal.available_lots,
        "market_retrieved_at": _iso(proposal.market_retrieved_at),
        "created_at": _iso(proposal.created_at),
        "expires_at": _iso(proposal.expires_at),
        "confirmation_code": proposal.confirmation_code,
        "state": proposal.state,
        "submitted_at": _iso(proposal.submitted_at),
        "broker_response_json": proposal.broker_response_json,
        "failure_code": proposal.failure_code,
        "failure_message": proposal.failure_message,
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _deserialize(payload_json: str) -> RealTradeProposalV1:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise JournalIntegrityError("journal payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise JournalIntegrityError("journal payload must be a JSON object")
    try:
        direction = str(payload["direction"])
        state = str(payload["state"])
        proposal = RealTradeProposalV1(
            proposal_id=str(payload["proposal_id"]),
            order_id=str(payload["order_id"]),
            account_id=str(payload["account_id"]),
            instrument_uid=str(payload["instrument_uid"]),
            ticker=str(payload["ticker"]),
            isin=(None if payload.get("isin") is None else str(payload["isin"])),
            direction=cast(Any, direction),
            quantity_lots=int(payload["quantity_lots"]),
            limit_price=Decimal(str(payload["limit_price"])),
            rationale=str(payload["rationale"]),
            preview_total_rub=Decimal(str(payload["preview_total_rub"])),
            preview_commission_rub=Decimal(str(payload["preview_commission_rub"])),
            available_lots=int(payload["available_lots"]),
            market_retrieved_at=_parse_datetime(
                payload.get("market_retrieved_at"), field="market_retrieved_at"
            ),
            created_at=_parse_datetime(payload.get("created_at"), field="created_at"),
            expires_at=_parse_datetime(payload.get("expires_at"), field="expires_at"),
            confirmation_code=str(payload["confirmation_code"]),
            state=cast(ProposalState, state),
            submitted_at=_parse_optional_datetime(
                payload.get("submitted_at"), field="submitted_at"
            ),
            broker_response_json=(
                None
                if payload.get("broker_response_json") is None
                else str(payload["broker_response_json"])
            ),
            failure_code=(
                None if payload.get("failure_code") is None else str(payload["failure_code"])
            ),
            failure_message=(
                None
                if payload.get("failure_message") is None
                else str(payload["failure_message"])
            ),
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise JournalIntegrityError("journal proposal payload is invalid") from exc

    if proposal.direction not in {"BUY", "SELL"}:
        raise JournalIntegrityError("journal proposal direction is invalid")
    if proposal.state not in {
        "prepared",
        "submitting",
        "submitted",
        "failed",
        "unknown",
        "expired",
    }:
        raise JournalIntegrityError("journal proposal state is invalid")
    if proposal.quantity_lots < 1:
        raise JournalIntegrityError("journal proposal quantity is invalid")
    if proposal.limit_price <= 0 or proposal.preview_total_rub <= 0:
        raise JournalIntegrityError("journal proposal monetary fields are invalid")
    return proposal


class SQLiteRealExecutionJournalV1:
    """Authenticated durable journal for the real-money execution contour.

    The database is suitable only when its path is backed by persistent storage.
    Route wiring is responsible for enforcing the production mount policy. Every
    proposal row carries an HMAC derived from the gateway secret so accidental or
    offline row modification fails closed before any recovered proposal is used.
    """

    durable = True

    def __init__(self, path: str | Path, *, gateway_secret: str) -> None:
        secret = gateway_secret.strip()
        if not secret:
            raise JournalStorageError("gateway secret is required for journal integrity")
        self._path = Path(path)
        if not self._path.is_absolute():
            raise JournalStorageError("real execution journal path must be absolute")
        parent = self._path.parent
        if not parent.exists() or not parent.is_dir():
            raise JournalStorageError("real execution journal parent directory is missing")
        self._integrity_key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-real-execution-journal-v1",
            hashlib.sha256,
        ).digest()
        self._initialize()

    @property
    def path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self._path,
                timeout=10.0,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA journal_mode = WAL")
            return connection
        except sqlite3.Error as exc:
            raise JournalStorageError("unable to open durable real execution journal") from exc

    def _initialize(self) -> None:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS journal_meta (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS proposals (
                        proposal_id TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        row_mac TEXT NOT NULL,
                        revision INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                row = connection.execute(
                    "SELECT value FROM journal_meta WHERE key = 'schema_version'"
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO journal_meta(key, value) VALUES('schema_version', ?)",
                        (str(SCHEMA_VERSION),),
                    )
                elif str(row["value"]) != str(SCHEMA_VERSION):
                    raise JournalStorageError("unsupported real execution journal schema")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _mac(self, proposal_id: str, revision: int, payload_json: str) -> str:
        canonical = f"{proposal_id}\n{revision}\n{payload_json}".encode("utf-8")
        return hmac.new(self._integrity_key, canonical, hashlib.sha256).hexdigest()

    def _verified_from_row(self, row: sqlite3.Row) -> RealTradeProposalV1:
        proposal_id = str(row["proposal_id"])
        payload_json = str(row["payload_json"])
        revision = int(row["revision"])
        expected = self._mac(proposal_id, revision, payload_json)
        supplied = str(row["row_mac"])
        if not hmac.compare_digest(expected, supplied):
            raise JournalIntegrityError("real execution journal integrity check failed")
        proposal = _deserialize(payload_json)
        if proposal.proposal_id != proposal_id:
            raise JournalIntegrityError("journal proposal id mismatch")
        return proposal

    def _select_verified(
        self, connection: sqlite3.Connection, proposal_id: str
    ) -> tuple[sqlite3.Row, RealTradeProposalV1]:
        row = connection.execute(
            "SELECT proposal_id, payload_json, row_mac, revision FROM proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError("real-trading proposal not found")
        return row, self._verified_from_row(row)

    def put(self, proposal: RealTradeProposalV1) -> None:
        payload_json = _serialize(proposal)
        revision = 0
        row_mac = self._mac(proposal.proposal_id, revision, payload_json)
        now = datetime.now(tz=proposal.created_at.tzinfo).isoformat()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO proposals(
                        proposal_id, payload_json, row_mac, revision, created_at, updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proposal.proposal_id,
                        payload_json,
                        row_mac,
                        revision,
                        proposal.created_at.isoformat(),
                        now,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise RuntimeError("duplicate proposal id") from exc
            except sqlite3.Error as exc:
                connection.rollback()
                raise JournalStorageError("failed to persist real-trading proposal") from exc

    def get(self, proposal_id: str) -> RealTradeProposalV1:
        with self._connect() as connection:
            _, proposal = self._select_verified(connection, proposal_id)
            return proposal

    def _write_transition(
        self,
        connection: sqlite3.Connection,
        *,
        proposal: RealTradeProposalV1,
        previous_revision: int,
    ) -> RealTradeProposalV1:
        payload_json = _serialize(proposal)
        revision = previous_revision + 1
        row_mac = self._mac(proposal.proposal_id, revision, payload_json)
        updated_at = datetime.now(tz=proposal.created_at.tzinfo).isoformat()
        cursor = connection.execute(
            """
            UPDATE proposals
               SET payload_json = ?, row_mac = ?, revision = ?, updated_at = ?
             WHERE proposal_id = ? AND revision = ?
            """,
            (
                payload_json,
                row_mac,
                revision,
                updated_at,
                proposal.proposal_id,
                previous_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise JournalStateConflict("proposal journal revision changed concurrently")
        return proposal

    def transition(
        self,
        proposal_id: str,
        *,
        allowed_from: frozenset[str],
        state: ProposalState,
        **changes: Any,
    ) -> RealTradeProposalV1:
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row, current = self._select_verified(connection, proposal_id)
                if current.state not in allowed_from:
                    raise JournalStateConflict(
                        f"proposal state conflict: {current.state}"
                    )
                updated = replace(current, state=state, **changes)
                result = self._write_transition(
                    connection,
                    proposal=updated,
                    previous_revision=int(row["revision"]),
                )
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    def _submitted_notional_for_moscow_date_in_connection(
        self,
        connection: sqlite3.Connection,
        day: date,
    ) -> Decimal:
        total = Decimal("0")
        rows = connection.execute(
            "SELECT proposal_id, payload_json, row_mac, revision FROM proposals"
        ).fetchall()
        for row in rows:
            proposal = self._verified_from_row(row)
            submitted_at = proposal.submitted_at
            if submitted_at is None:
                continue
            if proposal.state not in {"submitting", "submitted", "unknown"}:
                continue
            if submitted_at.astimezone(MOSCOW).date() == day:
                total += proposal.preview_total_rub
        return total

    def submitted_notional_for_moscow_date(self, day: date) -> Decimal:
        with self._connect() as connection:
            return self._submitted_notional_for_moscow_date_in_connection(connection, day)

    def reserve_submission(
        self,
        proposal_id: str,
        *,
        submitted_at: datetime,
        max_daily_rub: Decimal,
    ) -> RealTradeProposalV1:
        if submitted_at.tzinfo is None:
            raise ValueError("journal timestamps must be timezone-aware")
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row, current = self._select_verified(connection, proposal_id)
                if current.state != "prepared":
                    raise JournalStateConflict(
                        f"proposal state conflict: {current.state}"
                    )
                day = submitted_at.astimezone(MOSCOW).date()
                already = self._submitted_notional_for_moscow_date_in_connection(
                    connection, day
                )
                if already + current.preview_total_rub > max_daily_rub:
                    raise JournalDailyCapExceeded("daily submission cap exceeded")
                updated = replace(
                    current,
                    state=cast(ProposalState, "submitting"),
                    submitted_at=submitted_at,
                )
                result = self._write_transition(
                    connection,
                    proposal=updated,
                    previous_revision=int(row["revision"]),
                )
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    def integrity_check(self) -> int:
        """Verify every stored row and return the number of authenticated proposals."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT proposal_id, payload_json, row_mac, revision FROM proposals"
            ).fetchall()
            for row in rows:
                self._verified_from_row(row)
            return len(rows)
