"""Encrypted, transactional journal for the trusted Windows synthetic verifier.

This is engineering recovery state, not application persistence. No secrets or
provider identifiers are stored as plaintext, including SQLite rollback records.
Loss/restoration of this database requires reconciliation, never automatic APPLY.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import ctypes
from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3

from scripts import timeweb_ipv4_allocation as protocol


_MAX_RECORDS = 256
_MAX_BYTES = 65536
_TABLE = "CREATE TABLE allocation (handle TEXT PRIMARY KEY, sealed BLOB NOT NULL)"


class JournalError(RuntimeError):
    """Never exposes an SQL statement, filesystem path or decrypted record."""


def dpapi(data: bytes, *, decrypt: bool = False) -> bytes:
    """Use CurrentUser DPAPI with integrity checking; prohibit interactive UI."""
    if (
        os.name != "nt"
        or not isinstance(data, bytes)
        or not 0 < len(data) <= _MAX_BYTES
    ):
        raise JournalError("TIMEWEB_JOURNAL_PROTECTION_UNAVAILABLE")
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte))]

    backing = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(backing, ctypes.POINTER(ctypes.c_byte)))
    result = Blob()
    crypto = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        action = crypto.CryptUnprotectData
        action.argtypes = [
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
        second = None
    else:
        action = crypto.CryptProtectData
        action.argtypes = [
            ctypes.POINTER(Blob),
            wintypes.LPCWSTR,
            ctypes.POINTER(Blob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(Blob),
        ]
        second = "Omni-CIO RU-PG-B allocation v1"
    action.restype = wintypes.BOOL
    if not action(
        ctypes.byref(source),
        second,
        None,
        None,
        None,
        1,
        ctypes.byref(result),
    ):
        raise JournalError("TIMEWEB_JOURNAL_PROTECTION_FAILED")
    try:
        if not 0 < result.length <= _MAX_BYTES:
            raise JournalError("TIMEWEB_JOURNAL_PROTECTION_FAILED")
        return ctypes.string_at(result.data, result.length)
    finally:
        kernel.LocalFree(result.data)


def _encode(entry: protocol.Entry) -> bytes:
    payload = {
        "schema": 1,
        "plan": asdict(entry.plan),
        "phase": entry.phase.value,
        "approval_reference": entry.approval_reference,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _decode(raw: bytes, identifier: str) -> protocol.Entry:
    data = json.loads(raw)
    if (
        not isinstance(data, dict)
        or set(data) != {"schema", "plan", "phase", "approval_reference"}
        or type(data["schema"]) is not int
        or data["schema"] != 1
    ):
        raise JournalError("TIMEWEB_JOURNAL_RECORD_INVALID")
    value = dict(data["plan"])
    value["context"] = protocol.Context(**value["context"])
    value["snapshot"] = protocol.Snapshot(**value["snapshot"])
    plan = protocol.Plan(**value)
    protocol._plan(plan, plan.context)
    if plan.identifier != identifier:
        raise JournalError("TIMEWEB_JOURNAL_RECORD_INVALID")
    phase = protocol.Phase(data["phase"])
    reference = data["approval_reference"]
    if phase is protocol.Phase.PLANNED:
        if reference is not None:
            raise JournalError("TIMEWEB_JOURNAL_RECORD_INVALID")
    elif not isinstance(reference, str) or not 1 <= len(reference) <= 256:
        raise JournalError("TIMEWEB_JOURNAL_RECORD_INVALID")
    return protocol.Entry(plan, phase, reference)


class SqliteJournal:
    """A concrete durable journal; its codec and location are trusted dependencies.

    Production construction MUST supply an ACL-verified persistent location and
    the CurrentUser DPAPI codec. This class does not infer location authority from
    a browser payload or automatically initialize a missing APPLY journal.
    Each method owns a fresh connection and serializes writers with BEGIN IMMEDIATE.
    """

    def __init__(
        self,
        path: Path,
        *,
        protect: Callable[[bytes], bytes] = dpapi,
        unprotect: Callable[[bytes], bytes] | None = None,
        verify_location: Callable[[], None],
        initialize: bool = False,
    ) -> None:
        self._path = path
        self._protect = protect
        self._unprotect = unprotect or self._decrypt
        self._verify_location = verify_location
        try:
            verify_location()
            if path.is_symlink():
                raise JournalError("TIMEWEB_JOURNAL_LOCATION_INVALID")
            if not path.exists() and not initialize:
                raise JournalError("TIMEWEB_JOURNAL_MISSING_RECONCILIATION_REQUIRED")
            new_store = initialize and not path.exists()
            with self._connect(create=new_store) as db:
                if new_store:
                    db.execute(_TABLE)
                if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise JournalError("TIMEWEB_JOURNAL_INTEGRITY_FAILED")
                self._entries(db)
        except Exception:
            raise JournalError("TIMEWEB_JOURNAL_INITIALIZATION_FAILED") from None

    @staticmethod
    def _decrypt(raw: bytes) -> bytes:
        return dpapi(raw, decrypt=True)

    @contextmanager
    def _connect(self, *, create: bool = False) -> Iterator[sqlite3.Connection]:
        self._verify_location()
        if self._path.is_symlink():
            raise JournalError("TIMEWEB_JOURNAL_LOCATION_INVALID")
        uri = self._path.resolve().as_uri() + ("?mode=rwc" if create else "?mode=rw")
        db = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=EXTRA")
            if db.execute("PRAGMA synchronous").fetchone() != (3,):
                raise JournalError("TIMEWEB_JOURNAL_DURABILITY_INVALID")
            if db.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise JournalError("TIMEWEB_JOURNAL_DURABILITY_INVALID")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def _entries(self, db: sqlite3.Connection) -> list[protocol.Entry]:
        rows = db.execute(
            "SELECT handle, sealed FROM allocation LIMIT ?",
            (_MAX_RECORDS + 1,),
        ).fetchall()
        if len(rows) > _MAX_RECORDS:
            raise JournalError("TIMEWEB_JOURNAL_CAPACITY_RECONCILIATION_REQUIRED")
        entries = []
        for identifier, sealed in rows:
            if not isinstance(sealed, bytes) or not 0 < len(sealed) <= _MAX_BYTES:
                raise JournalError("TIMEWEB_JOURNAL_RECORD_INVALID")
            entries.append(_decode(self._unprotect(sealed), identifier))
        return entries

    def _get(self, db: sqlite3.Connection, identifier: str) -> protocol.Entry:
        matches = [
            entry
            for entry in self._entries(db)
            if entry.plan.identifier == identifier
        ]
        if len(matches) != 1:
            raise JournalError("TIMEWEB_JOURNAL_PLAN_NOT_FOUND")
        return matches[0]

    def _seal(self, entry: protocol.Entry) -> bytes:
        raw = _encode(entry)
        if len(raw) > _MAX_BYTES:
            raise JournalError("TIMEWEB_JOURNAL_RECORD_TOO_LARGE")
        sealed = self._protect(raw)
        if not isinstance(sealed, bytes) or not 0 < len(sealed) <= _MAX_BYTES:
            raise JournalError("TIMEWEB_JOURNAL_PROTECTION_FAILED")
        if _decode(self._unprotect(sealed), entry.plan.identifier) != entry:
            raise JournalError("TIMEWEB_JOURNAL_PROTECTION_FAILED")
        return sealed

    @staticmethod
    def _conflict(left: protocol.Plan, right: protocol.Plan) -> bool:
        # A matching resource blocks even when source, project or token changes.
        return left.snapshot.cluster_id == right.snapshot.cluster_id or (
            left.snapshot.floating_id == right.snapshot.floating_id
            or left.snapshot.ip_address == right.snapshot.ip_address
        )

    def create(self, plan: protocol.Plan) -> None:
        try:
            protocol._plan(plan, plan.context)
            with self._connect() as db:
                entries = self._entries(db)
                if len(entries) >= _MAX_RECORDS:
                    raise JournalError(
                        "TIMEWEB_JOURNAL_CAPACITY_RECONCILIATION_REQUIRED"
                    )
                for entry in entries:
                    active = (
                        entry.phase is not protocol.Phase.PLANNED
                        or entry.plan.expires_at > plan.issued_at
                    )
                    if self._conflict(entry.plan, plan) and active:
                        raise JournalError("TIMEWEB_JOURNAL_ACTIVE_PLAN_CONFLICT")
                entry = protocol.Entry(plan, protocol.Phase.PLANNED)
                db.execute(
                    "INSERT INTO allocation(handle, sealed) VALUES (?, ?)",
                    (plan.identifier, self._seal(entry)),
                )
        except Exception:
            raise JournalError("TIMEWEB_JOURNAL_CREATE_FAILED") from None

    def read(self, identifier: str) -> protocol.Entry:
        try:
            with self._connect() as db:
                return self._get(db, identifier)
        except Exception:
            raise JournalError("TIMEWEB_JOURNAL_READ_FAILED") from None

    def claim(self, identifier: str, digest: str, approval_reference: str) -> bool:
        try:
            with self._connect() as db:
                entry = self._get(db, identifier)
                if entry.plan.digest != digest:
                    raise JournalError("TIMEWEB_JOURNAL_PLAN_DRIFT")
                if entry.phase is not protocol.Phase.PLANNED:
                    return False
                for other in self._entries(db):
                    if other.plan.identifier == identifier:
                        continue
                    if self._conflict(other.plan, entry.plan) and (
                        other.phase is not protocol.Phase.PLANNED
                        or other.plan.issued_at >= entry.plan.expires_at
                    ):
                        raise JournalError("TIMEWEB_JOURNAL_PLAN_SUPERSEDED")
                claimed = protocol.Entry(
                    entry.plan,
                    protocol.Phase.ATTEMPTED,
                    approval_reference,
                )
                db.execute(
                    "UPDATE allocation SET sealed=? WHERE handle=?",
                    (self._seal(claimed), identifier),
                )
            return True
        except Exception:
            raise JournalError("TIMEWEB_JOURNAL_CLAIM_UNPROVEN") from None

    def complete(self, identifier: str, digest: str) -> None:
        try:
            with self._connect() as db:
                entry = self._get(db, identifier)
                if (
                    entry.plan.digest != digest
                    or entry.phase is not protocol.Phase.ATTEMPTED
                ):
                    raise JournalError("TIMEWEB_JOURNAL_COMPLETION_INVALID")
                saved = protocol.Entry(
                    entry.plan,
                    protocol.Phase.ALLOCATED,
                    entry.approval_reference,
                )
                db.execute(
                    "UPDATE allocation SET sealed=? WHERE handle=?",
                    (self._seal(saved), identifier),
                )
        except Exception:
            raise JournalError("TIMEWEB_JOURNAL_COMPLETION_UNPROVEN") from None
