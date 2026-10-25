# One-time administrator setup and a narrowly scoped Windows restart task.
# No broker credentials, network requests, forced application closure or software installs.
[CmdletBinding()]
param(
    [ValidateSet('Install','Run','Status','Disable','Test')]
    [string]$Mode = 'Status',
    [switch]$KeepAwakeOnAc
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$script:TaskName = 'AnalystAI-RestartAfter12Hours'
$script:InstallRoot = Join-Path $env:ProgramData 'AnalystAI-Maintenance'
$script:InstalledScript = Join-Path $script:InstallRoot 'AnalystAI-Maintenance.ps1'
$script:LeasePath = 'C:\Windows\ServiceProfiles\NetworkService\AppData\Local\Temp\analyst-ai-emulator-lease\android.lock'
$script:ExpectedHost = 'LAPTOP-NPSGA016'
$script:TaskDescription = 'Analyst AI: restart after 12 awake hours; defer for active jobs; no forced app closure.'
$script:PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$script:ShutdownExe = Join-Path $env:SystemRoot 'System32\shutdown.exe'

if (-not ('AnalystMaintenanceClock' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class AnalystMaintenanceClock {
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool QueryUnbiasedInterruptTime(out ulong time);
}
'@
}

function Get-AwakeSeconds {
    [UInt64]$ticks = 0
    if (-not [AnalystMaintenanceClock]::QueryUnbiasedInterruptTime([ref]$ticks)) {
        throw 'Cannot read the Windows awake-time clock; restart refused.'
    }
    return [double]$ticks / 10000000.0
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Open Windows PowerShell as administrator once to install this task. Runner privileges are not changed.'
    }
}

function Assert-LocalHost {
    if ($env:COMPUTERNAME -ne $script:ExpectedHost) { throw 'This setup belongs to the designated Analyst AI laptop.' }
}

function Assert-NoReparsePoint([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    while ($null -ne $item) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'A maintenance path is a reparse point; operation refused.'
        }
        if ($item -is [IO.FileInfo]) { $item = $item.Directory } else { $item = $item.Parent }
    }
}

function Write-Status([string]$State, [double]$AwakeSeconds, [string]$Detail = '') {
    $record = [ordered]@{at_utc=[DateTime]::UtcNow.ToString('o');state=$State;awake_hours=[Math]::Round($AwakeSeconds/3600,3);detail=$Detail}
    $json = $record | ConvertTo-Json -Compress
    if ($Mode -eq 'Run') {
        $file = Join-Path $script:InstallRoot 'status.json'
        [IO.File]::WriteAllText($file,$json,[Text.UTF8Encoding]::new($false))
    }
    Write-Output $json
}

function Get-WorkBlockers {
    # Query failures propagate: absence of a readable process list is not idle.
    $processes = @(Get-CimInstance Win32_Process)
    $blocked = @($processes | Where-Object {
        $_.Name -eq 'Runner.Worker.exe' -or
        $_.Name -match '^(emulator|qemu-system-.+|msiexec|TiWorker)\.exe$' -or
        ($_.Name -match '^java(w)?\.exe$' -and $_.CommandLine -match 'GradleWrapperMain|org\.gradle\.launcher\.GradleMain')
    })
    return @($blocked | Select-Object -ExpandProperty Name -Unique)
}

function Get-RestartDecision([double]$Seconds,[bool]$Busy,[bool]$Paused,[double]$LastAttempt = -3600) {
    if ([double]::IsNaN($Seconds) -or [double]::IsInfinity($Seconds) -or $Seconds -lt 0) { throw 'Invalid awake time.' }
    if ($Paused) { return 'paused' }
    if ($Seconds -lt 43200) { return 'not_due' }
    if ($Busy) { return 'busy' }
    if ($Seconds -ge $LastAttempt -and ($Seconds-$LastAttempt) -lt 3600) { return 'retry_cooldown' }
    return 'eligible'
}

function New-RestartTaskDefinition {
    $action = New-ScheduledTaskAction -Execute $script:PowerShellExe -Argument ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$script:InstalledScript+'" -Mode Run')
    $startup = New-ScheduledTaskTrigger -AtStartup
    $periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
    $principal = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
    return New-ScheduledTask -Action $action -Trigger @($startup,$periodic) -Settings $settings -Principal $principal -Description $script:TaskDescription
}

