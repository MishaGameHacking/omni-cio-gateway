[CmdletBinding()]
param()

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

if ($env:GITHUB_ACTIONS -eq "true") {
    throw "WP15_OWNER_GATE_MUST_NOT_RUN_IN_GITHUB_ACTIONS"
}

Write-Host "WP15 OWNER live gate: DEFERRED"
Write-Host "Reason: WP15_LIVE_ACCEPTANCE_DEFERRED_TO_WEB_PROVISIONING"
Write-Host "Normal broker credential provisioning now belongs to authenticated Omni-CIO Web Settings (WP17)."
Write-Host "Do not enter a T-Invest token in PowerShell for amended WP15 acceptance."
Write-Host "Block D credit remains disabled and WP18 real-data acceptance remains locked until the reviewed Web live gate passes."

throw "WP15_LIVE_ACCEPTANCE_DEFERRED_TO_WEB_PROVISIONING"
