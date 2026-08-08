param(
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeName = "omni-cio-runtime"
$executionName = "omni-cio-execution"
$runtimeMarker = "Omni-CIO V10 WP6 runtime role anchor; disabled until owning service bootstrap."
$executionMarker = "Omni-CIO V10 WP6 execution role anchor; disabled until owning service bootstrap."
$omniRoot = "C:\ProgramData\OmniCIO"
$wp6StateRoot = Join-Path $omniRoot "wp6"
$runnerAclBackupPath = Join-Path $wp6StateRoot "runner-config-acl-backup.json"
$runnerRoot = "C:\actions-runner"
$allowedRunnerNames = @(".runner", ".credentials", ".credentials_rsaparams", ".service")
$secretRoot = Join-Path $omniRoot "secrets"
$executionRoot = Join-Path $secretRoot "execution"
$sentinelPath = Join-Path $executionRoot "wp6-ci-deny-sentinel.txt"
$sentinelText = "OMNI-CIO-WP6-NON-SECRET-ACL-SENTINEL-v1"

function Assert-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "WP6 rollback requires an elevated OWNER-admin PowerShell."
    }
}

function Get-OwnedRole {
    param(
        [string]$Name,
        [string]$Marker
    )
    try {
        $user = Get-LocalUser -Name $Name -ErrorAction Stop
    }
    catch {
        return $null
    }
    if ($user.Description -ne $Marker) {
        throw "Refusing to remove pre-existing account '$Name' without the WP6 ownership marker."
    }
    if ($user.Enabled) {
        throw "Refusing to remove enabled role account '$Name'. Disable/review it first."
    }
    return $user
}

function Get-AclBackup {
    if (-not (Test-Path -LiteralPath $runnerAclBackupPath)) {
        return $null
    }
    try {
        $backup = Get-Content -LiteralPath $runnerAclBackupPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "WP6 runner ACL backup is malformed; refusing rollback."
    }
    if ($backup.schema_version -ne "1") {
        throw "Unexpected WP6 runner ACL backup schema."
    }
    foreach ($entry in @($backup.files)) {
        if ($entry.name -notin $allowedRunnerNames) {
            throw "Runner ACL backup contains an unexpected path name; refusing rollback."
        }
        if (-not $entry.sddl) {
            throw "Runner ACL backup contains an empty security descriptor."
        }
    }
    return $backup
}

function Restore-RunnerAclBackup {
    param($Backup)

    if ($null -eq $Backup) {
        return
    }
    foreach ($entry in @($Backup.files)) {
        $path = Join-Path $runnerRoot $entry.name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Reviewed runner config file '$($entry.name)' is missing; refusing partial ACL rollback."
        }
        $acl = [System.Security.AccessControl.FileSecurity]::new()
        $acl.SetSecurityDescriptorSddlForm([string]$entry.sddl)
        Set-Acl -LiteralPath $path -AclObject $acl
    }
}

$runtimeRole = Get-OwnedRole -Name $runtimeName -Marker $runtimeMarker
$executionRole = Get-OwnedRole -Name $executionName -Marker $executionMarker
$aclBackup = Get-AclBackup

if (Test-Path -LiteralPath $sentinelPath) {
    Assert-Administrator
    $content = Get-Content -LiteralPath $sentinelPath -Raw -ErrorAction Stop
    if ($content.Trim() -ne $sentinelText) {
        throw "Refusing to remove unexpected content at the WP6 sentinel path."
    }
}

Write-Host "WP6 rollback preflight: PASS" -ForegroundColor Green
Write-Host "Only WP6-owned disabled role anchors, fixed non-secret sentinel and locally backed-up runner ACLs are eligible."
Write-Host "Runner ACL backup present: $($null -ne $aclBackup)"

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply only if rollback is actually required." -ForegroundColor Yellow
    exit 0
}

Assert-Administrator
Restore-RunnerAclBackup -Backup $aclBackup

if (Test-Path -LiteralPath $sentinelPath) {
    Remove-Item -LiteralPath $sentinelPath -Force
}
if (Test-Path -LiteralPath $executionRoot) {
    $remaining = @(Get-ChildItem -LiteralPath $executionRoot -Force -ErrorAction Stop)
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $executionRoot -Force
    }
    else {
        throw "Execution directory contains non-WP6 material; refusing to remove it."
    }
}
if (Test-Path -LiteralPath $secretRoot) {
    $remaining = @(Get-ChildItem -LiteralPath $secretRoot -Force -ErrorAction Stop)
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $secretRoot -Force
    }
}

if ($null -ne $runtimeRole) {
    Remove-LocalUser -Name $runtimeName
}
if ($null -ne $executionRole) {
    Remove-LocalUser -Name $executionName
}

if (Test-Path -LiteralPath $runnerAclBackupPath) {
    Remove-Item -LiteralPath $runnerAclBackupPath -Force
}
if (Test-Path -LiteralPath $wp6StateRoot) {
    $remaining = @(Get-ChildItem -LiteralPath $wp6StateRoot -Force -ErrorAction Stop)
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $wp6StateRoot -Force
    }
}

Write-Host "WP6-owned local privilege-boundary test state removed." -ForegroundColor Green
Write-Host "Original reviewed runner config ACLs restored from local backup when available." -ForegroundColor Green
Write-Host "GitHub runner registration/service account was not modified." -ForegroundColor Green
