from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVATION = ROOT / ".github" / "workflows" / "v10-wp22a-provider-activation.yml"
CONTROLLER = ROOT / "infrastructure" / "windows" / "run_wp22a_provider_controller.ps1"
INSTALLER = (
    ROOT / "infrastructure" / "windows" / "install_wp22a_provider_controller.ps1"
)
BOUNDARY = ROOT / "docs" / "architecture" / "V10_WP22A_PROVIDER_ACTIVATION_BOUNDARY.md"
RUNBOOK = ROOT / "docs" / "operations" / "V10_WP22A_PROVIDER_ACTIVATION_RUNBOOK.md"
DORMANT_PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp22a_clientless_remote_access.ps1"
)


def _trigger_block(workflow: str) -> str:
    return workflow.split("on:\n", 1)[1].split("\npermissions:\n", 1)[0]


def test_activation_workflow_is_manual_main_oidc_only() -> None:
    workflow = ACTIVATION.read_text(encoding="utf-8")
    triggers = _trigger_block(workflow)

    assert "workflow_dispatch:" in triggers
    assert "pull_request:" not in triggers
    assert "push:" not in triggers
    assert "id-token: write" in workflow
    assert "contents: read" in workflow
    assert "refs/heads/main" in workflow
    assert "github.event_name" in workflow
    assert "git rev-parse HEAD" in workflow
    assert "git status --porcelain" in workflow
    assert "persist-credentials: false" in workflow

    assert 'EXPECTED_OWNER_ACTOR_ID: "201947041"' in workflow
    assert "github.actor_id" in workflow
    assert "github.run_attempt" in workflow
    assert "github.triggering_actor" in workflow
    assert "WP22A_PROVIDER_OWNER_ACTOR_REQUIRED" in workflow
    assert "WP22A_PROVIDER_RERUN_FORBIDDEN" in workflow
    assert "WP22A_PROVIDER_RERUN_BY_DIFFERENT_ACTOR_FORBIDDEN" in workflow

    assert "secrets." not in workflow.lower()
    assert "cloudflare_api" not in workflow.lower()
    assert "api_token" not in workflow.lower()
    assert "account_id" not in workflow.lower()
    assert "zone_id" not in workflow.lower()
    assert "hostname" not in triggers.lower()


def test_activation_workflow_never_interprets_boundary_as_provider_apply() -> None:
    workflow = ACTIVATION.read_text(encoding="utf-8")

    assert "omni-cio-wp22a-provider-controller" in workflow
    assert "ACTIONS_ID_TOKEN_REQUEST_URL" in workflow
    assert "ACTIONS_ID_TOKEN_REQUEST_TOKEN" in workflow
    assert "WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION" in workflow
    assert "WP22A_PROVIDER_PHASE_B1_MUTATION_FORBIDDEN" in workflow
    assert "mutation_performed" in workflow
    assert "provision_wp22a_clientless_remote_access.ps1" not in workflow
    assert "tofu apply" not in workflow.lower()
    assert "terraform apply" not in workflow.lower()
    assert "api.cloudflare.com" not in workflow.lower()


def test_controller_validates_signed_github_identity_and_replay() -> None:
    controller = CONTROLLER.read_text(encoding="utf-8")
    required = (
        '"RS256"',
        "VerifyData(",
        "https://token.actions.githubusercontent.com/.well-known/openid-configuration",
        '"https://token.actions.githubusercontent.com"',
        '"omni-cio-wp22a-provider-controller"',
        '"MishaGameHacking/omni-cio-gateway"',
        '"1312247309"',
        '$expectedOwnerActorId = "201947041"',
        '"actor_id"',
        "WP22A_PROVIDER_OIDC_OWNER_ACTOR_MISMATCH",
        '"refs/heads/main"',
        '"workflow_dispatch"',
        '"workflow_ref"',
        '"workflow_sha"',
        '"runner_environment"',
        '"self-hosted"',
        '"run_id"',
        '"run_attempt"',
        "WP22A_PROVIDER_OIDC_RERUN_FORBIDDEN",
        '"exp"',
        '"nbf"',
        '"iat"',
        "$payload.jti",
        "WP22A_PROVIDER_OIDC_JTI_INVALID",
        "WP22A_PROVIDER_OIDC_REPLAY_REJECTED",
    )
    for marker in required:
        assert marker in controller

    assert "api.cloudflare.com" not in controller.lower()
    assert "tofu apply" not in controller.lower()
    assert "terraform apply" not in controller.lower()
    assert "cloudflared tunnel run" not in controller.lower()
    assert "mutation_performed = $false" in controller


