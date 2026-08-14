[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$Apply,
    [switch]$Verify,
    [switch]$Cleanup,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [string]$ConfigPath = "C:\ProgramData\OmniCIO\wp22a\private-remote.json"
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = @($Apply, $Verify, $Cleanup | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw "Choose exactly one of -Apply, -Verify, or -Cleanup." }
if ($env:OS -ne "Windows_NT") { throw "WP22A private remote runtime provisioning requires Windows." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configurator = Join-Path $PSScriptRoot "configure_wp22a_tailscale_serve.ps1"
$launcherRelative = "infrastructure\windows\run_wp22a_private_remote_runtime.ps1"
$bootstrapDbRelative = "infrastructure\windows\bootstrap_wp15_live_database.py"
$runtimeName = "omni-cio-runtime"
$runtimeOwnershipMarker = "Omni-CIO V10 WP6 runtime role anchor"
$taskName = "OmniCIO.V10.WP22APrivateRemoteAcceptance"
$taskDescription = "OMNI-CIO-V10-WP22A-PRIVATE-REMOTE-ACCEPTANCE-v1"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-private"
$runtimeMarker = Join-Path $runtimeRoot ".omni-cio-wp22a-private-owned"
$runtimeMarkerValue = "OMNI-CIO-V10-WP22A-PRIVATE-RUNTIME-v1"
$appRoot = Join-Path $runtimeRoot "app"
$deploymentMarker = Join-Path $appRoot ".omni-cio-wp22a-private-deployment"
$venvRoot = Join-Path $runtimeRoot "venv"
$backupRoot = Join-Path $runtimeRoot "postgres-backup"
$backupMarker = Join-Path $backupRoot ".omni-cio-wp22a-postgres-backup"
$backupMarkerValue = "OMNI-CIO-V10-WP22A-POSTGRES-BACKUP-v1"
$hbaBackup = Join-Path $backupRoot "pg_hba.conf.pre-wp22a"
$identBackup = Join-Path $backupRoot "pg_ident.conf.pre-wp22a"
$pythonMachine = "C:\Program Files\Python314\python.exe"
$nodeExe = "C:\Program Files\nodejs\node.exe"
$npmCmd = "C:\Program Files\nodejs\npm.cmd"
$psqlExe = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
$pgCtlExe = "C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe"
$managedBegin = "# BEGIN OMNI-CIO V10 WP22A PRIVATE REMOTE"
$managedEnd = "# END OMNI-CIO V10 WP22A PRIVATE REMOTE"
$runnerRoot = "C:\actions-runner"
$batchRight = "SeBatchLogonRight"
$denyBatchRight = "SeDenyBatchLogonRight"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-IdentitySid {
    param([Parameter(Mandatory = $true)][System.Security.Principal.IdentityReference]$IdentityReference)
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) { return $IdentityReference }
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
    if ($services.Count -ne 1) { throw "WP22A_RUNNER_SERVICE_IDENTITY_UNAVAILABLE" }
    $account = [System.Security.Principal.NTAccount]::new([string]$services[0].StartName)
    return $account.Translate([System.Security.Principal.SecurityIdentifier])
}

function Get-RuntimeUser {
    $user = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    if ([string]$user.Description -ne $runtimeOwnershipMarker) { throw "WP22A_RUNTIME_ROLE_OWNERSHIP_INVALID" }
    $administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $admins = @(Get-LocalGroupMember -SID $administratorsSid -ErrorAction Stop)
    if ($admins.SID.Value -contains $user.SID.Value) { throw "WP22A_RUNTIME_IS_ADMINISTRATOR" }
    return $user
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

function Set-ProtectedDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$RuntimeRights,
        [switch]$IncludeRuntime
    )
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    if ($IncludeRuntime) {
        $acl.AddAccessRule((New-Rule -Sid $RuntimeSid -Rights $RuntimeRights -Inheritance $inherit))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Test-DirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RuntimeSid,
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$RunnerSid
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [ordered]@{ present = $false; protected = $false; runtime_read = $false; runtime_write = $true; runner_read = $true; runner_write = $true; broad = $true }
    }
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    $rules = @($acl.Access)
    $runtimeRules = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $sid -and $sid.Value -eq $RuntimeSid.Value -and $_.AccessControlType -eq 'Allow'
    })
    $runnerRules = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $null -ne $sid -and $sid.Value -eq $RunnerSid.Value -and $_.AccessControlType -eq 'Allow'
    })
    $broadSidValues = @("S-1-1-0", "S-1-5-11", "S-1-5-32-545")
    $broad = @($rules | Where-Object {
        $sid = Resolve-IdentitySid -IdentityReference $_.IdentityReference
        $name = [string]$_.IdentityReference
        ($null -ne $sid -and $broadSidValues -contains $sid.Value) -or $name -match '(?i)Everyone|Authenticated Users|\\Users$'
    })
    $runtimeRead = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0 })
    $runtimeWrite = [bool]($runtimeRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 -or ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 })
    $runnerRead = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0 })
    $runnerWrite = [bool]($runnerRules | Where-Object { ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::WriteData) -ne 0 -or ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Delete) -ne 0 })
    return [ordered]@{
        present = $true
        protected = [bool]$acl.AreAccessRulesProtected
        runtime_read = $runtimeRead
        runtime_write = $runtimeWrite
        runner_read = $runnerRead
        runner_write = $runnerWrite
        broad = ($broad.Count -gt 0)
    }
}

