from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp22a_private_remote_access.ps1"
)
DIAGNOSTIC = ROOT / "infrastructure" / "windows" / "diagnose_wp22a_local_state.ps1"
RUNNER_AUDITOR = ROOT / "infrastructure" / "windows" / "audit_wp22a_runner_loopback.ps1"
OWNER_FINALIZER = (
    ROOT / "infrastructure" / "windows" / "finalize_wp22a_owner_evidence.ps1"
)
OWNER_WORKFLOW = (
    ROOT / ".github" / "workflows" / "v10-wp22a-owner-private-remote-audit.yml"
)
LOCAL_APP_FACTORY = ROOT / "apps" / "api" / "app.py"
REMOTE_FACTORY = ROOT / "apps" / "api" / "wp22a_remote.py"


def test_provisioner_blocks_runner_loopback_and_rebuilds_local_runtime_on_rollback() -> (
    None
):
    source = PROVISIONER.read_text(encoding="utf-8")
    base_entrypoint = source[
        source.index("function Invoke-BaseProvisioner") : source.index(
            "function Remove-RunnerLoopbackFirewall"
        )
    ]
    assert "start_wp15_live_web_acceptance.ps1" in source
    assert (
        '$entrypoint = if ($Mode -eq "Apply") { $baseStarter } else { $baseProvisioner }'
        in base_entrypoint
    )
    assert '"-File", $entrypoint' in base_entrypoint
    assert 'if ($Mode -eq "Cleanup") { $arguments += "-Cleanup" }' in base_entrypoint
    assert '"-Apply"' not in base_entrypoint
    assert '"actions.runner.*"' in source
    assert '"OmniCIO.V10.WP22A.BlockRunnerLoopback"' in source
    assert "New-NetFirewallRule" in source
    assert "-Direction Outbound" in source
    assert "-Action Block" in source
    assert "-RemoteAddress 127.0.0.1" in source
    assert "-LocalUser $runnerSddl" in source
    assert "Get-NetFirewallSecurityFilter" in source
    assert '$expectedRunnerSddl = "D:(A;;CC;;;$runnerSid)"' in source
    assert "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND" in source
    assert 'Arguments @("funnel", "status") -AllowFailure' in source
    assert "WP22A_TAILSCALE_FUNNEL_STATUS_UNAVAILABLE" in source
    assert "Disable-ServeChecked -Exe $TailscaleExe" in source
    assert 'Arguments @("serve", "reset") -AllowFailure' in source
    assert "WP22A_TAILSCALE_SERVE_RESET_FAILED" in source
    assert 'Arguments @("serve", "off")' not in source
    assert 'Arguments @("serve", "status") -AllowFailure' in source
    assert "WP22A_TAILSCALE_SERVE_DISABLE_FAILED" in source
    assert source.count("Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup") == 2
    assert source.count("Invoke-BaseProvisioner -Sha $Sha -Mode Apply") == 2
    assert "$baseTaskPresent =" not in source
    assert "WP22A_LOCAL_WEB_ROLLBACK_NOT_RUNNING" in source
    assert "Start-ScheduledTask -TaskName $baseTaskName" not in source
    assert '"::1"' not in source


def test_remote_cutover_reuses_only_an_accepted_exact_head_base_runtime() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    base_boundary = source[
        source.index("function Get-BaseWebFailureReason") : source.index(
            "function Remove-RunnerLoopbackFirewall"
        )
    ]
    cutover = source[
        source.index("function Install-RemoteTask") : source.index(
            "function Test-BackendLoopback"
        )
    ]

    assert "function Test-BaseLocalWebReady" in base_boundary
    assert "function Ensure-BaseLocalWebReady" in base_boundary
    assert "Invoke-BaseProvisioner -Sha $Sha -Mode Verify" in base_boundary
    assert 'if ($Mode -eq "Verify") { $arguments += "-Verify" }' in base_boundary
    assert "Get-BaseWebFailureReason -Text $text -Mode $Mode" in base_boundary
    assert "ConvertFrom-Json -ErrorAction Stop" in base_boundary
    assert "WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY" in base_boundary
    assert "WP15_LIVE_TASK_NOT_RUNNING" in base_boundary
    assert "WP15_LIVE_RUNNER_PRIVATE_WRITE_EXPOSED" in base_boundary
    assert "Ensure-BaseLocalWebReady -Sha $Sha" in cutover
    assert "Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup" not in cutover
    assert "Invoke-BaseProvisioner -Sha $Sha -Mode Apply" not in cutover


