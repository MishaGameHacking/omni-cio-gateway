[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [Parameter(Mandatory = $true)][switch]$TailnetPolicyNarrowConfirmed,
    [Parameter(Mandatory = $true)][switch]$OwnerRemoteCabinetConfirmed,
    [Parameter(Mandatory = $true)][switch]$LocalFallbackConfirmed,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [string]$ConfigPath = "C:\ProgramData\OmniCIO\wp22a\private-remote.json",
    [string]$EvidencePath = "C:\ProgramData\OmniCIO\wp22a-evidence\owner-private-remote.sanitized.local.json"
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A OWNER evidence finalization requires Windows." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configurator = Join-Path $PSScriptRoot "configure_wp22a_tailscale_serve.ps1"
$provisioner = Join-Path $PSScriptRoot "provision_wp22a_private_remote_runtime.ps1"
$launcher = Join-Path $PSScriptRoot "run_wp22a_private_remote_runtime.ps1"
$finalizer = $MyInvocation.MyCommand.Path
$remoteSecurity = Join-Path $repoRoot "omni_cio\web\remote_security_v1.py"
$executionContract = Join-Path $repoRoot "docs\architecture\V10_WP22A_EXECUTION_CONTRACT.md"
$runtimeName = "omni-cio-runtime"
$runtimeOwnershipMarker = "Omni-CIO V10 WP6 runtime role anchor"
$runnerRoot = "C:\actions-runner"
$evidenceRoot = Split-Path -Parent $EvidencePath
$evidenceMarker = Join-Path $evidenceRoot ".omni-cio-wp22a-evidence-owned"
$evidenceMarkerValue = "OMNI-CIO-V10-WP22A-EVIDENCE-v1"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EVIDENCE_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_EVIDENCE_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_EVIDENCE_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP22A_EVIDENCE_WORKTREE_NOT_CLEAN" }
    return $actual
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
    if ($services.Count -ne 1) { throw "WP22A_EVIDENCE_RUNNER_IDENTITY_UNAVAILABLE" }
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
}

function Resolve-IdentitySid {
    param([Parameter(Mandatory = $true)][System.Security.Principal.IdentityReference]$IdentityReference)
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) { return $IdentityReference }
    try { return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]) }
    catch [System.Security.Principal.IdentityNotMappedException] { return $null }
}

function New-Rule {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $Inheritance,
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

function Test-EvidenceAcl {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)
    $acl = Get-Acl -LiteralPath $evidenceRoot -ErrorAction Stop
    if (-not $acl.AreAccessRulesProtected) { return $false }
    $allowed = @("S-1-5-18", "S-1-5-32-544", $RunnerSid.Value)
    $runnerRead = $false
    foreach ($rule in @($acl.Access)) {
        if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
        $sid = Resolve-IdentitySid -IdentityReference $rule.IdentityReference
        if ($null -eq $sid -or $allowed -notcontains $sid.Value) { return $false }
        if ($sid.Value -eq $RunnerSid.Value) {
            $rights = $rule.FileSystemRights
            $read = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
            if (($rights -band $read) -eq $read) { $runnerRead = $true }
            $forbidden = [System.Security.AccessControl.FileSystemRights]::Write -bor [System.Security.AccessControl.FileSystemRights]::Delete -bor [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor [System.Security.AccessControl.FileSystemRights]::TakeOwnership
            if (($rights -band $forbidden) -ne 0) { return $false }
        }
    }
    return $runnerRead
}

if (-not (Test-Administrator)) { throw "WP22A OWNER evidence finalizer requires administrator." }
$implementationSha = Get-ReviewedHead
$runnerSid = Get-RunnerSid
$runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
if ([string]$runtimeUser.Description -ne $runtimeOwnershipMarker) { throw "WP22A_EVIDENCE_RUNTIME_OWNERSHIP_INVALID" }
$administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
if (@(Get-LocalGroupMember -SID $administratorsSid -ErrorAction Stop).SID.Value -contains $runtimeUser.SID.Value) { throw "WP22A_EVIDENCE_RUNTIME_IS_ADMIN" }

foreach ($path in @($configurator, $provisioner, $launcher, $finalizer, $remoteSecurity, $executionContract)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "WP22A_EVIDENCE_SOURCE_MISSING" }
}

$configRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $configurator -Verify -BackendPort $Port -ConfigPath $ConfigPath -AsJson 2>$null | Out-String
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_CONFIG_VERIFY_FAILED" }
$configState = $configRaw.Trim() | ConvertFrom-Json -ErrorAction Stop
if (-not [bool]$configState.ready) { throw "WP22A_EVIDENCE_CONFIG_NOT_READY" }

$runtimeRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $provisioner -ExpectedImplementationSha $implementationSha -Verify -Port $Port -ConfigPath $ConfigPath -AsJson 2>$null | Out-String
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_RUNTIME_VERIFY_FAILED" }
$runtimeState = $runtimeRaw.Trim() | ConvertFrom-Json -ErrorAction Stop
if (-not [bool]$runtimeState.ready) { throw "WP22A_EVIDENCE_RUNTIME_NOT_READY" }

foreach ($confirmation in @($TailnetPolicyNarrowConfirmed, $OwnerRemoteCabinetConfirmed, $LocalFallbackConfirmed)) {
    if (-not [bool]$confirmation) { throw "WP22A_EVIDENCE_OWNER_CONFIRMATION_REQUIRED" }
}

