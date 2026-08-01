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
        runner_root = $RunnerRoot
        expected_runner_name = $ExpectedRunnerName
        service_name = $null
        service_identity_matches = $false
        service_state = $null
        service_start_mode = $null
        service_path = $null
        runner_configuration_present = $false
        run_command_present = $false
    }
    Write-Result -Result $result
    exit 2
}

$runnerRootExists = Test-Path -LiteralPath $RunnerRoot -PathType Container
$serviceFilePath = Join-Path -Path $RunnerRoot -ChildPath ".service"
$runnerConfigPath = Join-Path -Path $RunnerRoot -ChildPath ".runner"
$runCommandPath = Join-Path -Path $RunnerRoot -ChildPath "run.cmd"
$expectedServiceSuffix = ".$ExpectedRunnerName.service"

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

$serviceName = if ($null -ne $service) { $service.Name } else { $declaredServiceName }
$serviceIdentityMatches = (
    $null -ne $service -and
    $service.Name.EndsWith(
        $expectedServiceSuffix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
$serviceState = if ($null -ne $serviceDetails) { $serviceDetails.State } else { $null }
$serviceStartMode = if ($null -ne $serviceDetails) { $serviceDetails.StartMode } else { $null }
$servicePath = if ($null -ne $serviceDetails) { $serviceDetails.PathName } else { $null }
$runnerConfigurationPresent = Test-Path -LiteralPath $runnerConfigPath -PathType Leaf
$runCommandPresent = Test-Path -LiteralPath $runCommandPath -PathType Leaf

$healthy = (
    $runnerRootExists -and
    $runnerConfigurationPresent -and
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
    runner_root = $RunnerRoot
    expected_runner_name = $ExpectedRunnerName
    service_name = $serviceName
    service_identity_matches = $serviceIdentityMatches
    service_state = $serviceState
    service_start_mode = $serviceStartMode
    service_path = $servicePath
    runner_configuration_present = $runnerConfigurationPresent
    run_command_present = $runCommandPresent
}

Write-Result -Result $result
if ($healthy) {
    exit 0
}
exit 2
