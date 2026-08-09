[CmdletBinding()]
param([switch]$AsJson)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $repoRoot "docs\architecture\V10_WP9_SUPERVISION_CONTRACT.json"
$wp7ContractPath = Join-Path $repoRoot "docs\architecture\V10_WP7_BOOTSTRAP_CONTRACT.json"
$wp8ContractPath = Join-Path $repoRoot "docs\architecture\V10_WP8_SECRET_STORE_CONTRACT.json"
$contract = Get-Content -LiteralPath $contractPath -Raw -ErrorAction Stop | ConvertFrom-Json
$wp7 = Get-Content -LiteralPath $wp7ContractPath -Raw -ErrorAction Stop | ConvertFrom-Json
$wp8 = Get-Content -LiteralPath $wp8ContractPath -Raw -ErrorAction Stop | ConvertFrom-Json

$taskPath = [string]$contract.task_folder
$localServiceSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-19")
$reasons = @()

function Get-BootTimeUtc {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        return ([datetime]$os.LastBootUpTime).ToUniversalTime()
    }
    catch { return $null }
}

function Convert-PrincipalToSid {
    param([string]$UserId)
    try {
        if ($UserId -match '^S-1-') {
            return [System.Security.Principal.SecurityIdentifier]::new($UserId)
        }
        return ([System.Security.Principal.NTAccount]::new($UserId)).Translate(
            [System.Security.Principal.SecurityIdentifier]
        )
    }
    catch { return $null }
}

function Get-TaskSummary {
    param(
        [string]$TaskName,
        [bool]$ExpectedEnabled
    )
    try {
        $task = Get-ScheduledTask -TaskPath $taskPath -TaskName $TaskName -ErrorAction Stop
        $sid = Convert-PrincipalToSid -UserId ([string]$task.Principal.UserId)
        $localService = ($null -ne $sid -and $sid.Value -eq $localServiceSid.Value)
        $enabled = [bool]$task.Settings.Enabled
        $boundedRestart = (
            [int]$task.Settings.RestartCount -eq [int]$contract.supervision.component_restart_count -and
            [int]$task.Settings.RestartCount -gt 0
        )
        return [ordered]@{
            present = $true
            enabled = $enabled
            expected_enabled = $ExpectedEnabled
            principal_is_local_service = $localService
            bounded_restart = $boundedRestart
            valid = (
                $enabled -eq $ExpectedEnabled -and
                $localService -and
                $boundedRestart -and
                [string]$task.Description -eq "OMNI-CIO-V10-WP9-OWNED-v1"
            )
        }
    }
    catch {
        return [ordered]@{
            present = $false
            enabled = $null
            expected_enabled = $ExpectedEnabled
            principal_is_local_service = $false
            bounded_restart = $false
            valid = $false
        }
    }
}

function Get-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    }
    catch { return $null }
}

function Test-LocalServiceReadDataGrant {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
        $rules = @(
            $acl.GetAccessRules(
                $true,
                $true,
                [System.Security.Principal.SecurityIdentifier]
            ) | Where-Object { $_.IdentityReference.Value -eq $localServiceSid.Value }
        )
        return [bool](
            $rules | Where-Object {
                $_.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
                ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -ne 0
            }
        )
    }
    catch { return $true }
}

function Get-LocalRoleSummary {
    param([string]$Name)
    try {
        $role = Get-LocalUser -Name $Name -ErrorAction Stop
        $adminSid = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")
        $adminGroup = Get-LocalGroup -SID $adminSid -ErrorAction Stop
        $members = @(Get-LocalGroupMember -Group $adminGroup -ErrorAction Stop)
        $isAdmin = [bool]($members | Where-Object { $_.SID.Value -eq $role.SID.Value })
        return [ordered]@{
            present = $true
            enabled = [bool]$role.Enabled
            administrator = $isAdmin
        }
    }
    catch {
        return [ordered]@{ present = $false; enabled = $null; administrator = $null }
    }
}

$runnerProcess = (
    [string]$env:GITHUB_ACTIONS -eq "true" -and
    [string]$env:RUNNER_NAME -eq [string]$wp7.runner.expected_name
)
if (-not $runnerProcess) { $reasons += "RUNNER_PROCESS_NOT_PROVEN" }

$healthTask = Get-TaskSummary -TaskName ([string]$contract.tasks.health_supervisor) -ExpectedEnabled $true
if (-not $healthTask.valid) { $reasons += "HEALTH_SUPERVISOR_TASK_INVALID" }

$slotSummaries = @()
foreach ($id in @("core_api", "web", "telegram", "watchtower", "ai_worker")) {
    $summary = Get-TaskSummary -TaskName ([string]$contract.tasks.$id) -ExpectedEnabled $false
    if (-not $summary.valid) { $reasons += "SEALED_TASK_INVALID:$id" }
    $slotSummaries += [ordered]@{ id = $id; task = $summary }
}