function Get-ExistingTask {
    return Get-ScheduledTask -TaskName $script:TaskName -TaskPath '\' -ErrorAction SilentlyContinue
}

function Assert-OwnedTask($Task) {
    if ($null -ne $Task -and $Task.Description -ne $script:TaskDescription) {
        throw 'A different task already uses this name; it will not be overwritten.'
    }
}

function Get-PowerSnapshot {
    $powercfg = Join-Path $env:SystemRoot 'System32\powercfg.exe'
    $schemeText = (& $powercfg /getactivescheme | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the active power plan.' }
    $schemeMatch = [regex]::Match($schemeText,'[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')
    if (-not $schemeMatch.Success) { throw 'Cannot identify the active power plan.' }
    $snapshot = [ordered]@{scheme=$schemeMatch.Value;settings=@()}
    foreach ($entry in @(@('SUB_SLEEP','STANDBYIDLE'),@('SUB_SLEEP','HIBERNATEIDLE'),@('SUB_BUTTONS','LIDACTION'))) {
        $raw = (& $powercfg /qh $schemeMatch.Value $entry[0] $entry[1] | Out-String)
        if ($LASTEXITCODE -ne 0) { throw 'Cannot read a power setting; settings left unchanged.' }
        $indices = [regex]::Matches($raw,'0x[0-9a-fA-F]{8}')
        if ($indices.Count -lt 2) { throw 'Cannot parse a power setting; settings left unchanged.' }
        $snapshot.settings += @{subgroup=$entry[0];setting=$entry[1];ac=[Convert]::ToUInt32($indices[$indices.Count-2].Value.Substring(2),16)}
    }
    return $snapshot
}

function Set-AcPowerValues($Snapshot,[bool]$Restore) {
    $powercfg = Join-Path $env:SystemRoot 'System32\powercfg.exe'
    foreach ($entry in $Snapshot.settings) {
        $value = if ($Restore) { $entry.ac } else { 0 }
        & $powercfg /setacvalueindex $Snapshot.scheme $entry.subgroup $entry.setting $value
        if ($LASTEXITCODE -ne 0) { throw 'Cannot apply an AC power setting.' }
    }
    & $powercfg /setactive $Snapshot.scheme
    if ($LASTEXITCODE -ne 0) { throw 'Cannot activate the power settings.' }
}

function Install-Maintenance {
    Assert-Administrator
    Assert-LocalHost
    Assert-OwnedTask (Get-ExistingTask)
    Assert-NoReparsePoint $script:LeasePath
    $services = @(Get-CimInstance Win32_Service -Filter "Name LIKE 'actions.runner.%'" | Where-Object {$_.Name -like '*omni-cio-gateway*'})
    if ($services.Count -ne 4 -or @($services | Where-Object {$_.StartMode -ne 'Auto'}).Count -ne 0) {
        throw 'All four existing project runner services must be configured for automatic startup first.'
    }
    $power = $null
    if ($KeepAwakeOnAc) { $power = Get-PowerSnapshot }
    $existed = Test-Path -LiteralPath $script:InstallRoot
    if ($existed) {
        Assert-NoReparsePoint $script:InstallRoot
        $acl = Get-Acl -LiteralPath $script:InstallRoot
        $ownerSid = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        if ($ownerSid -notin @('S-1-5-18','S-1-5-32-544') -or -not (Test-Path -LiteralPath (Join-Path $script:InstallRoot 'installed.json'))) {
            throw 'The maintenance directory is not a recognized administrator-owned installation.'
        }
        foreach ($file in Get-ChildItem -LiteralPath $script:InstallRoot -Force) { Assert-NoReparsePoint $file.FullName }
    } else {
        Assert-NoReparsePoint (Split-Path $script:InstallRoot -Parent)
        [void][IO.Directory]::CreateDirectory($script:InstallRoot)
    }
    $security = New-Object Security.AccessControl.DirectorySecurity
    $security.SetAccessRuleProtection($true,$false)
    $security.SetOwner([Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))
    foreach ($sid in @('S-1-5-18','S-1-5-32-544')) {
        $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    foreach ($sid in @('S-1-5-32-545','S-1-5-20')) {
        $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
    }
    Set-Acl -LiteralPath $script:InstallRoot -AclObject $security
    $sourceBytes = [IO.File]::ReadAllBytes($PSCommandPath)
    [IO.File]::WriteAllBytes($script:InstalledScript,$sourceBytes)
    $hash = (Get-FileHash -LiteralPath $script:InstalledScript -Algorithm SHA256).Hash.ToLowerInvariant()
    $powerFile = Join-Path $script:InstallRoot 'original-ac-power.json'
    if ($null -ne $power -and -not (Test-Path -LiteralPath $powerFile)) {
        [IO.File]::WriteAllText($powerFile,($power | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    }
    if ($null -ne $power) {
        try { Set-AcPowerValues $power $false } catch { Set-AcPowerValues $power $true; throw }
    }
    $metadata = @{installed_at_utc=[DateTime]::UtcNow.ToString('o');sha256=$hash;task=$script:TaskName;threshold_seconds=43200;poll_seconds=60;forced_restart=$false}
    [IO.File]::WriteAllText((Join-Path $script:InstallRoot 'installed.json'),($metadata | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
    try {
        $definition = New-RestartTaskDefinition
        Register-ScheduledTask -TaskName $script:TaskName -TaskPath '\' -InputObject $definition -Force | Out-Null
        $pauseFile = Join-Path $script:InstallRoot 'pause'
        if (Test-Path -LiteralPath $pauseFile) { Remove-Item -LiteralPath $pauseFile }
        $actual = Get-ExistingTask
        if ($null -eq $actual -or $actual.State -eq 'Disabled') { throw 'Task registration could not be verified.' }
        if ($actual.Actions[0].Execute -ne $script:PowerShellExe -or $actual.Principal.UserId -notin @('SYSTEM','S-1-5-18')) { throw 'Unexpected registered task identity.' }
        Write-Output 'INSTALLED: AnalystAI-RestartAfter12Hours. No immediate restart was requested.'
        Write-Output ('Status file: '+(Join-Path $script:InstallRoot 'status.json'))
    } catch {
        $existing = Get-ExistingTask
        Assert-OwnedTask $existing
        if ($null -ne $existing) { Disable-ScheduledTask -TaskName $script:TaskName -TaskPath '\' | Out-Null }
        if ($null -ne $power) { Set-AcPowerValues $power $true }
        throw
    }
}

function Invoke-Maintenance {
    Assert-Administrator
    Assert-LocalHost
    if ($PSCommandPath -ne $script:InstalledScript) { throw 'Run mode is allowed only from the protected installation.' }
    Assert-NoReparsePoint $script:InstalledScript
    $seconds = Get-AwakeSeconds
    $statePath = Join-Path $script:InstallRoot 'last-restart-attempt.json'
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
    $lastAttempt = -3600.0
    if (Test-Path -LiteralPath $statePath) {
        $old = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($old.boot -eq $boot) { $lastAttempt = [double]$old.awake_seconds }
    }
    $paused = Test-Path -LiteralPath (Join-Path $script:InstallRoot 'pause')
    $blockers = @(Get-WorkBlockers)
    $decision = Get-RestartDecision $seconds ($blockers.Count -gt 0) $paused $lastAttempt
    if ($decision -ne 'eligible') { Write-Status $decision $seconds ($blockers -join ','); return }
    Assert-NoReparsePoint $script:LeasePath
    $lease = [IO.File]::Open($script:LeasePath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::ReadWrite)
    $locked = $false
    try {
        try { $lease.Lock(0,1); $locked = $true } catch [IO.IOException] { Write-Status 'build_lease_busy' $seconds; return }
        $blockers = @(Get-WorkBlockers)
        if ($blockers.Count -gt 0) { Write-Status 'busy' $seconds ($blockers -join ','); return }
        # Give signed-in users a warning without scheduling shutdown /t > 0,
        # because Windows implicitly enables forced closure for such a timeout.
        $msg = Join-Path $env:SystemRoot 'System32\msg.exe'
        if (Test-Path -LiteralPath $msg) {
            try { & $msg '*' /TIME:60 'Analyst AI: planned restart in about one minute. Save your work. Active project jobs postpone it.' 2>$null | Out-Null } catch { }
        }
        Write-Status 'warning' $seconds
        for ($i=0;$i -lt 12;$i++) {
            Start-Sleep -Seconds 5
            $blockers = @(Get-WorkBlockers)
            if ($blockers.Count -gt 0 -or (Test-Path -LiteralPath (Join-Path $script:InstallRoot 'pause'))) {
                Write-Status 'postponed' (Get-AwakeSeconds) ($blockers -join ','); return
            }
        }
        $attempt = @{boot=$boot;awake_seconds=(Get-AwakeSeconds)}
        [IO.File]::WriteAllText($statePath,($attempt | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
        Write-Status 'restart_requested' $attempt.awake_seconds
        & $script:ShutdownExe /r /t 0 /d p:4:1 /c 'Analyst AI scheduled restart after 12 active hours'
        if ($LASTEXITCODE -ne 0) { throw ('Windows rejected the restart request: '+$LASTEXITCODE) }
    } finally {
        if ($locked) { $lease.Unlock(0,1) }
        $lease.Dispose()
    }
}

function Test-Maintenance {
    # These tests never install a task, stop a service, or request a restart.
    $cases = @(
        @(0,$false,$false,-3600,'not_due'),
        @(43199,$false,$false,-3600,'not_due'),
        @(43200,$false,$false,-3600,'eligible'),
        @(90000,$true,$false,-3600,'busy'),
        @(90000,$false,$true,-3600,'paused'),
        @(45000,$false,$false,44000,'retry_cooldown'),
        @(48000,$false,$false,44000,'eligible')
    )
    foreach ($case in $cases) {
        $actual = Get-RestartDecision $case[0] $case[1] $case[2] $case[3]
        if ($actual -ne $case[4]) { throw ('Decision regression: '+$case[4]+' / '+$actual) }
    }
    foreach ($invalid in @(-1,[double]::NaN,[double]::PositiveInfinity)) {
        $rejected = $false
        try { [void](Get-RestartDecision $invalid $false $false) } catch { $rejected = $true }
        if (-not $rejected) { throw 'Invalid clock was accepted.' }
    }
    $first = Get-AwakeSeconds
    Start-Sleep -Milliseconds 50
    if ((Get-AwakeSeconds) -lt $first) { throw 'Native awake clock regressed.' }
    $definition = New-RestartTaskDefinition
    if ($definition.Principal.UserId -notin @('SYSTEM','S-1-5-18')) { throw 'Task must use SYSTEM.' }
    if ($definition.Actions[0].Arguments -notmatch '-Mode Run$') { throw 'Incorrect task action.' }
    if ($definition.Triggers.Count -ne 2) { throw 'Missing boot or periodic trigger.' }
    $power = Get-PowerSnapshot
    if ($power.settings.Count -ne 3) { throw 'Incomplete power snapshot.' }
    Assert-NoReparsePoint $script:LeasePath
    $f = [IO.File]::Open($script:LeasePath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::ReadWrite)
    $lockResult = 'busy'
    try {
        try { $f.Lock(0,1);$lockResult='acquired';$f.Unlock(0,1) } catch [IO.IOException] {}
    } finally { $f.Dispose() }
    return @{status='passed';decision_cases=10;native_clock=$true;task_definition=$true;power_snapshot=$true;lease=$lockResult;installed=$false;restarted=$false}
}

switch ($Mode) {
    'Install' { Install-Maintenance }
    'Run' { Invoke-Maintenance }
    'Test' { Test-Maintenance | ConvertTo-Json -Depth 5 }
    'Disable' {
        Assert-Administrator
        Assert-OwnedTask (Get-ExistingTask)
        [IO.File]::WriteAllText((Join-Path $script:InstallRoot 'pause'),'paused by administrator')
        Disable-ScheduledTask -TaskName $script:TaskName -TaskPath '\' | Out-Null
        Stop-ScheduledTask -TaskName $script:TaskName -TaskPath '\' -ErrorAction SilentlyContinue
        Write-Output 'DISABLED: automatic restarts. Other settings were not changed.'
    }
    'Status' {
        $task = Get-ExistingTask
        $state = if ($null -eq $task) { 'not_installed' } else { [string]$task.State }
        Write-Status $state (Get-AwakeSeconds)
    }
}