function Get-PostgresDataRoot {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -match '(?i)postgres' -and [string]$_.PathName -match '(?i)\s-D\s+' }
    )
    $candidates = @()
    foreach ($service in $services) {
        $pathName = [string]$service.PathName
        $match = [regex]::Match($pathName, '(?i)(?:^|\s)-D\s+(?:"([^"]+)"|(\S+))')
        if ($match.Success) {
            $candidate = if (-not [string]::IsNullOrWhiteSpace($match.Groups[1].Value)) { $match.Groups[1].Value } else { $match.Groups[2].Value }
            if (Test-Path -LiteralPath (Join-Path $candidate "PG_VERSION") -PathType Leaf) {
                $major = (Get-Content -LiteralPath (Join-Path $candidate "PG_VERSION") -Raw).Trim()
                if ($major -eq "18") { $candidates += $candidate }
            }
        }
    }
    $unique = @($candidates | Select-Object -Unique)
    if ($unique.Count -ne 1) { throw "WP22A_POSTGRES18_DATA_ROOT_UNAVAILABLE" }
    return [string]$unique[0]
}

function Quote-PgField {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + $Value.Replace('"', '""') + '"'
}

function Convert-NtAccountToSspiPrincipal {
    param([Parameter(Mandatory = $true)][string]$Value)
    $separator = $Value.IndexOf('\')
    if ($separator -lt 1 -or $separator -ge ($Value.Length - 1)) { throw "WP22A_SSPI_ACCOUNT_NAME_INVALID" }
    $realm = $Value.Substring(0, $separator).Trim()
    $user = $Value.Substring($separator + 1).Trim()
    if ([string]::IsNullOrWhiteSpace($realm) -or [string]::IsNullOrWhiteSpace($user)) { throw "WP22A_SSPI_ACCOUNT_NAME_INVALID" }
    return $user + "@" + $realm
}

function Remove-ManagedBlock {
    param([Parameter(Mandatory = $true)][string]$Text)
    $pattern = '(?ms)^' + [regex]::Escape($managedBegin) + '.*?^' + [regex]::Escape($managedEnd) + '\r?\n?'
    return [regex]::Replace($Text, $pattern, '')
}

function Set-ManagedConfigBlock {
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string[]]$Lines)
    $original = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
    $clean = Remove-ManagedBlock -Text $original
    $block = @($managedBegin) + $Lines + @($managedEnd)
    $text = ($block -join "`r`n") + "`r`n" + $clean.TrimStart("`r", "`n")
    [System.IO.File]::WriteAllText($Path, $text, [System.Text.UTF8Encoding]::new($false))
}

function Reload-Postgres {
    param([Parameter(Mandatory = $true)][string]$DataRoot)
    & $pgCtlExe reload -D $DataRoot -s *> $null
    if ($LASTEXITCODE -ne 0) { throw "WP22A_POSTGRES_RELOAD_FAILED" }
}

