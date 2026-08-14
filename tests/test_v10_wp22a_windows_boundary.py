from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp22a_private_remote_access.ps1"
)
RUNNER_AUDITOR = (
    ROOT / "infrastructure" / "windows" / "audit_wp22a_runner_loopback.ps1"
)
OWNER_FINALIZER = (
    ROOT / "infrastructure" / "windows" / "finalize_wp22a_owner_evidence.ps1"
)
OWNER_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp22a-owner-private-remote-audit.yml"
)


def test_provisioner_blocks_runner_loopback_and_rebuilds_local_runtime_on_rollback() -> (
    None
):
    source = PROVISIONER.read_text(encoding="utf-8")
    assert '"actions.runner.*"' in source
    assert '"OmniCIO.V10.WP22A.BlockRunnerLoopback"' in source
    assert "New-NetFirewallRule" in source
    assert "-Direction Outbound" in source
    assert "-Action Block" in source
    assert "-RemoteAddress 127.0.0.1" in source
    assert "-LocalUser $runnerSddl" in source
    assert "Get-NetFirewallSecurityFilter" in source
    assert "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND" in source
    assert "Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup" in source
    assert "Invoke-BaseProvisioner -Sha $Sha -Mode Apply" in source
    assert "Start-ScheduledTask -TaskName $baseTaskName" not in source


def test_owner_finalizer_protects_evidence_with_runner_read_only_acl() -> None:
    source = OWNER_FINALIZER.read_text(encoding="utf-8")
    assert "SetAccessRuleProtection($true, $false)" in source
    assert "ReadAndExecute" in source
    assert "WP22A_OWNER_EVIDENCE_ACL_INVALID" in source
    assert "evidence_acl_protected = $true" in source
    assert "runner_evidence_read_allowed = $true" in source
    assert "runner_evidence_write_allowed = $false" in source
    assert "raw_runner_identity_collected = $false" in source
    assert "raw_runner_sid_collected = $false" in source


def test_runner_auditor_requires_live_denials_for_backend_and_owner_evidence() -> None:
    source = RUNNER_AUDITOR.read_text(encoding="utf-8")
    assert "Get-NetTCPConnection -State Listen" in source
    assert "Get-NetFirewallSecurityFilter" in source
    assert "[System.Net.Sockets.TcpClient]::new()" in source
    assert "Test-FileWriteDenied" in source
    assert "Test-CreateDenied" in source
    assert "Test-RenameDenied" in source
    assert '"WP22A_RUNNER_LOOPBACK_AND_EVIDENCE_MUTATION_DENIED"' in source
    assert "runner_loopback_connection_denied" in source
    assert "runner_owner_evidence_file_write_denied" in source
    assert "runner_owner_evidence_create_denied" in source
    assert "runner_owner_evidence_rename_denied" in source
    assert "raw_runner_identity_emitted = $false" in source
    assert "raw_runner_sid_emitted = $false" in source


def test_owner_audit_runs_runner_spoof_probe_before_accepting_evidence() -> None:
    source = OWNER_WORKFLOW.read_text(encoding="utf-8")
    probe = source.index("audit_wp22a_runner_loopback.ps1")
    validate = source.index("validate_v10_wp22a_owner_evidence.py")
    assert probe < validate
