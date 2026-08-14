[CmdletBinding()]
param([switch]$AsJson)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$provisioner = Join-Path $PSScriptRoot "provision_wp22a_private_remote_runtime.ps1"
if (-not (Test-Path -LiteralPath $provisioner -PathType Leaf)) {
    throw "WP22A_RUNTIME_HELPER_PROVISIONER_MISSING"
}
$text = Get-Content -LiteralPath $provisioner -Raw -ErrorAction Stop
$pattern = "(?s)Add-Type\s+-TypeDefinition\s+@'\r?\n(?<code>.*?)\r?\n'@"
$match = [regex]::Match($text, $pattern)
if (-not $match.Success) { throw "WP22A_RUNTIME_HELPER_SOURCE_NOT_FOUND" }
$code = $match.Groups["code"].Value
if ([string]::IsNullOrWhiteSpace($code)) { throw "WP22A_RUNTIME_HELPER_SOURCE_EMPTY" }

Add-Type -TypeDefinition $code -ErrorAction Stop
$compiled = $null -ne ("OmniCioV10.Wp22aAccountRights" -as [type])
if (-not $compiled) { throw "WP22A_RUNTIME_HELPER_COMPILE_FAILED" }

$result = [ordered]@{
    schema_version = "1"
    work_package = "WP22A"
    evidence_type = "RUNTIME_ACCOUNT_RIGHTS_HELPER_VALIDATION"
    helper_compiled = $true
    mutation_performed = $false
    real_secret_values_used = $false
    broker_write_authority_added = $false
    trading_methods = $false
    real_trading_enabled = $false
    gateway_entrypoint = "app:app"
    ready = $true
}

if ($AsJson) { $result | ConvertTo-Json -Depth 4 } else { $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } }
