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
$targets = @(
    "scripts\check_v10_tbank_ca_trust.ps1",
    "infrastructure\windows\provision_v10_tbank_ca_trust.ps1"
)

$failures = @()
foreach ($relativePath in $targets) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        $failures += [pscustomobject]@{
            path = $relativePath
            reason = "MISSING_SOURCE"
            message = "required PowerShell source is missing"
        }
        continue
    }

    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $fullPath,
        [ref]$tokens,
        [ref]$parseErrors
    )

    foreach ($parseError in @($parseErrors)) {
        $failures += [pscustomobject]@{
            path = $relativePath
            reason = "PARSE_ERROR"
            message = [string]$parseError.Message
        }
    }
}

$ready = $failures.Count -eq 0
$reason = if ($ready) {
    "TBANK_CA_TRUST_POWERSHELL_SYNTAX_READY"
}
else {
    "TBANK_CA_TRUST_POWERSHELL_SYNTAX_INVALID"
}

$result = [ordered]@{
    schema_version = "1"
    reason = $reason
    checked_files = $targets
    failure_count = [int]$failures.Count
    failures = $failures
    ready = [bool]$ready
}

if ($AsJson) {
    $result | ConvertTo-Json -Depth 6
}
else {
    $result.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value }
}

if (-not $ready) {
    exit 31
}
