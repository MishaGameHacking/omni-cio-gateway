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

function Get-TaskSchedulerHistorySafe {
    param([Parameter(Mandatory = $true)][string]$TaskName)

    $result = [ordered]@{
        query_available = $false
        history_found = $false
        latest_event_id = 0
        latest_event_level = 0
        latest_event_at_utc = ""
        latest_result_event_id = 0
        latest_result_code = ""
        latest_result_event_at_utc = ""
    }
    try {
        $events = @(
            Get-WinEvent -FilterHashtable @{
                LogName = "Microsoft-Windows-TaskScheduler/Operational"
                StartTime = (Get-Date).AddHours(-24)
            } -MaxEvents 500 -ErrorAction Stop
        )
        $result.query_available = $true
        foreach ($event in $events) {
            try {
                [xml]$xml = $event.ToXml()
                $fields = @{}
                foreach ($node in @($xml.Event.EventData.Data)) {
                    $name = [string]$node.Name
                    if (-not [string]::IsNullOrWhiteSpace($name)) {
                        $fields[$name] = [string]$node.'#text'
                    }
                }
                $eventTask = [string]$fields["TaskName"]
                if ($eventTask.TrimStart('\') -ne $TaskName) { continue }

                if (-not [bool]$result.history_found) {
                    $result.history_found = $true
                    $result.latest_event_id = [int]$event.Id
                    $result.latest_event_level = [int]$event.Level
                    $result.latest_event_at_utc = $event.TimeCreated.ToUniversalTime().ToString("o")
                }

                if ([string]::IsNullOrWhiteSpace([string]$result.latest_result_code)) {
                    foreach ($key in @("ResultCode", "ErrorCode", "ReturnCode", "Result")) {
                        $candidate = [string]$fields[$key]
                        if ($candidate -match '^(?:0x[0-9A-Fa-f]+|-?[0-9]+)$') {
                            $result.latest_result_event_id = [int]$event.Id
                            $result.latest_result_code = $candidate
                            $result.latest_result_event_at_utc = $event.TimeCreated.ToUniversalTime().ToString("o")
                            break
                        }
                    }
                }
            }
            catch { }
        }
    }
    catch { }
    return $result
}

function Get-PathStateSafe {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][ValidateSet("Container", "Leaf")][string]$PathType
    )

    try {
        if (Test-Path -LiteralPath $Path -PathType $PathType -ErrorAction Stop) {
            return "PRESENT"
        }
        return "ABSENT"
    }
    catch [System.UnauthorizedAccessException] {
        return "ACCESS_DENIED"
    }
    catch {
        if ([string]$_.FullyQualifiedErrorId -match '(?i)UnauthorizedAccess') {
            return "ACCESS_DENIED"
        }
        return "ERROR"
    }
}

