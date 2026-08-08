[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1") {
    throw "Unsupported WP8 secret-store contract schema."
}

$runtimeName = [string]$contract.identities.runtime_role
$executionName = [string]$contract.identities.execution_role
$runnerRoot = "C:\actions-runner"
$statePath = Join-Path ([string]$contract.paths.evidence_root) "wp8-secret-store-state.json"

function Get-LocalRoleState {
    param([Parameter(Mandatory = $true)][string]$Name)

    try {
        $role = Get-LocalUser -Name $Name -ErrorAction Stop
    }
    catch {
        return [ordered]@{ present = $false; enabled = $null; administrator = $null; sid = $null }
    }
    $isAdmin = $null
    try {
        $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
        $members = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
        $isAdmin = [bool]($members | Where-Object { $_.SID.Value -eq $role.SID.Value })
    }
    catch {
        $isAdmin = $null
    }
    return [ordered]@{
        present = $true
        enabled = [bool]$role.Enabled
        administrator = $isAdmin
        sid = $role.SID
    }
}

function Get-RunnerServiceSid {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $pathName = [string]$_.PathName
                $_.Name -match '^actions\.runner\.' -and
                -not [string]::IsNullOrWhiteSpace($pathName) -and
                $pathName.IndexOf($runnerRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            }
    )
    if ($services.Count -ne 1) { throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE" }
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
}

function Get-RulesOrNull {
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
        return @($acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
    }
    catch {
        return $null
    }
}

function Test-AllowRight {
    param($Rules, $Sid, [System.Security.AccessControl.FileSystemRights]$Right)
    if ($null -eq $Rules -or $null -eq $Sid) { return $false }
    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -eq $Sid.Value -and
            (($rule.FileSystemRights -band $Right) -eq $Right)
        ) { return $true }
    }
    return $false
}

function Test-AnyAllowMask {
    param($Rules, $Sid, [System.Security.AccessControl.FileSystemRights]$Mask)
    if ($null -eq $Rules -or $null -eq $Sid) { return $false }
    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -eq $Sid.Value -and
            (($rule.FileSystemRights -band $Mask) -ne 0)
        ) { return $true }
    }
    return $false
}

function Test-BroadReadExposure {
    param($Rules)
    if ($null -eq $Rules) { return $false }
    foreach ($rule in @($Rules)) {
        if (
            $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            $rule.IdentityReference.Value -in @("S-1-1-0", "S-1-5-11", "S-1-5-32-545") -and
            (($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0)
        ) { return $true }
    }
    return $false
}

function Test-DataReadAttempt {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        $stream.Dispose()
        return "UNEXPECTED_READ_ALLOWED"
    }
    catch [System.UnauthorizedAccessException] { return "ACCESS_DENIED" }
    catch { return "READ_ERROR" }
}

$reasons = New-Object System.Collections.Generic.List[string]
$runtimeState = Get-LocalRoleState -Name $runtimeName
$executionState = Get-LocalRoleState -Name $executionName
if (-not $runtimeState.present -or $runtimeState.enabled -ne $false -or $runtimeState.administrator -ne $false) {
    [void]$reasons.Add("WP6_RUNTIME_ROLE_NOT_READY")
}
if (-not $executionState.present -or $executionState.enabled -ne $false -or $executionState.administrator -ne $false) {
    [void]$reasons.Add("WP6_EXECUTION_ROLE_NOT_READY")
}

$runnerSid = $null
try { $runnerSid = Get-RunnerServiceSid } catch { [void]$reasons.Add("RUNNER_SERVICE_IDENTITY_UNAVAILABLE") }
$runnerProcess = $false
if ($null -ne $runnerSid) {
    try {
        $runnerProcess = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value -eq $runnerSid.Value
    }
    catch { $runnerProcess = $false }
}
if (-not $runnerProcess) { [void]$reasons.Add("AUTHORITATIVE_RUNNER_PROCESS_NOT_PROVEN") }

