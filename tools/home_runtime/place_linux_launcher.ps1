param([Parameter(Mandatory)][string]$VerifiedCmd)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016') { throw 'Wrong machine' }
$who=[Security.Principal.WindowsIdentity]::GetCurrent().User
if ($who.Value -ne 'S-1-5-20') { throw 'Wrong staging owner' }
$expected='17859c87c059c40842eeea3ca76acc6355f9760da164bc4420814be15b21dc30'
$base=[Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
$folder=Join-Path $base 'AnalystAI-Linux'
$file=Join-Path $folder 'Start.cmd'
$users=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$admins=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
function Plain([string]$p) {
    $entry=Get-Item -Force -LiteralPath $p
    while ($null -ne $entry) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected path redirection' }
        $entry=if ($entry -is [IO.FileInfo]) { $entry.Directory } else { $entry.Parent }
    }
}
function Owned([string]$p) {
    Plain $p
    $acl=Get-Acl -LiteralPath $p
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $who.Value) { throw 'Location already belongs to another owner' }
    $read=$false
    foreach ($rule in $acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) {
        if ($rule.IdentityReference.Value -in @($system.Value,$admins.Value,$who.Value)) { continue }
        if ($rule.IdentityReference.Value -ne $users.Value -or $rule.AccessControlType -ne 'Allow' -or
            ([int]$rule.FileSystemRights -band (-bnot 0x1200a9))) { throw 'Unverified access rights on launcher' }
        $read=(($rule.FileSystemRights -band [Security.AccessControl.FileSystemRights]::ReadAndExecute) -eq [Security.AccessControl.FileSystemRights]::ReadAndExecute)
    }
    if (-not $read) { throw 'Local user cannot launch the file' }
}
Plain $base
if ((Get-FileHash $VerifiedCmd -Algorithm SHA256).Hash -ne $expected) { throw 'Unexpected approved CMD digest' }
if (-not [IO.Directory]::Exists($folder)) {
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetOwner($who); $acl.SetAccessRuleProtection($true,$false)
    foreach ($s in @($who,$system,$admins)) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($s,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($users,'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow'))
    $null=[IO.Directory]::CreateDirectory($folder,$acl)
}
Owned $folder
if (-not [IO.File]::Exists($file)) {
    $temp=Join-Path $folder ('stage-'+[guid]::NewGuid().ToString('N'))
    try {
        # Write a new file under this directory's ACL, without importing any staging-directory ACL.
        [IO.File]::WriteAllBytes($temp,[IO.File]::ReadAllBytes($VerifiedCmd))
        Owned $temp
        if ((Get-FileHash $temp -Algorithm SHA256).Hash -ne $expected) { throw 'Copied launcher changed' }
        [IO.File]::Move($temp,$file)
    } finally { if ([IO.File]::Exists($temp)) { [IO.File]::Delete($temp) } }
}
Owned $file
if ((Get-FileHash $file -Algorithm SHA256).Hash -ne $expected) { throw 'Another version already occupies the destination' }
Write-Output 'HOME_LOCAL_LAUNCHER=verified-user-read-execute'
