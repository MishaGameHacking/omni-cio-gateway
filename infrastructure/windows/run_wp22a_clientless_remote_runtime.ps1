[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AppRoot,
    [Parameter(Mandatory = $true)][string]$ImplementationSha,
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($env:OS -ne "Windows_NT") { throw "WP22A remote runtime requires Windows." }
if (Test-Administrator) { throw "WP22A remote runtime must not run elevated." }

$expectedUser = Get-LocalUser -Name "omni-cio-runtime" -ErrorAction Stop
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
if ($null -eq $currentSid -or $currentSid.Value -ne $expectedUser.SID.Value) {
    throw "WP22A_REMOTE_RUNTIME_IDENTITY_INVALID"
}

$sha = $ImplementationSha.Trim().ToLowerInvariant()
if ($sha -notmatch '^[0-9a-f]{40}$') { throw "WP22A_REMOTE_IMPLEMENTATION_SHA_INVALID" }

$configFile = (Resolve-Path -LiteralPath $ConfigPath -ErrorAction Stop).Path
try {
    $config = Get-Content -LiteralPath $configFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "WP22A_REMOTE_CONFIG_INVALID"
}
$hostName = ([string]$config.external_host).Trim().ToLowerInvariant().TrimEnd('.')
if ($hostName -notmatch '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$') {
    throw "WP22A_REMOTE_EXTERNAL_HOST_INVALID"
}
if ($hostName -in @("localhost", "127.0.0.1")) {
    throw "WP22A_REMOTE_EXTERNAL_HOST_INVALID"
}
$ownerFingerprint = ([string]$config.owner_identity_sha256).Trim().ToLowerInvariant()
if ($ownerFingerprint -notmatch '^[0-9a-f]{64}$') {
    throw "WP22A_REMOTE_OWNER_FINGERPRINT_INVALID"
}
$configSha = ([string]$config.implementation_sha).Trim().ToLowerInvariant()
if ($configSha -ne $sha) { throw "WP22A_REMOTE_CONFIG_SHA_MISMATCH" }

$app = (Resolve-Path -LiteralPath $AppRoot -ErrorAction Stop).Path
$marker = Join-Path $app ".omni-cio-wp15-live-deployment"
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
    throw "WP22A_REMOTE_DEPLOYMENT_MARKER_MISSING"
}
if ((Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim().ToLowerInvariant() -ne $sha) {
    throw "WP22A_REMOTE_DEPLOYMENT_SHA_MISMATCH"
}

$runtimeRoot = Split-Path -Parent $app
$python = Join-Path $runtimeRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "WP22A_REMOTE_RUNTIME_PYTHON_MISSING"
}

# External mode must never inherit the older loopback-only OWNER acceptance modes.
$env:OMNI_V10_WEB_PRIVATE_ACCEPTANCE = "0"
$env:OMNI_V10_WP15_LIVE_ACCEPTANCE = "0"
$env:OMNI_V10_WEB_PRIVATE_REMOTE = "1"
$env:OMNI_V10_WEB_EXTERNAL_PROVIDER = "cloudflare"
$env:OMNI_V10_WEB_EXTERNAL_HOST = $hostName
$env:OMNI_V10_CLOUDFLARE_OWNER_IDENTITY_SHA256 = $ownerFingerprint
$env:PGHOST = "127.0.0.1"
$env:PGPORT = "5432"
$env:PGDATABASE = "omni_cio_v10"
$env:PGUSER = "omni_cio_runtime"
$env:PGREQUIREAUTH = "sspi"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# cloudflared reaches this process only through loopback. Do not let forwarded
# client-address headers rewrite the ASGI peer used by the application trust gate.
Set-Location -LiteralPath $app
& $python -m uvicorn apps.api.wp22a_remote:create_private_remote_app --factory --host 127.0.0.1 --port $Port --log-level warning --no-access-log --no-proxy-headers
exit $LASTEXITCODE
