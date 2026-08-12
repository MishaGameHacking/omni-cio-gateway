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

    $propertyMatches = @(
        $InputObject.PSObject.Properties |
            Where-Object {
                [string]::Equals(
                    $_.Name,
                    $Name,
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            }
    )
    if ($propertyMatches.Count -ne 1) {
        return $null
    }
    return $propertyMatches[0].Value
}

function New-Result {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Healthy,
        [Parameter()][AllowNull()][object]$ErrorCode,
        [Parameter()][AllowNull()][object]$DiagnosticErrorCode,
        [Parameter()][AllowNull()][object]$RunnerConfigurationErrorDetail,
        [Parameter()][AllowNull()][object]$RecoveryAction,
        [Parameter(Mandatory = $true)][bool]$MutationsAttempted,
        [Parameter()][AllowNull()][object]$MutationStage,
        [Parameter()][AllowNull()][object]$ServiceState,
        [Parameter()][AllowNull()][object]$ServiceStartMode
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

function Write-FailureAndExit {
    param(
        [Parameter(Mandatory = $true)][string]$ErrorCode,
        [Parameter()][AllowNull()][object]$DiagnosticErrorCode = $null,
        [Parameter()][AllowNull()][object]$RunnerConfigurationErrorDetail = $null,
        [Parameter()][AllowNull()][object]$RecoveryAction = $null,
        [Parameter()][bool]$MutationsAttempted = $false,
        [Parameter()][AllowNull()][object]$MutationStage = $null,
        [Parameter()][AllowNull()][object]$ServiceState = $null,
        [Parameter()][AllowNull()][object]$ServiceStartMode = $null
    )

    Write-Result -Result (New-Result `
        -Healthy $false `
        -ErrorCode $ErrorCode `
        -DiagnosticErrorCode $DiagnosticErrorCode `
        -RunnerConfigurationErrorDetail $RunnerConfigurationErrorDetail `
        -RecoveryAction $RecoveryAction `
        -MutationsAttempted $MutationsAttempted `
        -MutationStage $MutationStage `
        -ServiceState $ServiceState `
        -ServiceStartMode $ServiceStartMode)
    exit 2
}

function Invoke-RunnerDiagnostic {
    $diagnosticScript = Join-Path `
        -Path $PSScriptRoot `
        -ChildPath "check_self_hosted_windows_runner_service.ps1"
    if (-not (Test-Path -LiteralPath $diagnosticScript -PathType Leaf)) {
        return [pscustomobject]@{ valid = $false; exit_code = $null; payload = $null }
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
        return [pscustomobject]@{ valid = $false; exit_code = $diagnosticExit; payload = $null }
    }

    try {
        $payload = $text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return [pscustomobject]@{ valid = $false; exit_code = $diagnosticExit; payload = $null }
    }

    return [pscustomobject]@{
        valid = ($null -ne $payload)
        exit_code = $diagnosticExit
        payload = $payload
    }
}

function Test-DiagnosticContract {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Diagnostic
    )

    if (-not $Diagnostic.valid -or $null -eq $Diagnostic.payload) {
        return $false
    }

    $requiredNames = @(
        "healthy",
        "error_code",
        "runner_root_exists",
        "expected_runner_name",
        "runner_configuration_present",
        "runner_configuration_valid",
        "runner_configuration_error_detail",
        "runner_configuration_identity_matches",
        "runner_ephemeral",
        "run_command_present",
        "service_marker_present",
        "service_marker_valid",
        "service_marker_identity_matches",
        "service_query_succeeded",
        "service_identity_matches",
        "service_state",
        "service_start_mode"
    )

    foreach ($name in $requiredNames) {
        $propertyMatches = @(
            $Diagnostic.payload.PSObject.Properties |
                Where-Object {
                    [string]::Equals(
                        $_.Name,
                        $name,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                }
        )
        if ($propertyMatches.Count -ne 1) {
            return $false
        }
    }

    $reportedName = Get-PropertyValueOrdinalIgnoreCase `
        -InputObject $Diagnostic.payload `
        -Name "expected_runner_name"
    if (
        $reportedName -isnot [string] -or
        -not [string]::Equals(
            $reportedName,
            $ExpectedRunnerName,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        return $false
    }

    return $true
}

function Test-RecoverableDiagnosticState {
    param(
        [Parameter(Mandatory = $true)][object]$Diagnostic,
        [Parameter(Mandatory = $true)][string]$DiagnosticErrorCode
    )

    if ($Diagnostic.exit_code -ne 2) {
        return $false
    }

    $payload = $Diagnostic.payload
    $healthy = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "healthy"
    $rootExists = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_root_exists"
    $configPresent = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_configuration_present"
    $configValid = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_configuration_valid"
    $configDetail = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_configuration_error_detail"
    $identityMatches = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_configuration_identity_matches"
    $ephemeral = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "runner_ephemeral"
    $runCommandPresent = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "run_command_present"
    $markerPresent = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_marker_present"
    $markerValid = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_marker_valid"
    $markerIdentityMatches = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_marker_identity_matches"
    $serviceQuerySucceeded = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_query_succeeded"
    $serviceIdentityMatches = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_identity_matches"
    $serviceState = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_state"
    $serviceStartMode = Get-PropertyValueOrdinalIgnoreCase -InputObject $payload -Name "service_start_mode"

    $baseValid = (
        $healthy -eq $false -and
        $rootExists -eq $true -and
        $configPresent -eq $true -and
        $configValid -eq $true -and
        $null -eq $configDetail -and
        $identityMatches -eq $true -and
        $ephemeral -eq $false -and
        $runCommandPresent -eq $true -and
        $markerPresent -eq $true -and
        $markerValid -eq $true -and
        $markerIdentityMatches -eq $true -and
        $serviceQuerySucceeded -eq $true -and
        $serviceIdentityMatches -eq $true -and
        $serviceState -is [string] -and
        $serviceStartMode -is [string]
    )
    if (-not $baseValid) {
        return $false
    }

    if ($DiagnosticErrorCode -eq "RUNNER_SERVICE_NOT_AUTOMATIC") {
        return $serviceStartMode -ne "Auto"
    }
    if ($DiagnosticErrorCode -eq "RUNNER_SERVICE_NOT_RUNNING") {
        return ($serviceStartMode -eq "Auto" -and $serviceState -ne "Running")
    }
    return $false
}

function Test-OwnerAdministrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if ($env:OS -ne "Windows_NT") {
    Write-FailureAndExit -ErrorCode "RUNNER_SERVICE_WINDOWS_REQUIRED"
}

$diagnostic = Invoke-RunnerDiagnostic
if (-not (Test-DiagnosticContract -Diagnostic $diagnostic)) {
    Write-FailureAndExit -ErrorCode "RUNNER_RECOVERY_DIAGNOSTIC_INVALID"
}

$diagnosticHealthy = Get-PropertyValueOrdinalIgnoreCase -InputObject $diagnostic.payload -Name "healthy"
$diagnosticErrorCode = Get-PropertyValueOrdinalIgnoreCase -InputObject $diagnostic.payload -Name "error_code"
$runnerConfigurationErrorDetail = Get-PropertyValueOrdinalIgnoreCase -InputObject $diagnostic.payload -Name "runner_configuration_error_detail"
$diagnosticServiceState = Get-PropertyValueOrdinalIgnoreCase -InputObject $diagnostic.payload -Name "service_state"
$diagnosticServiceStartMode = Get-PropertyValueOrdinalIgnoreCase -InputObject $diagnostic.payload -Name "service_start_mode"

if ($diagnostic.exit_code -eq 0 -and $diagnosticHealthy -eq $true) {
    Write-Result -Result (New-Result `
        -Healthy $true `
        -ErrorCode $null `
        -DiagnosticErrorCode $null `
        -RunnerConfigurationErrorDetail $null `
        -RecoveryAction "NONE" `
        -MutationsAttempted $false `
        -MutationStage $null `
        -ServiceState $diagnosticServiceState `
        -ServiceStartMode $diagnosticServiceStartMode)
    exit 0
}

$recoverableDiagnosticCodes = @(
    "RUNNER_SERVICE_NOT_AUTOMATIC",
    "RUNNER_SERVICE_NOT_RUNNING"
)
if ($diagnosticErrorCode -notin $recoverableDiagnosticCodes) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RunnerConfigurationErrorDetail $runnerConfigurationErrorDetail `
        -ServiceState $diagnosticServiceState `
        -ServiceStartMode $diagnosticServiceStartMode
}

