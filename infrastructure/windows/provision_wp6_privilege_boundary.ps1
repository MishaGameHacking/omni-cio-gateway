param(
    [switch]$Apply
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$runtimeName = "omni-cio-runtime"
$executionName = "omni-cio-execution"
$runtimeMarker = "Omni-CIO V10 WP6 runtime role anchor"
$executionMarker = "Omni-CIO V10 WP6 execution role anchor"
$omniRoot = "C:\ProgramData\OmniCIO"
$wp6StateRoot = Join-Path $omniRoot "wp6"
$runnerAclBackupPath = Join-Path $wp6StateRoot "runner-config-acl-backup.json"
$secretRoot = Join-Path $omniRoot "secrets"
$executionRoot = Join-Path $secretRoot "execution"
$sentinelPath = Join-Path $executionRoot "wp6-ci-deny-sentinel.txt"
$sentinelText = "OMNI-CIO-WP6-NON-SECRET-ACL-SENTINEL-v1"
$runnerRoot = "C:\actions-runner"
$runnerConfig = Join-Path $runnerRoot ".runner"
$runnerServiceMarker = Join-Path $runnerRoot ".service"
$runnerSensitiveNames = @(".runner", ".credentials", ".credentials_rsaparams", ".service")

function Assert-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "WP6 provisioning requires an elevated OWNER-admin PowerShell."
    }
}

function Get-RunnerServiceSafe {
    if (-not (Test-Path -LiteralPath $runnerServiceMarker -PathType Leaf)) {
        throw "Fail-closed: reviewed runner root has no .service ownership marker."
    }
    $serviceName = (Get-Content -LiteralPath $runnerServiceMarker -Raw -ErrorAction Stop).Trim()
    if (-not $serviceName.StartsWith("actions.runner.", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Fail-closed: reviewed runner .service marker is not a GitHub Actions runner service."
    }
    $services = @(
        Get-CimInstance Win32_Service |
            Where-Object { $_.Name -eq $serviceName }
    )
    if ($services.Count -ne 1) {
        throw "Expected exactly one GitHub Actions runner service bound to the reviewed runner root; found $($services.Count)."
    }
    return $services[0]
}

function Get-RunnerClass {
    param([string]$StartName)

    $normalized = $StartName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "LOCAL_SYSTEM"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") {
        return "NETWORK_SERVICE"
    }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") {
        return "LOCAL_SERVICE"
    }
    if ($normalized.StartsWith("NT SERVICE\")) {
        return "VIRTUAL_SERVICE"
    }
    return "LOCAL_OR_DOMAIN_USER"
}

function Get-AccountSidValue {
    param([string]$AccountName)

    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "S-1-5-18"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") {
        return "S-1-5-20"
    }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") {
        return "S-1-5-19"
    }
    $account = [System.Security.Principal.NTAccount]::new($AccountName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
}

function New-RandomSecurePassword {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        $plain = [Convert]::ToBase64String($bytes) + "!aA9"
        return ConvertTo-SecureString -String $plain -AsPlainText -Force
    }
    finally {
        $rng.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
        $plain = $null
    }
}

