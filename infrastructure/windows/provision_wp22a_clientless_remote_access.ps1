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
if ($env:OS -ne "Windows_NT") { throw "WP22A clientless provisioning requires Windows." }

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$baseProvisioner = Join-Path $repoRoot "infrastructure\windows\provision_wp15_live_web_acceptance.ps1"
$runtimeName = "omni-cio-runtime"
$baseTaskName = "OmniCIO.V10.WP15LiveAcceptance"
$cloudflaredTaskName = "OmniCIO.V10.WP22A.Cloudflared"
$runnerFirewallRuleName = "OmniCIO.V10.WP22A.BlockRunnerLoopback"
$runtimeRoot = "C:\ProgramData\OmniCIO\runtime\wp15-live"
$appRoot = Join-Path $runtimeRoot "app"
$deploymentMarker = Join-Path $appRoot ".omni-cio-wp15-live-deployment"
$wp22aRoot = "C:\ProgramData\OmniCIO\runtime\wp22a-clientless"
$configRoot = Join-Path $wp22aRoot "config"
$tokenRoot = Join-Path $wp22aRoot "token"
$binRoot = Join-Path $wp22aRoot "bin"
$configPath = Join-Path $configRoot "external-access.json"
$tokenPath = Join-Path $tokenRoot "tunnel.token"
$cloudflaredExe = Join-Path $binRoot "cloudflared.exe"
$launcher = Join-Path $appRoot "infrastructure\windows\run_wp22a_clientless_remote_runtime.ps1"
$cloudflaredVersion = "2026.7.3"
$cloudflaredSha256 = @(
    "8635da43",
    "3b6df819",
    "4746e88e",
    "d9d25895",
    "66c20e38",
    "bfc2a80e",
    "431a348b",
    "7c765841"
) -join ""
$cloudflaredUrl = "https://github.com/cloudflare/cloudflared/releases/download/$cloudflaredVersion/cloudflared-windows-amd64.exe"

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

function Resolve-AccountSid {
    param([Parameter(Mandatory = $true)][string]$AccountName)
    $normalized = $AccountName.Trim().ToUpperInvariant()
    if ($normalized -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) { return "S-1-5-18" }
    if ($normalized -eq "NT AUTHORITY\NETWORKSERVICE") { return "S-1-5-20" }
    if ($normalized -eq "NT AUTHORITY\LOCALSERVICE") { return "S-1-5-19" }
    try {
        $account = [System.Security.Principal.NTAccount]::new($AccountName)
        return $account.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
    catch { throw "WP22A_IDENTITY_SID_UNAVAILABLE" }
}

function Get-RunnerSidValue {
    $services = @(
        Get-CimInstance Win32_Service -ErrorAction Stop |
            Where-Object { $_.Name -like "actions.runner.*" }
    )
    if ($services.Count -ne 1) { throw "WP22A_RUNNER_SERVICE_IDENTITY_AMBIGUOUS" }
    $startName = ([string]$services[0].StartName).Trim()
    if ($startName.ToUpperInvariant() -in @("LOCALSYSTEM", ".\LOCALSYSTEM", "NT AUTHORITY\SYSTEM")) {
        throw "WP22A_RUNNER_LOCAL_SYSTEM_FORBIDDEN"
    }
    return Resolve-AccountSid -AccountName $startName
}

function New-AclRule {
    param(
        [Parameter(Mandatory = $true)][string]$SidValue,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights
    )
    $sid = [System.Security.Principal.SecurityIdentifier]::new($SidValue)
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid,
        $Rights,
        $inherit,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-ProtectedDirectoryAcl {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$AdditionalGrants
    )
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-AclRule -SidValue "S-1-5-18" -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    $acl.AddAccessRule((New-AclRule -SidValue "S-1-5-32-544" -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl)))
    foreach ($entry in $AdditionalGrants.GetEnumerator()) {
        $acl.AddAccessRule((New-AclRule -SidValue ([string]$entry.Key) -Rights ([System.Security.AccessControl.FileSystemRights]$entry.Value)))
    }
    Set-Acl -LiteralPath $Path -AclObject $acl -ErrorAction Stop
}

function Test-PathAclExcludesSid {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$SidValue
    )
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    foreach ($rule in $acl.Access) {
        try {
            $sid = $rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        }
        catch { continue }
        if ($sid -eq $SidValue -and $rule.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow) {
            return $false
        }
    }
    return $true
}

