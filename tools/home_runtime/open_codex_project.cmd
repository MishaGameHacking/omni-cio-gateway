@echo off
setlocal
set "ANALYST_PERSONAL_LAUNCHER=%~f0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop';$text=[IO.File]::ReadAllText($env:ANALYST_PERSONAL_LAUNCHER);$mark='# Analyst AI personal session';$idx=$text.IndexOf([Environment]::NewLine+$mark+[Environment]::NewLine);if($idx -lt 0){exit 1};& ([ScriptBlock]::Create($text.Substring($idx+$mark.Length+4)))"
exit /b %ERRORLEVEL%
# Analyst AI personal session
$ErrorActionPreference='Stop'
$parent=Split-Path -Parent $env:ANALYST_PERSONAL_LAUNCHER
$project=Join-Path $parent 'omni-cio-gateway'
$signal=Join-Path $parent 'session-status'
if (-not [IO.File]::Exists((Join-Path $project 'AGENTS.md'))) { Write-Host 'Project folder unavailable';$null=Read-Host 'Press Enter';exit 1 }
Set-Location -LiteralPath $parent
# Resolve executables before entering the editable repository.
$executable=$null
$fixed=Join-Path $env:LOCALAPPDATA 'Programs\OpenAI\Codex\bin'
foreach($n in @('codex.exe','codex.cmd')){
    $p=Join-Path $fixed $n
    if ([IO.File]::Exists($p)) { $executable=$p;break }
}
if (-not $executable) {
    foreach($n in @('codex.exe','codex.cmd','codex.bat')){
        $hit=Get-Command $n -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit -and -not $hit.Source.StartsWith($project+'\',[StringComparison]::OrdinalIgnoreCase)) { $executable=$hit.Source;break }
    }
}
function Record([string]$mode) {
    # An owner-generated status contains no prompt, output, account identifiers or credentials.
    if (-not [IO.Directory]::Exists($signal)) { return }
    $tmp=Join-Path $signal ([Guid]::NewGuid().ToString('N')+'.tmp')
    $dst=Join-Path $signal 'local.json'
    try {
        [IO.File]::WriteAllText($tmp,(@{mode=$mode;utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Compress))
        if ([IO.File]::Exists($dst)) { [IO.File]::Replace($tmp,$dst,[NullString]::Value) } else { [IO.File]::Move($tmp,$dst) }
    } catch {} finally { if ([IO.File]::Exists($tmp)) { [IO.File]::Delete($tmp) } }
}
if ($executable) {
    $n=0
    if ($env:GIT_CONFIG_COUNT) {
        if (-not [int]::TryParse($env:GIT_CONFIG_COUNT,[ref]$n) -or $n -lt 0 -or $n -gt 128) { throw 'Invalid inherited Git configuration' }
    }
    [Environment]::SetEnvironmentVariable('GIT_CONFIG_KEY_'+$n,'safe.directory','Process')
    [Environment]::SetEnvironmentVariable('GIT_CONFIG_VALUE_'+$n,$project.Replace('\','/'),'Process')
    $env:GIT_CONFIG_COUNT=[string]($n+1)
    Set-Location -LiteralPath $project
    $initialTask='Read the latest Lenovo instructions in AGENTS.md. Check AnalystAIHomeHost and the protected Linux API on port 18158. If registration is pending, use the verified local AnalystAI-Linux Start.cmd and confirm actual startup. Continue Analyst AI development here and reply in Russian.'
    Record 'cli-selected'
    & $executable $initialTask
    $result=$LASTEXITCODE
    if ($result -eq 0) { Record 'cli-completed' } else { Record 'cli-returned-error' }
    exit $result
}
try {
    $app=Get-StartApps -ErrorAction Stop | Where-Object { $_.AppID -match '^OpenAI\.(?:Codex|ChatGPT(?:[-.]?Desktop)?)_[a-zA-Z0-9]+![\w.-]+$' } |
        Sort-Object @{Expression={if ($_.AppID -match 'Codex') {0} else {1}}} | Select-Object -First 1
} catch { $app=$null }
$explorer=Join-Path $env:SystemRoot 'explorer.exe'
if ($app) {
    Start-Process -FilePath $explorer -ArgumentList ('shell:AppsFolder\'+$app.AppID)
    Record 'desktop-open-requested'
} else { Record 'select-project-in-ide' }
Write-Host 'Open this project in your installed Codex desktop app or IDE:'
Write-Host $project
Start-Process -FilePath $explorer -ArgumentList ('"'+$project+'"')
$null=Read-Host 'Press Enter to close'
