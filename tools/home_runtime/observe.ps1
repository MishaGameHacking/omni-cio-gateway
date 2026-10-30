# Verify a warm protected guest from Windows without starting it or reading any private files.
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
    try {
        $code=[int]$r.StatusCode
        if ($code -eq 200 -and $url.EndsWith('/health')) {
            $reader=[IO.StreamReader]::new($r.GetResponseStream())
            try {
                $data=New-Object char[] 1025
                $length=$reader.ReadBlock($data,0,$data.Length)
                if ($length -gt 1024 -or ((-join $data[0..($length-1)]) | ConvertFrom-Json).status -ne 'ok') { return 0 }
            } catch { return 0 } finally { $reader.Dispose() }
        }
        return $code
    } finally { $r.Close() }
}
function Account-State {
    try { $null=Get-LocalUser -Name 'AnalystAIHost' -ErrorAction Stop; return 'present' }
    catch { if ($_.FullyQualifiedErrorId -like 'UserNotFound,*') { return 'absent' }; return 'unavailable' }
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
    return [ordered]@{phase=$phase;checked_utc=[DateTime]::UtcNow.ToString('o');account=(Account-State);health=(Health 'http://127.0.0.1:18158/health');anonymous=(Health 'http://127.0.0.1:18158/me')}
}
$deadline=[DateTime]::UtcNow.AddMinutes(3)
$last=''
$healthy=0
do {
    $status=Observe
    $key="$($status.phase)/$($status.account)/$($status.health)/$($status.anonymous)"
    if ($last -ne $key) { Write-Output ('HOME_PROTECTED_OBSERVATION='+($status | ConvertTo-Json -Compress)) }
    $last=$key
    if ($status.phase -eq 'supervising' -and $status.account -eq 'present' -and $status.health -eq 200 -and $status.anonymous -eq 401) {
        $healthy++
        if ($healthy -ge 2) {
            Write-Output ('HOME_PROTECTED_READY='+($status | ConvertTo-Json -Compress))
            return
        }
    } else { $healthy=0 }
    if ($status.phase -like 'failed-*') { break }
    Start-Sleep -Seconds 15
} while ([DateTime]::UtcNow -lt $deadline)
Write-Output ('HOME_PROTECTED_PENDING='+($status | ConvertTo-Json -Compress))
exit 3
