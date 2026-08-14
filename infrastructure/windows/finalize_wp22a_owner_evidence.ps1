[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [Parameter(Mandatory = $true)][switch]$PhoneHttpsReachabilityConfirmed,
    [Parameter(Mandatory = $true)][switch]$LogoutSessionRevocationConfirmed,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stateRoot = "C:\ProgramData\OmniCIO\wp22a"
$evidencePath = Join-Path $stateRoot "owner-rehearsal.sanitized.local.json"
$provisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp22a_private_remote_access.ps1"
$runtimeLauncher = Join-Path $repoRoot "infrastructure\windows\run_wp22a_private_remote_runtime.ps1"
$ownerFinalizer = $PSCommandPath
$executionContract = Join-Path $repoRoot "docs\architecture\V10_WP22A_EXECUTION_CONTRACT.md"
$externalAccess = Join-Path $repoRoot "omni_cio\web\external_access_v1.py"
$remoteFactory = Join-Path $repoRoot "apps\api\wp22a_remote.py"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Sha256Lower {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "WP22A_IMPLEMENTATION_FILE_MISSING"
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP22A_WORKTREE_NOT_CLEAN" }
    return $actual
}

function Write-Summary {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)
    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 4 -Compress
        return
    }
    Write-Output "WP22A OWNER private remote gate: $($Result.status)"
    Write-Output "Reason: $($Result.reason_code)"
    Write-Output "Exact implementation binding: $($Result.exact_implementation_binding)"
    Write-Output "Backend loopback-only: $($Result.backend_loopback_only)"
    Write-Output "Tailscale Serve private: $($Result.tailscale_serve_private)"
    Write-Output "Funnel/public ingress: $($Result.funnel_public_ingress)"
    Write-Output "OWNER identity binding: $($Result.owner_identity_binding)"
    Write-Output "Secure session: $($Result.secure_server_session)"
    Write-Output "Phone HTTPS reachability: $($Result.phone_https_reachability_confirmed)"
    Write-Output "Logout/session revoke: $($Result.logout_session_revocation_confirmed)"
    Write-Output "Sensitive identity/URL/credential evidence emitted: NO"
}

$result = [ordered]@{
    status = "FAIL"
    reason_code = "WP22A_OWNER_EVIDENCE_NOT_COMPLETED"
    exact_implementation_binding = $false
    backend_loopback_only = $false
    tailscale_serve_private = $false
    funnel_public_ingress = $false
    owner_identity_binding = $false
    secure_server_session = $false
    phone_https_reachability_confirmed = $false
    logout_session_revocation_confirmed = $false
}

try {
    if ($env:OS -ne "Windows_NT") { throw "WP22A_WINDOWS_REQUIRED" }
    if (-not (Test-Administrator)) { throw "WP22A_OWNER_ADMIN_REQUIRED" }
    if (-not [bool]$PhoneHttpsReachabilityConfirmed) {
        throw "WP22A_PHONE_HTTPS_CONFIRMATION_REQUIRED"
    }
    if (-not [bool]$LogoutSessionRevocationConfirmed) {
        throw "WP22A_LOGOUT_CONFIRMATION_REQUIRED"
    }

    $sha = Get-ReviewedHead
    foreach ($path in @(
        $provisioner,
        $runtimeLauncher,
        $ownerFinalizer,
        $executionContract,
        $externalAccess,
        $remoteFactory
    )) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "WP22A_IMPLEMENTATION_FILE_MISSING"
        }
    }

    $verifyRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $provisioner `
        -ExpectedImplementationSha $sha `
        -Verify `
        -AsJson 2>$null
    if ($LASTEXITCODE -ne 0) { throw "WP22A_PRIVATE_REMOTE_VERIFY_FAILED" }
    try {
        $verify = ($verifyRaw | Out-String) | ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "WP22A_PRIVATE_REMOTE_VERIFY_OUTPUT_INVALID" }

    if (
        [string]$verify.status -ne "PASS" -or
        -not [bool]$verify.exact_implementation_binding -or
        -not [bool]$verify.backend_loopback_only -or
        -not [bool]$verify.tailscale_serve_private -or
        [bool]$verify.funnel_public_ingress -or
        -not [bool]$verify.owner_identity_binding -or
        -not [bool]$verify.secure_server_session -or
        -not [bool]$verify.phone_rehearsal_required
    ) {
        throw "WP22A_PRIVATE_REMOTE_VERIFY_NOT_PASS"
    }

    $fingerprint = [ordered]@{
        execution_contract_sha256 = Get-Sha256Lower -Path $executionContract
        external_access_sha256 = Get-Sha256Lower -Path $externalAccess
        remote_factory_sha256 = Get-Sha256Lower -Path $remoteFactory
        provisioner_sha256 = Get-Sha256Lower -Path $provisioner
        runtime_launcher_sha256 = Get-Sha256Lower -Path $runtimeLauncher
        owner_finalizer_sha256 = Get-Sha256Lower -Path $ownerFinalizer
    }

    $evidence = [ordered]@{
        schema_version = "1"
        work_package = "WP22A"
        evidence_class = "OWNER_PRIVATE_REMOTE_REHEARSAL"
        captured_at_utc = [DateTime]::UtcNow.ToString("o")
        implementation_sha = $sha
        implementation_fingerprint = $fingerprint
        exact_implementation_binding = $true
        backend_loopback_only = $true
        tailscale_serve_private = $true
        funnel_public_ingress = $false
        owner_identity_binding = $true
        secure_server_session = $true
        phone_https_reachability_confirmed = $true
        logout_session_revocation_confirmed = $true
        public_multi_user_enabled = $false
        broker_write_authority_added = $false
        trading_methods = $false
        real_trading_enabled = $false
        raw_owner_login_collected = $false
        tailscale_auth_material_collected = $false
        private_url_collected = $false
        broker_secret_collected = $false
        private_portfolio_payload_collected = $false
        status = "PASS"
        reason_code = "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED"
    }

    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    Remove-Item -LiteralPath $evidencePath -Force -ErrorAction SilentlyContinue
    $evidence | ConvertTo-Json -Depth 6 -Compress |
        Set-Content -LiteralPath $evidencePath -Encoding UTF8

    $result.status = "PASS"
    $result.reason_code = "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED"
    $result.exact_implementation_binding = $true
    $result.backend_loopback_only = $true
    $result.tailscale_serve_private = $true
    $result.funnel_public_ingress = $false
    $result.owner_identity_binding = $true
    $result.secure_server_session = $true
    $result.phone_https_reachability_confirmed = $true
    $result.logout_session_revocation_confirmed = $true
}
catch {
    Remove-Item -LiteralPath $evidencePath -Force -ErrorAction SilentlyContinue
    $reason = [string]$_.Exception.Message
    if ($reason -notmatch '^[A-Z0-9_:\-]+$') { $reason = "WP22A_OWNER_EVIDENCE_ERROR" }
    $result.status = "FAIL"
    $result.reason_code = $reason
}

Write-Summary -Result $result
if ($result.status -ne "PASS") { exit 1 }
exit 0
