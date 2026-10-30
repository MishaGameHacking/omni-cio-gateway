[CmdletBinding()]
param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or -not [Environment]::Is64BitProcess) {
    throw 'Run on the designated Lenovo in 64-bit Windows PowerShell.'
}
$PackageCode = 'd958608239005290f808'
$expected = [ordered]@{
    'Run-AnalystAIHome.ps1'='e95a456192a4c582f7d9ca8afea16256d05299c69dc1594e07ab21c188f61dc4'
    'protected_guest.py'='00517dd188ce723b94e19025f1b02466c6f04b70e0f44263a6a3427b27a8dd30'
    'guest_setup.py'='917c09f12cf116426a46d978b1f5e08d2e51575b41e56dfe077b24fb4ea28298'
    'smoke.py'='90846f9fd908ba168679d566a956bc0cba720edb7a30655a84e8baea879079d1'
    'upstream_prepare.py'='2049335293b40bddb0a9b12214af48bf64ad3d40c3eceec31720839f6730f8de'
    'ubuntu.wsl'='bb415d824822c4b878125729af451a5d18fb13d1cf5cbed9a7393ad64ac6039e'
    'model.litertlm'='0b2a8980ce155fd97673d8e820b4d29d9c7d99b8fa6806f425d969b145bd52e0'
}
$spool = Join-Path $env:SystemRoot 'ServiceProfiles\NetworkService\AppData\Local\AnalystAI-HomeLab'
$media = Join-Path $spool 'enrollment-media-v1'
$stage = Join-Path $spool ('enroll-'+$PackageCode)
$root = Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$receipt = Join-Path $root 'enrollment.json'
$name = 'AnalystAIHost'
$task = 'AnalystAI-HomeRuntime'
$machine = $env:COMPUTERNAME
$localUser = "$machine\$name"
$description = 'Analyst AI home runtime'
$accountOptions = @{Name=$name; Description=$description; PasswordNeverExpires=$true; UserMayNotChangePassword=$true}
$systemSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$adminsSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$networkSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-20')
function Need([bool]$ok,[string]$why) { if (-not $ok) { throw $why } }
function Plain([string]$path) {
    $p=Get-Item -Force -LiteralPath $path
    while ($null -ne $p) {
        Need (($p.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Reparse point in installation path'
        $p=if ($p -is [IO.FileInfo]) { $p.Directory } else { $p.Parent }
    }
}
function Check-File([string]$path,[string]$sha) {
    Plain $path
    Need ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $sha) 'Content verification failed'
}
function Source([string]$file) {
    if ($file -in 'ubuntu.wsl','model.litertlm') { return Join-Path $media $file }
    return Join-Path $stage $file
}
function Check-Scripts([string]$folder) {
    foreach ($file in @('Run-AnalystAIHome.ps1')) {
        $tokens=$null; $errors=$null
        $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $folder $file),[ref]$tokens,[ref]$errors)
        Need ($errors.Count -eq 0) 'PowerShell source syntax is invalid'
    }
}
function Lock-Directory([string]$path,[Security.Principal.SecurityIdentifier]$sid,[string]$level,[bool]$report) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    foreach ($pair in @(@($adminsSid,'FullControl'),@($systemSid,'FullControl'))) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($pair[0],$pair[1],$inherit,'None','Allow'))
    }
    if ($null -ne $sid) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$level,$inherit,'None','Allow'))
    }
    if ($report) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($networkSid,'ReadAndExecute',$inherit,'None','Allow'))
    }
    Set-Acl -LiteralPath $path -AclObject $acl
}
function Stage-Payload {
    foreach ($file in $expected.Keys) {
        $dest=Join-Path $root $file
        if (-not [IO.File]::Exists($dest)) {
            $tmp=Join-Path $root ('verified-'+[Guid]::NewGuid().ToString('N'))
            try {
                [IO.File]::Copy((Source $file),$tmp,$false)
                Check-File $tmp $expected[$file]
                [IO.File]::Move($tmp,$dest)
            } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
        } else { Check-File $dest $expected[$file] }
    }
}
function Read-Enrollment {
    Plain $root
    Plain $receipt
    $info=Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
    Need ($info.marker -eq 'analyst-home-runtime-v1' -and $info.package -eq $PackageCode -and $info.machine -eq $machine) 'Unknown deployment at destination'
    return $info
}
function Save-Enrollment($info) {
    $tmp=Join-Path $root ('receipt-'+[Guid]::NewGuid().ToString('N'))
    [IO.File]::WriteAllText($tmp,($info | ConvertTo-Json -Compress))
    if ([IO.File]::Exists($receipt)) { [IO.File]::Replace($tmp,$receipt,[NullString]::Value) } else { [IO.File]::Move($tmp,$receipt) }
}
function Home-TaskOptions {
    $action=New-ScheduledTaskAction -Execute $winPS -Argument ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+(Join-Path $root 'Run-AnalystAIHome.ps1')+'"')
    $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 2)
    return @{TaskPath='\'; TaskName=$task; Action=$action; Trigger=(New-ScheduledTaskTrigger -AtStartup)
             Settings=$settings; User=$localUser; RunLevel='Limited'; Description=$description}
}
function Verify-Task($t,$sid) {
    $action=@($t.Actions)
    $target=Join-Path $root 'Run-AnalystAIHome.ps1'
    $expectedArgs='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$target+'"'
    Need ($action.Count -eq 1 -and $action[0].Execute -eq $winPS -and $action[0].Arguments -eq $expectedArgs) 'Unexpected task program'
    Need ($t.Principal.UserId -in @($localUser,$sid.Value,$name) -and [string]$t.Principal.RunLevel -eq 'Limited' -and
          [string]$t.Principal.LogonType -eq 'Password' -and @($t.Triggers).Count -eq 1 -and
          $t.Triggers[0].CimClass.CimClassName -eq 'MSFT_TaskBootTrigger') 'Unexpected task identity or trigger'
}
function Observer-TaskDacl([string]$source) {
    $d=[Security.AccessControl.CommonSecurityDescriptor]::new($false,$false,$source)
    Need ($null -ne $d.DiscretionaryAcl -and $d.DiscretionaryAcl.Count -gt 0) 'Empty task access list'
    $mask=[int]([Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [Security.AccessControl.FileSystemRights]::Synchronize)
    foreach ($ace in $d.DiscretionaryAcl) {
        if ($ace -is [Security.AccessControl.CommonAce] -and $ace.SecurityIdentifier.Value -eq $networkSid.Value -and
            $ace.AceQualifier -eq [Security.AccessControl.AceQualifier]::AccessAllowed -and ($ace.AccessMask -band $mask) -eq $mask) {
            return $d.GetSddlForm([Security.AccessControl.AccessControlSections]::Access)
        }
    }
    $d.DiscretionaryAcl.AddAccess([Security.AccessControl.AccessControlType]::Allow,$networkSid,$mask,
                                  [Security.AccessControl.InheritanceFlags]::None,[Security.AccessControl.PropagationFlags]::None)
    return $d.GetSddlForm([Security.AccessControl.AccessControlSections]::Access)
}
function Permit-LimitedTaskRetry {
    # Called only after verifying the principal, executable, arguments and boot trigger.
    try {
        $service=New-Object -ComObject 'Schedule.Service'; $service.Connect()
        $registered=$service.GetFolder('\').GetTask($task)
        $old=$registered.GetSecurityDescriptor(4)
        $new=Observer-TaskDacl $old
        if ($new -cne $old) { $registered.SetSecurityDescriptor($new,16) }
        $actual=$registered.GetSecurityDescriptor(4)
        Need ((Observer-TaskDacl $actual) -ceq ([Security.AccessControl.CommonSecurityDescriptor]::new($false,$false,$actual)).GetSddlForm([Security.AccessControl.AccessControlSections]::Access)) 'Task retry permission was not retained'
    } catch { Write-Warning ('Limited task visibility: '+(Error-Code $_)) }
}
function Log-Enrollment([string]$step,[string]$code='') {
    if (-not $journalEnabled) { return }
    $directory=Join-Path $root 'install-status'
    $to=Join-Path $directory 'status.json'
    $next=Join-Path $directory ('next-'+[Guid]::NewGuid().ToString('N'))
    $row=[ordered]@{package=$PackageCode;stage=$step;code=$code;utc=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::WriteAllText($next,($row | ConvertTo-Json -Compress))
    if ([IO.File]::Exists($to)) { [IO.File]::Replace($next,$to,[NullString]::Value) } else { [IO.File]::Move($next,$to) }
}
function Error-Code($cause) {
    $e=$cause.Exception
    while ($null -ne $e.InnerException) { $e=$e.InnerException }
    if ($e -is [ComponentModel.Win32Exception]) {
        $n=[long]$e.NativeErrorCode
        if ((($n -band 4294901760L) -eq 2147942400L)) { $n=$n -band 65535 }
        return ('win32-'+$n)
    }
    return ('hresult-{0:X8}' -f ([long]$e.HResult -band 4294967295L))
}
function Read-WorkerPhase([DateTime]$since) {
    $file=Join-Path $root 'report\status.json'
    try {
        if ((Get-Item -Force -LiteralPath $file).Length -gt 4096) { return '' }
        $row=Get-Content -Raw -LiteralPath $file | ConvertFrom-Json
        if ($row.package -eq $PackageCode -and $row.phase -match '^(?:failed-)?(?:windows|import|configure|application|local-model|login-check|supervising)$' -and
            [DateTimeOffset]::Parse([string]$row.utc).UtcDateTime -ge $since.AddSeconds(-3)) { return [string]$row.phase }
    } catch { }
    return ''
}
function Wait-WorkerPhase([DateTime]$since,[int]$seconds) {
    $until=[DateTime]::UtcNow.AddSeconds($seconds)
    do {
        $phase=Read-WorkerPhase $since
        if ($phase -and $phase -ne 'windows') { return $phase }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $until)
    return (Read-WorkerPhase $since)
}
function Stage-ProfileProof([string]$folder) {
    # This script lives in the administrator-owned program directory and is readable by the limited service.
    $proof=@'
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ExpectedSid)
$ErrorActionPreference='Stop'
if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne $ExpectedSid) { exit 41 }
try {
    $row=Get-ItemProperty -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$ExpectedSid)
    $location=[Environment]::ExpandEnvironmentVariables([string]$row.ProfileImagePath)
    if (-not [IO.Directory]::Exists($location)) { exit 42 }
    if (-not (Test-Path -LiteralPath ('Registry::HKEY_USERS\'+$ExpectedSid))) { exit 43 }
} catch { exit 44 }
[Console]::WriteLine('ANALYST_PROFILE_OK')
exit 0
'@
    Plain $folder
    $file=Join-Path $folder 'Check-AnalystProfile-v1.ps1'
    $bytes=[Text.Encoding]::UTF8.GetBytes($proof)
    if (-not [IO.File]::Exists($file)) {
        $temp=Join-Path $folder ('proof-'+[Guid]::NewGuid().ToString('N'))
        try { [IO.File]::WriteAllBytes($temp,$bytes); [IO.File]::Move($temp,$file) }
        finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
    }
    Plain $file
    Need ([Convert]::ToBase64String([IO.File]::ReadAllBytes($file)) -ceq [Convert]::ToBase64String($bytes)) 'Unrecognized profile helper at destination'
    return $file
}
function Profile-ChildInfo([string]$file,[string]$expectedSid,[PSCredential]$credential) {
    Need ($expectedSid -match '^(?:S-1-5-20|S-1-5-21-(?:[0-9]+-){3}[0-9]+)$') 'Unexpected profile proof SID'
    Need ([IO.Path]::IsPathRooted($file) -and [IO.Path]::GetFileName($file) -ceq 'Check-AnalystProfile-v1.ps1' -and $file -notmatch '["\r\n]') 'Invalid profile proof file'
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=$winPS
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.LoadUserProfile=$true
    $psi.WorkingDirectory=$env:SystemRoot
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $psi.Arguments='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$file+'" -ExpectedSid '+$expectedSid
    # CreateProcessWithLogonW limits the entire command line, including the executable and its quotes.
    Need (($psi.FileName.Length+$psi.Arguments.Length+4) -le 1024) 'Alternate-account command exceeds Windows 1024-character limit'
    if ($null -ne $credential) {
        Need ($credential.UserName -eq $localUser) 'Unexpected profile logon target'
        $psi.Domain=$machine
        $psi.UserName=$name
        $psi.Password=$credential.Password
    }
    return $psi
}
function Run-ProfileChild([Diagnostics.ProcessStartInfo]$startInfo) {
    $p=[Diagnostics.Process]::new()
    $p.StartInfo=$startInfo
    try {
        Need ($p.Start()) 'Windows could not launch the profile check'
        $stdout=$p.StandardOutput.ReadToEndAsync()
        $stderr=$p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit(60000)) {
            try { $p.Kill() } catch {}
            throw 'The profile check timed out'
        }
        $proof=$stdout.GetAwaiter().GetResult().Trim()
        $null=$stderr.GetAwaiter().GetResult()
        Need ($p.ExitCode -eq 0 -and $proof -eq 'ANALYST_PROFILE_OK') ('Profile proof failed, process exit '+$p.ExitCode)
    } finally { $p.Dispose() }
}
function Import-ProfileApi {
    if ('AnalystHome.ProfileLoader' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security;
using System.Security.Principal;
using Microsoft.Win32;
namespace AnalystHome {
    public static class ProfileLoader {
        [StructLayout(LayoutKind.Sequential)] struct Luid { public uint Low; public int High; }
        [StructLayout(LayoutKind.Sequential)] struct Privileges { public uint Count; public Luid Id; public uint Attributes; }
        [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] struct Profile {
            public int Size, Flags; public string UserName, Path, DefaultPath, Server, Policy; public IntPtr Hive;
        }
        [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
        [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr handle);
        [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
        [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool LookupPrivilegeValue(string system,string name,out Luid id);
        [DllImport("advapi32.dll",SetLastError=true)] static extern bool AdjustTokenPrivileges(IntPtr token,bool all,ref Privileges state,uint length,out Privileges previous,out uint returned);
        [DllImport("advapi32.dll",EntryPoint="AdjustTokenPrivileges",SetLastError=true)] static extern bool RestorePrivilege(IntPtr token,bool all,ref Privileges state,uint length,IntPtr previous,IntPtr returned);
        [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true,ExactSpelling=true)] static extern bool LogonUserW(string user,string domain,IntPtr password,uint type,uint provider,out IntPtr token);
        [DllImport("userenv.dll",CharSet=CharSet.Unicode,SetLastError=true,ExactSpelling=true)] static extern bool LoadUserProfileW(IntPtr token,ref Profile profile);
        [DllImport("userenv.dll",SetLastError=true,ExactSpelling=true)] static extern bool UnloadUserProfile(IntPtr token,IntPtr hive);
        static void Check(bool success) { if(!success) throw new Win32Exception(Marshal.GetLastWin32Error()); }
        static Privileges Enable(IntPtr token,string name) {
            Privileges desired=new Privileges(), old; uint length;
            Check(LookupPrivilegeValue(null,name,out desired.Id)); desired.Count=1; desired.Attributes=2;
            bool result=AdjustTokenPrivileges(token,false,ref desired,(uint)Marshal.SizeOf(typeof(Privileges)),out old,out length);
            int error=Marshal.GetLastWin32Error(); if(!result || error!=0) throw new Win32Exception(error);
            return old;
        }
        public static int StructureSize { get { return Marshal.SizeOf(typeof(Profile)); } }
        public static void Load(string domain,string user,SecureString secret,string expectedSid) {
            if (!String.Equals(domain,Environment.MachineName,StringComparison.OrdinalIgnoreCase) || user!="AnalystAIHost") throw new InvalidOperationException("Unexpected account");
            IntPtr password=IntPtr.Zero, token=IntPtr.Zero, caller=IntPtr.Zero;
            Privileges backup=new Privileges(),restore=new Privileges(); bool changedBackup=false, changedRestore=false;
            try {
                password=Marshal.SecureStringToGlobalAllocUnicode(secret);
                Check(LogonUserW(user,domain,password,4,0,out token));
                Marshal.ZeroFreeGlobalAllocUnicode(password); password=IntPtr.Zero;
                using (WindowsIdentity identity=new WindowsIdentity(token)) {
                    if (identity.User.Value!=expectedSid) throw new InvalidOperationException("Service SID mismatch");
                }
                Check(OpenProcessToken(GetCurrentProcess(),0x28,out caller));
                backup=Enable(caller,"SeBackupPrivilege"); changedBackup=true;
                restore=Enable(caller,"SeRestorePrivilege"); changedRestore=true;
                Profile p=new Profile();p.Size=StructureSize;p.Flags=1;p.UserName=user;
                Check(LoadUserProfileW(token,ref p));
                try {
                    using(RegistryKey hive=Registry.Users.OpenSubKey(expectedSid)) {
                        if(hive==null) throw new InvalidOperationException("Dedicated hive proof missing");
                    }
                } finally { Check(UnloadUserProfile(token,p.Hive)); }
            } finally {
                if(changedRestore && restore.Count!=0) RestorePrivilege(caller,false,ref restore,0,IntPtr.Zero,IntPtr.Zero);
                if(changedBackup && backup.Count!=0) RestorePrivilege(caller,false,ref backup,0,IntPtr.Zero,IntPtr.Zero);
                if(caller!=IntPtr.Zero) CloseHandle(caller);
                if(token!=IntPtr.Zero) CloseHandle(token);
                if(password!=IntPtr.Zero) Marshal.ZeroFreeGlobalAllocUnicode(password);
            }
        }
    }
}
'@
}
function Initialize-ByLogon([PSCredential]$credential,[string]$ownerSid) {
    Need ($ownerSid -match '^S-1-5-21-(?:[0-9]+-){3}[0-9]+$') 'Unexpected service account SID'
    $proof=Stage-ProfileProof $root
    $launch=Profile-ChildInfo $proof $ownerSid $credential
    try {
        $secondary=Get-Service -Name seclogon
        if ($secondary.Status -ne 'Running') {
            Start-Service -Name seclogon
            $secondary.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running,[TimeSpan]::FromSeconds(25))
        }
        Run-ProfileChild $launch
    } catch {
        # Use the Windows batch logon and profile APIs in this same approved process, even when child creation is unavailable.
        Log-Enrollment 'native-profile-recovery' (Error-Code $_)
        Import-ProfileApi
        [AnalystHome.ProfileLoader]::Load($machine,$name,$credential.Password,$ownerSid)
    }
}
function Start-HomeSupervisor([PSCredential]$credential,[string]$ownerSid) {
    $since=[DateTime]::UtcNow
    Log-Enrollment 'starting-task'
    $profileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$ownerSid
    try {
        Start-ScheduledTask -TaskPath '\' -TaskName $task
        $phase=Wait-WorkerPhase $since 35
    } catch {
        if (Test-Path -LiteralPath $profileKey) { throw }
        Log-Enrollment 'start-needs-profile' (Error-Code $_)
        $phase=''
    }
    if ((-not $phase -or $phase -in 'windows','failed-windows','failed-import') -and -not (Test-Path -LiteralPath $profileKey)) {
        Log-Enrollment 'loading-profile'
        try { Initialize-ByLogon $credential $ownerSid } catch {
            if (-not (Test-Path -LiteralPath $profileKey)) { throw }
            $known=Get-ItemProperty -LiteralPath $profileKey
            $profilePath=[Environment]::ExpandEnvironmentVariables([string]$known.ProfileImagePath)
            if (-not [IO.Directory]::Exists($profilePath)) { throw }
            Log-Enrollment 'profile-present-after-logon' (Error-Code $_)
        }
        Log-Enrollment 'retrying-task'
        $originalStart=$since
        $since=[DateTime]::UtcNow
        $registered=Get-ScheduledTask -TaskPath '\' -TaskName $task
        $afterLogon=Read-WorkerPhase $originalStart
        if ($registered.State -eq 'Running' -and (-not $afterLogon -or $afterLogon -in 'windows','failed-windows','failed-import') -and
            -not (Test-Path -LiteralPath (Join-Path $root 'state\ready.txt'))) {
            # A newly enrolled task which never reached import may be holding a session without its new hive.
            Stop-ScheduledTask -TaskPath '\' -TaskName $task
            for ($attempt=0;$attempt -lt 10;$attempt++) {
                $registered=Get-ScheduledTask -TaskPath '\' -TaskName $task
                if ($registered.State -ne 'Running') { break }
                Start-Sleep -Seconds 1
            }
        }
        if ($registered.State -ne 'Running') { Start-ScheduledTask -TaskPath '\' -TaskName $task }
        $phase=Wait-WorkerPhase $since 65
    }
    if (-not $phase -or $phase -eq 'windows') {
        $result=(Get-ScheduledTaskInfo -TaskPath '\' -TaskName $task).LastTaskResult
        Log-Enrollment 'waiting-worker' ('task-{0:X8}' -f ([long]$result -band 4294967295L))
        Write-Output 'Boot task is registered. Windows has not yet reported guest startup.'
        return
    }
    Log-Enrollment ('worker-'+$phase)
    if ($phase -like 'failed-*') { Write-Output ('Windows registered the boot task. The guest reported '+$phase+'.'); return }
    Write-Output ('Windows registered the boot task. Guest startup checkpoint: '+$phase+'.')
}
$winPS=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
# Apply Windows' actual validation contract before touching protected resources.
$descriptionRule=@((Get-Command Microsoft.PowerShell.LocalAccounts\New-LocalUser).Parameters['Description'].Attributes | Where-Object { $_ -is [Management.Automation.ValidateLengthAttribute] })
Need ($descriptionRule.Count -eq 1 -and $description.Length -ge $descriptionRule[0].MinLength -and
      $description.Length -le $descriptionRule[0].MaxLength) 'Local account description exceeds the installed Windows limit'
if ($VerifyOnly) {
    $probePassword=ConvertTo-SecureString ('Aa1!'+[Guid]::NewGuid().ToString('N')) -AsPlainText -Force
    try { Microsoft.PowerShell.LocalAccounts\New-LocalUser @accountOptions -Password $probePassword -WhatIf }
    finally { $probePassword.Dispose() }
    foreach ($file in $expected.Keys) { Check-File (Source $file) $expected[$file] }
    Check-Scripts $stage
    Need ([IO.FileInfo]::new((Source 'model.litertlm')).Length -eq 3659530240) 'Incorrect model size'
    [PSCustomObject]@{package=$PackageCode;items=$expected.Count;media_sha256='verified';powershell_syntax='valid';requires_admin_for_boot=$true;description_chars=$description.Length;description_limit=$descriptionRule[0].MaxLength;account_whatif=$true} | ConvertTo-Json -Compress
    return
}
$journalEnabled=$false
$checkpoint='entry'
$caller=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
Need ($caller.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'One local Windows administrator elevation is required.'
Need ((Get-Service -Name Schedule).Status -eq 'Running') 'Windows Task Scheduler is unavailable'
Need (Test-Path -LiteralPath (Join-Path $env:SystemRoot 'System32\wsl.exe')) 'WSL is unavailable'
Plain $env:ProgramFiles
if (-not [IO.Directory]::Exists($root)) {
    Need (-not (Get-LocalUser -Name $name -ErrorAction SilentlyContinue)) 'Account name already in use'
    Need (-not (Get-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction SilentlyContinue)) 'Task name already in use'
    Need ((Get-PSDrive -Name $env:SystemDrive.Substring(0,1)).Free -ge 24GB) 'At least 24 GiB of free space is required'
    # Verify every source before creating identities. Verify the protected copies again before execution.
    foreach ($file in $expected.Keys) { Check-File (Source $file) $expected[$file] }
    $null=New-Item -Path $root -ItemType Directory
    Lock-Directory $root $null 'ReadAndExecute' $false
    Save-Enrollment ([ordered]@{marker='analyst-home-runtime-v1';package=$PackageCode;machine=$machine;sid=''})
}
$null=Read-Enrollment
$lockFile=Join-Path $root 'enrollment.lock'
if ([IO.File]::Exists($lockFile)) { Plain $lockFile }
$installLock=[IO.File]::Open($lockFile,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try {
$info=Read-Enrollment
$adminStatus=Join-Path $root 'install-status'
try {
    if (-not [IO.Directory]::Exists($adminStatus)) { $null=[IO.Directory]::CreateDirectory($adminStatus) }
    Plain $adminStatus
    Lock-Directory $adminStatus $null 'ReadAndExecute' $true
    $journalEnabled=$true
    Log-Enrollment 'receipt-verified'
} catch {
    $journalEnabled=$false
    Write-Warning 'The optional installer status channel is unavailable.'
}
$current=$null
if ($info.sid) {
    $account=Get-LocalUser -Name $name
    Need ($account.SID.Value -eq $info.sid -and $account.Description -eq $description) 'Owned account identity changed'
    $current=Get-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction SilentlyContinue
    if ($current) {
        Verify-Task $current $account.SID
        Permit-LimitedTaskRetry
        if ($current.State -eq 'Running') {
            $previous=Read-WorkerPhase ([DateTime]::UtcNow.AddMinutes(-10))
            if ($previous -and $previous -notlike 'failed-*') {
                Log-Enrollment ('worker-'+$previous)
                Write-Output ('Owned task is running. Its last guest checkpoint was '+$previous+'.')
                return
            }
        }
    }
} else {
    Need (-not (Get-LocalUser -Name $name -ErrorAction SilentlyContinue)) 'The local account name is occupied'
}
Stage-Payload
Check-Scripts $root
# The only password exists in this process and in the Windows scheduler credential store.
$bytes=New-Object byte[] 48
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$plainPassword='Aa1!'+[Convert]::ToBase64String($bytes)
[Array]::Clear($bytes,0,$bytes.Length)
$secret=ConvertTo-SecureString -AsPlainText $plainPassword -Force
try {
    $checkpoint='service-account'
    if (-not $info.sid) {
        $account=Microsoft.PowerShell.LocalAccounts\New-LocalUser @accountOptions -Password $secret
        $info.sid=$account.SID.Value
        Save-Enrollment $info
    } else {
        Set-LocalUser -SID $account.SID -Password $secret
    }
    $checkpoint='account-access'
    $membersId=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')
    if ($account.SID.Value -notin @((Get-LocalGroupMember -SID $membersId | ForEach-Object {$_.SID.Value}))) {
        Add-LocalGroupMember -SID $membersId -Member $localUser
    }
    Need ($account.SID.Value -notin @((Get-LocalGroupMember -SID $adminsSid | ForEach-Object {$_.SID.Value}))) 'Service identity is an administrator'
    Lock-Directory $root $account.SID 'ReadAndExecute' $false
    foreach ($dir in @('state','report')) {
        $path=Join-Path $root $dir
        if (-not [IO.Directory]::Exists($path)) { $null=[IO.Directory]::CreateDirectory($path) }
        Plain $path
        Lock-Directory $path $account.SID 'Modify' ($dir -eq 'report')
    }
    # Register before the first profile logon. Windows can now restart the limited supervisor at boot.
    $checkpoint='registering-task'
    Log-Enrollment $checkpoint
    $taskOptions=Home-TaskOptions
    if ($current) { $taskOptions.Force=$true }
    $null=Register-ScheduledTask @taskOptions -Password $plainPassword
    $created=Get-ScheduledTask -TaskPath '\' -TaskName $task
    Verify-Task $created $account.SID
    Permit-LimitedTaskRetry
    Log-Enrollment 'task-registered'
    $checkpoint='starting-supervisor'
    $credential=[PSCredential]::new($localUser,$secret)
    Start-HomeSupervisor $credential $account.SID.Value
} catch {
    $cause=$_
    try { Log-Enrollment ('failed-'+$checkpoint) (Error-Code $cause) } catch {}
    throw $cause
} finally { $plainPassword=$null; $secret.Dispose() }
} finally { $installLock.Dispose() }
