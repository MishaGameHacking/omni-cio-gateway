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
        configuration_present = $false
        service_marker_valid = $false
        service_running = $false
        service_automatic = $false
        service_non_admin = $false
        identity_match = $false
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
$runnerConfig = Join-Path $RunnerRoot ".runner"
$serviceMarker = Join-Path $RunnerRoot ".service"
$runCommand = Join-Path $RunnerRoot "run.cmd"
$runnerConfigPresent = Test-Path -LiteralPath $runnerConfig -PathType Leaf
$serviceMarkerPresent = Test-Path -LiteralPath $serviceMarker -PathType Leaf
$runCommandPresent = Test-Path -LiteralPath $runCommand -PathType Leaf

$runnerConfigBounded = $false
if ($runnerConfigPresent) {
    try {
        $runnerConfigLength = (Get-Item -LiteralPath $runnerConfig -ErrorAction Stop).Length
        $runnerConfigBounded = $runnerConfigLength -gt 0 -and $runnerConfigLength -le 65536
    }
    catch {
        $runnerConfigBounded = $false
    }
}

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

$configurationPresent = (
    $runnerConfigPresent -and
    $runnerConfigBounded -and
    $serviceMarkerPresent -and
    $serviceMarkerValid -and
    $runCommandPresent
)

$services = @()
if ($serviceMarkerValid) {
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
$service = if ($services.Count -eq 1) { $services[0] } else { $null }
$identityMatch = $false
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
    if ($normalized -notin @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        if ($normalized -in @(
            "NT AUTHORITY\NETWORKSERVICE",
            "NT AUTHORITY\LOCALSERVICE"
        ) -or $normalized.StartsWith("NT SERVICE\")) {
            $serviceNonAdmin = $true
        }
        else {
            $runnerSid = Get-AccountSidValue -AccountName $startName
            if ($runnerSid) {
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
}

$healthy = (
    $runnerRootPresent -and
    $configurationPresent -and
    $serviceMarkerValid -and
    $services.Count -eq 1 -and
    $identityMatch -and
    $serviceRunning -and
    $serviceAutomatic -and
    $serviceNonAdmin
)

$errorCode = $null
if (-not $runnerRootPresent) {
    $errorCode = "RUNNER_ROOT_MISSING"
}
elseif (-not $runnerConfigPresent -or -not $runnerConfigBounded) {
    $errorCode = "RUNNER_CONFIGURATION_MISSING_OR_UNBOUNDED"
}
elseif (-not $serviceMarkerPresent) {
    $errorCode = "RUNNER_SERVICE_MARKER_MISSING"
}
elseif (-not $serviceMarkerValid) {
    $errorCode = "RUNNER_SERVICE_MARKER_INVALID"
}
elseif (-not $runCommandPresent) {
    $errorCode = "RUNNER_COMMAND_MISSING"
}
elseif ($services.Count -ne 1) {
    $errorCode = "RUNNER_SERVICE_MISSING_OR_AMBIGUOUS"
}
elseif (-not $identityMatch) {
    $errorCode = "RUNNER_SERVICE_IDENTITY_MISMATCH"
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
    configuration_present = $configurationPresent
    service_marker_valid = $serviceMarkerValid
    service_running = $serviceRunning
    service_automatic = $serviceAutomatic
    service_non_admin = $serviceNonAdmin
    identity_match = $identityMatch
    privacy_safe = $true
})

if ($healthy) { exit 0 }
exit 2
