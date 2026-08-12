[CmdletBinding()]
param(
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RunnerRoot = "C:\actions-runner",

    [Parameter()]
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$ExpectedRunnerName = "omni-cio-ci",

    [Parameter()]
    [switch]$Apply,

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

function Get-PropertyValueOrdinalIgnoreCase {
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
    return $matches[0].Value
}

function Invoke-RunnerDiagnostic {
    $diagnosticScript = Join-Path -Path $PSScriptRoot -ChildPath "check_self_hosted_windows_runner_service.ps1"
    if (-not (Test-Path -LiteralPath $diagnosticScript -PathType Leaf)) {
        return [pscustomobject]@{
            valid = $false
            exit_code = $null
            payload = $null
        }
    }

    $output = @(
        & powershell.exe `
            -NoLogo `
            -NoProfile `
            -NonInteractive `
            -ExecutionPolicy Bypass `
            -File $diagnosticScript `
            -RunnerRoot $RunnerRoot `
            -ExpectedRunnerName $ExpectedRunnerName `
            -AsJson 2>$null
    )
    $diagnosticExit = $LASTEXITCODE
    $text = ($output -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return [pscustomobject]@{
            valid = $false
            exit_code = $diagnosticExit
            payload = $null
        }
    }

    try {
        $payload = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return [pscustomobject]@{
            valid = $false
            exit_code = $diagnosticExit
            payload = $null
        }
    }

    return [pscustomobject]@{
        valid = $true
        exit_code = $diagnosticExit
        payload = $payload
    }
}

function Test-OwnerAdministrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function New-Result {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Healthy,

        [Parameter()]
        [AllowNull()]
        [object]$ErrorCode,

        [Parameter()]
        [AllowNull()]
        [object]$DiagnosticErrorCode,

        [Parameter()]
        [AllowNull()]
        [object]$RunnerConfigurationErrorDetail,

        [Parameter()]
        [AllowNull()]
        [object]$RecoveryAction,

        [Parameter(Mandatory = $true)]
        [bool]$MutationsAttempted,

        [Parameter()]
        [AllowNull()]
        [object]$MutationStage,

        [Parameter()]
        [AllowNull()]
        [object]$ServiceState,

        [Parameter()]
        [AllowNull()]
        [object]$ServiceStartMode
    )

    return [pscustomobject]@{
        healthy = $Healthy
        error_code = $ErrorCode
        diagnostic_error_code = $DiagnosticErrorCode
        runner_configuration_error_detail = $RunnerConfigurationErrorDetail
        expected_runner_name = $ExpectedRunnerName
        apply_requested = [bool]$Apply
        recovery_action = $RecoveryAction
        mutations_attempted = $MutationsAttempted
        mutation_stage = $MutationStage
        service_state = $ServiceState
        service_start_mode = $ServiceStartMode
        ready = $Healthy
    }
}

if ($env:OS -ne "Windows_NT") {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_WINDOWS_REQUIRED" `
        -DiagnosticErrorCode $null `
        -RunnerConfigurationErrorDetail $null `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$diagnostic = Invoke-RunnerDiagnostic
if (-not $diagnostic.valid -or $null -eq $diagnostic.payload) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_DIAGNOSTIC_INVALID" `
        -DiagnosticErrorCode $null `
        -RunnerConfigurationErrorDetail $null `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$diagnosticHealthy = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $diagnostic.payload `
    -Name "healthy"
$diagnosticErrorCode = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $diagnostic.payload `
    -Name "error_code"
$runnerConfigurationErrorDetail = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $diagnostic.payload `
    -Name "runner_configuration_error_detail"
$diagnosticServiceState = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $diagnostic.payload `
    -Name "service_state"
$diagnosticServiceStartMode = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $diagnostic.payload `
    -Name "service_start_mode"

if ($diagnostic.exit_code -eq 0 -and $diagnosticHealthy -eq $true) {
    Write-Result -Result (New-Result `
        -Healthy $true `
        -ErrorCode $null `
        -DiagnosticErrorCode $null `
        -RunnerConfigurationErrorDetail $null `
        -RecoveryAction "NONE" `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState ([string]$diagnosticServiceState) `
        -ServiceStartMode ([string]$diagnosticServiceStartMode))
    exit 0
}

