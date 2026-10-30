# Exercise CreateProcessWithLogonW on the real Lenovo using a network-only test token.
# No actual user's password is supplied; the child only checks its current local SID/hive, with no network operations.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Installer)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Wrong witness context' }
. $Installer -VerifyOnly | Out-Null
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class AnalystNativeLengthProbe {
    [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]
    struct Startup { public int Size; public string Reserved,Desktop,Title; public int X,Y,CX,CY,CharsX,CharsY,Fill,Flags;
        public short Show,ReservedBytes; public IntPtr Reserved2,Input,Output,Error; }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr Process,Thread;public uint Pid,Tid; }
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)]
    static extern bool CreateProcessWithLogonW(string user,string domain,string password,uint logonFlags,string exe,StringBuilder line,
        uint flags,IntPtr environment,string directory,ref Startup startup,out ProcessInfo info);
    [DllImport("kernel32.dll",SetLastError=true)] static extern uint WaitForSingleObject(IntPtr handle,uint timeout);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetExitCodeProcess(IntPtr handle,out uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr handle,uint code);
    public static string Run(string exe,string args,string fakeUser,string secret) {
        string command="\""+exe+"\" "+args;
        Startup s=new Startup();s.Size=Marshal.SizeOf(typeof(Startup));ProcessInfo p;
        bool ok=CreateProcessWithLogonW(fakeUser,Environment.MachineName,secret,2,exe,new StringBuilder(command,command.Length+1),
            0x08000000,IntPtr.Zero,Environment.SystemDirectory,ref s,out p);
        if(!ok) return "win32-"+Marshal.GetLastWin32Error();
        try {
            if(WaitForSingleObject(p.Process,20000)!=0){TerminateProcess(p.Process,51);return "timeout";}
            uint code;if(!GetExitCodeProcess(p.Process,out code)) return "exit-error";
            return "exit-"+code;
        } finally {CloseHandle(p.Thread);CloseHandle(p.Process);}
    }
}
'@
$fake='aiq'+[Guid]::NewGuid().ToString('N').Substring(0,13)
if (Get-LocalUser -Name $fake -ErrorAction SilentlyContinue) { throw 'Test name collision' }
$testSecret='X7!'+[Guid]::NewGuid().ToString('N')
$mySid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$targetSid=(Get-LocalUser -Name AnalystAIHost).SID.Value
$old='62eab414a3ceb2aceabb63d056a05dbeb9fbbeba5dcdefb481ca5d6e2aea85ed'
$prior=Join-Path $spool ('installer-'+$old+'\Install-AnalystAIHome.ps1')
if ((Get-FileHash -LiteralPath $prior -Algorithm SHA256).Hash -ne $old) { throw 'Original revision not verified' }
$oldCode=[IO.File]::ReadAllText($prior)
$start=$oldCode.IndexOf("    `$probe=@'")
$end=$oldCode.IndexOf("'@",$start+16)
if ($start -lt 0 -or $end -lt 0) { throw 'Missing original check' }
$body=$oldCode.Substring($start,$end-$start).Split(@([char]10),2)[1].TrimEnd([char]13,[char]10).Replace('EXPECTED_SID',$targetSid)
$oldArgs='-NoLogo -NoProfile -NonInteractive -EncodedCommand '+[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($body))
$folder=Join-Path ([IO.Path]::GetTempPath()) ('Analyst local proof '+[Guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($folder)
try {
    $file=Stage-ProfileProof $folder
    $new=Profile-ChildInfo $file $mySid $null
    $live=Profile-ChildInfo (Join-Path $root 'Check-AnalystProfile-v1.ps1') $targetSid $null
    $oldResult=[AnalystNativeLengthProbe]::Run($winPS,$oldArgs,$fake,$testSecret)
    $newResult=[AnalystNativeLengthProbe]::Run($winPS,$new.Arguments,$fake,$testSecret)
    $liveLength=$live.FileName.Length+3+$live.Arguments.Length
    if ($liveLength -ge 1024 -or ($winPS.Length+3+$oldArgs.Length) -le 1024) { throw 'Win32 bound regression' }
    $row=[ordered]@{old_chars=$winPS.Length+3+$oldArgs.Length;new_production_chars=$liveLength;win32_limit=1024;
        old_native=$oldResult;short_native=$newResult;logon_mode='network_only_local_identity';real_account_credentials_used=$false}
    Write-Output ('HOME_NATIVE_LENGTH='+($row | ConvertTo-Json -Compress))
    if ($newResult.StartsWith('exit-') -and $newResult -ne 'exit-0') { throw 'Short native proof failed locally' }
} finally { $testSecret=$null; [IO.Directory]::Delete($folder,$true) }
