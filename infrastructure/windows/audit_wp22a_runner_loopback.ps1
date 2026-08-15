[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$remoteTaskName = "OmniCIO.V10.WP22APrivateRemote"
$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"
$evidenceRoot = "C:\ProgramData\OmniCIO\wp22a"
$evidencePath = Join-Path $evidenceRoot "owner-rehearsal.sanitized.local.json"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-AccountSidValue {
    param([Parameter(Mandatory = $true)][string]$AccountName)

    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        return "S-1-5-18"
    }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") { return "S-1-5-20" }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") { return "S-1-5-19" }
    try {
        $account = [System.Security.Principal.NTAccount]::new($AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
    catch { throw "WP22A_RUNNER_IDENTITY_SID_UNAVAILABLE" }
}

function Get-RunnerSidValue {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like "actions.runner.*" }
    )
    if ($services.Count -ne 1) { throw "WP22A_RUNNER_SERVICE_IDENTITY_AMBIGUOUS" }
    $startName = ([string]$services[0].StartName).Trim()
    $normalized = $startName.ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        throw "WP22A_RUNNER_LOCAL_SYSTEM_FORBIDDEN"
    }
    return Get-AccountSidValue -AccountName $startName
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_GIT_HEAD_MISMATCH" }
    return $actual
}

function Test-RunnerFirewallBinding {
    param([Parameter(Mandatory = $true)][string]$RunnerSid)

    $rule = Get-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule) { return $false }
    if ([string]$rule.Enabled -ne "True" -or [string]$rule.Direction -ne "Outbound" -or [string]$rule.Action -ne "Block") {
        return $false
    }
    try {
        $portFilter = $rule | Get-NetFirewallPortFilter -ErrorAction Stop
        $addressFilter = $rule | Get-NetFirewallAddressFilter -ErrorAction Stop
        $securityFilter = $rule | Get-NetFirewallSecurityFilter -ErrorAction Stop
    }
    catch { return $false }
    $remotePorts = @($portFilter.RemotePort | ForEach-Object { [string]$_ })
    $remoteAddresses = @($addressFilter.RemoteAddress | ForEach-Object { [string]$_ })
    $localUser = [string]$securityFilter.LocalUser
    return (
        [string]$portFilter.Protocol -eq "TCP" -and
        $remotePorts -contains [string]$Port -and
        $remoteAddresses -contains "127.0.0.1" -and
        $localUser.IndexOf($RunnerSid, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Test-LoopbackListenerPresent {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $false }
    foreach ($listener in $listeners) {
        if ([string]$listener.LocalAddress -notin @("127.0.0.1", "::1")) { return $false }
    }
    return $true
}

function Test-RunnerConnectionDenied {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        try {
            if (-not $async.AsyncWaitHandle.WaitOne(1500)) { return $true }
            try {
                $client.EndConnect($async)
                return $false
            }
            catch [System.Net.Sockets.SocketException] { return $true }
            catch { return $false }
        }
        finally { $async.AsyncWaitHandle.Close() }
    }
    finally { $client.Dispose() }
}

function Test-FileWriteDenied {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = $null
    try {
        $stream = [System.IO.File]::Open(
            $Path,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::Read
        )
        return $false
    }
    catch [System.UnauthorizedAccessException] { return $true }
    catch [System.Security.SecurityException] { return $true }
    catch { return $false }
    finally { if ($null -ne $stream) { $stream.Dispose() } }
}

function Test-CreateDenied {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $probe = Join-Path $Directory ("wp22a-runner-write-probe-" + [guid]::NewGuid().ToString("N") + ".tmp")
    $stream = $null
    $created = $false
    try {
        $stream = [System.IO.File]::Open(
            $probe,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $created = $true
        return $false
    }
    catch [System.UnauthorizedAccessException] { return $true }
    catch [System.Security.SecurityException] { return $true }
    catch { return $false }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if ($created) { Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }
    }
}

function Test-RenameDenied {
    param([Parameter(Mandatory = $true)][string]$Path)

    $directory = Split-Path -Parent $Path
    $target = Join-Path $directory ("wp22a-owner-evidence-rename-probe-" + [guid]::NewGuid().ToString("N") + ".json")
    $renamed = $false
    try {
        [System.IO.File]::Move($Path, $target)
        $renamed = $true
        return $false
    }
    catch [System.UnauthorizedAccessException] { return $true }
    catch [System.Security.SecurityException] { return $true }
    catch { return $false }
    finally {
        if ($renamed -and (Test-Path -LiteralPath $target -PathType Leaf)) {
            try { [System.IO.File]::Move($target, $Path) } catch { }
        }
    }
}

function Write-Result {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)
    if ($AsJson) { $Result | ConvertTo-Json -Depth 4 -Compress; return }
    foreach ($key in $Result.Keys) { Write-Output ("{0}: {1}" -f $key, $Result[$key]) }
}

