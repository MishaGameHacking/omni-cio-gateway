[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Round-Number {
    param(
        [Parameter(Mandatory = $true)]
        [double]$Value,
        [int]$Digits = 2
    )
    return [Math]::Round($Value, $Digits)
}

function Get-NvidiaSmiPath {
    $command = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $candidate = Join-Path $env:ProgramFiles "NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    return $null
}

function Get-NormalizedLenovoSetting {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [Parameter(Mandatory = $true)]
        [string]$UnknownValue
    )
    try {
        $settings = Get-CimInstance -Namespace root\wmi -ClassName Lenovo_BiosSetting -ErrorAction Stop
        $match = $settings | Where-Object {
            $_.CurrentSetting -match $Pattern
        } | Select-Object -First 1
        if ($null -eq $match) {
            return $UnknownValue
        }
        $raw = [string]$match.CurrentSetting
        if ($raw -match '(?i),\s*(Enabled|On|Power On|Last State)\s*;?$') {
            return "ENABLED"
        }
        if ($raw -match '(?i),\s*(Disabled|Off|Power Off)\s*;?$') {
            return "DISABLED"
        }
        return $UnknownValue
    }
    catch {
        return $UnknownValue
    }
}

function Get-W32TimeOffsetMs {
    try {
        $output = & w32tm.exe /stripchart /computer:time.windows.com /samples:3 /dataonly 2>$null
        $values = @()
        foreach ($line in $output) {
            $matches = [regex]::Matches([string]$line, '([+-]\d+(?:[\.,]\d+)?)s')
            foreach ($match in $matches) {
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
        if ($values.Count -eq 0) {
            return $null
        }
        return Round-Number -Value (($values | Measure-Object -Average).Average) -Digits 3
    }
    catch {
        return $null
    }
}

function Get-W32TimeSourceClass {
    try {
        $source = ((& w32tm.exe /query /source 2>$null) | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($source)) {
            return "UNKNOWN"
        }
        if ($source -match '(?i)time\.windows\.com|pool\.ntp|ntp') {
            return "WINDOWS_NTP"
        }
        if ($source -match '(?i)local cmos|free-running|vm ic time') {
            return "LOCAL_CLOCK"
        }
        if ($source -match '(?i)domain|nt5ds') {
            return "DOMAIN_HIERARCHY"
        }
        return "OTHER"
    }
    catch {
        return "UNKNOWN"
    }
}

$capturedAt = (Get-Date).ToUniversalTime().ToString("o")
$computerSystem = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$operatingSystem = Get-CimInstance Win32_OperatingSystem

$cpu = [ordered]@{
    model = ([string]$processor.Name).Trim()
    physical_cores = [int]$processor.NumberOfCores
    logical_processors = [int]$processor.NumberOfLogicalProcessors
}
$memory = [ordered]@{
    total_gib = Round-Number -Value ([double]$computerSystem.TotalPhysicalMemory / 1GB)
}

$gpu = [ordered]@{
    present = $false
    vendor = $null
    model = $null
    vram_mib = $null
    driver_version = $null
    idle_temperature_c = $null
    telemetry_source = "UNAVAILABLE"
}
$nvidiaSmi = Get-NvidiaSmiPath
if ($null -ne $nvidiaSmi) {
    try {
        $line = (& $nvidiaSmi --query-gpu=name,memory.total,driver_version,temperature.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
        if (-not [string]::IsNullOrWhiteSpace([string]$line)) {
            $parts = ([string]$line) -split '\s*,\s*'
            if ($parts.Count -ge 4) {
                $gpu.present = $true
                $gpu.vendor = "NVIDIA"
                $gpu.model = $parts[0].Trim()
                $vram = 0.0
                if ([double]::TryParse($parts[1], [ref]$vram)) {
                    $gpu.vram_mib = Round-Number -Value $vram -Digits 0
                }
                $gpu.driver_version = $parts[2].Trim()
                $temperature = 0.0
                if ([double]::TryParse($parts[3], [ref]$temperature)) {
                    $gpu.idle_temperature_c = Round-Number -Value $temperature -Digits 1
                }
                $gpu.telemetry_source = "NVIDIA_SMI"
            }
        }
    }
    catch {
        # Fall through to the privacy-safe CIM fallback below.
    }
}
if (-not $gpu.present) {
    try {
        $video = Get-CimInstance Win32_VideoController | Where-Object {
            -not [string]::IsNullOrWhiteSpace([string]$_.Name)
        } | Select-Object -First 1
        if ($null -ne $video) {
            $gpu.present = $true
            $gpu.vendor = if ([string]$video.Name -match '(?i)nvidia') { "NVIDIA" } else { "OTHER" }
            $gpu.model = ([string]$video.Name).Trim()
            $gpu.driver_version = if ($null -ne $video.DriverVersion) { ([string]$video.DriverVersion).Trim() } else { $null }
            $gpu.telemetry_source = "WIN32_VIDEO_CONTROLLER"
        }
    }
    catch {
        # Keep the explicit UNAVAILABLE state.
    }
}

$driveLetter = $env:SystemDrive.TrimEnd(':')
$volume = Get-Volume -DriveLetter $driveLetter
$capacityGiB = [double]$volume.Size / 1GB
$freeGiB = [double]$volume.SizeRemaining / 1GB
$freePercent = if ($capacityGiB -gt 0) { ($freeGiB / $capacityGiB) * 100.0 } else { 0.0 }
$physicalDisks = @()
try {
    foreach ($disk in Get-PhysicalDisk) {
        $physicalDisks += [ordered]@{
            size_gib = Round-Number -Value ([double]$disk.Size / 1GB)
            media_type = [string]$disk.MediaType
            health_status = [string]$disk.HealthStatus
            operational_status = ((@($disk.OperationalStatus) | ForEach-Object { [string]$_ }) -join '|')
        }
    }
}
catch {
    $physicalDisks = @(
        [ordered]@{
            size_gib = Round-Number -Value $capacityGiB
            media_type = "Unknown"
            health_status = "Unknown"
            operational_status = "Unknown"
        }
    )
}
$storage = [ordered]@{
    system_volume = [ordered]@{
        capacity_gib = Round-Number -Value $capacityGiB
        free_gib = Round-Number -Value $freeGiB
        free_percent = Round-Number -Value $freePercent
        health_status = [string]$volume.HealthStatus
    }
    physical_disks = $physicalDisks
}

$bitLocker = [ordered]@{
    provider = "UNAVAILABLE"
    volume_status = "UNKNOWN"
    protection_status = "UNKNOWN"
    encryption_percentage = $null
    encryption_method = $null
    recovery_key_custody_status = "OWNER_CONFIRMATION_REQUIRED"
}
try {
    $bl = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop
    $bitLocker.provider = "BITLOCKER"
    $bitLocker.volume_status = [string]$bl.VolumeStatus
    $bitLocker.protection_status = if ([string]$bl.ProtectionStatus -match '(?i)^on$|^1$') { "ON" } elseif ([string]$bl.ProtectionStatus -match '(?i)^off$|^0$') { "OFF" } else { "UNKNOWN" }
    $bitLocker.encryption_percentage = if ($null -ne $bl.EncryptionPercentage) { [double]$bl.EncryptionPercentage } else { $null }
    $bitLocker.encryption_method = if ($null -ne $bl.EncryptionMethod) { [string]$bl.EncryptionMethod } else { $null }
}
catch {
    # UNAVAILABLE is an explicit blocker until the OWNER node can prove disk-at-rest protection.
}

$firewallProfiles = @()
try {
    foreach ($profile in Get-NetFirewallProfile -PolicyStore ActiveStore) {
        $firewallProfiles += [ordered]@{
            name = [string]$profile.Name
            enabled = [bool]$profile.Enabled
            default_inbound_action = [string]$profile.DefaultInboundAction
            default_outbound_action = [string]$profile.DefaultOutboundAction
        }
    }
}
catch {
    foreach ($name in @("Domain", "Private", "Public")) {
        $firewallProfiles += [ordered]@{
            name = $name
            enabled = $false
            default_inbound_action = "Unknown"
            default_outbound_action = "Unknown"
        }
    }
}
$wildcardListeners = 0
try {
    $wildcardListeners = @(
        Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object {
            $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::'
        }
    ).Count
}
catch {
    $wildcardListeners = 0
}

$timeService = Get-Service W32Time -ErrorAction SilentlyContinue
$timeServiceStatus = if ($null -ne $timeService) { ([string]$timeService.Status).ToUpperInvariant() } else { "UNKNOWN" }
$clockOffsetMs = Get-W32TimeOffsetMs
$clockGate = if ($timeServiceStatus -ne "RUNNING" -or $null -eq $clockOffsetMs) {
    "BLOCK_UNKNOWN_TIME"
} elseif ([Math]::Abs([double]$clockOffsetMs) -gt 2000.0) {
    "BLOCK_DRIFT"
} else {
    "PASS"
}
$timeData = [ordered]@{
    service_status = $timeServiceStatus
    source_class = Get-W32TimeSourceClass
    measured_against = "time.windows.com"
    offset_ms = $clockOffsetMs
    utc_policy = "CANONICAL_EVENT_TIMESTAMPS_UTC"
    sensitive_operation_gate = $clockGate
}

$wiredAdapters = @()
try {
    $wiredAdapters = @(
        Get-CimInstance Win32_NetworkAdapter | Where-Object {
            $_.PhysicalAdapter -eq $true -and $_.NetConnectionStatus -eq 2 -and $_.AdapterTypeID -eq 0
        }
    )
}
catch {
    $wiredAdapters = @()
}
$wiredSpeedMbps = $null
if ($wiredAdapters.Count -gt 0) {
    $speeds = @($wiredAdapters | Where-Object { $null -ne $_.Speed } | ForEach-Object { [double]$_.Speed / 1MB })
    if ($speeds.Count -gt 0) {
        $wiredSpeedMbps = Round-Number -Value (($speeds | Measure-Object -Maximum).Maximum) -Digits 0
    }
}
$network = [ordered]@{
    wired_connected = ($wiredAdapters.Count -gt 0)
    wired_link_speed_mbps = $wiredSpeedMbps
    public_exposure_assessment = "BASELINE_FIREWALL_ONLY_NO_V10_RUNTIME"
}

$battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
$acOnline = $null
try {
    $batteryStatus = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop | Select-Object -First 1
    if ($null -ne $batteryStatus -and $null -ne $batteryStatus.PowerOnline) {
        $acOnline = [bool]$batteryStatus.PowerOnline
    }
}
catch {
    $acOnline = $null
}
$powerScheme = "UNKNOWN"
try {
    $powerOutput = ((& powercfg.exe /getactivescheme 2>$null) | Out-String).Trim()
    $match = [regex]::Match($powerOutput, '\(([^\r\n()]+)\)\s*$')
    if ($match.Success) {
        $powerScheme = $match.Groups[1].Value.Trim()
    }
}
catch {
    $powerScheme = "UNKNOWN"
}
$batteryConservation = if ($null -eq $battery) {
    "NOT_APPLICABLE"
} else {
    Get-NormalizedLenovoSetting -Pattern '(?i)conservation|battery.*charge' -UnknownValue "UNKNOWN_REQUIRES_OWNER_CHECK"
}
$restartAfterPowerLoss = Get-NormalizedLenovoSetting -Pattern '(?i)after.*power.*loss|restore.*ac|ac.*power.*loss' -UnknownValue "UNKNOWN_REQUIRES_FIRMWARE_CHECK"
$power = [ordered]@{
    battery_present = ($null -ne $battery)
    ac_online = $acOnline
    active_power_scheme = $powerScheme
    battery_conservation = $batteryConservation
    restart_after_power_loss = $restartAfterPowerLoss
}

$acpiTemperatures = @()
try {
    $thermalZones = Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop
    foreach ($zone in $thermalZones) {
        $celsius = ([double]$zone.CurrentTemperature / 10.0) - 273.15
        if ($celsius -ge 0 -and $celsius -le 125) {
            $acpiTemperatures += $celsius
        }
    }
}
catch {
    $acpiTemperatures = @()
}
$acpiMax = if ($acpiTemperatures.Count -gt 0) {
    Round-Number -Value (($acpiTemperatures | Measure-Object -Maximum).Maximum) -Digits 1
} else {
    $null
}
$thermalObservation = if ($null -ne $gpu.idle_temperature_c -and $null -ne $acpiMax) {
    "PASSIVE_BASELINE"
} elseif ($null -ne $gpu.idle_temperature_c -or $null -ne $acpiMax) {
    "SENSORS_PARTIAL"
} else {
    "SENSORS_UNAVAILABLE"
}
$thermal = [ordered]@{
    acpi_zone_max_idle_c = $acpiMax
    gpu_idle_c = $gpu.idle_temperature_c
    observation = $thermalObservation
}

$diskHealth = "PASS"
if ([string]$volume.HealthStatus -notmatch '(?i)^healthy$') {
    $diskHealth = "WARN"
}
foreach ($disk in $physicalDisks) {
    if ([string]$disk.health_status -match '(?i)unhealthy|warning') {
        $diskHealth = "FAIL"
        break
    }
    if ([string]$disk.health_status -notmatch '(?i)^healthy$' -and $diskHealth -eq "PASS") {
        $diskHealth = "UNKNOWN"
    }
}

$profile = [ordered]@{
    schema_version = "1"
    captured_at_utc = $capturedAt
    capture_mode = "PASSIVE_READ_ONLY"
    node_role = "OWNER_PERSONAL_NODE"
    privacy = [ordered]@{
        serial_numbers_collected = $false
        mac_or_ip_collected = $false
        usernames_or_hostnames_collected = $false
        secret_values_collected = $false
        recovery_key_material_collected = $false
    }
    hardware = [ordered]@{
        cpu = $cpu
        memory = $memory
        gpu = $gpu
        storage = $storage
    }
    os = [ordered]@{
        product_name = ([string]$operatingSystem.Caption).Trim()
        version = ([string]$operatingSystem.Version).Trim()
        build = ([string]$operatingSystem.BuildNumber).Trim()
        architecture = ([string]$operatingSystem.OSArchitecture).Trim()
        last_boot_utc = ([datetime]$operatingSystem.LastBootUpTime).ToUniversalTime().ToString("o")
    }
    security = [ordered]@{
        full_disk_encryption = $bitLocker
        firewall = [ordered]@{
            profiles = $firewallProfiles
            wildcard_tcp_listener_count = [int]$wildcardListeners
        }
        private_at_rest = [ordered]@{
            classification = "BROKER_SECRETS_PRIVATE_DB_CORTEX_HISTORY_PRIVATE"
            acl_state = "WP6_NOT_YET_CONFIGURED"
        }
    }
    time = $timeData
    network = $network
    power = $power
    thermal = $thermal
    checks = [ordered]@{
        disk_health = $diskHealth
        reboot = "NOT_RUN"
        network_reconnect = "NOT_RUN"
        sustained_cpu_gpu_load = "NOT_RUN"
    }
    thresholds_ref = "infrastructure/windows/wp5_node_thresholds.json"
    exit_gate = [ordered]@{
        status = "BLOCKED"
        blocking_reasons = @()
    }
}

$output = [System.IO.Path]::GetFullPath($OutputPath)
$directory = Split-Path -Parent $output
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$profile | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $output -Encoding utf8
Write-Host "WP5 passive OWNER node profile collected: $output"
Write-Host "Privacy contract: no serial numbers, MAC/IP addresses, usernames/hostnames, secrets or recovery-key material collected."