function Get-ListenerState {
    try {
        $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
        if ($listeners.Count -eq 0) {
            return [ordered]@{ present = $false; loopback_only = $false; query_available = $true }
        }
        $loopbackOnly = $true
        foreach ($listener in $listeners) {
            if ([string]$listener.LocalAddress -ne "127.0.0.1") {
                $loopbackOnly = $false
            }
        }
        return [ordered]@{
            present = $true
            loopback_only = [bool]$loopbackOnly
            query_available = $true
        }
    }
    catch {
        return [ordered]@{ present = $false; loopback_only = $false; query_available = $false }
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
        $serveTargetsBackendPort = [bool](
            $serve.text -match ("127\.0\.0\.1:{0}(?:\s|$)" -f $Port)
        )
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
$firewallQueryAvailable = $true
try {
    $firewallPresent = $null -ne (
        Get-NetFirewallRule -Name $runnerFirewallRuleName -ErrorAction SilentlyContinue
    )
}
catch {
    $firewallQueryAvailable = $false
}

$runtimeRootState = Get-PathStateSafe -Path $runtimeRoot -PathType Container
$deploymentMarkerState = Get-PathStateSafe -Path $deploymentMarker -PathType Leaf
$listener = Get-ListenerState
$wp15History = Get-TaskSchedulerHistorySafe -TaskName $baseTaskName
$remoteHistory = Get-TaskSchedulerHistorySafe -TaskName $remoteTaskName
$baseTaskState = Get-TaskStateSafe -Name $baseTaskName
$remoteTaskState = Get-TaskStateSafe -Name $remoteTaskName

$deploymentStateClass = "WP22A_LOCAL_STATE_UNCLASSIFIED"
$applyInProgressOrBlocked = $false
if ($funnelPublic) {
    $deploymentStateClass = "WP22A_PUBLIC_INGRESS_FORBIDDEN"
}
elseif (
    $remoteTaskState -eq "RUNNING" -and
    [bool]$listener.present -and
    [bool]$listener.loopback_only -and
    $firewallPresent -and
    -not $serveConfigured
) {
    $deploymentStateClass = "WP22A_REMOTE_RUNTIME_SERVE_PENDING"
    $applyInProgressOrBlocked = $true
}
elseif (
    $remoteTaskState -eq "RUNNING" -and
    [bool]$listener.present -and
    [bool]$listener.loopback_only -and
    $firewallPresent -and
    $serveConfigured -and
    $serveTargetsBackendPort
) {
    $deploymentStateClass = "WP22A_PRIVATE_REMOTE_RUNTIME_PRESENT"
}
elseif (
    $remoteTaskState -eq "MISSING" -and
    [bool]$listener.present -and
    [bool]$listener.loopback_only -and
    -not $firewallPresent -and
    -not $serveConfigured
) {
    $deploymentStateClass = "WP22A_LOCAL_WEB_ONLY"
}
elseif (
    $remoteTaskState -eq "MISSING" -and
    -not [bool]$listener.present -and
    -not $firewallPresent -and
    -not $serveConfigured
) {
    $deploymentStateClass = "WP22A_DISABLED_NO_WEB_LISTENER"
}

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_class = "SANITIZED_LOCAL_DEPLOYMENT_DIAGNOSTIC"
    deployment_state_class = $deploymentStateClass
    apply_in_progress_or_blocked = [bool]$applyInProgressOrBlocked
    base_task_state = $baseTaskState
    remote_task_state = $remoteTaskState
    task_scheduler_history_query_available = [bool]$wp15History.query_available
    wp15_task_history_found = [bool]$wp15History.history_found
    wp15_latest_scheduler_event_id = [int]$wp15History.latest_event_id
    wp15_latest_scheduler_event_level = [int]$wp15History.latest_event_level
    wp15_latest_scheduler_event_at_utc = [string]$wp15History.latest_event_at_utc
    wp15_latest_scheduler_result_event_id = [int]$wp15History.latest_result_event_id
    wp15_latest_scheduler_result_code = [string]$wp15History.latest_result_code
    wp15_latest_scheduler_result_event_at_utc = [string]$wp15History.latest_result_event_at_utc
    wp22a_remote_task_history_found = [bool]$remoteHistory.history_found
    wp22a_remote_latest_scheduler_event_id = [int]$remoteHistory.latest_event_id
    wp22a_remote_latest_scheduler_event_level = [int]$remoteHistory.latest_event_level
    wp22a_remote_latest_scheduler_event_at_utc = [string]$remoteHistory.latest_event_at_utc
    wp22a_remote_latest_scheduler_result_event_id = [int]$remoteHistory.latest_result_event_id
    wp22a_remote_latest_scheduler_result_code = [string]$remoteHistory.latest_result_code
    wp22a_remote_latest_scheduler_result_event_at_utc = [string]$remoteHistory.latest_result_event_at_utc
    runtime_root_state = $runtimeRootState
    deployment_marker_state = $deploymentMarkerState
    runtime_root_present = [bool]($runtimeRootState -eq "PRESENT")
    deployment_marker_present = [bool]($deploymentMarkerState -eq "PRESENT")
    protected_runtime_path_access_denied = [bool](
        $runtimeRootState -eq "ACCESS_DENIED" -or
        $deploymentMarkerState -eq "ACCESS_DENIED"
    )
    runtime_user_available = [bool]$runtimeUserAvailable
    runtime_user_enabled = [bool]$runtimeUserEnabled
    backend_listener_query_available = [bool]$listener.query_available
    backend_listener_present = [bool]$listener.present
    backend_listener_loopback_only = [bool]$listener.loopback_only
    runner_loopback_firewall_query_available = [bool]$firewallQueryAvailable
    runner_loopback_firewall_present = [bool]$firewallPresent
    tailscale_cli_present = [bool]($null -ne $tailscale)
    tailscale_serve_status_available = [bool]$serveStatusAvailable
    tailscale_serve_configured = [bool]$serveConfigured
    tailscale_serve_targets_backend_port = [bool]$serveTargetsBackendPort
    tailscale_funnel_status_available = [bool]$funnelStatusAvailable
    funnel_public_ingress = [bool]$funnelPublic
    task_scheduler_message_emitted = $false
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
