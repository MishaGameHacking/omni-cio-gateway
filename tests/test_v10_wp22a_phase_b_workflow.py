from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "v10-wp22a-provider-phase-b.yml"
ORCHESTRATOR = ROOT / "scripts" / "run_wp22a_provider_phase_b.ps1"
ENVIRONMENT_CHECK = ROOT / "scripts" / "check_wp22a_deployment_environment.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ENVIRONMENT = _load("wp22a_environment_check_test", ENVIRONMENT_CHECK)


def test_provider_workflow_is_manual_environment_bound_and_never_pr_routed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("permissions:", 1)[0]
    assert "workflow_dispatch:" in trigger
    assert "pull_request:" not in trigger
    assert "push:" not in trigger
    assert "environment: wp22a-provider-production" in text
    assert "cancel-in-progress: false" in text
    assert "refs/heads/main" in text
    assert "check_wp22a_deployment_environment.py" in text


def test_provider_secrets_are_not_bound_before_environment_and_main_guard() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    guard_index = text.index("Verify current main and deployment environment before provider secrets")
    provider_index = text.index("Run guarded Cloudflare provider operation")
    secret_index = text.index("secrets.WP22A_CLOUDFLARE_API_TOKEN")
    assert guard_index < provider_index <= secret_index
    for secret in (
        "WP22A_CLOUDFLARE_API_TOKEN",
        "WP22A_CLOUDFLARE_ACCOUNT_ID",
        "WP22A_CLOUDFLARE_ZONE_ID",
        "WP22A_EXTERNAL_HOST",
        "WP22A_CLOUDFLARE_TEAM_NAME",
    ):
        assert f"secrets.{secret}" in text
    assert "upload-artifact" not in text


def test_orchestrator_uses_private_local_state_and_never_uploads_raw_plan() -> None:
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert '$env:LOCALAPPDATA' in text
    assert '"OmniCIO\\wp22a-provider-state"' in text
    assert "wp22a_provider_state_guard.py" in text
    assert "check_wp22a_provider_state_binding.py" in text
    assert '"-json-into=$planJson"' in text
    assert '"-json-into=$stateJson"' in text
    assert "APPLY_WP22A_PROVIDER" in text
    assert "DESTROY_WP22A_PROVIDER" in text
    assert "Write-Output $tofuLog" not in text
    assert "Get-Content -LiteralPath $tofuLog" not in text


def test_environment_contract_accepts_exact_custom_main_only() -> None:
    environment = {
        "name": ENVIRONMENT.ENVIRONMENT_NAME,
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }
    branch_policies = {
        "total_count": 1,
        "branch_policies": [{"name": "main", "type": "branch"}],
    }
    ENVIRONMENT.validate_environment_snapshot(environment, branch_policies)


@pytest.mark.parametrize(
    "branch_policies",
    [
        {"total_count": 0, "branch_policies": []},
        {"total_count": 1, "branch_policies": [{"name": "*", "type": "branch"}]},
        {"total_count": 1, "branch_policies": [{"name": "main", "type": "tag"}]},
        {
            "total_count": 2,
            "branch_policies": [
                {"name": "main", "type": "branch"},
                {"name": "release/*", "type": "branch"},
            ],
        },
    ],
)
def test_environment_contract_rejects_anything_but_exact_main(branch_policies) -> None:
    environment = {
        "name": ENVIRONMENT.ENVIRONMENT_NAME,
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }
    with pytest.raises(ENVIRONMENT.DeploymentEnvironmentError):
        ENVIRONMENT.validate_environment_snapshot(environment, branch_policies)


def test_environment_contract_rejects_stale_or_nonexact_main_sha() -> None:
    branch = {"commit": {"sha": "a" * 40}}
    ENVIRONMENT.validate_main_snapshot(
        branch, event_sha="a" * 40, expected_sha="a" * 40
    )
    with pytest.raises(
        ENVIRONMENT.DeploymentEnvironmentError, match="WP22A_CURRENT_MAIN_MOVED"
    ):
        ENVIRONMENT.validate_main_snapshot(
            {"commit": {"sha": "b" * 40}},
            event_sha="a" * 40,
            expected_sha="a" * 40,
        )
