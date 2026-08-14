[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$Verify,
    [switch]$SelfTestStatusParser,
    [string]$OwnerLogin,
    [ValidateRange(1024, 65535)][int]$BackendPort = 8765,
    [string]$ConfigPath = "C:\ProgramData\OmniCIO\wp22a\private-remote.json",
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$modeCount = 0
foreach ($mode in @($Apply, $Verify, $SelfTestStatusParser)) {
    if ($mode) { $modeCount++ }
}
if ($modeCount -ne 1) { throw "Choose exactly one of -Apply, -Verify, or -SelfTestStatusParser." }

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
        $digest = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($digest)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Resolve-IdentitySid {
    param(
        [Parameter(Mandatory = $true)]
        [System.Security.Principal.IdentityReference]$IdentityReference
    )
    if ($IdentityReference -is [System.Security.Principal.SecurityIdentifier]) {
        return [System.Security.Principal.SecurityIdentifier]$IdentityReference
    }
    try {
        return $IdentityReference.Translate([System.Security.Principal.SecurityIdentifier])
    }
    catch [System.Security.Principal.IdentityNotMappedException] {
        return $null
    }
}

function New-Rule {
    param(
        [Parameter(Mandatory = $true)][System.Security.Principal.SecurityIdentifier]$Sid,
        [Parameter(Mandatory = $true)][System.Security.AccessControl.FileSystemRights]$Rights,
        [System.Security.AccessControl.InheritanceFlags]$Inheritance = [System.Security.AccessControl.InheritanceFlags]::None
    )
    return [System.Security.AccessControl.FileSystemAccessRule]::new(
        $Sid,
        $Rights,
        $Inheritance,
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
}

function Set-PrivateConfigAcl {
    param([Parameter(Mandatory = $true)][string]$Root)
    $runtime = Get-LocalUser -Name "omni-cio-runtime" -ErrorAction Stop
    $runtimeSid = $runtime.SID
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $adminsSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
    $inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Rule -Sid $systemSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $adminsSid -Rights ([System.Security.AccessControl.FileSystemRights]::FullControl) -Inheritance $inherit))
    $acl.AddAccessRule((New-Rule -Sid $runtimeSid -Rights ([System.Security.AccessControl.FileSystemRights]::ReadAndExecute) -Inheritance $inherit))
    Set-Acl -LiteralPath $Root -AclObject $acl -ErrorAction Stop
}

function Test-PrivateConfigAcl {
    param([Parameter(Mandatory = $true)][string]$Root)
    $runtimeSid = (Get-LocalUser -Name "omni-cio-runtime" -ErrorAction Stop).SID
    $allowedSidValues = @(
        "S-1-5-18",
        "S-1-5-32-544",
        $runtimeSid.Value
    )
    $acl = Get-Acl -LiteralPath $Root -ErrorAction Stop
    if (-not $acl.AreAccessRulesProtected) { return $false }

    $runtimeReadExecute = $false
    foreach ($rule in @($acl.Access)) {
        if ($rule.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) {
            continue
        }
        $sid = Resolve-IdentitySid -IdentityReference $rule.IdentityReference
        if ($null -eq $sid -or $allowedSidValues -notcontains $sid.Value) {
            return $false
        }
        if ($sid.Value -eq $runtimeSid.Value) {
            $rights = $rule.FileSystemRights
            $readExecute = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute
            if (($rights -band $readExecute) -eq $readExecute) {
                $runtimeReadExecute = $true
            }
            $forbidden = (
                [System.Security.AccessControl.FileSystemRights]::Write -bor
                [System.Security.AccessControl.FileSystemRights]::Delete -bor
                [System.Security.AccessControl.FileSystemRights]::ChangePermissions -bor
                [System.Security.AccessControl.FileSystemRights]::TakeOwnership
            )
            if (($rights -band $forbidden) -ne 0) { return $false }
        }
    }
    return $runtimeReadExecute
}

function Test-EmptyTailscaleStatusJson {
    param([Parameter(Mandatory = $true)][string]$Text)
    $compact = ($Text -replace '\s', '')
    return @('', '{}', '[]', 'null') -contains $compact
}

function Convert-TailscaleServeStatusJson {
    param([Parameter(Mandatory = $true)][string]$Text)
    if (Test-EmptyTailscaleStatusJson -Text $Text) { return $null }
    try {
        return $Text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        throw "WP22A_TAILSCALE_SERVE_STATUS_INVALID"
    }
}

