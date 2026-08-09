[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TargetVolume,
    [switch]$Apply,
    [switch]$RecoveryKeyCustodyConfirmed,
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$BackupRootName = "OmniCIO-WP10-Backups"
$TargetMarkerName = ".omni-cio-wp10-target.json"
$SentinelName = ".wp10-access-sentinel.bin"
$EvidenceRoot = "C:\ProgramData\OmniCIO\wp10"
$EvidencePath = Join-Path $EvidenceRoot "offdevice-target.json"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Resolve-LocalAccountSid {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $account = New-Object Security.Principal.NTAccount(
        "$env:COMPUTERNAME\$AccountName"
    )
    try {
        return $account.Translate(
            [Security.Principal.SecurityIdentifier]
        ).Value
    }
    catch {
        throw "LOCAL_ACCOUNT_NOT_FOUND:$AccountName"
    }
}

function Invoke-IcaclsChecked {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & icacls.exe @Arguments *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "ICACLS_FAILED"
    }
}

function ConvertTo-TargetMountPoint {
    param([Parameter(Mandatory = $true)][string]$Value)

    $trimmed = $Value.Trim()
    if ($trimmed -notmatch "^[A-Za-z]:\\?$") {
        throw "TARGET_VOLUME_MUST_BE_DRIVE_ROOT"
    }
    return ($trimmed.Substring(0, 2).ToUpperInvariant())
}

