[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$provisionerPath = Join-Path $PSScriptRoot "provision_wp17_web_read_vault.ps1"
$evidenceRoot = "C:\ProgramData\OmniCIO\wp17"
$finalEvidencePath = Join-Path $evidenceRoot "owner-read-vault-evidence.sanitized.local.json"
$runnerRoot = "C:\actions-runner"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
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
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
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

function Resolve-IdentitySid {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.IdentityReference]$IdentityReference
    )
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) {
        return [System.Security.Principal.SecurityIdentifier]$IdentityReference
    }
    try {
        return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch [System.Security.Principal.IdentityNotMappedException] {
        return $null
    }
}

function Set-EvidenceAcl {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)

    if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
    }

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

function Get-EvidenceAclAssessment {
    param([Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid)

    $acl = Get-Acl -LiteralPath $evidenceRoot -ErrorAction Stop
    $runnerRules = @($acl.Access | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $sid -and
        $sid.Value -eq $RunnerSid.Value -and
        $_.AccessControlType -eq 'Allow'
    })
    $runnerWrite = [bool]($runnerRules | Where-Object {
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Write) -ne 0 -or
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 -or
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ChangePermissions) -ne 0 -or
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::TakeOwnership) -ne 0
    })
    return [ordered]@{
        inheritance_protected = [bool]$acl.AreAccessRulesProtected
        runner_write_allowed = $runnerWrite
    }
}

function Get-ImplementationSha {
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) {
        throw "REVIEWED_GIT_HEAD_UNAVAILABLE"
    }
    $sha = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($sha -notmatch '^[0-9a-f]{40}$') {
        throw "REVIEWED_GIT_HEAD_INVALID"
    }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "REVIEWED_GIT_STATUS_UNAVAILABLE"
    }
    if ($dirty.Count -ne 0) {
        throw "REVIEWED_WORKTREE_NOT_CLEAN"
    }
    return $sha
}

if (-not (Test-Administrator)) {
    throw "WP17 OWNER evidence finalization requires Administrator."
}
if (-not (Test-Path -LiteralPath $provisionerPath -PathType Leaf)) {
    throw "WP17 READ-vault provisioner is unavailable."
}

$implementationSha = Get-ImplementationSha
$provisionerHash = (Get-FileHash -LiteralPath $provisionerPath -Algorithm SHA256).Hash.ToLowerInvariant()
$finalizerHash = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
$runnerSid = Get-RunnerSid
Set-EvidenceAcl -RunnerSid $runnerSid
$evidenceAcl = Get-EvidenceAclAssessment -RunnerSid $runnerSid

$verifyOutput = @(
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $provisionerPath -Verify -AsJson 2>$null
)
$verifyExit = $LASTEXITCODE
$verifyText = ($verifyOutput -join [Environment]::NewLine).Trim()
$verify = $null
try {
    if (-not [string]::IsNullOrWhiteSpace($verifyText)) {
        $verify = $verifyText | ConvertFrom-Json -ErrorAction Stop
    }
}
catch {
    $verify = $null
}

$ownerVerifyReady = $verifyExit -eq 0 -and $null -ne $verify -and [bool]$verify.ready
$ready = $ownerVerifyReady -and $evidenceAcl.inheritance_protected -and (-not $evidenceAcl.runner_write_allowed)
$reason = if ($ready) { "WP17_OWNER_READ_VAULT_VERIFIED" } else { "WP17_OWNER_READ_VAULT_NOT_READY" }

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP17"
    evidence_type = "OWNER_READ_VAULT"
    reason = $reason
    implementation_sha = $implementationSha
    provisioner_sha256 = $provisionerHash
    evidence_finalizer_sha256 = $finalizerHash
    owner_verify_ready = [bool]$ownerVerifyReady
    read_connection_vault_present = if ($null -ne $verify) { [bool]$verify.read_connection_vault_present } else { $false }
    ownership_marker_ok = if ($null -ne $verify) { [bool]$verify.ownership_marker_ok } else { $false }
    runtime_modify_read_child = if ($null -ne $verify) { [bool]$verify.runtime_modify_read_child } else { $false }
    runner_read_data_allowed = if ($null -ne $verify) { [bool]$verify.runner_read_data_allowed } else { $true }
    runner_write_allowed = if ($null -ne $verify) { [bool]$verify.runner_write_allowed } else { $true }
    broad_read_principal_present = if ($null -ne $verify) { [bool]$verify.broad_read_principal_present } else { $true }
    broker_trading_acl_unchanged = if ($null -ne $verify) { [bool]$verify.broker_trading_acl_unchanged } else { $false }
    evidence_acl_protected = [bool]$evidenceAcl.inheritance_protected
    runner_evidence_write_allowed = [bool]$evidenceAcl.runner_write_allowed
    real_secret_values_used = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $finalEvidencePath -Encoding UTF8

if ($AsJson) {
    $result | ConvertTo-Json -Depth 5
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if (-not $ready) { exit 51 }
