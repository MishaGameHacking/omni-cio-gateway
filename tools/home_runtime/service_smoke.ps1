param([string]$Setup,[string]$Cs)
$ErrorActionPreference='Stop'
if ($env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or $env:GITHUB_ACTIONS -ne 'true' -or $env:COMPUTERNAME -eq 'LAPTOP-NPSGA016') { throw 'Disposable runner required' }
$stage='fixture'
trap {
    $e=$_.Exception.GetBaseException()
    $tag=$e.Message -replace '[^A-Za-z0-9 ._-]',''
    if ($tag.Length -gt 180) { $tag=$tag.Substring(0,180) }
    Write-Output ('HOME_SCM_QA_ERROR='+(@{stage=$stage;line=$_.InvocationInfo.ScriptLineNumber;reason=$tag;type=$e.GetType().Name}|ConvertTo-Json -Compress))
    exit 1
}
$root=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$task='AnalystAI-HomeRuntime'
$service='AnalystAIHomeHost'
$user='AnalystAIHost'
$account=$env:COMPUTERNAME+'\'+$user
if ((Test-Path $root) -or (Get-LocalUser $user -ErrorAction SilentlyContinue) -or (Get-Service $service -ErrorAction SilentlyContinue) -or
    (Get-ScheduledTask -TaskName $task -TaskPath '\' -ErrorAction SilentlyContinue)) { throw 'Test fixture already in use' }
$plain='Aa1!'+[guid]::NewGuid().ToString('N')+[guid]::NewGuid().ToString('N')
$pass=ConvertTo-SecureString $plain -AsPlainText -Force
$member=New-LocalUser $user -Description 'Analyst AI home runtime' -Password $pass -PasswordNeverExpires
try {
    $null=New-Item -ItemType Directory -Path $root
    $null=New-Item -ItemType Directory -Path (Join-Path $root 'install-status'),(Join-Path $root 'report')
    $record=@{machine=$env:COMPUTERNAME;marker='analyst-home-runtime-v1';sid=$member.SID.Value;package='d958608239005290f808'}
    [IO.File]::WriteAllText((Join-Path $root 'enrollment.json'),($record|ConvertTo-Json -Compress))
    [IO.File]::WriteAllText((Join-Path $root 'enrollment.lock'),'')
    $null=& icacls.exe $root /grant ('*'+$member.SID.Value+':(OI)(CI)RX')
    if ($LASTEXITCODE) { throw 'Cannot allow fixture read' }
    $report=Join-Path $root 'report'
    $null=& icacls.exe $report /grant ('*'+$member.SID.Value+':(OI)(CI)M')
    if ($LASTEXITCODE) { throw 'Cannot allow fixture witness' }
    $worker=Join-Path $root 'Run-AnalystAIHome.ps1'
    $proof=@'
$ErrorActionPreference='Stop'
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$root=$PSScriptRoot
$expected=(Get-Content (Join-Path $root 'enrollment.json') -Raw|ConvertFrom-Json).sid
$admin=[Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($admin -or $id.User.Value -ne $expected -or -not (Test-Path -LiteralPath ('Registry::HKEY_USERS\'+$expected))) { exit 41 }
$dest=Join-Path $root 'report\witness.json'
$tmp=$dest+'.next'
$witness=@{limited=$true;profile=$true;pid=$PID;session=[Diagnostics.Process]::GetCurrentProcess().SessionId}
[IO.File]::WriteAllText($tmp,($witness|ConvertTo-Json -Compress))
if ([IO.File]::Exists($dest)) { [IO.File]::Replace($tmp,$dest,[NullString]::Value) } else { [IO.File]::Move($tmp,$dest) }
while ($true) { Start-Sleep 5 }
'@
    [IO.File]::WriteAllText($worker,$proof)
    $digest=(Get-FileHash $worker -Algorithm SHA256).Hash.ToLowerInvariant()
    $shell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $a=New-ScheduledTaskAction -Execute $shell -Argument ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$worker+'"')
    $null=Register-ScheduledTask -TaskName $task -TaskPath '\' -Action $a -Trigger (New-ScheduledTaskTrigger -AtStartup) -RunLevel Limited -User $account -Password $plain
    $plain=$null
    $source=[IO.File]::ReadAllText($Cs)
    function Witness([int]$oldPid) {
        for ($i=0;$i -lt 35;$i++) {
            $p=Join-Path $root 'report\witness.json'
            if ([IO.File]::Exists($p)) {
                $w=Get-Content -Raw $p|ConvertFrom-Json
                if ($w.limited -and $w.profile -and $w.session -eq 0 -and $w.pid -ne $oldPid) { return $w.pid }
            }
            Start-Sleep 1
        }
        throw 'Limited worker did not witness its own profile'
    }
    $stage='activate'; & $Setup -HostSource $source -HostedFixtureDigest $digest
    $stage='service-witness'; $first=Witness 0
    $t=Get-ScheduledTask -TaskName $task -TaskPath '\'
    if ($t.Settings.Enabled) { throw 'Two boot mechanisms active' }
    $credTime=(Get-LocalUser $user).PasswordLastSet
    $stage='repeat-active'; & $Setup -HostSource $source -HostedFixtureDigest $digest
    if ((Get-LocalUser $user).PasswordLastSet -ne $credTime -or (Witness 0) -ne $first) { throw 'Active process or credential changed on retry' }
    $sc=Join-Path $env:SystemRoot 'System32\sc.exe'
    $sd=[Security.AccessControl.RawSecurityDescriptor]::new(((& $sc sdshow $service) -join '').Trim())
    $aces=@($sd.DiscretionaryAcl | Where-Object { $_.SecurityIdentifier.Value -eq 'S-1-5-20' -and $_.AceQualifier -eq 'AccessAllowed' })
    if ($aces.Count -ne 1 -or $aces[0].AccessMask -ne 0x20015) { throw 'Service observer grant is not query and start only' }
    $stage='stop-restart';Stop-Service $service
    if (Get-Process -Id $first -ErrorAction SilentlyContinue) { throw 'Child survived service stop' }
    Start-Service $service
    $second=Witness $first
    $entry=Get-CimInstance Win32_Service -Filter "Name='AnalystAIHomeHost'"
    if ($entry.State -ne 'Running' -or $entry.StartMode -ne 'Auto' -or $entry.StartName -notin @($account,('.\'+$user))) { throw 'Unexpected service identity or start mode' }
    Write-Output ('HOME_SCM_QA='+(@{registration='real';standard_account=$true;session_zero=$true;profile=$true;automatic=$true;
        observer_mask='0x20015';previous_task_disabled=$true;repeat_kept_process=$true;worker_stopped=$true;restart_new_process=($second -ne $first);
        real_reboot=$false;test_guest='fixture'}|ConvertTo-Json -Compress))
} finally {
    $plain=$null;$pass.Dispose()
    if (Get-Service $service -ErrorAction SilentlyContinue) { Stop-Service $service -ErrorAction SilentlyContinue; $null=& sc.exe delete $service }
    if (Get-ScheduledTask -TaskName $task -TaskPath '\' -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $task -TaskPath '\' -Confirm:$false }
    Remove-LocalUser -SID $member.SID
    # The disposable runner erases the test installation; the loaded .NET assembly may remain open until exit.
}