function Get-LocalRole {
    param([string]$Name)
    try {
        return Get-LocalUser -Name $Name -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Assert-RoleOwnership {
    param(
        [string]$Name,
        [string]$Marker
    )

    $existing = Get-LocalRole -Name $Name
    if ($null -ne $existing -and $existing.Description -ne $Marker) {
        throw "Refusing to reuse pre-existing local account '$Name' without the WP6 ownership marker."
    }
}

function Ensure-RoleAnchor {
    param(
        [string]$Name,
        [string]$Marker
    )

    $existing = Get-LocalRole -Name $Name
    if ($null -eq $existing) {
        $password = New-RandomSecurePassword
        try {
            New-LocalUser `
                -Name $Name `
                -Password $password `
                -AccountNeverExpires `
                -PasswordNeverExpires `
                -UserMayNotChangePassword `
                -Description $Marker | Out-Null
        }
        finally {
            $password = $null
        }
    }

    Disable-LocalUser -Name $Name

    $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
    $members = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
    $role = Get-LocalUser -Name $Name -ErrorAction Stop
    if ($members | Where-Object { $_.SID.Value -eq $role.SID.Value }) {
        Remove-LocalGroupMember -Group $adminGroup -Member $role -Confirm:$false
    }

    return $role
}

function New-Rule {
    param(
        [System.Security.Principal.IdentityReference]$Identity,
        [System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance,
        [System.Security.AccessControl.PropagationFlags]$Propagation
    )

    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Identity,
        $Rights,
        $Inheritance,
        $Propagation,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function New-DenyRule {
    param(
        [System.Security.Principal.IdentityReference]$Identity,
        [System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance,
        [System.Security.AccessControl.PropagationFlags]$Propagation
    )

    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Identity,
        $Rights,
        $Inheritance,
        $Propagation,
        [System.Security.AccessControl.AccessControlType]::Deny
    )
}

function Set-OwnerStateDirectoryAcl {
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $none = [System.Security.AccessControl.PropagationFlags]::None
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Identity $systemSid -Rights FullControl -Inheritance $inherit -Propagation $none))
    $acl.AddAccessRule((New-Rule -Identity $adminsSid -Rights FullControl -Inheritance $inherit -Propagation $none))
    Set-Acl -LiteralPath $wp6StateRoot -AclObject $acl
}

function Get-RunnerSensitivePaths {
    return @(
        foreach ($name in $runnerSensitiveNames) {
            $path = Join-Path $runnerRoot $name
            if (Test-Path -LiteralPath $path -PathType Leaf) {
                $path
            }
        }
    )
}

function Save-RunnerAclBackup {
    param([string[]]$Paths)

    if (Test-Path -LiteralPath $runnerAclBackupPath) {
        $existing = Get-Content -LiteralPath $runnerAclBackupPath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        $names = @($existing.files | ForEach-Object { [string]$_.name })
        if ($existing.schema_version -ne "1" -or "." -notin $names) {
            throw "Existing WP6 runner ACL backup is incomplete; refusing to overwrite it."
        }
        return
    }

    $rootAcl = Get-Acl -LiteralPath $runnerRoot -ErrorAction Stop
    $entries = @()
    $entries += [ordered]@{
        name = "."
        sddl = $rootAcl.Sddl
    }
    foreach ($path in $Paths) {
        $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
        $entries += [ordered]@{
            name = [System.IO.Path]::GetFileName($path)
            sddl = $acl.Sddl
        }
    }

    $payload = [ordered]@{
        schema_version = "1"
        files = $entries
    } | ConvertTo-Json -Depth 5
    Set-Content -LiteralPath $runnerAclBackupPath -Value $payload -Encoding UTF8
}

function Set-RunnerRootDenyAcl {
    param(
        [System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [System.Security.Principal.SecurityIdentifier]$ExecutionSid
    )

    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $none = [System.Security.AccessControl.PropagationFlags]::None
    $acl = Get-Acl -LiteralPath $runnerRoot -ErrorAction Stop
    $acl.SetAccessRule(
        (New-DenyRule -Identity $RuntimeSid -Rights FullControl -Inheritance $inherit -Propagation $none)
    )
    $acl.SetAccessRule(
        (New-DenyRule -Identity $ExecutionSid -Rights FullControl -Inheritance $inherit -Propagation $none)
    )
    Set-Acl -LiteralPath $runnerRoot -AclObject $acl
}

function Set-RunnerSensitiveFileAcl {
    param(
        [string]$Path,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $noneInheritance = [System.Security.AccessControl.InheritanceFlags]::None
    $nonePropagation = [System.Security.AccessControl.PropagationFlags]::None

    $acl = [System.Security.AccessControl.FileSecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Identity $systemSid -Rights FullControl -Inheritance $noneInheritance -Propagation $nonePropagation))
    $acl.AddAccessRule((New-Rule -Identity $adminsSid -Rights FullControl -Inheritance $noneInheritance -Propagation $nonePropagation))
    $acl.AddAccessRule((New-Rule -Identity $RunnerSid -Rights Modify -Inheritance $noneInheritance -Propagation $nonePropagation))
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Set-ExecutionDirectoryAcl {
    param(
        [System.Security.Principal.SecurityIdentifier]$ExecutionSid,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
        [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $noneInheritance = [System.Security.AccessControl.InheritanceFlags]::None
    $nonePropagation = [System.Security.AccessControl.PropagationFlags]::None

    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Identity $systemSid -Rights FullControl -Inheritance $inherit -Propagation $nonePropagation))
    $acl.AddAccessRule((New-Rule -Identity $adminsSid -Rights FullControl -Inheritance $inherit -Propagation $nonePropagation))
    $acl.AddAccessRule((New-Rule -Identity $ExecutionSid -Rights ReadAndExecute -Inheritance $inherit -Propagation $nonePropagation))
    $acl.AddAccessRule((New-Rule -Identity $RunnerSid -Rights ReadPermissions -Inheritance $noneInheritance -Propagation $nonePropagation))
    Set-Acl -LiteralPath $executionRoot -AclObject $acl
}

function Set-SentinelAcl {
    param(
        [System.Security.Principal.SecurityIdentifier]$ExecutionSid,
        [System.Security.Principal.SecurityIdentifier]$RunnerSid
    )

    $noneInheritance = [System.Security.AccessControl.InheritanceFlags]::None
    $nonePropagation = [System.Security.AccessControl.PropagationFlags]::None

    # The execution directory is the authoritative ACL source. Re-enable inheritance
    # first so a previously protected/broken sentinel can recover the reviewed
    # execution ReadAndExecute ACE, then freeze the inherited rules as explicit rules.
    $acl = Get-Acl -LiteralPath $sentinelPath -ErrorAction Stop
    $acl.SetAccessRuleProtection($false, $true)
    Set-Acl -LiteralPath $sentinelPath -AclObject $acl

    $acl = Get-Acl -LiteralPath $sentinelPath -ErrorAction Stop
    $acl.SetAccessRuleProtection($true, $true)
    $acl.SetAccessRule(
        (New-Rule -Identity $RunnerSid -Rights ReadPermissions -Inheritance $noneInheritance -Propagation $nonePropagation)
    )
    Set-Acl -LiteralPath $sentinelPath -AclObject $acl

    # Fail closed if Windows did not persist the intended execution grant or if
    # the runner accidentally received file-data read authority.
    $applied = Get-Acl -LiteralPath $sentinelPath -ErrorAction Stop
    $rules = $applied.GetAccessRules(
        $true,
        $true,
        [System.Security.Principal.SecurityIdentifier]
    )
    $executionReadMask = [int64][System.Security.AccessControl.FileSystemRights]::Read
    $runnerDataReadMask = [int64][System.Security.AccessControl.FileSystemRights]::ReadData
    $executionReadPresent = $false
    $runnerDataReadPresent = $false
    foreach ($rule in $rules) {
        if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
            continue
        }
        $ruleSid = [string]$rule.IdentityReference.Value
        $rights = [int64]$rule.FileSystemRights
        if ($ruleSid -eq $ExecutionSid.Value -and (($rights -band $executionReadMask) -ne 0)) {
            $executionReadPresent = $true
        }
        if ($ruleSid -eq $RunnerSid.Value -and (($rights -band $runnerDataReadMask) -ne 0)) {
            $runnerDataReadPresent = $true
        }
    }
    if (-not $executionReadPresent) {
        throw "Fail-closed: execution role read grant was not persisted on the WP6 sentinel."
    }
    if ($runnerDataReadPresent) {
        throw "Fail-closed: runner received sentinel data-read authority."
    }
}

$runner = Get-RunnerServiceSafe
$runnerClass = Get-RunnerClass -StartName $runner.StartName
$runnerSidValue = Get-AccountSidValue -AccountName $runner.StartName
$runnerSid = [System.Security.Principal.SecurityIdentifier]::new($runnerSidValue)
$runnerSensitivePaths = @(Get-RunnerSensitivePaths)
if ($runnerClass -eq "LOCAL_SYSTEM") {
    throw "Fail-closed: GitHub runner uses LocalSystem. WP6 will not provision around a privileged CI identity."
}
if ($runner.State -ne "Running") {
    throw "Fail-closed: GitHub runner service is not running."
}
if (-not (Test-Path -LiteralPath $runnerConfig)) {
    throw "Fail-closed: GitHub runner configuration is not present at the reviewed runner root."
}
if ($runnerSensitivePaths.Count -lt 1) {
    throw "Fail-closed: no reviewed GitHub runner configuration files were found."
}

Assert-RoleOwnership -Name $runtimeName -Marker $runtimeMarker
Assert-RoleOwnership -Name $executionName -Marker $executionMarker

Write-Host "WP6 privilege provisioning preflight: PASS" -ForegroundColor Green
Write-Host "Runner service bound to reviewed runner root: YES"
Write-Host "Runner account class: $runnerClass"
Write-Host "Runner sensitive config files found: $($runnerSensitivePaths.Count)"
Write-Host "Real secret values used: NO"
Write-Host "Runtime role anchor: $runtimeName (disabled)"
Write-Host "Execution role anchor: $executionName (disabled)"
Write-Host "Sentinel: non-secret ACL test material only"

if (-not $Apply) {
    Write-Host "DRY RUN ONLY. Re-run with -Apply after reviewed CI is green." -ForegroundColor Yellow
    exit 0
}

Assert-Administrator

if (Test-Path -LiteralPath $sentinelPath) {
    $existingSentinel = Get-Content -LiteralPath $sentinelPath -Raw -ErrorAction Stop
    if ($existingSentinel.Trim() -ne $sentinelText) {
        throw "Refusing to replace unexpected content at the WP6 sentinel path."
    }
}
if ((Test-Path -LiteralPath $secretRoot) -and -not (Test-Path -LiteralPath $sentinelPath)) {
    $unexpected = @(Get-ChildItem -LiteralPath $secretRoot -Force -ErrorAction Stop)
    if ($unexpected.Count -gt 0) {
        throw "Refusing to modify a non-empty pre-existing secret root before WP8 owns real secret provisioning."
    }
}

if (-not (Test-Path -LiteralPath $omniRoot)) {
    New-Item -ItemType Directory -Path $omniRoot -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $wp6StateRoot)) {
    New-Item -ItemType Directory -Path $wp6StateRoot -Force | Out-Null
}
Set-OwnerStateDirectoryAcl
Save-RunnerAclBackup -Paths $runnerSensitivePaths

$runtimeRole = Ensure-RoleAnchor -Name $runtimeName -Marker $runtimeMarker
$executionRole = Ensure-RoleAnchor -Name $executionName -Marker $executionMarker
Set-RunnerRootDenyAcl -RuntimeSid $runtimeRole.SID -ExecutionSid $executionRole.SID
foreach ($path in $runnerSensitivePaths) {
    Set-RunnerSensitiveFileAcl -Path $path -RunnerSid $runnerSid
}

if (-not (Test-Path -LiteralPath $secretRoot)) {
    New-Item -ItemType Directory -Path $secretRoot -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $executionRoot)) {
    New-Item -ItemType Directory -Path $executionRoot -Force | Out-Null
}

Set-ExecutionDirectoryAcl -ExecutionSid $executionRole.SID -RunnerSid $runnerSid
Set-Content -LiteralPath $sentinelPath -Value $sentinelText -Encoding ASCII -NoNewline
Set-SentinelAcl -ExecutionSid $executionRole.SID -RunnerSid $runnerSid

Write-Host "WP6 local identity/ACL provisioning applied." -ForegroundColor Green
Write-Host "Both role accounts are disabled and non-admin; no real secret was created." -ForegroundColor Green
Write-Host "Runtime and execution identities are explicitly denied access to the entire runner root." -ForegroundColor Green
Write-Host "Sensitive runner config ACLs are limited to SYSTEM, Administrators and the runner service identity." -ForegroundColor Green
Write-Host "Runner can inspect sentinel ACL metadata but has no sentinel data-read grant." -ForegroundColor Green
Write-Host "Original runner-root/config ACLs were backed up locally for guarded rollback." -ForegroundColor Green
Write-Host "Run the privacy-safe WP6 identity audit next." -ForegroundColor Cyan