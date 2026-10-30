@echo off
setlocal
set "ANALYST_HOME_LAUNCHER_PATH=%~f0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; $lines=[IO.File]::ReadAllLines($env:ANALYST_HOME_LAUNCHER_PATH); $n=[Array]::IndexOf($lines,'# Analyst AI PowerShell'); if($n -lt 0 -or $n -ge $lines.Length-1){exit 1}; $payload=[ScriptBlock]::Create([String]::Join([Environment]::NewLine,[string[]]($lines[($n+1)..($lines.Length-1)]))); if($env:ANALYST_HOME_TEST_LAUNCHER -eq '1'){& $payload -Verify}else{& $payload}"
exit /b %ERRORLEVEL%
# Analyst AI PowerShell
# Run from the downloaded package under your usual Windows account.
[CmdletBinding()]
param([switch]$Verify)
$ErrorActionPreference='Stop'
$checked={
    $ErrorActionPreference='Stop'
    try {
        if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016') { throw 'This package belongs to another computer.' }
        $expected='fb477f21eab4ad72d0b777e3266e60bc49806b812e8f3f2d25910d7168ccd7c4'
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
        Write-Host ('Enrollment failed. {0} (0x{1:X8})' -f $_.Exception.Message,([long]$_.Exception.HResult -band 4294967295L)) -ForegroundColor Red
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