function Write-OutputResult {
    param([Parameter(Mandatory = $true)][hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }

    Write-Output "WP10 off-device target status: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Non-system volume: $($Result.non_system_volume)"
    Write-Output "BitLocker fully encrypted: $($Result.bitlocker_fully_encrypted)"
    Write-Output "BitLocker protection on: $($Result.bitlocker_protection_on)"
    Write-Output "Recovery-key custody confirmed: $($Result.recovery_key_custody_confirmed)"
    Write-Output "Runner payload access granted: NO"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    mode = $(if ($Apply) { "OWNER_APPLY" } else { "OWNER_PREVIEW" })
    status = "BLOCKED"
    reason_code = "TARGET_NOT_VERIFIED"
    target_class = "BITLOCKER_OWNER_CONTROLLED_NON_SYSTEM_VOLUME"
    target_mount_point = "UNKNOWN"
    backup_root_name = $BackupRootName
    marker_name = $TargetMarkerName
    non_system_volume = $false
    data_volume = $false
    bitlocker_state_known = $false
    bitlocker_fully_encrypted = $false
    bitlocker_protection_on = $false
    recovery_key_custody_confirmed = [bool]$RecoveryKeyCustodyConfirmed
    runtime_identity_resolved = $false
    runner_identity_resolved = $false
    runner_payload_access_granted = $false
    target_marker_present = $false
    sentinel_present = $false
    applied = $false
    private_payload_used = $false
    secret_value_used = $false
    recovery_key_value_used = $false
}

try {
    $mountPoint = ConvertTo-TargetMountPoint -Value $TargetVolume
    $result.target_mount_point = $mountPoint

    $systemRoot = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\")
    if ($mountPoint -eq $systemRoot) {
        throw "SYSTEM_VOLUME_FORBIDDEN"
    }
    $result.non_system_volume = $true

    $drive = Get-PSDrive -Name $mountPoint.Substring(0, 1) -PSProvider FileSystem `
        -ErrorAction Stop
    if ($null -eq $drive.Root) {
        throw "TARGET_VOLUME_NOT_MOUNTED"
    }

    $bitlocker = Get-BitLockerVolume -MountPoint $mountPoint -ErrorAction Stop
    $result.bitlocker_state_known = $true
    $result.data_volume = ($bitlocker.VolumeType.ToString() -eq "Data")
    $result.bitlocker_fully_encrypted = (
        $bitlocker.VolumeStatus.ToString() -eq "FullyEncrypted"
    )
    $result.bitlocker_protection_on = (
        $bitlocker.ProtectionStatus.ToString() -eq "On"
    )
    if (-not $result.data_volume) {
        throw "TARGET_NOT_DATA_VOLUME"
    }
    if (-not $result.bitlocker_fully_encrypted) {
        throw "TARGET_NOT_FULLY_ENCRYPTED"
    }
    if (-not $result.bitlocker_protection_on) {
        throw "TARGET_BITLOCKER_PROTECTION_OFF"
    }

    $runtimeSid = Resolve-LocalAccountSid -AccountName "omni-cio-runtime"
    $runnerSid = Resolve-LocalAccountSid -AccountName "omni-ci-runner"
    $result.runtime_identity_resolved = $true
    $result.runner_identity_resolved = $true

    if (-not $Apply) {
        $result.status = "READY"
        $result.reason_code = "TARGET_PREVIEW_PASS"
        Write-OutputResult -Result $result
        exit 0
    }

    if (-not (Test-IsAdministrator)) {
        throw "OWNER_ADMIN_REQUIRED"
    }
    if (-not $RecoveryKeyCustodyConfirmed) {
        throw "RECOVERY_KEY_CUSTODY_CONFIRMATION_REQUIRED"
    }

    $volumeRoot = "$mountPoint\"
    $backupRoot = Join-Path $volumeRoot $BackupRootName
    $targetMarker = Join-Path $backupRoot $TargetMarkerName
    $sentinelPath = Join-Path $backupRoot $SentinelName

    if (Test-Path -LiteralPath $backupRoot) {
        if (-not (Test-Path -LiteralPath $targetMarker -PathType Leaf)) {
            throw "EXISTING_UNOWNED_BACKUP_ROOT_REFUSED"
        }
        try {
            $existingMarker = Get-Content -LiteralPath $targetMarker -Raw |
                ConvertFrom-Json
        }
        catch {
            throw "TARGET_MARKER_INVALID"
        }
        if (
            $existingMarker.schema_version -ne "1" -or
            $existingMarker.work_package -ne "WP10" -or
            $existingMarker.target_class -ne $result.target_class
        ) {
            throw "TARGET_MARKER_INVALID"
        }
    }
    else {
        New-Item -ItemType Directory -Path $backupRoot | Out-Null
    }

    Invoke-IcaclsChecked -Arguments @($backupRoot, "/inheritance:r")
    Invoke-IcaclsChecked -Arguments @(
        $backupRoot,
        "/grant:r",
        "*S-1-5-18:(OI)(CI)F",
        "*S-1-5-32-544:(OI)(CI)F",
        "*$runtimeSid:(OI)(CI)M"
    )
    Invoke-IcaclsChecked -Arguments @($backupRoot, "/remove:g", "*$runnerSid")
    Invoke-IcaclsChecked -Arguments @($backupRoot, "/remove:d", "*$runnerSid")

    $marker = [ordered]@{
        schema_version = "1"
        work_package = "WP10"
        target_class = $result.target_class
        target_mount_point = $mountPoint
        backup_root_name = $BackupRootName
        created_at_utc = [DateTime]::UtcNow.ToString("o")
        bitlocker_fully_encrypted = $true
        bitlocker_protection_on = $true
        recovery_key_custody_confirmed = $true
        runtime_identity_sid_bound = $true
        runner_payload_access_granted = $false
    }
    $marker | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $targetMarker `
        -Encoding UTF8

    if (-not (Test-Path -LiteralPath $sentinelPath -PathType Leaf)) {
        $bytes = New-Object byte[] 64
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        try {
            [IO.File]::WriteAllBytes($sentinelPath, $bytes)
        }
        finally {
            [Array]::Clear($bytes, 0, $bytes.Length)
        }
    }

    Invoke-IcaclsChecked -Arguments @($targetMarker, "/inheritance:e")
    Invoke-IcaclsChecked -Arguments @($sentinelPath, "/inheritance:e")

    if (-not (Test-Path -LiteralPath $EvidenceRoot)) {
        New-Item -ItemType Directory -Path $EvidenceRoot -Force | Out-Null
    }
    $evidence = [ordered]@{
        schema_version = "1"
        work_package = "WP10"
        evidence_class = "OFFDEVICE_OWNER_APPLY"
        target_class = $result.target_class
        target_mount_point = $mountPoint
        backup_root_name = $BackupRootName
        marker_name = $TargetMarkerName
        sentinel_name = $SentinelName
        applied_at_utc = [DateTime]::UtcNow.ToString("o")
        non_system_volume = $true
        data_volume = $true
        bitlocker_fully_encrypted = $true
        bitlocker_protection_on = $true
        recovery_key_custody_confirmed = $true
        runtime_identity_resolved = $true
        runner_identity_resolved = $true
        runner_payload_access_granted = $false
        private_payload_used = $false
        secret_value_used = $false
        recovery_key_value_used = $false
    }
    $evidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $EvidencePath `
        -Encoding UTF8

    $result.target_marker_present = $true
    $result.sentinel_present = $true
    $result.applied = $true
    $result.status = "READY"
    $result.reason_code = "TARGET_APPLY_PASS"
}
catch {
    if ($_.Exception.Message -match "^[A-Z0-9_:-]+$") {
        $result.reason_code = $_.Exception.Message
    }
    else {
        $result.reason_code = "TARGET_VERIFICATION_ERROR"
    }
    $result.status = "BLOCKED"
}

Write-OutputResult -Result $result
if ($result.status -ne "READY") {
    exit 1
}
exit 0
