[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP9_SUPERVISION_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1" -or [string]$contract.work_package -ne "WP9") {
    throw "Unsupported WP9 supervision contract."
}

$wp9Root = [string]$contract.paths.wp9_root
$taskPath = [string]$contract.task_folder
$ownershipMarker = "OMNI-CIO-V10-WP9-OWNED-v1"
$ownershipMarkerName = ".omni-cio-wp9-owned"
$taskDescription = "OMNI-CIO-V10-WP9-OWNED-v1"
$ownedTaskNames = @(
    [string]$contract.tasks.health_supervisor,
    [string]$contract.tasks.core_api,
    [string]$contract.tasks.web,
    [string]$contract.tasks.telegram,
    [string]$contract.tasks.watchtower,
    [string]$contract.tasks.ai_worker
)

function Test-Administrator {
    if ($env:OS -ne "Windows_NT") { return $false }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-OwnedRoot {
    if (-not (Test-Path -LiteralPath $wp9Root -PathType Container)) { return $false }
    $marker = Join-Path $wp9Root $ownershipMarkerName
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { return $false }
    try {
        return (Get-Content -LiteralPath $marker -Raw -ErrorAction Stop).Trim() -eq $ownershipMarker
    }
    catch { return $false }
}

function Get-TaskInventory {
    $items = @()
    if ($env:OS -ne "Windows_NT") { return $items }
    foreach ($name in $ownedTaskNames) {
        $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $name -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            $items += [ordered]@{ id = $name; present = $false; owned = $false }
            continue
        }
        $items += [ordered]@{
            id = $name
            present = $true
            owned = ([string]$task.Description -eq $taskDescription)
        }
    }
    return $items
}

$inventory = @(Get-TaskInventory)
$unowned = @($inventory | Where-Object { $_.present -eq $true -and $_.owned -ne $true })
$rootPresent = Test-Path -LiteralPath $wp9Root
$rootOwned = Test-OwnedRoot
$reasons = @()
if ($unowned.Count -gt 0) { $reasons += "UNOWNED_TASK_COLLISION" }
if ($rootPresent -and -not $rootOwned) { $reasons += "UNOWNED_ROOT_COLLISION" }

if (-not $Apply) {
    $profile = [ordered]@{
        schema_version = "1"
        mode = "PREVIEW"
        status = if ($reasons.Count -eq 0) { "PASS" } else { "REFUSED" }
        reasons = $reasons
        root_present = [bool]$rootPresent
        root_owned = [bool]$rootOwned
        owned_tasks_present = @($inventory | Where-Object { $_.present -eq $true -and $_.owned -eq $true }).Count
        would_preserve_postgresql = $true
        would_preserve_runner = $true
        would_preserve_wp6_wp7_wp8 = $true
        real_secret_values_used = $false
    }
    if ($AsJson) { $profile | ConvertTo-Json -Depth 6 -Compress }
    else {
        Write-Output ("WP9 rollback preview status: {0}" -f $profile.status)
        Write-Output ("WP9 owned tasks present: {0}" -f $profile.owned_tasks_present)
        Write-Output "PostgreSQL/runner/WP6/WP7/WP8 preserved: True"
    }
    if ($profile.status -eq "REFUSED") { exit 1 }
    exit 0
}

if ($env:OS -ne "Windows_NT" -or -not (Test-Administrator)) {
    throw "WP9_ROLLBACK_APPLY_REQUIRES_OWNER_ADMINISTRATOR"
}
if ($reasons.Count -gt 0) {
    throw ("WP9_ROLLBACK_REFUSED:{0}" -f ($reasons -join ","))
}

$removedTasks = 0
foreach ($item in $inventory) {
    if ($item.present -eq $true -and $item.owned -eq $true) {
        Unregister-ScheduledTask -TaskPath $taskPath -TaskName ([string]$item.id) -Confirm:$false
        $removedTasks += 1
    }
}

if ($rootPresent -and $rootOwned) {
    Remove-Item -LiteralPath $wp9Root -Recurse -Force
}

$profile = [ordered]@{
    schema_version = "1"
    mode = "APPLY"
    status = "PASS"
    removed_tasks = $removedTasks
    removed_owned_root = [bool]($rootPresent -and $rootOwned)
    postgresql_preserved = $true
    runner_preserved = $true
    wp6_wp7_wp8_preserved = $true
    real_secret_values_used = $false
    real_money_authority_changed = $false
}
if ($AsJson) { $profile | ConvertTo-Json -Depth 5 -Compress }
else {
    Write-Output "WP9 rollback status: PASS"
    Write-Output ("WP9 owned tasks removed: {0}" -f $removedTasks)
    Write-Output "PostgreSQL/runner/WP6/WP7/WP8 preserved: True"
    Write-Output "Real secret values used: NO"
}
exit 0
