[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExpectedImplementationSha,
    [switch]$Apply,
    [switch]$Verify,
    [switch]$Cleanup,
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = @(@($Apply, $Verify, $Cleanup) | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw "Choose exactly one of -Apply, -Verify, or -Cleanup." }
if ($env:OS -ne "Windows_NT") { throw "WP22A private remote provisioning requires Windows." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$baseProvisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp15_live_web_acceptance.ps1"
$runtimeName = "omni-cio-runtime"
$baseTaskName = "OmniCIO.V10.WP15LiveAcceptance"
$remoteTaskName = "OmniCIO.V10.WP22APrivateRemote"
$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp15-live"
$appRoot = Join-Path $runtimeRoot "app"
$launcherRelative = "infrastructure\windows\run_wp22a_private_remote_runtime.ps1"
$deploymentMarker = Join-Path $appRoot ".omni-cio-wp15-live-deployment"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ReviewedHead {
    $expected = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    if ($expected -notmatch '^[0-9a-f]{40}$') { throw "WP22A_EXPECTED_SHA_INVALID" }
    $head = @(& git -C $repoRoot rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0 -or $head.Count -ne 1) { throw "WP22A_GIT_HEAD_UNAVAILABLE" }
    $actual = ([string]$head[0]).Trim().ToLowerInvariant()
    if ($actual -ne $expected) { throw "WP22A_GIT_HEAD_MISMATCH" }
    $dirty = @(& git -C $repoRoot status --porcelain 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_GIT_STATUS_UNAVAILABLE" }
    if ($dirty.Count -ne 0) { throw "WP22A_WORKTREE_NOT_CLEAN" }
    return $actual
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

function Resolve-TailscaleExe {
    $candidate = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($null -ne $candidate) { return $candidate.Source }
    $paths = @(
        (Join-Path $env:ProgramFiles "Tailscale\tailscale.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Tailscale\tailscale.exe")
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path -PathType Leaf) { return $path }
    }
    throw "WP22A_TAILSCALE_CLI_NOT_INSTALLED"
}

function Invoke-TailscaleText {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$AllowFailure
    )
    $output = @(& $Exe @Arguments 2>&1)
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { [string]$_ }) -join "`n"
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "WP22A_TAILSCALE_COMMAND_FAILED"
    }
    return [ordered]@{ exit_code = $exitCode; text = $text }
}

function Get-TailscaleIdentity {
    param([Parameter(Mandatory = $true)][string]$Exe)
    $raw = Invoke-TailscaleText -Exe $Exe -Arguments @("status", "--json")
    try { $status = $raw.text | ConvertFrom-Json -ErrorAction Stop }
    catch { throw "WP22A_TAILSCALE_STATUS_INVALID" }
    if ([string]$status.BackendState -ne "Running") { throw "WP22A_TAILSCALE_NOT_RUNNING" }
    if ($null -eq $status.Self -or -not [bool]$status.Self.Online) {
        throw "WP22A_TAILSCALE_SELF_OFFLINE"
    }
    $tagsProperty = @($status.Self.PSObject.Properties | Where-Object { $_.Name -eq "Tags" }) | Select-Object -First 1
    $tags = if ($null -ne $tagsProperty) { @($tagsProperty.Value) } else { @() }
    $activeTags = @($tags | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
    if ($activeTags.Count -ne 0) {
        throw "WP22A_TAILSCALE_TAGGED_NODE_UNSUPPORTED"
    }
    $hostName = ([string]$status.Self.DNSName).Trim().ToLowerInvariant().TrimEnd('.')
    if ($hostName -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.ts\.net$') {
        throw "WP22A_TAILSCALE_DNS_NAME_INVALID"
    }
    $userId = [string]$status.Self.UserID
    $property = @($status.User.PSObject.Properties | Where-Object { $_.Name -eq $userId }) | Select-Object -First 1
    if ($null -eq $property) { throw "WP22A_TAILSCALE_OWNER_IDENTITY_UNAVAILABLE" }
    $login = ([string]$property.Value.LoginName).Trim()
    if ([string]::IsNullOrWhiteSpace($login)) { throw "WP22A_TAILSCALE_OWNER_LOGIN_EMPTY" }
    if ($login.ToCharArray() | Where-Object { [int]$_ -gt 127 }) {
        throw "WP22A_TAILSCALE_OWNER_LOGIN_NON_ASCII_UNSUPPORTED"
    }
    $normalized = $login.ToLowerInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $digest = $sha.ComputeHash($bytes)
        $fingerprint = -join ($digest | ForEach-Object { $_.ToString("x2") })
    }
    finally { $sha.Dispose() }
    return [ordered]@{ host = $hostName; owner_login_sha256 = $fingerprint }
}

