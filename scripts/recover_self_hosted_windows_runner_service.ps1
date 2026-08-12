[CmdletBinding()]
param(
    [Parameter()][ValidateNotNullOrEmpty()][string]$RunnerRoot = "C:\actions-runner",
    [Parameter()][ValidatePattern('^[A-Za-z0-9._-]{1,64}$')][string]$ExpectedRunnerName = "omni-cio-ci",
    [Parameter()][switch]$Apply,
    [Parameter()][switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Result {
    param([Parameter(Mandatory = $true)][pscustomobject]$Result)
    if ($AsJson) { $Result | ConvertTo-Json -Depth 4 -Compress }
    else { $Result | Format-List }
}

function Get-PropertyValueOrdinalIgnoreCase {
    param(
        [Parameter(Mandatory = $true)][object]$InputObject,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$Name
    )
    $propertyMatches = @($InputObject.PSObject.Properties | Where-Object {
        [string]::Equals($_.Name, $Name, [System.StringComparison]::OrdinalIgnoreCase)
    })
    if ($propertyMatches.Count -ne 1) { return $null }
    return $propertyMatches[0].Value
}

function Test-ServiceExecutablePathMatches {
    param(
        [AllowNull()][object]$PathName,
        [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$ExpectedPath
    )
    if ($null -eq $PathName) { return $false }
    $candidate = ([string]$PathName).Trim()
    if ([string]::IsNullOrWhiteSpace($candidate)) { return $false }
    if (
        $candidate.Length -ge 2 -and
        $candidate[0] -eq [char]34 -and
        $candidate[$candidate.Length - 1] -eq [char]34
    ) {
        $candidate = $candidate.Substring(1, $candidate.Length - 2)
    }
    try {
        $normalizedCandidate = [System.IO.Path]::GetFullPath($candidate)
        $normalizedExpected = [System.IO.Path]::GetFullPath($ExpectedPath)
    }
    catch { return $false }
    return [string]::Equals(
        $normalizedCandidate,
        $normalizedExpected,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function New-Result {
    param(
        [Parameter(Mandatory = $true)][bool]$Healthy,
        [AllowNull()][object]$ErrorCode,
        [AllowNull()][object]$DiagnosticErrorCode,
        [AllowNull()][object]$RunnerConfigurationErrorDetail,
        [AllowNull()][object]$RecoveryAction,
        [Parameter(Mandatory = $true)][bool]$MutationsAttempted,
        [AllowNull()][object]$MutationStage,
        [AllowNull()][object]$ServiceState,
        [AllowNull()][object]$ServiceStartMode
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
        [AllowNull()][object]$DiagnosticErrorCode = $null,
        [AllowNull()][object]$RunnerConfigurationErrorDetail = $null,
        [AllowNull()][object]$RecoveryAction = $null,
        [bool]$MutationsAttempted = $false,
        [AllowNull()][object]$MutationStage = $null,
        [AllowNull()][object]$ServiceState = $null,
        [AllowNull()][object]$ServiceStartMode = $null
    )
    Write-Result -Result (New-Result $false $ErrorCode $DiagnosticErrorCode $RunnerConfigurationErrorDetail $RecoveryAction $MutationsAttempted $MutationStage $ServiceState $ServiceStartMode)
    exit 2
}

function Invoke-RunnerDiagnostic {
    $diagnosticScript = Join-Path -Path $PSScriptRoot -ChildPath "check_self_hosted_windows_runner_service.ps1"
    if (-not (Test-Path -LiteralPath $diagnosticScript -PathType Leaf)) {
        return [pscustomobject]@{ valid = $false; exit_code = $null; payload = $null }
    }
    $output = @(& powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $diagnosticScript -RunnerRoot $RunnerRoot -ExpectedRunnerName $ExpectedRunnerName -AsJson 2>$null)
    $exitCode = $LASTEXITCODE
    $text = ($output -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return [pscustomobject]@{ valid = $false; exit_code = $exitCode; payload = $null }
    }
    try { $payload = $text | ConvertFrom-Json -ErrorAction Stop }
    catch { return [pscustomobject]@{ valid = $false; exit_code = $exitCode; payload = $null } }
    return [pscustomobject]@{ valid = ($null -ne $payload); exit_code = $exitCode; payload = $payload }
}

function Test-DiagnosticContract {
    param([Parameter(Mandatory = $true)][object]$Diagnostic)
    if (-not $Diagnostic.valid -or $null -eq $Diagnostic.payload) { return $false }
    $required = @(
        "healthy", "error_code", "runner_root_exists", "expected_runner_name",
        "runner_configuration_present", "runner_configuration_valid",
        "runner_configuration_error_detail", "runner_configuration_identity_matches",
        "runner_ephemeral", "run_command_present", "service_marker_present",
        "service_marker_valid", "service_marker_identity_matches",
        "service_query_succeeded", "service_identity_matches", "service_state",
        "service_start_mode"
    )
    foreach ($name in $required) {
        $matches = @($Diagnostic.payload.PSObject.Properties | Where-Object {
            [string]::Equals($_.Name, $name, [System.StringComparison]::OrdinalIgnoreCase)
        })
        if ($matches.Count -ne 1) { return $false }
    }
    $reportedName = Get-PropertyValueOrdinalIgnoreCase -InputObject $Diagnostic.payload -Name "expected_runner_name"
    return (
        $reportedName -is [string] -and
        [string]::Equals($reportedName, $ExpectedRunnerName, [System.StringComparison]::OrdinalIgnoreCase)
    )
}

function Test-RecoverableDiagnosticState {
    param(
        [Parameter(Mandatory = $true)][object]$Diagnostic,
        [Parameter(Mandatory = $true)][string]$DiagnosticErrorCode
    )
    if ($Diagnostic.exit_code -ne 2) { return $false }
    $p = $Diagnostic.payload
    $healthy = Get-PropertyValueOrdinalIgnoreCase $p "healthy"
    $rootExists = Get-PropertyValueOrdinalIgnoreCase $p "runner_root_exists"
    $configPresent = Get-PropertyValueOrdinalIgnoreCase $p "runner_configuration_present"
    $configValid = Get-PropertyValueOrdinalIgnoreCase $p "runner_configuration_valid"
    $configDetail = Get-PropertyValueOrdinalIgnoreCase $p "runner_configuration_error_detail"
    $identityMatches = Get-PropertyValueOrdinalIgnoreCase $p "runner_configuration_identity_matches"
    $ephemeral = Get-PropertyValueOrdinalIgnoreCase $p "runner_ephemeral"
    $runCommandPresent = Get-PropertyValueOrdinalIgnoreCase $p "run_command_present"
    $markerPresent = Get-PropertyValueOrdinalIgnoreCase $p "service_marker_present"
    $markerValid = Get-PropertyValueOrdinalIgnoreCase $p "service_marker_valid"
    $markerIdentityMatches = Get-PropertyValueOrdinalIgnoreCase $p "service_marker_identity_matches"
    $serviceQuerySucceeded = Get-PropertyValueOrdinalIgnoreCase $p "service_query_succeeded"
    $serviceIdentityMatches = Get-PropertyValueOrdinalIgnoreCase $p "service_identity_matches"
    $serviceState = Get-PropertyValueOrdinalIgnoreCase $p "service_state"
    $serviceStartMode = Get-PropertyValueOrdinalIgnoreCase $p "service_start_mode"
    $baseValid = (
        $healthy -eq $false -and $rootExists -eq $true -and $configPresent -eq $true -and
        $configValid -eq $true -and $null -eq $configDetail -and $identityMatches -eq $true -and
        $ephemeral -eq $false -and $runCommandPresent -eq $true -and $markerPresent -eq $true -and
        $markerValid -eq $true -and $markerIdentityMatches -eq $true -and
        $serviceQuerySucceeded -eq $true -and $serviceIdentityMatches -eq $true -and
        $serviceState -is [string] -and $serviceStartMode -is [string]
    )
    if (-not $baseValid) { return $false }
    if ($DiagnosticErrorCode -eq "RUNNER_SERVICE_NOT_AUTOMATIC") { return $serviceStartMode -ne "Auto" }
    if ($DiagnosticErrorCode -eq "RUNNER_SERVICE_NOT_RUNNING") { return ($serviceStartMode -eq "Auto" -and $serviceState -ne "Running") }
    return $false
}

function Test-OwnerAdministrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($env:OS -ne "Windows_NT") { Write-FailureAndExit "RUNNER_SERVICE_WINDOWS_REQUIRED" }

$diagnostic = Invoke-RunnerDiagnostic
if (-not (Test-DiagnosticContract $diagnostic)) { Write-FailureAndExit "RUNNER_RECOVERY_DIAGNOSTIC_INVALID" }
$diagnosticHealthy = Get-PropertyValueOrdinalIgnoreCase $diagnostic.payload "healthy"
$diagnosticErrorCode = Get-PropertyValueOrdinalIgnoreCase $diagnostic.payload "error_code"
$configDetail = Get-PropertyValueOrdinalIgnoreCase $diagnostic.payload "runner_configuration_error_detail"
$diagnosticState = Get-PropertyValueOrdinalIgnoreCase $diagnostic.payload "service_state"
$diagnosticMode = Get-PropertyValueOrdinalIgnoreCase $diagnostic.payload "service_start_mode"

if ($diagnostic.exit_code -eq 0 -and $diagnosticHealthy -eq $true) {
    Write-Result -Result (New-Result $true $null $null $null "NONE" $false $null $diagnosticState $diagnosticMode)
    exit 0
}

$recoverableDiagnosticCodes = @("RUNNER_SERVICE_NOT_AUTOMATIC", "RUNNER_SERVICE_NOT_RUNNING")
if ($diagnosticErrorCode -notin $recoverableDiagnosticCodes) {
    Write-FailureAndExit "RUNNER_RECOVERY_BLOCKED_BY_DIAGNOSTIC" $diagnosticErrorCode $configDetail $null $false $null $diagnosticState $diagnosticMode
}
if ($diagnosticErrorCode -isnot [string] -or -not (Test-RecoverableDiagnosticState $diagnostic $diagnosticErrorCode)) {
    Write-FailureAndExit "RUNNER_RECOVERY_DIAGNOSTIC_INVALID" $diagnosticErrorCode $configDetail $null $false $null $diagnosticState $diagnosticMode
}

$serviceFilePath = Join-Path $RunnerRoot ".service"
$expectedServiceSuffix = ".$ExpectedRunnerName"
$serviceNamePattern = '^actions\.runner\.[A-Za-z0-9._-]{1,65}$'
try {
    $expectedServiceExecutablePath = [System.IO.Path]::GetFullPath(
        (Join-Path $RunnerRoot "bin\RunnerService.exe")
    )
}
catch {
    Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_IDENTITY_MISMATCH" $diagnosticErrorCode
}
if (-not (Test-Path -LiteralPath $serviceFilePath -PathType Leaf)) {
    Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" $diagnosticErrorCode
}
try {
    $info = [System.IO.FileInfo]::new($serviceFilePath)
    $info.Refresh()
    if ($info.Length -le 0 -or $info.Length -gt 1024) { throw "bounded service marker required" }
    $declaredServiceName = [System.IO.File]::ReadAllText($serviceFilePath, [System.Text.Encoding]::UTF8).Trim()
}
catch { Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" $diagnosticErrorCode }

$markerValid = (
    $declaredServiceName.Length -le 80 -and
    $declaredServiceName -match $serviceNamePattern -and
    $declaredServiceName.EndsWith($expectedServiceSuffix, [System.StringComparison]::OrdinalIgnoreCase)
)
if (-not $markerValid) { Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_MARKER_CHANGED" $diagnosticErrorCode }

try {
    $matchingServices = @(Get-Service -ErrorAction Stop | Where-Object {
        [string]::Equals($_.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase)
    })
    $matchingServiceDetails = @(Get-CimInstance -ClassName Win32_Service -ErrorAction Stop | Where-Object {
        [string]::Equals($_.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase)
    })
}
catch { Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_QUERY_FAILED" $diagnosticErrorCode }
if ($matchingServices.Count -ne 1 -or $matchingServiceDetails.Count -ne 1) {
    Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_IDENTITY_AMBIGUOUS" $diagnosticErrorCode
}
$service = $matchingServices[0]
$serviceDetails = $matchingServiceDetails[0]
if (-not (
    [string]::Equals($service.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase) -and
    [string]::Equals($serviceDetails.Name, $declaredServiceName, [System.StringComparison]::OrdinalIgnoreCase) -and
    (Test-ServiceExecutablePathMatches -PathName $serviceDetails.PathName -ExpectedPath $expectedServiceExecutablePath)
)) { Write-FailureAndExit "RUNNER_RECOVERY_SERVICE_IDENTITY_MISMATCH" $diagnosticErrorCode }

$serviceState = [string]$serviceDetails.State
$serviceStartMode = [string]$serviceDetails.StartMode
$needsAutomatic = $serviceStartMode -ne "Auto"
$needsStart = $serviceState -ne "Running"
$recoveryAction = if ($needsAutomatic -and $needsStart) { "SET_AUTOMATIC_AND_START" } elseif ($needsAutomatic) { "SET_AUTOMATIC" } elseif ($needsStart) { "START" } else { "VERIFY_HEALTHY" }

if (-not $needsAutomatic -and -not $needsStart) {
    $post = Invoke-RunnerDiagnostic
    if ((Test-DiagnosticContract $post) -and $post.exit_code -eq 0 -and (Get-PropertyValueOrdinalIgnoreCase $post.payload "healthy") -eq $true) {
        Write-Result -Result (New-Result $true $null $null $null "NONE" $false $null "Running" "Auto")
        exit 0
    }
    Write-FailureAndExit "RUNNER_RECOVERY_STATE_CHANGED" $diagnosticErrorCode $null "VERIFY_HEALTHY" $false $null $serviceState $serviceStartMode
}

if (-not $Apply) { Write-FailureAndExit "RUNNER_SERVICE_RECOVERY_PREVIEW" $diagnosticErrorCode $null $recoveryAction $false $null $serviceState $serviceStartMode }
if (-not (Test-OwnerAdministrator)) { Write-FailureAndExit "RUNNER_SERVICE_RECOVERY_ADMIN_REQUIRED" $diagnosticErrorCode $null $recoveryAction $false $null $serviceState $serviceStartMode }

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
catch { Write-FailureAndExit "RUNNER_SERVICE_RECOVERY_MUTATION_FAILED" $diagnosticErrorCode $null $recoveryAction $mutationsAttempted $mutationStage $serviceState $serviceStartMode }

$post = Invoke-RunnerDiagnostic
if (-not (Test-DiagnosticContract $post)) { Write-FailureAndExit "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" $null $null $recoveryAction $mutationsAttempted $mutationStage }
$postHealthy = Get-PropertyValueOrdinalIgnoreCase $post.payload "healthy"
$postError = Get-PropertyValueOrdinalIgnoreCase $post.payload "error_code"
$postDetail = Get-PropertyValueOrdinalIgnoreCase $post.payload "runner_configuration_error_detail"
$postState = Get-PropertyValueOrdinalIgnoreCase $post.payload "service_state"
$postMode = Get-PropertyValueOrdinalIgnoreCase $post.payload "service_start_mode"
if ($post.exit_code -ne 0 -or $postHealthy -ne $true) {
    Write-FailureAndExit "RUNNER_SERVICE_RECOVERY_POSTCONDITION_FAILED" $postError $postDetail $recoveryAction $mutationsAttempted $mutationStage $postState $postMode
}
Write-Result -Result (New-Result $true $null $null $null $recoveryAction $mutationsAttempted $mutationStage $postState $postMode)
exit 0