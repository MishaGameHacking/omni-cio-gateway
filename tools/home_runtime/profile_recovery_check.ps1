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
    # Windows PowerShell 5.1 Start-Process has no WhatIf switch. Validate the credential parameter set
    # and really start a harmless process as the observer. The cross-account logon is exercised only by Windows enrollment.
    $needed=@('FilePath','ArgumentList','Credential','LoadUserProfile','WorkingDirectory','WindowStyle','PassThru')
    $sets=@((Get-Command Microsoft.PowerShell.Management\Start-Process).ParameterSets | Where-Object {
        $names=@($_.Parameters.Name)
        @($needed | Where-Object {$_ -notin $names}).Count -eq 0
    })
    Need ($sets.Count -ge 1) 'Native profile launch parameter set is unavailable'
    $probe="if ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { exit 21 }; exit 0"
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe))
    $child=Microsoft.PowerShell.Management\Start-Process -FilePath $winPS -ArgumentList ('-NoProfile -NonInteractive -EncodedCommand '+$encoded) -LoadUserProfile -WorkingDirectory $env:SystemRoot -WindowStyle Hidden -PassThru
    try { Need ($child.WaitForExit(20000) -and $child.ExitCode -eq 0) 'Observer profile launch failed' }
    finally { $child.Dispose() }

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
