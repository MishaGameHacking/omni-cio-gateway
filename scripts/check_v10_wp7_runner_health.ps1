[CmdletBinding()]
param(
    [string]$RunnerRoot = "C:\actions-runner",
    [string]$ExpectedRunnerName = "omni-cio-ci",
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Write-Result {
    param([pscustomobject]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 4 -Compress
    }
    else {
        $Result | Format-List
    }
}

function Get-AccountSidValue {
    param([string]$AccountName)

    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "S-1-5-18"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") {
        return "S-1-5-20"
    }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") {
        return "S-1-5-19"
    }
    try {
        $account = [System.Security.Principal.NTAccount]::new($AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
    catch {
        return $null
    }
}

function Write-Failure {
    param([string]$Code)

    Write-Result -Result ([pscustomobject]@{
        healthy = $false
        error_code = $Code
        root_present = $false
        run_command_present = $false
        service_marker_present = $false
        service_marker_valid = $false
        service_running = $false
        service_automatic = $false
        service_non_admin = $false
        identity_match = $false
        process_identity_match = $false
        runner_private_config_read = $false
        privacy_safe = $true
    })
}

if ($ExpectedRunnerName -notmatch '^[A-Za-z0-9._-]{1,64}$') {
    Write-Failure -Code "EXPECTED_RUNNER_NAME_INVALID"
    exit 2
}

if ($env:OS -ne "Windows_NT") {
    Write-Failure -Code "RUNNER_SERVICE_WINDOWS_REQUIRED"
    exit 2
}

$runnerRootPresent = Test-Path -LiteralPath $RunnerRoot -PathType Container
$serviceMarker = Join-Path $RunnerRoot ".service"
$runCommand = Join-Path $RunnerRoot "run.cmd"
$serviceMarkerPresent = Test-Path -LiteralPath $serviceMarker -PathType Leaf
$runCommandPresent = Test-Path -LiteralPath $runCommand -PathType Leaf

# WP6 deliberately classifies .runner/.credentials as hardened sensitive runner
# configuration. WP7 therefore treats the Windows service boundary as its
# authoritative health source and never reads .runner or credential material.
$runnerPrivateConfigRead = $false
$declaredServiceName = $null
$serviceMarkerValid = $false
if ($serviceMarkerPresent) {
    try {
        $markerLength = (Get-Item -LiteralPath $serviceMarker -ErrorAction Stop).Length
        if ($markerLength -gt 0 -and $markerLength -le 1024) {
            $candidate = (Get-Content -LiteralPath $serviceMarker -Raw -ErrorAction Stop).Trim()
            $expectedSuffix = ".$ExpectedRunnerName.service"
            if (
                $candidate -match '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$' -and
                $candidate.EndsWith(
                    $expectedSuffix,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            ) {
                $declaredServiceName = $candidate
                $serviceMarkerValid = $true
            }
        }
    }
    catch {
        $declaredServiceName = $null
        $serviceMarkerValid = $false
    }
}

$services = @()
if ($serviceMarkerValid) {
    try {
        $services = @(
            Get-CimInstance Win32_Service -ErrorAction Stop |
                Where-Object {
                    [string]::Equals(
                        $_.Name,
                        $declaredServiceName,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                }
        )
    }
    catch {
        $services = @()
    }
}
$service = if ($services.Count -eq 1) { $services[0] } else { $null }
$identityMatch = $false
$processIdentityMatch = $false
$serviceRunning = $false
$serviceAutomatic = $false
$serviceNonAdmin = $false

if ($null -ne $service) {
    $identityMatch = [string]::Equals(
        $service.Name,
        $declaredServiceName,
        [System.StringComparison]::OrdinalIgnoreCase
    )
    $serviceRunning = $service.State -eq "Running"
    $serviceAutomatic = $service.StartMode -eq "Auto"

    $startName = [string]$service.StartName
    $normalized = $startName.Trim().ToUpperInvariant()
    $runnerSid = Get-AccountSidValue -AccountName $startName
    if ($runnerSid) {
        try {
            $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            $processIdentityMatch = [string]::Equals(
                $currentSid,
                $runnerSid,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
        catch {
            $processIdentityMatch = $false
        }
    }

    if ($normalized -notin @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        if ($normalized -in @(
            "NT AUTHORITY\NETWORKSERVICE",
            "NT AUTHORITY\LOCALSERVICE"
        ) -or $normalized.StartsWith("NT SERVICE\")) {
            $serviceNonAdmin = $true
        }
        elseif ($runnerSid) {
            try {
                $adminSid = [System.Security.Principal.SecurityIdentifier]::new(
                    "S-1-5-32-544"
                )
                $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
                $members = @(
                    Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop
                )
                $serviceNonAdmin = -not [bool](
                    $members | Where-Object { $_.SID.Value -eq $runnerSid }
                )
            }
            catch {
                $serviceNonAdmin = $false
            }
        }
    }
}

$healthy = (
    $runnerRootPresent -and
    $runCommandPresent -and
    $serviceMarkerPresent -and
    $serviceMarkerValid -and
    $services.Count -eq 1 -and
    $identityMatch -and
    $processIdentityMatch -and
    $serviceRunning -and
    $serviceAutomatic -and
    $serviceNonAdmin -and
    -not $runnerPrivateConfigRead
)

$errorCode = $null
if (-not $runnerRootPresent) {
    $errorCode = "RUNNER_ROOT_MISSING"
}
elseif (-not $runCommandPresent) {
    $errorCode = "RUNNER_COMMAND_MISSING"
}
elseif (-not $serviceMarkerPresent) {
    $errorCode = "RUNNER_SERVICE_MARKER_MISSING"
}
elseif (-not $serviceMarkerValid) {
    $errorCode = "RUNNER_SERVICE_MARKER_INVALID"
}
elseif ($services.Count -ne 1) {
    $errorCode = "RUNNER_SERVICE_MISSING_OR_AMBIGUOUS"
}
elseif (-not $identityMatch) {
    $errorCode = "RUNNER_SERVICE_IDENTITY_MISMATCH"
}
elseif (-not $processIdentityMatch) {
    $errorCode = "RUNNER_PROCESS_IDENTITY_MISMATCH"
}
elseif (-not $serviceNonAdmin) {
    $errorCode = "RUNNER_SERVICE_PRIVILEGE_INVALID"
}
elseif (-not $serviceAutomatic) {
    $errorCode = "RUNNER_SERVICE_NOT_AUTOMATIC"
}
elseif (-not $serviceRunning) {
    $errorCode = "RUNNER_SERVICE_NOT_RUNNING"
}

Write-Result -Result ([pscustomobject]@{
    healthy = $healthy
    error_code = $errorCode
    root_present = $runnerRootPresent
    run_command_present = $runCommandPresent
    service_marker_present = $serviceMarkerPresent
    service_marker_valid = $serviceMarkerValid
    service_running = $serviceRunning
    service_automatic = $serviceAutomatic
    service_non_admin = $serviceNonAdmin
    identity_match = $identityMatch
    process_identity_match = $processIdentityMatch
    runner_private_config_read = $runnerPrivateConfigRead
    privacy_safe = $true
})

if ($healthy) { exit 0 }
exit 2
