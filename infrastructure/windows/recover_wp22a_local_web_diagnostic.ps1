[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$baseProvisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp15_live_web_acceptance.ps1"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP22A_WORKTREE_NOT_CLEAN" }
    return $actual
}

function Get-SafeReasonCode {
    param(
        [AllowNull()][string]$Text,
        [Parameter(Mandatory = $true)][string]$Fallback
    )

    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        $matches = [regex]::Matches($Text, '(?<![A-Z0-9_])(?:WP15|WP17|WP22A)_[A-Z0-9_]+')
        if ($matches.Count -gt 0) { return [string]$matches[$matches.Count - 1].Value }
    }
    return $Fallback
}

function Invoke-BaseProvisionerCaptured {
    param([Parameter(Mandatory = $true)][ValidateSet("Apply", "Cleanup")][string]$Mode)

    $modeArgument = if ($Mode -eq "Apply") { "-Apply" } else { "-Cleanup" }
    $arguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", $baseProvisioner,
        "-ExpectedImplementationSha", $ExpectedImplementationSha,
        $modeArgument,
        "-Port", [string]$Port,
        "-AsJson"
    )
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& powershell.exe @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [ordered]@{
        exit_code = [int]$exitCode
        text = (($output | ForEach-Object { [string]$_ }) -join "`n")
    }
}

function Get-NotReadyDetails {
    param([AllowNull()][string]$Text)

    $details = [ordered]@{
        found = $false
        task_state = ""
        last_task_result = ""
        result_class = ""
    }
    if ([string]::IsNullOrWhiteSpace($Text)) { return $details }

    $match = [regex]::Match(
        $Text,
        'WP15_LIVE_LOOPBACK_RUNTIME_NOT_READY;\s*task_state=([A-Za-z]+);\s*last_task_result=(-?[0-9]+)'
    )
    if (-not $match.Success) { return $details }

    $taskState = $match.Groups[1].Value.ToUpperInvariant()
    $resultText = $match.Groups[2].Value
    [int64]$resultValue = 0
    if (-not [int64]::TryParse($resultText, [ref]$resultValue)) { return $details }

    $class = switch ($resultValue) {
        71 { "WP15_SESSION_PROBE_CONNECTION_FAILED" }
        72 { "WP15_SESSION_PROBE_CREATE_FAILED" }
        73 { "WP15_SESSION_PROBE_RESOLVE_FAILED" }
        74 { "WP15_SESSION_PROBE_REVOKE_FAILED" }
        75 { "WP15_SESSION_PROBE_CLEANUP_FAILED" }
        76 { "WP15_SESSION_PROBE_BOOTSTRAP_FAILED" }
        267008 { "TASK_SCHEDULER_READY" }
        267009 { "TASK_SCHEDULER_RUNNING" }
        267010 { "TASK_SCHEDULER_DISABLED" }
        267011 { "TASK_SCHEDULER_HAS_NOT_RUN" }
        267012 { "TASK_SCHEDULER_NO_MORE_RUNS" }
        267013 { "TASK_SCHEDULER_NOT_SCHEDULED" }
        267014 { "TASK_SCHEDULER_TERMINATED" }
        default { "WP15_RUNTIME_RESULT_OTHER" }
    }

    $details.found = $true
    $details.task_state = $taskState
    $details.last_task_result = [string]$resultValue
    $details.result_class = $class
    return $details
}

function Write-Result {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 4 -Compress
        return
    }
    foreach ($key in $Result.Keys) { Write-Output ("{0}: {1}" -f $key, $Result[$key]) }
}

if ($env:OS -ne "Windows_NT") { throw "WP22A_WINDOWS_REQUIRED" }
if (-not (Test-Administrator)) { throw "WP22A_OWNER_ADMIN_REQUIRED" }
$sha = Get-ReviewedHead
if (-not (Test-Path -LiteralPath $baseProvisioner -PathType Leaf)) {
    throw "WP22A_BASE_WEB_PROVISIONER_MISSING"
}

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_class = "LOCAL_WEB_RECOVERY_DIAGNOSTIC"
    implementation_sha = $sha
    status = "FAIL"
    reason_code = "WP22A_LOCAL_WEB_RECOVERY_NOT_RUN"
    pre_cleanup_pass = $false
    base_apply_pass = $false
    wp15_reason_code = ""
    wp15_runtime_not_ready_detail_found = $false
    wp15_task_state = ""
    wp15_last_task_result = ""
    wp15_last_task_result_class = ""
    post_failure_cleanup_pass = $false
    local_web_restored = $false
    final_safe_state = $false
    raw_child_output_emitted = $false
    task_scheduler_message_emitted = $false
    raw_identity_emitted = $false
    secret_value_emitted = $false
}

$preCleanup = Invoke-BaseProvisionerCaptured -Mode Cleanup
if ($preCleanup.exit_code -ne 0) {
    $result.reason_code = "WP22A_LOCAL_RECOVERY_PRE_CLEANUP_FAILED"
    $result.wp15_reason_code = Get-SafeReasonCode -Text $preCleanup.text -Fallback "WP15_CLEANUP_FAILED"
    Write-Result -Result $result
    exit 1
}
$result.pre_cleanup_pass = $true

$apply = Invoke-BaseProvisionerCaptured -Mode Apply
if ($apply.exit_code -eq 0) {
    $result.status = "PASS"
    $result.reason_code = "WP22A_LOCAL_WEB_RECOVERY_PASS"
    $result.base_apply_pass = $true
    $result.local_web_restored = $true
    $result.final_safe_state = $true
    Write-Result -Result $result
    exit 0
}

$result.wp15_reason_code = Get-SafeReasonCode -Text $apply.text -Fallback "WP15_APPLY_FAILED"
$notReady = Get-NotReadyDetails -Text $apply.text
$result.wp15_runtime_not_ready_detail_found = [bool]$notReady.found
$result.wp15_task_state = [string]$notReady.task_state
$result.wp15_last_task_result = [string]$notReady.last_task_result
$result.wp15_last_task_result_class = [string]$notReady.result_class

$postCleanup = Invoke-BaseProvisionerCaptured -Mode Cleanup
$result.post_failure_cleanup_pass = [bool]($postCleanup.exit_code -eq 0)
$result.final_safe_state = [bool]$result.post_failure_cleanup_pass
if (-not $result.post_failure_cleanup_pass) {
    $result.reason_code = "WP22A_LOCAL_RECOVERY_DIAGNOSTIC_CLEANUP_FAILED"
}
elseif ($notReady.found) {
    $result.reason_code = "WP22A_LOCAL_RECOVERY_DIAGNOSTIC_CAPTURED"
}
else {
    $result.reason_code = "WP22A_LOCAL_RECOVERY_APPLY_FAILED"
}

Write-Result -Result $result
exit 1
