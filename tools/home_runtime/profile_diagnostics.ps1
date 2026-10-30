# Only facts relevant to the dedicated account. Event text, paths, user and machine SIDs stay on the host.
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Wrong observer' }
$user=Get-LocalUser -Name 'AnalystAIHost'
$ids=$user.SID.Value
$reg='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'
$props=Get-ItemProperty -LiteralPath $reg
function Category([string]$data) {
    if ($data -match '(?i)ntuser\.dat') { return 'user_hive' }
    if ($data -match '(?i)usrclass\.dat') { return 'class_hive' }
    if ($data -match '(?i)\\default\\') { return 'default_template' }
    return 'other'
}
function Exists-State([string]$name) {
    try { $null=Get-Item -LiteralPath $name -Force -ErrorAction Stop; return 'present' }
    catch [Management.Automation.ItemNotFoundException] { return 'absent' }
    catch { return 'unreadable' }
}
$default=[Environment]::ExpandEnvironmentVariables([string]$props.Default)
$profiles=[Environment]::ExpandEnvironmentVariables([string]$props.ProfilesDirectory)
$info=[ordered]@{account_enabled=$user.Enabled;account_password_set=[bool]$user.PasswordLastSet;
    registered_profile=(Exists-State ($reg+'\'+$ids));
    duplicate_profile_entry=(Exists-State ($reg+'\'+$ids+'.bak'));
    project_profile_directory=(Exists-State (Join-Path $profiles 'AnalystAIHost'));
    default_template=(Exists-State $default);default_hive=(Exists-State (Join-Path $default 'NTUSER.DAT'));
    profile_service=[string](Get-Service ProfSvc).Status;secondary_logon=[string](Get-Service seclogon).Status;
    schedule_service=[string](Get-Service Schedule).Status;events=@();event_access='no_matching_error'}
$since=([DateTime]::Now).AddMinutes(-30)
try {
    $events=@(Get-WinEvent -FilterHashtable @{LogName='Application';ProviderName='Microsoft-Windows-User Profiles Service';StartTime=$since;Level=1,2,3} -MaxEvents 70 -ErrorAction Stop)
    $bound=@()
    foreach ($e in $events) {
        $raw=$e.ToXml()
        $delta=if ($user.PasswordLastSet) { [math]::Abs(($e.TimeCreated-$user.PasswordLastSet).TotalSeconds) } else { 999999 }
        $targeted=$raw -match '(?i)AnalystAIHost' -or $raw.Contains($ids)
        if (-not $targeted -and $delta -gt 60) { continue }
        $xml=[xml]$raw
        $codes=@()
        foreach ($node in @($xml.Event.EventData.Data)) {
            if ($null -eq $node -or -not $node.Attributes) { continue }
            $attr=$node.Attributes['Name']
            if ($attr -and $attr.Value -match '(?i)error|result|status' -and $node.InnerText -match '^(?:-?[0-9]{1,11}|0x[0-9A-Fa-f]{1,8})$') {
                $codes += $node.InnerText
            }
        }
        $bound += [ordered]@{event_id=$e.Id;direct_match=$targeted;near_account_change=($delta -le 60);item=(Category $raw);codes=$codes}
    }
    $info.events=$bound
    $info.event_access='inspected'
} catch { if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { $info.event_access='unavailable' } }
try {
    $t=Get-ScheduledTask -TaskName 'AnalystAI-HomeRuntime' -TaskPath '\' -ErrorAction Stop
    $info.task=[string]$t.State
} catch { $info.task=if ($_.FullyQualifiedErrorId -like 'CmdletizationQuery_NotFound*') { 'not_listed' } else { 'unavailable' } }
try {
    $runners=@(Get-CimInstance Win32_Service -Filter "Name LIKE 'actions.runner.%' AND State='Running'")
    $info.runner_contexts=[ordered]@{total=$runners.Count;network_service=@($runners | Where-Object { ($_.StartName -replace '[\s_]','') -match '(?i)NETWORKSERVICE$' }).Count;
        system=@($runners | Where-Object { $_.StartName -in 'LocalSystem','NT AUTHORITY\SYSTEM' }).Count}
} catch { $info.runner_contexts='unavailable' }
try {
    # Inspect only failed logons naming the project account. No account or event text leaves Windows.
    $q="*[System[(EventID=4625) and TimeCreated[timediff(@SystemTime) <= 3600000]] and EventData[Data[@Name='TargetUserName']='AnalystAIHost']]"
    $matches=@(Get-WinEvent -LogName Security -FilterXPath $q -MaxEvents 4 -ErrorAction Stop)
    $info.batch_errors=@(foreach ($entry in $matches) {
        $known=@{}
        foreach ($n in @(([xml]$entry.ToXml()).Event.EventData.Data)) {
            $k=$n.GetAttribute('Name')
            if ($k -in 'Status','SubStatus','LogonType' -and $n.InnerText -match '^(?:0x[0-9A-Fa-f]{1,8}|[0-9]{1,3})$') { $known[$k]=$n.InnerText }
        }
        if ($known.LogonType -eq '4') { [ordered]@{status=$known.Status;substatus=$known.SubStatus;utc=$entry.TimeCreated.ToUniversalTime().ToString('o')} }
    })
} catch { $info.batch_errors=if ($_.FullyQualifiedErrorId -like 'NoMatchingEventsFound*') { 'none' } else { 'unavailable' } }
Write-Output ('HOME_PROFILE_DIAG='+($info | ConvertTo-Json -Depth 5 -Compress))
