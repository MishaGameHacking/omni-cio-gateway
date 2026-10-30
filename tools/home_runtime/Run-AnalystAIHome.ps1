# Installed program. The transport self-test has no personal data or persistent effects.
[CmdletBinding()]
param([switch]$TransportCheck)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$state = Join-Path $root 'state'
$import = Join-Path $state 'linux'
$wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
$distro = 'AnalystAI-Service'
$tool = '/opt/analyst-home-bootstrap'
function Save-Status([string]$phase) {
    $dest=Join-Path $root 'report\status.json'
    $next="$dest.next"
    $message=[ordered]@{phase=$phase;utc=[DateTime]::UtcNow.ToString('o');package=$spec.package;port=18158}
    [IO.File]::WriteAllText($next, ($message | ConvertTo-Json -Compress))
    if ([IO.File]::Exists($dest)) { [IO.File]::Replace($next,$dest,[NullString]::Value) }
    else { [IO.File]::Move($next,$dest) }
}
function Native([string[]]$parts) {
    & $wsl @parts
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed ($LASTEXITCODE)" }
}
function Guest([string[]]$parts, [string]$as='root') {
    Native (@('-d',$distro,'-u',$as,'--exec')+$parts)
}
function Send-Bytes([string]$file, [string[]]$parts) {
    $argsList = @('-d',$distro,'-u','root','--exec')+$parts
    # These are fixed Linux names, integers or hashes. Windows paths never enter the child command line here.
    foreach ($v in $argsList) { if ($v -notmatch '^[A-Za-z0-9/._=-]+$') { throw 'Unsupported WSL argument' } }
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $wsl
    $psi.Arguments = $argsList -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $p = New-Object Diagnostics.Process
    $p.StartInfo = $psi
    $source = [IO.File]::OpenRead($file)
    try {
        if (-not $p.Start()) { throw 'Cannot start WSL' }
        try { $source.CopyTo($p.StandardInput.BaseStream,1048576) }
        finally { $p.StandardInput.BaseStream.Close() }
        $p.WaitForExit()
        if ($p.ExitCode -ne 0) { throw "WSL input failed ($($p.ExitCode))" }
    } finally { $source.Dispose(); $p.Dispose() }
}
function Registration {
    $key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
    if (Test-Path -LiteralPath $key) {
        foreach ($item in @(Get-ChildItem -LiteralPath $key)) {
            $properties=Get-ItemProperty -LiteralPath $item.PSPath
            if ($properties.PSObject.Properties['DistributionName'] -and $properties.DistributionName -eq $distro) {
                return [string]$properties.BasePath
            }
        }
    }
}
if ($TransportCheck) {
    if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Wrong transport witness' }
    $distro='AnalystAI-Home'
    $test=[IO.Path]::GetTempFileName()
    try {
        $buffer=New-Object byte[] 1048601
        $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
        [IO.File]::WriteAllBytes($test,$buffer)
        $local=(Get-FileHash -Algorithm SHA256 -LiteralPath $test).Hash
        # The Linux child writes to the real native stdout handle. The staging job compares its digest.
        Write-Output ('EXPECTED_TRANSPORT='+$local.ToLowerInvariant())
        Send-Bytes $test @('/usr/bin/sha256sum')
    } finally { [IO.File]::Delete($test) }
    return
}
$spec = Get-Content -Raw -LiteralPath (Join-Path $root 'enrollment.json') | ConvertFrom-Json
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or $id.User.Value -ne $spec.sid -or
    ([Security.Principal.WindowsPrincipal]::new($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dedicated limited Windows identity required'
}
$ready=Join-Path $state 'ready.txt'
$phase='windows'
try {
    Save-Status $phase
    $location=Registration
    if (-not $location) {
        if ((Test-Path -LiteralPath $import) -or (Test-Path -LiteralPath $ready)) { throw 'Ambiguous guest ownership' }
        $phase='import'; Save-Status $phase
        Native @('--import',$distro,$import,(Join-Path $root 'ubuntu.wsl'),'--version','2')
        $location=Registration
    }
    if (-not $location -or $location.Replace('\\?\','').TrimEnd('\') -ne $import) { throw 'Foreign WSL registration' }
    if (-not (Test-Path -LiteralPath $ready)) {
        $phase='configure'; Save-Status $phase
        Send-Bytes (Join-Path $root 'protected_guest.py') @('/usr/bin/python3','-I','-','configure')
        Native @('--terminate',$distro)
        for ($a=0;$a -lt 45;$a++) {
            $running=((& $wsl --list --running --quiet | Out-String) -replace "`0",'') -split '\s+'
            if ($distro -notin $running) { break }
            Start-Sleep 1
        }
        Send-Bytes (Join-Path $root 'protected_guest.py') @('/usr/bin/python3','-I','-','isolation')
        foreach ($file in @('protected_guest.py','guest_setup.py','upstream_prepare.py','smoke.py')) {
            $source=Join-Path $root $file
            $sha=(Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
            Send-Bytes $source @('/bin/dd',"of=$tool/$file",'status=none')
            Send-Bytes (Join-Path $root 'protected_guest.py') @('/usr/bin/python3','-I','-','verify-file',$file,$sha)
        }
        $phase='application'; Save-Status $phase
        Guest @('/usr/bin/python3','-I',"$tool/guest_setup.py",'api')
        $phase='local-model'; Save-Status $phase
        $modelState=Guest @('/usr/bin/python3','-I',"$tool/guest_setup.py",'model-status')
        if (($modelState | ConvertFrom-Json).status -ne 'verified') {
            Send-Bytes (Join-Path $root 'model.litertlm') @('/usr/bin/python3','-I',"$tool/guest_setup.py",'receive-model')
        }
        Guest @('/usr/bin/python3','-I',"$tool/guest_setup.py",'ai')
        $phase='login-check'; Save-Status $phase
        Guest @('/opt/analyst-ai/venv/bin/python','-I',"$tool/smoke.py") 'analyst-ai'
        [IO.File]::WriteAllText($ready,$spec.package)
    } elseif ([IO.File]::ReadAllText($ready) -ne $spec.package) { throw 'Unknown runtime receipt' }
    Guest @('/bin/systemctl','start','analyst-ai-owner.service','analyst-local-research.service')
    $phase='supervising'; Save-Status $phase
    Guest @('/usr/bin/python3','-I',"$tool/protected_guest.py",'watch') 'analyst-ai'
    throw 'WSL supervisor exited unexpectedly'
} catch { Save-Status ("failed-"+$phase); exit 1 }
