[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp22a_private_remote_access.ps1"
$omniStateRoot = Join-Path $env:ProgramData "OmniCIO"
$resultRoot = Join-Path $omniStateRoot "diagnostics"
$resultPath = Join-Path $resultRoot "wp22a-owner-apply.sanitized.local.json"
$normalizedExpectedSha = $ExpectedImplementationSha.Trim().ToLowerInvariant()
$recordedImplementationSha = if ($normalizedExpectedSha -match '^[0-9a-f]{40}$') {
    $normalizedExpectedSha
}
else {
    $null
}

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
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

function Set-ProtectedResultRoot {
    if ([string]::IsNullOrWhiteSpace([string]$env:ProgramData)) {
        throw "WP22A_PROGRAMDATA_UNAVAILABLE"
    }

    # Reject any pre-existing redirected parent/root before creating the
    # diagnostics descendant. Re-check after creation before applying ACLs so
    # the safe-result path never follows an unreviewed junction or symlink.
    foreach ($path in @($omniStateRoot, $resultRoot)) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "WP22A_SAFE_RESULT_ROOT_REPARSE_POINT_FORBIDDEN"
        }
    }

    New-Item -ItemType Directory -Path $resultRoot -Force | Out-Null
    foreach ($path in @($omniStateRoot, $resultRoot)) {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "WP22A_SAFE_RESULT_ROOT_REPARSE_POINT_FORBIDDEN"
        }
    }

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = (
        [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    )
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-AllowRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    Set-Acl -LiteralPath $resultRoot -AclObject $acl -ErrorAction Stop

    $applied = Get-Acl -LiteralPath $resultRoot -ErrorAction Stop
    if (-not [bool]$applied.AreAccessRulesProtected) {
        throw "WP22A_SAFE_RESULT_ACL_NOT_PROTECTED"
    }
}

function Set-ProtectedResultFileAcl {
    $item = Get-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) { return }
    if (
        [bool]$item.PSIsContainer -or
        ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    ) {
        throw "WP22A_SAFE_RESULT_FILE_BOUNDARY_INVALID"
    }

    # File.Replace preserves the DACL of the destination file on Windows. A
    # pre-created permissive result file must therefore be hardened before the
    # atomic replace, then verified again after replace/move.
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $none = [System.Security.AccessControl.InheritanceFlags]::None
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AllowRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $none))
    $acl.AddAccessRule((New-AllowRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $none))
    Set-Acl -LiteralPath $resultPath -AclObject $acl -ErrorAction Stop

    $applied = Get-Acl -LiteralPath $resultPath -ErrorAction Stop
    $rules = @(
        $applied.GetAccessRules(
            $true,
            $false,
            [System.Security.Principal.SecurityIdentifier]
        )
    )
    $allowedSids = @($systemSid.Value, $adminsSid.Value)
    $unexpected = @(
        $rules | Where-Object {
            $_.AccessControlType -ne "Allow" -or
            $allowedSids -notcontains $_.IdentityReference.Value
        }
    )
    $systemFull = [bool]($rules | Where-Object {
        $_.IdentityReference.Value -eq $systemSid.Value -and
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -eq [System.Security.AccessControl.FileSystemRights]::FullControl
    })
    $adminsFull = [bool]($rules | Where-Object {
        $_.IdentityReference.Value -eq $adminsSid.Value -and
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::FullControl) -eq [System.Security.AccessControl.FileSystemRights]::FullControl
    })
    if (
        -not [bool]$applied.AreAccessRulesProtected -or
        $unexpected.Count -ne 0 -or
        -not $systemFull -or
        -not $adminsFull
    ) {
        throw "WP22A_SAFE_RESULT_FILE_ACL_INVALID"
    }
}

function Get-SafeReasonCode {
    param(
        [AllowNull()][string]$Text,
        [Parameter(Mandatory = $true)][string]$Fallback
    )

    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        $apply = [regex]::Match(
            $Text,
            'WP22A_APPLY_FAILED:(?:WP15|WP17|WP22A)_[A-Z0-9_]+;LOCAL_ROLLBACK_(?:PASS|FAILED:(?:WP15|WP17|WP22A)_[A-Z0-9_]+)'
        )
        if ($apply.Success) { return [string]$apply.Value }

        $codes = [regex]::Matches(
            $Text,
            '(?<![A-Z0-9_])(?:WP15|WP17|WP22A)_[A-Z0-9_]+'
        )
        if ($codes.Count -gt 0) {
            return [string]$codes[$codes.Count - 1].Value
        }
    }
    return $Fallback
}

