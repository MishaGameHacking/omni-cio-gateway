[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisionerPath = Join-Path $PSScriptRoot "provision_wp15_live_web_acceptance.ps1"
$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"
$launcherPath = Join-Path $PSScriptRoot "run_wp15_live_web_runtime.ps1"
$bootstrapDbPath = Join-Path $PSScriptRoot "bootstrap_wp15_live_database.py"
$finalizerPath = Join-Path $PSScriptRoot "finalize_wp15_live_web_evidence.ps1"
$wp8ContractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$evidenceRoot = "C:\ProgramData\OmniCIO\wp15-live"
$evidencePath = Join-Path $evidenceRoot "owner-live-read-evidence.sanitized.local.json"
$evidenceMarker = Join-Path $evidenceRoot ".omni-cio-wp15-live-evidence"
$evidenceMarkerValue = "OMNI-CIO-V10-WP15-LIVE-EVIDENCE-v1"
$runtimeName = "omni-cio-runtime"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-IdentitySid {
    param([Parameter(Mandatory = $true)][System.Security.Principal.IdentityReference]$IdentityReference)
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) { return [System.Security.Principal.SecurityIdentifier]$IdentityReference }
    try { return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]) }
    catch [System.Security.Principal.IdentityNotMappedException] { return $null }
}

function Test-ReadDataDenied {
    param([Parameter(Mandatory = $true)][string]$Path)
    $stream = $null
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        return $false
    }
    catch [System.UnauthorizedAccessException] { return $true }
    catch [System.Security.SecurityException] { return $true }
    catch { return $false }
    finally { if ($null -ne $stream) { $stream.Dispose() } }
}

function Test-CreateDenied {
    param([Parameter(Mandatory = $true)][string]$Directory)
    $probe = Join-Path $Directory ("wp15-live-runner-probe-" + [guid]::NewGuid().ToString("N") + ".tmp")
    $stream = $null
    $created = $false
    try {
        $stream = [System.IO.File]::Open($probe, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $created = $true
        return $false
    }
    catch [System.UnauthorizedAccessException] { return $true }
    catch [System.Security.SecurityException] { return $true }
    catch { return $false }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if ($created) { try { Remove-Item -LiteralPath $probe -Force -ErrorAction Stop } catch { } }
    }
}

function Get-EvidenceValue {
    param([AllowNull()][object]$Object, [Parameter(Mandatory = $true)][string]$Name, [AllowNull()][object]$Default)
    if ($null -eq $Object) { return $Default }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $Default }
    return $property.Value
}

$expectedSha = $ExpectedImplementationSha.Trim().ToLowerInvariant()
$expectedShaValid = $expectedSha -match '^[0-9a-f]{40}$'
$runnerIsAdmin = Test-Administrator
$evidencePresent = $false
$evidenceReadable = $false
$evidence = $null
try {
    $evidencePresent = Test-Path -LiteralPath $evidencePath -PathType Leaf -ErrorAction Stop
    if ($evidencePresent) {
        $evidence = Get-Content -LiteralPath $evidencePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $evidenceReadable = $true
    }
}
catch {
    $evidencePresent = $false
    $evidenceReadable = $false
    $evidence = $null
}

