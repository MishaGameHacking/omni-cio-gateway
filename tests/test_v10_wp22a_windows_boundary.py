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


def test_tailscale_serve_enable_is_bounded_and_never_auto_accepts() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    bounded = source[
        source.index("function Invoke-TailscaleServeEnableBounded") : source.index(
            "function Get-TailscaleIdentity"
        )
    ]
    enable = source[
        source.index("function Enable-ServeChecked") : source.index(
            "function Get-RemoteAcceptanceState"
        )
    ]

    assert "System.Diagnostics.ProcessStartInfo" in bounded
    assert "RedirectStandardOutput = $true" in bounded
    assert "RedirectStandardError = $true" in bounded
    assert "ReadToEndAsync()" in bounded
    assert "WaitForExit($TimeoutMilliseconds)" in bounded
    assert "WaitForExit(5000)" in bounded
    assert "$process.Kill()" in bounded
    assert "WP22A_TAILSCALE_SERVE_PROCESS_START_FAILED" in bounded
    assert "WP22A_TAILSCALE_SERVE_PROCESS_TERMINATION_FAILED" in bounded
    assert "timed_out" in bounded
    assert "Write-Output" not in bounded
    assert "Invoke-TailscaleServeEnableBounded -Exe $Exe" in enable
    assert "WP22A_TAILSCALE_HTTPS_CONSENT_REQUIRED" in enable
    assert "WP22A_TAILSCALE_SERVE_ENABLE_TIMEOUT" in enable
    assert '"--yes"' not in source
    assert 'Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "--bg"' not in enable


def test_apply_post_cutover_acceptance_stays_inside_rollback_boundary() -> None:
    source = PROVISIONER.read_text(encoding="utf-8")
    apply_start = source.rindex("if ($Apply) {")
    verify_start = source.index("if ($null -eq $acceptance)", apply_start)
    apply_block = source[apply_start:verify_start]
    acceptance = source[
        source.index("function Get-RemoteAcceptanceState") : source.index(
            "function Get-RemoteAcceptanceFailureReason"
        )
    ]

    assert "Get-RemoteAcceptanceState -Exe $tailscale" in apply_block
    assert "Get-RemoteAcceptanceFailureReason -State $acceptance" in apply_block
    assert "Restore-LocalWebTask -Sha $sha -TailscaleExe $tailscale" in apply_block
    assert apply_block.index(
        "Get-RemoteAcceptanceState -Exe $tailscale"
    ) < apply_block.index("catch {")
    assert "Test-NoFunnel -Exe $Exe" in acceptance
    assert "Test-LocalServeIdentitySpoofDenied" in acceptance
    assert "local_serve_identity_spoof_denied" in acceptance
    assert "Test-RemoteOwnerSession" not in source
    assert "WP22A_LOCAL_SERVE_IDENTITY_SPOOF_NOT_DENIED" in source
    assert 'reason = "WP22A_PRIVATE_REMOTE_INFRASTRUCTURE_ACCEPTED"' not in source
    assert '"WP22A_PRIVATE_REMOTE_INFRASTRUCTURE_ACCEPTED"' in source
    assert "owner_identity_binding = $null" in source
    assert "secure_server_session = $null" in source


