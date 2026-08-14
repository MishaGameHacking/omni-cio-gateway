[CmdletBinding()]
param(
    [string]$EvidencePath = "C:\ProgramData\OmniCIO\wp22a-evidence\owner-private-remote.sanitized.local.json",
    [string]$ConfigPath = "C:\ProgramData\OmniCIO\wp22a\private-remote.json",
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") { throw "WP22A runner isolation probe requires Windows." }

function Test-Administrator {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-FileReadAllowed {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
        try { [void]$stream.ReadByte() } finally { $stream.Dispose() }
        return $true
    }
    catch [System.UnauthorizedAccessException] { return $false }
    catch [System.IO.IOException] { return $false }
}

function Test-DirectoryWriteAllowed {
    param([Parameter(Mandatory = $true)][string]$Directory)
    $probe = Join-Path $Directory (".omni-cio-runner-write-probe-" + [guid]::NewGuid().ToString("N") + ".tmp")
    try {
        [System.IO.File]::WriteAllText($probe, "synthetic-non-secret-probe", [System.Text.UTF8Encoding]::new($false))
        return $true
    }
    catch [System.UnauthorizedAccessException] { return $false }
    catch [System.IO.IOException] { return $false }
    finally { Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }
}

$evidencePresent = Test-Path -LiteralPath $EvidencePath -PathType Leaf
$configPresent = Test-Path -LiteralPath $ConfigPath -PathType Leaf
$evidenceRoot = Split-Path -Parent $EvidencePath
$configRoot = Split-Path -Parent $ConfigPath
$runnerAdmin = Test-Administrator
$evidenceRead = $false
$evidenceWrite = $true
$configRead = $true
$configWrite = $true

if ($evidencePresent) {
    $evidenceRead = Test-FileReadAllowed -Path $EvidencePath
    $evidenceWrite = Test-DirectoryWriteAllowed -Directory $evidenceRoot
}
if ($configPresent) {
    $configRead = Test-FileReadAllowed -Path $ConfigPath
    $configWrite = Test-DirectoryWriteAllowed -Directory $configRoot
}

$ready = $evidencePresent -and $configPresent -and (-not $runnerAdmin) -and $evidenceRead -and (-not $evidenceWrite) -and (-not $configRead) -and (-not $configWrite)
$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_type = "RUNNER_PRIVATE_REMOTE_ISOLATION"
    runner_is_administrator = [bool]$runnerAdmin
    sanitized_evidence_present = [bool]$evidencePresent
    runner_evidence_read_allowed = [bool]$evidenceRead
    runner_evidence_write_allowed = [bool]$evidenceWrite
    private_config_present = [bool]$configPresent
    runner_private_config_read_allowed = [bool]$configRead
    runner_private_config_write_allowed = [bool]$configWrite
    real_secret_values_used = $false
    raw_owner_identity_recorded = $false
    raw_tailnet_hostname_recorded = $false
    broker_write_authority_added = $false
    trading_methods = $false
    real_trading_enabled = $false
    gateway_entrypoint = "app:app"
    ready = [bool]$ready
}

if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
if (-not $ready) { exit 81 }
