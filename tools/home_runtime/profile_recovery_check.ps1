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
    $folder=Join-Path ([IO.Path]::GetTempPath()) ('Analyst profile proof '+[Guid]::NewGuid().ToString('N'))
    $null=[IO.Directory]::CreateDirectory($folder)
    try {
        $file=Stage-ProfileProof $folder
        Need ((Stage-ProfileProof $folder) -eq $file) 'Repeat proof file staging failed'
        $cross=Profile-ChildInfo $file $id $credential
        $livePath=Join-Path $root 'Check-AnalystProfile-v1.ps1'
        $actualCommand=Profile-ChildInfo $livePath $id $credential
        $actualChars=$actualCommand.FileName.Length+$actualCommand.Arguments.Length+4
        Need ($cross.LoadUserProfile -and -not $cross.UseShellExecute -and $cross.Domain -eq $machine -and
              $cross.UserName -eq $name -and $cross.Password.Length -gt 0 -and $actualChars -le 1024 -and
              $actualCommand.Arguments -notmatch 'EncodedCommand') 'Service logon command does not satisfy Windows limits'
        Run-ProfileChild (Profile-ChildInfo $file 'S-1-5-20' $null)
        $negative=$false
        try { Run-ProfileChild (Profile-ChildInfo $file $id $null) }
        catch { if ($_.Exception.Message -notmatch 'process exit 41$') { throw }; $negative=$true }
        Need $negative 'The wrong user identity was accepted'
        $tooLong=$false
        $longFile=Join-Path ([IO.Path]::GetPathRoot($folder)) (('x'*1050)+'\Check-AnalystProfile-v1.ps1')
        try { $null=Profile-ChildInfo $longFile $id $credential } catch {
            if ($_.Exception.Message -notmatch '1024-character limit') { throw }
            $tooLong=$true
        }
        Need $tooLong 'A command above the Win32 logon limit was accepted'
        Import-ProfileApi
        Need ([IntPtr]::Size -eq 8 -and [AnalystHome.ProfileLoader]::StructureSize -eq 56) 'Native profile ABI mismatch'
    } finally { [IO.Directory]::Delete($folder,$true) }
    $original='D:P(A;;FA;;;SY)(A;;FA;;;BA)'
    $dacl=Observer-TaskDacl $original
    Need ((Observer-TaskDacl $dacl) -ceq $dacl) 'Task observer access was not idempotent'
    $parsed=[Security.AccessControl.RawSecurityDescriptor]::new($dacl)
    $added=@($parsed.DiscretionaryAcl | Where-Object {$_.SecurityIdentifier.Value -eq 'S-1-5-20'})
    Need ($parsed.DiscretionaryAcl.Count -eq 3 -and $added.Count -eq 1 -and $added[0].AccessMask -eq 0x1200A9) 'Task permissions exceed read and execute'

    $astErrors=$null; $tokens=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$tokens,[ref]$astErrors)
    Need ($astErrors.Count -eq 0) 'Profile recovery script parse failed'
    $ops=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.CommandAst]},$true))
    $registration=@($ops | Where-Object {$_.GetCommandName() -eq 'Register-ScheduledTask'})
    $activation=@($ops | Where-Object {$_.GetCommandName() -eq 'Start-HomeSupervisor'})
    Need ($registration.Count -eq 1 -and $activation.Count -eq 1 -and $registration[0].Extent.StartOffset -lt $activation[0].Extent.StartOffset) 'Registration must precede profile work'
    Need ([IO.File]::ReadAllText($Installer) -notmatch '\bCreateProfileW?\s*\(') 'Old explicit profile prerequisite is present'

    # These doubles model only OS operations that require local elevation. The coordinator itself is the shipped function.
    $scenario=@{events=[Collections.Generic.List[string]]::new();answers=[Collections.Generic.Queue[string]]::new();profile=$false;reject_first=$false}
    function Log-Enrollment([string]$step,[string]$code='') {}
    function Start-ScheduledTask { $scenario.events.Add('start'); if($scenario.reject_first) { $scenario.reject_first=$false; throw 'test_start_error' } }
    function Read-WorkerPhase([DateTime]$since) { return '' }
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
    coordinated_cases=4;actual_cross_command_chars=$actualChars;windows_max=1024;oversize_blocked=$true;
    wrong_identity_rejected=$true;native_profile_abi=56;observer_task_rights='read_execute';target_account_logon_performed=$false} | ConvertTo-Json -Compress
