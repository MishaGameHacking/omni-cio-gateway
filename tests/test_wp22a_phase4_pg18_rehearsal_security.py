from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REHEARSAL = ROOT / "scripts" / "rehearse_v10_wp22a_phase4_runtime_role.py"
WINDOWS_REHEARSAL = (
    ROOT / "infrastructure" / "windows" / "rehearse_wp22a_phase4_runtime_role.ps1"
)
AUTHORITATIVE_WORKFLOW = ROOT / ".github" / "workflows" / "self-hosted-windows-smoke.yml"
CIRCLECI = ROOT / ".circleci" / "config.yml"
DECISION = ROOT / "docs" / "architecture" / "V10_WP22A_SUPPLEMENTAL_LINUX_CI_DECISION.md"


def test_phase4_pg18_rehearsal_generates_ephemeral_credentials() -> None:
    source = REHEARSAL.read_text(encoding="utf-8")

    assert "import secrets" in source
    assert source.count("secrets.token_urlsafe(32)") == 1
    assert source.count("_ephemeral_password()") == 5
    assert "first_password = _ephemeral_password()" in source
    assert "second_password = _ephemeral_password()" in source
    assert "SYNTHETIC_PASSWORD" not in source
    assert "BOOTSTRAP_PASSWORD" not in source


def test_phase4_pg18_windows_rehearsal_is_ephemeral_and_fail_closed() -> None:
    source = WINDOWS_REHEARSAL.read_text(encoding="utf-8")

    assert '"PostgreSQL\\18\\bin\\$Name.exe"' in source
    assert '"--username=phase4_owner"' in source
    assert '"--auth=trust"' in source
    assert '"-h 127.0.0.1 -p $Port"' in source
    assert '"creator-edge"' in source
    assert '"bootstrap"' in source
    assert "POSTGRES_START_READINESS_TIMEOUT" in source
    assert "POSTGRES_MAJOR_MISMATCH" in source
    assert "POSTGRES_TEMPORARY_STATE_CLEANUP_FAILED" in source
    assert "V10_WP22A_PHASE4_WINDOWS_POSTGRES18=PASS" in source
    assert "REAL_SECRETS_USED=NO" in source


def test_authoritative_gate_runs_both_real_postgres18_phase4_rehearsals() -> None:
    source = AUTHORITATIVE_WORKFLOW.read_text(encoding="utf-8")

    assert source.count("Rehearse Phase 4 PostgreSQL 18 runtime-role semantics") == 1
    assert source.count("rehearse_wp22a_phase4_runtime_role.ps1") == 2
    assert (
        'script_path="$(cygpath -w infrastructure/windows/'
        'rehearse_wp22a_phase4_runtime_role.ps1)"'
    ) in source
    assert '-File "$script_path"' in source
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in source
    assert "V10 authoritative merge gate" in source


def test_unavailable_circleci_provider_is_not_an_active_acceptance_dependency() -> None:
    assert not CIRCLECI.exists()
    decision = DECISION.read_text(encoding="utf-8")

    assert "CircleCI provider requirement: **RETIRED**" in decision
    assert "Linux-specific hosted evidence remains mandatory" in decision
    assert "Azure Pipelines is not activated" in decision
