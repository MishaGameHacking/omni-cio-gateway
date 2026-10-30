# Inspect the requested installation and its own CLI status. Never inspect personal authentication files.
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Unexpected machine or service context' }
$r=[ordered]@{technical_user='NetworkService';desktop_processes=0;desktop_packages=@();owner_cli_files=@();service_cli='absent_from_path';linux=@()}
trap {
    if (-not $r) { $r=[ordered]@{} }
    $r.check_fault=[ordered]@{line=$_.InvocationInfo.ScriptLineNumber;type=$_.Exception.GetBaseException().GetType().Name;id=(($_.FullyQualifiedErrorId -split ',')[0] -replace '[^a-zA-Z0-9_-]','')}
    [Console]::WriteLine('HOME_CODEX_HOST='+($r|ConvertTo-Json -Depth 6 -Compress))
    exit 1
}
$apps=@(Get-CimInstance -ClassName Win32_Process -Filter "Name='Codex.exe' OR Name='ChatGPT.exe' OR Name='codex-app-server.exe' OR Name='codex-x86_64-pc-windows-msvc.exe'" -ErrorAction SilentlyContinue)
$r.desktop_processes=$apps.Count
$r.desktop_names=@($apps.Name | Where-Object { $_ -in 'Codex.exe','ChatGPT.exe','codex-app-server.exe','codex-x86_64-pc-windows-msvc.exe' } | Sort-Object -Unique)
function PackageInfo([string]$scope) {
    try {
        $argsFor=@{ErrorAction='Stop'}
        if ($scope -eq 'all_users') { $argsFor.AllUsers=$true }
        $packages=@(Get-AppxPackage @argsFor | Where-Object { $_.Name -match '^OpenAI\.(Codex|ChatGPT[-.]?Desktop|ChatGPT)$' })
        return [ordered]@{scope=$scope;status='queried';packages=@($packages | ForEach-Object { [ordered]@{name=$_.Name;version=[string]$_.Version} })}
    } catch { return [ordered]@{scope=$scope;status='unavailable'} }
}
$r.desktop_packages=@((PackageInfo 'service'),(PackageInfo 'all_users'))
# Only publisher/package names or installation metadata from the single owner's confirmed Windows profile.
$ownerProfile=Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and [IO.Path]::GetFileName($_.LocalPath) -ieq 'Klima' } | Select-Object -First 1
if ($ownerProfile) {
    $r.owner_apps=@()
    foreach ($target in @(@('AppData\Local\Packages','OpenAI.Codex_*','desktop-package'),@('AppData\Local\Packages','OpenAI.ChatGPT-Desktop_*','chatgpt-package'),@('.vscode\extensions','openai.chatgpt-*','ide-extension'))) {
        try {
            $items=@(Get-ChildItem -Directory -LiteralPath (Join-Path $ownerProfile.LocalPath $target[0]) -Filter $target[1] -ErrorAction Stop)
            $r.owner_apps+=@([ordered]@{kind=$target[2];status=if ($items.Count) {'present'} else {'not_listed'}})
        } catch { $r.owner_apps+=@([ordered]@{kind=$target[2];status='unavailable'}) }
    }
    try {
        $key='Registry::HKEY_USERS\'+$ownerProfile.SID+'_Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages'
        $packageKeys=@(Get-ChildItem -LiteralPath $key -ErrorAction Stop | Where-Object { $_.PSChildName -match '^OpenAI\.(?:Codex|ChatGPT[-.]?Desktop|ChatGPT)_' })
        $r.owner_package_records=@($packageKeys | ForEach-Object { if ($_.PSChildName -match '^(OpenAI\.[A-Za-z.-]+)_([0-9.]+)_') { [ordered]@{product=$Matches[1];version=$Matches[2]} } })
    } catch { $r.owner_package_records='unavailable' }
    foreach ($entry in @(@('winget-link','AppData\Local\Microsoft\WinGet\Links\codex.exe'),@('npm-shim','AppData\Roaming\npm\codex.cmd'),@('npm-package','AppData\Roaming\npm\node_modules\@openai\codex\package.json'),
                          @('windows-alias','AppData\Local\Microsoft\WindowsApps\codex.exe'),@('desktop-exe','AppData\Local\Programs\Codex\Codex.exe'))) {
        $path=Join-Path $ownerProfile.LocalPath $entry[1]
        try {
            $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop
            $record=[ordered]@{kind=$entry[0];status='present'}
            if ($entry[0] -eq 'npm-package' -and $item.Length -le 100000 -and -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                $p=Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
                if ($p.name -eq '@openai/codex' -and $p.version -match '^[0-9][0-9a-zA-Z.+-]{0,45}$') { $record.version=$p.version }
            }
        } catch [UnauthorizedAccessException] { $record=[ordered]@{kind=$entry[0];status='unreadable'} }
          catch { continue }
        $r.owner_cli_files+=@($record)
    }
}
$r.machine_installs=@()
foreach ($rel in @('OpenAI\Codex\codex.exe','Codex\Codex.exe','WinGet\Links\codex.exe','nodejs\node_modules\@openai\codex\package.json')) {
    $item=Get-Item -LiteralPath (Join-Path $env:ProgramFiles $rel) -ErrorAction SilentlyContinue
    if ($item) { $r.machine_installs+=@([IO.Path]::GetFileName($rel)) }
}
foreach ($key in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall')) {
    foreach ($entry in @(Get-ItemProperty ($key+'\*') -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match '^(?:OpenAI )?(?:ChatGPT|Codex)(?: Desktop| CLI)?$' })) {
        $r.machine_installs+=$entry.DisplayName
    }
}
if ($ownerProfile) {
    try {
        $shellKey='Registry::HKEY_USERS\'+$ownerProfile.SID+'\Software\Microsoft\Windows\CurrentVersion\Lxss'
        $items=@(Get-ChildItem -LiteralPath $shellKey -ErrorAction Stop)
        $r.owner_wsl_registrations=$items.Count
    } catch { $r.owner_wsl_registrations='unavailable' }
}
$cmd=Get-Command codex.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($cmd) {
    $r.service_cli='found'
    $version=(& $cmd.Source --version 2>$null | Out-String)
    if ($version -match '(?i)codex(?:-cli)?\s+([0-9][\w.-]{0,45})') { $r.service_cli_version=$Matches[1] }
}
$linux=@'
import json, os, pathlib, pwd, re, shutil, subprocess
home=pathlib.Path.home()
paths=[shutil.which('codex'), '/usr/local/bin/codex', '/usr/bin/codex',home/'.local/bin/codex',home/'.npm-global/bin/codex',*sorted(home.glob('.nvm/versions/node/*/bin/codex'))]
exe=next((pathlib.Path(x) for x in paths if x and pathlib.Path(x).is_file() and os.access(x,os.X_OK)),None)
row={'cli':'unavailable','identity':pwd.getpwuid(os.geteuid()).pw_name}
if exe:
    env=dict(os.environ,PATH=str(exe.parent)+':'+os.environ.get('PATH','/usr/bin:/bin'))
    version=subprocess.run([str(exe),'--version'],capture_output=True,text=True,env=env,timeout=12)
    m=re.search(r'codex(?:-cli)?\s+([0-9][\w.-]{0,45})',version.stdout,re.I)
    row['cli']='verified' if m else 'unverified'
    if m:
        row['version']=m.group(1)
        status=subprocess.run([str(exe),'login','status'],capture_output=True,text=True,env=env,timeout=12)
        row['own_login']='available' if status.returncode==0 else 'not_confirmed'
print(json.dumps(row))
'@
$wsl=Join-Path $env:SystemRoot 'System32\wsl.exe'
$ErrorActionPreference='Continue'
$list=((& $wsl --list --quiet 2>$null | Out-String) -replace "`0",'') -split '\s+'
foreach ($target in @(@('AnalystAI-Home','analyst-ai'),@('Ubuntu-24.04','analyst-ci'))) {
    if ($target[0] -notin $list) { continue }
    $result=$linux | & $wsl -d $target[0] -u $target[1] --exec /usr/bin/python3 -I - 2>$null
    if ($LASTEXITCODE -eq 0) {
        $obj=$result|ConvertFrom-Json
        $r.linux+=@([ordered]@{distribution=$target[0];details=$obj})
    } else { $r.linux+=@([ordered]@{distribution=$target[0];status='check_unavailable'}) }
}
Write-Output ('HOME_CODEX_HOST='+($r|ConvertTo-Json -Depth 6 -Compress))
