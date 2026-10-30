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
$description = 'Dedicated account for the Analyst AI home deployment.'
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
function Verify-Task($t,$sid) {
    $action=@($t.Actions)
    $target=Join-Path $root 'Run-AnalystAIHome.ps1'
    $expectedArgs='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$target+'"'
    Need ($action.Count -eq 1 -and $action[0].Execute -eq $winPS -and $action[0].Arguments -eq $expectedArgs) 'Unexpected task program'
    Need ($t.Principal.UserId -in @($localUser,$sid.Value,$name) -and [string]$t.Principal.RunLevel -eq 'Limited' -and
          [string]$t.Principal.LogonType -eq 'Password' -and @($t.Triggers).Count -eq 1 -and
          $t.Triggers[0].CimClass.CimClassName -eq 'MSFT_TaskBootTrigger') 'Unexpected task identity or trigger'
}
$winPS=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if ($VerifyOnly) {
    foreach ($file in $expected.Keys) { Check-File (Source $file) $expected[$file] }
    Check-Scripts $stage
    Need ([IO.FileInfo]::new((Source 'model.litertlm')).Length -eq 3659530240) 'Incorrect model size'
    [PSCustomObject]@{package=$PackageCode;items=$expected.Count;media_sha256='verified';powershell_syntax='valid';requires_admin_for_boot=$true} | ConvertTo-Json -Compress
    return
}
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
$info=Read-Enrollment
if ($info.sid) {
    $account=Get-LocalUser -Name $name
    Need ($account.SID.Value -eq $info.sid -and $account.Description -eq $description) 'Owned account identity changed'
    $current=Get-ScheduledTask -TaskPath '\' -TaskName $task -ErrorAction SilentlyContinue
    if ($current) {
        Verify-Task $current $account.SID
        if ($current.State -ne 'Running') { Start-ScheduledTask -TaskPath '\' -TaskName $task }
        Write-Output 'Enrolled. Local service startup has been requested.'
        return
    }
} else {
    Need (-not (Get-LocalUser -Name $name -ErrorAction SilentlyContinue)) 'The local account name is occupied'
}
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
Check-Scripts $root
# The only password exists in this process and in the Windows scheduler credential store.
$bytes=New-Object byte[] 48
$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
$plainPassword='Aa1!'+[Convert]::ToBase64String($bytes)
[Array]::Clear($bytes,0,$bytes.Length)
$secret=ConvertTo-SecureString -AsPlainText $plainPassword -Force
try {
    if (-not $info.sid) {
        $account=New-LocalUser -Name $name -Password $secret -PasswordNeverExpires -UserMayNotChangePassword -Description $description
        $info.sid=$account.SID.Value
        Save-Enrollment $info
    } else {
        Set-LocalUser -SID $account.SID -Password $secret
    }
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
    $profileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$account.SID.Value
    if (-not (Test-Path -LiteralPath $profileKey)) {
        Add-Type -Namespace AnalystHome -Name UserEnvironment -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("userenv.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode)]
public static extern int CreateProfile(string sid,string user,System.Text.StringBuilder path,uint size);
'@
        $buffer=[Text.StringBuilder]::new(1024)
        $hr=[AnalystHome.UserEnvironment]::CreateProfile($account.SID.Value,$name,$buffer,1024)
        Need ($hr -eq 0 -or (Test-Path -LiteralPath $profileKey)) 'Could not create the dedicated WSL user profile'
    }
    $action=New-ScheduledTaskAction -Execute $winPS -Argument ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+(Join-Path $root 'Run-AnalystAIHome.ps1')+'"')
    $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 2)
    $null=Register-ScheduledTask -TaskPath '\' -TaskName $task -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -Settings $settings -User $localUser -Password $plainPassword -RunLevel Limited -Description $description
    $created=Get-ScheduledTask -TaskPath '\' -TaskName $task
    Verify-Task $created $account.SID
    Start-ScheduledTask -TaskPath '\' -TaskName $task
    Write-Output 'Enrolled. Private Ubuntu installation has started. See C:\Program Files\AnalystAI-HomeRuntime\report\status.json.'
} finally { $plainPassword=$null; $secret.Dispose() }
