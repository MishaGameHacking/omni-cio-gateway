[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RunnerRoot = "C:\actions-runner",

    [Parameter()]
    [ValidateNotNullOrEmpty()]
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
        Where-Object { $_.Name -like "*.$ExpectedRunnerName.service" } |
        Select-Object -First 1
}

$serviceDetails = $null
if ($null -ne $service) {
    $escapedServiceName = $service.Name.Replace("'", "''")
    $serviceDetails = Get-CimInstance -ClassName Win32_Service -Filter "Name='$escapedServiceName'"
}

$serviceName = if ($null -ne $service) { $service.Name } else { $declaredServiceName }
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