function Test-Wp22aServeMapping {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port
    )
    $state = Convert-TailscaleServeStatusJson -Text $Text
    if ($null -eq $state) { return $false }

    $tcp = $state.PSObject.Properties['TCP']
    if ($null -eq $tcp -or $null -eq $tcp.Value) { return $false }
    $https443 = $tcp.Value.PSObject.Properties['443']
    if ($null -eq $https443) { return $false }
    $httpsProperty = $https443.Value.PSObject.Properties['HTTPS']
    if ($null -eq $httpsProperty -or -not [bool]$httpsProperty.Value) { return $false }
    $httpProperty = $https443.Value.PSObject.Properties['HTTP']
    if ($null -ne $httpProperty -and [bool]$httpProperty.Value) { return $false }
    $forwardProperty = $https443.Value.PSObject.Properties['TCPForward']
    if ($null -ne $forwardProperty -and -not [string]::IsNullOrWhiteSpace([string]$forwardProperty.Value)) {
        return $false
    }

    $web = $state.PSObject.Properties['Web']
    if ($null -eq $web -or $null -eq $web.Value) { return $false }
    $hostPort = $HostName + ':443'
    $site = $web.Value.PSObject.Properties[$hostPort]
    if ($null -eq $site) { return $false }
    $handlersProperty = $site.Value.PSObject.Properties['Handlers']
    if ($null -eq $handlersProperty -or $null -eq $handlersProperty.Value) { return $false }
    $handlers = @($handlersProperty.Value.PSObject.Properties)
    if ($handlers.Count -ne 1) { return $false }
    $root = $handlersProperty.Value.PSObject.Properties['/']
    if ($null -eq $root) { return $false }
    $proxyProperty = $root.Value.PSObject.Properties['Proxy']
    if ($null -eq $proxyProperty) { return $false }
    return [string]$proxyProperty.Value -ceq "http://127.0.0.1:$Port"
}

if ($SelfTestStatusParser) {
    $testHost = 'omni-owner.synthetic-tailnet.ts.net'
    $valid = @'
{"TCP":{"443":{"HTTPS":true}},"Web":{"omni-owner.synthetic-tailnet.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8765"}}}}}
'@
    $wrongTarget = @'
{"TCP":{"443":{"HTTPS":true}},"Web":{"omni-owner.synthetic-tailnet.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:9999"}}}}}
'@
    $wrongPort = @'
{"TCP":{"8443":{"HTTPS":true}},"Web":{"omni-owner.synthetic-tailnet.ts.net:8443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8765"}}}}}
'@
    $extraHandler = @'
{"TCP":{"443":{"HTTPS":true}},"Web":{"omni-owner.synthetic-tailnet.ts.net:443":{"Handlers":{"/":{"Proxy":"http://127.0.0.1:8765"},"/other":{"Proxy":"http://127.0.0.1:9999"}}}}}
'@
    $ready = (
        (Test-Wp22aServeMapping -Text $valid -HostName $testHost -Port 8765) -and
        -not (Test-Wp22aServeMapping -Text $wrongTarget -HostName $testHost -Port 8765) -and
        -not (Test-Wp22aServeMapping -Text $wrongPort -HostName $testHost -Port 8765) -and
        -not (Test-Wp22aServeMapping -Text $extraHandler -HostName $testHost -Port 8765) -and
        -not (Test-Wp22aServeMapping -Text '{}' -HostName $testHost -Port 8765)
    )
    $result = [ordered]@{
        schema_version = "1"
        work_package = "WP22A"
        evidence_type = "TAILSCALE_SERVE_STATUS_PARSER_SELF_TEST"
        exact_https_443_mapping_accepted = [bool](Test-Wp22aServeMapping -Text $valid -HostName $testHost -Port 8765)
        wrong_target_rejected = [bool](-not (Test-Wp22aServeMapping -Text $wrongTarget -HostName $testHost -Port 8765))
        wrong_port_rejected = [bool](-not (Test-Wp22aServeMapping -Text $wrongPort -HostName $testHost -Port 8765))
        extra_handler_rejected = [bool](-not (Test-Wp22aServeMapping -Text $extraHandler -HostName $testHost -Port 8765))
        empty_status_rejected = [bool](-not (Test-Wp22aServeMapping -Text '{}' -HostName $testHost -Port 8765))
        mutation_performed = $false
        ready = [bool]$ready
    }
    if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
    if (-not $ready) { exit 42 }
    exit 0
}

