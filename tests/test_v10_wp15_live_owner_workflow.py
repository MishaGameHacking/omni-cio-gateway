from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER_WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp15-live-web-owner-audit.yml"
SUPPORT_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp15-live-web-support-audit.yml"
)


def _push_scope(workflow: str) -> str:
    return workflow.split("  push:\n", 1)[1].split("  workflow_dispatch:\n", 1)[0]


def test_owner_audit_cleanup_is_windows_native_and_fail_closed() -> None:
    workflow = OWNER_WORKFLOW.read_text(encoding="utf-8")
    marker = "- name: Clean self-hosted workspace"

    assert marker in workflow
    cleanup = workflow.split(marker, 1)[1]

    assert "shell: cmd" in cleanup
    assert "shell: bash" not in cleanup
    assert "git reset --hard HEAD" in cleanup
    assert "if errorlevel 1 exit /b 70" in cleanup
    assert "git clean -ffdx" in cleanup
    assert "if errorlevel 1 exit /b 71" in cleanup


def test_owner_audit_push_scope_only_tracks_physical_wp15_evidence_surfaces() -> None:
    owner_workflow = OWNER_WORKFLOW.read_text(encoding="utf-8")
    support_workflow = SUPPORT_WORKFLOW.read_text(encoding="utf-8")
    owner_push = _push_scope(owner_workflow)

    shared_downstream_web_surfaces = (
        "apps/api/app.py",
        "apps/web/src/app-shell/**",
        "omni_cio/web/api_v1.py",
        "docs/operations/V10_WP15_OWNER_LIVE_READ_RUNBOOK.md",
        ".github/workflows/v10-wp15-live-web-owner-audit.yml",
    )
    for path in shared_downstream_web_surfaces:
        assert f'- "{path}"' not in owner_push
        assert f'- "{path}"' in support_workflow

    evidence_bound_surfaces = (
        "omni_cio/web/live_acceptance_v1.py",
        "docs/architecture/V10_WP15_LIVE_WEB_ACCEPTANCE_CONTRACT.json",
        "infrastructure/windows/provision_wp15_live_web_acceptance.ps1",
        "infrastructure/windows/start_wp15_live_web_acceptance.ps1",
        "infrastructure/windows/run_wp15_live_web_runtime.ps1",
        "infrastructure/windows/bootstrap_wp15_live_database.py",
        "infrastructure/windows/probe_wp15_live_session_runtime.py",
        "infrastructure/windows/finalize_wp15_live_web_evidence.ps1",
        "infrastructure/windows/audit_wp15_live_web_runner.ps1",
    )
    for path in evidence_bound_surfaces:
        assert f'- "{path}"' in owner_push

    assert "  workflow_dispatch:\n" in owner_workflow
    assert '-ExpectedImplementationSha "%GITHUB_SHA%"' in owner_workflow