function Invoke-PsqlText {
    param([Parameter(Mandatory = $true)][string]$Database, [Parameter(Mandatory = $true)][string]$Sql)
    $sqlPath = Join-Path $env:TEMP ("omni-cio-wp22a-" + [guid]::NewGuid().ToString("N") + ".sql")
    try {
        [System.IO.File]::WriteAllText($sqlPath, $Sql, [System.Text.UTF8Encoding]::new($false))
        $previousRequireAuth = $env:PGREQUIREAUTH
        $env:PGREQUIREAUTH = "sspi"
        try {
            & $psqlExe -X -q -v ON_ERROR_STOP=1 -h 127.0.0.1 -U postgres -d $Database -f $sqlPath *> $null
            if ($LASTEXITCODE -ne 0) { throw "WP22A_POSTGRES_ADMIN_SQL_FAILED" }
        }
        finally { $env:PGREQUIREAUTH = $previousRequireAuth }
    }
    finally { Remove-Item -LiteralPath $sqlPath -Force -ErrorAction SilentlyContinue }
}

function Invoke-MigrationsAsOwnerSspi {
    param([Parameter(Mandatory = $true)][string]$PythonPath)
    $previous = @{
        PGHOST = $env:PGHOST; PGPORT = $env:PGPORT; PGDATABASE = $env:PGDATABASE;
        PGUSER = $env:PGUSER; PGREQUIREAUTH = $env:PGREQUIREAUTH; PYTHONDONTWRITEBYTECODE = $env:PYTHONDONTWRITEBYTECODE
    }
    $env:PGHOST = "127.0.0.1"
    $env:PGPORT = "5432"
    $env:PGDATABASE = "omni_cio_v10"
    $env:PGUSER = "postgres"
    $env:PGREQUIREAUTH = "sspi"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    Push-Location -LiteralPath $appRoot
    try {
        & $PythonPath (Join-Path $appRoot $bootstrapDbRelative) *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP22A_DATABASE_MIGRATION_FAILED" }
    }
    finally {
        Pop-Location
        foreach ($name in $previous.Keys) {
            if ($null -eq $previous[$name]) { Remove-Item -Path ("Env:" + $name) -ErrorAction SilentlyContinue }
            else { Set-Item -Path ("Env:" + $name) -Value $previous[$name] }
        }
    }
}

function New-RandomRuntimePassword {
    $bytes = New-Object byte[] 36
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        return ([Convert]::ToBase64String($bytes) + "!Aa1")
    }
    finally {
        $rng.Dispose()
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
}

function Stop-And-RemoveTask {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        if ([string]$task.Description -ne $taskDescription) { throw "WP22A_REFUSES_UNOWNED_TASK" }
        try { Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue } catch { }
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
    }
}

function Restore-PostgresConfig {
    if (-not (Test-Path -LiteralPath $backupRoot -PathType Container)) { return $false }
    if (-not (Test-Path -LiteralPath $backupMarker -PathType Leaf)) { throw "WP22A_POSTGRES_BACKUP_UNOWNED" }
    if ((Get-Content -LiteralPath $backupMarker -Raw).Trim() -ne $backupMarkerValue) { throw "WP22A_POSTGRES_BACKUP_MARKER_MISMATCH" }
    if (-not (Test-Path -LiteralPath $hbaBackup -PathType Leaf) -or -not (Test-Path -LiteralPath $identBackup -PathType Leaf)) { throw "WP22A_POSTGRES_BACKUP_INCOMPLETE" }
    $dataRoot = Get-PostgresDataRoot
    Copy-Item -LiteralPath $hbaBackup -Destination (Join-Path $dataRoot "pg_hba.conf") -Force
    Copy-Item -LiteralPath $identBackup -Destination (Join-Path $dataRoot "pg_ident.conf") -Force
    Reload-Postgres -DataRoot $dataRoot
    return $true
}

