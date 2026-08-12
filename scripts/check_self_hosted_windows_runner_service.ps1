[CmdletBinding()]
param(
    [Parameter()][ValidateNotNullOrEmpty()][string]$RunnerRoot = "C:\actions-runner",
    [Parameter()][ValidatePattern('^[A-Za-z0-9._-]{1,64}$')][string]$ExpectedRunnerName = "omni-cio-ci",
    [Parameter()][switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][pscustomobject]$Result)
    if ($AsJson) { $Result | ConvertTo-Json -Depth 4 -Compress }
    else { $Result | Format-List }
}

function Get-JsonPropertyOrdinalIgnoreCase {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$Name
    )
    $propertyMatches = @(
        $InputObject.PSObject.Properties | Where-Object {
            [string]::Equals($_.Name, $Name, [System.StringComparison]::OrdinalIgnoreCase)
        }
    )
    if ($propertyMatches.Count -ne 1) { return $null }
    return $propertyMatches[0]
}

function New-Result {
    param(
        [bool]$Healthy,
        [AllowNull()][object]$ErrorCode,
        [bool]$RunnerRootExists,
        [bool]$RunnerConfigurationPresent,
        [bool]$RunnerConfigurationValid,
        [AllowNull()][object]$RunnerConfigurationErrorDetail,
        [bool]$RunnerConfigurationIdentityMatches,
        [AllowNull()][object]$RunnerEphemeral,
        [bool]$RunCommandPresent,
        [bool]$ServiceMarkerPresent,
        [bool]$ServiceMarkerValid,
        [bool]$ServiceMarkerIdentityMatches,
        [bool]$ServiceQuerySucceeded,
        [bool]$ServiceIdentityMatches,
        [AllowNull()][object]$ServiceState,
        [AllowNull()][object]$ServiceStartMode
    )
    return [pscustomobject]@{
        healthy = $Healthy
        error_code = $ErrorCode
        runner_root_exists = $RunnerRootExists
        expected_runner_name = $ExpectedRunnerName
        runner_configuration_present = $RunnerConfigurationPresent
        runner_configuration_valid = $RunnerConfigurationValid
        runner_configuration_error_detail = $RunnerConfigurationErrorDetail
        runner_configuration_identity_matches = $RunnerConfigurationIdentityMatches
        runner_ephemeral = $RunnerEphemeral
        run_command_present = $RunCommandPresent
        service_marker_present = $ServiceMarkerPresent
        service_marker_valid = $ServiceMarkerValid
        service_marker_identity_matches = $ServiceMarkerIdentityMatches
        service_query_succeeded = $ServiceQuerySucceeded
        service_identity_matches = $ServiceIdentityMatches
        service_state = $ServiceState
        service_start_mode = $ServiceStartMode
    }
}

if ($env:OS -ne "Windows_NT") {
    Write-Result -Result (New-Result $false "RUNNER_SERVICE_WINDOWS_REQUIRED" $false $false $false $null $false $null $false $false $false $false $false $false $null $null)
    exit 2
}

$runnerRootExists = Test-Path -LiteralPath $RunnerRoot -PathType Container
$runnerConfigPath = Join-Path $RunnerRoot ".runner"
$serviceFilePath = Join-Path $RunnerRoot ".service"
$runCommandPath = Join-Path $RunnerRoot "run.cmd"
$expectedServiceSuffix = ".$ExpectedRunnerName"
# actions/runner WindowsServiceControlManager writes actions.runner.{repo-or-org}.{runner-name}.
# Windows limits the service name to 80 chars; the allowed source characters are [0-9A-Za-z._-].
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,65}$'

$runnerConfigurationPresent = Test-Path -LiteralPath $runnerConfigPath -PathType Leaf
$runnerConfigurationValid = $false
$runnerConfigurationErrorDetail = $null
$runnerConfigurationIdentityMatches = $false
$runnerEphemeral = $null