function Test-NoFunnel {
    param([Parameter(Mandatory = $true)][string]$Exe)
    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("funnel", "status") -AllowFailure
    if ($status.exit_code -ne 0 -and [string]::IsNullOrWhiteSpace($status.text)) { return $true }
    return -not (
        $status.text -match '(?i)Available on the internet:' -or
        $status.text -match '(?i)\(Funnel on\)'
    )
}

function Get-ServeState {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string]$HostName
    )
    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "status") -AllowFailure
    $target = "127.0.0.1:$Port"
    $matches = $status.exit_code -eq 0 -and
        $status.text.IndexOf($HostName, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $status.text.IndexOf($target, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $anyServe = $status.exit_code -eq 0 -and $status.text -match '(?i)https://[^\s]+\.ts\.net'
    return [ordered]@{ expected = [bool]$matches; any = [bool]$anyServe }
}

function Disable-ServeChecked {
    param([Parameter(Mandatory = $true)][string]$Exe)

    [void](Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "off") -AllowFailure)
    $status = Invoke-TailscaleText -Exe $Exe -Arguments @("serve", "status")
    if ($status.text -match '(?i)https://[^\s]+\.ts\.net') {
        throw "WP22A_TAILSCALE_SERVE_DISABLE_FAILED"
    }
}

function New-RandomRuntimePassword {
    $bytes = New-Object byte[] 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) }
    finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes) + "!aA7"
}