function Save-SanitizedResult {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)

    Set-ProtectedResultRoot
    Set-ProtectedResultFileAcl
    $temporaryPath = Join-Path $resultRoot (".{0}.tmp" -f [Guid]::NewGuid().ToString("N"))
    try {
        $json = $Result | ConvertTo-Json -Depth 5 -Compress
        $utf8 = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText(
            $temporaryPath,
            $json + [Environment]::NewLine,
            $utf8
        )
        if ([System.IO.File]::Exists($resultPath)) {
            [System.IO.File]::Replace($temporaryPath, $resultPath, $null, $true)
        }
        else {
            [System.IO.File]::Move($temporaryPath, $resultPath)
        }
        Set-ProtectedResultFileAcl
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}

function Write-Summary {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)

    if ($AsJson) {
        $Result | ConvertTo-Json -Depth 5 -Compress
        return
    }
    foreach ($key in $Result.Keys) {
        Write-Output ("{0}: {1}" -f $key, $Result[$key])
    }
}

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_class = "OWNER_APPLY_SANITIZED_LOCAL_RESULT"
    attempt_id = [Guid]::NewGuid().ToString("N")
    started_at_utc = [DateTime]::UtcNow.ToString("o")
    completed_at_utc = $null
    implementation_sha = $recordedImplementationSha
    status = "PENDING"
    reason = "WP22A_OWNER_APPLY_NOT_STARTED"
    apply_reason = $null
    child_process_started = $false
    child_exit_code = $null
    captured_output_present = $false
    captured_item_count = 0
    exact_implementation_binding = $null
    backend_loopback_only = $null
    runner_loopback_firewall_bound = $null
    remote_runtime_batch_logon_bound = $null
    tailscale_serve_private = $null
    funnel_public_ingress = $null
    local_serve_identity_spoof_denied = $null
    owner_identity_binding = $null
    secure_server_session = $null
    private_external_url_present = $null
    phone_rehearsal_required = $null
    local_rollback_pass = $null
    sanitized_result_persisted = $false
    result_acl_protected = $false
    raw_child_output_persisted = $false
    raw_child_output_emitted = $false
    private_url_persisted = $false
    private_url_emitted = $false
    private_identity_persisted = $false
    secret_value_persisted = $false
}

