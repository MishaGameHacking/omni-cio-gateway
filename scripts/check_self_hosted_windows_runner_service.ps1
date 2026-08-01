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

if ($env:OS -ne "Windows_NT") {
    $result = [pscustomobject]@{
        healthy = $false
        error_code = "RUNNER_SERVICE_WINDOWS_REQUIRED"
        runner_root_exists = $false
        expected_runner_name = $ExpectedRunnerName
        runner_configuration_present = $false
        runner_configuration_valid = $false
        runner_configuration_identity_matches = $false
        runner_ephemeral = $null
        run_command_present = $false
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

$runnerConfigurationPresent = Test-Path -LiteralPath $runnerConfigPath -PathType Leaf
$runnerConfigurationValid = $false
$runnerConfigurationIdentityMatches = $false
$runnerEphemeral = $null

if ($runnerConfigurationPresent) {
    try {
        $runnerConfigInfo = Get-Item -LiteralPath $runnerConfigPath
        if ($runnerConfigInfo.Length -le 65536) {
            $runnerSettings = Get-Content -LiteralPath $runnerConfigPath -Raw |
                ConvertFrom-Json -ErrorAction Stop
            $agentNameProperty = $runnerSettings.PSObject.Properties["AgentName"]
            $ephemeralProperty = $runnerSettings.PSObject.Properties["Ephemeral"]

            $agentNameValid = (
                $null -ne $agentNameProperty -and
                $agentNameProperty.Value -is [string] -and
                -not [string]::IsNullOrWhiteSpace($agentNameProperty.Value)
            )
            $ephemeralValid = (
                $null -eq $ephemeralProperty -or
                $ephemeralProperty.Value -is [bool]
            )

            if ($agentNameValid -and $ephemeralValid) {
                $runnerConfigurationValid = $true
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
    catch {
        $runnerConfigurationValid = $false
        $runnerConfigurationIdentityMatches = $false
        $runnerEphemeral = $null
    }
}

$declaredServiceName = $null
if (Test-Path -LiteralPath $serviceFilePath -PathType Leaf) {
    $declaredServiceName = (Get-Content -LiteralPath $serviceFilePath -Raw).Trim()
    if ([string]::IsNullOrWhiteSpace($declaredServiceName)) {
        $declaredServiceName = $null
    }
}

$service = $null
if ($null -ne $declaredServiceName) {
    $service = Get-Service -Name $declaredServiceName -ErrorAction SilentlyContinue
}

if ($null -eq $service) {
    $service = Get-Service -Name "actions.runner.*" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name.EndsWith(
                $expectedServiceSuffix,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        } |
        Select-Object -First 1
}

$serviceDetails = $null
if ($null -ne $service) {
    $escapedServiceName = $service.Name.Replace("'", "''")
    $serviceDetails = Get-CimInstance `
        -ClassName Win32_Service `
        -Filter "Name='$escapedServiceName'" `
        -ErrorAction SilentlyContinue
}

$serviceIdentityMatches = (
    $null -ne $service -and
    $service.Name.EndsWith(
        $expectedServiceSuffix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
$serviceState = if ($null -ne $serviceDetails) { $serviceDetails.State } else { $null }
$serviceStartMode = if ($null -ne $serviceDetails) { $serviceDetails.StartMode } else { $null }
$runCommandPresent = Test-Path -LiteralPath $runCommandPath -PathType Leaf

$healthy = (
    $runnerRootExists -and
    $runnerConfigurationPresent -and
    $runnerConfigurationValid -and
    $runnerConfigurationIdentityMatches -and
    $runnerEphemeral -eq $false -and
    $runCommandPresent -and
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
    runner_configuration_identity_matches = $runnerConfigurationIdentityMatches
    runner_ephemeral = $runnerEphemeral
    run_command_present = $runCommandPresent
    service_identity_matches = $serviceIdentityMatches
    service_state = $serviceState
    service_start_mode = $serviceStartMode
}

Write-Result -Result $result
if ($healthy) {
    exit 0
}
exit 2