function Invoke-BaseProvisioner {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][ValidateSet("Apply", "Cleanup")][string]$Mode
    )
    $switchName = "-$Mode"
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $baseProvisioner `
        -ExpectedImplementationSha $Sha $switchName -Port $Port *> $null
    if ($LASTEXITCODE -ne 0) {
        throw ("WP22A_BASE_WEB_{0}_FAILED" -f $Mode.ToUpperInvariant())
    }
}

function Remove-RunnerLoopbackFirewall {
    Remove-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
}

function Install-RunnerLoopbackFirewall {
    if (-not (Test-Administrator)) { throw "WP22A_FIREWALL_REQUIRES_ADMINISTRATOR" }
    $runnerSid = Get-RunnerSidValue
    $runnerSddl = "D:(A;;CC;;;$runnerSid)"
    Remove-RunnerLoopbackFirewall
    New-NetFirewallRule `
        -Name $runnerFirewallRuleName `
        -DisplayName "Omni-CIO V10 WP22A block CI runner loopback Web" `
        -Description "Blocks the ordinary GitHub runner identity from connecting directly to the WP22A loopback backend and spoofing Tailscale identity headers." `
        -Direction Outbound `
        -Action Block `
        -Enabled True `
        -Profile Any `
        -Protocol TCP `
        -RemoteAddress 127.0.0.1 `
        -RemotePort $Port `
        -LocalUser $runnerSddl `
        -ErrorAction Stop | Out-Null
}

function Test-RunnerLoopbackFirewall {
    $runnerSid = Get-RunnerSidValue
    $rule = Get-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule) { return $false }
    if ([string]$rule.Enabled -ne "True" -or [string]$rule.Direction -ne "Outbound" -or [string]$rule.Action -ne "Block") {
        return $false
    }
    $portFilter = $rule | Get-NetFirewallPortFilter -ErrorAction Stop
    $addressFilter = $rule | Get-NetFirewallAddressFilter -ErrorAction Stop
    $securityFilter = $rule | Get-NetFirewallSecurityFilter -ErrorAction Stop
    $remotePorts = @($portFilter.RemotePort | ForEach-Object { [string]$_ })
    $remoteAddresses = @($addressFilter.RemoteAddress | ForEach-Object { [string]$_ })
    $localUser = [string]$securityFilter.LocalUser
    return (
        [string]$portFilter.Protocol -eq "TCP" -and
        $remotePorts -contains [string]$Port -and
        $remoteAddresses -contains "127.0.0.1" -and
        $localUser.IndexOf($runnerSid, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    )
}

function Restore-LocalWebTask {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][string]$TailscaleExe
    )

    Disable-ServeChecked -Exe $TailscaleExe
    if (-not (Test-NoFunnel -Exe $TailscaleExe)) {
        throw "WP22A_FUNNEL_PUBLIC_INGRESS_ACTIVE"
    }
    Stop-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $remoteTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-RunnerLoopbackFirewall

    $baseTaskPresent = $null -ne (Get-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue)
    if ((Test-Path -LiteralPath $runtimeRoot) -or $baseTaskPresent) {
        Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup
    }
    Invoke-BaseProvisioner -Sha $Sha -Mode Apply
}

function Install-RemoteTask {
    param(
        [Parameter(Mandatory = $true)][string]$Sha,
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][string]$OwnerFingerprint
    )
    if (-not (Test-Administrator)) { throw "WP22A_APPLY_REQUIRES_ADMINISTRATOR" }

    Stop-ScheduledTask -TaskName $remoteTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $remoteTaskName -Confirm:$false -ErrorAction SilentlyContinue
    $baseTaskPresent = $null -ne (Get-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue)
    if ((Test-Path -LiteralPath $runtimeRoot) -or $baseTaskPresent) {
        Invoke-BaseProvisioner -Sha $Sha -Mode Cleanup
    }
    Invoke-BaseProvisioner -Sha $Sha -Mode Apply

    $launcher = Join-Path $appRoot $launcherRelative
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        throw "WP22A_REMOTE_LAUNCHER_MISSING"
    }
    if (-not (Test-Path -LiteralPath $deploymentMarker -PathType Leaf)) {
        throw "WP22A_DEPLOYMENT_MARKER_MISSING"
    }
    if ((Get-Content -LiteralPath $deploymentMarker -Raw).Trim().ToLowerInvariant() -ne $Sha) {
        throw "WP22A_DEPLOYMENT_MARKER_MISMATCH"
    }

    Stop-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue

    $runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    $administratorsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $admins = @(Get-LocalGroupMember -SID $administratorsSid -ErrorAction Stop)
    if ($admins.SID.Value -contains $runtimeUser.SID.Value) {
        throw "WP22A_REMOTE_RUNTIME_IS_ADMINISTRATOR"
    }

    Install-RunnerLoopbackFirewall
    if (-not (Test-RunnerLoopbackFirewall)) {
        throw "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND"
    }

    $runtimePassword = New-RandomRuntimePassword
    try {
        $securePassword = ConvertTo-SecureString -String $runtimePassword -AsPlainText -Force
        Set-LocalUser -Name $runtimeName -Password $securePassword -ErrorAction Stop
        Enable-LocalUser -Name $runtimeName -ErrorAction Stop
        $runtimeAccount = "$env:COMPUTERNAME\$runtimeName"
        $arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$appRoot`" -ImplementationSha $Sha -ExternalHost $HostName -OwnerLoginSha256 $OwnerFingerprint -Port $Port"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
        Register-ScheduledTask -TaskName $remoteTaskName -Action $action -Trigger $trigger -Settings $settings -User $runtimeAccount -Password $runtimePassword -RunLevel Limited -Force | Out-Null
        Start-ScheduledTask -TaskName $remoteTaskName -ErrorAction Stop
    }
    finally {
        $runtimePassword = $null
        $securePassword = $null
    }
}

function Test-BackendLoopback {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $false }
    foreach ($listener in $listeners) {
        $address = [string]$listener.LocalAddress
        if ($address -notin @("127.0.0.1", "::1")) { return $false }
    }
    return $true
}

function Wait-LocalRemoteStatus {
    param([Parameter(Mandatory = $true)][string]$HostName)
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/v10/web/private-tailnet-login/status" -Headers @{ Host = $HostName } -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $body = $response.Content | ConvertFrom-Json -ErrorAction Stop
                if ([bool]$body.enabled) { return $true }
            }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-RemoteOwnerSession {
    param([Parameter(Mandatory = $true)][string]$HostName)
    $origin = "https://$HostName"
    $session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    try {
        $login = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$origin/api/v10/web/private-tailnet-login" -Headers @{ Origin = $origin } -WebSession $session -ContentType "application/json" -Body "{}" -TimeoutSec 10
        if ($login.StatusCode -ne 200) { return $false }
        $view = Invoke-WebRequest -UseBasicParsing -Uri "$origin/api/v10/web/session" -WebSession $session -TimeoutSec 10
        if ($view.StatusCode -ne 200) { return $false }
        $payload = $view.Content | ConvertFrom-Json -ErrorAction Stop
        if (-not [bool]$payload.authenticated) { return $false }
        $csrf = $session.Cookies.GetCookies([Uri]$origin)["__Host-omni_v10_csrf"]
        if ($null -eq $csrf -or [string]::IsNullOrWhiteSpace($csrf.Value)) { return $false }
        $logout = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$origin/api/v10/web/session/logout" -Headers @{ Origin = $origin; "X-Omni-CSRF" = $csrf.Value } -WebSession $session -ContentType "application/json" -Body "{}" -TimeoutSec 10
        return $logout.StatusCode -eq 200
    }
    catch { return $false }
}