if (
    $diagnosticErrorCode -isnot [string] -or
    -not (Test-RecoverableDiagnosticState `
        -Diagnostic $diagnostic `
        -DiagnosticErrorCode $diagnosticErrorCode)
) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_DIAGNOSTIC_INVALID" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RunnerConfigurationErrorDetail $runnerConfigurationErrorDetail `
        -ServiceState $diagnosticServiceState `
        -ServiceStartMode $diagnosticServiceStartMode
}

$serviceFilePath = Join-Path -Path $RunnerRoot -ChildPath ".service"
$expectedServiceSuffix = ".$ExpectedRunnerName.service"
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,480}\.service$'

if (-not (Test-Path -LiteralPath $serviceFilePath -PathType Leaf)) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode $diagnosticErrorCode
}

try {
    $serviceMarkerInfo = [System.IO.FileInfo]::new($serviceFilePath)
    $serviceMarkerInfo.Refresh()
    if ($serviceMarkerInfo.Length -le 0 -or $serviceMarkerInfo.Length -gt 1024) {
        throw "bounded service marker required"
    }
    $declaredServiceName = [System.IO.File]::ReadAllText(
        $serviceFilePath,
        [System.Text.Encoding]::UTF8
    ).Trim()
}
catch {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode $diagnosticErrorCode
}

$serviceMarkerValid = (
    $declaredServiceName -match $serviceNamePattern -and
    $declaredServiceName.EndsWith(
        $expectedServiceSuffix,
        [System.StringComparison]::OrdinalIgnoreCase
    )
)
if (-not $serviceMarkerValid) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" `
        -DiagnosticErrorCode $diagnosticErrorCode
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
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_QUERY_FAILED" `
        -DiagnosticErrorCode $diagnosticErrorCode
}

