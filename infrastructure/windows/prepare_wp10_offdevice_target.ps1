[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Za-z]:$')][string]$TargetMountPoint,
    [Parameter(Mandatory = $true)][switch]$RecoveryKeyCustodyConfirmed,
    [switch]$Apply,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$StateRoot = "C:\ProgramData\OmniCIO\wp10"
$LocalDescriptorPath = Join-Path $StateRoot "offdevice-owner-prepare.local.json"
$BackupRootName = "OmniCIO-WP10-Backups"
$MarkerName = ".omni-cio-wp10-target.json"
$SentinelName = ".omni-cio-wp10-access-sentinel"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-SanitizedResult {
    param([hashtable]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }
    Write-Output "WP10 off-device preparation: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Non-system volume: $($Result.non_system_volume)"
    Write-Output "Fully encrypted: $($Result.bitlocker_fully_encrypted)"
    Write-Output "BitLocker protection on: $($Result.bitlocker_protection_on)"
    Write-Output "Recovery-key custody confirmed: $($Result.recovery_key_custody_confirmed)"
    Write-Output "Destructive disk operation performed: NO"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    evidence_class = "OWNER_OFFDEVICE_PREPARE"
    status = "FAIL"
    reason_code = "PREPARATION_NOT_COMPLETED"
    non_system_volume = $false
    data_volume = $false
    bitlocker_fully_encrypted = $false
    bitlocker_protection_on = $false
    recovery_key_custody_confirmed = [bool]$RecoveryKeyCustodyConfirmed
    target_marker_present = $false
    backup_root_prepared = $false
    destructive_disk_operation_performed = $false
    raw_disk_identity_collected = $false
    recovery_key_value_collected = $false
    secret_value_collected = $false
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

    $mountPoint = $TargetMountPoint.ToUpperInvariant()
    $systemVolume = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\").ToUpperInvariant()
    if ($mountPoint -eq $systemVolume) {
        throw "SYSTEM_VOLUME_FORBIDDEN"
    }
    $result.non_system_volume = $true

    $volume = Get-BitLockerVolume -MountPoint $mountPoint -ErrorAction Stop
    if ([string]$volume.VolumeType -ne "Data") {
        throw "TARGET_NOT_DATA_VOLUME"
    }
    $result.data_volume = $true
    if ([string]$volume.VolumeStatus -ne "FullyEncrypted") {
        throw "TARGET_NOT_FULLY_ENCRYPTED"
    }
    $result.bitlocker_fully_encrypted = $true
    if ([string]$volume.ProtectionStatus -ne "On") {
        throw "TARGET_BITLOCKER_PROTECTION_OFF"
    }
    $result.bitlocker_protection_on = $true

    $backupRoot = Join-Path "$mountPoint\" $BackupRootName
    $markerPath = Join-Path $backupRoot $MarkerName
    $sentinelPath = Join-Path $backupRoot $SentinelName

    if ($Apply) {
        New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null

        $marker = [ordered]@{
            schema_version = "1"
            work_package = "WP10"
            marker_class = "OWNER_CONTROLLED_OFFDEVICE_TARGET"
            backup_root_name = $BackupRootName
            destructive_provisioning_forbidden = $true
        }
        $marker | ConvertTo-Json -Compress | Set-Content -LiteralPath $markerPath -Encoding UTF8
        "WP10_ACCESS_SENTINEL_NO_PRIVATE_DATA" | Set-Content -LiteralPath $sentinelPath -Encoding ASCII

        # The target volume must already exist and already be encrypted. This
        # script changes only the dedicated Omni-CIO directory ACL; it never
        # formats, partitions, shrinks or erases a disk/volume. Well-known SIDs
        # avoid depending on the Windows display language.
        & icacls.exe $backupRoot /inheritance:r *> $null
        if ($LASTEXITCODE -ne 0) { throw "BACKUP_ROOT_ACL_INHERITANCE_FAILED" }
        & icacls.exe $backupRoot /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" *> $null
        if ($LASTEXITCODE -ne 0) { throw "BACKUP_ROOT_ACL_GRANT_FAILED" }

        $localDescriptor = [ordered]@{
            schema_version = "1"
            work_package = "WP10"
            local_only = $true
            target_mount_point = $mountPoint
            backup_root_name = $BackupRootName
            marker_name = $MarkerName
            sentinel_name = $SentinelName
            non_system_volume = $true
            data_volume = $true
            bitlocker_fully_encrypted = $true
            bitlocker_protection_on = $true
            recovery_key_custody_confirmed = $true
            destructive_disk_operation_performed = $false
            captured_at_utc = [DateTime]::UtcNow.ToString("o")
        }
        $localDescriptor | ConvertTo-Json -Compress -Depth 4 |
            Set-Content -LiteralPath $LocalDescriptorPath -Encoding UTF8
    }

    $result.target_marker_present = Test-Path -LiteralPath $markerPath -PathType Leaf
    $result.backup_root_prepared = Test-Path -LiteralPath $backupRoot -PathType Container
    if ($Apply -and (-not $result.target_marker_present -or -not $result.backup_root_prepared)) {
        throw "TARGET_PREPARATION_INCOMPLETE"
    }

    $result.status = if ($Apply) { "PASS" } else { "READY_TO_APPLY" }
    $result.reason_code = if ($Apply) { "OWNER_TARGET_PREPARED" } else { "OWNER_TARGET_VALIDATED_NONDESTRUCTIVE" }
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -notmatch '^[A-Z0-9_:\-]+$') {
        $message = "OWNER_TARGET_PREPARATION_ERROR"
    }
    $result.status = "FAIL"
    $result.reason_code = $message
}

Write-SanitizedResult -Result $result
if ($result.status -eq "FAIL") {
    exit 1
}
