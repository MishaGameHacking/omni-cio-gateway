[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TargetVolume,
    [switch]$RecoveryKeyCustodyConfirmed,
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$SealedWriter = "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Invoke-ChildPowerShellJson {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $output = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $ScriptPath @Arguments 2>&1
    $code = $LASTEXITCODE
    $text = ($output | Out-String).Trim()
    if ($code -ne 0) {
        throw "OWNER_CHILD_GATE_FAILED"
    }
    try {
        return ($text | ConvertFrom-Json)
    }
    catch {
        throw "OWNER_CHILD_GATE_OUTPUT_INVALID"
    }
}

function Write-Result {
    param([Parameter(Mandatory = $true)][hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }

    Write-Output "WP10 OWNER off-device gate: $($Result.status)"
    Write-Output "Target apply: $($Result.target_apply_pass)"
    Write-Output "PostgreSQL off-device restore rehearsal: $($Result.restore_rehearsal_pass)"
    Write-Output "Production backup writer: SEALED"
    Write-Output "Recovery-key value collected: NO"
    Write-Output "Real secrets/private portfolio data used: NO"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    mode = "OWNER_OFFDEVICE_GATE"
    status = "FAIL"
    reason_code = "OWNER_GATE_NOT_COMPLETED"
    target_apply_pass = $false
    restore_rehearsal_pass = $false
    corruption_rejection_pass = $false
    offdevice_copy_pass = $false
    offdevice_cleanup_pass = $false
    recovery_key_custody_confirmed = [bool]$RecoveryKeyCustodyConfirmed
    production_backup_writer_identity = $SealedWriter
    runtime_payload_access_granted = $false
    runner_payload_access_granted = $false
    recovery_key_value_collected = $false
    secret_value_collected = $false
    private_portfolio_data_collected = $false
    production_database_accessed = $false
}

try {
    if (-not (Test-IsAdministrator)) {
        throw "OWNER_ADMIN_REQUIRED"
    }
    if (-not $RecoveryKeyCustodyConfirmed) {
        throw "RECOVERY_KEY_CUSTODY_CONFIRMATION_REQUIRED"
    }

    $prepareScript = Join-Path $PSScriptRoot "prepare_wp10_offdevice_target.ps1"
    $rehearsalScript = Join-Path $PSScriptRoot "rehearse_wp10_recovery.ps1"
    foreach ($path in @($prepareScript, $rehearsalScript)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "OWNER_GATE_SCRIPT_MISSING"
        }
    }

    $prepared = Invoke-ChildPowerShellJson -ScriptPath $prepareScript -Arguments @(
        "-TargetVolume", $TargetVolume,
        "-Apply",
        "-RecoveryKeyCustodyConfirmed",
        "-AsJson"
    )
    if (
        $prepared.status -ne "READY" -or
        $prepared.reason_code -ne "TARGET_APPLY_PASS" -or
        -not [bool]$prepared.applied -or
        [string]$prepared.production_backup_writer_identity -ne $SealedWriter -or
        [bool]$prepared.runtime_payload_access_granted -or
        [bool]$prepared.runner_payload_access_granted -or
        [bool]$prepared.private_payload_used -or
        [bool]$prepared.secret_value_used -or
        [bool]$prepared.recovery_key_value_used
    ) {
        throw "OWNER_TARGET_APPLY_INVALID"
    }
    $result.target_apply_pass = $true

    $rehearsed = Invoke-ChildPowerShellJson -ScriptPath $rehearsalScript -Arguments @(
        "-UsePreparedOffdeviceTarget",
        "-AsJson"
    )
    if (
        $rehearsed.status -ne "PASS" -or
        $rehearsed.mode -ne "OWNER_OFFDEVICE_RECOVERY_REHEARSAL" -or
        -not [bool]$rehearsed.bundle_integrity_pass -or
        -not [bool]$rehearsed.corruption_rejected -or
        -not [bool]$rehearsed.offdevice_copy_pass -or
        -not [bool]$rehearsed.restore_probe_pass -or
        -not [bool]$rehearsed.offdevice_cleanup_pass -or
        -not [bool]$rehearsed.temporary_state_cleaned -or
        [bool]$rehearsed.real_secret_values_used -or
        [bool]$rehearsed.private_portfolio_data_used -or
        [bool]$rehearsed.account_identifiers_used -or
        [bool]$rehearsed.production_database_accessed
    ) {
        throw "OWNER_RECOVERY_REHEARSAL_INVALID"
    }

    $result.restore_rehearsal_pass = $true
    $result.corruption_rejection_pass = $true
    $result.offdevice_copy_pass = $true
    $result.offdevice_cleanup_pass = $true
    $result.status = "PASS"
    $result.reason_code = "OWNER_OFFDEVICE_GATE_PASS"
}
catch {
    if ($_.Exception.Message -match "^[A-Z0-9_:-]+$") {
        $result.reason_code = $_.Exception.Message
    }
    else {
        $result.reason_code = "OWNER_OFFDEVICE_GATE_ERROR"
    }
    $result.status = "FAIL"
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
exit 0
