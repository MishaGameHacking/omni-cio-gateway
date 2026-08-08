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
        service_query_succeeded = $false
        service_identity_matches = $false
        service_root_bound = $false
        service_running = $false
        service_automatic = $false
        service_non_admin = $false
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
$runCommand = Join-Path $RunnerRoot "run.cmd"
$runCommandPresent = Test-Path -LiteralPath $runCommand -PathType Leaf

# WP6 deliberately hardens .runner, .credentials, .credentials_rsaparams and
# .service. WP7 therefore does not read any of those files. GitHub documents
# Get-Service "actions.runner.*" as the Windows service-health surface. We bind
# that service to the reviewed runner name, runner root and current CI identity.
$runnerPrivateConfigRead = $false
$expectedServiceSuffix = ".$ExpectedRunnerName.service"
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$'
$services = @()
$serviceQuerySucceeded = $false
try {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $_.Name -match $serviceNamePattern -and
                $_.Name.EndsWith(
                    $expectedServiceSuffix,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            }
    )
    $serviceQuerySucceeded = $true
}
catch {
    $services = @()
    $serviceQuerySucceeded = $false
}

$service = if ($services.Count -eq 1) { $services[0] } else { $null }
$serviceIdentityMatches = $false
$serviceRootBound = $false
$processIdentityMatch = $false
$serviceRunning = $false
$serviceAutomatic = $false
$serviceNonAdmin = $false

if ($null -ne $service) {
    $serviceIdentityMatches = (
        $service.Name -match $serviceNamePattern -and
        $service.Name.EndsWith(
            $expectedServiceSuffix,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    )
    $serviceRunning = $service.State -eq "Running"
    $serviceAutomatic = $service.StartMode -eq "Auto"

    $pathName = [string]$service.PathName
    if (-not [string]::IsNullOrWhiteSpace($pathName)) {
        $serviceRootBound = $pathName.IndexOf(
            $RunnerRoot,
            [System.StringComparison]::OrdinalIgnoreCase
        ) -ge 0
    }

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
    $serviceQuerySucceeded -and
    $services.Count -eq 1 -and
    $serviceIdentityMatches -and
    $serviceRootBound -and
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
elseif (-not $serviceQuerySucceeded) {
    $errorCode = "RUNNER_SERVICE_QUERY_FAILED"
}
elseif ($services.Count -ne 1) {
    $errorCode = "RUNNER_SERVICE_MISSING_OR_AMBIGUOUS"
}
elseif (-not $serviceIdentityMatches) {
    $errorCode = "RUNNER_SERVICE_IDENTITY_MISMATCH"
}
elseif (-not $serviceRootBound) {
    $errorCode = "RUNNER_SERVICE_ROOT_MISMATCH"
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
    service_query_succeeded = $serviceQuerySucceeded
    service_identity_matches = $serviceIdentityMatches
    service_root_bound = $serviceRootBound
    service_running = $serviceRunning
    service_automatic = $serviceAutomatic
    service_non_admin = $serviceNonAdmin
    process_identity_match = $processIdentityMatch
    runner_private_config_read = $runnerPrivateConfigRead
    privacy_safe = $true
})

if ($healthy) { exit 0 }
exit 2