function Write-Result {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Result)
    if ($AsJson) { $Result | ConvertTo-Json -Depth 4 -Compress; return }
    foreach ($key in $Result.Keys) { Write-Output ("{0}: {1}" -f $key, $Result[$key]) }
}

$sha = Get-ReviewedHead
$tailscale = Resolve-TailscaleExe
$identity = Get-TailscaleIdentity -Exe $tailscale

if ($Cleanup) {
    if (-not (Test-Administrator)) { throw "WP22A_CLEANUP_REQUIRES_ADMINISTRATOR" }
    Restore-LocalWebTask -Sha $sha -TailscaleExe $tailscale
    Write-Result -Result ([ordered]@{
        status = "PASS"; reason = "WP22A_PRIVATE_REMOTE_DISABLED"; public_ingress = $false
    })
    exit 0
}

if (-not (Test-NoFunnel -Exe $tailscale)) { throw "WP22A_FUNNEL_PUBLIC_INGRESS_ACTIVE" }
$serveBefore = Get-ServeState -Exe $tailscale -HostName $identity.host
if ($Apply -and $serveBefore.any -and -not $serveBefore.expected) {
    throw "WP22A_EXISTING_SERVE_CONFIGURATION_REQUIRES_OWNER_REVIEW"
}

if ($Apply) {
    try {
        Install-RemoteTask -Sha $sha -HostName $identity.host -OwnerFingerprint $identity.owner_login_sha256
        if (-not (Wait-LocalRemoteStatus -HostName $identity.host)) {
            throw "WP22A_REMOTE_BACKEND_NOT_READY"
        }
        if (-not (Test-BackendLoopback)) { throw "WP22A_BACKEND_NOT_LOOPBACK_ONLY" }
        if (-not (Test-RunnerLoopbackFirewall)) {
            throw "WP22A_RUNNER_LOOPBACK_FIREWALL_NOT_BOUND"
        }
        if (-not $serveBefore.expected) {
            & $tailscale serve --bg "http://127.0.0.1:$Port"
            if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_SERVE_ENABLE_FAILED" }
        }
    }
    catch {
        try {
            Restore-LocalWebTask -Sha $sha -TailscaleExe $tailscale
        }
        catch {
            throw "WP22A_APPLY_FAILED_AND_LOCAL_ROLLBACK_FAILED"
        }
        throw
    }
}

$serve = Get-ServeState -Exe $tailscale -HostName $identity.host
$loopbackOnly = Test-BackendLoopback
$runnerFirewallBound = Test-RunnerLoopbackFirewall
$remoteOwnerSession = $false
if ($serve.expected -and $loopbackOnly -and $runnerFirewallBound) {
    $remoteOwnerSession = Test-RemoteOwnerSession -HostName $identity.host
}

$ok = $serve.expected -and $loopbackOnly -and $runnerFirewallBound -and $remoteOwnerSession -and (Test-NoFunnel -Exe $tailscale)
$result = [ordered]@{
    status = $(if ($ok) { "PASS" } else { "FAIL" })
    reason = $(if ($ok) { "WP22A_PRIVATE_REMOTE_RUNTIME_ACCEPTED" } else { "WP22A_PRIVATE_REMOTE_RUNTIME_NOT_READY" })
    exact_implementation_binding = $true
    backend_loopback_only = [bool]$loopbackOnly
    runner_loopback_firewall_bound = [bool]$runnerFirewallBound
    tailscale_serve_private = [bool]$serve.expected
    funnel_public_ingress = $false
    owner_identity_binding = [bool]$remoteOwnerSession
    secure_server_session = [bool]$remoteOwnerSession
    external_url = "https://$($identity.host)"
    phone_rehearsal_required = $true
}
Write-Result -Result $result
if (-not $ok) { exit 2 }
exit 0
