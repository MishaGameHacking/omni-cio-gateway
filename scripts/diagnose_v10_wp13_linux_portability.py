from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal
import os

import psycopg

from omni_cio.contracts.v1.domain import CanonicalDomainCatalogV1
from omni_cio.persistence import (
    PersistenceConflictError,
    PostgresDomainRepository,
    apply_migrations,
    current_migration_state,
    discover_migrations,
)
from scripts.rehearse_v10_wp13_persistence import (
    NOW,
    _catalog,
    _expect_database_failure,
)

DSN_ENV = "OMNI_CIO_WP13_DSN"


def _initialized() -> tuple[psycopg.Connection[object], CanonicalDomainCatalogV1, PostgresDomainRepository]:
    dsn = os.environ[DSN_ENV]
    connection = psycopg.connect(dsn)
    apply_migrations(connection)
    catalog = _catalog()
    repository = PostgresDomainRepository(connection)
    repository.persist_catalog(catalog)
    return connection, catalog, repository


def numeric() -> None:
    connection, _, _ = _initialized()
    try:
        quantity_row = connection.execute(
            "SELECT quantity, blocked_quantity FROM omni_cio_v10.positions"
        ).fetchone()
        assert quantity_row == (
            Decimal("10.125000000000000001"),
            Decimal("0.125000000000000001"),
        ), quantity_row
        numeric_meta = connection.execute(
            "SELECT data_type, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema = 'omni_cio_v10' AND table_name = 'positions' "
            "AND column_name = 'quantity'"
        ).fetchone()
        assert numeric_meta == ("numeric", 38, 18), numeric_meta
        approximate_count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = 'omni_cio_v10' "
            "AND (data_type IN ('real', 'double precision') OR udt_name = 'money')"
        ).fetchone()
        assert approximate_count is not None and int(approximate_count[0]) == 0
    finally:
        connection.close()
    print("CIRCLECI_WP13_NUMERIC=PASS")


def negatives() -> None:
    connection, catalog, repository = _initialized()
    try:
        _expect_database_failure(
            connection,
            "UPDATE omni_cio_v10.decisions SET payload_sha256 = repeat('a', 64)",
        )
        _expect_database_failure(connection, "DELETE FROM omni_cio_v10.journal")
        _expect_database_failure(
            connection,
            "INSERT INTO omni_cio_v10.tenants "
            "(tenant_id, schema_version, identity_version, mode, created_at, record_sha256) "
            "VALUES ('tenant:v1:foreign', '1.0', 1, 'owner_personal', now(), repeat('a', 64))",
        )
        conflicting_decision = catalog.decisions[0].model_copy(
            update={"payload_sha256": "a" * 64}
        )
        conflicting_catalog = CanonicalDomainCatalogV1.model_validate(
            {
                **catalog.model_dump(mode="python"),
                "decisions": (conflicting_decision,),
            }
        )
        rejected = False
        try:
            repository.persist_catalog(conflicting_catalog)
        except PersistenceConflictError:
            rejected = True
        assert rejected
    finally:
        connection.close()
    print("CIRCLECI_WP13_NEGATIVES=PASS")


def content_cache_digest() -> None:
    connection, _, repository = _initialized()
    try:
        blob_payload = b"WP13 synthetic private durable payload"
        blob_hash = repository.put_content_blob(
            blob_payload,
            media_type="application/octet-stream",
            schema_ref="synthetic/wp13",
            created_at=NOW,
        )
        assert (
            repository.put_content_blob(
                blob_payload,
                media_type="application/octet-stream",
                schema_ref="synthetic/wp13",
                created_at=NOW,
            )
            == blob_hash
        )
        with connection.transaction():
            connection.execute(
                "INSERT INTO omni_cio_v10.research_cache "
                "(cache_key, tenant_id, source_identity, content_sha256, retrieved_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s)",
                (
                    "expired",
                    "tenant:v1:owner",
                    "synthetic:expired",
                    "2" * 64,
                    NOW - timedelta(hours=2),
                    NOW - timedelta(hours=1),
                    "current",
                    "tenant:v1:owner",
                    "synthetic:current",
                    "3" * 64,
                    NOW,
                    NOW + timedelta(hours=1),
                ),
            )
        assert repository.prune_research_cache(expired_before=NOW) == 1
        remaining = connection.execute(
            "SELECT cache_key FROM omni_cio_v10.research_cache ORDER BY cache_key"
        ).fetchall()
        assert remaining == [("current",)], remaining
        assert len(repository.state_digest()) == 64
        assert len(current_migration_state(connection)) == len(discover_migrations())
    finally:
        connection.close()
    print("CIRCLECI_WP13_CONTENT_CACHE_DIGEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "stage",
        choices=("numeric", "negatives", "content-cache-digest"),
    )
    stage = parser.parse_args().stage
    if stage == "numeric":
        numeric()
    elif stage == "negatives":
        negatives()
    else:
        content_cache_digest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
