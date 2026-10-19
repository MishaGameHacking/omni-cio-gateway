"""Database boundary for a fresh, explicitly bound single-owner installation.

The subject comes from server configuration, never the first visitor, a username,
phone number or device identifier. Authentication still verifies Telegram tokens.
This module neither imports user backups nor deletes/reassigns anyone's records.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import os
import sqlite3
from typing import Callable, Mapping

ENV_SUBJECT = "ANALYST_OWNER_TELEGRAM_SUB"
DENIED = "owner_access_denied"
POLICY_VERSION = "single-owner-0.11.0-v1"
REGISTRY = "installation_owner"


class OwnerConfigurationError(RuntimeError):
    """A fixed, non-identifying reason why this installation cannot start."""


@dataclass(frozen=True)
class OwnerIdentity:
    subject: str

    def __post_init__(self) -> None:
        value = self.subject
        if (not isinstance(value, str) or not value or len(value) > 256
                or not value.isascii() or any(character.isspace() or ord(character) < 33 for character in value)):
            raise OwnerConfigurationError("owner_subject_missing_or_invalid")

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> OwnerIdentity:
        settings = os.environ if environ is None else environ
        return cls(settings.get(ENV_SUBJECT, ""))


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _tables(db: sqlite3.Connection) -> list[str]:
    return [row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]


def _owner_tables(db: sqlite3.Connection) -> list[str]:
    result = []
    for table in _tables(db):
        columns = {row[1] for row in db.execute("PRAGMA table_info(" + _identifier(table) + ")")}
        if "user_id" in columns:
            result.append(table)
    return result


def _verify_existing(db: sqlite3.Connection, identity: OwnerIdentity) -> list[str]:
    users = db.execute("SELECT id,telegram_sub FROM users").fetchall()
    if len(users) > 1 or any(row[1] != identity.subject for row in users):
        raise OwnerConfigurationError("existing_users_do_not_match_owner")
    tables = _owner_tables(db)
    for table in tables:
        invalid = db.execute(
            "SELECT 1 FROM " + _identifier(table) + " AS item "
            "WHERE NOT EXISTS (SELECT 1 FROM users WHERE users.id=item.user_id "
            "AND users.telegram_sub=?) LIMIT 1", (identity.subject,),
        ).fetchone()
        if invalid:
            raise OwnerConfigurationError("existing_records_do_not_match_owner")
    return tables


def _registry(db: sqlite3.Connection, identity: OwnerIdentity) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS installation_owner ("
               "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
               "telegram_sub TEXT NOT NULL,policy_version TEXT NOT NULL)")
    rows = db.execute("SELECT singleton,telegram_sub,policy_version FROM installation_owner").fetchall()
    if not rows:
        db.execute("INSERT INTO installation_owner VALUES (1,?,?)", (identity.subject, POLICY_VERSION))
    elif len(rows) != 1 or tuple(rows[0]) != (1, identity.subject, POLICY_VERSION):
        raise OwnerConfigurationError("owner_binding_change_requires_explicit_migration")


def _trigger(db: sqlite3.Connection, name: str, clause: str, condition: str = "1") -> None:
    # Rebuild our own triggers transactionally; IF NOT EXISTS alone would retain
    # obsolete policy bodies after an upgrade. Values never enter the DDL.
    quoted = _identifier(name)
    db.execute("DROP TRIGGER IF EXISTS " + quoted)
    db.execute("CREATE TRIGGER " + quoted + " " + clause + " WHEN " + condition
               + " BEGIN SELECT RAISE(ABORT, '" + DENIED + "'); END")


def _protect_registry_and_users(db: sqlite3.Connection) -> None:
    for operation in ("INSERT", "UPDATE", "DELETE"):
        _trigger(db, "owner_registry_" + operation.lower(),
                 "BEFORE " + operation + " ON installation_owner")
    allowed = "NOT EXISTS (SELECT 1 FROM installation_owner WHERE telegram_sub=NEW.telegram_sub)"
    _trigger(db, "owner_users_insert", "BEFORE INSERT ON users", allowed + " OR EXISTS (SELECT 1 FROM users)")
    _trigger(db, "owner_users_update", "BEFORE UPDATE ON users",
             "NEW.id IS NOT OLD.id OR " + allowed)
    # Account erasure/rebinding needs an explicit maintenance procedure, never
    # INSERT OR REPLACE or a normal session/API request.
    _trigger(db, "owner_users_delete", "BEFORE DELETE ON users")
    db.execute("DROP TRIGGER IF EXISTS users_private_limit")


def _protect_owned_tables(db: sqlite3.Connection, tables: list[str]) -> None:
    condition = ("NOT EXISTS (SELECT 1 FROM users JOIN installation_owner "
                 "ON users.telegram_sub=installation_owner.telegram_sub WHERE users.id=NEW.user_id)")
    for table in tables:
        key = hashlib.sha256(table.encode()).hexdigest()[:20]
        for operation in ("INSERT", "UPDATE"):
            _trigger(db, "owner_record_" + key + "_" + operation.lower(),
                     "BEFORE " + operation + " ON " + _identifier(table), condition)


def bind_owner(connect: Callable[[], sqlite3.Connection], identity: OwnerIdentity) -> None:
    """Fail closed on unknown existing data; commit all guards or none of them.

    Re-run after schema initialization to cover new user-owned tables. A database
    file is not a security boundary against an administrator who can edit it.
    All normal application connections are subject to the persisted triggers.
    """
    if not isinstance(identity, OwnerIdentity):
        raise OwnerConfigurationError("validated_owner_identity_required")
    with closing(connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            tables = _verify_existing(db, identity)
            _registry(db, identity)
            _protect_registry_and_users(db)
            _protect_owned_tables(db, tables)
            db.commit()
        except BaseException:
            db.rollback()
            raise