$sourceHashes = [ordered]@{
    configurator_sha256 = (Get-FileHash -LiteralPath $configurator -Algorithm SHA256).Hash.ToLowerInvariant()
    provisioner_sha256 = (Get-FileHash -LiteralPath $provisioner -Algorithm SHA256).Hash.ToLowerInvariant()
    launcher_sha256 = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant()
    finalizer_sha256 = (Get-FileHash -LiteralPath $finalizer -Algorithm SHA256).Hash.ToLowerInvariant()
    remote_security_sha256 = (Get-FileHash -LiteralPath $remoteSecurity -Algorithm SHA256).Hash.ToLowerInvariant()
    execution_contract_sha256 = (Get-FileHash -LiteralPath $executionContract -Algorithm SHA256).Hash.ToLowerInvariant()
}

$tailscale = (Get-Command tailscale.exe -ErrorAction Stop).Source
& $tailscale serve --https=443 off 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_SERVE_DISABLE_FAILED" }
& $tailscale funnel --https=443 off 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_FUNNEL_DISABLE_FAILED" }
$serveAfter = (& $tailscale serve status --json 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_SERVE_STATUS_FAILED" }
$serveDisabled = @("", "{}", "[]", "null") -contains ($serveAfter -replace '\s', '')
if (-not $serveDisabled) { throw "WP22A_EVIDENCE_SERVE_STILL_ACTIVE" }
$funnelAfter = (& $tailscale funnel status --json 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_FUNNEL_STATUS_FAILED" }
$funnelDisabledAfter = @("", "{}", "[]", "null") -contains ($funnelAfter -replace '\s', '')
if (-not $funnelDisabledAfter) { throw "WP22A_EVIDENCE_FUNNEL_STILL_ACTIVE" }

$cleanupRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $provisioner -ExpectedImplementationSha $implementationSha -Cleanup -Port $Port -ConfigPath $ConfigPath -AsJson 2>$null | Out-String
if ($LASTEXITCODE -ne 0) { throw "WP22A_EVIDENCE_RUNTIME_CLEANUP_FAILED" }
$cleanupState = $cleanupRaw.Trim() | ConvertFrom-Json -ErrorAction Stop
if (-not [bool]$cleanupState.ready) { throw "WP22A_EVIDENCE_RUNTIME_CLEANUP_NOT_READY" }

if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    Set-Content -LiteralPath $evidenceMarker -Value $evidenceMarkerValue -Encoding ASCII -NoNewline
}
elseif (-not (Test-Path -LiteralPath $evidenceMarker -PathType Leaf)) {
    throw "WP22A_EVIDENCE_REFUSES_UNMARKED_ROOT"
}
if ((Get-Content -LiteralPath $evidenceMarker -Raw).Trim() -ne $evidenceMarkerValue) { throw "WP22A_EVIDENCE_MARKER_MISMATCH" }
Set-EvidenceAcl -RunnerSid $runnerSid
if (-not (Test-EvidenceAcl -RunnerSid $runnerSid)) { throw "WP22A_EVIDENCE_ACL_INVALID" }

$evidence = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_type = "OWNER_PRIVATE_REMOTE_SANITIZED"
    implementation_sha = $implementationSha
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    configurator_sha256 = $sourceHashes.configurator_sha256
    provisioner_sha256 = $sourceHashes.provisioner_sha256
    launcher_sha256 = $sourceHashes.launcher_sha256
    finalizer_sha256 = $sourceHashes.finalizer_sha256
    remote_security_sha256 = $sourceHashes.remote_security_sha256
    execution_contract_sha256 = $sourceHashes.execution_contract_sha256
    tailscale_private_serve_observed = [bool]$configState.serve_configured
    funnel_disabled_during_rehearsal = [bool]$configState.funnel_disabled
    backend_loopback_only = [bool]$configState.backend_loopback_only
    private_config_acl_ok = [bool]$configState.private_config_acl_ok
    owner_identity_fingerprint_present = [bool]$configState.owner_identity_fingerprint_present
    runtime_exact_deployment = [bool]$runtimeState.deployment_bound
    runtime_non_admin = [bool]$runtimeState.runtime_role_non_admin
    runtime_task_principal_exact = [bool]$runtimeState.task_principal_runtime
    runtime_task_action_exact = [bool]$runtimeState.task_action_exact
    runner_runtime_data_access = [bool]$runtimeState.runner_runtime_data_access
    tailnet_policy_narrow_owner_only_confirmed = $true
    owner_remote_https_cabinet_confirmed = $true
    local_loopback_fallback_confirmed = $true
    non_owner_identity_denial_deterministic = $true
    serve_disabled_after_rehearsal = [bool]$serveDisabled
    funnel_disabled_after_rehearsal = [bool]$funnelDisabledAfter
    temporary_runtime_cleaned = [bool](-not $cleanupState.temporary_task_present -and -not $cleanupState.runtime_role_enabled)
    postgres_config_restored = [bool]$cleanupState.postgres_config_restored
    raw_owner_identity_recorded = $false
    raw_tailnet_hostname_recorded = $false
    session_cookie_recorded = $false
    tailscale_auth_key_recorded = $false
    broker_secret_recorded = $false
    private_portfolio_payload_recorded = $false
    public_ingress = $false
    public_multi_user_enabled = $false
    broker_write_authority_added = $false
    trading_methods = $false
    real_trading_enabled = $false
    gateway_entrypoint = "app:app"
    ready = $true
}

$evidence | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8
Set-EvidenceAcl -RunnerSid $runnerSid

if ($AsJson) { $evidence | ConvertTo-Json -Depth 5 } else { $evidence.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
