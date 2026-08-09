[CmdletBinding()]
param(
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$EvidencePath = "C:\ProgramData\OmniCIO\wp10\offdevice-target.json"
$RehearsalEvidencePath = "C:\ProgramData\OmniCIO\wp10\offdevice-rehearsal.json"
$SealedWriter = "NOT_READY_UNTIL_PRODUCT_DB_AND_BACKUP_JOB_BINDING"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Write-Result {
    param([Parameter(Mandatory = $true)][hashtable]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }

    Write-Output "WP10 off-device audit status: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "BitLocker fully encrypted: $($Result.bitlocker_fully_encrypted)"
    Write-Output "BitLocker protection on: $($Result.bitlocker_protection_on)"
    Write-Output "OWNER restore rehearsal: $($Result.owner_offdevice_rehearsal_pass)"
    Write-Output "Runtime payload access granted: NO"
    Write-Output "Runner read denied: $($Result.runner_read_denied)"
    Write-Output "Runner write denied: $($Result.runner_write_denied)"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    mode = "NONADMIN_OFFDEVICE_AUDIT"
    status = "FAIL"
    reason_code = "OFFDEVICE_AUDIT_NOT_COMPLETED"
    owner_evidence_present = $false
    owner_rehearsal_evidence_present = $false
    owner_offdevice_rehearsal_pass = $false
    target_present = $false
    non_system_volume = $false
    data_volume = $false
    bitlocker_state_known = $false
    bitlocker_fully_encrypted = $false
    bitlocker_protection_on = $false
    recovery_key_custody_confirmed = $false
    target_marker_expected = $false
    sentinel_expected = $false
    production_backup_writer_identity = $SealedWriter
    runtime_payload_access_granted = $false
    runner_read_denied = $false
    runner_write_denied = $false
    runner_payload_access_granted = $false
    private_payload_collected = $false
    secret_value_collected = $false
    recovery_key_value_collected = $false
}

try {
    # This audit intentionally runs with the GitHub runner's non-admin token.
    # Privileged target preparation/BitLocker validation belongs to the OWNER
    # gate; this side independently proves that the prepared volume is mounted
    # and that the runner still cannot read or write the protected payload root.
    if (Test-IsAdministrator) {
        throw "RUNNER_MUST_BE_NON_ADMIN"
    }

    if (-not (Test-Path -LiteralPath $EvidencePath -PathType Leaf)) {
        throw "OWNER_OFFDEVICE_EVIDENCE_MISSING"
    }
    $result.owner_evidence_present = $true

    try {
        $evidence = Get-Content -LiteralPath $EvidencePath -Raw | ConvertFrom-Json
    }
    catch {
        throw "OWNER_OFFDEVICE_EVIDENCE_INVALID"
    }

    if (
        $evidence.schema_version -ne "1" -or
        $evidence.work_package -ne "WP10" -or
        $evidence.evidence_class -ne "OFFDEVICE_OWNER_APPLY" -or
        $evidence.target_class -ne "BITLOCKER_OWNER_CONTROLLED_NON_SYSTEM_VOLUME"
    ) {
        throw "OWNER_OFFDEVICE_EVIDENCE_INVALID"
    }

    foreach ($field in @(
        "non_system_volume",
        "data_volume",
        "bitlocker_fully_encrypted",
        "bitlocker_protection_on",
        "recovery_key_custody_confirmed"
    )) {
        if (-not [bool]$evidence.$field) {
            throw "OWNER_OFFDEVICE_EVIDENCE_INCOMPLETE"
        }
    }
    if ([string]$evidence.production_backup_writer_identity -ne $SealedWriter) {
        throw "OWNER_EVIDENCE_PRODUCTION_WRITER_SCOPE_LEAK"
    }
    if ([bool]$evidence.runtime_payload_access_granted) {
        throw "OWNER_EVIDENCE_RUNTIME_ACCESS_ENABLED"
    }
    if ([bool]$evidence.runner_payload_access_granted) {
        throw "OWNER_EVIDENCE_RUNNER_ACCESS_ENABLED"
    }
    foreach ($field in @(
        "private_payload_used",
        "secret_value_used",
        "recovery_key_value_used"
    )) {
        if ([bool]$evidence.$field) {
            throw "OWNER_OFFDEVICE_PRIVACY_BOUNDARY_VIOLATION"
        }
    }

    if (-not (Test-Path -LiteralPath $RehearsalEvidencePath -PathType Leaf)) {
        throw "OWNER_OFFDEVICE_REHEARSAL_EVIDENCE_MISSING"
    }
    $result.owner_rehearsal_evidence_present = $true
    try {
        $rehearsal = Get-Content -LiteralPath $RehearsalEvidencePath -Raw |
            ConvertFrom-Json
    }
    catch {
        throw "OWNER_OFFDEVICE_REHEARSAL_EVIDENCE_INVALID"
    }

    if (
        $rehearsal.schema_version -ne "1" -or
        $rehearsal.work_package -ne "WP10" -or
        $rehearsal.evidence_class -ne "OWNER_OFFDEVICE_RECOVERY_REHEARSAL" -or
        $rehearsal.target_class -ne $evidence.target_class -or
        $rehearsal.target_mount_point -ne $evidence.target_mount_point
    ) {
        throw "OWNER_OFFDEVICE_REHEARSAL_EVIDENCE_INVALID"
    }
    foreach ($field in @(
        "bundle_integrity_pass",
        "corruption_rejected",
        "offdevice_copy_pass",
        "restore_probe_pass",
        "offdevice_cleanup_pass",
        "temporary_state_cleaned"
    )) {
        if (-not [bool]$rehearsal.$field) {
            throw "OWNER_OFFDEVICE_REHEARSAL_INCOMPLETE"
        }
    }
    foreach ($field in @(
        "real_secret_values_used",
        "private_portfolio_data_used",
        "account_identifiers_used",
        "production_database_accessed",
        "recovery_key_value_used"
    )) {
        if ([bool]$rehearsal.$field) {
            throw "OWNER_OFFDEVICE_REHEARSAL_PRIVACY_BOUNDARY_VIOLATION"
        }
    }
    try {
        $appliedAt = [DateTimeOffset]::Parse([string]$evidence.applied_at_utc)
        $rehearsedAt = [DateTimeOffset]::Parse([string]$rehearsal.rehearsed_at_utc)
    }
    catch {
        throw "OWNER_OFFDEVICE_EVIDENCE_TIMESTAMP_INVALID"
    }
    if ($rehearsedAt -lt $appliedAt) {
        throw "OWNER_REHEARSAL_PREDATES_TARGET_APPLY"
    }
    $result.owner_offdevice_rehearsal_pass = $true

    $mountPoint = [string]$evidence.target_mount_point
    if ($mountPoint -notmatch "^[A-Z]:$") {
        throw "OWNER_TARGET_MOUNT_POINT_INVALID"
    }
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
    $result.target_present = $true

    # Do not call Get-BitLockerVolume from the deliberately non-admin runner.
    # The OWNER apply gate already live-validates VolumeType=Data,
    # VolumeStatus=FullyEncrypted and ProtectionStatus=On before writing this
    # sanitized evidence. Requiring the same privileged cmdlet here would make
    # the least-privilege audit self-contradictory. Keep the claims fail-closed
    # by accepting them only from the strictly validated OWNER evidence above.
    $result.bitlocker_state_known = $true
    $result.data_volume = [bool]$evidence.data_volume
    $result.bitlocker_fully_encrypted = [bool]$evidence.bitlocker_fully_encrypted
    $result.bitlocker_protection_on = [bool]$evidence.bitlocker_protection_on
    $result.recovery_key_custody_confirmed = [bool](
        $evidence.recovery_key_custody_confirmed
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

    $backupRoot = Join-Path "$mountPoint\" ([string]$evidence.backup_root_name)
    $markerPath = Join-Path $backupRoot ([string]$evidence.marker_name)
    $sentinelPath = Join-Path $backupRoot ([string]$evidence.sentinel_name)
    $result.target_marker_expected = $true
    $result.sentinel_expected = $true

    try {
        $stream = [IO.File]::Open(
            $sentinelPath,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            [IO.FileShare]::Read
        )
        $stream.Dispose()
        throw "RUNNER_SENTINEL_READ_SUCCEEDED"
    }
    catch [UnauthorizedAccessException] {
        $result.runner_read_denied = $true
    }
    catch [Security.SecurityException] {
        $result.runner_read_denied = $true
    }

    $probePath = Join-Path $backupRoot ".wp10-runner-write-probe.tmp"
    try {
        $stream = [IO.File]::Open(
            $probePath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )
        $stream.Dispose()
        Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
        throw "RUNNER_WRITE_SUCCEEDED"
    }
    catch [UnauthorizedAccessException] {
        $result.runner_write_denied = $true
    }
    catch [Security.SecurityException] {
        $result.runner_write_denied = $true
    }

    if (-not $result.runner_read_denied -or -not $result.runner_write_denied) {
        throw "RUNNER_OFFDEVICE_ACCESS_NOT_DENIED"
    }

    # The marker itself is intentionally inside the protected payload root.
    # Do not read it in CI; OWNER evidence carries only its non-secret schema facts.
    $null = $markerPath
    $result.status = "PASS"
    $result.reason_code = "OFFDEVICE_AUDIT_PASS"
}
catch {
    if ($_.Exception.Message -match "^[A-Z0-9_:-]+$") {
        $result.reason_code = $_.Exception.Message
    }
    else {
        $result.reason_code = "OFFDEVICE_AUDIT_ERROR"
    }
    $result.status = "FAIL"
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
exit 0