if (-not ("OmniCioV10.Wp22aAccountRights" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
namespace OmniCioV10 {
public static class Wp22aAccountRights {
    private const uint POLICY_CREATE_ACCOUNT = 0x10;
    private const uint POLICY_LOOKUP_NAMES = 0x800;
    private const uint STATUS_SUCCESS = 0;
    [StructLayout(LayoutKind.Sequential)] private struct LSA_OBJECT_ATTRIBUTES { public uint Length; public IntPtr RootDirectory; public IntPtr ObjectName; public uint Attributes; public IntPtr SecurityDescriptor; public IntPtr SecurityQualityOfService; }
    [StructLayout(LayoutKind.Sequential)] private struct LSA_UNICODE_STRING { public ushort Length; public ushort MaximumLength; public IntPtr Buffer; }
    [DllImport("advapi32.dll", PreserveSig=true)] private static extern uint LsaOpenPolicy(IntPtr SystemName, ref LSA_OBJECT_ATTRIBUTES ObjectAttributes, uint DesiredAccess, out IntPtr PolicyHandle);
    [DllImport("advapi32.dll", PreserveSig=true)] private static extern uint LsaEnumerateAccountRights(IntPtr PolicyHandle, IntPtr AccountSid, out IntPtr UserRights, out uint CountOfRights);
    [DllImport("advapi32.dll", PreserveSig=true)] private static extern uint LsaAddAccountRights(IntPtr PolicyHandle, IntPtr AccountSid, [In] LSA_UNICODE_STRING[] UserRights, uint CountOfRights);
    [DllImport("advapi32.dll", PreserveSig=true)] private static extern uint LsaRemoveAccountRights(IntPtr PolicyHandle, IntPtr AccountSid, [MarshalAs(UnmanagedType.U1)] bool AllRights, [In] LSA_UNICODE_STRING[] UserRights, uint CountOfRights);
    [DllImport("advapi32.dll")] private static extern uint LsaNtStatusToWinError(uint Status);
    [DllImport("advapi32.dll")] private static extern uint LsaClose(IntPtr PolicyHandle);
    [DllImport("advapi32.dll")] private static extern uint LsaFreeMemory(IntPtr Buffer);
    private static void Throw(uint status, string op) { if (status == STATUS_SUCCESS) return; throw new Win32Exception(unchecked((int)LsaNtStatusToWinError(status)), op + " failed"); }
    private static IntPtr Open(uint access) { var attr = new LSA_OBJECT_ATTRIBUTES(); IntPtr handle; Throw(LsaOpenPolicy(IntPtr.Zero, ref attr, access, out handle), "LsaOpenPolicy"); return handle; }
    private static IntPtr AllocSid(string text) { var sid = new SecurityIdentifier(text); var bytes = new byte[sid.BinaryLength]; sid.GetBinaryForm(bytes, 0); var ptr = Marshal.AllocHGlobal(bytes.Length); Marshal.Copy(bytes, 0, ptr, bytes.Length); Array.Clear(bytes, 0, bytes.Length); return ptr; }
    private static LSA_UNICODE_STRING MakeString(string value) { var ptr = Marshal.StringToHGlobalUni(value); return new LSA_UNICODE_STRING { Buffer = ptr, Length = checked((ushort)(value.Length * 2)), MaximumLength = checked((ushort)((value.Length + 1) * 2)) }; }
    public static string[] GetRights(string sidText) { IntPtr policy=IntPtr.Zero, sid=IntPtr.Zero, rights=IntPtr.Zero; try { policy=Open(POLICY_LOOKUP_NAMES); sid=AllocSid(sidText); uint count; uint status=LsaEnumerateAccountRights(policy,sid,out rights,out count); if(status!=STATUS_SUCCESS){uint error=LsaNtStatusToWinError(status); if(error==2)return new string[0]; throw new Win32Exception(unchecked((int)error),"LsaEnumerateAccountRights failed");} var result=new List<string>(); int size=Marshal.SizeOf(typeof(LSA_UNICODE_STRING)); for(uint i=0;i<count;i++){var item=(LSA_UNICODE_STRING)Marshal.PtrToStructure(IntPtr.Add(rights,checked((int)(i*(uint)size))),typeof(LSA_UNICODE_STRING)); var text=Marshal.PtrToStringUni(item.Buffer,item.Length/2); if(!String.IsNullOrWhiteSpace(text))result.Add(text);} return result.ToArray(); } finally { if(rights!=IntPtr.Zero)LsaFreeMemory(rights); if(sid!=IntPtr.Zero)Marshal.FreeHGlobal(sid); if(policy!=IntPtr.Zero)LsaClose(policy); } }
    public static void AddRight(string sidText,string right){Change(sidText,right,true);} public static void RemoveRight(string sidText,string right){Change(sidText,right,false);}
    private static void Change(string sidText,string right,bool add){IntPtr policy=IntPtr.Zero,sid=IntPtr.Zero; LSA_UNICODE_STRING native=default(LSA_UNICODE_STRING); try{policy=Open(POLICY_LOOKUP_NAMES|(add?POLICY_CREATE_ACCOUNT:0));sid=AllocSid(sidText);native=MakeString(right);var values=new[]{native};uint status=add?LsaAddAccountRights(policy,sid,values,1):LsaRemoveAccountRights(policy,sid,false,values,1);Throw(status,add?"LsaAddAccountRights":"LsaRemoveAccountRights");}finally{if(native.Buffer!=IntPtr.Zero)Marshal.FreeHGlobal(native.Buffer);if(sid!=IntPtr.Zero)Marshal.FreeHGlobal(sid);if(policy!=IntPtr.Zero)LsaClose(policy);}}
}}
'@
}

$implementationSha = Get-ReviewedHead
$runtimeUser = Get-RuntimeUser
$runnerSid = Get-RunnerSid

if ($Cleanup) {
    if (-not (Test-Administrator)) { throw "WP22A cleanup requires OWNER administrator." }
    Stop-And-RemoveTask
    Disable-LocalUser -Name $runtimeName -ErrorAction Stop
    $postgresRestored = Restore-PostgresConfig
    if (Test-Path -LiteralPath $runtimeRoot -PathType Container) {
        if (-not (Test-Path -LiteralPath $runtimeMarker -PathType Leaf)) { throw "WP22A_RUNTIME_ROOT_UNOWNED" }
        if ((Get-Content -LiteralPath $runtimeMarker -Raw).Trim() -ne $runtimeMarkerValue) { throw "WP22A_RUNTIME_MARKER_MISMATCH" }
        Remove-Item -LiteralPath $runtimeRoot -Recurse -Force -ErrorAction Stop
    }
    $result = [ordered]@{
        schema_version = "1"; work_package = "WP22A"; evidence_type = "PRIVATE_REMOTE_RUNTIME_CLEANUP";
        implementation_sha = $implementationSha; temporary_task_present = $false; runtime_role_enabled = $false;
        postgres_config_restored = [bool]$postgresRestored; real_secret_values_logged = $false;
        broker_write_authority_added = $false; trading_methods = $false; real_trading_enabled = $false;
        gateway_entrypoint = "app:app"; ready = $true
    }
    if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
    exit 0
}

if (-not (Test-Administrator)) { throw "WP22A apply/verify requires OWNER administrator." }

$configRaw = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $configurator -Verify -BackendPort $Port -ConfigPath $ConfigPath -AsJson 2>$null | Out-String
if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_CONFIG_VERIFY_FAILED" }
$configState = $configRaw.Trim() | ConvertFrom-Json -ErrorAction Stop
if (-not [bool]$configState.ready) { throw "WP22A_TAILSCALE_CONFIG_NOT_READY" }

if ($Apply) {
    if ([bool]$runtimeUser.Enabled) { throw "WP22A_RUNTIME_ROLE_MUST_START_DISABLED" }
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { throw "WP22A_TASK_ALREADY_EXISTS" }
    if (Test-Path -LiteralPath $runtimeRoot) { throw "WP22A_RUNTIME_ROOT_ALREADY_EXISTS" }
    foreach ($path in @($pythonMachine, $nodeExe, $npmCmd, $psqlExe, $pgCtlExe)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "WP22A_REQUIRED_TOOL_MISSING" }
    }
    $pythonVersion = @(& $pythonMachine -c "import platform; print(platform.python_version())")
    if ($LASTEXITCODE -ne 0 -or ($pythonVersion -join "").Trim() -ne "3.14.6") { throw "WP22A_PYTHON_VERSION_MISMATCH" }
    $nodeVersion = @(& $nodeExe --version)
    if ($LASTEXITCODE -ne 0 -or ($nodeVersion -join "").Trim() -ne "v24.18.0") { throw "WP22A_NODE_VERSION_MISMATCH" }
    $npmVersion = @(& $npmCmd --version)
    if ($LASTEXITCODE -ne 0 -or ($npmVersion -join "").Trim() -ne "11.16.0") { throw "WP22A_NPM_VERSION_MISMATCH" }

    $runtimeSid = $runtimeUser.SID
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    Set-Content -LiteralPath $runtimeMarker -Value $runtimeMarkerValue -Encoding ASCII -NoNewline
    Set-ProtectedDirectoryAcl -Path $runtimeRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    Set-ProtectedDirectoryAcl -Path $backupRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute)
    Set-Content -LiteralPath $backupMarker -Value $backupMarkerValue -Encoding ASCII -NoNewline

    $dataRoot = Get-PostgresDataRoot
    $hbaPath = Join-Path $dataRoot "pg_hba.conf"
    $identPath = Join-Path $dataRoot "pg_ident.conf"
    Copy-Item -LiteralPath $hbaPath -Destination $hbaBackup -ErrorAction Stop
    Copy-Item -LiteralPath $identPath -Destination $identBackup -ErrorAction Stop

    $zipPath = Join-Path $env:TEMP ("omni-cio-wp22a-" + [guid]::NewGuid().ToString("N") + ".zip")
    try {
        & git -C $repoRoot archive --format=zip --output=$zipPath HEAD
        if ($LASTEXITCODE -ne 0) { throw "WP22A_GIT_ARCHIVE_FAILED" }
        New-Item -ItemType Directory -Path $appRoot -Force | Out-Null
        Expand-Archive -LiteralPath $zipPath -DestinationPath $appRoot -Force
    }
    finally { Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue }
    Set-Content -LiteralPath $deploymentMarker -Value $implementationSha -Encoding ASCII -NoNewline

    Push-Location -LiteralPath (Join-Path $appRoot "apps\web")
    $previousGitSha = $env:GITHUB_SHA
    $env:GITHUB_SHA = $implementationSha
    try {
        $previousNativeErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & $npmCmd ci --ignore-scripts --no-audit --no-fund *> $null
            if ($LASTEXITCODE -ne 0) { throw "WP22A_WEB_NPM_CI_FAILED" }
            & $npmCmd run typecheck *> $null
            if ($LASTEXITCODE -ne 0) { throw "WP22A_WEB_TYPECHECK_FAILED" }
            & $npmCmd run build *> $null
            if ($LASTEXITCODE -ne 0) { throw "WP22A_WEB_BUILD_FAILED" }
        }
        finally { $ErrorActionPreference = $previousNativeErrorActionPreference }
    }
    finally {
        $env:GITHUB_SHA = $previousGitSha
        Remove-Item -LiteralPath (Join-Path $appRoot "apps\web\node_modules") -Recurse -Force -ErrorAction SilentlyContinue
        Pop-Location
    }

    & $pythonMachine -m venv $venvRoot *> $null
    if ($LASTEXITCODE -ne 0) { throw "WP22A_VENV_CREATE_FAILED" }
    $venvPython = Join-Path $venvRoot "Scripts\python.exe"
    $windowsRuntimeLock = Join-Path $runtimeRoot "requirements.windows.txt"
    try {
        & $pythonMachine (Join-Path $appRoot "scripts\windows_ci_lock.py") project (Join-Path $appRoot "requirements.txt") $windowsRuntimeLock *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP22A_WINDOWS_LOCK_PROJECTION_FAILED" }
        & $venvPython -m pip install --disable-pip-version-check --require-hashes -r $windowsRuntimeLock *> $null
        if ($LASTEXITCODE -ne 0) { throw "WP22A_DEPENDENCY_INSTALL_FAILED" }
    }
    finally { Remove-Item -LiteralPath $windowsRuntimeLock -Force -ErrorAction SilentlyContinue }

    Set-ProtectedDirectoryAcl -Path $appRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime
    Set-ProtectedDirectoryAcl -Path $venvRoot -RuntimeSid $runtimeSid -RuntimeRights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -IncludeRuntime

    $ownerIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $runtimeAccount = $runtimeSid.Translate([System.Security.Principal.NTAccount]).Value
    $ownerField = Quote-PgField -Value (Convert-NtAccountToSspiPrincipal -Value $ownerIdentity)
    $runtimeField = Quote-PgField -Value (Convert-NtAccountToSspiPrincipal -Value $runtimeAccount)
    $sspiOptions = "include_realm=1 compat_realm=1 upn_username=0"
    Set-ManagedConfigBlock -Path $hbaPath -Lines @(
        "host all postgres 127.0.0.1/32 sspi $sspiOptions map=omni_cio_wp22a_owner_map",
        "host omni_cio_v10 omni_cio_runtime 127.0.0.1/32 sspi $sspiOptions map=omni_cio_wp22a_runtime_map"
    )
    Set-ManagedConfigBlock -Path $identPath -Lines @(
        "omni_cio_wp22a_owner_map $ownerField postgres",
        "omni_cio_wp22a_runtime_map $runtimeField omni_cio_runtime"
    )
    Reload-Postgres -DataRoot $dataRoot

    try {
        Invoke-PsqlText -Database "postgres" -Sql @'
\set ON_ERROR_STOP on
DO $omni$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'omni_cio_runtime') THEN
        CREATE ROLE omni_cio_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSE
        ALTER ROLE omni_cio_runtime LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
