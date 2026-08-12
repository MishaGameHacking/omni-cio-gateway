[CmdletBinding()]
param([switch]$AsJson)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisionerPath = Join-Path $PSScriptRoot "provision_wp15_live_web_acceptance.ps1"
$starterPath = Join-Path $PSScriptRoot "start_wp15_live_web_acceptance.ps1"
$launcherPath = Join-Path $PSScriptRoot "run_wp15_live_web_runtime.ps1"
$bootstrapDbPath = Join-Path $PSScriptRoot "bootstrap_wp15_live_database.py"
$auditorPath = Join-Path $PSScriptRoot "audit_wp15_live_web_runner.ps1"
$pendingPath = "C:\ProgramData\OmniCIO\runtime\wp15-live\pending\owner-confirmation.json"
$evidenceRoot = "C:\ProgramData\OmniCIO\wp15-live"
$evidencePath = Join-Path $evidenceRoot "owner-live-read-evidence.sanitized.local.json"
$evidenceMarker = Join-Path $evidenceRoot ".omni-cio-wp15-live-evidence"
$evidenceMarkerValue = "OMNI-CIO-V10-WP15-LIVE-EVIDENCE-v1"
$runtimeName = "omni-cio-runtime"
$runnerRoot = "C:\actions-runner"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-IdentitySid {
    param([Parameter(Mandatory = $true)][System.Security.Principal.IdentityReference]$IdentityReference)
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) {
        return [System.Security.Principal.SecurityIdentifier]$IdentityReference
    }
    try { return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]) }
    catch [System.Security.Principal.IdentityNotMappedException] { return $null }
}

function Get-RunnerSid {
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
    return [System.Security.Principal.NTAccount]::new([string]$services[0].StartName).Translate([System.Security.Principal.SecurityIdentifier])
}

function New-Rule {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid, $Rights, $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-EvidenceAcl {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $RunnerSid -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -Inheritance $inherit))
    Set-Acl -LiteralPath $evidenceRoot -AclObject $acl -ErrorAction Stop
}

function Get-ExactHead {
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP15_LIVE_GIT_HEAD_UNAVAILABLE" }
    $sha = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{40}$') { throw "WP15_LIVE_GIT_HEAD_INVALID" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw "WP15_LIVE_WORKTREE_NOT_CLEAN" }
    return $sha
}

function Get-PropertySet {
    param([Parameter(Mandatory = $true)][object]$Object)
    return @($Object.PSObject.Properties.Name | Sort-Object)
}

function Test-ExactProperties {
    param(
        [Parameter(Mandatory = $true)][object]$Object,
        [Parameter(Mandatory = $true)][string[]]$Expected
    )
    $actual = Get-PropertySet -Object $Object
    $wanted = @($Expected | Sort-Object)
    if ($actual.Count -ne $wanted.Count) { return $false }
    return -not [bool](Compare-Object -ReferenceObject $wanted -DifferenceObject $actual)
}

if (-not (Test-Administrator)) { throw "WP15 live evidence finalization requires OWNER administrator." }
$implementationSha = Get-ExactHead
if (-not (Test-Path -LiteralPath $pendingPath -PathType Leaf)) { throw "WP15_LIVE_OWNER_CONFIRMATION_REQUIRED" }

$pending = Get-Content -LiteralPath $pendingPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
$expectedPendingFields = @(
    "schema_version", "work_package", "evidence_type", "implementation_sha", "observed_at", "confirmed_at",
    "broker_authority", "intended_masked_account_confirmed", "portfolio_summary_parity",
    "sample_position_quantity_value_parity", "freshness_state", "freshness_confirmed", "sample_position_present",
    "normalized_position_count", "real_broker_read_observation", "real_read_credential_used_locally",
    "secret_value_recorded", "full_account_id_recorded", "account_fingerprint_recorded",
    "private_portfolio_values_recorded", "broker_write_authority_added", "trading_methods", "gateway_entrypoint",
    "ready_for_owner_finalization"
)
if (-not (Test-ExactProperties -Object $pending -Expected $expectedPendingFields)) { throw "WP15_LIVE_PENDING_SCHEMA_INVALID" }
if ([string]$pending.schema_version -ne "1" -or [string]$pending.work_package -ne "WP15" -or [string]$pending.evidence_type -ne "LIVE_WEB_READ_ACCEPTANCE_PENDING") { throw "WP15_LIVE_PENDING_IDENTITY_INVALID" }
if ([string]$pending.implementation_sha -ne $implementationSha) { throw "WP15_LIVE_PENDING_IMPLEMENTATION_MISMATCH" }
if ([string]$pending.broker_authority -ne "READ_ONLY" -or [string]$pending.freshness_state -ne "FRESH") { throw "WP15_LIVE_PENDING_AUTHORITY_OR_FRESHNESS_INVALID" }
if (-not [bool]$pending.intended_masked_account_confirmed -or -not [bool]$pending.portfolio_summary_parity -or -not [bool]$pending.sample_position_quantity_value_parity -or -not [bool]$pending.freshness_confirmed -or -not [bool]$pending.sample_position_present -or -not [bool]$pending.real_broker_read_observation -or -not [bool]$pending.real_read_credential_used_locally -or -not [bool]$pending.ready_for_owner_finalization) { throw "WP15_LIVE_PENDING_CONFIRMATION_INCOMPLETE" }
if ([bool]$pending.secret_value_recorded -or [bool]$pending.full_account_id_recorded -or [bool]$pending.account_fingerprint_recorded -or [bool]$pending.private_portfolio_values_recorded -or [bool]$pending.broker_write_authority_added -or [bool]$pending.trading_methods -or [string]$pending.gateway_entrypoint -ne "app:app") { throw "WP15_LIVE_PENDING_SAFETY_INVALID" }
if ([int]$pending.normalized_position_count -lt 1) { throw "WP15_LIVE_PENDING_SAMPLE_INVALID" }

