# One ordinary, authorization-checked retry of the exact already-enrolled limited boot task.
# No task/ACL modification, credentials, passwords or private event messages are used.
$ErrorActionPreference='Stop'
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
function NativeCode($err) {
    $e=$err.Exception
    while ($null -ne $e.InnerException) { $e=$e.InnerException }
    return ('0x{0:X8}' -f ([long]$e.HResult -band 4294967295L))
}
try {
    $svc=New-Object -ComObject 'Schedule.Service';$svc.Connect()
    $r.phase='lookup'
    $registered=$svc.GetFolder('\').GetTask('AnalystAI-HomeRuntime')
    $d=$registered.Definition
    $expected='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$program+'"'
    if ($d.Actions.Count -ne 1 -or $d.Actions.Item(1).Path -ne $exe -or $d.Actions.Item(1).Arguments -ne $expected -or
        $d.Principal.UserId -notin @($identity,($env:COMPUTERNAME+'\AnalystAIHost'),'AnalystAIHost') -or
        $d.Principal.RunLevel -ne 0 -or $d.Principal.LogonType -ne 1 -or $d.Triggers.Count -ne 1 -or $d.Triggers.Item(1).Type -ne 8) { throw 'Task identity mismatch' }
    $r.last_result=('0x{0:X8}' -f ([long]$registered.LastTaskResult -band 4294967295L));$r.task_state=[int]$registered.State
    if ($registered.State -eq 3) { $r.phase='run';$null=$registered.Run($null);$r.phase='requested' }
    else { $r.phase='observed' }
} catch { $r.code=NativeCode $_ }
try {
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
