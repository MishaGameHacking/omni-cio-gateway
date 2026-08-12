[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RunnerRoot = "C:\actions-runner",

    [Parameter()]
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$ExpectedRunnerName = "omni-cio-ci",

    [Parameter()]
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Result {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Result
    )

    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 4 -Compress
    }
    else {
        $Result | Format-List
    }
}

function Get-JsonPropertyOrdinalIgnoreCase {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string]$Name
    )

    $matches = @(
        $InputObject.PSObject.Properties |
            Where-Object {
                [string]::Equals(
                    $_.Name,
                    $Name,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            }
    )

    if ($matches.Count -ne 1) {
        return $null
    }
    return $matches[0]
}

if ($env:OS -ne "Windows_NT") {
    $result = [pscustomobject]@{
        healthy = $false
        error_code = "RUNNER_SERVICE_WINDOWS_REQUIRED"
        runner_root_exists = $false
        expected_runner_name = $ExpectedRunnerName
        runner_configuration_present = $false
        runner_configuration_valid = $false
        runner_configuration_error_detail = $null
        runner_configuration_identity_matches = $false
        runner_ephemeral = $null
        run_command_present = $false
        service_marker_present = $false
        service_marker_valid = $false
        service_marker_identity_matches = $false
        service_query_succeeded = $false
        service_identity_matches = $false
        service_state = $null
        service_start_mode = $null
    }
    Write-Result -Result $result
    exit 2
}

$runnerRootExists = Test-Path -LiteralPath $RunnerRoot -PathType Container
$serviceFilePath = Join-Path -Path $RunnerRoot -ChildPath ".service"
$runnerConfigPath = Join-Path -Path $RunnerRoot -ChildPath ".runner"
$runCommandPath = Join-Path -Path $RunnerRoot -ChildPath "run.cmd"
$expectedServiceSuffix = ".$ExpectedRunnerName.service"
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$'

$runnerConfigurationPresent = Test-Path -LiteralPath $runnerConfigPath -PathType Leaf
$runnerConfigurationValid = $false
$runnerConfigurationErrorDetail = $null
$runnerConfigurationIdentityMatches = $false
$runnerEphemeral = $null

