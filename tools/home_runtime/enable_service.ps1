[CmdletBinding()]
param([string]$HostSource,[switch]$VerifyOnly,[string]$HostedFixtureDigest)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$serviceName='AnalystAIHomeHost'
$sourceDigest='fc2e2f5dae51c82d7295c733bbd15884be089216092a30e9fb45fe317d655c7e'
$workerDigest='e95a456192a4c582f7d9ca8afea16256d05299c69dc1594e07ab21c188f61dc4'
$package='d958608239005290f808'
function Check([bool]$condition,[string]$message) { if (-not $condition) { throw $message } }
function BytesHash([byte[]]$data) {
    $alg=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($alg.ComputeHash($data)).Replace('-','').ToLowerInvariant() } finally { $alg.Dispose() }
}
function NoLinks([string]$path) {
    $node=Get-Item -Force -LiteralPath $path
    while ($null -ne $node) {
        Check (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'Unexpected filesystem link'
        $node=if ($node -is [IO.FileInfo]) { $node.Directory } else { $node.Parent }
    }
}
function MakeHost([string]$root,[string]$code,[string]$workerHash) {
    Check ((BytesHash ([Text.Encoding]::UTF8.GetBytes($code))) -eq $sourceDigest -and $workerHash -match '^[a-f0-9]{64}$') 'Unverified service source'
    NoLinks $root
    $folder=Join-Path $root ('scm-'+$sourceDigest.Substring(0,16))
    $exe=Join-Path $folder 'AnalystAIHomeHost.exe'
    if (-not [IO.Directory]::Exists($folder)) {
        $tmp=Join-Path $root ('scm-build-'+[guid]::NewGuid().ToString('N'))
        $null=[IO.Directory]::CreateDirectory($tmp)
        try {
            $build=Join-Path $tmp 'AnalystAIHomeHost.exe'
            $compiler=[Microsoft.CSharp.CSharpCodeProvider]::new()
            $settings=[CodeDom.Compiler.CompilerParameters]::new()
            $settings.GenerateExecutable=$true; $settings.OutputAssembly=$build
            $settings.CompilerOptions='/nologo /platform:x64 /optimize+'
            $null=$settings.ReferencedAssemblies.Add('System.dll')
            $null=$settings.ReferencedAssemblies.Add('System.ServiceProcess.dll')
            $settings.TempFiles=[CodeDom.Compiler.TempFileCollection]::new($tmp,$false)
            try {
                $result=$compiler.CompileAssemblyFromSource($settings,$code.Replace('__WORKER_DIGEST__',$workerHash))
                if ($result.Errors.HasErrors) {
                    $err=@($result.Errors | Where-Object { -not $_.IsWarning })[0]
                    throw ('Compiler '+$err.ErrorNumber+' at line '+$err.Line)
                }
            } finally { $compiler.Dispose();$settings.TempFiles.Delete() }
            $manifest=[ordered]@{source=$sourceDigest;worker=$workerHash;binary=(Get-FileHash -LiteralPath $build -Algorithm SHA256).Hash}
            [IO.File]::WriteAllText((Join-Path $tmp 'manifest.json'),($manifest|ConvertTo-Json -Compress))
            [IO.Directory]::Move($tmp,$folder)
        } finally { if ([IO.Directory]::Exists($tmp)) { [IO.Directory]::Delete($tmp,$true) } }
    }
    NoLinks $exe
    $manifestFile=Join-Path $folder 'manifest.json'
    NoLinks $manifestFile
    $saved=Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
    Check ($saved.source -eq $sourceDigest -and $saved.worker -eq $workerHash -and
           $saved.binary -eq (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash) 'Unverified installed service binary'
    return $exe
}
function SetServiceAccess {
    $sc=Join-Path $env:SystemRoot 'System32\sc.exe'
    $previous=((& $sc sdshow $serviceName) -join '').Trim()
    Check ($LASTEXITCODE -eq 0 -and $previous.StartsWith('D:')) 'Cannot read service permissions'
    $sd=[Security.AccessControl.CommonSecurityDescriptor]::new($false,$false,$previous)
    $network=[Security.Principal.SecurityIdentifier]::new('S-1-5-20')
    # Query configuration/status and start only. The service account has no project administration privileges.
    $rights=0x20015
    $allowed=@($sd.DiscretionaryAcl | Where-Object {
        $_ -is [Security.AccessControl.CommonAce] -and $_.SecurityIdentifier -eq $network -and
        $_.AceQualifier -eq 'AccessAllowed' -and ($_.AccessMask -band $rights) -eq $rights })
    if (-not $allowed.Count) {
        $sd.DiscretionaryAcl.AddAccess('Allow',$network,$rights,'None','None')
        $updated=$sd.GetSddlForm([Security.AccessControl.AccessControlSections]::All)
        $null=& $sc sdset $serviceName $updated
        Check ($LASTEXITCODE -eq 0) 'Cannot grant the service observer query/start rights'
    }
}
function ConfigureService([string]$exe,[string]$account,[PSCredential]$credentials) {
    $entry=Get-CimInstance Win32_Service -Filter "Name='AnalystAIHomeHost'"
    $quoted='"'+$exe+'"'
    if ($entry) {
        Check ($entry.PathName -ceq $quoted -and $entry.StartName -ieq $account) 'A different service owns this name'
        if ($entry.State -ne 'Running') {
            $result=Invoke-CimMethod -InputObject $entry -MethodName Change -Arguments @{
                StartName=$account;StartPassword=$credentials.GetNetworkCredential().Password}
            Check ($result.ReturnValue -eq 0) ('Cannot refresh service credentials, code '+$result.ReturnValue)
        }
    } else {
        $null=New-Service -Name $serviceName -DisplayName 'Analyst AI home server' -BinaryPathName $quoted -Credential $credentials -StartupType Manual
    }
    SetServiceAccess
    $sc=Join-Path $env:SystemRoot 'System32\sc.exe'
    $null=& $sc failure $serviceName 'reset=' 86400 'actions=' 'restart/60000/restart/120000/restart/300000'
    Check ($LASTEXITCODE -eq 0) 'Cannot configure service recovery'
}
function WriteServiceReceipt([string]$stage,[string]$code='') {
    $directory=Join-Path $root 'install-status'
    NoLinks $directory
    $tmp=Join-Path $directory ('svc-'+[guid]::NewGuid().ToString('N'))
    $dest=Join-Path $directory 'service.json'
    $record=[ordered]@{package=$package;mode='scm';stage=$stage;code=$code;utc=[DateTime]::UtcNow.ToString('o')}
    try {
        [IO.File]::WriteAllText($tmp,($record|ConvertTo-Json -Compress))
        if ([IO.File]::Exists($dest)) { NoLinks $dest;[IO.File]::Replace($tmp,$dest,[NullString]::Value) } else { [IO.File]::Move($tmp,$dest) }
    } finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
}
function ExistingTask([Security.Principal.SecurityIdentifier]$sid) {
    $t=Get-ScheduledTask -TaskName 'AnalystAI-HomeRuntime' -TaskPath '\'
    $actions=@($t.Actions)
    $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $argsText='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+(Join-Path $root 'Run-AnalystAIHome.ps1')+'"'
    Check ($actions.Count -eq 1 -and $actions[0].Execute -eq $ps -and $actions[0].Arguments -ceq $argsText -and
        $t.Principal.UserId -in @($sid.Value,$account,$userName) -and [string]$t.Principal.RunLevel -eq 'Limited' -and
        [string]$t.Principal.LogonType -eq 'Password' -and @($t.Triggers).Count -eq 1 -and
        $t.Triggers[0].CimClass.CimClassName -eq 'MSFT_TaskBootTrigger') 'Unrecognized previous boot task'
    return $t
}
function ServiceError($reason) {
    $e=$reason.Exception.GetBaseException()
    if ($e -is [ComponentModel.Win32Exception]) { return ('win32-'+$e.NativeErrorCode) }
    return ('hresult-{0:X8}' -f ([long]$e.HResult -band 4294967295L))
}
Check ([Environment]::Is64BitProcess) '64-bit Windows required'
if ($HostedFixtureDigest) {
    Check ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -and $env:GITHUB_ACTIONS -eq 'true' -and
           $env:RUNNER_ENVIRONMENT -eq 'github-hosted' -and $env:RUNNER_OS -eq 'Windows' -and
           $HostedFixtureDigest -match '^[a-f0-9]{64}$') 'Disposable Windows test machine required'
    $workerDigest=$HostedFixtureDigest
} else { Check ($env:COMPUTERNAME -eq 'LAPTOP-NPSGA016') 'Designated Windows host required' }
Check ((BytesHash ([Text.Encoding]::UTF8.GetBytes($HostSource))) -eq $sourceDigest) 'Unverified source'
if ($VerifyOnly) {
    $temp=Join-Path ([IO.Path]::GetTempPath()) ('analyst-scm-check-'+[guid]::NewGuid().ToString('N'))
    $null=[IO.Directory]::CreateDirectory($temp)
    try {
        $test=MakeHost $temp $HostSource $workerDigest
        Check ((MakeHost $temp $HostSource $workerDigest) -ceq $test) 'Repeat compilation check failed'
        Write-Output 'HOME_SCM_SOURCE_VERIFIED'
    } finally { [IO.Directory]::Delete($temp,$true) }
    return
}
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
Check ([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) 'Local administrator confirmation required'
$root=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$enroll=Join-Path $root 'enrollment.json'
NoLinks $enroll
$receipt=Get-Content -Raw -LiteralPath $enroll | ConvertFrom-Json
$userName='AnalystAIHost'
$account=$env:COMPUTERNAME+'\'+$userName
$u=Get-LocalUser -Name $userName
Check ($receipt.marker -eq 'analyst-home-runtime-v1' -and $receipt.package -eq $package -and $receipt.machine -eq $env:COMPUTERNAME -and
       $u.Enabled -and $u.SID.Value -eq $receipt.sid -and $u.Description -eq 'Analyst AI home runtime') 'Previous enrollment not verified'
Check ($u.SID.Value -notin @((Get-LocalGroupMember -SID 'S-1-5-32-544').SID.Value)) 'Service identity is an administrator'
$worker=Join-Path $root 'Run-AnalystAIHome.ps1'
NoLinks $worker
Check ((Get-FileHash -LiteralPath $worker -Algorithm SHA256).Hash -eq $workerDigest) 'Protected worker changed'
$lock=Join-Path $root 'enrollment.lock'
NoLinks $lock
$lease=[IO.File]::Open($lock,'Open','ReadWrite','None')
$stage='identity'
try {
    $original=ExistingTask $u.SID
    $stage='compile';WriteServiceReceipt $stage
    $exe=MakeHost $root $HostSource $workerDigest
    $entry=Get-CimInstance Win32_Service -Filter "Name='AnalystAIHomeHost'"
    if ($entry) { Check ($entry.PathName -ceq ('"'+$exe+'"') -and $entry.StartName -ieq $account) 'Different service with this name exists' }
    $workerStatus=Join-Path $root 'report\status.json'
    if (-not $entry -and $original.State -eq 'Running' -and [IO.File]::Exists($workerStatus)) {
        $prior=Get-Content -LiteralPath $workerStatus -Raw | ConvertFrom-Json
        if ($prior.package -eq $package -and $prior.phase -in @('import','configure','application','local-model','login-check','supervising')) {
            WriteServiceReceipt 'task-active'
            Write-Output 'The existing limited worker is active. Its current installation will continue.'
            return
        }
    }
    if (-not $entry -or $entry.State -ne 'Running') {
        $stage='logon-right';WriteServiceReceipt $stage
        $null=[Reflection.Assembly]::LoadFrom($exe)
        [AnalystHome.LogonRight]::GrantServiceLogon($u.SID)
        $random=New-Object byte[] 48;$rng=[Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($random) } finally { $rng.Dispose() }
        $plain='Aa1!'+[Convert]::ToBase64String($random);[Array]::Clear($random,0,$random.Length)
        $secret=ConvertTo-SecureString $plain -AsPlainText -Force
        try {
            $stage='account';WriteServiceReceipt $stage
            Set-LocalUser -SID $u.SID -Password $secret
            $null=Set-ScheduledTask -TaskName 'AnalystAI-HomeRuntime' -TaskPath '\' -User $account -Password $plain
            $stage='register';WriteServiceReceipt $stage
            ConfigureService $exe $account ([PSCredential]::new($account,$secret))
        } finally { $plain=$null;$secret.Dispose() }
    } else { SetServiceAccess }
    $stage='switch';WriteServiceReceipt $stage
    $original=ExistingTask $u.SID
    $null=Disable-ScheduledTask -InputObject $original
    if ($original.State -in @('Running','Queued')) {
        Stop-ScheduledTask -TaskPath '\' -TaskName 'AnalystAI-HomeRuntime'
    }
    $svc=New-Object -ComObject 'Schedule.Service';$svc.Connect()
    $priorTask=$svc.GetFolder('\').GetTask('AnalystAI-HomeRuntime')
    for ($i=0;$i -lt 20 -and $priorTask.GetInstances(0).Count -gt 0;$i++) { Start-Sleep -Seconds 1 }
    Check (-not $priorTask.Enabled -and $priorTask.GetInstances(0).Count -eq 0) 'Previous worker is still active'
    $stage='start';WriteServiceReceipt $stage
    Set-Service -Name $serviceName -StartupType Automatic
    $service=Get-Service -Name $serviceName
    if ($service.Status -ne 'Running') { Start-Service -Name $serviceName }
    $service.WaitForStatus([ServiceProcess.ServiceControllerStatus]::Running,[TimeSpan]::FromSeconds(45))
    $current=Get-CimInstance Win32_Service -Filter "Name='AnalystAIHomeHost'"
    Check ($current.State -eq 'Running' -and $current.StartMode -eq 'Auto' -and $current.StartName -ieq $account -and $current.ProcessId -gt 0) 'SCM did not confirm the limited automatic service'
    WriteServiceReceipt 'running'
    Write-Output 'Windows started the Analyst AI service. The Ubuntu worker is now being checked separately.'
} catch {
    $reason=$_
    try { WriteServiceReceipt ('failed-'+$stage) (ServiceError $reason) } catch {}
    throw $reason
} finally { $lease.Dispose() }
