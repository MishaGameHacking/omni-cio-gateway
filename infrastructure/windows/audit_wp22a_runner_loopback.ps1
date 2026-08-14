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
            catch { return $true }
        }
        finally { $async.AsyncWaitHandle.Close() }
    }
    finally { $client.Dispose() }
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

$ready = (
    $runnerIdentityMatchesService -and
    -not $runnerIsAdministrator -and
    $remoteTaskRunning -and
    $loopbackListenerPresent -and
    $firewallBound -and
    $connectionDenied
)
$reason = if ($ready) {
    "WP22A_RUNNER_LOOPBACK_SPOOF_DENIED"
}
elseif (-not $runnerIdentityMatchesService) {
    "WP22A_RUNNER_IDENTITY_MISMATCH"
}
elseif ($runnerIsAdministrator) {
    "WP22A_RUNNER_ADMINISTRATOR_FORBIDDEN"
}
elseif (-not $remoteTaskRunning -or -not $loopbackListenerPresent) {
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
    evidence_class = "RUNNER_LOOPBACK_SPOOF_AUDIT"
    implementation_sha = $sha
    runner_identity_matches_service = [bool]$runnerIdentityMatchesService
    runner_is_administrator = [bool]$runnerIsAdministrator
    remote_task_running = [bool]$remoteTaskRunning
    loopback_listener_present = [bool]$loopbackListenerPresent
    runner_loopback_firewall_bound = [bool]$firewallBound
    runner_loopback_connection_denied = [bool]$connectionDenied
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
