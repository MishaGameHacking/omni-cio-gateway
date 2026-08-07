[CmdletBinding()]
param(
    [ValidateRange(1, 3600)]
    [int]$DurationSeconds = 1800,
    [ValidateRange(1, 60)]
    [int]$SampleIntervalSeconds = 5,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-NvidiaSmiPath {
    $command = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }
    $candidate = Join-Path $env:ProgramFiles "NVIDIA Corporation\NVSMI\nvidia-smi.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    throw "nvidia-smi.exe is required for the WP5 GPU telemetry measurement."
}

$nvidiaSmi = Get-NvidiaSmiPath
$temperatures = New-Object System.Collections.Generic.List[double]
$utilizations = New-Object System.Collections.Generic.List[double]
$powers = New-Object System.Collections.Generic.List[double]
$started = Get-Date
$deadline = $started.AddSeconds($DurationSeconds)

while ((Get-Date) -lt $deadline) {
    $line = & $nvidiaSmi --query-gpu=temperature.gpu,utilization.gpu,power.draw --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    if (-not [string]::IsNullOrWhiteSpace([string]$line)) {
        $parts = ([string]$line) -split '\s*,\s*'
        if ($parts.Count -ge 3) {
            $temperature = 0.0
            $utilization = 0.0
            $power = 0.0
            if ([double]::TryParse($parts[0], [ref]$temperature)) {
                $temperatures.Add($temperature)
            }
            if ([double]::TryParse($parts[1], [ref]$utilization)) {
                $utilizations.Add($utilization)
            }
            if ([double]::TryParse($parts[2], [ref]$power)) {
                $powers.Add($power)
            }
        }
    }
    Start-Sleep -Seconds $SampleIntervalSeconds
}

if ($temperatures.Count -eq 0 -or $utilizations.Count -eq 0) {
    throw "No valid NVIDIA telemetry samples were collected."
}

$tempStats = $temperatures | Measure-Object -Minimum -Maximum -Average
$utilStats = $utilizations | Measure-Object -Minimum -Maximum -Average
$powerStats = if ($powers.Count -gt 0) { $powers | Measure-Object -Minimum -Maximum -Average } else { $null }

$result = [ordered]@{
    schema_version = "1"
    duration_seconds = $DurationSeconds
    sample_interval_seconds = $SampleIntervalSeconds
    sample_count = $temperatures.Count
    gpu_temperature_c = [ordered]@{
        minimum = [Math]::Round([double]$tempStats.Minimum, 1)
        maximum = [Math]::Round([double]$tempStats.Maximum, 1)
        average = [Math]::Round([double]$tempStats.Average, 1)
    }
    gpu_utilization_percent = [ordered]@{
        minimum = [Math]::Round([double]$utilStats.Minimum, 1)
        maximum = [Math]::Round([double]$utilStats.Maximum, 1)
        average = [Math]::Round([double]$utilStats.Average, 1)
    }
    gpu_power_w = if ($null -eq $powerStats) {
        $null
    } else {
        [ordered]@{
            minimum = [Math]::Round([double]$powerStats.Minimum, 2)
            maximum = [Math]::Round([double]$powerStats.Maximum, 2)
            average = [Math]::Round([double]$powerStats.Average, 2)
        }
    }
    privacy = [ordered]@{
        model_or_uuid_collected = $false
        serial_collected = $false
        address_collected = $false
        process_list_collected = $false
    }
}

$parent = Split-Path -Parent $OutputPath
if (-not [string]::IsNullOrWhiteSpace($parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "WP5 GPU telemetry written without device identifiers: $OutputPath"
