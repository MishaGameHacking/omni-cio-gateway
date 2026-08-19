from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "omni_cio/persistence/migrations/0004_product_identity_multi_tenant.sql"
IDENTITY = ROOT / "omni_cio/web/product_identity_v1.py"
PERSISTENCE = ROOT / "omni_cio/web/persistence_v1.py"
SHELL = ROOT / "apps/web/src/app-shell/app-shell.tsx"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"


def test_phase2_migration_generalizes_only_authorized_boundaries() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    for required in (
        "DROP CONSTRAINT owner_tenant_only",
        "DROP CONSTRAINT owner_user_only",
        "DROP CONSTRAINT web_session_owner_only",
        "DROP CONSTRAINT broker_account_owner_only",
        "DROP CONSTRAINT broker_connection_owner_only",
        "DROP CONSTRAINT broker_connection_accounts_owner_only",
        "subject_binding_hmac_sha256",
        "ENABLE ROW LEVEL SECURITY",
        "broker_accounts_tenant_isolation",
        "broker_connections_tenant_isolation",
        "broker_connection_accounts_tenant_isolation",
        "current_setting('omni_cio.tenant_id', true)",
    ):
        assert required in source

    for forbidden in (
        "DROP CONSTRAINT portfolio_owner_only",
        "DROP CONSTRAINT policy_owner_only",
        "DROP CONSTRAINT snapshot_owner_only",
        "DROP CONSTRAINT position_owner_only",
        "DROP CONSTRAINT evidence_owner_only",
        "DROP CONSTRAINT incident_owner_only",
        "DROP CONSTRAINT decision_owner_only",
        "DROP CONSTRAINT plan_owner_only",
        "DROP CONSTRAINT execution_owner_only",
        "DROP CONSTRAINT journal_owner_only",
        "DROP CONSTRAINT research_owner_only",
        "DROP CONSTRAINT job_owner_only",
        "DROP CONSTRAINT health_owner_only",
        "DROP CONSTRAINT content_blob_owner_only",
        "DROP CONSTRAINT state_revision_owner_only",
        "FORCE ROW LEVEL SECURITY",
    ):
        assert forbidden not in source


def test_product_identity_uses_keyed_binding_and_fail_closed_registration() -> None:
    source = IDENTITY.read_text(encoding="utf-8")

    assert "hmac.new" in source
    assert "PRODUCT_IDENTITY_BINDING_KEY_TOO_SHORT" in source
    assert "PUBLIC_REGISTRATION_DISABLED" in source
    assert "pg_advisory_xact_lock" in source
    assert "ProductAuthenticationServiceV1" in source
    assert "subject_binding_sha256" not in source


def test_broker_repository_sets_transaction_local_tenant_context() -> None:
    source = PERSISTENCE.read_text(encoding="utf-8")

    assert "set_config('omni_cio.tenant_id', %s, true)" in source
    assert "WP17 private acceptance admits only OWNER tenant" not in source
    assert source.count("_set_tenant_scope(self._connection, tenant_id)") >= 4


def test_product_shell_has_no_engineering_edge_owner_login() -> None:
    source = SHELL.read_text(encoding="utf-8")

    assert "OWNER private access" not in source
    assert "privateRemoteLogin" not in source
    assert "readPrivateRemoteStatus" not in source
    assert "Продолжить через Telegram" in source
    assert "Продолжить через VK ID" in source
    assert "<span>USER</span>" in source


def test_phase2_keeps_public_activation_and_wp23_locked() -> None:
    source = STATUS.read_text(encoding="utf-8")

    assert "PUBLIC_MULTI_USER_ENABLED=false" in source
    assert "WP23+ remains locked" in source