function Convert-SecureStringToPlainText {
    param([Parameter(Mandatory = $true)][Security.SecureString]$SecureValue)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

function Read-OwnerConfiguration {
    $hostName = (Read-Host "WP22A reviewed external hostname (for example omni.example.com)").Trim().ToLowerInvariant().TrimEnd('.')
    if ($hostName -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$') {
        throw "WP22A_EXTERNAL_HOST_INVALID"
    }
    $identitySecure = Read-Host "Cloudflare OWNER identity used by Access" -AsSecureString
    $identity = Convert-SecureStringToPlainText -SecureValue $identitySecure
    try {
        $normalized = $identity.Trim().ToLowerInvariant()
        if (
            [string]::IsNullOrWhiteSpace($normalized) -or
            $normalized.Length -gt 320 -or
            $normalized -notmatch '^[\x21-\x7e]+@[\x21-\x7e]+$'
        ) {
            throw "WP22A_OWNER_IDENTITY_INVALID"
        }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            $digest = $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($normalized))
            $fingerprint = -join ($digest | ForEach-Object { $_.ToString("x2") })
        }
        finally { $sha.Dispose() }
    }
    finally { $identity = $null }

    $tokenSecure = Read-Host "Cloudflare Tunnel token (stored only in protected local file)" -AsSecureString
    $token = Convert-SecureStringToPlainText -SecureValue $tokenSecure
    if ([string]::IsNullOrWhiteSpace($token) -or $token.Length -lt 80 -or $token.Length -gt 4096) {
        $token = $null
        throw "WP22A_TUNNEL_TOKEN_INVALID"
    }
    return [ordered]@{
        external_host = $hostName
        owner_identity_sha256 = $fingerprint
        tunnel_token = $token
    }
}

function Install-CloudflaredBinary {
    New-Item -ItemType Directory -Path $binRoot -Force | Out-Null
    $temp = Join-Path $env:TEMP ("cloudflared-" + [guid]::NewGuid().ToString("N") + ".exe")
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $cloudflaredUrl -OutFile $temp
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $temp -ErrorAction Stop).Hash.ToLowerInvariant()
        if ($actual -ne $cloudflaredSha256) { throw "WP22A_CLOUDFLARED_HASH_MISMATCH" }
        Copy-Item -LiteralPath $temp -Destination $cloudflaredExe -Force
    }
    finally { Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue }
    $installed = (Get-FileHash -Algorithm SHA256 -LiteralPath $cloudflaredExe -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($installed -ne $cloudflaredSha256) { throw "WP22A_CLOUDFLARED_INSTALL_HASH_MISMATCH" }
}

function Set-RunnerLoopbackBlock {
    param([Parameter(Mandatory = $true)][string]$RunnerSid)
    Get-NetFirewallRule -DisplayName $runnerFirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    $sddl = "D:(A;;CC;;;$RunnerSid)"
    New-NetFirewallRule -DisplayName $runnerFirewallRuleName -Direction Outbound -Action Block -Protocol TCP -RemoteAddress "127.0.0.1" -RemotePort $Port -LocalUser $sddl -Profile Any | Out-Null
}