$hashes = [ordered]@{
    provisioner_sha256 = if (Test-Path -LiteralPath $provisionerPath -PathType Leaf) { (Get-FileHash -LiteralPath $provisionerPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { "" }
    acceptance_starter_sha256 = if (Test-Path -LiteralPath $starterPath -PathType Leaf) { (Get-FileHash -LiteralPath $starterPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { "" }
    runtime_launcher_sha256 = if (Test-Path -LiteralPath $launcherPath -PathType Leaf) { (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { "" }
    database_bootstrap_sha256 = if (Test-Path -LiteralPath $bootstrapDbPath -PathType Leaf) { (Get-FileHash -LiteralPath $bootstrapDbPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { "" }
    evidence_finalizer_sha256 = if (Test-Path -LiteralPath $finalizerPath -PathType Leaf) { (Get-FileHash -LiteralPath $finalizerPath -Algorithm SHA256).Hash.ToLowerInvariant() } else { "" }
    runner_auditor_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
}

$implementationBound = $false
$scriptHashesBound = $false
$ownerEvidenceReady = $false
$forbiddenFieldsAbsent = $false
$evidenceWriteDenied = $false
$runtimeEvidenceAccessPresent = $true
$secretReadDenied = $false
$secretWriteDenied = $false
$runtimeDisabled = $false
$temporaryTaskAbsent = $false

if ($expectedShaValid -and $evidenceReadable -and $null -ne $evidence) {
    $implementationBound = ([string](Get-EvidenceValue -Object $evidence -Name "implementation_sha" -Default "")).ToLowerInvariant() -eq $expectedSha
    $scriptHashesBound = $true
    foreach ($name in $hashes.Keys) {
        if (([string](Get-EvidenceValue -Object $evidence -Name $name -Default "")).ToLowerInvariant() -ne [string]$hashes[$name]) {
            $scriptHashesBound = $false
        }
    }
    $ownerEvidenceReady = (
        [string](Get-EvidenceValue -Object $evidence -Name "schema_version" -Default "") -eq "1" -and
        [string](Get-EvidenceValue -Object $evidence -Name "work_package" -Default "") -eq "WP15" -and
        [string](Get-EvidenceValue -Object $evidence -Name "evidence_type" -Default "") -eq "LIVE_WEB_READ_ACCEPTANCE_FINAL" -and
        [string](Get-EvidenceValue -Object $evidence -Name "reason" -Default "") -eq "WP15_LIVE_WEB_READ_VERIFIED" -and
        [bool](Get-EvidenceValue -Object $evidence -Name "owner_verify_ready" -Default $false) -and
        [string](Get-EvidenceValue -Object $evidence -Name "broker_authority" -Default "") -eq "READ_ONLY" -and
        [bool](Get-EvidenceValue -Object $evidence -Name "intended_masked_account_confirmed" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "portfolio_summary_parity" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "sample_position_quantity_value_parity" -Default $false) -and
        [string](Get-EvidenceValue -Object $evidence -Name "freshness_state" -Default "") -eq "FRESH" -and
        [bool](Get-EvidenceValue -Object $evidence -Name "freshness_confirmed" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "real_broker_read_observation" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "real_read_credential_used_locally" -Default $false) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "secret_value_recorded" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "full_account_id_recorded" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "account_fingerprint_recorded" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "private_portfolio_values_recorded" -Default $true)) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "runtime_cleanup_complete" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "postgres_config_restored" -Default $false) -and
        [bool](Get-EvidenceValue -Object $evidence -Name "evidence_acl_protected" -Default $false) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "runtime_evidence_write_allowed" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "runner_evidence_write_allowed" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "broker_write_authority_added" -Default $true)) -and
        (-not [bool](Get-EvidenceValue -Object $evidence -Name "trading_methods" -Default $true)) -and
        [string](Get-EvidenceValue -Object $evidence -Name "gateway_entrypoint" -Default "") -eq "app:app" -and
        [bool](Get-EvidenceValue -Object $evidence -Name "ready" -Default $false)
    )
    $forbidden = @("token", "secret", "ciphertext", "broker_account_id", "account_fingerprint", "portfolio_total", "quantity", "unit_price", "market_value", "position_payload", "private_portfolio_payload", "masked_account")
    $forbiddenFieldsAbsent = -not [bool](@($evidence.PSObject.Properties.Name | Where-Object { $forbidden -contains $_ }).Count)
}

if ($ownerEvidenceReady -and $implementationBound -and $scriptHashesBound -and $forbiddenFieldsAbsent -and -not $runnerIsAdmin) {
    try {
        if (-not (Test-Path -LiteralPath $evidenceMarker -PathType Leaf) -or (Get-Content -LiteralPath $evidenceMarker -Raw).Trim() -ne $evidenceMarkerValue) { throw "EVIDENCE_MARKER_INVALID" }
        $runtimeSid = (Get-LocalUser -Name $runtimeName -ErrorAction Stop).SID
        $runtimeDisabled = -not [bool](Get-LocalUser -Name $runtimeName -ErrorAction Stop).Enabled
        $temporaryTaskAbsent = $null -eq (Get-ScheduledTask -TaskName "OmniCIO.V10.WP15LiveAcceptance" -ErrorAction SilentlyContinue)
        $acl = Get-Acl -LiteralPath $evidenceRoot -ErrorAction Stop
        $runtimeRules = @($acl.Access | Where-Object {
            $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
            $null -ne $sid -and $sid.Value -eq $runtimeSid.Value -and $_.AccessControlType -eq 'Allow'
        })
        $runtimeEvidenceAccessPresent = $runtimeRules.Count -gt 0
        $evidenceWriteDenied = Test-CreateDenied -Directory $evidenceRoot

        $wp8 = Get-Content -LiteralPath $wp8ContractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $readSpec = @($wp8.secret_classes | Where-Object { [string]$_.id -eq "broker_read" })
        if ($readSpec.Count -ne 1) { throw "WP8_READ_SPEC_INVALID" }
        $connectionsRoot = Join-Path ([string]$readSpec[0].directory) "connections"
        $sentinel = Join-Path $connectionsRoot "wp17-ci-deny-sentinel.dpapi"
        $secretReadDenied = Test-ReadDataDenied -Path $sentinel
        $secretWriteDenied = Test-CreateDenied -Directory $connectionsRoot
    }
    catch {
        $runtimeDisabled = $false
        $temporaryTaskAbsent = $false
        $runtimeEvidenceAccessPresent = $true
        $evidenceWriteDenied = $false
        $secretReadDenied = $false
        $secretWriteDenied = $false
    }
}

$ready = (
    $expectedShaValid -and -not $runnerIsAdmin -and $evidenceReadable -and $implementationBound -and
    $scriptHashesBound -and $ownerEvidenceReady -and $forbiddenFieldsAbsent -and $runtimeDisabled -and
    $temporaryTaskAbsent -and (-not $runtimeEvidenceAccessPresent) -and $evidenceWriteDenied -and
    $secretReadDenied -and $secretWriteDenied
)
$reason = if (-not $evidencePresent) { "WP15_LIVE_OWNER_ACTION_REQUIRED" }
elseif ($runnerIsAdmin) { "WP15_LIVE_RUNNER_IDENTITY_INVALID" }
elseif (-not $ready) { "WP15_LIVE_RUNNER_ISOLATION_NOT_PROVEN" }
else { "WP15_LIVE_WEB_READ_ACCEPTED" }

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP15"
    evidence_type = "RUNNER_LIVE_WEB_ACCEPTANCE_AUDIT"
    reason = $reason
    expected_implementation_sha = $expectedSha
    evidence_present = [bool]$evidencePresent
    evidence_readable = [bool]$evidenceReadable
    implementation_bound = [bool]$implementationBound
    script_hashes_bound = [bool]$scriptHashesBound
    owner_evidence_ready = [bool]$ownerEvidenceReady
    forbidden_private_fields_absent = [bool]$forbiddenFieldsAbsent
    runner_is_administrator = [bool]$runnerIsAdmin
    runtime_role_disabled = [bool]$runtimeDisabled
    temporary_runtime_task_absent = [bool]$temporaryTaskAbsent
    runtime_final_evidence_access_present = [bool]$runtimeEvidenceAccessPresent
    runner_secret_read_allowed = [bool](-not $secretReadDenied)
    runner_secret_write_allowed = [bool](-not $secretWriteDenied)
    runner_evidence_write_allowed = [bool](-not $evidenceWriteDenied)
    real_broker_read_observation = [bool](Get-EvidenceValue -Object $evidence -Name "real_broker_read_observation" -Default $false)
    real_read_credential_used_locally = [bool](Get-EvidenceValue -Object $evidence -Name "real_read_credential_used_locally" -Default $false)
    secret_value_recorded = $false
    private_portfolio_values_recorded = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) { $result | ConvertTo-Json -Depth 5 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (-not $ready) { exit 61 }
