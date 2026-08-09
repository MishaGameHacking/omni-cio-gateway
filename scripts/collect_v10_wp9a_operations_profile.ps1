[CmdletBinding()]
param(
    [switch]$AsJson
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Round-Number {
    param([double]$Value, [int]$Digits = 2)
    return [Math]::Round($Value, $Digits)
}

function Get-W32TimeOffsetMs {
    try {
        $output = & w32tm.exe /stripchart /computer:time.windows.com /samples:3 /dataonly 2>$null
        $values = @()
        foreach ($line in $output) {
            foreach ($match in [regex]::Matches([string]$line, '([+-]\d+(?:[\.,]\d+)?)s')) {
                $normalized = $match.Groups[1].Value.Replace(',', '.')
                $seconds = 0.0
                if ([double]::TryParse(
                    $normalized,
                    [System.Globalization.NumberStyles]::Float,
                    [System.Globalization.CultureInfo]::InvariantCulture,
                    [ref]$seconds
                )) {
                    $values += ($seconds * 1000.0)
                }
            }
        }
        if ($values.Count -eq 0) { return $null }
        return Round-Number -Value (($values | Measure-Object -Average).Average) -Digits 3
    }
    catch { return $null }
}

function Test-PendingReboot {
    $paths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired',
        'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
    )
    if (Test-Path -LiteralPath $paths[0]) { return $true }
    if (Test-Path -LiteralPath $paths[1]) { return $true }
    try {
        $session = Get-ItemProperty -LiteralPath $paths[2] -Name PendingFileRenameOperations -ErrorAction Stop
        if ($null -ne $session.PendingFileRenameOperations) { return $true }
    }
    catch { }
    return $false
}

function Find-RunnerRoot {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($env:GITHUB_WORKSPACE)) {
        $cursor = [System.IO.DirectoryInfo](Split-Path -Parent $env:GITHUB_WORKSPACE)
        while ($null -ne $cursor) {
            $candidates += $cursor.FullName
            $cursor = $cursor.Parent
        }
    }
    $candidates += @('C:\actions-runner')
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath (Join-Path $candidate '.runner') -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Get-RunnerUpdateFacts {
    $result = [ordered]@{
        service_present = $false
        service_running = $false
        disable_update = $null
        version_known = $false
        version = $null
        update_diagnostics_present = $false
    }
    try {
        $service = Get-Service -Name 'actions.runner.*' -ErrorAction Stop | Select-Object -First 1
        if ($null -ne $service) {
            $result.service_present = $true
            $result.service_running = ([string]$service.Status -eq 'Running')
        }
    }
    catch { }

    $root = Find-RunnerRoot
    if ($null -eq $root) { return $result }

    try {
        $settings = Get-Content -LiteralPath (Join-Path $root '.runner') -Raw -ErrorAction Stop | ConvertFrom-Json
        $property = $settings.PSObject.Properties | Where-Object { $_.Name -match '(?i)^disableupdate$' } | Select-Object -First 1
        if ($null -ne $property) { $result.disable_update = [bool]$property.Value }
        else { $result.disable_update = $false }
    }
    catch { $result.disable_update = $null }

    $listener = Join-Path $root 'bin\Runner.Listener.exe'
    if (Test-Path -LiteralPath $listener -PathType Leaf) {
        try {
            $version = ((& $listener --version 2>$null) | Out-String).Trim()
            if ($version -match '^\d+\.\d+\.\d+$') {
                $result.version_known = $true
                $result.version = $version
            }
        }
        catch { }
    }
    try {
        $diag = Join-Path $root '_diag'
        if (Test-Path -LiteralPath $diag -PathType Container) {
            $result.update_diagnostics_present = (@(Get-ChildItem -LiteralPath $diag -Filter 'SelfUpdate*.log' -File -ErrorAction SilentlyContinue).Count -gt 0)
        }
    }
    catch { }
    return $result
}

function Get-NvidiaFacts {
    $result = [ordered]@{
        present = $false
        driver_version_known = $false
        driver_version = $null
        temperature_c = $null
        vram_used_percent = $null
    }
    $command = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $candidate = Join-Path $env:ProgramFiles 'NVIDIA Corporation\NVSMI\nvidia-smi.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $command = [pscustomobject]@{ Source = $candidate } }
    }
    if ($null -eq $command) { return $result }
    try {
        $line = (& $command.Source --query-gpu=driver_version,temperature.gpu,memory.total,memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
        if ([string]::IsNullOrWhiteSpace([string]$line)) { return $result }
        $parts = ([string]$line) -split '\s*,\s*'
        if ($parts.Count -lt 4) { return $result }
        $result.present = $true
        $result.driver_version_known = -not [string]::IsNullOrWhiteSpace($parts[0])
        $result.driver_version = $parts[0].Trim()
        $temperature = 0.0
        if ([double]::TryParse($parts[1], [ref]$temperature)) { $result.temperature_c = Round-Number $temperature 1 }
        $total = 0.0
        $used = 0.0
        if ([double]::TryParse($parts[2], [ref]$total) -and [double]::TryParse($parts[3], [ref]$used) -and $total -gt 0) {
            $result.vram_used_percent = Round-Number (($used / $total) * 100.0) 1
        }
    }
    catch { }
    return $result
}

