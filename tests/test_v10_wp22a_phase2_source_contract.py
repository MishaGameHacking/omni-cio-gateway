from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "omni_cio/persistence/migrations/0004_product_identity_multi_tenant.sql"
)
IDENTITY = ROOT / "omni_cio/web/product_identity_v1.py"
API = ROOT / "omni_cio/web/api_v1.py"
PERSISTENCE = ROOT / "omni_cio/web/persistence_v1.py"
SHELL = ROOT / "apps/web/src/app-shell/app-shell.tsx"
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
REHEARSAL_WRAPPER = (
    ROOT / "infrastructure/windows/rehearse_wp22a_phase2_tenant_security.ps1"
)
REHEARSAL_WATCHDOG = ROOT / "scripts/run_v10_wp22a_phase2_rehearsal_watchdog.py"
PHASE2_WORKFLOW = ROOT / ".github/workflows/v10-wp22a-phase2-product-auth-audit.yml"


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
        "external_identity_product_scope",
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
    assert "OWNER_IDENTITY_RESERVED" in source
    assert "pg_advisory_xact_lock" in source
    assert "ProductAuthenticationServiceV1" in source
    assert "subject_binding_sha256" not in source


def test_product_session_view_has_no_historical_owner_product_labels() -> None:
    source = API.read_text(encoding="utf-8")

    assert '"user_label": "OWNER"' not in source
    assert '"tenant_label": "Personal"' not in source
    assert '"authenticated": True' in source
    assert '"expires_at": scope.expires_at.isoformat()' in source


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
    assert "Продолжить через VK ID" not in source
    assert "<span>USER</span>" in source


def test_phase2_rehearsal_has_layered_finite_waits_and_safe_stage_markers() -> None:
    source = REHEARSAL_WRAPPER.read_text(encoding="utf-8")

    for required in (
        "ProbeTimeoutSeconds = 120",
        'PGCTLTIMEOUT = "10"',
        "statement_timeout=15000",
        "lock_timeout=10000",
        "taskkill.exe /PID $processId /T /F",
        "Start-TemporaryPostgresBounded",
        "Test-PostgresReadyBounded",
        '"-W"',
        '"WP22A_PHASE2_STAGE=initdb"',
        '"WP22A_PHASE2_STAGE=postgres_start"',
        '"WP22A_PHASE2_STAGE=postgres_ready"',
        '"WP22A_PHASE2_STAGE=database_create"',
        '"WP22A_PHASE2_STAGE=python_probe"',
        "Arm cleanup before any startup attempt",
        "-TimeoutSeconds 45",
        "-TimeoutSeconds 15",
        "-w -t 10 -s",
    ):
        assert required in source

    assert "& $pgCtl start" not in source
    cleanup_arm = source.index("$started = $true")
    startup_call = source.index("Start-TemporaryPostgresBounded -PgCtl")
    assert cleanup_arm < startup_call


def test_phase2_focused_gate_has_independent_outer_process_tree_watchdog() -> None:
    watchdog = REHEARSAL_WATCHDOG.read_text(encoding="utf-8")
    workflow = PHASE2_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "subprocess.Popen",
        "process.wait(timeout=args.timeout_seconds)",
        '"taskkill.exe", "/PID", str(process_id), "/T", "/F"',
        "timeout=_KILL_TIMEOUT_SECONDS",
        "WP22A_PHASE2_OUTER_WATCHDOG_TIMEOUT",
    ):
        assert required in watchdog
    assert "run_v10_wp22a_phase2_rehearsal_watchdog.py" in workflow
    assert "--timeout-seconds 240" in workflow
    assert (
        "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "
        "infrastructure\\windows\\rehearse_wp22a_phase2_tenant_security.ps1"
        not in workflow
    )


def test_phase2_keeps_public_activation_and_wp23_locked() -> None:
    source = STATUS.read_text(encoding="utf-8")

    assert "PUBLIC_MULTI_USER_ENABLED=false" in source
    assert "WP23+ remains locked" in source