if ($runnerConfigurationPresent) {
    try {
        $runnerConfigInfo = Get-Item -LiteralPath $runnerConfigPath -ErrorAction Stop
        if ($runnerConfigInfo.Length -le 0 -or $runnerConfigInfo.Length -gt 65536) {
            $runnerConfigurationErrorDetail = "SIZE_INVALID"
        }
        else {
            $runnerSettings = $null
            try {
                $runnerSettings = Get-Content -LiteralPath $runnerConfigPath -Raw -ErrorAction Stop |
                    ConvertFrom-Json -ErrorAction Stop
            }
            catch {
                $runnerConfigurationErrorDetail = "JSON_INVALID"
            }

            if ($null -ne $runnerSettings) {
                $agentNameProperty = Get-JsonPropertyOrdinalIgnoreCase `
                    -InputObject $runnerSettings `
                    -Name "agentName"
                $ephemeralProperty = Get-JsonPropertyOrdinalIgnoreCase `
                    -InputObject $runnerSettings `
                    -Name "ephemeral"

                $agentNameValid = (
                    $null -ne $agentNameProperty -and
                    $agentNameProperty.Value -is [string] -and
                    -not [string]::IsNullOrWhiteSpace($agentNameProperty.Value)
                )
                $ephemeralValid = (
                    $null -eq $ephemeralProperty -or
                    $ephemeralProperty.Value -is [bool]
                )

                if (-not $agentNameValid) {
                    $runnerConfigurationErrorDetail = "AGENT_NAME_INVALID"
                }
                elseif (-not $ephemeralValid) {
                    $runnerConfigurationErrorDetail = "EPHEMERAL_INVALID"
                }
                else {
                    $runnerConfigurationValid = $true
                    $runnerConfigurationErrorDetail = $null
                    $runnerConfigurationIdentityMatches = [string]::Equals(
                        [string]$agentNameProperty.Value,
                        $ExpectedRunnerName,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                    $runnerEphemeral = if ($null -eq $ephemeralProperty) {
                        $false
                    }
                    else {
                        [bool]$ephemeralProperty.Value
                    }
                }
            }
        }
    }
    catch {
        $runnerConfigurationValid = $false
        $runnerConfigurationErrorDetail = "READ_FAILED"
        $runnerConfigurationIdentityMatches = $false
        $runnerEphemeral = $null
    }
}

$runCommandPresent = Test-Path -LiteralPath $runCommandPath -PathType Leaf
$serviceMarkerPresent = Test-Path -LiteralPath $serviceFilePath -PathType Leaf
$serviceMarkerValid = $false
$serviceMarkerIdentityMatches = $false
$declaredServiceName = $null

if ($serviceMarkerPresent) {
    try {
        $serviceMarkerInfo = Get-Item -LiteralPath $serviceFilePath -ErrorAction Stop
        if ($serviceMarkerInfo.Length -gt 0 -and $serviceMarkerInfo.Length -le 1024) {
            $serviceNameCandidate = (
                Get-Content -LiteralPath $serviceFilePath -Raw -ErrorAction Stop
            ).Trim()
            if ($serviceNameCandidate -match $serviceNamePattern) {
                $serviceMarkerValid = $true
                $serviceMarkerIdentityMatches = $serviceNameCandidate.EndsWith(
                    $expectedServiceSuffix,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
                if ($serviceMarkerIdentityMatches) {
                    $declaredServiceName = $serviceNameCandidate
                }
            }
        }
    }
    catch {
        $serviceMarkerValid = $false
        $serviceMarkerIdentityMatches = $false
        $declaredServiceName = $null
    }
}

$service = $null
$serviceDetails = $null
$serviceQuerySucceeded = $false
$serviceQueryFailed = $false

if ($null -ne $declaredServiceName) {
    try {
        $matchingServices = @(
            Get-Service -ErrorAction Stop |
                Where-Object {
                    [string]::Equals(
                        $_.Name,
                        $declaredServiceName,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                }
        )
        $serviceQuerySucceeded = $true
        if ($matchingServices.Count -eq 1) {
            $service = $matchingServices[0]
        }
        elseif ($matchingServices.Count -gt 1) {
            $serviceQueryFailed = $true
            $serviceQuerySucceeded = $false
        }
    }
    catch {
        $serviceQueryFailed = $true
        $serviceQuerySucceeded = $false
    }
}

if ($null -ne $service -and -not $serviceQueryFailed) {
    try {
        $serviceDetailsMatches = @(
            Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
                Where-Object {
                    [string]::Equals(
                        $_.Name,
                        $declaredServiceName,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                }
        )
        if ($serviceDetailsMatches.Count -eq 1) {
            $serviceDetails = $serviceDetailsMatches[0]
        }
        else {
            $serviceQueryFailed = $true
            $serviceQuerySucceeded = $false
        }
    }
    catch {
        $serviceQueryFailed = $true
        $serviceQuerySucceeded = $false
    }
}

$serviceIdentityMatches = (
    $null -ne $service -and
    $null -ne $declaredServiceName -and
    [string]::Equals(
        $service.Name,
        $declaredServiceName,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and
    $service.Name.EndsWith(
        $expectedServiceSuffix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
$serviceState = if ($null -ne $serviceDetails) { $serviceDetails.State } else { $null }
$serviceStartMode = if ($null -ne $serviceDetails) { $serviceDetails.StartMode } else { $null }

$healthy = (
    $runnerRootExists -and
    $runnerConfigurationPresent -and
    $runnerConfigurationValid -and
    $runnerConfigurationIdentityMatches -and
    $runnerEphemeral -eq $false -and
    $runCommandPresent -and
    $serviceMarkerPresent -and
    $serviceMarkerValid -and
    $serviceMarkerIdentityMatches -and
    $serviceQuerySucceeded -and
    -not $serviceQueryFailed -and
    $null -ne $service -and
    $serviceIdentityMatches -and
    $null -ne $serviceDetails -and
    $serviceState -eq "Running" -and
    $serviceStartMode -eq "Auto"
)

$errorCode = $null
if (-not $runnerRootExists) {
    $errorCode = "RUNNER_ROOT_MISSING"
}
elseif (-not $runnerConfigurationPresent) {
    $errorCode = "RUNNER_CONFIGURATION_MISSING"
}
elseif (-not $runnerConfigurationValid) {
    $errorCode = "RUNNER_CONFIGURATION_INVALID"
}
elseif (-not $runnerConfigurationIdentityMatches) {
    $errorCode = "RUNNER_CONFIGURATION_IDENTITY_MISMATCH"
}
elseif ($runnerEphemeral -eq $true) {
    $errorCode = "RUNNER_EPHEMERAL_UNSUPPORTED"
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
elseif (-not $serviceMarkerIdentityMatches) {
    $errorCode = "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH"
}
elseif ($serviceQueryFailed -or -not $serviceQuerySucceeded) {
    $errorCode = "RUNNER_SERVICE_QUERY_FAILED"
}
elseif ($null -eq $service) {
    $errorCode = "RUNNER_SERVICE_MISSING"
}
elseif (-not $serviceIdentityMatches) {
    $errorCode = "RUNNER_SERVICE_IDENTITY_MISMATCH"
}
elseif ($null -eq $serviceDetails) {
    $errorCode = "RUNNER_SERVICE_QUERY_FAILED"
}
elseif ($serviceStartMode -ne "Auto") {
    $errorCode = "RUNNER_SERVICE_NOT_AUTOMATIC"
}
elseif ($serviceState -ne "Running") {
    $errorCode = "RUNNER_SERVICE_NOT_RUNNING"
}

$result = [pscustomobject]@{
    healthy = $healthy
    error_code = $errorCode
    runner_root_exists = $runnerRootExists
    expected_runner_name = $ExpectedRunnerName
    runner_configuration_present = $runnerConfigurationPresent
    runner_configuration_valid = $runnerConfigurationValid
    runner_configuration_error_detail = $runnerConfigurationErrorDetail
    runner_configuration_identity_matches = $runnerConfigurationIdentityMatches
    runner_ephemeral = $runnerEphemeral
    run_command_present = $runCommandPresent
    service_marker_present = $serviceMarkerPresent
    service_marker_valid = $serviceMarkerValid
    service_marker_identity_matches = $serviceMarkerIdentityMatches
    service_query_succeeded = $serviceQuerySucceeded
    service_identity_matches = $serviceIdentityMatches
    service_state = $serviceState
    service_start_mode = $serviceStartMode
}

Write-Result -Result $result
if ($healthy) {
    exit 0
}
exit 2
