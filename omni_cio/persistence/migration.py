from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Protocol


SCHEMA_NAME = "omni_cio_v10"
POSTGRES_MAJOR = 18
MIGRATION_LOCK_KEY = 132013
_MIGRATION_PATTERN = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql$")
_MIGRATION_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS omni_cio_v10;
CREATE TABLE IF NOT EXISTS omni_cio_v10.schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    sha256 char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    CONSTRAINT schema_migration_sha256 CHECK (sha256 ~ '^[a-f0-9]{64}$')
);
"""
_SELECT_APPLIED_MIGRATIONS_SQL = (
    "SELECT version, name, sha256 FROM omni_cio_v10.schema_migrations ORDER BY version"
)
_INSERT_MIGRATION_SQL = (
    "INSERT INTO omni_cio_v10.schema_migrations "
    "(version, name, sha256) VALUES (%s, %s, %s)"
)
_SELECT_MIGRATION_STATE_SQL = (
    "SELECT version, sha256 FROM omni_cio_v10.schema_migrations ORDER BY version"
)


class CursorLike(Protocol):
    rowcount: int

    def fetchone(self) -> Sequence[Any] | None: ...

    def fetchall(self) -> list[Sequence[Any]]: ...


class TransactionContext(Protocol):
    def __enter__(self) -> Any: ...

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None: ...


class ConnectionLike(Protocol):
    def execute(
        self,
        query: Any,
        params: Sequence[Any] | None = None,
        *,
        prepare: bool | None = None,
    ) -> CursorLike: ...

    def transaction(self) -> TransactionContext: ...


class MigrationError(RuntimeError):
    """Base fail-closed WP13 migration error."""


class UnsupportedPostgresError(MigrationError):
    """Raised when the database major does not match the accepted V10 baseline."""


class MigrationChecksumError(MigrationError):
    """Raised when an already-applied migration file has changed."""


class MigrationSeriesError(MigrationError):
    """Raised when migration discovery finds an invalid or ambiguous series."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path
    sha256: str

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def migration_root() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _migration_checksum_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise MigrationSeriesError(
            f"migration source must be UTF-8: {path.name}"
        ) from None

    normalized_lf = source.replace("\r\n", "\n")
    if "\r" in normalized_lf:
        raise MigrationSeriesError(
            f"migration source contains unsupported bare CR line endings: {path.name}"
        )

    # Migration checksums predate hosted Linux recovery and were first persisted
    # from the authoritative Windows checkout. Preserve that accepted checksum
    # identity while making discovery independent of the runner working-tree EOL.
    return normalized_lf.replace("\n", "\r\n").encode("utf-8")


def discover_migrations(root: Path | None = None) -> tuple[Migration, ...]:
    base = root or migration_root()
    migrations: list[Migration] = []
    versions: set[int] = set()
    for path in sorted(base.glob("*.sql")):
        match = _MIGRATION_PATTERN.fullmatch(path.name)
        if match is None:
            raise MigrationSeriesError(f"invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in versions:
            raise MigrationSeriesError(f"duplicate migration version: {version:04d}")
        versions.add(version)
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                path=path,
                sha256=hashlib.sha256(_migration_checksum_bytes(path)).hexdigest(),
            )
        )

    if not migrations:
        raise MigrationSeriesError("no WP13 migrations found")
    expected = list(range(1, len(migrations) + 1))
    actual = [item.version for item in migrations]
    if actual != expected:
        raise MigrationSeriesError(
            f"migration versions must be contiguous from 0001: {actual}"
        )
    return tuple(migrations)


def _server_major(connection: ConnectionLike) -> int:
    row = connection.execute("SHOW server_version_num").fetchone()
    if row is None:
        raise UnsupportedPostgresError("PostgreSQL version query returned no row")
    try:
        version_num = int(row[0])
    except (TypeError, ValueError) as exc:
        raise UnsupportedPostgresError("PostgreSQL version is not numeric") from exc
    return version_num // 10000


def require_postgres_18(connection: ConnectionLike) -> None:
    major = _server_major(connection)
    if major != POSTGRES_MAJOR:
        raise UnsupportedPostgresError(
            f"WP13 requires PostgreSQL {POSTGRES_MAJOR}; connected major is {major}"
        )


def apply_migrations(
    connection: ConnectionLike,
    migrations: Iterable[Migration] | None = None,
) -> tuple[int, ...]:
    series = tuple(migrations or discover_migrations())
    if not series:
        raise MigrationSeriesError("migration series cannot be empty")

    applied_now: list[int] = []
    with connection.transaction():
        require_postgres_18(connection)
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_KEY,))
        connection.execute(_MIGRATION_TABLE_SQL, prepare=False)
        rows = connection.execute(_SELECT_APPLIED_MIGRATIONS_SQL).fetchall()
        applied = {int(row[0]): (str(row[1]), str(row[2])) for row in rows}

        known_versions = {migration.version for migration in series}
        unexpected = sorted(set(applied) - known_versions)
        if unexpected:
            raise MigrationSeriesError(
                f"database contains unknown migration versions: {unexpected}"
            )

        for migration in series:
            previous = applied.get(migration.version)
            if previous is not None:
                if previous != (migration.name, migration.sha256):
                    raise MigrationChecksumError(
                        f"migration {migration.version:04d} checksum/name drift"
                    )
                continue

            connection.execute(migration.sql, prepare=False)
            connection.execute(
                _INSERT_MIGRATION_SQL,
                (migration.version, migration.name, migration.sha256),
            )
            applied_now.append(migration.version)

    return tuple(applied_now)


def current_migration_state(connection: ConnectionLike) -> tuple[tuple[int, str], ...]:
    rows = connection.execute(_SELECT_MIGRATION_STATE_SQL).fetchall()
    return tuple((int(row[0]), str(row[1])) for row in rows)


def migration_series_digest(migrations: Iterable[Migration] | None = None) -> str:
    series = tuple(migrations or discover_migrations())
    payload = "\n".join(
        f"{item.version:04d}:{item.name}:{item.sha256}" for item in series
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def connect_postgres(
    dsn: str,
    *,
    connect_timeout: int | None = None,
) -> ConnectionLike:
    """Open PostgreSQL without putting credentials in source or diagnostics."""

    import psycopg  # type: ignore[import-not-found]

    if connect_timeout is None:
        return psycopg.connect(dsn)
    return psycopg.connect(dsn, connect_timeout=connect_timeout)