END
$omni$;
SELECT 'CREATE DATABASE omni_cio_v10 WITH OWNER = postgres ENCODING = ''UTF8''' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'omni_cio_v10') \gexec
REVOKE ALL ON DATABASE omni_cio_v10 FROM PUBLIC;
GRANT CONNECT ON DATABASE omni_cio_v10 TO omni_cio_runtime;
'@
        Invoke-MigrationsAsOwnerSspi -PythonPath $venvPython
        Invoke-PsqlText -Database "omni_cio_v10" -Sql @'
\set ON_ERROR_STOP on
GRANT USAGE ON SCHEMA omni_cio_v10 TO omni_cio_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA omni_cio_v10 TO omni_cio_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    omni_cio_v10.web_sessions,
    omni_cio_v10.broker_connections,
    omni_cio_v10.broker_connection_accounts,
    omni_cio_v10.broker_accounts
TO omni_cio_runtime;
DO $omni$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_hba_file_rules WHERE error IS NOT NULL) THEN RAISE EXCEPTION 'HBA_RULE_PARSE_ERROR'; END IF;
    IF EXISTS (SELECT 1 FROM pg_ident_file_mappings WHERE error IS NOT NULL) THEN RAISE EXCEPTION 'IDENT_RULE_PARSE_ERROR'; END IF;
