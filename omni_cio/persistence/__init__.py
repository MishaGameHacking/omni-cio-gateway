"""PostgreSQL durable-state boundary for Omni-CIO V10 WP13."""

from omni_cio.persistence.migration import (
    MIGRATION_LOCK_KEY,
    POSTGRES_MAJOR,
    SCHEMA_NAME,
    Migration,
    MigrationChecksumError,
    MigrationError,
    MigrationSeriesError,
    UnsupportedPostgresError,
    apply_migrations,
    connect_postgres,
    current_migration_state,
    discover_migrations,
    migration_series_digest,
    require_postgres_18,
)
from omni_cio.persistence.repository import (
    ContentHashMismatchError,
    PersistenceConflictError,
    PostgresDomainRepository,
    catalog_sha256,
    model_record_sha256,
)

__all__ = [
    "MIGRATION_LOCK_KEY",
    "POSTGRES_MAJOR",
    "SCHEMA_NAME",
    "ContentHashMismatchError",
    "Migration",
    "MigrationChecksumError",
    "MigrationError",
    "MigrationSeriesError",
    "PersistenceConflictError",
    "PostgresDomainRepository",
    "UnsupportedPostgresError",
    "apply_migrations",
    "catalog_sha256",
    "connect_postgres",
    "current_migration_state",
    "discover_migrations",
    "migration_series_digest",
    "model_record_sha256",
    "require_postgres_18",
]
