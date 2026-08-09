[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("core_api", "web", "telegram", "watchtower", "ai_worker")]
    [string]$ComponentId
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

Write-Output ("WP9 component slot '{0}' is sealed until its owning V10 work package." -f $ComponentId)
exit 23