END
$omni$;
'@
    }
    catch {
        Copy-Item -LiteralPath $hbaBackup -Destination $hbaPath -Force -ErrorAction SilentlyContinue
        Copy-Item -LiteralPath $identBackup -Destination $identPath -Force -ErrorAction SilentlyContinue
        try { Reload-Postgres -DataRoot $dataRoot } catch { }
        throw
    }

    Set-ManagedConfigBlock -Path $hbaPath -Lines @("host omni_cio_v10 omni_cio_runtime 127.0.0.1/32 sspi $sspiOptions map=omni_cio_wp22a_runtime_map")
    Set-ManagedConfigBlock -Path $identPath -Lines @("omni_cio_wp22a_runtime_map $runtimeField omni_cio_runtime")
    Reload-Postgres -DataRoot $dataRoot

    $runtimeSidText = $runtimeSid.Value
    $rightsBefore = @([OmniCioV10.Wp22aAccountRights]::GetRights($runtimeSidText))
    if ($rightsBefore -contains $denyBatchRight) { throw "WP22A_RUNTIME_DENY_BATCH_LOGON_RIGHT_PRESENT" }
    $batchRightAdded = $false
    $runtimePassword = $null
    $securePassword = $null
    try {
        if ($rightsBefore -notcontains $batchRight) {
            [OmniCioV10.Wp22aAccountRights]::AddRight($runtimeSidText, $batchRight)
            $batchRightAdded = $true
        }
        $runtimePassword = New-RandomRuntimePassword
        $securePassword = ConvertTo-SecureString -String $runtimePassword -AsPlainText -Force
        Set-LocalUser -Name $runtimeName -Password $securePassword -ErrorAction Stop
        Enable-LocalUser -Name $runtimeName -ErrorAction Stop
        $launcher = Join-Path $appRoot $launcherRelative
        $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$appRoot`" -ImplementationSha $implementationSha -ConfigPath `"$ConfigPath`" -Port $Port"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew -RestartCount 0 -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $taskName -Action $action -Settings $settings -User $runtimeAccount -Password $runtimePassword -RunLevel Limited -Description $taskDescription -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
        $readyTcp = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Seconds 2
            try {
                $client = [System.Net.Sockets.TcpClient]::new()
                try {
                    $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
                    if ($async.AsyncWaitHandle.WaitOne(1500) -and $client.Connected) { $readyTcp = $true; break }
                }
                finally { $client.Close() }
            }
            catch { }
        }
        if (-not $readyTcp) {
            $failedTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
            $failedTaskState = if ($null -ne $failedTask) { [string]$failedTask.State } else { "Missing" }
            $failedTaskInfo = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            $failedTaskResult = if ($null -ne $failedTaskInfo) { [int64]$failedTaskInfo.LastTaskResult } else { -1 }
            throw ("WP22A_LOOPBACK_RUNTIME_NOT_READY; task_state={0}; last_task_result={1}" -f $failedTaskState, $failedTaskResult)
        }
    }
    finally {
        $runtimePassword = $null
        $securePassword = $null
        if ($batchRightAdded) {
            [OmniCioV10.Wp22aAccountRights]::RemoveRight($runtimeSidText, $batchRight)
            if (@([OmniCioV10.Wp22aAccountRights]::GetRights($runtimeSidText)) -contains $batchRight) { throw "WP22A_BATCH_LOGON_RIGHT_RESTORE_FAILED" }
        }
    }
}

