# Exercise the restart decision on the real Lenovo without impersonating or modifying its protected account.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Installer)
$ErrorActionPreference='Stop'
trap {
    $kind=($_.FullyQualifiedErrorId -split ',')[0] -replace '[^A-Za-z0-9_-]',''
    if ($kind.Length -gt 80) { $kind=$kind.Substring(0,80) }
    [Console]::Error.WriteLine('HOME_TEST_DIAG='+$kind+'_'+$_.InvocationInfo.ScriptLineNumber)
    exit 1
}
. $Installer -VerifyOnly | Out-Null
$id=(Get-LocalUser -Name 'AnalystAIHost').SID.Value
$secret=ConvertTo-SecureString ('Fp4!'+[Guid]::NewGuid().ToString('N')) -AsPlainText -Force
$credential=[PSCredential]::new($localUser,$secret)
try {
    # Exercise the very same process transport as the approved logon, without authenticating as another user.
    $probe="if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { exit 21 }; [Console]::WriteLine('ANALYST_PROFILE_OK'); exit 0"
    $cross=Profile-ChildInfo $probe $credential
    Need ($cross.LoadUserProfile -and -not $cross.UseShellExecute -and $cross.Domain -eq $machine -and
          $cross.UserName -eq $name -and $cross.Password.Length -gt 0) 'Native logon settings are incomplete'
    Run-ProfileChild (Profile-ChildInfo $probe $null)
    $negative=$false
    try { Run-ProfileChild (Profile-ChildInfo 'exit 42' $null) }
    catch { if ($_.Exception.Message -notmatch 'process exit 42$') { throw }; $negative=$true }
    Need $negative 'An unsuccessful profile child was accepted'

    $astErrors=$null; $tokens=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$tokens,[ref]$astErrors)
    Need ($astErrors.Count -eq 0) 'Profile recovery script parse failed'
    $ops=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true))
    $registration=@($ops | Where-Object {$_.GetCommandName() -eq 'Register-ScheduledTask'})
    $activation=@($ops | Where-Object {$_.GetCommandName() -eq 'Start-HomeSupervisor'})
    Need ($registration.Count -eq 1 -and $activation.Count -eq 1 -and $registration[0].Extent.StartOffset -lt $activation[0].Extent.StartOffset) 'Registration must precede profile work'
    Need (-not [IO.File]::ReadAllText($Installer).Contains('userenv.dll')) 'Old explicit profile prerequisite is present'

    # These doubles model only OS operations that require local elevation. The coordinator itself is the shipped function.
    $scenario=@{events=[Collections.Generic.List[string]]::new();answers=[Collections.Generic.Queue[string]]::new();profile=$false;reject_first=$false}
    function Log-Enrollment([string]$step,[string]$code='') {}
    function Start-ScheduledTask { $scenario.events.Add('start'); if($scenario.reject_first) { $scenario.reject_first=$false; throw 'test_start_error' } }
    function Wait-WorkerPhase([DateTime]$since,[int]$seconds) { $scenario.events.Add('wait'); return $scenario.answers.Dequeue() }
    function Test-Path { param($LiteralPath) return $scenario.profile }
    function Initialize-ByLogon([PSCredential]$check,[string]$sid) {
        if ($sid -ne $id -or $check.UserName -ne $localUser) { throw 'Wrong profile target' }
        $scenario.events.Add('profile');$scenario.profile=$true
    }
    function Get-ScheduledTask { return [pscustomobject]@{State='Ready'} }
    function Get-ScheduledTaskInfo { return [pscustomobject]@{LastTaskResult=267011} }

    $scenario.answers.Enqueue('import')
    Start-HomeSupervisor $credential $id | Out-Null
    Need (($scenario.events -join ',') -eq 'start,wait') 'Normal boot performed an unnecessary profile logon'

    $scenario.events.Clear();$scenario.answers.Enqueue('');$scenario.answers.Enqueue('configure')
    Start-HomeSupervisor $credential $id | Out-Null
    Need (($scenario.events -join ',') -eq 'start,wait,profile,start,wait') 'Missing-profile retry order failed'

    $scenario.events.Clear();$scenario.profile=$false;$scenario.reject_first=$true;$scenario.answers.Enqueue('import')
    Start-HomeSupervisor $credential $id | Out-Null
    Need (($scenario.events -join ',') -eq 'start,profile,start,wait') 'Native start failure did not recover via profile'

    $scenario.events.Clear();$scenario.profile=$true;$scenario.answers.Enqueue('failed-application')
    $out=Start-HomeSupervisor $credential $id
    Need (($scenario.events -join ',') -eq 'start,wait' -and ($out -join ' ') -match 'failed-application') 'Guest failure was reported as healthy'
} finally { $secret.Dispose() }
[ordered]@{dedicated_identity_present=$true;task_first=$true;old_profile_call_removed=$true;profile_parameter_set='verified';observer_process_started=$true;
    coordinated_cases=4;target_account_logon_performed=$false} | ConvertTo-Json -Compress
