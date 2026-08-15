[CmdletBinding()]
param(
    [switch]$AsJson,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$baseTaskName = "OmniCIO.V10.WP15LiveAcceptance"
$remoteTaskName = "OmniCIO.V10.WP22APrivateRemote"
$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"
$runtimeName = "omni-cio-runtime"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp15-live"
$deploymentMarker = Join-Path $runtimeRoot "app\.omni-cio-wp15-live-deployment"

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
    return $null
}

function Invoke-TailscaleStatusText {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][ValidateSet("serve", "funnel")][string]$Mode
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = @(& $Exe $Mode status 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [ordered]@{
        ok = ($exitCode -eq 0)
        text = (($output | ForEach-Object { [string]$_ }) -join "`n")
    }
}

function Get-TaskStateSafe {
    param([Parameter(Mandatory = $true)][string]$Name)
    try {
        $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
        if ($null -eq $task) { return "MISSING" }
        return ([string]$task.State).ToUpperInvariant()
    }
    catch { return "UNAVAILABLE" }
}

function Get-ListenerState {
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 0) {
            return [ordered]@{ present = $false; loopback_only = $false }
        }
        $loopbackOnly = $true
        foreach ($listener in $listeners) {
            if ([string]$listener.LocalAddress -notin @("127.0.0.1", "::1")) {
                $loopbackOnly = $false
            }
        }
        return [ordered]@{ present = $true; loopback_only = [bool]$loopbackOnly }
    }
    catch {
        return [ordered]@{ present = $false; loopback_only = $false }
    }
}

$tailscale = Resolve-TailscaleExe
$serveStatusAvailable = $false
$serveConfigured = $false
$serveTargetsBackendPort = $false
$funnelStatusAvailable = $false
$funnelPublic = $false
if ($null -ne $tailscale) {
    $serve = Invoke-TailscaleStatusText -Exe $tailscale -Mode serve
    $serveStatusAvailable = [bool]$serve.ok
    if ($serve.ok) {
        $serveConfigured = [bool]($serve.text -match '(?i)https://[^\s]+\.ts\.net')
        $serveTargetsBackendPort = [bool]($serve.text -match ("127\.0\.0\.1:{0}(?:\s|$)" -f $Port))
    }
    $funnel = Invoke-TailscaleStatusText -Exe $tailscale -Mode funnel
    $funnelStatusAvailable = [bool]$funnel.ok
    if ($funnel.ok) {
        $funnelPublic = [bool](
            $funnel.text -match '(?i)Available on the internet:' -or
            $funnel.text -match '(?i)\(Funnel on\)'
        )
    }
}

$runtimeUserEnabled = $false
$runtimeUserAvailable = $false
try {
    $runtimeUser = Get-LocalUser -Name $runtimeName -ErrorAction Stop
    $runtimeUserAvailable = $true
    $runtimeUserEnabled = [bool]$runtimeUser.Enabled
}
catch { }

$firewallPresent = $false
try {
    $firewallPresent = $null -ne (
        Get-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
    )
}
catch { }

$listener = Get-ListenerState
$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_class = "SANITIZED_LOCAL_DEPLOYMENT_DIAGNOSTIC"
    base_task_state = Get-TaskStateSafe -Name $baseTaskName
    remote_task_state = Get-TaskStateSafe -Name $remoteTaskName
    runtime_root_present = [bool](Test-Path -LiteralPath $runtimeRoot -PathType Container)
    deployment_marker_present = [bool](Test-Path -LiteralPath $deploymentMarker -PathType Leaf)
    runtime_user_available = [bool]$runtimeUserAvailable
    runtime_user_enabled = [bool]$runtimeUserEnabled
    backend_listener_present = [bool]$listener.present
    backend_listener_loopback_only = [bool]$listener.loopback_only
    runner_loopback_firewall_present = [bool]$firewallPresent
    tailscale_cli_present = [bool]($null -ne $tailscale)
    tailscale_serve_status_available = [bool]$serveStatusAvailable
    tailscale_serve_configured = [bool]$serveConfigured
    tailscale_serve_targets_backend_port = [bool]$serveTargetsBackendPort
    tailscale_funnel_status_available = [bool]$funnelStatusAvailable
    funnel_public_ingress = [bool]$funnelPublic
    raw_tailnet_hostname_emitted = $false
    raw_owner_login_emitted = $false
    raw_runner_identity_emitted = $false
    secret_value_emitted = $false
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 4 -Compress
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}
exit 0