def test_local_self_serve_is_a_negative_identity_probe_not_positive_owner_proof() -> (
    None
):
    source = PROVISIONER.read_text(encoding="utf-8")
    identity = source[
        source.index("function Get-TailscaleIdentity") : source.index(
            "function Test-NoFunnel"
        )
    ]
    probe = source[
        source.index("function Test-LocalServeIdentitySpoofDenied") : source.index(
            "function Enable-ServeChecked"
        )
    ]
    acceptance = source[
        source.index("function Get-RemoteAcceptanceState") : source.index(
            "function Get-RemoteAcceptanceFailureReason"
        )
    ]
    result = source[source.rindex("$result = [ordered]@{") :]

    assert "owner_login = $login" in identity
    assert "$handler.UseProxy = $false" in probe
    assert '[Parameter(Mandatory = $true)][string]$OwnerLogin' in probe
    assert '"Tailscale-User-Login"' in probe
    assert "$OwnerLogin" in probe
    assert '"wp22a-local-spoof.invalid"' not in probe
    assert "return [int]$response.StatusCode -eq 403" in probe
    assert "Use the real OWNER login only in memory." in probe
    assert "private-tailnet-login" not in probe
    assert "-OwnerLogin $OwnerLogin" in acceptance
    assert "-OwnerLogin $identity.owner_login" in source
    assert "owner_login" not in result


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
    assert "deployment_state_class" in source
    assert "apply_in_progress_or_blocked" in source
    assert "WP22A_REMOTE_RUNTIME_SERVE_PENDING" in source
    assert "WP22A_PRIVATE_REMOTE_RUNTIME_PRESENT" in source
    assert "WP22A_PUBLIC_INGRESS_FORBIDDEN" in source
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
    protect = source.index("Set-ProtectedEvidenceAcl -RunnerSid $runnerSid")
    remove = source.index("Remove-Item -LiteralPath $evidencePath", protect)

    assert "SetAccessRuleProtection($true, $false)" in source
    assert "ReadAndExecute" in source
    assert "WP22A_OWNER_EVIDENCE_ACL_INVALID" in source
    assert "evidence_acl_protected = $true" in source
    assert "runner_evidence_read_allowed = $true" in source
    assert "runner_evidence_write_allowed = $false" in source
    assert "raw_runner_identity_collected = $false" in source
    assert "raw_runner_sid_collected = $false" in source
    assert "local_app_factory_sha256" in source
    assert "OwnerPrivateLoginConfirmed" in source
    assert "WP22A_OWNER_PRIVATE_LOGIN_CONFIRMATION_REQUIRED" in source
    assert "WP22A_PRIVATE_REMOTE_INFRASTRUCTURE_ACCEPTED" in source
    assert "local_serve_identity_spoof_denied" in source
    assert "WP22A_EVIDENCE_PARENT_REPARSE_POINT_FORBIDDEN" in source
    assert "WP22A_EVIDENCE_ROOT_REPARSE_POINT_FORBIDDEN" in source
    assert protect < remove


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


def test_owner_apply_wrapper_persists_only_sanitized_result() -> None:
    wrapper = ROOT / "infrastructure" / "windows" / "invoke_wp22a_owner_apply_safe.ps1"
    runbook = (
        ROOT / "docs" / "operations" / "V10_WP22A_PRIVATE_REMOTE_ACCESS_RUNBOOK.md"
    ).read_text(encoding="utf-8")
    source = wrapper.read_text(encoding="utf-8")
    workflow = OWNER_WORKFLOW.read_text(encoding="utf-8")

    marker = source.index('reason = "WP22A_OWNER_APPLY_IN_PROGRESS"')
    child = source.index("& powershell.exe")
    assert marker < child
    assert source.count("Save-SanitizedResult -Result $result") == 2
    assert "provision_wp22a_private_remote_access.ps1" in source
    assert "-ExpectedImplementationSha $recordedImplementationSha" in source
    assert "-Apply" in source
    assert "-AsJson 2>&1" in source
    assert "wp22a-owner-apply.sanitized.local.json" in source
    assert "SetAccessRuleProtection($true, $false)" in source
    assert "S-1-5-18" in source
    assert "S-1-5-32-544" in source
    assert "ReparsePoint" in source
    assert "System.IO.File]::WriteAllText" in source
    assert "System.IO.File]::Replace" in source
    assert "WP22A_SAFE_RESULT_PERSIST_FAILED" in source
    assert "OWNER_APPLY_SANITIZED_LOCAL_RESULT" in source
    assert "WP22A_PRIVATE_REMOTE_INFRASTRUCTURE_ACCEPTED" in source
    assert "local_serve_identity_spoof_denied" in source
    assert "$null -ne $payload.owner_identity_binding" in source
    assert "$null -ne $payload.secure_server_session" in source
    assert "raw_child_output_persisted = $false" in source
    assert "raw_child_output_emitted = $false" in source
    assert "private_url_persisted = $false" in source
    assert "private_url_emitted = $false" in source
    assert "private_identity_persisted = $false" in source
    assert "secret_value_persisted = $false" in source
    assert "$captured | Set-Content" not in source
    assert "$capturedText | Set-Content" not in source
    assert "Write-Output $captured" not in source
    assert "Write-Output $capturedText" not in source
    assert '"--yes"' not in source
    assert "invoke_wp22a_owner_apply_safe.ps1" in runbook
    assert "infrastructure/windows/*wp22a*" in workflow
