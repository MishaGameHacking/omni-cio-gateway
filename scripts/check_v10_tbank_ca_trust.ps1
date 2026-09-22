[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:OS -ne "Windows_NT") {
    throw "TBANK_CA_TRUST_WINDOWS_REQUIRED"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_TBANK_CA_TRUST_CONTRACT.json"
$provisionerPath = Join-Path $repoRoot "infrastructure\windows\provision_v10_tbank_ca_trust.ps1"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop

$verifyOutput = @(
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $provisionerPath -Verify -AsJson 2>$null
)
$verifyExit = $LASTEXITCODE
$verifyText = ($verifyOutput -join [Environment]::NewLine).Trim()
$verify = $null
try {
    if (-not [string]::IsNullOrWhiteSpace($verifyText)) {
        $verify = $verifyText | ConvertFrom-Json -ErrorAction Stop
    }
}
catch {
    $verify = $null
}

$storeReady = (
    $verifyExit -eq 0 -and
    $null -ne $verify -and
    [bool]$verify.ready -and
    [bool]$verify.root_ca_present -and
    [bool]$verify.intermediate_ca_present
)

$indexReady = $false
if ($storeReady) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        $previousNoInput = $env:PIP_NO_INPUT
        try {
            $env:PIP_NO_INPUT = "1"
            & $python.Source -m pip --disable-pip-version-check index versions t-tech-investments --index-url ([string]$contract.package_index) --retries 0 --timeout 10 *> $null
            $indexReady = $LASTEXITCODE -eq 0
        }
        finally {
            if ($null -eq $previousNoInput) {
                Remove-Item Env:PIP_NO_INPUT -ErrorAction SilentlyContinue
            }
            else {
                $env:PIP_NO_INPUT = $previousNoInput
            }
        }
    }
}

$ready = $storeReady -and $indexReady
$reason = if (-not $storeReady) {
    "TBANK_CA_TRUST_STORE_NOT_READY"
}
elseif (-not $indexReady) {
    "TBANK_PACKAGE_INDEX_TLS_NOT_READY"
}
else {
    "TBANK_PACKAGE_INDEX_TLS_READY"
}

$result = [ordered]@{
    schema_version = "1"
    reason = $reason
    trust_store_ready = [bool]$storeReady
    package_index_tls_ready = [bool]$indexReady
    mutations_attempted = $false
    ready = [bool]$ready
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 4
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if (-not $ready) {
    exit 72
}
