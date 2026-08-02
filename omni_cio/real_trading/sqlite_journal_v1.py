from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from typing import Any, cast

from .journal_v1 import JournalDailyCapExceeded, JournalStateConflict, MOSCOW
from .models_v1 import ProposalState, RealTradeProposalV1


_SCHEMA_VERSION = "1"
_COUNTED_STATES = frozenset({"submitting", "submitted", "unknown"})
_VALID_STATES = frozenset(
    {"prepared", "submitting", "submitted", "failed", "unknown", "expired"}
)


class JournalIntegrityError(RuntimeError):
    pass


class JournalStorageError(RuntimeError):
    pass


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _aware_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise JournalIntegrityError(f"invalid datetime: {field}") from exc
    if parsed.tzinfo is None:
        raise JournalIntegrityError(f"naive datetime: {field}")
    return parsed


def _optional_datetime(value: Any, field: str) -> datetime | None:
    return None if value is None else _aware_datetime(value, field)


def _encode(proposal: RealTradeProposalV1) -> str:
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
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode(raw: str) -> RealTradeProposalV1:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("payload must be an object")
        state = str(data["state"])
        direction = str(data["direction"])
        proposal = RealTradeProposalV1(
            proposal_id=str(data["proposal_id"]),
            order_id=str(data["order_id"]),
            account_id=str(data["account_id"]),
            instrument_uid=str(data["instrument_uid"]),
            ticker=str(data["ticker"]),
            isin=None if data.get("isin") is None else str(data["isin"]),
            direction=cast(Any, direction),
            quantity_lots=int(data["quantity_lots"]),
            limit_price=Decimal(str(data["limit_price"])),
            rationale=str(data["rationale"]),
            preview_total_rub=Decimal(str(data["preview_total_rub"])),
            preview_commission_rub=Decimal(str(data["preview_commission_rub"])),
            available_lots=int(data["available_lots"]),
            market_retrieved_at=_aware_datetime(
                data["market_retrieved_at"], "market_retrieved_at"
            ),
            created_at=_aware_datetime(data["created_at"], "created_at"),
            expires_at=_aware_datetime(data["expires_at"], "expires_at"),
            confirmation_code=str(data["confirmation_code"]),
            state=cast(ProposalState, state),
            submitted_at=_optional_datetime(data.get("submitted_at"), "submitted_at"),
            broker_response_json=(
                None
                if data.get("broker_response_json") is None
                else str(data["broker_response_json"])
            ),
            failure_code=(
                None if data.get("failure_code") is None else str(data["failure_code"])
            ),
            failure_message=(
                None
                if data.get("failure_message") is None
                else str(data["failure_message"])
            ),
        )
    except (ArithmeticError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise JournalIntegrityError("invalid durable proposal payload") from exc
    if proposal.state not in _VALID_STATES or proposal.direction not in {"BUY", "SELL"}:
        raise JournalIntegrityError("invalid durable proposal state or direction")
    if proposal.quantity_lots < 1 or proposal.limit_price <= 0:
        raise JournalIntegrityError("invalid durable proposal quantity or price")
    if proposal.preview_total_rub <= 0 or proposal.preview_commission_rub < 0:
        raise JournalIntegrityError("invalid durable proposal preview")
    return proposal


class SQLiteRealExecutionJournalV1:
    """Durable, HMAC-authenticated proposal journal for the real-money contour."""

    durable = True

    def __init__(self, path: str | Path, *, gateway_secret: str) -> None:
        self._path = Path(path)
        secret = gateway_secret.strip()
        if not secret:
            raise JournalStorageError("gateway secret is required")
        if not self._path.is_absolute():
            raise JournalStorageError("journal path must be absolute")
        if not self._path.parent.is_dir():
            raise JournalStorageError("journal parent directory does not exist")
        self._key = hmac.new(
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
            connection = sqlite3.connect(self._path, timeout=10, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=10000")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA journal_mode=WAL")
            return connection
        except sqlite3.Error as exc:
            raise JournalStorageError("cannot open durable journal") from exc

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS journal_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS proposals(
                    proposal_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    row_mac TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            row = connection.execute(
                "SELECT value FROM journal_meta WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO journal_meta(key,value) VALUES('schema_version',?)",
                    (_SCHEMA_VERSION,),
                )
            elif str(row["value"]) != _SCHEMA_VERSION:
                raise JournalStorageError("unsupported journal schema version")

    def _mac(self, proposal_id: str, revision: int, payload: str) -> str:
        message = f"{proposal_id}\n{revision}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _verified(self, row: sqlite3.Row) -> RealTradeProposalV1:
        proposal_id = str(row["proposal_id"])
        payload = str(row["payload_json"])
        revision = int(row["revision"])
        if not hmac.compare_digest(
            str(row["row_mac"]), self._mac(proposal_id, revision, payload)
        ):
            raise JournalIntegrityError("durable journal integrity check failed")
        proposal = _decode(payload)
        if proposal.proposal_id != proposal_id:
            raise JournalIntegrityError("proposal id mismatch")
        return proposal

    def _select(
        self, connection: sqlite3.Connection, proposal_id: str
    ) -> tuple[sqlite3.Row, RealTradeProposalV1]:
        row = connection.execute(
            "SELECT proposal_id,payload_json,row_mac,revision FROM proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError("real-trading proposal not found")
        return row, self._verified(row)

    def put(self, proposal: RealTradeProposalV1) -> None:
        payload = _encode(proposal)
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO proposals(proposal_id,payload_json,row_mac,revision,updated_at) VALUES(?,?,?,?,?)",
                    (
                        proposal.proposal_id,
                        payload,
                        self._mac(proposal.proposal_id, 0, payload),
                        0,
                        proposal.created_at.isoformat(),
                    ),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise RuntimeError("duplicate proposal id") from exc
        except sqlite3.Error as exc:
            raise JournalStorageError("failed to persist proposal") from exc

    def get(self, proposal_id: str) -> RealTradeProposalV1:
        with self._connect() as connection:
            return self._select(connection, proposal_id)[1]

    def _write(
        self,
        connection: sqlite3.Connection,
        proposal: RealTradeProposalV1,
        revision: int,
    ) -> RealTradeProposalV1:
        new_revision = revision + 1
        payload = _encode(proposal)
        cursor = connection.execute(
            """
            UPDATE proposals SET payload_json=?,row_mac=?,revision=?,updated_at=?
            WHERE proposal_id=? AND revision=?
            """,
            (
                payload,
                self._mac(proposal.proposal_id, new_revision, payload),
                new_revision,
                datetime.now(tz=proposal.created_at.tzinfo).isoformat(),
                proposal.proposal_id,
                revision,
            ),
        )
        if cursor.rowcount != 1:
            raise JournalStateConflict("proposal revision changed concurrently")
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
                row, current = self._select(connection, proposal_id)
                if current.state not in allowed_from:
                    raise JournalStateConflict(f"proposal state conflict: {current.state}")
                updated = replace(current, state=state, **changes)
                result = self._write(connection, updated, int(row["revision"]))
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    def _daily_total(self, connection: sqlite3.Connection, day: date) -> Decimal:
        total = Decimal("0")
        rows = connection.execute(
            "SELECT proposal_id,payload_json,row_mac,revision FROM proposals"
        ).fetchall()
        for row in rows:
            proposal = self._verified(row)
            if proposal.state not in _COUNTED_STATES or proposal.submitted_at is None:
                continue
            if proposal.submitted_at.astimezone(MOSCOW).date() == day:
                total += proposal.preview_total_rub
        return total

    def submitted_notional_for_moscow_date(self, day: date) -> Decimal:
        with self._connect() as connection:
            return self._daily_total(connection, day)

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
                row, current = self._select(connection, proposal_id)
                if current.state != "prepared":
                    raise JournalStateConflict(f"proposal state conflict: {current.state}")
                if (
                    self._daily_total(connection, submitted_at.astimezone(MOSCOW).date())
                    + current.preview_total_rub
                    > max_daily_rub
                ):
                    raise JournalDailyCapExceeded("daily submission cap exceeded")
                updated = replace(
                    current,
                    state=cast(ProposalState, "submitting"),
                    submitted_at=submitted_at,
                )
                result = self._write(connection, updated, int(row["revision"]))
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise

    def integrity_check(self) -> int:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT proposal_id,payload_json,row_mac,revision FROM proposals"
            ).fetchall()
            for row in rows:
                self._verified(row)
            return len(rows)
