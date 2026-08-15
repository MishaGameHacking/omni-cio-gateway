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
$runnerAuditor = Join-Path $repoRoot "infrastructure\windows\audit_wp22a_runner_loopback.ps1"
$ownerFinalizer = $PSCommandPath
$executionContract = Join-Path $repoRoot "docs\architecture\V10_WP22A_EXECUTION_CONTRACT.md"
$externalAccess = Join-Path $repoRoot "omni_cio\web\external_access_v1.py"
$localAppFactory = Join-Path $repoRoot "apps\api\app.py"
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

function Get-AccountSid {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") {
        return [System.Security.Principal.SecurityIdentifier]::new("S-1-5-20")
    }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") {
        return [System.Security.Principal.SecurityIdentifier]::new("S-1-5-19")
    }
    try {
        $account = [System.Security.Principal.NTAccount]::new($AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch { throw "WP22A_RUNNER_IDENTITY_SID_UNAVAILABLE" }
}

function Get-RunnerSid {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like "actions.runner.*" }
    )
    if ($services.Count -ne 1) { throw "WP22A_RUNNER_SERVICE_IDENTITY_AMBIGUOUS" }
    $startName = ([string]$services[0].StartName).Trim()
    if ($startName.ToUpperInvariant() -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        throw "WP22A_RUNNER_LOCAL_SYSTEM_FORBIDDEN"
    }
    return Get-AccountSid -AccountName $startName
}

function New-AllowRule {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.InheritanceFlags]$Inheritance
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedEvidenceAcl {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)

    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    $item = Get-Item -LiteralPath $stateRoot -Force -ErrorAction Stop
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "WP22A_EVIDENCE_ROOT_REPARSE_POINT_FORBIDDEN"
    }

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Sid $RunnerSid -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -Inheritance $inherit))
    Set-Acl -LiteralPath $stateRoot -AclObject $acl -ErrorAction Stop
}

function Get-EvidenceAclState {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)

    $systemSid = "S-1-5-18"
    $adminsSid = "S-1-5-32-544"
    $broadSids = @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")
    $writeMask = (
        [System.Security.AccessControl.FileSystemRights]::WriteData -bor
        [System.Security.AccessControl.FileSystemRights]::AppendData -bor
        [System.Security.AccessControl.FileSystemRights]::Delete -bor
        [System.Security.AccessControl.FileSystemRights]::DeleteSubdirectoriesAndFiles -bor
        [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
        [System.Security.AccessControl.FileSystemRights]::TakeOwnership
    )
    $acl = Get-Acl -LiteralPath $stateRoot -ErrorAction Stop
    $rules = @(
        $acl.GetAccessRules(
            $true,
            $false,
            [System.Security.Principal.SecurityIdentifier]
        )
    )
    $allows = @($rules | Where-Object { $_.AccessControlType -eq "Allow" })
    $runnerRules = @($allows | Where-Object { $_.IdentityReference.Value -eq $RunnerSid.Value })
    $runnerRead = [bool]($runnerRules | Where-Object {
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0
    })
    $runnerWrite = [bool]($runnerRules | Where-Object {
        ($_.FileSystemRights -band $writeMask) -ne 0
    })
    $systemFull = [bool]($allows | Where-Object {
        $_.IdentityReference.Value -eq $systemSid -and
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -eq [System.Security.AccessControl.FileSystemRights]::FullControl
    })
    $adminsFull = [bool]($allows | Where-Object {
        $_.IdentityReference.Value -eq $adminsSid -and
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -eq [System.Security.AccessControl.FileSystemRights]::FullControl
    })
    $broadAllow = [bool]($allows | Where-Object { $broadSids -contains $_.IdentityReference.Value })
    return [ordered]@{
        protected = [bool]$acl.AreAccessRulesProtected
        runner_read = [bool]$runnerRead
        runner_write = [bool]$runnerWrite
        system_full = [bool]$systemFull
        admins_full = [bool]$adminsFull
        broad_allow = [bool]$broadAllow
    }
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
    Write-Output "CI runner loopback firewall: $($Result.runner_loopback_firewall_bound)"
    Write-Output "OWNER evidence ACL protected: $($Result.evidence_acl_protected)"
    Write-Output "CI runner evidence write allowed: $($Result.runner_evidence_write_allowed)"
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
    runner_loopback_firewall_bound = $false
    evidence_acl_protected = $false
    runner_evidence_read_allowed = $false
    runner_evidence_write_allowed = $true
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
        $runnerAuditor,
        $ownerFinalizer,
        $executionContract,
        $externalAccess,
        $localAppFactory,
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
        -not [bool]$verify.runner_loopback_firewall_bound -or
        -not [bool]$verify.tailscale_serve_private -or
        [bool]$verify.funnel_public_ingress -or
        -not [bool]$verify.owner_identity_binding -or
        -not [bool]$verify.secure_server_session -or
        -not [bool]$verify.phone_rehearsal_required
    ) {
        throw "WP22A_PRIVATE_REMOTE_VERIFY_NOT_PASS"
    }

    $runnerSid = Get-RunnerSid
    Remove-Item -LiteralPath $evidencePath -Force -ErrorAction SilentlyContinue
    Set-ProtectedEvidenceAcl -RunnerSid $runnerSid
    $aclState = Get-EvidenceAclState -RunnerSid $runnerSid
    if (
        -not [bool]$aclState.protected -or
        -not [bool]$aclState.runner_read -or
        [bool]$aclState.runner_write -or
        -not [bool]$aclState.system_full -or
        -not [bool]$aclState.admins_full -or
        [bool]$aclState.broad_allow
    ) {
        throw "WP22A_OWNER_EVIDENCE_ACL_INVALID"
    }

    $fingerprint = [ordered]@{
        execution_contract_sha256 = Get-Sha256Lower -Path $executionContract
        external_access_sha256 = Get-Sha256Lower -Path $externalAccess
        local_app_factory_sha256 = Get-Sha256Lower -Path $localAppFactory
        remote_factory_sha256 = Get-Sha256Lower -Path $remoteFactory
        provisioner_sha256 = Get-Sha256Lower -Path $provisioner
        runtime_launcher_sha256 = Get-Sha256Lower -Path $runtimeLauncher
        runner_auditor_sha256 = Get-Sha256Lower -Path $runnerAuditor
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
        runner_loopback_firewall_bound = $true
        evidence_acl_protected = $true
        runner_evidence_read_allowed = $true
        runner_evidence_write_allowed = $false
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
        raw_runner_identity_collected = $false
        raw_runner_sid_collected = $false
        tailscale_auth_material_collected = $false
        private_url_collected = $false
        broker_secret_collected = $false
        private_portfolio_payload_collected = $false
        status = "PASS"
        reason_code = "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED"
    }

    $evidence | ConvertTo-Json -Depth 6 -Compress |
        Set-Content -LiteralPath $evidencePath -Encoding UTF8

    $fileAcl = Get-Acl -LiteralPath $evidencePath -ErrorAction Stop
    if (-not [bool]$fileAcl.AreAccessRulesProtected -and -not [bool]$aclState.protected) {
        throw "WP22A_OWNER_EVIDENCE_FILE_ACL_INVALID"
    }

    $result.status = "PASS"
    $result.reason_code = "WP22A_OWNER_PRIVATE_REMOTE_PHONE_ACCEPTED"
    $result.exact_implementation_binding = $true
    $result.backend_loopback_only = $true
    $result.runner_loopback_firewall_bound = $true
    $result.evidence_acl_protected = $true
    $result.runner_evidence_read_allowed = $true
    $result.runner_evidence_write_allowed = $false
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