$executionTaskPresent = $false
try {
    $executionTaskPresent = $null -ne (Get-ScheduledTask `
        -TaskPath $taskPath `
        -TaskName "OmniCIO.V10.Execution" `
        -ErrorAction SilentlyContinue)
}
catch { $executionTaskPresent = $true }
if ($executionTaskPresent) { $reasons += "EXECUTION_TASK_PRESENT" }

$runtimeRole = Get-LocalRoleSummary -Name "omni-cio-runtime"
$executionRole = Get-LocalRoleSummary -Name "omni-cio-execution"
if (-not $runtimeRole.present -or $runtimeRole.enabled -ne $false -or $runtimeRole.administrator -ne $false) {
    $reasons += "RUNTIME_ROLE_BOUNDARY_INVALID"
}
if (-not $executionRole.present -or $executionRole.enabled -ne $false -or $executionRole.administrator -ne $false) {
    $reasons += "EXECUTION_ROLE_BOUNDARY_INVALID"
}

$localServiceWp8Read = $false
foreach ($class in @($wp8.secret_classes)) {
    $directory = [string]$class.directory
    $sentinel = Join-Path $directory ([string]$class.sentinel_blob)
    if (Test-LocalServiceReadDataGrant -Path $directory) { $localServiceWp8Read = $true }
    if (Test-LocalServiceReadDataGrant -Path $sentinel) { $localServiceWp8Read = $true }
}
if ($localServiceWp8Read) { $reasons += "LOCAL_SERVICE_WP8_PAYLOAD_GRANT_PRESENT" }

$provision = Get-JsonFile -Path ([string]$contract.paths.provision_state)
$restart = Get-JsonFile -Path ([string]$contract.paths.restart_rehearsal)
$dependency = Get-JsonFile -Path ([string]$contract.paths.dependency_rehearsal)
$reboot = Get-JsonFile -Path ([string]$contract.paths.reboot_rehearsal)
$health = Get-JsonFile -Path ([string]$contract.paths.status_file)

if ($null -eq $provision -or $provision.idempotence_verified -ne $true) {
    $reasons += "PROVISION_STATE_NOT_READY"
}
if ($null -eq $restart -or $restart.passed -ne $true) {
    $reasons += "RESTART_REHEARSAL_NOT_PROVEN"
}
if ($null -eq $dependency -or $dependency.passed -ne $true) {
    $reasons += "DEPENDENCY_REHEARSAL_NOT_PROVEN"
}
if ($null -eq $health -or [string]$health.status -notin @("HEALTHY", "DEGRADED")) {
    $reasons += "HEALTH_STATUS_NOT_SAFE"
}

$bootUtc = Get-BootTimeUtc
$postBootFresh = $false
if ($null -ne $reboot -and $reboot.post_boot_observed -eq $true -and $null -ne $bootUtc) {
    try {
        $observedBoot = [datetime]::Parse(
            [string]$reboot.observed_boot_time_utc,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        ).ToUniversalTime()
        $supervisorObserved = [datetime]::Parse(
            [string]$reboot.supervisor_observed_at_utc,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind
        ).ToUniversalTime()
        $statusObserved = if ($null -ne $health) {
            [datetime]::Parse(
                [string]$health.observed_at_utc,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind
            ).ToUniversalTime()
        } else { [datetime]::MinValue }
        $sameBoot = [math]::Abs(($observedBoot - $bootUtc).TotalSeconds) -le 5
        $afterBoot = $supervisorObserved -gt $bootUtc -and $statusObserved -gt $bootUtc
        $freshWindow = $supervisorObserved -ge [datetime]::UtcNow.AddMinutes(-[int]$contract.reboot_rehearsal.freshness_minutes)
        $postBootFresh = ($sameBoot -and $afterBoot -and $freshWindow)
    }
    catch { $postBootFresh = $false }
}
if (-not $postBootFresh) { $reasons += "POST_REBOOT_FRESH_STATUS_NOT_PROVEN" }

$overall = if ($reasons.Count -eq 0) { "PASS" } else { "FAIL" }
$profile = [ordered]@{
    schema_version = "1"
    work_package = "WP9"
    mode = "AUDIT"
    status = $overall
    reasons = @($reasons | Sort-Object -Unique)
    runner_process = $runnerProcess
    health_task = $healthTask
    sealed_slots = $slotSummaries
    execution_task_present = $executionTaskPresent
    runtime_role = $runtimeRole
    execution_role = $executionRole
    local_service_wp8_payload_read_grant = $localServiceWp8Read
    provision = [ordered]@{
        present = ($null -ne $provision)
        idempotence_verified = ($null -ne $provision -and $provision.idempotence_verified -eq $true)
        future_product_slots_sealed = ($null -ne $provision -and $provision.future_product_slots_sealed -eq $true)
        real_secret_values_used = ($null -ne $provision -and $provision.real_secret_values_used -eq $true)
        real_money_authority_changed = ($null -ne $provision -and $provision.real_money_authority_changed -eq $true)
    }
    restart_rehearsal_pass = ($null -ne $restart -and $restart.passed -eq $true)
    dependency_rehearsal_pass = ($null -ne $dependency -and $dependency.passed -eq $true)
    post_reboot_fresh_status = $postBootFresh
    health_status = if ($null -ne $health) { [string]$health.status } else { "UNAVAILABLE" }
    privacy = [ordered]@{
        raw_usernames_collected = $false
        sids_emitted = $false
        hostnames_collected = $false
        addresses_collected = $false
        credential_values_collected = $false
        ciphertext_collected = $false
        credential_hashes_collected = $false
        account_ids_collected = $false
        private_data_collected = $false
        process_command_lines_collected = $false
        process_dumps_collected = $false
    }
}

if ($AsJson) {
    $profile | ConvertTo-Json -Depth 10 -Compress
}
else {
    Write-Output ("WP9 supervision audit status: {0}" -f $profile.status)
    Write-Output ("WP9 health status: {0}" -f $profile.health_status)
    Write-Output ("WP9 post-reboot fresh status: {0}" -f $profile.post_reboot_fresh_status)
}

if ($profile.status -eq "PASS") { exit 0 }
exit 1
