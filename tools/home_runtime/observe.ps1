# Verify a warm protected guest from Windows without starting it or reading any private files.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') {
    throw 'Wrong observer context'
}
$base=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$file=Join-Path $base 'report\status.json'
function Health([string]$url) {
    $request=[Net.HttpWebRequest]::Create($url)
    $request.Proxy=$null
    $request.AllowAutoRedirect=$false
    $request.Timeout=3500
    try { $r=$request.GetResponse() }
    catch [Net.WebException] { $r=$_.Exception.Response; if (-not $r) { return 0 } }
    try {
        $code=[int]$r.StatusCode
        if ($code -eq 200 -and $url.EndsWith('/health')) {
            $reader=[IO.StreamReader]::new($r.GetResponseStream())
            try {
                $data=New-Object char[] 1025
                $length=$reader.ReadBlock($data,0,$data.Length)
                if ($length -gt 1024 -or ((-join $data[0..($length-1)]) | ConvertFrom-Json).status -ne 'ok') { return 0 }
            } catch { return 0 } finally { $reader.Dispose() }
        }
        return $code
    } finally { $r.Close() }
}
function Account-State {
    try { $null=Get-LocalUser -Name 'AnalystAIHost' -ErrorAction Stop; return 'present' }
    catch { if ($_.FullyQualifiedErrorId -like 'UserNotFound,*') { return 'absent' }; return 'unavailable' }
}
function Scheduler-State {
    try {
        $t=Get-ScheduledTask -TaskName 'AnalystAI-HomeRuntime' -TaskPath '\' -ErrorAction Stop
        $info=Get-ScheduledTaskInfo -InputObject $t -ErrorAction Stop
        return [ordered]@{visibility='visible';state=[string]$t.State;
            last_result=('0x{0:X8}' -f ([long]$info.LastTaskResult -band 4294967295L));
            boot_trigger=(@($t.Triggers).Count -eq 1 -and $t.Triggers[0].CimClass.CimClassName -eq 'MSFT_TaskBootTrigger');
            limited=([string]$t.Principal.RunLevel -eq 'Limited')}
    } catch {
        $why=if ($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound*') { 'not_listed' } else { 'unavailable' }
    }
    # CIM enumeration can omit a task even when its own ACL permits a direct read.
    try {
        $service=New-Object -ComObject 'Schedule.Service'
        $service.Connect()
        $task=$service.GetFolder('\').GetTask('AnalystAI-HomeRuntime')
        $def=$task.Definition
        $states=@('Unknown','Disabled','Queued','Ready','Running')
        return [ordered]@{visibility='visible';state=$states[[int]$task.State];
            last_result=('0x{0:X8}' -f ([long]$task.LastTaskResult -band 4294967295L));
            boot_trigger=($def.Triggers.Count -eq 1 -and $def.Triggers.Item(1).Type -eq 8);
            limited=($def.Principal.RunLevel -eq 0)}
    } catch {
        $errorDetail=$_.Exception.GetBaseException()
        return [ordered]@{visibility=$why;direct_read=('0x{0:X8}' -f ([long]$errorDetail.HResult -band 4294967295L))}
    }
}
function Profile-State {
    try {
        $u=Get-LocalUser -Name 'AnalystAIHost' -ErrorAction Stop
        $key='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$u.SID.Value
        if (Test-Path -LiteralPath $key -ErrorAction Stop) { return 'present' }
        return 'absent'
    } catch { return 'unavailable' }
}
function Installer-State {
    $file=Join-Path $base 'install-status\status.json'
    try {
        if ((Get-Item -Force -LiteralPath $file).Length -gt 4096) { throw 'Oversized receipt' }
        $r=Get-Content -Raw -LiteralPath $file | ConvertFrom-Json
        $label=[string]$r.stage
        $code=[string]$r.code
        $allowed='^(receipt-verified|task-registered|starting-task|start-needs-profile|loading-profile|native-profile-recovery|profile-present-after-logon|retrying-task|waiting-worker|existing-supervisor|registering-task|worker-(?:failed-)?(?:windows|import|configure|application|local-model|login-check|supervising)|failed-(?:entry|service-account|account-access|registering-task|starting-supervisor))$'
        if ($r.package -ne 'd958608239005290f808' -or $label -notmatch $allowed -or $code -notmatch '^(?:|win32--?[0-9]{1,10}|hresult-[0-9A-F]{8}|task-[0-9A-F]{8})$') { throw 'Unknown receipt' }
        if (-not $r.utc) { throw 'Missing journal time' }
        $stamp=[DateTimeOffset]$r.utc
        return [ordered]@{stage=$label;code=$code;written_utc=$stamp.UtcDateTime.ToString('o')}
    } catch { return [ordered]@{stage='unavailable';code=''} }
}
function Subsequent-Boot {
    try {
        $set=(Get-LocalUser -Name 'AnalystAIHost' -ErrorAction Stop).PasswordLastSet
        if (-not $set) { return 'unknown' }
        $boot=(Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime.ToUniversalTime()
        if ($boot -gt $set.ToUniversalTime()) { return 'observed' }
        return 'same_boot'
    } catch { return 'unknown' }
}
function Observe {
    try {
        $row=Get-Content -ErrorAction Stop -Raw -LiteralPath $file | ConvertFrom-Json
        if ($row.package -ne 'd958608239005290f808' -or [string]$row.phase -notmatch '^(?:failed-)?(?:windows|import|configure|application|local-model|login-check|supervising)$') {
            throw [IO.InvalidDataException]::new('Foreign receipt')
        }
        $phase=[string]$row.phase
    } catch [Management.Automation.ItemNotFoundException] { $phase='awaiting_enrollment' }
      catch [UnauthorizedAccessException] { $phase='status_not_readable' }
      catch { $phase='status_unavailable' }
    return [ordered]@{phase=$phase;checked_utc=[DateTime]::UtcNow.ToString('o');account=(Account-State);profile=(Profile-State);scheduler=(Scheduler-State);installer=(Installer-State);windows_reboot=(Subsequent-Boot);health=(Health 'http://127.0.0.1:18158/health');anonymous=(Health 'http://127.0.0.1:18158/me')}
}
$deadline=[DateTime]::UtcNow.AddMinutes(3)
$last=''
$healthy=0
do {
    $status=Observe
    $key="$($status.phase)/$($status.account)/$($status.profile)/$($status.scheduler.visibility)/$($status.scheduler.state)/$($status.scheduler.last_result)/$($status.installer.stage)/$($status.installer.written_utc)/$($status.health)/$($status.anonymous)"
    if ($last -ne $key) { Write-Output ('HOME_PROTECTED_OBSERVATION='+($status | ConvertTo-Json -Compress)) }
    $last=$key
    if ($status.phase -eq 'supervising' -and $status.account -eq 'present' -and $status.profile -eq 'present' -and
        $status.scheduler.state -eq 'Running' -and $status.scheduler.boot_trigger -and $status.scheduler.limited -and
        $status.health -eq 200 -and $status.anonymous -eq 401) {
        $healthy++
        if ($healthy -ge 2) {
            Write-Output ('HOME_PROTECTED_READY='+($status | ConvertTo-Json -Compress))
            return
        }
    } else { $healthy=0 }
    if ($status.phase -like 'failed-*') { break }
    Start-Sleep -Seconds 15
} while ([DateTime]::UtcNow -lt $deadline)
Write-Output ('HOME_PROTECTED_PENDING='+($status | ConvertTo-Json -Compress))
exit 3
