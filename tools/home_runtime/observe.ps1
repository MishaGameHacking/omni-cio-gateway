# Read only the sanitized enrollment receipt and health endpoints. Never wakes the protected WSL guest.
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') {
    throw 'Wrong observer context'
}
$base=Join-Path $env:ProgramFiles 'AnalystAI-HomeRuntime'
$file=Join-Path $base 'report\status.json'
function Health([string]$url) {
    $request=[Net.HttpWebRequest]::Create($url)
    $request.Proxy=$null
    $request.AllowAutoRedirect=$false
    $request.Timeout=3500
    try { $r=$request.GetResponse() }
    catch [Net.WebException] { $r=$_.Exception.Response; if (-not $r) { return 0 } }
    try { return [int]$r.StatusCode } finally { $r.Close() }
}
function Observe {
    try {
        $row=Get-Content -ErrorAction Stop -Raw -LiteralPath $file | ConvertFrom-Json
        if ($row.package -ne 'd958608239005290f808' -or [string]$row.phase -notmatch '^(?:failed-)?(?:windows|import|configure|application|local-model|login-check|supervising)$') {
            throw [IO.InvalidDataException]::new('Foreign receipt')
        }
        $phase=[string]$row.phase
    } catch [Management.Automation.ItemNotFoundException] { $phase='awaiting_enrollment' }
      catch [UnauthorizedAccessException] { $phase='status_not_readable' }
      catch { $phase='status_unavailable' }
    return [ordered]@{phase=$phase;health=(Health 'http://127.0.0.1:18158/health');anonymous=(Health 'http://127.0.0.1:18158/me')}
}
foreach ($i in 0..4) {
    $status=Observe
    if ($i -eq 0 -or $i -eq 4 -or $last -ne $status.phase) {
        Write-Output ('HOME_PROTECTED_OBSERVATION='+($status | ConvertTo-Json -Compress))
    }
    if ($status.phase -eq 'supervising' -and $status.health -eq 200 -and $status.anonymous -eq 401) { break }
    if ($status.phase -like 'failed-*' -or $i -eq 4) { break }
    $last=$status.phase
    Start-Sleep -Seconds 30
}
