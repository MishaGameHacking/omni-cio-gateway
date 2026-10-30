# One ordinary, authorization-checked retry of the exact already-enrolled limited boot task.
# No task/ACL modification, credentials, passwords or private event messages are used.
$ErrorActionPreference='Stop'
trap {
    $why=$_.Exception.GetBaseException()
    $summary=[ordered]@{phase='diagnostic-fault';line=$_.InvocationInfo.ScriptLineNumber;type=$why.GetType().Name;hresult=('0x{0:X8}' -f ([long]$why.HResult -band 4294967295L))}
    Write-Output ('HOME_REGISTERED_RETRY='+($summary | ConvertTo-Json -Compress))
    exit 1
}
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Unexpected observer' }
$identity=(Get-LocalUser -Name AnalystAIHost).SID.Value
$exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$program=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime\Run-AnalystAIHome.ps1'
$old='62eab414a3ceb2aceabb63d056a05dbeb9fbbeba5dcdefb481ca5d6e2aea85ed'
$installer=Join-Path $env:SystemRoot ('ServiceProfiles\NetworkService\AppData\Local\AnalystAI-HomeLab\installer-'+$old+'\Install-AnalystAIHome.ps1')
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash -ne $old) { throw 'Foreign previous installer' }
$script=[IO.File]::ReadAllText($installer)
$start=$script.IndexOf("    `$probe=@'")
$end=$script.IndexOf("'@",$start+16)
if ($start -lt 0 -or $end -lt 0) { throw 'Original profile probe missing' }
$probe=$script.Substring($start,$end-$start).Split(@([char]10),2)[1].TrimEnd([char]13,[char]10).Replace('EXPECTED_SID',$identity)
$originalArguments='-NoLogo -NoProfile -NonInteractive -EncodedCommand '+[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
$r=[ordered]@{original_command_chars=($exe.Length+3+$originalArguments.Length);win32_limit_chars=1024;
    profile_service=[string](Get-Service ProfSvc).Status;secondary_logon=[string](Get-Service seclogon).Status;phase='connect';events=@()}
$base=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$readyToRetry=$false
try {
    $journal=Get-Content -Raw -LiteralPath (Join-Path $base 'install-status\status.json') | ConvertFrom-Json
    if ($journal.package -eq 'd958608239005290f808' -and $journal.stage -match '^(?:[a-z]+-)*[a-z]+$' -and $journal.stage.Length -le 48) {
        $r.install_stage=[string]$journal.stage
        $stamp=[DateTimeOffset]$journal.utc
        $r.install_utc=$stamp.UtcDateTime.ToString('o')
        if ($journal.code -match '^(?:task-[0-9A-F]{8}|win32--?[0-9]{1,10}|hresult-[0-9A-F]{8})$') { $r.install_code=$journal.code }
        $readyToRetry=($journal.stage -eq 'waiting-worker' -and ([DateTimeOffset]::UtcNow-$stamp).TotalMinutes -ge 2)
    }
} catch { $r.install_stage='unavailable' }
$r.has_profile=Test-Path -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$identity)
function NativeCode($err) {
    $e=$err.Exception
    while ($null -ne $e.InnerException) { $e=$e.InnerException }
    return ('0x{0:X8}' -f ([long]$e.HResult -band 4294967295L))
}
try {
    $svc=New-Object -ComObject 'Schedule.Service';$svc.Connect()
    $r.phase='folder'
    $folder=$svc.GetFolder('\')
    $r.phase='lookup'
    $registered=$folder.GetTask('AnalystAI-HomeRuntime')
    $d=$registered.Definition
    $expected='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$program+'"'
    if ($d.Actions.Count -ne 1 -or $d.Actions.Item(1).Path -ne $exe -or $d.Actions.Item(1).Arguments -ne $expected -or
        $d.Principal.UserId -notin @($identity,($env:COMPUTERNAME+'\AnalystAIHost'),'AnalystAIHost') -or
        $d.Principal.RunLevel -ne 0 -or $d.Principal.LogonType -ne 1 -or $d.Triggers.Count -ne 1 -or $d.Triggers.Item(1).Type -ne 8) { throw 'Task identity mismatch' }
    $r.last_result=('0x{0:X8}' -f ([long]$registered.LastTaskResult -band 4294967295L));$r.task_state=[int]$registered.State
    if ($registered.State -eq 3 -and $r.has_profile -and $readyToRetry) { $r.phase='run';$null=$registered.Run($null);$r.phase='requested' }
    else { $r.phase='observed' }
} catch { $r.code=NativeCode $_ }
if ($r.phase -eq 'lookup' -and $r.code -eq '0x80070005' -and $readyToRetry -and $r.has_profile -and
    $r.install_code -eq 'task-00041303') {
    # Try the registered task by its exact name. The scheduler enforces its execution permission.
    $psi=[Diagnostics.ProcessStartInfo]::new()
    $psi.FileName=Join-Path $env:SystemRoot 'System32\schtasks.exe'
    $psi.Arguments='/Run /TN "\AnalystAI-HomeRuntime"'
    $psi.UseShellExecute=$false
    $psi.CreateNoWindow=$true
    $psi.RedirectStandardOutput=$true
    $psi.RedirectStandardError=$true
    $command=[Diagnostics.Process]::new()
    try {
        $command.StartInfo=$psi
        $null=$command.Start()
        $stdout=$command.StandardOutput.ReadToEndAsync()
        $stderr=$command.StandardError.ReadToEndAsync()
        if ($command.WaitForExit(12000)) {
            $null=$stdout.GetAwaiter().GetResult()
            $message=$stderr.GetAwaiter().GetResult()
            $r.direct_exit=$command.ExitCode
            $r.direct_reason=if ($message -match '(?i)access is denied|access denied|0x80070005') { 'access-denied' } else { 'not_classified' }
        } else { $command.Kill();$r.direct_reason='timeout' }
    } catch { $r.direct_error=NativeCode $_ } finally { $command.Dispose() }
}
try {
    $r.task_history_enabled=[bool](Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational').IsEnabled
    $query="*[System[TimeCreated[timediff(@SystemTime) <= 3600000]] and EventData[Data[@Name='TaskName']='\AnalystAI-HomeRuntime']]"
    $items=@(Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' -FilterXPath $query -MaxEvents 12 -ErrorAction Stop)
    foreach($item in $items) {
        $codes=@()
        foreach($node in @(([xml]$item.ToXml()).Event.EventData.Data)){
            if ($node.Attributes -and $node.Attributes['Name'] -and $node.Attributes['Name'].Value -match '^(ResultCode|ErrorValue|ErrorCode)$' -and $node.InnerText -match '^(?:[0-9]{1,10}|0x[0-9a-fA-F]{1,8})$') { $codes+=$node.InnerText }
        }
        $r.events+=@([ordered]@{id=$item.Id;utc=$item.TimeCreated.ToUniversalTime().ToString('o');codes=$codes})
    }
    $r.events_status='inspected'
} catch { $r.events_status=if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') {'none'} else {'unavailable'} }
Write-Output ('HOME_REGISTERED_RETRY='+($r | ConvertTo-Json -Depth 5 -Compress))
exit 0
