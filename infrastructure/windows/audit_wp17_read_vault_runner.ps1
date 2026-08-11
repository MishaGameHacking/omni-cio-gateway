[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisionerPath = Join-Path $PSScriptRoot "provision_wp17_web_read_vault.ps1"
$finalizerPath = Join-Path $PSScriptRoot "finalize_wp17_web_read_vault_evidence.ps1"
$wp8ContractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$evidenceRoot = "C:\ProgramData\OmniCIO\wp17"
$evidencePath = Join-Path $evidenceRoot "owner-read-vault-evidence.sanitized.local.json"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-ReadDataDenied {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::ReadWrite
        )
        return $false
    }
    catch [System.UnauthorizedAccessException] {
        return $true
    }
    catch [System.Security.SecurityException] {
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Test-CreateDenied {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $probe = Join-Path $Directory ("wp17-runner-write-probe-" + [guid]::NewGuid().ToString("N") + ".tmp")
    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            $probe,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        return $false
    }
    catch [System.UnauthorizedAccessException] {
        return $true
    }
    catch [System.Security.SecurityException] {
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if (Test-Path -LiteralPath $probe -PathType Leaf) {
            try { Remove-Item -LiteralPath $probe -Force -ErrorAction Stop } catch { }
        }
    }
}

$expectedSha = $ExpectedImplementationSha.Trim().ToLowerInvariant()
$expectedShaValid = $expectedSha -match '^[0-9a-f]{40}$'
$runnerIsAdmin = Test-Administrator
$evidencePresent = Test-Path -LiteralPath $evidencePath -PathType Leaf
$evidence = $null
$evidenceReadable = $false

if ($evidencePresent) {
    try {
        $evidence = Get-Content -LiteralPath $evidencePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $evidenceReadable = $true
    }
    catch {
        $evidence = $null
    }
}

$provisionerHash = if (Test-Path -LiteralPath $provisionerPath -PathType Leaf) {
    (Get-FileHash -LiteralPath $provisionerPath -Algorithm SHA256).Hash.ToLowerInvariant()
} else { "" }
$finalizerHash = if (Test-Path -LiteralPath $finalizerPath -PathType Leaf) {
    (Get-FileHash -LiteralPath $finalizerPath -Algorithm SHA256).Hash.ToLowerInvariant()
} else { "" }
$auditorHash = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()

$implementationBound = $false
$scriptHashesBound = $false
$ownerEvidenceReady = $false
$secretReadDenied = $false
$secretWriteDenied = $false
$evidenceWriteDenied = $false

if ($expectedShaValid -and $evidenceReadable -and $null -ne $evidence) {
    $implementationBound = ([string]$evidence.implementation_sha).ToLowerInvariant() -eq $expectedSha
    $scriptHashesBound = (
        ([string]$evidence.provisioner_sha256).ToLowerInvariant() -eq $provisionerHash -and
        ([string]$evidence.evidence_finalizer_sha256).ToLowerInvariant() -eq $finalizerHash
    )
    $ownerEvidenceReady = (
        [bool]$evidence.ready -and
        [bool]$evidence.owner_verify_ready -and
        [bool]$evidence.read_connection_vault_present -and
        [bool]$evidence.ownership_marker_ok -and
        [bool]$evidence.runtime_modify_read_child -and
        (-not [bool]$evidence.runner_read_data_allowed) -and
        (-not [bool]$evidence.runner_write_allowed) -and
        (-not [bool]$evidence.broad_read_principal_present) -and
        [bool]$evidence.broker_trading_acl_unchanged -and
        [bool]$evidence.evidence_acl_protected -and
        (-not [bool]$evidence.runner_evidence_write_allowed) -and
        (-not [bool]$evidence.real_secret_values_used) -and
        (-not [bool]$evidence.broker_write_authority_added) -and
        (-not [bool]$evidence.trading_methods) -and
        ([string]$evidence.gateway_entrypoint -eq "app:app")
    )
}

if ($ownerEvidenceReady -and $implementationBound -and $scriptHashesBound -and (-not $runnerIsAdmin)) {
    try {
        $wp8Contract = Get-Content -LiteralPath $wp8ContractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $readSpec = @($wp8Contract.secret_classes | Where-Object { [string]$_.id -eq "broker_read" })
        if ($readSpec.Count -eq 1) {
            $connectionsRoot = Join-Path ([string]$readSpec[0].directory) "connections"
            $sentinelPath = Join-Path $connectionsRoot "wp17-ci-deny-sentinel.dpapi"
            if ((Test-Path -LiteralPath $connectionsRoot -PathType Container) -and (Test-Path -LiteralPath $sentinelPath -PathType Leaf)) {
                $secretReadDenied = Test-ReadDataDenied -Path $sentinelPath
                $secretWriteDenied = Test-CreateDenied -Directory $connectionsRoot
            }
            if (Test-Path -LiteralPath $evidenceRoot -PathType Container) {
                $evidenceWriteDenied = Test-CreateDenied -Directory $evidenceRoot
            }
        }
    }
    catch {
        $secretReadDenied = $false
        $secretWriteDenied = $false
        $evidenceWriteDenied = $false
    }
}

$ready = (
    $expectedShaValid -and
    (-not $runnerIsAdmin) -and
    $evidenceReadable -and
    $implementationBound -and
    $scriptHashesBound -and
    $ownerEvidenceReady -and
    $secretReadDenied -and
    $secretWriteDenied -and
    $evidenceWriteDenied
)

$reason = if (-not $evidencePresent) {
    "WP17_OWNER_ACTION_REQUIRED"
}
elseif ($runnerIsAdmin) {
    "WP17_RUNNER_IDENTITY_INVALID"
}
elseif (-not $ready) {
    "WP17_RUNNER_ISOLATION_NOT_PROVEN"
}
else {
    "WP17_OWNER_READ_VAULT_ACCEPTED"
}

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP17"
    evidence_type = "RUNNER_READ_VAULT_ISOLATION"
    reason = $reason
    expected_implementation_sha = $expectedSha
    evidence_present = [bool]$evidencePresent
    evidence_readable = [bool]$evidenceReadable
    implementation_bound = [bool]$implementationBound
    script_hashes_bound = [bool]$scriptHashesBound
    owner_evidence_ready = [bool]$ownerEvidenceReady
    runner_is_administrator = [bool]$runnerIsAdmin
    runner_secret_read_allowed = [bool](-not $secretReadDenied)
    runner_secret_write_allowed = [bool](-not $secretWriteDenied)
    runner_evidence_write_allowed = [bool](-not $evidenceWriteDenied)
    provisioner_sha256 = $provisionerHash
    evidence_finalizer_sha256 = $finalizerHash
    runner_auditor_sha256 = $auditorHash
    real_secret_values_used = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 5
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if (-not $ready) { exit 61 }