$captured = @()
$capturedLines = @()
$capturedText = $null
$jsonCandidates = @()
$payload = $null
$storeReady = $false
$exitCode = 2
try {
    if ($null -eq $recordedImplementationSha) {
        throw "WP22A_EXPECTED_SHA_INVALID"
    }
    if (-not (Test-Administrator)) {
        throw "WP22A_OWNER_APPLY_REQUIRES_ADMINISTRATOR"
    }
    if (-not (Test-Path -LiteralPath $provisioner -PathType Leaf)) {
        throw "WP22A_OWNER_APPLY_PROVISIONER_MISSING"
    }

    # Persist an attempt marker before the mutating child starts. If the OWNER
    # console later closes, a new Administrator session can distinguish a lost
    # console from a never-started attempt without reading raw child output.
    $result.status = "RUNNING"
    $result.reason = "WP22A_OWNER_APPLY_IN_PROGRESS"
    $result.sanitized_result_persisted = $true
    $result.result_acl_protected = $true
    try {
        Save-SanitizedResult -Result $result
        $storeReady = $true
    }
    catch {
        $result.status = "FAIL"
        $result.reason = "WP22A_SAFE_RESULT_PERSIST_FAILED"
        $result.sanitized_result_persisted = $false
        $result.result_acl_protected = $false
        $exitCode = 3
        throw "WP22A_SAFE_RESULT_PERSIST_FAILED"
    }

    $result.child_process_started = $true
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $captured = @(
            & powershell.exe `
                -NoProfile `
                -NonInteractive `
                -ExecutionPolicy Bypass `
                -File $provisioner `
                -ExpectedImplementationSha $recordedImplementationSha `
                -Apply `
                -Port $Port `
                -AsJson 2>&1
        )
        $result.child_exit_code = [int]$LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $capturedLines = @($captured | ForEach-Object { [string]$_ })
    $capturedText = $capturedLines -join [Environment]::NewLine
    $result.captured_item_count = [int]$capturedLines.Count
    $result.captured_output_present = [bool]($capturedLines.Count -gt 0)

    $jsonCandidates = @(
        $capturedLines |
            Where-Object { $_.TrimStart().StartsWith("{") }
    )
    for ($index = $jsonCandidates.Count - 1; $index -ge 0; $index--) {
        try {
            $payload = $jsonCandidates[$index] | ConvertFrom-Json -ErrorAction Stop
            break
        }
        catch { }
    }

    if ($null -ne $result.child_exit_code -and [int]$result.child_exit_code -eq 0) {
        if (
            $null -eq $payload -or
            [string]$payload.status -ne "PASS" -or
            [string]$payload.reason -ne "WP22A_PRIVATE_REMOTE_INFRASTRUCTURE_ACCEPTED" -or
            -not [bool]$payload.exact_implementation_binding -or
            -not [bool]$payload.backend_loopback_only -or
            -not [bool]$payload.runner_loopback_firewall_bound -or
            -not [bool]$payload.remote_runtime_batch_logon_bound -or
            -not [bool]$payload.tailscale_serve_private -or
            [bool]$payload.funnel_public_ingress -or
            -not [bool]$payload.local_serve_identity_spoof_denied -or
            $null -ne $payload.owner_identity_binding -or
            $null -ne $payload.secure_server_session -or
            [string]::IsNullOrWhiteSpace([string]$payload.external_url) -or
            -not [bool]$payload.phone_rehearsal_required
        ) {
            throw "WP22A_OWNER_APPLY_RESULT_INVALID"
        }
        $result.status = "PASS"
        $result.reason = [string]$payload.reason
        $result.exact_implementation_binding = [bool]$payload.exact_implementation_binding
        $result.backend_loopback_only = [bool]$payload.backend_loopback_only
        $result.runner_loopback_firewall_bound = [bool]$payload.runner_loopback_firewall_bound
        $result.remote_runtime_batch_logon_bound = [bool]$payload.remote_runtime_batch_logon_bound
        $result.tailscale_serve_private = [bool]$payload.tailscale_serve_private
        $result.funnel_public_ingress = [bool]$payload.funnel_public_ingress
        $result.local_serve_identity_spoof_denied = [bool]$payload.local_serve_identity_spoof_denied
        $result.owner_identity_binding = $null
        $result.secure_server_session = $null
        $result.private_external_url_present = -not [string]::IsNullOrWhiteSpace([string]$payload.external_url)
        $result.phone_rehearsal_required = [bool]$payload.phone_rehearsal_required
        $exitCode = 0
    }
    else {
        $result.status = "FAIL"
        $result.reason = Get-SafeReasonCode `
            -Text $capturedText `
            -Fallback "WP22A_OWNER_APPLY_CHILD_FAILED"
        if ($result.reason -match ';LOCAL_ROLLBACK_PASS$') {
            $result.local_rollback_pass = $true
        }
        elseif ($result.reason -match ';LOCAL_ROLLBACK_FAILED:') {
            $result.local_rollback_pass = $false
        }
    }
}
catch {
    if ([string]$result.reason -ne "WP22A_SAFE_RESULT_PERSIST_FAILED") {
        $result.status = "FAIL"
        $result.reason = Get-SafeReasonCode `
            -Text ([string]$_.Exception.Message) `
            -Fallback "WP22A_OWNER_APPLY_WRAPPER_FAILED"
        $exitCode = 2
    }
}
finally {
    $captured = @()
    $capturedLines = @()
    $capturedText = $null
    $jsonCandidates = @()
    $payload = $null
}

$result.completed_at_utc = [DateTime]::UtcNow.ToString("o")
if ($storeReady) {
    try {
        Save-SanitizedResult -Result $result
    }
    catch {
        $result.apply_reason = [string]$result.reason
        $result.status = "FAIL"
        $result.reason = "WP22A_SAFE_RESULT_PERSIST_FAILED"
        $result.sanitized_result_persisted = $false
        $result.result_acl_protected = $false
        $exitCode = 3
    }
}

Write-Summary -Result $result
if ($exitCode -ne 0) { exit $exitCode }
exit 0
