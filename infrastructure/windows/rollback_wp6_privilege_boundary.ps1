param(
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeName = "omni-cio-runtime"
$executionName = "omni-cio-execution"
$runtimeMarker = "Omni-CIO V10 WP6 runtime role anchor; disabled until owning service bootstrap."
$executionMarker = "Omni-CIO V10 WP6 execution role anchor; disabled until owning service bootstrap."
$secretRoot = "C:\ProgramData\OmniCIO\secrets"
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

$runtimeRole = Get-OwnedRole -Name $runtimeName -Marker $runtimeMarker
$executionRole = Get-OwnedRole -Name $executionName -Marker $executionMarker

if (Test-Path -LiteralPath $sentinelPath) {
    Assert-Administrator
    $content = Get-Content -LiteralPath $sentinelPath -Raw -ErrorAction Stop
    if ($content.Trim() -ne $sentinelText) {
        throw "Refusing to remove unexpected content at the WP6 sentinel path."
    }
}

Write-Host "WP6 rollback preflight: PASS" -ForegroundColor Green
Write-Host "Only WP6-owned disabled role anchors and the fixed non-secret sentinel are eligible."

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply only if rollback is actually required." -ForegroundColor Yellow
    exit 0
}

Assert-Administrator

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

Write-Host "WP6-owned local privilege-boundary test state removed." -ForegroundColor Green
Write-Host "GitHub runner registration/service was not modified." -ForegroundColor Green
