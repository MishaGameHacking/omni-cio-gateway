[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1") {
    throw "Unsupported WP8 secret-store contract schema."
}

$secretRoot = [string]$contract.paths.secret_root
$evidenceRoot = [string]$contract.paths.evidence_root
$wp6Sentinel = [string]$contract.paths.wp6_execution_sentinel
$statePath = Join-Path $evidenceRoot "wp8-secret-store-state.json"
$ownershipMarkerName = ".omni-cio-wp8-owned"
$ownershipMarkerValue = "OMNI-CIO-V10-WP8-NON-SECRET-OWNED-v1"

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

function Get-SanitizedState {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return $null
    }
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $null
    }
    if ([string]$state.schema_version -ne "1") {
        return $null
    }
    return $state
}

function Test-OwnedDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $markerPath = Join-Path $Path $ownershipMarkerName
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $true
    }
    if (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        return $false
    }
    try {
        return (Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop) -eq $ownershipMarkerValue
    }
    catch {
        return $false
    }
}

function Get-RollbackProfile {
    $reasons = New-Object System.Collections.Generic.List[string]
    $state = Get-SanitizedState
    $stateReady = $null -ne $state
    if (-not $stateReady -and (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
        [void]$reasons.Add("WP8_STATE_NOT_READABLE")
    }

    $realSecretProvisioned = $false
    if ($stateReady) {
        foreach ($entry in @($state.classes)) {
            if ([bool]$entry.provisioned) {
                $realSecretProvisioned = $true
                [void]$reasons.Add("REAL_SECRET_PROVISIONED:$([string]$entry.secret_class)")
            }
        }
    }

    $activeBlobPresent = $false
    $ownedDirectories = $true
    foreach ($spec in @($contract.secret_classes)) {
        $directory = [string]$spec.directory
        $activePath = Join-Path $directory ([string]$spec.active_blob)
        if (Test-Path -LiteralPath $activePath -PathType Leaf) {
            $activeBlobPresent = $true
            [void]$reasons.Add("ACTIVE_SECRET_BLOB_PRESENT:$([string]$spec.id)")
        }
        if (-not (Test-OwnedDirectory -Path $directory)) {
            $ownedDirectories = $false
            [void]$reasons.Add("UNOWNED_CLASS_DIRECTORY:$([string]$spec.id)")
        }
    }

    $wp6SentinelPreserved = Test-Path -LiteralPath $wp6Sentinel -PathType Leaf
    if (-not $wp6SentinelPreserved) {
        [void]$reasons.Add("WP6_SENTINEL_NOT_PRESENT")
    }

    $safe = (
        -not $realSecretProvisioned -and
        -not $activeBlobPresent -and
        $ownedDirectories -and
        $wp6SentinelPreserved
    )
    return [ordered]@{
        schema_version = "1"
        mode = if ($Apply) { "APPLY" } else { "PREVIEW" }
        safe_to_cleanup = [bool]$safe
        reasons = @($reasons)
        real_secret_provisioned = [bool]$realSecretProvisioned
        active_secret_blob_present = [bool]$activeBlobPresent
        owned_directories = [bool]$ownedDirectories
        wp6_execution_sentinel_preserved = [bool]$wp6SentinelPreserved
        secret_root_will_be_removed = $false
        wp6_identities_will_be_changed = $false
        wp7_prerequisites_will_be_changed = $false
        real_secret_values_collected = $false
    }
}

function Write-Profile {
    param([Parameter(Mandatory = $true)]$Profile)

    if ($AsJson) {
        $Profile | ConvertTo-Json -Depth 6 -Compress
        return
    }
    Write-Host "WP8 rollback mode: $($Profile.mode)"
    Write-Host "Safe to cleanup: $($Profile.safe_to_cleanup)"
    Write-Host "Real secret provisioned: $($Profile.real_secret_provisioned)"
    Write-Host "Active secret blob present: $($Profile.active_secret_blob_present)"
    Write-Host "WP6 execution sentinel preserved: $($Profile.wp6_execution_sentinel_preserved)"
    Write-Host "WP6 secret root will be removed: NO"
    Write-Host "WP6 identities/runner boundary will be changed: NO"
    Write-Host "WP7 prerequisites/directories will be changed: NO"
    Write-Host "Real secret values collected: NO"
    if (@($Profile.reasons).Count -gt 0) {
        Write-Host "Reason codes: $(@($Profile.reasons) -join ', ')"
    }
}

$profile = Get-RollbackProfile
if (-not $Apply) {
    Write-Profile -Profile $profile
    exit 0
}

if (-not (Test-Administrator)) {
    throw "WP8 rollback -Apply requires an elevated OWNER-admin PowerShell."
}
if (-not $profile.safe_to_cleanup) {
    Write-Profile -Profile $profile
    throw "WP8 rollback refused because cleanup cannot be proven safe."
}

foreach ($spec in @($contract.secret_classes)) {
    $directory = [string]$spec.directory
    if (Test-Path -LiteralPath $directory -PathType Container) {
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
}
if (Test-Path -LiteralPath $evidenceRoot -PathType Container) {
    Remove-Item -LiteralPath $evidenceRoot -Recurse -Force
}

if (-not (Test-Path -LiteralPath $secretRoot -PathType Container)) {
    throw "WP8 rollback unexpectedly removed the WP6 secret root."
}
if (-not (Test-Path -LiteralPath $wp6Sentinel -PathType Leaf)) {
    throw "WP8 rollback unexpectedly removed the WP6 execution sentinel."
}

$after = Get-RollbackProfile
Write-Profile -Profile $after
exit 0
