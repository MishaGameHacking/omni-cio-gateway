param(
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeRoleName = "omni-cio-runtime"
$executionRoleName = "omni-cio-execution"
$secretSentinel = "C:\ProgramData\OmniCIO\secrets\execution\wp6-ci-deny-sentinel.txt"
$executionRoot = Split-Path -Parent $secretSentinel
$runnerRoot = "C:\actions-runner"
$runnerConfig = Join-Path $runnerRoot ".runner"
$runnerServiceMarker = Join-Path $runnerRoot ".service"
$runnerSensitiveNames = @(".runner", ".credentials", ".credentials_rsaparams", ".service")

function Get-AccountClass {
    param([string]$StartName)

    $normalized = $StartName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "LOCAL_SYSTEM"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") {
        return "NETWORK_SERVICE"
    }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") {
        return "LOCAL_SERVICE"
    }
    if ($normalized.StartsWith("NT SERVICE\")) {
        return "VIRTUAL_SERVICE"
    }
    return "LOCAL_OR_DOMAIN_USER"
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

function Get-LocalRoleState {
    param([string]$Name)

    try {
        $user = Get-LocalUser -Name $Name -ErrorAction Stop
    }
    catch {
        return [ordered]@{
            present = $false
            enabled = $null
            administrator = $null
            sid = $null
        }
    }

    $sid = $user.SID.Value
    $isAdmin = $false
    try {
        $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
        $members = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
        $isAdmin = [bool]($members | Where-Object { $_.SID.Value -eq $sid })
    }
    catch {
        $isAdmin = $null
    }

    return [ordered]@{
        present = $true
        enabled = [bool]$user.Enabled
        administrator = $isAdmin
        sid = $sid
    }
}

function Test-AclRule {
    param(
        [string]$Path,
        [string]$Sid,
        [int64]$Mask,
        [System.Security.AccessControl.AccessControlType]$ControlType
    )

    if (-not $Sid) {
        return $false
    }
    try {
        $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
        $rules = $acl.GetAccessRules(
            $true,
            $true,
            [System.Security.Principal.SecurityIdentifier]
        )
        foreach ($rule in $rules) {
            if ($rule.AccessControlType -ne $ControlType) {
                continue
            }
            $ruleSid = [string]$rule.IdentityReference.Value
            if ($ruleSid -eq $Sid -and (([int64]$rule.FileSystemRights -band $Mask) -ne 0)) {
                return $true
            }
        }
    }
    catch {
        return $false
    }
    return $false
}

function Test-AclAllow {
    param(
        [string]$Path,
        [string]$Sid,
        [int64]$Mask
    )

    return Test-AclRule `
        -Path $Path `
        -Sid $Sid `
        -Mask $Mask `
        -ControlType ([System.Security.AccessControl.AccessControlType]::Allow)
}

function Test-AclDeny {
    param(
        [string]$Path,
        [string]$Sid,
        [int64]$Mask
    )

    return Test-AclRule `
        -Path $Path `
        -Sid $Sid `
        -Mask $Mask `
        -ControlType ([System.Security.AccessControl.AccessControlType]::Deny)
}

function Test-BroadAclAllow {
    param(
        [string]$Path,
        [int64]$Mask
    )

    $broadSids = @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")
    foreach ($sid in $broadSids) {
        if (Test-AclAllow -Path $Path -Sid $sid -Mask $Mask) {
            return $true
        }
    }
    return $false
}

function Get-RunnerSensitivePaths {
    return @(
        foreach ($name in $runnerSensitiveNames) {
            $path = Join-Path $runnerRoot $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $path
            }
        }
    )
}

