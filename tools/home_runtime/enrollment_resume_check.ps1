# Real Windows parameter binding, scheduler definitions and recovery of an interrupted file copy.
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Installer)
$ErrorActionPreference='Stop'
. $Installer -VerifyOnly | Out-Null
$old='Dedicated account for the Analyst AI home deployment.'
$pass=ConvertTo-SecureString ('Aa1!'+[Guid]::NewGuid().ToString('N')) -AsPlainText -Force
$rejected=$false
try {
    try { Microsoft.PowerShell.LocalAccounts\New-LocalUser -Name $name -Description $old -Password $pass -WhatIf }
    catch [Management.Automation.ParameterBindingException] {
        if ($_.Exception.ParameterName -ne 'Description') { throw }
        $rejected=$true
    }
} finally { $pass.Dispose() }
Need ($rejected -and $old.Length -eq 53 -and $description.Length -le $descriptionRule[0].MaxLength) 'Original Windows regression did not reproduce'

# Nothing is registered with the Windows scheduler during validation.
$options=Home-TaskOptions
$principal=New-ScheduledTaskPrincipal -UserId $options.User -LogonType Password -RunLevel $options.RunLevel
$definition=New-ScheduledTask -Action $options.Action -Trigger $options.Trigger -Settings $options.Settings -Principal $principal -Description $options.Description
Verify-Task $definition ([Security.Principal.WindowsIdentity]::GetCurrent().User)
Need ($definition.Settings.RestartCount -eq 999 -and $definition.Settings.ExecutionTimeLimit -in @('PT0S','P0DT0H0M0S')) 'Boot task settings were not preserved'

$testDir=Join-Path ([IO.Path]::GetTempPath()) ('analyst-resume-'+[Guid]::NewGuid().ToString('N'))
$null=[IO.Directory]::CreateDirectory($testDir)
try {
    $root=Join-Path $testDir 'protected'
    $stage=Join-Path $testDir 'stage'
    $receipt=Join-Path $root 'enrollment.json'
    foreach ($d in @($root,$stage)) { $null=[IO.Directory]::CreateDirectory($d) }
    Save-Enrollment ([ordered]@{marker='analyst-home-runtime-v1';package='d958608239005290f808';machine=$machine;sid=''})
    $prior=Read-Enrollment
    Need (-not $prior.sid -and $prior.package -eq $PackageCode) 'Interrupted receipt cannot be resumed'
    $fileName='enrollment-fixture.txt'
    $copy=Join-Path $root $fileName
    $fixtureSource=Join-Path $stage $fileName
    [IO.File]::WriteAllText($fixtureSource,'enrollment retry fixture')
    $expected=[ordered]@{}
    $expected[$fileName]=(Get-FileHash -Algorithm SHA256 -LiteralPath $fixtureSource).Hash
    Stage-Payload
    $mtime=[IO.File]::GetLastWriteTimeUtc($copy)
    [IO.File]::Delete($fixtureSource)
    Stage-Payload
    Need ([IO.File]::GetLastWriteTimeUtc($copy) -eq $mtime) 'Previously copied input was rewritten'
    $prior.package='foreign'
    Save-Enrollment $prior
    $foreign=$false
    try { $null=Read-Enrollment } catch {
        if ($_.Exception.Message -ne 'Unknown deployment at destination') { throw }
        $foreign=$true
    }
    Need $foreign 'Foreign receipt accepted'
} finally { [IO.Directory]::Delete($testDir,$true) }
[ordered]@{legacy_rejected=$rejected;original_chars=$old.Length;corrected_chars=$description.Length;limit=$descriptionRule[0].MaxLength;
            interrupted_payload='reused';foreign_receipt='rejected';native_task_contract='verified';registered=$false} | ConvertTo-Json -Compress