if ($env:OS -ne "Windows_NT") { throw "WP22A Tailscale configuration requires Windows." }
if (-not (Test-Administrator)) { throw "WP22A Tailscale apply/verify requires OWNER administrator." }
$tailscaleCommand = Get-Command tailscale.exe -ErrorAction Stop
$tailscale = $tailscaleCommand.Source
$statusRaw = (& $tailscale status --json 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_STATUS_FAILED" }
$status = $statusRaw | ConvertFrom-Json
if ([string]$status.BackendState -ne "Running") { throw "WP22A_TAILSCALE_NOT_RUNNING" }
$hostName = ([string]$status.Self.DNSName).Trim().ToLowerInvariant().TrimEnd('.')
if ($hostName -notmatch '^[a-z0-9][a-z0-9.-]*\.ts\.net$' -or $hostName.Contains('..')) {
    throw "WP22A_TAILSCALE_DNS_NAME_INVALID"
}

$configRoot = Split-Path -Parent $ConfigPath
if ($Apply) {
    $existingServeRaw = (& $tailscale serve status --json 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_SERVE_STATUS_FAILED" }
    if (
        -not (Test-EmptyTailscaleStatusJson -Text $existingServeRaw) -and
        -not (Test-Wp22aServeMapping -Text $existingServeRaw -HostName $hostName -Port $BackendPort)
    ) {
        throw "WP22A_REFUSES_EXISTING_SERVE_CONFIGURATION"
    }
    $existingFunnelRaw = (& $tailscale funnel status --json 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_FUNNEL_STATUS_FAILED" }
    if (-not (Test-EmptyTailscaleStatusJson -Text $existingFunnelRaw)) {
        throw "WP22A_REFUSES_EXISTING_FUNNEL_CONFIGURATION"
    }

    $normalizedLogin = $OwnerLogin.Trim()
    if ([string]::IsNullOrWhiteSpace($normalizedLogin)) {
        $normalizedLogin = (Read-Host "Exact decoded Tailscale OWNER login; the raw value will only be hashed locally").Trim()
    }
    if ([string]::IsNullOrWhiteSpace($normalizedLogin) -or $normalizedLogin.Length -gt 320) {
        throw "WP22A_OWNER_LOGIN_INVALID"
    }
    $ownerFingerprint = Get-Sha256Hex -Value $normalizedLogin

    if (-not (Test-Path -LiteralPath $configRoot -PathType Container)) {
        New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
    }
    Set-PrivateConfigAcl -Root $configRoot
    $config = [ordered]@{
        schema_version = "1"
        transport = "TAILSCALE_SERVE_PRIVATE"
        host = $hostName
        owner_login_sha256 = $ownerFingerprint
        backend_host = "127.0.0.1"
        backend_port = $BackendPort
        public_ingress = $false
        tailscale_funnel_allowed = $false
        public_multi_user_enabled = $false
        real_trading_enabled = $false
    }
    $config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8

    & $tailscale funnel --https=443 off 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "WP22A_FUNNEL_DISABLE_FAILED" }
    & $tailscale serve --bg --https=443 "http://127.0.0.1:$BackendPort" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_SERVE_APPLY_FAILED" }
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "WP22A_PRIVATE_REMOTE_CONFIG_MISSING" }
$configCurrent = Get-Content -LiteralPath $ConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json
$configHost = ([string]$configCurrent.host).Trim().ToLowerInvariant().TrimEnd('.')
$ownerHash = ([string]$configCurrent.owner_login_sha256).Trim().ToLowerInvariant()
$configOk = (
    [string]$configCurrent.transport -eq "TAILSCALE_SERVE_PRIVATE" -and
    $configHost -eq $hostName -and
    $ownerHash -match '^[0-9a-f]{64}$' -and
    [string]$configCurrent.backend_host -eq "127.0.0.1" -and
    [int]$configCurrent.backend_port -eq $BackendPort -and
    -not [bool]$configCurrent.public_ingress -and
    -not [bool]$configCurrent.tailscale_funnel_allowed -and
    -not [bool]$configCurrent.public_multi_user_enabled -and
    -not [bool]$configCurrent.real_trading_enabled
)
$aclOk = Test-PrivateConfigAcl -Root $configRoot
$serveRaw = (& $tailscale serve status --json 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_SERVE_STATUS_FAILED" }
$serveOk = Test-Wp22aServeMapping -Text $serveRaw -HostName $hostName -Port $BackendPort
$funnelRaw = (& $tailscale funnel status --json 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0) { throw "WP22A_TAILSCALE_FUNNEL_STATUS_FAILED" }
$funnelDisabled = Test-EmptyTailscaleStatusJson -Text $funnelRaw

$ready = $configOk -and $aclOk -and $serveOk -and $funnelDisabled
$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    transport = "TAILSCALE_SERVE_PRIVATE"
    host_sha256 = Get-Sha256Hex -Value $hostName
    backend_loopback_only = ([string]$configCurrent.backend_host -eq "127.0.0.1")
    serve_configured = [bool]$serveOk
    funnel_disabled = [bool]$funnelDisabled
    private_config_acl_ok = [bool]$aclOk
    owner_identity_fingerprint_present = [bool]($ownerHash -match '^[0-9a-f]{64}$')
    public_ingress = $false
    public_multi_user_enabled = $false
    broker_write_authority_added = $false
    trading_methods = $false
    real_trading_enabled = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (-not $ready) { exit 41 }
