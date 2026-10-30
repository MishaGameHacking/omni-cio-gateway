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
        $expected='115b06788a375286861743f2b48e25d8bd99e6896328ac044d071c764678f682'
        $sourceSha='fc2e2f5dae51c82d7295c733bbd15884be089216092a30e9fb45fe317d655c7e'
        $spool=Join-Path $env:SystemRoot ('ServiceProfiles/NetworkService/AppData/Local/AnalystAI-HomeLab/scm-setup-'+$expected)
        function Verified([string]$filename,[string]$digest) {
            $bytes=[IO.File]::ReadAllBytes((Join-Path $spool $filename))
            $h=[Security.Cryptography.SHA256]::Create()
            try { $actual=[BitConverter]::ToString($h.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
            finally { $h.Dispose() }
            if ($actual -ne $digest) { throw 'The local service setup does not match the reviewed release.' }
            return [Text.Encoding]::UTF8.GetString($bytes)
        }
        $setup=[ScriptBlock]::Create((Verified 'enable_service.ps1' $expected))
        $source=Verified 'AnalystAIHomeHost.cs' $sourceSha
        if ($env:ANALYST_HOME_VERIFY_ONLY -eq '1') { & $setup -HostSource $source -VerifyOnly; return }
        & $setup -HostSource $source
        Start-Sleep -Seconds 5
    } catch {
        Write-Host ('Analyst AI service: {0} (0x{1:X8})' -f $_.Exception.Message,([long]$_.Exception.HResult -band 4294967295L)) -ForegroundColor Red
        if ($env:ANALYST_HOME_VERIFY_ONLY -ne '1') { $null=Read-Host 'Press Enter to close' }
        exit 1
    }
}
if ($Verify) { $env:ANALYST_HOME_VERIFY_ONLY='1'; & $checked; return }
Remove-Item Env:ANALYST_HOME_VERIFY_ONLY -ErrorAction SilentlyContinue
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
if ([Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { & $checked; return }
$payload=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($checked.ToString()))
$exe=Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
$p=Start-Process -FilePath $exe -Verb RunAs -ArgumentList ('-NoLogo -NoProfile -EncodedCommand '+$payload) -Wait -PassThru
exit $p.ExitCode
