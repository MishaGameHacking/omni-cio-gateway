Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -ne 5) {
    throw "WP10_CONTINUITY_WINDOWS_POWERSHELL_51_REQUIRED"
}

$Files = @(
    "infrastructure\windows\rehearse_wp10_recovery.ps1",
    "infrastructure\windows\prepare_wp10_offdevice_target.ps1",
    "infrastructure\windows\audit_wp10_offdevice_target.ps1",
    "infrastructure\windows\complete_wp10_owner_offdevice_gate.ps1",
    "infrastructure\windows\run_wp10_owner_rehearsal.ps1"
)

foreach ($File in $Files) {
    $Resolved = Resolve-Path -LiteralPath $File -ErrorAction Stop
    $Tokens = $null
    $Errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $Resolved.Path,
        [ref]$Tokens,
        [ref]$Errors
    )
    if ($Errors.Count -gt 0) {
        $Errors | ForEach-Object { Write-Error $_.Message }
        throw "WP10_CONTINUITY_POWERSHELL_PARSE_FAILED:$File"
    }
}

Write-Host "WP10_CONTINUITY_POWERSHELL51_PARSE=PASS"
