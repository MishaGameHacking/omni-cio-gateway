[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($Apply -and $Verify) { throw "Choose -Apply or -Verify, not both." }
if (($Apply -or $Verify) -and $env:OS -ne "Windows_NT") {
    throw "WP17 READ-vault verification requires Windows."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$wp8Contract = Get-Content -LiteralPath (Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json") -Raw | ConvertFrom-Json
$readSpec = @($wp8Contract.secret_classes | Where-Object { [string]$_.id -eq "broker_read" })
if ($readSpec.Count -ne 1) { throw "Accepted WP8 broker_read class is unavailable." }

$readRoot = [string]$readSpec[0].directory
$tradingSpec = @($wp8Contract.secret_classes | Where-Object { [string]$_.id -eq "broker_trading" })
if ($tradingSpec.Count -ne 1) { throw "Accepted WP8 broker_trading class is unavailable." }
$tradingRoot = [string]$tradingSpec[0].directory
$connectionsRoot = Join-Path $readRoot "connections"
$markerName = ".omni-cio-wp17-read-vault-owned"
$markerValue = "OMNI-CIO-V10-WP17-READ-CONNECTION-VAULT-v1"
$markerPath = Join-Path $connectionsRoot $markerName
$sentinelPath = Join-Path $connectionsRoot "wp17-ci-deny-sentinel.dpapi"
$wp8Marker = Join-Path $readRoot ".omni-cio-wp8-owned"
$wp8MarkerValue = "OMNI-CIO-V10-WP8-NON-SECRET-OWNED-v1"
$runtimeName = [string]$wp8Contract.identities.runtime_role
$evidenceRoot = "C:\ProgramData\OmniCIO\wp17"
$statePath = Join-Path $evidenceRoot "wp17-web-read-vault-state.json"
$runnerRoot = "C:\actions-runner"

Add-Type -AssemblyName System.Security

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

function Get-LocalUserSid {
    param([Parameter(Mandatory = $true)][string]$Name)
    $user = Get-LocalUser -Name $Name -ErrorAction Stop
    if ([bool]$user.Enabled) { throw "WP17 role anchor must remain disabled outside service activation." }
    return $user.SID
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

function Set-ConnectionsAcl {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid
    )
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $RuntimeSid -Rights ([System.Security.AccessControl.FileSystemRights]::Modify) -Inheritance $inherit))
    $runnerRights = [System.Security.AccessControl.FileSystemRights]::ReadPermissions -bor [System.Security.AccessControl.FileSystemRights]::ReadAttributes -bor [System.Security.AccessControl.FileSystemRights]::Traverse
    $acl.AddAccessRule((New-Rule -Sid $RunnerSid -Rights $runnerRights))
    Set-Acl -LiteralPath $connectionsRoot -AclObject $acl -ErrorAction Stop
}

function Protect-LocalMachine {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    return [System.Security.Cryptography.ProtectedData]::Protect(
        $Bytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
}

function Ensure-Sentinel {
    if (-not (Test-Path -LiteralPath $sentinelPath -PathType Leaf)) {
        $plain = New-Object byte[] 32
        $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $rng.GetBytes($plain)
            $protected = Protect-LocalMachine -Bytes $plain
            [System.IO.File]::WriteAllBytes($sentinelPath, $protected)
        }
        finally {
            $rng.Dispose()
            [Array]::Clear($plain, 0, $plain.Length)
        }
    }
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

function Get-AclAssessment {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid
    )
    $acl = Get-Acl -LiteralPath $connectionsRoot -ErrorAction Stop
    $rules = @($acl.Access)
    $runtimeRules = @($rules | Where-Object {
        $ruleSid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $ruleSid -and
        $ruleSid.Value -eq $RuntimeSid.Value -and
        $_.AccessControlType -eq 'Allow'
    })
    $runnerRules = @($rules | Where-Object {
        $ruleSid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $ruleSid -and
        $ruleSid.Value -eq $RunnerSid.Value -and
        $_.AccessControlType -eq 'Allow'
    })
    $broadSidValues = @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")
    $broad = @($rules | Where-Object {
        $ruleSid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $name = [string]$_.IdentityReference
        ($null -ne $ruleSid -and $broadSidValues -contains $ruleSid.Value) -or
        $name -match '(?i)Everyone|Authenticated Users|\\Users$'
    })
    $runtimeModify = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Modify) -eq [System.Security.AccessControl.FileSystemRights]::Modify })
    $runnerReadData = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0 })
    $runnerWrite = [bool]($runnerRules | Where-Object {
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 -or
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 -or
        ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ChangePermissions) -ne 0
    })
    return [ordered]@{
        inheritance_protected = [bool]$acl.AreAccessRulesProtected
        runtime_modify_read_child = $runtimeModify
        runner_read_data = $runnerReadData
        runner_write = $runnerWrite
        broad_read_principal_present = ($broad.Count -gt 0)
    }
}

