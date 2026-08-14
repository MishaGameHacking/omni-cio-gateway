[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AppRoot,
    [Parameter(Mandatory = $true)][string]$ImplementationSha,
    [string]$ConfigPath = "C:\ProgramData\OmniCIO\wp22a\private-remote.json",
    [ValidateRange(1024, 65535)][int]$Port = 8765
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ($env:OS -ne "Windows_NT") { throw "WP22A private remote runtime requires Windows." }
if (Test-Administrator) { throw "WP22A private remote runtime must not run elevated." }

$expectedUser = Get-LocalUser -Name "omni-cio-runtime" -ErrorAction Stop
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
if ($null -eq $currentSid -or $currentSid.Value -ne $expectedUser.SID.Value) {
    throw "WP22A_RUNTIME_IDENTITY_INVALID"
}

$sha = $ImplementationSha.Trim().ToLowerInvariant()
if ($sha -notmatch '^[0-9a-f]{40}$') { throw "WP22A_IMPLEMENTATION_SHA_INVALID" }
$app = (Resolve-Path -LiteralPath $AppRoot -ErrorAction Stop).Path
$marker = Join-Path $app ".omni-cio-wp22a-private-remote-deployment"
if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "WP22A_DEPLOYMENT_MARKER_MISSING" }
if ((Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim().ToLowerInvariant() -ne $sha) {
    throw "WP22A_DEPLOYMENT_SHA_MISMATCH"
}

$runtimeRoot = Split-Path -Parent $app
$python = Join-Path $runtimeRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "WP22A_RUNTIME_PYTHON_MISSING" }
if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw "WP22A_PRIVATE_REMOTE_CONFIG_MISSING" }
$config = Get-Content -LiteralPath $ConfigPath -Raw -ErrorAction Stop | ConvertFrom-Json
$hostName = ([string]$config.host).Trim().ToLowerInvariant().TrimEnd('.')
$ownerFingerprint = ([string]$config.owner_login_sha256).Trim().ToLowerInvariant()
if ($hostName -notmatch '^[a-z0-9][a-z0-9.-]*\.ts\.net$' -or $hostName.Contains('..')) {
    throw "WP22A_PRIVATE_REMOTE_HOST_INVALID"
}
if ($ownerFingerprint -notmatch '^[0-9a-f]{64}$') { throw "WP22A_OWNER_LOGIN_FINGERPRINT_INVALID" }

$env:OMNI_V10_WEB_PRIVATE_ACCEPTANCE = "0"
$env:OMNI_V10_WP15_LIVE_ACCEPTANCE = "0"
$env:OMNI_V10_WP22A_PUBLIC_INGRESS = "0"
$env:PUBLIC_MULTI_USER_ENABLED = "0"
$env:REAL_TRADING_ENABLED = "0"
$env:OMNI_V10_TAILSCALE_HOST = $hostName
$env:OMNI_V10_TAILSCALE_OWNER_LOGIN_SHA256 = $ownerFingerprint
$env:OMNI_V10_IMPLEMENTATION_SHA = $sha
$env:PGHOST = "127.0.0.1"
$env:PGPORT = "5432"
$env:PGDATABASE = "omni_cio_v10"
$env:PGUSER = "omni_cio_runtime"
$env:PGREQUIREAUTH = "sspi"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Set-Location -LiteralPath $app
& $python -m uvicorn apps.api.private_remote:create_private_remote_app --factory --host 127.0.0.1 --port $Port --log-level warning --no-access-log
exit $LASTEXITCODE