$recoverableDiagnosticCodes = @(
    "RUNNER_SERVICE_NOT_AUTOMATIC",
    "RUNNER_SERVICE_NOT_RUNNING"
)
if ($diagnosticErrorCode -notin $recoverableDiagnosticCodes) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState ([string]$diagnosticServiceState) `
        -ServiceStartMode ([string]$diagnosticServiceStartMode))
    exit 2
}

$serviceFilePath = Join-Path -Path $RunnerRoot -ChildPath ".service"
$expectedServiceSuffix = ".$ExpectedRunnerName.service"
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$'

if (-not (Test-Path -LiteralPath $serviceFilePath -PathType Leaf)) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

try {
    $serviceMarkerInfo = Get-Item -LiteralPath $serviceFilePath -ErrorAction Stop
    if ($serviceMarkerInfo.Length -le 0 -or $serviceMarkerInfo.Length -gt 1024) {
        throw "bounded service marker required"
    }
    $declaredServiceName = (
        Get-Content -LiteralPath $serviceFilePath -Raw -ErrorAction Stop
    ).Trim()
}
catch {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$serviceMarkerValid = (
    $declaredServiceName -match $serviceNamePattern -and
    $declaredServiceName.EndsWith(
        $expectedServiceSuffix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
if (-not $serviceMarkerValid) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

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
    $matchingServiceDetails = @(
        Get-CimInstance -ClassName Win32_Service -ErrorAction Stop |
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
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_QUERY_FAILED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

if ($matchingServices.Count -ne 1 -or $matchingServiceDetails.Count -ne 1) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_IDENTITY_AMBIGUOUS" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$service = $matchingServices[0]
$serviceDetails = $matchingServiceDetails[0]
$serviceIdentityValid = (
    [string]::Equals(
        $service.Name,
        $declaredServiceName,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -and
    [string]::Equals(
        $serviceDetails.Name,
        $declaredServiceName,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
if (-not $serviceIdentityValid) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_IDENTITY_AMBIGUOUS" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $null `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$serviceState = [string]$serviceDetails.State
$serviceStartMode = [string]$serviceDetails.StartMode
$needsAutomatic = $serviceStartMode -ne "Auto"
$needsStart = $serviceState -ne "Running"

$recoveryAction = if ($needsAutomatic -and $needsStart) {
    "SET_AUTOMATIC_AND_START"
}
elseif ($needsAutomatic) {
    "SET_AUTOMATIC"
}
elseif ($needsStart) {
    "START"
}
else {
    "VERIFY_HEALTHY"
}

if (-not $needsAutomatic -and -not $needsStart) {
    $postDiagnostic = Invoke-RunnerDiagnostic
    $postHealthy = if ($postDiagnostic.valid -and $null -ne $postDiagnostic.payload) {
        Get-PropertyValueOrdinalIgnoreCase `
            -InputObject $postDiagnostic.payload `
            -Name "healthy"
    }
    else {
        $false
    }

    if ($postDiagnostic.exit_code -eq 0 -and $postHealthy -eq $true) {
        Write-Result -Result (New-Result `
            -Healthy $true `
            -ErrorCode $null `
            -DiagnosticErrorCode $null `
            -RunnerConfigurationErrorDetail $null `
            -RecoveryAction "NONE" `
            -MutationsAttempted $false `
            -MutationStage $null `
            -ServiceState "Running" `
            -ServiceStartMode "Auto")
        exit 0
    }

    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_RECOVERY_STATE_CHANGED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction "VERIFY_HEALTHY" `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode)
    exit 2
}

if (-not $Apply) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_PREVIEW" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode)
    exit 2
}

if (-not (Test-OwnerAdministrator)) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode)
    exit 2
}

$mutationsAttempted = $false
$mutationStage = $null
try {
    if ($needsAutomatic) {
        $mutationStage = "SET_AUTOMATIC"
        $mutationsAttempted = $true
        Set-Service -Name $declaredServiceName -StartupType Automatic -ErrorAction Stop
    }
    if ($needsStart) {
        $mutationStage = "START"
        $mutationsAttempted = $true
        Start-Service -Name $declaredServiceName -ErrorAction Stop
    }
}
catch {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_MUTATION_FAILED" `
        -DiagnosticErrorCode ([string]$diagnosticErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$runnerConfigurationErrorDetail) `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode)
    exit 2
}

$postDiagnostic = Invoke-RunnerDiagnostic
if (-not $postDiagnostic.valid -or $null -eq $postDiagnostic.payload) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" `
        -DiagnosticErrorCode $null `
        -RunnerConfigurationErrorDetail $null `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage `
        -ServiceState $null `
        -ServiceStartMode $null)
    exit 2
}

$postHealthy = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $postDiagnostic.payload `
    -Name "healthy"
$postErrorCode = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $postDiagnostic.payload `
    -Name "error_code"
$postConfigurationDetail = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $postDiagnostic.payload `
    -Name "runner_configuration_error_detail"
$postServiceState = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $postDiagnostic.payload `
    -Name "service_state"
$postServiceStartMode = Get-PropertyValueOrdinalIgnoreCase `
    -InputObject $postDiagnostic.payload `
    -Name "service_start_mode"

if ($postDiagnostic.exit_code -ne 0 -or $postHealthy -ne $true) {
    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" `
        -DiagnosticErrorCode ([string]$postErrorCode) `
        -RunnerConfigurationErrorDetail ([string]$postConfigurationDetail) `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage `
        -ServiceState ([string]$postServiceState) `
        -ServiceStartMode ([string]$postServiceStartMode))
    exit 2
}

Write-Result -Result (New-Result `
    -Healthy $true `
    -ErrorCode $null `
    -DiagnosticErrorCode $null `
    -RunnerConfigurationErrorDetail $null `
    -RecoveryAction $recoveryAction `
    -MutationsAttempted $mutationsAttempted `
    -MutationStage $mutationStage `
    -ServiceState ([string]$postServiceState) `
    -ServiceStartMode ([string]$postServiceStartMode))
exit 0