if (-not (Test-Path -LiteralPath $readRoot -PathType Container)) { throw "WP8 read-broker root is not provisioned." }
if (-not (Test-Path -LiteralPath $wp8Marker -PathType Leaf)) { throw "WP8 read-broker ownership marker missing." }
if ((Get-Content -LiteralPath $wp8Marker -Raw -ErrorAction Stop) -ne $wp8MarkerValue) { throw "WP8 read-broker ownership marker mismatch." }

$runtimeSid = Get-LocalUserSid -Name $runtimeName
$runnerSid = Get-RunnerSid
$tradingAclBefore = if (Test-Path -LiteralPath $tradingRoot -PathType Container) { (Get-Acl -LiteralPath $tradingRoot).Sddl } else { $null }

if ($Apply) {
    if (-not (Test-Administrator)) { throw "WP17 READ-vault apply requires OWNER administrator." }
    if (-not (Test-Path -LiteralPath $connectionsRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $connectionsRoot -Force | Out-Null
        Set-Content -LiteralPath $markerPath -Value $markerValue -Encoding ASCII -NoNewline
    }
    elseif (-not (Test-Path -LiteralPath $markerPath -PathType Leaf)) {
        throw "WP17 refuses to adopt an unmarked existing READ-connections directory."
    }
    if ((Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop) -ne $markerValue) { throw "WP17 READ-vault ownership marker mismatch." }
    Set-ConnectionsAcl -RuntimeSid $runtimeSid -RunnerSid $runnerSid
    Ensure-Sentinel
}

$present = Test-Path -LiteralPath $connectionsRoot -PathType Container
$markerOk = $false
$assessment = $null
if ($present) {
    $markerOk = (Test-Path -LiteralPath $markerPath -PathType Leaf) -and ((Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop) -eq $markerValue)
    $assessment = Get-AclAssessment -RuntimeSid $runtimeSid -RunnerSid $runnerSid
}
$tradingAclAfter = if (Test-Path -LiteralPath $tradingRoot -PathType Container) { (Get-Acl -LiteralPath $tradingRoot).Sddl } else { $null }
$tradingUnchanged = ($tradingAclBefore -eq $tradingAclAfter)

$ready = $present -and $markerOk -and $null -ne $assessment -and $assessment.inheritance_protected -and $assessment.runtime_modify_read_child -and (-not $assessment.runner_read_data) -and (-not $assessment.runner_write) -and (-not $assessment.broad_read_principal_present) -and $tradingUnchanged

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP17"
    read_connection_vault_present = [bool]$present
    ownership_marker_ok = [bool]$markerOk
    runtime_modify_read_child = if ($null -ne $assessment) { [bool]$assessment.runtime_modify_read_child } else { $false }
    runner_read_data_allowed = if ($null -ne $assessment) { [bool]$assessment.runner_read_data } else { $false }
    runner_write_allowed = if ($null -ne $assessment) { [bool]$assessment.runner_write } else { $false }
    broad_read_principal_present = if ($null -ne $assessment) { [bool]$assessment.broad_read_principal_present } else { $false }
    broker_trading_acl_unchanged = [bool]$tradingUnchanged
    real_secret_values_used = $false
    broker_write_authority_added = $false
    trading_methods = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($Apply -or $Verify) {
    if (-not (Test-Path -LiteralPath $evidenceRoot -PathType Container)) { New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null }
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding UTF8
}

if ($AsJson) { $result | ConvertTo-Json -Depth 5 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (($Apply -or $Verify) -and -not $ready) { exit 41 }
if (-not $Apply -and -not $Verify -and -not $ready) { exit 42 }
