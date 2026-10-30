$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016') { throw 'wrong owner host' }
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne 'S-1-5-20') { throw 'wrong service identity' }
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AnalystScmAccess {
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  public static extern IntPtr OpenSCManager(string machine,string db,uint access);
  [DllImport("advapi32.dll")] public static extern bool CloseServiceHandle(IntPtr h);
}
'@
$h=[AnalystScmAccess]::OpenSCManager($null,$null,2)
$scmError=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
$scm=($h -ne [IntPtr]::Zero)
if($scm){$null=[AnalystScmAccess]::CloseServiceHandle($h)}
$features=@{}
try {
    foreach($f in @(Get-CimInstance Win32_OptionalFeature -Filter "Name='Microsoft-Hyper-V-All' OR Name='Microsoft-Hyper-V' OR Name='VirtualMachinePlatform' OR Name='Microsoft-Windows-Subsystem-Linux' OR Name='HypervisorPlatform'")) {
        $features[[string]$f.Name]=[int]$f.InstallState
    }
} catch {}
# Register a disjoint, limited, harmless task under the calling identity and remove just this probe.
$name='AnalystAI-Permissions-'+$env:GITHUB_RUN_ID+'-'+$env:GITHUB_RUN_ATTEMPT
$created=$false
$taskResult='unknown'
$cleanup=$true
try {
    $scheduler=New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    $folder=$scheduler.GetFolder('\')
    $td=$scheduler.NewTask(0)
    $td.RegistrationInfo.Description='Analyst AI owner boot-permission probe'
    $td.Principal.UserId='S-1-5-20'
    $td.Principal.LogonType=5
    $td.Principal.RunLevel=0
    $t=$td.Triggers.Create(8)
    $t.Enabled=$true
    $act=$td.Actions.Create(0)
    $act.Path=[IO.Path]::Combine($env:SystemRoot,'System32','cmd.exe')
    $act.Arguments='/d /c exit 0'
    $null=$folder.RegisterTaskDefinition($name,$td,2,'S-1-5-20',$null,5,$null)
    $created=$true
    $taskResult='accepted'
} catch { $taskResult=('0x{0:X8}' -f ($_.Exception.HResult)) }
finally { if($created){ try{$folder.DeleteTask($name,0)}catch{$cleanup=$false}} }
$ts=$null
foreach($path in @((Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'), "$env:SystemDrive\Program Files (x86)\Tailscale\tailscale.exe")){
    if(Test-Path -LiteralPath $path -PathType Leaf){$ts=$path;break}
}
$tail='cli_absent'
$tailOnline=$null
if($ts){
    try {
        $text=(& $ts status --json 2>$null | Out-String)
        if($LASTEXITCODE -eq 0){$j=$text|ConvertFrom-Json;$tail='read_ok';$tailOnline=($j.BackendState -eq 'Running' -and $j.Self.Online)}
        else{$tail='status_unavailable'}
    }catch{$tail='status_unavailable'}
}
$fw=Get-Service -Name vmms -ErrorAction SilentlyContinue
$os=Get-CimInstance Win32_OperatingSystem
$wslCmd=(Join-Path $env:SystemRoot 'System32\wsl.exe')
$distros=((& $wslCmd -l -q 2>$null | Out-String)-replace "\x00",'')
[ordered]@{
    admin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    scm_create_allowed=$scm
    scm_error=$(if($scm){0}else{$scmError})
    features=$features
    vmms=$(if($fw){[string]$fw.Status}else{'not_visible'})
    hyperv_admin=$principal.IsInRole([Security.Principal.SecurityIdentifier]::new('S-1-5-32-578'))
    boot_limited_task=$taskResult
    probe_removed=$cleanup
    build_distro=($distros -split '\s+' -ccontains 'Ubuntu-24.04')
    home_distro=($distros -split '\s+' -ccontains 'AnalystAI-Home')
    tailscale=$tail
    tail_online=$tailOnline
    free_bytes=([IO.DriveInfo]::new($env:SystemDrive)).AvailableFreeSpace
} | ConvertTo-Json -Compress -Depth 4