$stateClasses = @{}
$rotationRead = $false
$rotationTelegram = $false
$realSecretValuesUsed = $false
try {
    $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    if ([string]$state.schema_version -ne "1") { throw "schema" }
    $rotationRead = [bool]$state.rotation_rehearsal.broker_read
    $rotationTelegram = [bool]$state.rotation_rehearsal.telegram_bot
    $realSecretValuesUsed = [bool]$state.real_secret_values_used_for_wp8_acceptance
    foreach ($entry in @($state.classes)) { $stateClasses[[string]$entry.secret_class] = $entry }
}
catch {
    [void]$reasons.Add("WP8_SANITIZED_STATE_NOT_READY")
}
if (-not $rotationRead) { [void]$reasons.Add("BROKER_READ_ROTATION_REHEARSAL_NOT_PROVEN") }
if (-not $rotationTelegram) { [void]$reasons.Add("TELEGRAM_ROTATION_REHEARSAL_NOT_PROVEN") }
if ($realSecretValuesUsed) { [void]$reasons.Add("REAL_SECRET_VALUE_USED_IN_WP8_ACCEPTANCE") }

$writeMask = (
    [System.Security.AccessControl.FileSystemRights]::WriteData -bor
    [System.Security.AccessControl.FileSystemRights]::AppendData -bor
    [System.Security.AccessControl.FileSystemRights]::WriteAttributes -bor
    [System.Security.AccessControl.FileSystemRights]::WriteExtendedAttributes -bor
    [System.Security.AccessControl.FileSystemRights]::Delete -bor
    [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
    [System.Security.AccessControl.FileSystemRights]::TakeOwnership
)

$classProfiles = @(
    foreach ($spec in @($contract.secret_classes)) {
        $id = [string]$spec.id
        $directory = [string]$spec.directory
        $sentinel = Join-Path $directory ([string]$spec.sentinel_blob)
        $directoryRules = Get-RulesOrNull -Path $directory
        $rules = Get-RulesOrNull -Path $sentinel
        $directoryPresent = $null -ne $directoryRules
        $sentinelPresent = $null -ne $rules
        $runtimeReadGrant = Test-AllowRight -Rules $rules -Sid $runtimeState.sid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
        $executionReadGrant = Test-AllowRight -Rules $rules -Sid $executionState.sid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
        $runnerReadDataGrant = Test-AllowRight -Rules $rules -Sid $runnerSid -Right ([System.Security.AccessControl.FileSystemRights]::ReadData)
        $runnerWriteGrant = Test-AnyAllowMask -Rules $rules -Sid $runnerSid -Mask $writeMask
        $broadReadExposure = Test-BroadReadExposure -Rules $rules
        $intendedReadGrant = $false
        if ([string]$spec.consumer_role -eq $runtimeName) {
            $intendedReadGrant = $runtimeReadGrant -and -not $executionReadGrant
        }
        elseif ([string]$spec.consumer_role -eq $executionName) {
            $intendedReadGrant = $executionReadGrant -and -not $runtimeReadGrant
        }
        else {
            $intendedReadGrant = -not $runtimeReadGrant -and -not $executionReadGrant
        }
        $runnerDataRead = if ($sentinelPresent -and $runnerProcess) {
            Test-DataReadAttempt -Path $sentinel
        } else {
            "NOT_TESTED"
        }

        if (-not $directoryPresent) { [void]$reasons.Add("WP8_CLASS_DIRECTORY_NOT_READY:$id") }
        if (-not $sentinelPresent) { [void]$reasons.Add("WP8_SENTINEL_NOT_READY:$id") }
        if (-not $intendedReadGrant) { [void]$reasons.Add("WP8_INTENDED_SECRET_GRANT_INVALID:$id") }
        if ($runnerReadDataGrant) { [void]$reasons.Add("CI_RUNNER_SECRET_READ_GRANT_PRESENT:$id") }
        if ($runnerWriteGrant) { [void]$reasons.Add("CI_RUNNER_SECRET_WRITE_GRANT_PRESENT:$id") }
        if ($broadReadExposure) { [void]$reasons.Add("BROAD_SECRET_READ_EXPOSURE:$id") }
        if ($runnerProcess -and $sentinelPresent -and $runnerDataRead -ne "ACCESS_DENIED") {
            [void]$reasons.Add("CI_RUNNER_SECRET_DATA_READ_NOT_DENIED:$id")
        }

        $lifecycleState = "UNKNOWN"
        $lifecycleVersion = -1
        $provisioned = $null
        if ($stateClasses.ContainsKey($id)) {
            $entry = $stateClasses[$id]
            $lifecycleState = [string]$entry.state
            $lifecycleVersion = [int]$entry.version
            $provisioned = [bool]$entry.provisioned
            if ($provisioned) { [void]$reasons.Add("REAL_SECRET_ALREADY_PROVISIONED_DURING_WP8_ACCEPTANCE:$id") }
        }
        else { [void]$reasons.Add("WP8_LIFECYCLE_METADATA_NOT_READY:$id") }

        [ordered]@{
            secret_class = $id
            directory_present = [bool]$directoryPresent
            sentinel_present = [bool]$sentinelPresent
            intended_read_grant = [bool]$intendedReadGrant
            runtime_read_grant = [bool]$runtimeReadGrant
            execution_read_grant = [bool]$executionReadGrant
            runner_read_data_grant = [bool]$runnerReadDataGrant
            runner_write_grant = [bool]$runnerWriteGrant
            broad_read_exposure = [bool]$broadReadExposure
            runner_data_read = $runnerDataRead
            lifecycle_state = $lifecycleState
            lifecycle_version = $lifecycleVersion
            real_secret_provisioned = $provisioned
        }
    }
)

$status = if ($reasons.Count -eq 0) { "PASS" } else { "FAIL" }
$profile = [ordered]@{
    schema_version = "1"
    mode = "AUDIT"
    status = $status
    reasons = @($reasons)
    provider = "WINDOWS_DPAPI_LOCAL_MACHINE_PLUS_PROTECTED_DACL"
    runner_process = [bool]$runnerProcess
    runtime_role = [ordered]@{ present = [bool]$runtimeState.present; enabled = $runtimeState.enabled; administrator = $runtimeState.administrator }
    execution_role = [ordered]@{ present = [bool]$executionState.present; enabled = $executionState.enabled; administrator = $executionState.administrator }
    rotation_rehearsal = [ordered]@{ broker_read = [bool]$rotationRead; telegram_bot = [bool]$rotationTelegram }
    classes = $classProfiles
    real_secret_values_used = [bool]$realSecretValuesUsed
    privacy = [ordered]@{
        raw_usernames_collected = $false
        sids_emitted = $false
        hostnames_collected = $false
        addresses_collected = $false
        secret_values_collected = $false
        secret_hashes_collected = $false
        ciphertext_collected = $false
        account_ids_collected = $false
        private_data_collected = $false
        process_dumps_collected = $false
    }
}

if ($AsJson) {
    $profile | ConvertTo-Json -Depth 10 -Compress
}
else {
    Write-Host "WP8 local secret-store audit status: $($profile.status)"
    Write-Host "Runner process: $($profile.runner_process)"
    foreach ($item in @($profile.classes)) {
        Write-Host ("Class {0}: intended-read={1}; runner-read={2}; runner-write={3}; runner-data={4}" -f $item.secret_class, $item.intended_read_grant, $item.runner_read_data_grant, $item.runner_write_grant, $item.runner_data_read)
    }
    Write-Host "Real secret values used: NO"
    if (@($profile.reasons).Count -gt 0) { Write-Host "Reason codes: $(@($profile.reasons) -join ', ')" }
}
exit 0