function Test-RunnerLoopbackBlock {
    param([Parameter(Mandatory = $true)][string]$RunnerSid)
    $rule = Get-NetFirewallRule -DisplayName $runnerFirewallRuleName -ErrorAction SilentlyContinue
    if ($null -eq $rule -or [string]$rule.Enabled -ne "True" -or [string]$rule.Action -ne "Block" -or [string]$rule.Direction -ne "Outbound") {
        return $false
    }
    $portFilter = $rule | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
    $addressFilter = $rule | Get-NetFirewallAddressFilter -ErrorAction SilentlyContinue
    $securityFilter = $rule | Get-NetFirewallSecurityFilter -ErrorAction SilentlyContinue
    if ($null -eq $portFilter -or $null -eq $addressFilter -or $null -eq $securityFilter) { return $false }
    $protocolOk = ([string]$portFilter.Protocol).ToUpperInvariant() -in @("TCP", "6")
    $portOk = [string]$portFilter.RemotePort -eq [string]$Port
    $addressOk = @($addressFilter.RemoteAddress) -contains "127.0.0.1"
    $identityOk = ([string]$securityFilter.LocalUser).IndexOf($RunnerSid, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    return $protocolOk -and $portOk -and $addressOk -and $identityOk
}

function Remove-Wp22aLocalContour {
    Stop-ScheduledTask -TaskName $cloudflaredTaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $cloudflaredTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Get-NetFirewallRule -DisplayName $runnerFirewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $wp22aRoot -Recurse -Force -ErrorAction SilentlyContinue
}

function Invoke-BaseProvisionerMode {
    param([Parameter(Mandatory = $true)][ValidateSet("Apply", "Verify", "Cleanup")][string]$Mode)

    $arguments = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", $baseProvisioner,
        "-ExpectedImplementationSha", $ExpectedImplementationSha,
        "-$Mode",
        "-AsJson"
    )
    $raw = @(& powershell.exe @arguments 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_BASE_PROVISIONER_${Mode}_FAILED" }
    try {
        return (($raw | ForEach-Object { [string]$_ }) -join "`n") | ConvertFrom-Json -ErrorAction Stop
    }
    catch { throw "WP22A_BASE_PROVISIONER_${Mode}_OUTPUT_INVALID" }
}

function Restore-AcceptedLocalWeb {
    try {
        [void](Invoke-BaseProvisionerMode -Mode Cleanup)
    }
    catch { throw "WP22A_LOCAL_WEB_CLEANUP_FAILED" }

    try {
        $restored = Invoke-BaseProvisionerMode -Mode Apply
        if ($null -eq $restored -or -not [bool]$restored.ready) {
            throw "WP22A_LOCAL_WEB_RESTORE_NOT_READY"
        }
    }
    catch {
        try { [void](Invoke-BaseProvisionerMode -Mode Cleanup) } catch { }
        throw "WP22A_LOCAL_WEB_RESTORE_FAILED"
    }
}

function Test-BootTriggerPresent {
    param($Task)
    if ($null -eq $Task) { return $false }
    return @(
        $Task.Triggers |
            Where-Object { [string]$_.CimClass.CimClassName -eq "MSFT_TaskBootTrigger" }
    ).Count -ge 1
}

function Test-PersistentTaskSettings {
    param($Task)
    if ($null -eq $Task) { return $false }
    $limit = [string]$Task.Settings.ExecutionTimeLimit
    $unbounded = $limit -in @("PT0S", "P0DT0H0M0S")
    return $unbounded -and [bool]$Task.Settings.StartWhenAvailable -and [int]$Task.Settings.RestartCount -ge 3
}

function Get-Wp22aState {
    $sha = $ExpectedImplementationSha.Trim().ToLowerInvariant()
    $runnerSid = Get-RunnerSidValue
    $markerOk = (Test-Path -LiteralPath $deploymentMarker -PathType Leaf) -and ((Get-Content -LiteralPath $deploymentMarker -Raw -ErrorAction SilentlyContinue).Trim().ToLowerInvariant() -eq $sha)
    $cloudflaredHashOk = $false
    if (Test-Path -LiteralPath $cloudflaredExe -PathType Leaf) {
        $cloudflaredHashOk = ((Get-FileHash -Algorithm SHA256 -LiteralPath $cloudflaredExe -ErrorAction SilentlyContinue).Hash.ToLowerInvariant() -eq $cloudflaredSha256)
    }
    $configOk = $false
    if (Test-Path -LiteralPath $configPath -PathType Leaf) {
        try {
            $config = Get-Content -LiteralPath $configPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            $configOk = ([string]$config.implementation_sha).Trim().ToLowerInvariant() -eq $sha -and
                ([string]$config.owner_identity_sha256) -match '^[0-9a-f]{64}$' -and
                ([string]$config.external_host) -match '^[a-z0-9].*\.[a-z0-9].*$'
        }
        catch { $configOk = $false }
    }

    $baseTask = Get-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue
    $baseAction = if ($null -ne $baseTask) { @($baseTask.Actions) | Select-Object -First 1 } else { $null }
    $basePrincipalOk = $null -ne $baseTask -and ([string]$baseTask.Principal.UserId).ToLowerInvariant().EndsWith("\$runtimeName")
    $remoteTaskDefinitionOk = $null -ne $baseAction -and
        ([string]$baseAction.Arguments).IndexOf("run_wp22a_clientless_remote_runtime.ps1", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ([string]$baseAction.Arguments).IndexOf("-ConfigPath", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $remoteTaskPersistenceOk = (Test-BootTriggerPresent -Task $baseTask) -and (Test-PersistentTaskSettings -Task $baseTask)
    $remoteTaskRunning = $null -ne $baseTask -and [string]$baseTask.State -eq "Running"

    $cfTask = Get-ScheduledTask -TaskName $cloudflaredTaskName -ErrorAction SilentlyContinue
    $cfAction = if ($null -ne $cfTask) { @($cfTask.Actions) | Select-Object -First 1 } else { $null }
    $cfPrincipalOk = $null -ne $cfTask -and ([string]$cfTask.Principal.UserId).ToUpperInvariant() -eq "NT AUTHORITY\LOCAL SERVICE" -and [string]$cfTask.Principal.RunLevel -eq "Limited"
    $cfActionOk = $null -ne $cfAction -and
        ([string]$cfAction.Arguments).IndexOf("--no-autoupdate", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ([string]$cfAction.Arguments).IndexOf("--token-file", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        ([string]$cfAction.Arguments).IndexOf($tokenPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $cfTaskPersistenceOk = (Test-BootTriggerPresent -Task $cfTask) -and (Test-PersistentTaskSettings -Task $cfTask)
    $cfTaskRunning = $null -ne $cfTask -and [string]$cfTask.State -eq "Running"

    $runnerAclDenied = (Test-PathAclExcludesSid -Path $configRoot -SidValue $runnerSid) -and (Test-PathAclExcludesSid -Path $tokenRoot -SidValue $runnerSid)
    $firewallOk = Test-RunnerLoopbackBlock -RunnerSid $runnerSid
    $loopback = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -eq "127.0.0.1" }).Count -gt 0
    $nonLoopback = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.LocalAddress -ne "127.0.0.1" }).Count -gt 0

    return [ordered]@{
        implementation_binding = [bool]$markerOk
        cloudflared_hash = [bool]$cloudflaredHashOk
        protected_config_present = [bool]$configOk
        protected_token_present = [bool](Test-Path -LiteralPath $tokenPath -PathType Leaf)
        runner_secret_acl_denied = [bool]$runnerAclDenied
        remote_web_task_definition = [bool]($basePrincipalOk -and $remoteTaskDefinitionOk)
        remote_web_task_boot_persistent = [bool]$remoteTaskPersistenceOk
        remote_web_task_running = [bool]$remoteTaskRunning
        cloudflared_task_definition = [bool]($cfPrincipalOk -and $cfActionOk)
        cloudflared_task_boot_persistent = [bool]$cfTaskPersistenceOk
        cloudflared_task_running = [bool]$cfTaskRunning
        runner_loopback_firewall = [bool]$firewallOk
        backend_loopback_listening = [bool]$loopback
        backend_non_loopback_listening = [bool]$nonLoopback
        cloudflared_version = $cloudflaredVersion
    }
}

function Test-Wp22aStatePassed {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$State)
    return $State.implementation_binding -and
        $State.cloudflared_hash -and
        $State.protected_config_present -and
        $State.protected_token_present -and
        $State.runner_secret_acl_denied -and
        $State.remote_web_task_definition -and
        $State.remote_web_task_boot_persistent -and
        $State.remote_web_task_running -and
        $State.cloudflared_task_definition -and
        $State.cloudflared_task_boot_persistent -and
        $State.cloudflared_task_running -and
        $State.runner_loopback_firewall -and
        $State.backend_loopback_listening -and
        -not $State.backend_non_loopback_listening
}

if (-not (Test-Administrator)) { throw "WP22A_ADMINISTRATOR_REQUIRED" }
$reviewedHead = Get-ReviewedHead

if ($Cleanup) {
    Remove-Wp22aLocalContour
    Restore-AcceptedLocalWeb
    $result = [ordered]@{
        gate = "WP22A_CLIENTLESS_LOCAL_CLEANUP"
        passed = $true
        reason = "WP22A_CLIENTLESS_LOCAL_CLEANUP_COMPLETE"
        local_web_restored = $true
    }
    if ($AsJson) { $result | ConvertTo-Json -Compress } else { $result }
    exit 0
}

if ($Apply) {
    $baseNormalized = $false
    try {
        Restore-AcceptedLocalWeb
        $baseNormalized = $true
        Stop-ScheduledTask -TaskName $baseTaskName -ErrorAction SilentlyContinue

        $runtimeSid = Resolve-AccountSid -AccountName $runtimeName
        $runnerSid = Get-RunnerSidValue
        $localServiceSid = "S-1-5-19"

        New-Item -ItemType Directory -Path $wp22aRoot, $configRoot, $tokenRoot, $binRoot -Force | Out-Null
        Set-ProtectedDirectoryAcl -Path $wp22aRoot -AdditionalGrants @{
            $runtimeSid = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
            $localServiceSid = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
        }
        Set-ProtectedDirectoryAcl -Path $configRoot -AdditionalGrants @{
            $runtimeSid = [System.Security.AccessControl.FileSystemRights]::Read
        }
        Set-ProtectedDirectoryAcl -Path $tokenRoot -AdditionalGrants @{
            $localServiceSid = [System.Security.AccessControl.FileSystemRights]::Read
        }
        Set-ProtectedDirectoryAcl -Path $binRoot -AdditionalGrants @{
            $localServiceSid = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
        }

        Install-CloudflaredBinary
        $ownerConfig = Read-OwnerConfiguration
        try {
            $safeConfig = [ordered]@{
                schema_version = 1
                implementation_sha = $reviewedHead
                external_host = [string]$ownerConfig.external_host
                owner_identity_sha256 = [string]$ownerConfig.owner_identity_sha256
                provider = "cloudflare"
            }
            [System.IO.File]::WriteAllText($configPath, ($safeConfig | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
            [System.IO.File]::WriteAllText($tokenPath, [string]$ownerConfig.tunnel_token, [System.Text.UTF8Encoding]::new($false))
        }
        finally { $ownerConfig.tunnel_token = $null }

        if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "WP22A_REMOTE_LAUNCHER_MISSING" }
        $remoteArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" -AppRoot `"$appRoot`" -ImplementationSha $reviewedHead -ConfigPath `"$configPath`" -Port $Port"
        $remoteAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $remoteArgs -WorkingDirectory $appRoot
        $remoteTrigger = New-ScheduledTaskTrigger -AtStartup
        $remoteSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Set-ScheduledTask -TaskName $baseTaskName -Action $remoteAction -Trigger $remoteTrigger -Settings $remoteSettings | Out-Null

        Set-RunnerLoopbackBlock -RunnerSid $runnerSid

        $cfArgs = "tunnel --no-autoupdate run --token-file `"$tokenPath`""
        $cfAction = New-ScheduledTaskAction -Execute $cloudflaredExe -Argument $cfArgs -WorkingDirectory $wp22aRoot
        $cfTrigger = New-ScheduledTaskTrigger -AtStartup
        $cfPrincipal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\LOCAL SERVICE" -LogonType ServiceAccount -RunLevel Limited
        $cfSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
        Register-ScheduledTask -TaskName $cloudflaredTaskName -Action $cfAction -Trigger $cfTrigger -Principal $cfPrincipal -Settings $cfSettings -Description "Omni-CIO V10 WP22A clientless Cloudflare Tunnel" -Force | Out-Null

        Start-ScheduledTask -TaskName $baseTaskName
        Start-ScheduledTask -TaskName $cloudflaredTaskName
        Start-Sleep -Seconds 5
        $state = Get-Wp22aState
        if (-not (Test-Wp22aStatePassed -State $state)) {
            throw "WP22A_CLIENTLESS_LOCAL_VERIFY_FAILED"
        }
        $result = [ordered]@{
            gate = "WP22A_CLIENTLESS_LOCAL_APPLY"
            passed = $true
            reason = "WP22A_CLIENTLESS_LOCAL_APPLY_COMPLETE"
            state = $state
        }
        if ($AsJson) { $result | ConvertTo-Json -Depth 4 -Compress } else { $result }
        exit 0
    }
    catch {
        $reason = $_.Exception.Message
        Remove-Wp22aLocalContour
        if ($baseNormalized) {
            try { Restore-AcceptedLocalWeb } catch { $reason = "WP22A_ROLLBACK_LOCAL_WEB_FAILED" }
        }
        $failure = [ordered]@{
            gate = "WP22A_CLIENTLESS_LOCAL_APPLY"
            passed = $false
            reason = $reason
            rollback_attempted = $true
        }
        if ($AsJson) { $failure | ConvertTo-Json -Compress } else { $failure }
        exit 1
    }
}

$state = Get-Wp22aState
$passed = Test-Wp22aStatePassed -State $state
$result = [ordered]@{
    gate = "WP22A_CLIENTLESS_LOCAL_VERIFY"
    passed = [bool]$passed
    reason = if ($passed) { "WP22A_CLIENTLESS_LOCAL_VERIFY_COMPLETE" } else { "WP22A_CLIENTLESS_LOCAL_VERIFY_FAILED" }
    state = $state
}
if ($AsJson) { $result | ConvertTo-Json -Depth 4 -Compress } else { $result }
if (-not $passed) { exit 1 }