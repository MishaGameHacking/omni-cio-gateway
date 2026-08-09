[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z]:$')][string]$TargetMountPoint,
    [Parameter(Mandatory = $true)][switch]$RecoveryKeyCustodyConfirmed,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$StateRoot = "C:\ProgramData\OmniCIO\wp10"
$PrepareScript = Join-Path $PSScriptRoot "prepare_wp10_offdevice_target.ps1"
$RehearsalScript = Join-Path $PSScriptRoot "rehearse_wp10_recovery.ps1"
$BackupRunner = Join-Path $PSScriptRoot "run_wp10_backup.ps1"
$OwnerGateScript = $PSCommandPath
$ContractPath = Join-Path $RepoRoot "docs\architecture\V10_WP10_RECOVERY_CONTRACT.json"
$BundleTool = Join-Path $RepoRoot "scripts\v10_wp10_backup_bundle.py"
$OwnerRehearsalPath = Join-Path $StateRoot "owner-rehearsal.sanitized.local.json"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-Sha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "IMPLEMENTATION_FILE_MISSING"
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-Result {
    param([hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }

    Write-Output "WP10 OWNER gate: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Target preparation: $($Result.target_preparation_pass)"
    Write-Output "Off-device recovery rehearsal: $($Result.recovery_rehearsal_pass)"
    Write-Output "Implementation binding: $($Result.implementation_binding_written)"
    Write-Output "Next gate: $($Result.next_gate)"
    Write-Output "Sensitive target identity emitted: NO"
    Write-Output "Recovery key emitted: NO"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    evidence_class = "OWNER_GATE_LOCAL_ORCHESTRATION"
    status = "FAIL"
    reason_code = "OWNER_GATE_NOT_COMPLETED"
    target_preparation_pass = $false
    recovery_rehearsal_pass = $false
    implementation_binding_written = $false
    sanitized_local_evidence_written = $false
    next_gate = "NONADMIN_RUNNER_ACCESS_AUDIT"
    destructive_disk_operation_performed = $false
    recovery_key_value_collected = $false
    target_identity_emitted = $false
}

try {
    if ($env:OS -ne "Windows_NT") {
        throw "WINDOWS_REQUIRED"
    }
    if (-not (Test-Administrator)) {
        throw "OWNER_ADMIN_REQUIRED"
    }
    if (-not [bool]$RecoveryKeyCustodyConfirmed) {
        throw "RECOVERY_KEY_CUSTODY_CONFIRMATION_REQUIRED"
    }
    foreach ($requiredPath in @(
        $PrepareScript,
        $RehearsalScript,
        $BackupRunner,
        $OwnerGateScript,
        $ContractPath,
        $BundleTool
    )) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "OWNER_GATE_IMPLEMENTATION_FILE_MISSING"
        }
    }

    New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null

    # Never allow a previous developer run to satisfy this rebuild's OWNER gate.
    # A failed/incomplete new run leaves no PASS rehearsal behind.
    Remove-Item -LiteralPath $OwnerRehearsalPath -Force -ErrorAction SilentlyContinue

    $prepareRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $PrepareScript `
        -TargetMountPoint $TargetMountPoint `
        -RecoveryKeyCustodyConfirmed `
        -Apply `
        -AsJson 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "OWNER_TARGET_PREPARATION_FAILED"
    }
    try {
        $prepare = ($prepareRaw | Out-String) | ConvertFrom-Json
    }
    catch {
        throw "OWNER_TARGET_PREPARATION_OUTPUT_INVALID"
    }
    if (
        [string]$prepare.status -ne "PASS" -or
        -not [bool]$prepare.non_system_volume -or
        -not [bool]$prepare.data_volume -or
        -not [bool]$prepare.bitlocker_fully_encrypted -or
        -not [bool]$prepare.bitlocker_protection_on -or
        -not [bool]$prepare.recovery_key_custody_confirmed -or
        [bool]$prepare.destructive_disk_operation_performed
    ) {
        throw "OWNER_TARGET_PREPARATION_NOT_PASS"
    }
    $result.target_preparation_pass = $true

    $rehearsalRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $RehearsalScript `
        -UsePreparedOffdeviceTarget `
        -AsJson 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "OWNER_RECOVERY_REHEARSAL_FAILED"
    }
    try {
        $rehearsal = ($rehearsalRaw | Out-String) | ConvertFrom-Json
    }
    catch {
        throw "OWNER_RECOVERY_REHEARSAL_OUTPUT_INVALID"
    }

    if (
        [string]$rehearsal.evidence_class -ne "OWNER_OFFDEVICE_RECOVERY_REHEARSAL" -or
        [string]$rehearsal.status -ne "PASS" -or
        -not [bool]$rehearsal.owner_target_used -or
        -not [bool]$rehearsal.offdevice_copy_pass -or
        -not [bool]$rehearsal.bundle_integrity_pass -or
        -not [bool]$rehearsal.corruption_rejected -or
        -not [bool]$rehearsal.separate_restore_database_used -or
        -not [bool]$rehearsal.restore_probe_exact_match -or
        -not [bool]$rehearsal.temporary_state_cleaned -or
        [bool]$rehearsal.real_secret_values_used -or
        [bool]$rehearsal.private_portfolio_data_used -or
        [bool]$rehearsal.account_identifiers_used -or
        [bool]$rehearsal.production_database_accessed
    ) {
        throw "OWNER_RECOVERY_REHEARSAL_NOT_PASS"
    }
    $result.recovery_rehearsal_pass = $true

    $implementationFingerprint = [ordered]@{
        recovery_contract_sha256 = Get-Sha256Lower -Path $ContractPath
        rehearsal_script_sha256 = Get-Sha256Lower -Path $RehearsalScript
        backup_runner_sha256 = Get-Sha256Lower -Path $BackupRunner
        bundle_tool_sha256 = Get-Sha256Lower -Path $BundleTool
        prepare_script_sha256 = Get-Sha256Lower -Path $PrepareScript
        owner_gate_script_sha256 = Get-Sha256Lower -Path $OwnerGateScript
    }
    $rehearsal | Add-Member `
        -NotePropertyName "implementation_fingerprint" `
        -NotePropertyValue $implementationFingerprint `
        -Force
    $result.implementation_binding_written = $true

    # The owner rehearsal payload is deliberately sanitized: no mount point,
    # serial/UUID, account ID, secret, token or recovery-key value is present.
    # Hashes bind evidence to this exact reviewed WP10 implementation only.
    $rehearsal | ConvertTo-Json -Compress -Depth 7 |
        Set-Content -LiteralPath $OwnerRehearsalPath -Encoding UTF8
    $result.sanitized_local_evidence_written = $true
    $result.status = "PASS"
    $result.reason_code = "OWNER_TARGET_AND_OFFDEVICE_REHEARSAL_PASS"
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -notmatch '^[A-Z0-9_:\-]+$') {
        $message = "OWNER_GATE_ERROR"
    }
    $result.status = "FAIL"
    $result.reason_code = $message
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
