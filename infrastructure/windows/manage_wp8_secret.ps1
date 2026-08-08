[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Set", "Rotate", "Revoke", "MarkCompromised", "Status")]
    [string]$Operation,

    [Parameter(Mandatory = $true)]
    [ValidateSet("broker_read", "broker_trading", "telegram_bot", "local_encryption_key", "external_source")]
    [string]$SecretClass,

    [switch]$AcknowledgeContourReady
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1") {
    throw "Unsupported WP8 secret-store contract schema."
}

$evidenceRoot = [string]$contract.paths.evidence_root
$statePath = Join-Path $evidenceRoot "wp8-secret-store-state.json"
$runnerRoot = "C:\actions-runner"
$runtimeName = [string]$contract.identities.runtime_role
$executionName = [string]$contract.identities.execution_role

Add-Type -AssemblyName System.Security

function Test-Administrator {
    if ($env:OS -ne "Windows_NT") {
        return $false
    }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [System.Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-RunnerServiceSid {
    $serviceNamePattern = '^actions\.runner\.'
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object {
                $pathName = [string]$_.PathName
                $_.Name -match $serviceNamePattern -and
                -not [string]::IsNullOrWhiteSpace($pathName) -and
                $pathName.IndexOf(
                    $runnerRoot,
                    [System.StringComparison]::OrdinalIgnoreCase
                ) -ge 0
            }
    )
    if ($services.Count -ne 1) {
        throw "RUNNER_SERVICE_IDENTITY_UNAVAILABLE"
    }
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
}

function Get-RoleSid {
    param([Parameter(Mandatory = $true)][string]$Name)

    $role = Get-LocalUser -Name $Name -ErrorAction Stop
    return $role.SID
}

function Get-ClassSpec {
    foreach ($spec in @($contract.secret_classes)) {
        if ([string]$spec.id -eq $SecretClass) {
            return $spec
        }
    }
    throw "Unknown WP8 secret class."
}

function Get-ConsumerSid {
    param([Parameter(Mandatory = $true)]$Spec)

    $consumer = [string]$Spec.consumer_role
    if ($consumer -eq $runtimeName) {
        return Get-RoleSid -Name $runtimeName
    }
    if ($consumer -eq $executionName) {
        return Get-RoleSid -Name $executionName
    }
    return $null
}

function New-FileSystemRule {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)]
        [System.Security.AccessControl.FileSystemRights]$Rights
    )

    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        [System.Security.AccessControl.InheritanceFlags]::None,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedFileAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [System.Security.Principal.SecurityIdentifier]$ConsumerSid,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    if ($null -ne $ConsumerSid) {
        $acl.AddAccessRule((New-FileSystemRule -Sid $ConsumerSid -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    }
    $runnerRights = (
        [System.Security.AccessControl.FileSystemRights]::ReadPermissions -bor
        [System.Security.AccessControl.FileSystemRights]::ReadAttributes
    )
    $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights $runnerRights))
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Set-StateFileAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-FileSystemRule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-FileSystemRule -Sid $RunnerSid -Rights ([System.Security.AccessControl.FileSystemRights]::Read)))
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Convert-SecureStringToBytes {
    param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)

    $bstr = [IntPtr]::Zero
    try {
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
        $byteLength = [Runtime.InteropServices.Marshal]::ReadInt32($bstr, -4)
        if ($byteLength -le 0) {
            throw "Empty secret values are not accepted."
        }
        $bytes = New-Object byte[] $byteLength
        [Runtime.InteropServices.Marshal]::Copy($bstr, $bytes, 0, $byteLength)
        return $bytes
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Protect-Wp8Bytes {
    param([Parameter(Mandatory = $true)][byte[]]$PlainBytes)

    return [System.Security.Cryptography.ProtectedData]::Protect(
        $PlainBytes,
        $null,
        [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
}

function Write-EncryptedBlobAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][byte[]]$ProtectedBytes,
        [System.Security.Principal.SecurityIdentifier]$ConsumerSid,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $directory = Split-Path -Parent $Destination
    $temporary = Join-Path $directory (".wp8-" + [Guid]::NewGuid().ToString("N") + ".tmp")
    $backup = Join-Path $directory (".wp8-" + [Guid]::NewGuid().ToString("N") + ".bak")
    try {
        [System.IO.File]::WriteAllBytes($temporary, $ProtectedBytes)
        Set-ProtectedFileAcl -Path $temporary -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid
        if (Test-Path -LiteralPath $Destination -PathType Leaf) {
            [System.IO.File]::Replace($temporary, $Destination, $backup, $true)
            Set-ProtectedFileAcl -Path $Destination -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid
            if (Test-Path -LiteralPath $backup -PathType Leaf) {
                Remove-Item -LiteralPath $backup -Force
            }
        }
        else {
            Move-Item -LiteralPath $temporary -Destination $Destination
            Set-ProtectedFileAcl -Path $Destination -ConsumerSid $ConsumerSid -RunnerSid $RunnerSid
        }
    }
    finally {
        foreach ($path in @($temporary, $backup)) {
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                Remove-Item -LiteralPath $path -Force
            }
        }
    }
}

