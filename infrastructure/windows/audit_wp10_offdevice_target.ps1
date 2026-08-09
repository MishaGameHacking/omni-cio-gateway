[CmdletBinding()]
param(
    [string]$LocalDescriptorPath = "C:\ProgramData\OmniCIO\wp10\offdevice-owner-prepare.local.json",
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Result {
    param([hashtable]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Compress -Depth 5
        return
    }
    Write-Output "WP10 off-device non-admin audit: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Runner read denied: $($Result.runner_payload_read_denied)"
    Write-Output "Runner write denied: $($Result.runner_payload_write_denied)"
    Write-Output "Raw disk identity emitted: NO"
}

$result = @{
    schema_version = "1"
    work_package = "WP10"
    evidence_class = "NONADMIN_OFFDEVICE_ACCESS_AUDIT"
    status = "FAIL"
    reason_code = "AUDIT_NOT_COMPLETED"
    owner_descriptor_valid = $false
    runner_payload_read_denied = $false
    runner_payload_write_denied = $false
    raw_disk_identity_emitted = $false
    secret_value_emitted = $false
}

$probePath = $null
try {
    if ($env:OS -ne "Windows_NT") {
        throw "WINDOWS_REQUIRED"
    }
    if (Test-Administrator) {
        throw "NONADMIN_AUDIT_REQUIRED"
    }
    if (-not (Test-Path -LiteralPath $LocalDescriptorPath -PathType Leaf)) {
        throw "OWNER_DESCRIPTOR_MISSING"
    }

    try {
        $descriptor = Get-Content -LiteralPath $LocalDescriptorPath -Raw | ConvertFrom-Json
    }
    catch {
        throw "OWNER_DESCRIPTOR_INVALID"
    }
    if (
        [string]$descriptor.schema_version -ne "1" -or
        [string]$descriptor.work_package -ne "WP10" -or
        -not [bool]$descriptor.local_only -or
        -not [bool]$descriptor.non_system_volume -or
        -not [bool]$descriptor.data_volume -or
        -not [bool]$descriptor.bitlocker_fully_encrypted -or
        -not [bool]$descriptor.bitlocker_protection_on -or
        -not [bool]$descriptor.recovery_key_custody_confirmed -or
        [bool]$descriptor.destructive_disk_operation_performed
    ) {
        throw "OWNER_DESCRIPTOR_INVALID"
    }

    $mountPoint = [string]$descriptor.target_mount_point
    if ($mountPoint -notmatch '^[A-Z]:$') {
        throw "OWNER_DESCRIPTOR_TARGET_INVALID"
    }
    $systemVolume = [System.IO.Path]::GetPathRoot($env:SystemRoot).TrimEnd("\").ToUpperInvariant()
    if ($mountPoint -eq $systemVolume) {
        throw "SYSTEM_VOLUME_FORBIDDEN"
    }
    $backupRoot = Join-Path "$mountPoint\" ([string]$descriptor.backup_root_name)
    $sentinelPath = Join-Path $backupRoot ([string]$descriptor.sentinel_name)
    $result.owner_descriptor_valid = $true

    try {
        $null = Get-Content -LiteralPath $sentinelPath -Raw -ErrorAction Stop
        $result.runner_payload_read_denied = $false
    }
    catch [System.UnauthorizedAccessException] {
        $result.runner_payload_read_denied = $true
    }
    catch [System.Security.SecurityException] {
        $result.runner_payload_read_denied = $true
    }
    catch {
        # Missing/unmounted targets are not equivalent to an ACL denial.
        throw "RUNNER_READ_DENIAL_NOT_PROVEN"
    }
    if (-not $result.runner_payload_read_denied) {
        throw "RUNNER_READ_ACCESS_NOT_DENIED"
    }

    $probePath = Join-Path $backupRoot (".wp10-write-probe-" + [Guid]::NewGuid().ToString("N"))
    try {
        "probe" | Set-Content -LiteralPath $probePath -Encoding ASCII -ErrorAction Stop
        $result.runner_payload_write_denied = $false
    }
    catch [System.UnauthorizedAccessException] {
        $result.runner_payload_write_denied = $true
    }
    catch [System.Security.SecurityException] {
        $result.runner_payload_write_denied = $true
    }
    catch {
        throw "RUNNER_WRITE_DENIAL_NOT_PROVEN"
    }
    if (-not $result.runner_payload_write_denied) {
        throw "RUNNER_WRITE_ACCESS_NOT_DENIED"
    }

    $result.status = "PASS"
    $result.reason_code = "RUNNER_PAYLOAD_ACCESS_DENIED"
}
catch {
    $message = [string]$_.Exception.Message
    if ($message -notmatch '^[A-Z0-9_:\-]+$') {
        $message = "OFFDEVICE_ACCESS_AUDIT_ERROR"
    }
    $result.status = "FAIL"
    $result.reason_code = $message
}
finally {
    if ($null -ne $probePath -and (Test-Path -LiteralPath $probePath -PathType Leaf)) {
        Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
    }
}

Write-Result -Result $result
if ($result.status -ne "PASS") {
    exit 1
}
