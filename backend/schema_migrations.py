"""Execute trusted schema constants without executescript's implicit commit.

The caller owns an already-open transaction. This helper never begins, commits,
rolls back, closes, or replaces it, and never replaces an SQLite authorizer.
Use the existing ai_budget.transaction(connect) boundary for new connections.
Only source-controlled DDL constants belong here; this is not an untrusted SQL
sandbox. Atomicity is per initializer, not an all-services startup transaction.
"""
from __future__ import annotations

import re
import sqlite3

MAX_SCHEMA_CHARACTERS = 262144
MAX_SCHEMA_STATEMENTS = 512
_LEADING = re.compile(r"(?:\s+|--[^\r\n]*(?:\r?\n|\Z)|/\*[\s\S]*?\*/)*")
_KEYWORD = re.compile(r"[A-Za-z]+")
_ALLOWED = frozenset({"CREATE", "ALTER", "DROP"})


class SchemaMigrationError(ValueError):
    """Sanitized error in a trusted schema contract, distinct from SQLite errors."""


def _body(statement: str) -> str:
    match = _LEADING.match(statement)
    return statement[match.end():] if match else statement


def schema_statements(script: str) -> tuple[str, ...]:
    """Validate the bounded DDL batch before executing its first statement."""
    if (not isinstance(script, str) or not script
            or len(script) > MAX_SCHEMA_CHARACTERS or "\x00" in script):
        raise SchemaMigrationError("schema_script_invalid_or_oversized")
    statements, start = [], 0
    # SQLite's completeness check understands quotes, comments and trigger bodies.
    for index, character in enumerate(script):
        if character != ";" or not sqlite3.complete_statement(script[start:index + 1]):
            continue
        statement = script[start:index + 1]
        start = index + 1
        body = _body(statement).strip()
        if body == ";":
            continue
        keyword = _KEYWORD.match(body)
        if keyword is None or keyword.group().upper() not in _ALLOWED:
            raise SchemaMigrationError("schema_statement_not_ddl")
        statements.append(statement)
        if len(statements) > MAX_SCHEMA_STATEMENTS:
            raise SchemaMigrationError("schema_statement_limit")
    if _body(script[start:]).strip():
        raise SchemaMigrationError("schema_statement_incomplete")
    if not statements:
        raise SchemaMigrationError("schema_statements_required")
    return tuple(statements)


def execute_schema(db: sqlite3.Connection, script: str) -> int:
    """Keep the caller's transaction and rollback boundary intact."""
    if not isinstance(db, sqlite3.Connection) or not db.in_transaction:
        raise SchemaMigrationError("schema_write_transaction_required")
    statements = schema_statements(script)
    for statement in statements:
        db.execute(statement)
        if not db.in_transaction:
            raise SchemaMigrationError("schema_transaction_lost")
    return len(statements)
