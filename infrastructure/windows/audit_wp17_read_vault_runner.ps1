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

function Get-EvidenceValue {
    param(
        [AllowNull()][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [AllowNull()][object]$Default
    )

    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
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
    $created = $false
    try {
        $stream = [System.IO.File]::Open(
            $probe,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $created = $true
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
        if ($created) {
            try { Remove-Item -LiteralPath $probe -Force -ErrorAction Stop } catch { }
        }
    }
}

$expectedSha = $ExpectedImplementationSha.Trim().ToLowerInvariant()
$expectedShaValid = $expectedSha -match '^[0-9a-f]{40}$'
$runnerIsAdmin = Test-Administrator
$evidencePresent = $false
$evidence = $null
$evidenceReadable = $false

try {
    $evidencePresent = Test-Path -LiteralPath $evidencePath -PathType Leaf -ErrorAction Stop
    if ($evidencePresent) {
        $evidence = Get-Content -LiteralPath $evidencePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $evidenceReadable = $true
    }
}
catch {
    $evidencePresent = $false
    $evidence = $null
    $evidenceReadable = $false
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
$permissionProbesExecuted = $false

if ($expectedShaValid -and $evidenceReadable -and $null -ne $evidence) {
    $evidenceImplementation = [string](Get-EvidenceValue -Object $evidence -Name "implementation_sha" -Default "")
    $evidenceProvisionerHash = [string](Get-EvidenceValue -Object $evidence -Name "provisioner_sha256" -Default "")
    $evidenceFinalizerHash = [string](Get-EvidenceValue -Object $evidence -Name "evidence_finalizer_sha256" -Default "")
    $implementationBound = $evidenceImplementation.ToLowerInvariant() -eq $expectedSha
    $scriptHashesBound = (
        $evidenceProvisionerHash.ToLowerInvariant() -eq $provisionerHash -and
        $evidenceFinalizerHash.ToLowerInvariant() -eq $finalizerHash
    )
    $ownerEvidenceReady = (
        [bool](Get-EvidenceValue -Object $evidence -Name "ready" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "owner_verify_ready" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "read_connection_vault_present" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "ownership_marker_ok" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "runtime_modify_read_child" -Default $false) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "runner_read_data_allowed" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "runner_write_allowed" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "broad_read_principal_present" -Default $true)) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "broker_trading_acl_unchanged" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "evidence_acl_protected" -Default $false) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "runner_evidence_write_allowed" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "real_secret_values_used" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "broker_write_authority_added" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "trading_methods" -Default $true)) -and
        ([string](Get-EvidenceValue -Object $evidence -Name "gateway_entrypoint" -Default "") -eq "app:app")
    )
}

if ($ownerEvidenceReady -and $implementationBound -and $scriptHashesBound -and (-not $runnerIsAdmin)) {
    $permissionProbesExecuted = $true
    try {
        $wp8Contract = Get-Content -LiteralPath $wp8ContractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $readSpec = @($wp8Contract.secret_classes | Where-Object { [string]$_.id -eq "broker_read" })
        if ($readSpec.Count -eq 1) {
            $connectionsRoot = Join-Path ([string]$readSpec[0].directory) "connections"
            $sentinelPath = Join-Path $connectionsRoot "wp17-ci-deny-sentinel.dpapi"
            $secretReadDenied = Test-ReadDataDenied -Path $sentinelPath
            $secretWriteDenied = Test-CreateDenied -Directory $connectionsRoot
            $evidenceWriteDenied = Test-CreateDenied -Directory $evidenceRoot
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
elseif (-not $evidenceReadable) {
    "WP17_OWNER_EVIDENCE_UNREADABLE"
}
elseif ($runnerIsAdmin) {
    "WP17_RUNNER_IDENTITY_INVALID"
}
elseif (-not $implementationBound) {
    "WP17_OWNER_EVIDENCE_HEAD_DRIFT"
}
elseif (-not $scriptHashesBound) {
    "WP17_OWNER_EVIDENCE_SCRIPT_DRIFT"
}
elseif (-not $ownerEvidenceReady) {
    "WP17_OWNER_EVIDENCE_NOT_READY"
}
elseif (-not $permissionProbesExecuted) {
    "WP17_RUNNER_PROBES_NOT_EXECUTED"
}
elseif (-not $secretReadDenied) {
    "WP17_RUNNER_SECRET_READ_NOT_DENIED"
}
elseif (-not $secretWriteDenied) {
    "WP17_RUNNER_SECRET_WRITE_NOT_DENIED"
}
elseif (-not $evidenceWriteDenied) {
    "WP17_RUNNER_EVIDENCE_WRITE_NOT_DENIED"
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
    permission_probes_executed = [bool]$permissionProbesExecuted
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