def test_remote_task_persists_only_its_owned_batch_logon_right() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")

    assert '"SeBatchLogonRight"' in source
    assert '"SeDenyBatchLogonRight"' in source
    assert "LsaEnumerateAccountRights" in source
    assert "LsaAddAccountRights" in source
    assert "LsaRemoveAccountRights" in source
    assert "BatchRightOwned=true" in source
    assert "BatchRightOwned=false" in source
    assert "Test-RemoteTaskOwnsBatchRight" in source
    assert "Remove-RemoteBatchRightIfOwned" in source
    assert "WP22A_REMOTE_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT" in source
    assert "WP22A_REMOTE_RUNTIME_BATCH_LOGON_RIGHT_UNAVAILABLE" in source
    assert "WP22A_REMOTE_RUNTIME_BATCH_LOGON_RIGHT_CLEANUP_FAILED" in source
    assert "-Description $taskDescription -Force" in source
    assert "remote_runtime_batch_logon_bound" in source
    assert "remote_runtime_batch_logon_restored" in source
    assert "WP22A_REMOTE_TASK_BATCH_LOGON_DENIED" in source
    assert "WP22A_REMOTE_TASK_HAS_NOT_RUN" in source
    assert "SeServiceLogonRight" not in source
    assert "SeInteractiveLogonRight" not in source


def test_provisioner_preserves_sanitized_primary_and_rollback_failure_reasons() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    assert "function Get-SafeReasonCode" in source
    assert '"-AsJson"' in source
    assert "*> $null" not in source
    assert "WP22A_APPLY_FAILED:{0};LOCAL_ROLLBACK_FAILED:{1}" in source
    assert "WP22A_APPLY_FAILED:{0};LOCAL_ROLLBACK_PASS" in source
    assert "WP22A_TAILSCALE_HTTPS_CONSENT_REQUIRED" in source


def test_provisioner_encodes_runtime_password_before_clearing_entropy() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    generator = source[source.index("function New-RandomRuntimePassword") :]
    generator = generator[: generator.index("function Invoke-BaseProvisioner")]
    encode = generator.index("$password = [Convert]::ToBase64String($bytes)")
    clear = generator.index("[Array]::Clear($bytes, 0, $bytes.Length)")
    returned = generator.index("return $password")
    assert encode < clear < returned
    assert "return [Convert]::ToBase64String($bytes)" not in generator


def test_sanitized_local_diagnostic_treats_protected_paths_as_state_not_failure() -> (
    None
):
    source = DIAGNOSTIC.read_text(encoding="utf-8")
    assert 'evidence_class = "SANITIZED_LOCAL_DEPLOYMENT_DIAGNOSTIC"' in source
    assert "function Get-PathStateSafe" in source
    assert 'return "ACCESS_DENIED"' in source
    assert "runtime_root_state" in source
    assert "deployment_marker_state" in source
    assert "protected_runtime_path_access_denied" in source
    assert "backend_listener_query_available" in source
    assert "runner_loopback_firewall_query_available" in source
    assert "base_task_state" in source
    assert "remote_task_state" in source
    assert "tailscale_serve_configured" in source
    assert "tailscale_serve_targets_backend_port" in source
    assert "funnel_public_ingress" in source
    assert "raw_tailnet_hostname_emitted = $false" in source
    assert "raw_owner_login_emitted = $false" in source
    assert "raw_runner_identity_emitted = $false" in source
    assert "secret_value_emitted = $false" in source
    assert '"::1"' not in source


def test_sanitized_local_diagnostic_keeps_scheduler_result_without_message_or_identity() -> (
    None
):
    source = DIAGNOSTIC.read_text(encoding="utf-8")
    assert "function Get-TaskSchedulerHistorySafe" in source
    assert 'LogName = "Microsoft-Windows-TaskScheduler/Operational"' in source
    assert "task_scheduler_history_query_available" in source
    assert "wp15_task_history_found" in source
    assert "wp15_latest_scheduler_event_id" in source
    assert "wp15_latest_scheduler_event_level" in source
    assert "wp15_latest_scheduler_event_at_utc" in source
    assert "wp15_latest_scheduler_result_event_id" in source
    assert "wp15_latest_scheduler_result_code" in source
    assert "wp15_latest_scheduler_result_event_at_utc" in source
    assert "wp22a_remote_task_history_found" in source
    assert "wp22a_remote_latest_scheduler_event_id" in source
    assert "wp22a_remote_latest_scheduler_result_code" in source
    assert "wp22a_remote_latest_scheduler_result_event_at_utc" in source
    assert "task_scheduler_message_emitted = $false" in source
    assert ".Message" not in source
    assert "ActionName" not in source
    assert "UserContext" not in source