function Read-State {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        throw "WP8 secret store is not initialized. Run the reviewed provisioner first."
    }
    $state = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop |
        ConvertFrom-Json -ErrorAction Stop
    if ([string]$state.schema_version -ne "1") {
        throw "WP8 sanitized state schema mismatch."
    }
    return $state
}

function Get-StateEntry {
    param([Parameter(Mandatory = $true)]$State)

    foreach ($entry in @($State.classes)) {
        if ([string]$entry.secret_class -eq $SecretClass) {
            return $entry
        }
    }
    throw "WP8 lifecycle metadata is missing for the requested class."
}

function Write-State {
    param(
        [Parameter(Mandatory = $true)]$State,
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $json = $State | ConvertTo-Json -Depth 8
    Set-Content -LiteralPath $statePath -Value $json -Encoding UTF8
    Set-StateFileAcl -Path $statePath -RunnerSid $RunnerSid
}

function Write-SafeStatus {
    param([Parameter(Mandatory = $true)]$Entry)

    Write-Host "WP8 secret class: $SecretClass"
    Write-Host "Lifecycle state: $([string]$Entry.state)"
    Write-Host "Version: $([int]$Entry.version)"
    Write-Host "Provisioned: $([bool]$Entry.provisioned)"
    Write-Host "Compromised: $([bool]$Entry.compromised)"
    Write-Host "Secret value/ciphertext output: NEVER"
}

$spec = Get-ClassSpec
$state = Read-State
$entry = Get-StateEntry -State $state

if ($Operation -eq "Status") {
    Write-SafeStatus -Entry $entry
    exit 0
}

if ($env:GITHUB_ACTIONS -eq "true") {
    throw "WP8 real secret lifecycle changes are forbidden in GitHub Actions."
}
if (-not (Test-Administrator)) {
    throw "WP8 secret lifecycle changes require elevated OWNER-admin PowerShell."
}
if (-not $AcknowledgeContourReady) {
    throw "Secret-changing operations require -AcknowledgeContourReady from the owning contour runbook."
}

$runnerSid = Get-RunnerServiceSid
$consumerSid = Get-ConsumerSid -Spec $spec
$activePath = Join-Path ([string]$spec.directory) ([string]$spec.active_blob)

if (-not (Test-Path -LiteralPath ([string]$spec.directory) -PathType Container)) {
    throw "WP8 class directory is not initialized."
}

if ($Operation -in @("Set", "Rotate")) {
    if ($Operation -eq "Set" -and [bool]$entry.provisioned) {
        throw "Secret is already provisioned; use Rotate."
    }
    if ($Operation -eq "Rotate" -and -not [bool]$entry.provisioned) {
        throw "Secret is not active; use Set."
    }

    Write-Host "Enter the secret locally. Input is masked and will not be logged."
    $secureValue = Read-Host -AsSecureString
    $plainBytes = $null
    $protectedBytes = $null
    try {
        $plainBytes = Convert-SecureStringToBytes -SecureValue $secureValue
        $protectedBytes = Protect-Wp8Bytes -PlainBytes $plainBytes
        Write-EncryptedBlobAtomically `
            -Destination $activePath `
            -ProtectedBytes $protectedBytes `
            -ConsumerSid $consumerSid `
            -RunnerSid $runnerSid
    }
    finally {
        if ($null -ne $plainBytes) {
            [Array]::Clear($plainBytes, 0, $plainBytes.Length)
        }
        if ($null -ne $secureValue) {
            $secureValue.Dispose()
        }
    }

    $entry.state = "ACTIVE"
    $entry.version = ([int]$entry.version) + 1
    $entry.compromised = $false
    $entry.provisioned = $true
    Write-State -State $state -RunnerSid $runnerSid
    Write-Host "WP8 secret lifecycle update: PASS"
    Write-SafeStatus -Entry $entry
    exit 0
}

if ($Operation -eq "Revoke") {
    if (Test-Path -LiteralPath $activePath -PathType Leaf) {
        Remove-Item -LiteralPath $activePath -Force
    }
    $entry.state = "REVOKED"
    $entry.provisioned = $false
    Write-State -State $state -RunnerSid $runnerSid
    Write-Host "WP8 local ciphertext removed. External issuer revocation is still required when applicable."
    Write-SafeStatus -Entry $entry
    exit 0
}

if ($Operation -eq "MarkCompromised") {
    if (Test-Path -LiteralPath $activePath -PathType Leaf) {
        Remove-Item -LiteralPath $activePath -Force
    }
    $entry.state = "COMPROMISED"
    $entry.compromised = $true
    $entry.provisioned = $false
    Write-State -State $state -RunnerSid $runnerSid
    Write-Host "WP8 class marked COMPROMISED; external issuer revoke/rotate is mandatory when applicable."
    Write-SafeStatus -Entry $entry
    exit 0
}

throw "Unsupported WP8 secret lifecycle operation."