function Get-RunnerServiceSafe {
    if (-not (Test-Path -LiteralPath $runnerServiceMarker -PathType Leaf)) {
        throw "Fail-closed: reviewed runner root has no .service ownership marker."
    }
    $serviceName = (Get-Content -LiteralPath $runnerServiceMarker -Raw -ErrorAction Stop).Trim()
    if (-not $serviceName.StartsWith("actions.runner.", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Fail-closed: reviewed runner .service marker is not a GitHub Actions runner service."
    }
    $services = @(
        Get-CimInstance Win32_Service |
            Where-Object { $_.Name -eq $serviceName }
    )
    if ($services.Count -ne 1) {
        throw "Expected exactly one GitHub Actions runner service bound to the reviewed runner root; found $($services.Count)."
    }
    return $services[0]
}

$runnerService = Get-RunnerServiceSafe
$runnerClass = Get-AccountClass -StartName $runnerService.StartName
$runnerSid = Get-AccountSidValue -AccountName $runnerService.StartName
$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$currentSid = $currentIdentity.User.Value
$currentPrincipal = [System.Security.Principal.WindowsPrincipal]::new($currentIdentity)
$currentTokenAdmin = $currentPrincipal.IsInRole(
    [System.Security.Principal.WindowsBuiltInRole]::Administrator
)

$runnerAdmin = $null
if ($runnerClass -eq "LOCAL_SYSTEM") {
    $runnerAdmin = $true
}
elseif ($runnerClass -in @("NETWORK_SERVICE", "LOCAL_SERVICE", "VIRTUAL_SERVICE")) {
    $runnerAdmin = $false
}
elseif ($runnerSid) {
    try {
        $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
        $adminMembers = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
        $runnerAdmin = [bool]($adminMembers | Where-Object { $_.SID.Value -eq $runnerSid })
    }
    catch {
        $runnerAdmin = $null
    }
}

$interactiveDistinct = $null
try {
    $interactiveName = (Get-CimInstance Win32_ComputerSystem).UserName
    if ($interactiveName) {
        $interactiveSid = Get-AccountSidValue -AccountName $interactiveName
        if ($interactiveSid -and $runnerSid) {
            $interactiveDistinct = ($interactiveSid -ne $runnerSid)
        }
    }
}
catch {
    $interactiveDistinct = $null
}

$runtimeState = Get-LocalRoleState -Name $runtimeRoleName
$executionState = Get-LocalRoleState -Name $executionRoleName

$sentinelReadResult = "NOT_CONFIGURED"
$sentinelKnownPresent = $false
try {
    $stream = [System.IO.File]::Open(
        $secretSentinel,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        [System.IO.FileShare]::ReadWrite
    )
    $stream.Dispose()
    $sentinelKnownPresent = $true
    $sentinelReadResult = "ACCESS_GRANTED"
}
catch [System.UnauthorizedAccessException] {
    $sentinelKnownPresent = $true
    $sentinelReadResult = "ACCESS_DENIED"
}
catch [System.IO.FileNotFoundException] {
    $sentinelReadResult = "NOT_CONFIGURED"
}
catch [System.IO.DirectoryNotFoundException] {
    $sentinelReadResult = "NOT_CONFIGURED"
}
catch {
    $sentinelReadResult = "ERROR"
}

$readMask = [int64][System.Security.AccessControl.FileSystemRights]::Read
$writeMask = (
    [int64][System.Security.AccessControl.FileSystemRights]::Write -bor
    [int64][System.Security.AccessControl.FileSystemRights]::Modify -bor
    [int64][System.Security.AccessControl.FileSystemRights]::Delete -bor
    [int64][System.Security.AccessControl.FileSystemRights]::FullControl
)

$runtimeSid = $runtimeState.sid
$executionSid = $executionState.sid
$runtimeSecretReadGrant = $false
$executionSecretReadGrant = $false
$secretBroadReadExposure = $false
if ($sentinelKnownPresent) {
    $runtimeSecretReadGrant = Test-AclAllow -Path $secretSentinel -Sid $runtimeSid -Mask $readMask
    $executionSecretReadGrant = Test-AclAllow -Path $secretSentinel -Sid $executionSid -Mask $readMask
    $secretBroadReadExposure = Test-BroadAclAllow -Path $secretSentinel -Mask $readMask
}

$executionDirectoryReadGrant = Test-AclAllow -Path $executionRoot -Sid $executionSid -Mask $readMask
$executionSentinelAnyAllow = Test-AclAllow `
    -Path $secretSentinel `
    -Sid $executionSid `
    -Mask ([int64][System.Security.AccessControl.FileSystemRights]::FullControl)
Write-Host "WP6 ACL diagnostic: execution-directory-read-grant=$executionDirectoryReadGrant"
Write-Host "WP6 ACL diagnostic: execution-sentinel-any-allow=$executionSentinelAnyAllow"

$runtimeRunnerRootDeny = Test-AclDeny -Path $runnerRoot -Sid $runtimeSid -Mask $writeMask
$executionRunnerRootDeny = Test-AclDeny -Path $runnerRoot -Sid $executionSid -Mask $writeMask

$runnerSensitivePaths = @(Get-RunnerSensitivePaths)
$runtimeRunnerWriteGrant = $false
$runnerConfigBroadWriteExposure = $null
if ($runnerSensitivePaths.Count -gt 0) {
    $runtimeRunnerWriteGrant = [bool](
        $runnerSensitivePaths |
            Where-Object { Test-AclAllow -Path $_ -Sid $runtimeSid -Mask $writeMask } |
            Select-Object -First 1
    )
    $runnerConfigBroadWriteExposure = [bool](
        $runnerSensitivePaths |
            Where-Object { Test-BroadAclAllow -Path $_ -Mask $writeMask } |
            Select-Object -First 1
    )
}

$profile = [ordered]@{
    schema_version = "1"
    capture_mode = "PASSIVE"
    runner = [ordered]@{
        service_running = ($runnerService.State -eq "Running")
        service_start_mode = [string]$runnerService.StartMode
        account_class = $runnerClass
        administrator = $runnerAdmin
        service_identity_matches_current_process = if ($runnerSid) { $runnerSid -eq $currentSid } else { $null }
        current_process_administrator = [bool]$currentTokenAdmin
        distinct_from_interactive_owner = $interactiveDistinct
    }
    runtime = [ordered]@{
        identity_present = [bool]$runtimeState.present
        identity_enabled = $runtimeState.enabled
        administrator = $runtimeState.administrator
        execution_secret_direct_read_grant = [bool]$runtimeSecretReadGrant
        runner_config_direct_write_grant = [bool]$runtimeRunnerWriteGrant
        runner_root_deny_present = [bool]$runtimeRunnerRootDeny
    }
    execution = [ordered]@{
        identity_present = [bool]$executionState.present
        identity_enabled = $executionState.enabled
        administrator = $executionState.administrator
        execution_secret_direct_read_grant = [bool]$executionSecretReadGrant
        runner_root_deny_present = [bool]$executionRunnerRootDeny
    }
    boundaries = [ordered]@{
        execution_secret_sentinel_present = $sentinelKnownPresent
        runner_execution_secret_read = $sentinelReadResult
        execution_secret_broad_read_exposure = [bool]$secretBroadReadExposure
        runner_config_present = (Test-Path -LiteralPath $runnerConfig)
        runner_config_broad_write_exposure = $runnerConfigBroadWriteExposure
    }
    privacy = [ordered]@{
        raw_usernames_collected = $false
        sids_emitted = $false
        hostnames_collected = $false
        addresses_collected = $false
        secret_values_collected = $false
        process_lists_collected = $false
    }
}

$profileJson = $profile | ConvertTo-Json -Depth 8

if ($OutputPath) {
    $parent = Split-Path -Parent $OutputPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    Set-Content -LiteralPath $OutputPath -Value $profileJson -Encoding UTF8
}

$profileJson