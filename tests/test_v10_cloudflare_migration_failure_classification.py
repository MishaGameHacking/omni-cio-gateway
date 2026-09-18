from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = ROOT / "scripts/provision_v10_cloudflare_neon_runtime.py"


def test_cloudflare_neon_runtime_classifies_migration_failures_before_generic_bootstrap() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")

    checksum_handler = source.index("except MigrationChecksumError:")
    series_handler = source.index("except MigrationSeriesError:")
    migration_handler = source.index("except MigrationError:")
    network_handler = source.index("except psycopg.OperationalError:")
    generic_handler = source.index("except Exception:", migration_handler)

    assert checksum_handler < series_handler < migration_handler < network_handler < generic_handler
    assert "CLOUDFLARE_DATABASE_MIGRATION_CHECKSUM_MISMATCH" in source
    assert "CLOUDFLARE_DATABASE_MIGRATION_SERIES_INVALID" in source
    assert "CLOUDFLARE_DATABASE_MIGRATION_FAILED" in source
    assert "CLOUDFLARE_DATABASE_BOOTSTRAP_FAILED" in source


def test_cloudflare_neon_runtime_keeps_migration_failure_output_sanitized() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")

    for forbidden in (
        "str(exc)",
        "repr(exc)",
        "exc.diag",
        "exc.pgerror",
        "exc.sql",
    ):
        assert forbidden not in source