if ($runnerConfigurationPresent) {
    $runnerSettings = $null
    try {
        $info = [System.IO.FileInfo]::new($runnerConfigPath)
        $info.Refresh()
        if ($info.Length -le 0 -or $info.Length -gt 65536) {
            $runnerConfigurationErrorDetail = "SIZE_INVALID"
        }
        else {
            $text = [System.IO.File]::ReadAllText($runnerConfigPath, [System.Text.Encoding]::UTF8)
            try { $runnerSettings = $text | ConvertFrom-Json -ErrorAction Stop }
            catch { $runnerConfigurationErrorDetail = "JSON_INVALID" }
            if ($null -eq $runnerSettings -and $null -eq $runnerConfigurationErrorDetail) {
                $runnerConfigurationErrorDetail = "AGENT_NAME_INVALID"
            }
        }
    }
    catch {
        $runnerConfigurationErrorDetail = "READ_FAILED"
    }

    if ($null -ne $runnerSettings) {
        try {
            $agentNameProperty = Get-JsonPropertyOrdinalIgnoreCase -InputObject $runnerSettings -Name "AgentName"
            $ephemeralProperty = Get-JsonPropertyOrdinalIgnoreCase -InputObject $runnerSettings -Name "Ephemeral"
            $agentNameValid = (
                $null -ne $agentNameProperty -and
                $agentNameProperty.Value -is [string] -and
                -not [string]::IsNullOrWhiteSpace($agentNameProperty.Value)
            )
            $ephemeralValid = ($null -eq $ephemeralProperty -or $ephemeralProperty.Value -is [bool])
            if (-not $agentNameValid) { $runnerConfigurationErrorDetail = "AGENT_NAME_INVALID" }
            elseif (-not $ephemeralValid) { $runnerConfigurationErrorDetail = "EPHEMERAL_INVALID" }
            else {
                $runnerConfigurationValid = $true
                $runnerConfigurationErrorDetail = $null
                $runnerConfigurationIdentityMatches = [string]::Equals(
                    [string]$agentNameProperty.Value,
                    $ExpectedRunnerName,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
                $runnerEphemeral = if ($null -eq $ephemeralProperty) { $false } else { [bool]$ephemeralProperty.Value }
            }
        }
        catch {
            $runnerConfigurationErrorDetail = "AGENT_NAME_INVALID"
            $runnerConfigurationValid = $false
        }
    }
}

$runCommandPresent = Test-Path -LiteralPath $runCommandPath -PathType Leaf
$serviceMarkerPresent = Test-Path -LiteralPath $serviceFilePath -PathType Leaf
$serviceMarkerValid = $false
$serviceMarkerIdentityMatches = $false
$declaredServiceName = $null

if ($serviceMarkerPresent) {
    try {
        $info = [System.IO.FileInfo]::new($serviceFilePath)
        $info.Refresh()
        if ($info.Length -gt 0 -and $info.Length -le 1024) {
            $candidate = [System.IO.File]::ReadAllText($serviceFilePath, [System.Text.Encoding]::UTF8).Trim()
            if ($candidate.Length -le 80 -and $candidate -match $serviceNamePattern) {
                $serviceMarkerValid = $true
                $serviceMarkerIdentityMatches = $candidate.EndsWith(
                    $expectedServiceSuffix,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
                if ($serviceMarkerIdentityMatches) { $declaredServiceName = $candidate }
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
        $matchingServices = @(Get-Service -ErrorAction Stop | Where-Object {
            [string]::Equals($_.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase)
        })
        $serviceQuerySucceeded = $true
        if ($matchingServices.Count -eq 1) { $service = $matchingServices[0] }
        elseif ($matchingServices.Count -gt 1) { $serviceQueryFailed = $true; $serviceQuerySucceeded = $false }
    }
    catch { $serviceQueryFailed = $true; $serviceQuerySucceeded = $false }
}
if ($null -ne $service -and -not $serviceQueryFailed) {
    try {
        $matchingDetails = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop | Where-Object {
            [string]::Equals($_.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase)
        })
        if ($matchingDetails.Count -eq 1) { $serviceDetails = $matchingDetails[0] }
        else { $serviceQueryFailed = $true; $serviceQuerySucceeded = $false }
    }
    catch { $serviceQueryFailed = $true; $serviceQuerySucceeded = $false }
}

$serviceIdentityMatches = (
    $null -ne $service -and $null -ne $declaredServiceName -and
    [string]::Equals($service.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase) -and
    $service.Name.EndsWith($expectedServiceSuffix, [System.StringComparison]::OrdinalIgnoreCase)
)
$serviceState = if ($null -ne $serviceDetails) { [string]$serviceDetails.State } else { $null }
$serviceStartMode = if ($null -ne $serviceDetails) { [string]$serviceDetails.StartMode } else { $null }

$healthy = (
    $runnerRootExists -and $runnerConfigurationPresent -and $runnerConfigurationValid -and
    $runnerConfigurationIdentityMatches -and $runnerEphemeral -eq $false -and $runCommandPresent -and
    $serviceMarkerPresent -and $serviceMarkerValid -and $serviceMarkerIdentityMatches -and
    $serviceQuerySucceeded -and -not $serviceQueryFailed -and $null -ne $service -and
    $serviceIdentityMatches -and $null -ne $serviceDetails -and
    $serviceState -eq "Running" -and $serviceStartMode -eq "Auto"
)

$errorCode = $null
if (-not $runnerRootExists) { $errorCode = "RUNNER_ROOT_MISSING" }
elseif (-not $runnerConfigurationPresent) { $errorCode = "RUNNER_CONFIGURATION_MISSING" }
elseif (-not $runnerConfigurationValid) { $errorCode = "RUNNER_CONFIGURATION_INVALID" }
elseif (-not $runnerConfigurationIdentityMatches) { $errorCode = "RUNNER_CONFIGURATION_IDENTITY_MISMATCH" }
elseif ($runnerEphemeral -eq $true) { $errorCode = "RUNNER_EPHEMERAL_UNSUPPORTED" }
elseif (-not $runCommandPresent) { $errorCode = "RUNNER_COMMAND_MISSING" }
elseif (-not $serviceMarkerPresent) { $errorCode = "RUNNER_SERVICE_MARKER_MISSING" }
elseif (-not $serviceMarkerValid) { $errorCode = "RUNNER_SERVICE_MARKER_INVALID" }
elseif (-not $serviceMarkerIdentityMatches) { $errorCode = "RUNNER_SERVICE_MARKER_IDENTITY_MISMATCH" }
elseif ($serviceQueryFailed -or -not $serviceQuerySucceeded) { $errorCode = "RUNNER_SERVICE_QUERY_FAILED" }
elseif ($null -eq $service) { $errorCode = "RUNNER_SERVICE_MISSING" }
elseif (-not $serviceIdentityMatches) { $errorCode = "RUNNER_SERVICE_IDENTITY_MISMATCH" }
elseif ($null -eq $serviceDetails) { $errorCode = "RUNNER_SERVICE_QUERY_FAILED" }
elseif ($serviceStartMode -ne "Auto") { $errorCode = "RUNNER_SERVICE_NOT_AUTOMATIC" }
elseif ($serviceState -ne "Running") { $errorCode = "RUNNER_SERVICE_NOT_RUNNING" }

Write-Result -Result (New-Result $healthy $errorCode $runnerRootExists $runnerConfigurationPresent $runnerConfigurationValid $runnerConfigurationErrorDetail $runnerConfigurationIdentityMatches $runnerEphemeral $runCommandPresent $serviceMarkerPresent $serviceMarkerValid $serviceMarkerIdentityMatches $serviceQuerySucceeded $serviceIdentityMatches $serviceState $serviceStartMode)
if ($healthy) { exit 0 }
exit 2