def test_remote_factory_uses_wp22a_short_session_policy_and_verified_database() -> None:
    remote_source = REMOTE_FACTORY.read_text(encoding="utf-8")
    local_source = LOCAL_APP_FACTORY.read_text(encoding="utf-8")
    assert "create_local_private_app(" in remote_source
    assert "session_policy=REMOTE_SESSION_POLICY" in remote_source
    assert "verify_existing_database=True" in remote_source
    assert "policy=REMOTE_SESSION_POLICY" in remote_source
    assert "session_policy: SessionPolicyV1 | None = None" in local_source
    assert "verify_existing_database: bool = False" in local_source
    assert "if live_acceptance_enabled or verify_existing_database:" in local_source
    assert "if session_policy is None:" in local_source
    assert "PostgresWebSessionRegistryV1(connection)" in local_source
    assert "policy=session_policy" in local_source


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
    assert "local_app_factory_sha256" in source


def test_runner_auditor_requires_live_denials_for_backend_and_owner_evidence() -> None:
    source = RUNNER_AUDITOR.read_text(encoding="utf-8")
    connection_probe = source[
        source.index("function Test-RunnerConnectionDenied") : source.index(
            "function Test-FileWriteDenied"
        )
    ]
    assert "Get-NetTCPConnection -State Listen" in source
    assert "Get-NetFirewallSecurityFilter" in source
    assert '$expectedRunnerSddl = "D:(A;;CC;;;$RunnerSid)"' in source
    assert "[System.Net.Sockets.TcpClient]::new()" in source
    assert "function Get-TailscaleSelfIdentity" in source
    assert "function Test-RemoteTaskIdentityBinding" in source
    assert "function Test-RunnerPrivateServeSpoofDenied" in source
    assert "$handler.UseProxy = $false" in source
    assert '"Tailscale-User-Login"' in source
    assert (
        "catch [System.Net.Sockets.SocketException] { return $true }"
        in connection_probe
    )
    assert "catch { return $false }" in connection_probe
    assert "remote_task_running_after_probe" in source
    assert "loopback_listener_present_after_probe" in source
    assert "Test-FileWriteDenied" in source
    assert "Test-CreateDenied" in source
    assert "Test-RenameDenied" in source
    assert '"WP22A_RUNNER_NETWORK_AND_EVIDENCE_MUTATION_DENIED"' in source
    assert "runner_loopback_connection_denied" in source
    assert "remote_task_identity_binding_current" in source
    assert "runner_private_serve_identity_spoof_denied" in source
    assert "runner_owner_evidence_file_write_denied" in source
    assert "runner_owner_evidence_create_denied" in source
    assert "runner_owner_evidence_rename_denied" in source
    assert "raw_runner_identity_emitted = $false" in source
    assert "raw_runner_sid_emitted = $false" in source
    assert '"::1"' not in source


def test_owner_audit_reports_sanitized_state_before_requiring_owner_evidence() -> None:
    source = OWNER_WORKFLOW.read_text(encoding="utf-8")
    assert '- "apps/web/**"' in source
    diagnostic = source.index("diagnose_wp22a_local_state.ps1")
    require_evidence = source.index("Require real local OWNER phone rehearsal evidence")
    probe = source.index("audit_wp22a_runner_loopback.ps1")
    validate = source.index("validate_v10_wp22a_owner_evidence.py")
    assert diagnostic < require_evidence < probe < validate


def test_owner_audit_uses_cmd_wrapper_for_bypass_powershell_child_processes() -> None:
    source = OWNER_WORKFLOW.read_text(encoding="utf-8")
    assert "shell: powershell" not in source
    bypass = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File"
    assert source.count(bypass) >= 2
    assert 'diagnose_wp22a_local_state.ps1" -AsJson' in source
    assert (
        'audit_wp22a_runner_loopback.ps1" -ExpectedImplementationSha '
        '"%EXPECTED_HEAD%" -AsJson'
    ) in source
