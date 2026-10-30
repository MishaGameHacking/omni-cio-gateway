# Run from the downloaded package under your usual Windows account.
[CmdletBinding()]
param([switch]$Verify)
$ErrorActionPreference='Stop'
$checked={
    $ErrorActionPreference='Stop'
    try {
        if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016') { throw 'This package belongs to another computer.' }
        $expected='cf7cd33acc01a6df8d00f9d67ee84682f0b331dfcb93ffbc2db20f8f0b7c315d'
        $spool=Join-Path $env:SystemRoot 'ServiceProfiles/NetworkService/AppData/Local/AnalystAI-HomeLab'
        $file=Join-Path $spool ('installer-'+$expected+'/Install-AnalystAIHome.ps1')
        # Hash the same in-memory bytes that PowerShell will execute. Never elevate a mutable CI file by its path.
        $bytes=[IO.File]::ReadAllBytes($file)
        $h=[Security.Cryptography.SHA256]::Create()
        try { $actual=[BitConverter]::ToString($h.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
        finally { $h.Dispose() }
        if ($actual -ne $expected) { throw 'The staged installer does not match the pinned release.' }
        $install=[ScriptBlock]::Create([Text.Encoding]::UTF8.GetString($bytes))
        if ($env:ANALYST_HOME_VERIFY_ONLY -eq '1') { & $install -VerifyOnly; return }
        & $install
        Start-Sleep -Seconds 5
    } catch {
        Write-Host ('Enrollment failed. '+$_.Exception.Message) -ForegroundColor Red
        if ($env:ANALYST_HOME_VERIFY_ONLY -ne '1') { $null=Read-Host 'Press Enter to close' }
        exit 1
    }
}
if ($Verify) { $env:ANALYST_HOME_VERIFY_ONLY='1'; & $checked; return }
Remove-Item Env:ANALYST_HOME_VERIFY_ONLY -ErrorAction SilentlyContinue
$payload=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($checked.ToString()))
$exe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$child=Start-Process -FilePath $exe -ArgumentList ('-NoLogo -NoProfile -EncodedCommand '+$payload) -Verb RunAs -Wait -PassThru
exit $child.ExitCode