$sha = Get-ReviewedHead
$runnerSid = Get-RunnerSidValue
$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$currentSid = if ($null -ne $currentIdentity.User) { $currentIdentity.User.Value } else { "" }
$runnerIdentityMatchesService = -not [string]::IsNullOrWhiteSpace($currentSid) -and $currentSid -eq $runnerSid
$runnerIsAdministrator = Test-Administrator
$remoteTask = Get-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
$remoteTaskRunning = $null -ne $remoteTask -and [string]$remoteTask.State -eq "Running"
$loopbackListenerPresent = Test-LoopbackListenerPresent
$firewallBound = Test-RunnerFirewallBinding -RunnerSid $runnerSid
$evidencePresent = Test-Path -LiteralPath $evidencePath -PathType Leaf
$evidenceReadable = $false
$evidenceFileWriteDenied = $false
$evidenceCreateDenied = $false
$evidenceRenameDenied = $false
if ($runnerIdentityMatchesService -and -not $runnerIsAdministrator -and $evidencePresent) {
    try {
        [void](Get-Content -LiteralPath $evidencePath -Raw -ErrorAction Stop)
        $evidenceReadable = $true
    }
    catch { $evidenceReadable = $false }
    $evidenceFileWriteDenied = Test-FileWriteDenied -Path $evidencePath
    $evidenceCreateDenied = Test-CreateDenied -Directory $evidenceRoot
    $evidenceRenameDenied = Test-RenameDenied -Path $evidencePath
}

$connectionDenied = $false
if (
    $runnerIdentityMatchesService -and
    -not $runnerIsAdministrator -and
    $remoteTaskRunning -and
    $loopbackListenerPresent -and
    $firewallBound
) {
    $connectionDenied = Test-RunnerConnectionDenied
}
$remoteTaskAfterProbe = Get-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
$remoteTaskRunningAfterProbe = (
    $null -ne $remoteTaskAfterProbe -and
    [string]$remoteTaskAfterProbe.State -eq "Running"
)
$loopbackListenerPresentAfterProbe = Test-LoopbackListenerPresent

$ready = (
    $runnerIdentityMatchesService -and
    -not $runnerIsAdministrator -and
    $remoteTaskRunning -and
    $loopbackListenerPresent -and
    $remoteTaskRunningAfterProbe -and
    $loopbackListenerPresentAfterProbe -and
    $firewallBound -and
    $connectionDenied -and
    $evidencePresent -and
    $evidenceReadable -and
    $evidenceFileWriteDenied -and
    $evidenceCreateDenied -and
    $evidenceRenameDenied
)
$reason = if ($ready) {
    "WP22A_RUNNER_LOOPBACK_AND_EVIDENCE_MUTATION_DENIED"
}
elseif (-not $runnerIdentityMatchesService) {
    "WP22A_RUNNER_IDENTITY_MISMATCH"
}
elseif ($runnerIsAdministrator) {
    "WP22A_RUNNER_ADMINISTRATOR_FORBIDDEN"
}
elseif (-not $evidencePresent -or -not $evidenceReadable) {
    "WP22A_OWNER_EVIDENCE_NOT_RUNNER_READABLE"
}
elseif (-not $evidenceFileWriteDenied -or -not $evidenceCreateDenied -or -not $evidenceRenameDenied) {
    "WP22A_OWNER_EVIDENCE_RUNNER_MUTATION_ALLOWED"
}
elseif (
    -not $remoteTaskRunning -or
    -not $loopbackListenerPresent -or
    -not $remoteTaskRunningAfterProbe -or
    -not $loopbackListenerPresentAfterProbe
) {
    "WP22A_REMOTE_RUNTIME_NOT_LIVE_FOR_RUNNER_AUDIT"
}
elseif (-not $firewallBound) {
    "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND"
}
else {
    "WP22A_RUNNER_LOOPBACK_CONNECT_ALLOWED"
}

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_class = "RUNNER_LOOPBACK_AND_OWNER_EVIDENCE_AUDIT"
    implementation_sha = $sha
    runner_identity_matches_service = [bool]$runnerIdentityMatchesService
    runner_is_administrator = [bool]$runnerIsAdministrator
    remote_task_running = [bool]$remoteTaskRunning
    loopback_listener_present = [bool]$loopbackListenerPresent
    remote_task_running_after_probe = [bool]$remoteTaskRunningAfterProbe
    loopback_listener_present_after_probe = [bool]$loopbackListenerPresentAfterProbe
    runner_loopback_firewall_bound = [bool]$firewallBound
    runner_loopback_connection_denied = [bool]$connectionDenied
    owner_evidence_present = [bool]$evidencePresent
    owner_evidence_readable = [bool]$evidenceReadable
    runner_owner_evidence_file_write_denied = [bool]$evidenceFileWriteDenied
    runner_owner_evidence_create_denied = [bool]$evidenceCreateDenied
    runner_owner_evidence_rename_denied = [bool]$evidenceRenameDenied
    raw_runner_identity_emitted = $false
    raw_runner_sid_emitted = $false
    private_url_emitted = $false
    owner_login_emitted = $false
    secret_value_emitted = $false
    status = $(if ($ready) { "PASS" } else { "FAIL" })
    reason_code = $reason
}
Write-Result -Result $result
if (-not $ready) { exit 1 }
exit 0