$owned = (Test-Path -LiteralPath $runtimeRoot -PathType Container) -and (Test-Path -LiteralPath $runtimeMarker -PathType Leaf) -and ((Get-Content -LiteralPath $runtimeMarker -Raw).Trim() -eq $runtimeMarkerValue)
$deploymentBound = $owned -and (Test-Path -LiteralPath $deploymentMarker -PathType Leaf) -and ((Get-Content -LiteralPath $deploymentMarker -Raw).Trim().ToLowerInvariant() -eq $implementationSha)
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$taskPresent = $null -ne $task
$taskOwned = $taskPresent -and [string]$task.Description -eq $taskDescription
$taskRunning = $taskOwned -and [string]$task.State -eq "Running"
$runtimeEnabled = [bool](Get-LocalUser -Name $runtimeName -ErrorAction Stop).Enabled
$appAcl = Test-DirectoryAcl -Path $appRoot -RuntimeSid $runtimeUser.SID -RunnerSid $runnerSid
$venvAcl = Test-DirectoryAcl -Path $venvRoot -RuntimeSid $runtimeUser.SID -RunnerSid $runnerSid
$taskPrincipalOk = $false
$taskActionOk = $false
if ($taskOwned) {
    $principalSid = try { ([System.Security.Principal.NTAccount]::new([string]$task.Principal.UserId)).Translate([System.Security.Principal.SecurityIdentifier]) } catch { $null }
    $taskPrincipalOk = $null -ne $principalSid -and $principalSid.Value -eq $runtimeUser.SID.Value -and [string]$task.Principal.RunLevel -eq "Limited"
    $actions = @($task.Actions)
    if ($actions.Count -eq 1) {
        $expectedLauncher = Join-Path $appRoot $launcherRelative
        $taskActionOk = [string]$actions[0].Execute -match '(?i)powershell\.exe$' -and [string]$actions[0].Arguments -match [regex]::Escape($expectedLauncher) -and [string]$actions[0].Arguments -match [regex]::Escape($implementationSha) -and [string]$actions[0].Arguments -match [regex]::Escape($ConfigPath)
    }
}
$ready = $owned -and $deploymentBound -and $taskOwned -and $taskRunning -and $runtimeEnabled -and $taskPrincipalOk -and $taskActionOk -and $appAcl.protected -and $appAcl.runtime_read -and (-not $appAcl.runtime_write) -and (-not $appAcl.runner_read) -and (-not $appAcl.runner_write) -and (-not $appAcl.broad) -and $venvAcl.protected -and $venvAcl.runtime_read -and (-not $venvAcl.runtime_write) -and (-not $venvAcl.runner_read) -and (-not $venvAcl.runner_write) -and (-not $venvAcl.broad) -and [bool]$configState.ready

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_type = "PRIVATE_REMOTE_RUNTIME_PROVISIONING"
    implementation_sha = $implementationSha
    runtime_root_owned = [bool]$owned
    deployment_bound = [bool]$deploymentBound
    temporary_task_present = [bool]$taskPresent
    temporary_task_running = [bool]$taskRunning
    runtime_role_enabled = [bool]$runtimeEnabled
    runtime_role_non_admin = $true
    task_principal_runtime = [bool]$taskPrincipalOk
    task_action_exact = [bool]$taskActionOk
    app_runtime_read_only = [bool]($appAcl.runtime_read -and (-not $appAcl.runtime_write))
    runner_runtime_data_access = [bool]($appAcl.runner_read -or $appAcl.runner_write -or $venvAcl.runner_read -or $venvAcl.runner_write)
    postgres_authentication = "SSPI"
    postgres_trust_used = $false
    database_password_persisted = $false
    runtime_password_logged_or_exported = $false
    tailscale_private_config_ready = [bool]$configState.ready
    public_ingress = $false
    public_multi_user_enabled = $false
    broker_write_authority_added = $false
    trading_methods = $false
    real_trading_enabled = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) { $result | ConvertTo-Json -Depth 5 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (-not $ready) { exit 71 }