if ($matchingServices.Count -ne 1 -or $matchingServiceDetails.Count -ne 1) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_IDENTITY_AMBIGUOUS" `
        -DiagnosticErrorCode $diagnosticErrorCode
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
    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_SERVICE_IDENTITY_AMBIGUOUS" `
        -DiagnosticErrorCode $diagnosticErrorCode
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
    if (
        (Test-DiagnosticContract -Diagnostic $postDiagnostic) -and
        $postDiagnostic.exit_code -eq 0 -and
        (Get-PropertyValueOrdinalIgnoreCase `
            -InputObject $postDiagnostic.payload `
            -Name "healthy") -eq $true
    ) {
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

    Write-FailureAndExit `
        -ErrorCode "RUNNER_RECOVERY_STATE_CHANGED" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RecoveryAction "VERIFY_HEALTHY" `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode
}

if (-not $Apply) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_PREVIEW" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RecoveryAction $recoveryAction `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode
}

if (-not (Test-OwnerAdministrator)) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RecoveryAction $recoveryAction `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode
}

$mutationsAttempted = $false
$mutationStage = $null
try {
    if ($needsAutomatic) {
        $mutationStage = "SET_AUTOMATIC"
        $mutationsAttempted = $true
        Set-Service `
            -Name $declaredServiceName `
            -StartupType Automatic `
            -ErrorAction Stop
    }
    if ($needsStart) {
        $mutationStage = "START"
        $mutationsAttempted = $true
        Start-Service -Name $declaredServiceName -ErrorAction Stop
    }
}
catch {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_MUTATION_FAILED" `
        -DiagnosticErrorCode $diagnosticErrorCode `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage `
        -ServiceState $serviceState `
        -ServiceStartMode $serviceStartMode
}

$postDiagnostic = Invoke-RunnerDiagnostic
if (-not (Test-DiagnosticContract -Diagnostic $postDiagnostic)) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage
}

$postHealthy = Get-PropertyValueOrdinalIgnoreCase -InputObject $postDiagnostic.payload -Name "healthy"
$postErrorCode = Get-PropertyValueOrdinalIgnoreCase -InputObject $postDiagnostic.payload -Name "error_code"
$postConfigurationDetail = Get-PropertyValueOrdinalIgnoreCase -InputObject $postDiagnostic.payload -Name "runner_configuration_error_detail"
$postServiceState = Get-PropertyValueOrdinalIgnoreCase -InputObject $postDiagnostic.payload -Name "service_state"
$postServiceStartMode = Get-PropertyValueOrdinalIgnoreCase -InputObject $postDiagnostic.payload -Name "service_start_mode"

if ($postDiagnostic.exit_code -ne 0 -or $postHealthy -ne $true) {
    Write-FailureAndExit `
        -ErrorCode "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" `
        -DiagnosticErrorCode $postErrorCode `
        -RunnerConfigurationErrorDetail $postConfigurationDetail `
        -RecoveryAction $recoveryAction `
        -MutationsAttempted $mutationsAttempted `
        -MutationStage $mutationStage `
        -ServiceState $postServiceState `
        -ServiceStartMode $postServiceStartMode
}

Write-Result -Result (New-Result `
    -Healthy $true `
    -ErrorCode $null `
    -DiagnosticErrorCode $null `
    -RunnerConfigurationErrorDetail $null `
    -RecoveryAction $recoveryAction `
    -MutationsAttempted $mutationsAttempted `
    -MutationStage $mutationStage `
    -ServiceState $postServiceState `
    -ServiceStartMode $postServiceStartMode)
exit 0
