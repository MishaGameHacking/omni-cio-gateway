from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp15-live-web-owner-audit.yml"
)


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