function Get-PostgresFacts {
    $result = [ordered]@{
        present = $false
        version_known = $false
        version = $null
        major = $null
        ready = $false
    }
    $psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
    $pgReady = 'C:\Program Files\PostgreSQL\18\bin\pg_isready.exe'
    if (-not (Test-Path -LiteralPath $psql -PathType Leaf)) { return $result }
    $result.present = $true
    try {
        $raw = ((& $psql --version 2>$null) | Out-String).Trim()
        if ($raw -match '(\d+\.\d+)') {
            $result.version_known = $true
            $result.version = $Matches[1]
            $result.major = [int](($Matches[1] -split '\.')[0])
        }
    }
    catch { }
    if (Test-Path -LiteralPath $pgReady -PathType Leaf) {
        & $pgReady -h localhost -p 5432 -q 2>$null
        $result.ready = ($LASTEXITCODE -eq 0)
    }
    return $result
}

function Get-Wp9HealthFacts {
    $result = [ordered]@{
        present = $false
        status = 'UNKNOWN'
        fresh = $false
    }
    $path = 'C:\ProgramData\OmniCIO\services\wp9\evidence\health-status.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $result }
    try {
        $health = Get-Content -LiteralPath $path -Raw -ErrorAction Stop | ConvertFrom-Json
        $result.present = $true
        $result.status = [string]$health.status
        $observed = [datetime]::Parse([string]$health.observed_at_utc).ToUniversalTime()
        $result.fresh = ((([datetime]::UtcNow - $observed).TotalMinutes) -le 1500)
    }
    catch { }
    return $result
}

$capturedAt = [datetime]::UtcNow.ToString('o')
$timeServiceRunning = $false
try { $timeServiceRunning = ([string](Get-Service W32Time -ErrorAction Stop).Status -eq 'Running') } catch { }
$timeOffset = Get-W32TimeOffsetMs

$systemDrive = $env:SystemDrive.TrimEnd(':')
$freeGiB = $null
$freePercent = $null
try {
    $volume = Get-Volume -DriveLetter $systemDrive -ErrorAction Stop
    $freeGiB = Round-Number ([double]$volume.SizeRemaining / 1GB) 2
    if ([double]$volume.Size -gt 0) { $freePercent = Round-Number (([double]$volume.SizeRemaining / [double]$volume.Size) * 100.0) 2 }
}
catch { }

$memoryUsedPercent = $null
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    if ([double]$os.TotalVisibleMemorySize -gt 0) {
        $used = [double]$os.TotalVisibleMemorySize - [double]$os.FreePhysicalMemory
        $memoryUsedPercent = Round-Number (($used / [double]$os.TotalVisibleMemorySize) * 100.0) 1
    }
}
catch { }

$updateService = [ordered]@{ present = $false; disabled = $true }
try {
    $wu = Get-CimInstance Win32_Service -Filter "Name='wuauserv'" -ErrorAction Stop
    if ($null -ne $wu) {
        $updateService.present = $true
        $updateService.disabled = ([string]$wu.StartMode -eq 'Disabled')
    }
}
catch { }

$ollamaPresent = $false
try { $ollamaPresent = ($null -ne (Get-Command ollama.exe -ErrorAction SilentlyContinue)) } catch { }

$profile = [ordered]@{
    schema_version = '1'
    work_package = 'WP9A'
    mode = 'AUDIT'
    captured_at_utc = $capturedAt
    windows_update = [ordered]@{
        service_present = [bool]$updateService.present
        service_disabled = [bool]$updateService.disabled
        pending_reboot = [bool](Test-PendingReboot)
    }
    time = [ordered]@{
        service_running = [bool]$timeServiceRunning
        offset_ms = $timeOffset
    }
    runner = Get-RunnerUpdateFacts
    postgresql = Get-PostgresFacts
    nvidia = Get-NvidiaFacts
    ollama = [ordered]@{
        present = [bool]$ollamaPresent
        not_ready_allowed = $true
    }
    resources = [ordered]@{
        system_disk_free_gib = $freeGiB
        system_disk_free_percent = $freePercent
        memory_used_percent = $memoryUsedPercent
    }
    wp9 = Get-Wp9HealthFacts
    privacy = [ordered]@{
        raw_usernames_collected = $false
        hostnames_collected = $false
        addresses_collected = $false
        credential_values_collected = $false
        ciphertext_collected = $false
        account_ids_collected = $false
        private_portfolio_data_collected = $false
        process_command_lines_collected = $false
        process_dumps_collected = $false
    }
}

$json = $profile | ConvertTo-Json -Depth 8 -Compress:$AsJson
Write-Output $json