def test_result_exchange_is_read_only_to_runner_and_controller_retained() -> None:
    workflow = ACTIVATION.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "$resultRetentionHours = 24" in controller
    assert "function Remove-StaleResultFiles" in controller
    assert "Remove-StaleResultFiles" in controller
    assert "^[0-9a-f]{32}\\.(json|tmp)$" in controller
    assert (
        "$runnerSid = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute"
        in installer
    )
    assert "Remove-Item -LiteralPath $resultPath" not in workflow


def test_installer_protects_controller_and_separates_exchange_roots() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "SupportsShouldProcess" in installer
    assert "WP22A_PROVIDER_MAIN_BRANCH_REQUIRED" in installer
    assert "WP22A_PROVIDER_WORKTREE_NOT_CLEAN" in installer
    assert 'runnerRoot = "C:\\actions-runner"' in installer
    assert "actions.runner.*" in installer
    assert "WP22A_PROVIDER_RUNNER_LOCAL_SYSTEM_FORBIDDEN" in installer
    assert "Assert-RunnerNotAdministrator" in installer
    assert "Get-LocalGroupMember -SID" in installer
    assert "WP22A_PROVIDER_RUNNER_ADMINISTRATOR_FORBIDDEN" in installer
    assert "S-1-5-18" in installer
    assert "S-1-5-32-544" in installer
    assert "Test-PathAclExcludesSid" in installer
    assert "wp22a-provider-controller" in installer
    assert "wp22a-provider-requests" in installer
    assert "wp22a-provider-results" in installer
    assert "New-ScheduledTaskPrincipal" in installer
    assert 'UserId "NT AUTHORITY\\SYSTEM"' in installer
    assert "-ValidateOnly" in installer
    assert "WP22A_PROVIDER_OIDC_OWNER_ACTOR_MISMATCH" in installer
    assert "WP22A_PROVIDER_OIDC_RERUN_FORBIDDEN" in installer
    assert "WP22A_PROVIDER_OWNER_ACTOR_REQUIRED" in installer
    assert "WP22A_PROVIDER_RERUN_FORBIDDEN" in installer
    assert "WP22A_PROVIDER_RERUN_BY_DIFFERENT_ACTOR_FORBIDDEN" in installer
    assert "resultRetentionHours = 24" in installer
    assert "Remove-StaleResultFiles" in installer

    assert "Get-ReviewedBlobText" in installer
    assert "git --no-replace-objects" in installer
    assert "cat-file blob" in installer
    assert "WP22A_PROVIDER_REVIEWED_BLOB_UNAVAILABLE" in installer
    assert "WP22A_PROVIDER_CONTROLLER_REVIEWED_BLOB_COPY_MISMATCH" in installer
    assert "Copy-Item -LiteralPath $sourceController" not in installer

    assert "Read-Host" not in installer
    assert "Cloudflare API token" not in installer
    assert "WP22A_PROVIDER_WORKFLOW_SECRET_REFERENCE_FORBIDDEN" in installer
    assert '.IndexOf("secrets.",' in installer


def test_phase_b1_contract_keeps_provider_and_physical_mutation_blocked() -> None:
    boundary = BOUNDARY.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")
    dormant = DORMANT_PROVISIONER.read_text(encoding="utf-8")

    for marker in (
        "PHASE B SOURCE-ONLY / PROVIDER MUTATION DISABLED",
        "WP22A_PROVIDER_BOUNDARY_READY_NO_MUTATION",
        "mutation_performed=false",
        "trading_methods=false",
        "REAL_TRADING_ENABLED=false",
    ):
        assert marker in boundary
    assert "wp23 remains locked" in boundary.lower()

    assert "OWNER action is **NOT REQUIRED**" in runbook
    assert "Provider apply is intentionally still blocked" in runbook
    assert "physical OWNER evidence" in boundary
    assert "Cloudflare Tunnel token" in dormant
    assert "manual tunnel-token prompt" in runbook
