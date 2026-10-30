param([Parameter(Mandatory)][string]$Revision,[Parameter(Mandatory)][string]$StartFile)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or $Revision -notmatch '^[0-9a-f]{40}$') { throw 'Invalid workstation or revision' }
$caller=[Security.Principal.WindowsIdentity]::GetCurrent().User
if ($caller.Value -ne 'S-1-5-20') { throw 'Wrong staging user' }
$base=[Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
$root=Join-Path $base 'AnalystAI-Codex'
$dest=Join-Path $root 'omni-cio-gateway'
$receipt=Join-Path $root 'workspace-v1.json'
$remote='https://github.com/MishaGameHacking/omni-cio-gateway.git'
$branch='codex/timeweb-owner-prepare-2026-10-23'
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$admins=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$step='owner'
trap {
    $errorType=$_.Exception.GetBaseException().GetType().Name
    $label=if ($_.Exception.Message -match '^stage_[a-z_0-9]{1,70}$') { $_.Exception.Message } else { $errorType }
    Write-Output ('HOME_CODEX_PROJECT_ERROR='+(@{step=$step;reason=$label;line=$_.InvocationInfo.ScriptLineNumber}|ConvertTo-Json -Compress))
    exit 1
}
function Must([bool]$ok,[string]$code) { if (-not $ok) { throw ('stage_'+$code) } }
function Plain([string]$path) {
    $node=Get-Item -LiteralPath $path -Force -ErrorAction Stop
    while ($null -ne $node) {
        Must (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'filesystem_link'
        $node=if ($node -is [IO.FileInfo]) { $node.Directory } else { $node.Parent }
    }
}
$interactive=(Get-CimInstance Win32_ComputerSystem).UserName
Must ([bool]$interactive) 'no_interactive_owner'
$owner=([Security.Principal.NTAccount]::new($interactive)).Translate([Security.Principal.SecurityIdentifier])
$profile=Get-CimInstance Win32_UserProfile -Filter ("SID='"+$owner.Value+"'")
Must ($owner.Value -match '^S-1-5-21-(?:[0-9]+-){3}[0-9]+$' -and $profile -and -not $profile.Special) 'no_personal_profile'
function DirectoryRules([string]$ownerRight) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetOwner($caller);$acl.SetAccessRuleProtection($true,$false)
    foreach($sid in @($system,$admins,$caller)) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($owner,$ownerRight,'ContainerInherit,ObjectInherit','None','Allow'))
    return $acl
}
function Access([string]$path,[string]$right) {
    Plain $path
    $acl=Get-Acl -LiteralPath $path
    Must ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -eq $caller.Value) 'foreign_owner'
    $ownerMask=[int]([Security.AccessControl.FileSystemRights]$right -bor [Security.AccessControl.FileSystemRights]::Synchronize)
    $matched=$false
    foreach ($a in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($a.IdentityReference.Value -in @($system.Value,$admins.Value,$caller.Value)) { continue }
        Must ($a.IdentityReference.Value -eq $owner.Value -and $a.AccessControlType -eq 'Allow' -and
              ([int]$a.FileSystemRights -band (-bnot $ownerMask)) -eq 0) 'unexpected_writer'
        if (([int]$a.FileSystemRights -band $ownerMask) -eq $ownerMask) { $matched=$true }
    }
    Must $matched 'owner_right_missing'
}
$step='workspace'
Plain $base
if (-not [IO.Directory]::Exists($root)) { $null=[IO.Directory]::CreateDirectory($root,(DirectoryRules 'ReadAndExecute')) }
Access $root 'ReadAndExecute'
$mutex=Join-Path $root 'prepare.lock'
if ([IO.File]::Exists($mutex)) { Plain $mutex }
$lock=[IO.File]::Open($mutex,'OpenOrCreate','ReadWrite','None')
try {
    $launcher=Join-Path $root 'Open.cmd'
    $launchBytes=[IO.File]::ReadAllBytes($StartFile)
    if (-not [IO.File]::Exists($launcher)) {
        $lt=Join-Path $root ('open-'+[Guid]::NewGuid().ToString('N'))
        try { [IO.File]::WriteAllBytes($lt,$launchBytes);[IO.File]::Move($lt,$launcher) }
        finally { if ([IO.File]::Exists($lt)) { [IO.File]::Delete($lt) } }
    }
    Access $launcher 'ReadAndExecute'
    Must ((Get-FileHash $launcher).Hash -eq (Get-FileHash $StartFile).Hash) 'launcher_conflict'
    if ([IO.File]::Exists($receipt)) {
        Access $receipt 'ReadAndExecute'
        $data=Get-Content $receipt -Raw|ConvertFrom-Json
        Must ($data.marker -eq 'analyst-user-codex-workspace-v1' -and $data.owner -eq $owner.Value -and
            $data.revision -match '^[0-9a-f]{40}$' -and [IO.Directory]::Exists($dest)) 'unknown_workspace'
        # The owner can work here now. Never run Git from that mutable tree as the build account.
        if ($data.phase -eq 'prepared') {
            Plain $dest
            Set-Acl -LiteralPath $dest -AclObject (DirectoryRules 'Modify')
        }
        Access $dest 'Modify'
        Write-Output ('HOME_CODEX_PROJECT='+(@{status='previously_delivered';initial_revision=$data.revision;files=$data.files;owner_modify=$true;personal_login_used=$false}|ConvertTo-Json -Compress))
        return
    }
    Must (-not [IO.Directory]::Exists($dest) -and -not [IO.File]::Exists($dest)) 'destination_occupied'
    Must ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($base)).AvailableFreeSpace -gt 8GB) 'insufficient_reserve'
    $git=(Get-Command git.exe -CommandType Application | Select-Object -First 1).Source
    $env:GIT_CONFIG_GLOBAL='NUL';$env:GIT_CONFIG_NOSYSTEM='1';$env:GIT_TERMINAL_PROMPT='0';$env:GCM_INTERACTIVE='never'
    $env:GIT_LFS_SKIP_SMUDGE='1'
    function RunGit([string[]]$arguments) {
        $previous=$ErrorActionPreference
        try {
            $ErrorActionPreference='Continue'
            $lines=@(& $git -c 'credential.helper=' -c 'core.hooksPath=NUL' -c 'core.autocrlf=false' @arguments 2>&1)
            $code=$LASTEXITCODE
        } finally { $ErrorActionPreference=$previous }
        if ($code) {
            $message=$lines -join ' '
            $reason=if ($message -match '(?i)could not resolve|unable to access|connect|timed out') {'transport'} elseif ($message -match '(?i)not.*repository|not our ref') {'source'} else {'command'}
            throw ('stage_git_'+$reason+'_'+$code)
        }
        return (($lines | ForEach-Object { [string]$_ }) -join [Environment]::NewLine)
    }
    $temp=Join-Path $root ('checkout-'+[guid]::NewGuid().ToString('N'))
    $null=[IO.Directory]::CreateDirectory($temp)
    try {
        $step='public_fetch'
        $null=RunGit @('init','--quiet',$temp)
        $null=RunGit @('-C',$temp,'remote','add','origin',$remote)
        $null=RunGit @('-C',$temp,'fetch','--quiet','--depth=1','--no-tags','origin',$Revision)
        $null=RunGit @('-C',$temp,'update-ref',('refs/remotes/origin/'+$branch),$Revision)
        $null=RunGit @('-C',$temp,'checkout','-q','-b',$branch,$Revision)
        $null=RunGit @('-C',$temp,'branch','--set-upstream-to',('origin/'+$branch),$branch)
        $step='verify'
        Must ((RunGit @('-C',$temp,'rev-parse','HEAD')) -ceq $Revision) 'revision_mismatch'
        Must ((RunGit @('-C',$temp,'remote','get-url','origin')) -ceq $remote) 'remote_mismatch'
        Must ([string]::IsNullOrWhiteSpace((RunGit @('-C',$temp,'status','--porcelain=v1')))) 'dirty_checkout'
        Must ([IO.File]::Exists((Join-Path $temp 'AGENTS.md')) -and [IO.File]::Exists((Join-Path $temp 'app\src\main\AndroidManifest.xml'))) 'project_incomplete'
        $count=@((RunGit @('-C',$temp,'ls-files')) -split '\r?\n').Count
        Must ($count -gt 1000 -and $count -lt 10000) 'unexpected_tracked_count'
        $size=[long]((Get-ChildItem -LiteralPath $temp -File -Force -Recurse | Measure-Object -Property Length -Sum).Sum)
        Must ($size -gt 0 -and $size -le 192MB) 'workspace_size'
        $step='handoff'
        $data=[ordered]@{marker='analyst-user-codex-workspace-v1';owner=$owner.Value;revision=$Revision;files=$count;bytes=$size;phase='prepared'}
        $stamp=Join-Path $root ('record-'+[guid]::NewGuid().ToString('N'))
        try {
            [IO.File]::WriteAllText($stamp,($data|ConvertTo-Json -Compress))
            [IO.Directory]::Move($temp,$dest)
            [IO.File]::Move($stamp,$receipt)
        } finally { if ([IO.File]::Exists($stamp)) { [IO.File]::Delete($stamp) } }
        Set-Acl -LiteralPath $dest -AclObject (DirectoryRules 'Modify')
        Access $dest 'Modify'
        $data.phase='ready'
        $stamp=Join-Path $root ('record-'+[guid]::NewGuid().ToString('N'))
        try { [IO.File]::WriteAllText($stamp,($data|ConvertTo-Json -Compress));[IO.File]::Replace($stamp,$receipt,[NullString]::Value) }
        finally { if ([IO.File]::Exists($stamp)) { [IO.File]::Delete($stamp) } }
        Write-Output ('HOME_CODEX_PROJECT='+(@{status='delivered';initial_revision=$Revision;files=$count;bytes=$size;clean=$true;owner_modify=$true;personal_login_used=$false}|ConvertTo-Json -Compress))
    } finally { if ([IO.Directory]::Exists($temp)) { [IO.Directory]::Delete($temp,$true) } }
} finally { $lock.Dispose() }