$observedAt = [DateTimeOffset]::Parse([string]$pending.observed_at).ToUniversalTime()
$confirmedAt = [DateTimeOffset]::Parse([string]$pending.confirmed_at).ToUniversalTime()
$now = [DateTimeOffset]::UtcNow
if ($observedAt -gt $confirmedAt -or $confirmedAt -gt $now.AddMinutes(5) -or $confirmedAt -lt $now.AddHours(-2)) { throw "WP15_LIVE_PENDING_TIME_INVALID" }

foreach ($path in @($provisionerPath, $starterPath, $launcherPath, $bootstrapDbPath, $auditorPath, $PSCommandPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "WP15_LIVE_EVIDENCE_SCRIPT_MISSING" }
}
$provisionerHash = (Get-FileHash -LiteralPath $provisionerPath -Algorithm SHA256).Hash.ToLowerInvariant()
$starterHash = (Get-FileHash -LiteralPath $starterPath -Algorithm SHA256).Hash.ToLowerInvariant()
$launcherHash = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash.ToLowerInvariant()
$bootstrapHash = (Get-FileHash -LiteralPath $bootstrapDbPath -Algorithm SHA256).Hash.ToLowerInvariant()
$finalizerHash = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
$auditorHash = (Get-FileHash -LiteralPath $auditorPath -Algorithm SHA256).Hash.ToLowerInvariant()

$cleanupJson = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $provisionerPath -ExpectedImplementationSha $implementationSha -Cleanup -AsJson)
if ($LASTEXITCODE -ne 0) { throw "WP15_LIVE_RUNTIME_CLEANUP_FAILED" }
$cleanup = ($cleanupJson -join "`n") | ConvertFrom-Json -ErrorAction Stop
if (-not [bool]$cleanup.ready -or -not [bool]$cleanup.postgres_config_restored -or [bool]$cleanup.runtime_role_enabled -or [bool]$cleanup.temporary_task_present) { throw "WP15_LIVE_RUNTIME_CLEANUP_NOT_READY" }

$runnerSid = Get-RunnerSid
$runtimeSid = (Get-LocalUser -Name $runtimeName -ErrorAction Stop).SID
if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) { New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null }
Set-EvidenceAcl -RunnerSid $runnerSid
Set-Content -LiteralPath $evidenceMarker -Value $evidenceMarkerValue -Encoding ASCII -NoNewline

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP15"
    evidence_type = "LIVE_WEB_READ_ACCEPTANCE_FINAL"
    reason = "WP15_LIVE_WEB_READ_VERIFIED"
    implementation_sha = $implementationSha
    provisioner_sha256 = $provisionerHash
    acceptance_starter_sha256 = $starterHash
    runtime_launcher_sha256 = $launcherHash
    database_bootstrap_sha256 = $bootstrapHash
    evidence_finalizer_sha256 = $finalizerHash
    runner_auditor_sha256 = $auditorHash
    owner_verify_ready = $true
    broker_authority = "READ_ONLY"
    intended_masked_account_confirmed = $true
    portfolio_summary_parity = $true
    sample_position_quantity_value_parity = $true
    freshness_state = "FRESH"
    freshness_confirmed = $true
    real_broker_read_observation = $true
    real_read_credential_used_locally = $true
    secret_value_recorded = $false
    full_account_id_recorded = $false
    account_fingerprint_recorded = $false
    private_portfolio_values_recorded = $false
    runtime_cleanup_complete = $true
    postgres_config_restored = $true
    evidence_acl_protected = $true
    runtime_evidence_write_allowed = $false
    runner_evidence_write_allowed = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = $true
}

$payload = $result | ConvertTo-Json -Depth 5
$tempPath = Join-Path $evidenceRoot (".owner-live-read-evidence." + [guid]::NewGuid().ToString("N") + ".tmp")
try {
    [System.IO.File]::WriteAllText($tempPath, $payload, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $evidencePath -Force
}
finally {
    Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
}
Set-EvidenceAcl -RunnerSid $runnerSid

$acl = Get-Acl -LiteralPath $evidenceRoot -ErrorAction Stop
$runtimeRules = @($acl.Access | Where-Object {
    $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
    $null -ne $sid -and $sid.Value -eq $runtimeSid.Value -and $_.AccessControlType -eq 'Allow'
})
$runnerRules = @($acl.Access | Where-Object {
    $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
    $null -ne $sid -and $sid.Value -eq $runnerSid.Value -and $_.AccessControlType -eq 'Allow'
})
$runtimeWrite = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 })
$runnerWrite = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 -or ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 })
if (-not $acl.AreAccessRulesProtected -or $runtimeWrite -or $runnerWrite) {
    Remove-Item -LiteralPath $evidencePath -Force -ErrorAction SilentlyContinue
    throw "WP15_LIVE_FINAL_EVIDENCE_ACL_INVALID"
}

if ($AsJson) { $result | ConvertTo-Json -Depth 5 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
