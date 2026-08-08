[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$AsJson
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = "C:\ProgramData\OmniCIO"
$ownershipMarker = "OMNI-CIO-V10-WP7-NON-SECRET-OWNED-v1"
$ownershipMarkerName = ".omni-cio-wp7-owned"
$ownedPaths = @(
    Join-Path $root "services",
    Join-Path $root "logs",
    Join-Path $root "data",
    Join-Path $root "runtime",
    Join-Path $root "bootstrap"
)
$allowedFiles = @{
    (Join-Path $root "services") = @($ownershipMarkerName, "wp7-service-definitions.json")
    (Join-Path $root "logs") = @($ownershipMarkerName)
    (Join-Path $root "data") = @($ownershipMarkerName)
    (Join-Path $root "runtime") = @($ownershipMarkerName)
    (Join-Path $root "bootstrap") = @($ownershipMarkerName, "wp7-bootstrap-state.json")
}
$futureServiceNames = @(
    "OmniCIO.Core",
    "OmniCIO.WebApi",
    "OmniCIO.ResearchAI",
    "OmniCIO.Execution"
)

function Test-Administrator {
    if ($env:OS -ne "Windows_NT") {
        return $false
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Test-OwnedDirectory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    $marker = Join-Path $Path $ownershipMarkerName
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        return $false
    }
    try {
        return (Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim() -eq $ownershipMarker
    }
    catch {
        return $false
    }
}

function Get-CleanupState {
    $present = 0
    $unowned = @()
    $unexpected = @()

    foreach ($path in $ownedPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        $present += 1
        if (-not (Test-OwnedDirectory -Path $path)) {
            $unowned += [System.IO.Path]::GetFileName($path)
            continue
        }
        $allowed = @($allowedFiles[$path])
        $items = @(Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop)
        foreach ($item in $items) {
            if ($item.PSIsContainer -or $item.Name -notin $allowed) {
                $unexpected += "{0}:{1}" -f [System.IO.Path]::GetFileName($path), $item.Name
            }
        }
    }

    $activeFutureServices = @()
    if ($env:OS -eq "Windows_NT") {
        foreach ($serviceName in $futureServiceNames) {
            if ($null -ne (Get-Service -Name $serviceName -ErrorAction SilentlyContinue)) {
                $activeFutureServices += $serviceName
            }
        }
    }

    return [ordered]@{
        schema_version = "1"
        mode = if ($Apply) { "APPLY" } else { "PREVIEW" }
        owned_paths_present = $present
        unowned_paths = $unowned
        unexpected_entries = $unexpected
        future_services_present = $activeFutureServices.Count -gt 0
        safe_to_cleanup = (
            $unowned.Count -eq 0 -and
            $unexpected.Count -eq 0 -and
            $activeFutureServices.Count -eq 0
        )
        privacy = [ordered]@{
            raw_usernames_collected = $false
            sids_emitted = $false
            hostnames_collected = $false
            addresses_collected = $false
            secret_values_collected = $false
            runner_credentials_collected = $false
            private_data_collected = $false
        }
    }
}

function Write-State {
    param([hashtable]$State)

    if ($AsJson) {
        $State | ConvertTo-Json -Depth 6 -Compress
        return
    }
    Write-Host "WP7 cleanup mode: $($State.mode)"
    Write-Host "WP7 owned paths present: $($State.owned_paths_present)"
    Write-Host "Safe to cleanup: $($State.safe_to_cleanup)"
    if ($State.unowned_paths.Count -gt 0) {
        Write-Host "Unowned path blockers: $($State.unowned_paths -join ', ')"
    }
    if ($State.unexpected_entries.Count -gt 0) {
        Write-Host "Unexpected-entry blockers: $($State.unexpected_entries -join ', ')"
    }
    Write-Host "Future services present: $($State.future_services_present)"
    Write-Host "Prerequisites will be uninstalled: NO"
    Write-Host "WP6 identities/runner/secret boundary will be changed: NO"
}

$state = Get-CleanupState
Write-State -State $state

if (-not $Apply) {
    if ($state.safe_to_cleanup) { exit 0 }
    exit 2
}

if ($env:OS -ne "Windows_NT") {
    throw "WP7 cleanup mutation requires Windows."
}
if (-not (Test-Administrator)) {
    throw "WP7 cleanup -Apply requires an elevated OWNER-admin PowerShell."
}
if (-not $state.safe_to_cleanup) {
    throw "WP7 cleanup refused because state is unowned, already consumed, or future services exist."
}

foreach ($path in $ownedPaths) {
    if (-not (Test-Path -LiteralPath $path)) {
        continue
    }
    if (-not (Test-OwnedDirectory -Path $path)) {
        throw "WP7 cleanup ownership changed after preflight; refusing mutation."
    }
    $allowed = @($allowedFiles[$path])
    $items = @(Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop)
    foreach ($item in $items) {
        if ($item.PSIsContainer -or $item.Name -notin $allowed) {
            throw "WP7 cleanup state changed after preflight; refusing mutation."
        }
    }
    foreach ($item in $items) {
        Remove-Item -LiteralPath $item.FullName -Force -ErrorAction Stop
    }
    Remove-Item -LiteralPath $path -Force -ErrorAction Stop
}

$after = Get-CleanupState
if ($after.owned_paths_present -ne 0) {
    throw "WP7 cleanup did not converge to an empty WP7-owned state."
}
Write-Host "WP7 guarded cleanup applied: PASS" -ForegroundColor Green
Write-Host "Public prerequisites were left installed; WP6 and secret/runner boundaries were untouched."
exit 0
