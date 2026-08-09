[CmdletBinding()]
param(
    [string]$ContractPath = "C:\ProgramData\OmniCIO\services\wp9\deployed\V10_WP9_SUPERVISION_CONTRACT.json",
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Get-BootTimeUtc {
    try {
        $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        return ([datetime]$os.LastBootUpTime).ToUniversalTime()
    }
    catch {
        return $null
    }
}

function Get-TaskState {
    param(
        [string]$TaskPath,
        [string]$TaskName,
        [bool]$ExpectedEnabled
    )

    try {
        $task = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction Stop
        $enabled = ([string]$task.State -ne "Disabled")
        return [ordered]@{
            present = $true
            enabled = $enabled
            expected_enabled = $ExpectedEnabled
            valid = ($enabled -eq $ExpectedEnabled)
        }
    }
    catch {
        return [ordered]@{
            present = $false
            enabled = $null
            expected_enabled = $ExpectedEnabled
            valid = $false
        }
    }
}

function Get-DatabaseState {
    param([object]$Component)

    $serviceReady = $false
    $probeReady = $false
    try {
        $service = Get-Service -Name ([string]$Component.service_name) -ErrorAction Stop
        $serviceReady = ([string]$service.Status -eq "Running")
    }
    catch {
        $serviceReady = $false
    }

    $probePath = "C:\Program Files\PostgreSQL\18\bin\pg_isready.exe"
    if ($serviceReady -and (Test-Path -LiteralPath $probePath -PathType Leaf)) {
        try {
            & $probePath -h 127.0.0.1 -p 5432 -q
            $probeReady = ($LASTEXITCODE -eq 0)
        }
        catch {
            $probeReady = $false
        }
    }

    return [ordered]@{
        service_running = $serviceReady
        readiness_probe = $probeReady
        state = if ($serviceReady -and $probeReady) { "READY" } else { "DEGRADED" }
    }
}

function Write-AtomicJson {
    param(
        [string]$Path,
        [object]$Value
    )

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "WP9_EVIDENCE_DIRECTORY_MISSING"
    }
    $temporary = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

if ($env:OS -ne "Windows_NT") {
    throw "WP9_HEALTH_WINDOWS_REQUIRED"
}
if (-not (Test-Path -LiteralPath $ContractPath -PathType Leaf)) {
    throw "WP9_SUPERVISION_CONTRACT_MISSING"
}

$contract = Get-Content -LiteralPath $ContractPath -Raw -ErrorAction Stop |
    ConvertFrom-Json -ErrorAction Stop
if ([string]$contract.schema_version -ne "1" -or [string]$contract.work_package -ne "WP9") {
    throw "WP9_SUPERVISION_CONTRACT_INVALID"
}

$taskPath = [string]$contract.task_folder
$taskMap = $contract.tasks
$componentRows = @()
$reasons = @()
$database = $null
$supervisorTaskValid = $false
$sealedTasksValid = $true
$sealedCount = 0

foreach ($component in @($contract.components)) {
    $id = [string]$component.id
    $activation = [string]$component.activation
    if ($id -eq "database") {
        $database = Get-DatabaseState -Component $component
        $componentRows += [ordered]@{
            id = $id
            activation = $activation
            state = [string]$database.state
            task_present = $null
            task_enabled = $null
        }
        if ([string]$database.state -ne "READY") {
            $reasons += "DATABASE_NOT_READY"
        }
        continue
    }

    if ($id -eq "health_supervisor") {
        $taskName = [string]$taskMap.health_supervisor
        $state = Get-TaskState -TaskPath $taskPath -TaskName $taskName -ExpectedEnabled $true
        $supervisorTaskValid = [bool]$state.valid
        $componentRows += [ordered]@{
            id = $id
            activation = $activation
            state = if ($state.valid) { "READY" } else { "ERROR" }
            task_present = [bool]$state.present
            task_enabled = $state.enabled
        }
        if (-not $state.valid) {
            $reasons += "HEALTH_SUPERVISOR_TASK_INVALID"
        }
        continue
    }

    if ($activation -eq "SEALED_UNTIL_OWNING_WP") {
        $taskName = [string]$taskMap.$id
        $state = Get-TaskState -TaskPath $taskPath -TaskName $taskName -ExpectedEnabled $false
        $sealedCount += 1
        if (-not $state.valid) {
            $sealedTasksValid = $false
            $reasons += "SEALED_TASK_INVALID:$id"
        }
        $componentRows += [ordered]@{
            id = $id
            activation = $activation
            state = if ($state.valid) { "NOT_READY" } else { "ERROR" }
            task_present = [bool]$state.present
            task_enabled = $state.enabled
        }
        continue
    }

    $sealedTasksValid = $false
    $reasons += "UNEXPECTED_COMPONENT_ACTIVATION:$id"
    $componentRows += [ordered]@{
        id = $id
        activation = $activation
        state = "ERROR"
        task_present = $null
        task_enabled = $null
    }
}

if ($sealedCount -gt 0 -and $sealedTasksValid) {
    $reasons += "SEALED_PRODUCT_SLOTS_NOT_READY"
}

if (-not $supervisorTaskValid -or -not $sealedTasksValid) {
    $overall = "ERROR"
}
elseif ($null -eq $database -or [string]$database.state -ne "READY" -or $sealedCount -gt 0) {
    $overall = "DEGRADED"
}
else {
    $overall = "HEALTHY"
}

$nowUtc = [datetime]::UtcNow
$bootUtc = Get-BootTimeUtc
$statusPath = [string]$contract.paths.status_file
$rebootPath = [string]$contract.paths.reboot_rehearsal

$profile = [ordered]@{
    schema_version = "1"
    work_package = "WP9"
    observed_at_utc = $nowUtc.ToString("o")
    boot_time_utc = if ($null -ne $bootUtc) { $bootUtc.ToString("o") } else { $null }
    status = $overall
    reasons = @($reasons | Sort-Object -Unique)
    components = $componentRows
    real_money_authority_changed = $false
    credential_values_observed = $false
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

Write-AtomicJson -Path $statusPath -Value $profile

if (Test-Path -LiteralPath $rebootPath -PathType Leaf) {
    try {
        $reboot = Get-Content -LiteralPath $rebootPath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        if ($reboot.armed -eq $true -and $reboot.post_boot_observed -ne $true -and $null -ne $bootUtc) {
            $preBoot = [datetime]::Parse(
                [string]$reboot.pre_reboot_boot_time_utc,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind
            ).ToUniversalTime()
            if ($bootUtc -gt $preBoot.AddSeconds(1)) {
                $updated = [ordered]@{
                    schema_version = "1"
                    armed = $true
                    armed_at_utc = [string]$reboot.armed_at_utc
                    pre_reboot_boot_time_utc = $preBoot.ToString("o")
                    post_boot_observed = $true
                    observed_boot_time_utc = $bootUtc.ToString("o")
                    supervisor_observed_at_utc = $nowUtc.ToString("o")
                    supervisor_status = $overall
                }
                Write-AtomicJson -Path $rebootPath -Value $updated
            }
        }
    }
    catch {
        $profile.status = "ERROR"
        $profile.reasons = @($profile.reasons + "REBOOT_EVIDENCE_INVALID" | Sort-Object -Unique)
        Write-AtomicJson -Path $statusPath -Value $profile
    }
}

if ($AsJson) {
    $profile | ConvertTo-Json -Depth 10 -Compress
}
elseif ($profile.status -eq "ERROR") {
    Write-Output "WP9 health supervisor status: ERROR"
}
else {
    Write-Output ("WP9 health supervisor status: {0}" -f $profile.status)
}

if ($profile.status -eq "ERROR") {
    exit 1
}
exit 0
