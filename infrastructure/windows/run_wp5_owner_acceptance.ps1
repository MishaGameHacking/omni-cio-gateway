[CmdletBinding()]
param(
    [ValidateRange(30, 60)]
    [int]$DurationMinutes = 30,
    [ValidateRange(50, 100)]
    [int]$MaxProcessorPerformancePercent = 90,
    [string]$Aida64Path = "C:\Program Files (x86)\FinalWire\AIDA64 Extreme\aida64.exe"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-SelfElevated {
    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('\"{0}\"' -f $PSCommandPath),
        "-DurationMinutes", $DurationMinutes,
        "-MaxProcessorPerformancePercent", $MaxProcessorPerformancePercent,
        "-Aida64Path", ('\"{0}\"' -f $Aida64Path)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList ($arguments -join " ")
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
    throw "nvidia-smi.exe is required for WP5 combined-load start detection."
}

function Get-CpuLoadPercent {
    $samples = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop | Select-Object -ExpandProperty LoadPercentage)
    if ($samples.Count -eq 0) {
        throw "CPU load telemetry is unavailable."
    }
    return [double](($samples | Measure-Object -Average).Average)
}

function Get-NvidiaUtilizationPercent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NvidiaSmiPath
    )

    $line = & $NvidiaSmiPath --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$line)) {
        throw "NVIDIA utilization telemetry is unavailable."
    }

    $value = 0.0
    if (-not [double]::TryParse(([string]$line).Trim(), [ref]$value)) {
        throw "NVIDIA utilization telemetry could not be parsed."
    }
    return $value
}

function Wait-ForCombinedLoadStart {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NvidiaSmiPath,
        [ValidateRange(30, 600)]
        [int]$TimeoutSeconds = 300,
        [ValidateRange(1, 100)]
        [int]$MinimumCpuLoadPercent = 80,
        [ValidateRange(1, 100)]
        [int]$MinimumGpuLoadPercent = 20,
        [ValidateRange(1, 10)]
        [int]$ConsecutiveSamplesRequired = 3
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $consecutiveSamples = 0

    Write-Host "Waiting for AIDA64 combined CPU+GPU load to start automatically..." -ForegroundColor Yellow
    Write-Host "No ENTER timing step is required. Start AIDA64 when ready."

    while ((Get-Date) -lt $deadline) {
        try {
            $cpuLoad = Get-CpuLoadPercent
            $gpuLoad = Get-NvidiaUtilizationPercent -NvidiaSmiPath $NvidiaSmiPath

            if ($cpuLoad -ge $MinimumCpuLoadPercent -and $gpuLoad -ge $MinimumGpuLoadPercent) {
                $consecutiveSamples += 1
            } else {
                $consecutiveSamples = 0
            }

            if ($consecutiveSamples -ge $ConsecutiveSamplesRequired) {
                Write-Host "Combined CPU+GPU load detected. Starting the 30-minute evidence window automatically." -ForegroundColor Green
                return
            }
        } catch {
            $consecutiveSamples = 0
        }

        Start-Sleep -Seconds 2
    }

    throw "Combined CPU+GPU load was not detected within $TimeoutSeconds seconds. No acceptance evidence was recorded."
}

function Read-ValidatedGpuEvidence {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [int]$ExpectedDurationSeconds
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "GPU telemetry sampler did not produce the required evidence file."
    }

    try {
        $evidence = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "GPU telemetry evidence is not valid JSON: $($_.Exception.Message)"
    }

    if ([string]$evidence.schema_version -ne "1") {
        throw "GPU telemetry evidence schema_version is unsupported."
    }
    if ([int]$evidence.duration_seconds -ne $ExpectedDurationSeconds) {
        throw "GPU telemetry evidence duration does not match the requested acceptance window."
    }
    if ([int]$evidence.observed_duration_seconds -lt $ExpectedDurationSeconds) {
        throw "GPU telemetry evidence did not observe the complete acceptance window."
    }
    if ([int]$evidence.sample_count -le 0) {
        throw "GPU telemetry evidence contains no valid samples."
    }
    if ($null -eq $evidence.gpu_temperature_c -or $null -eq $evidence.gpu_temperature_c.maximum) {
        throw "GPU telemetry evidence is missing the peak GPU temperature."
    }
    if ($null -eq $evidence.gpu_utilization_percent -or $null -eq $evidence.gpu_utilization_percent.maximum) {
        throw "GPU telemetry evidence is missing GPU utilization."
    }
    if (
        [bool]$evidence.privacy.model_or_uuid_collected -or
        [bool]$evidence.privacy.serial_collected -or
        [bool]$evidence.privacy.address_collected -or
        [bool]$evidence.privacy.process_list_collected
    ) {
        throw "GPU telemetry evidence violates the WP5 privacy contract."
    }

    return $evidence
}

function New-TemporaryNodePowerScheme {
    param(
        [Parameter(Mandatory = $true)]
        [int]$MaximumProcessorPercent
    )

    $duplicateText = powercfg /duplicatescheme SCHEME_BALANCED
    if ($LASTEXITCODE -ne 0) {
        throw "Could not duplicate the Windows Balanced power plan."
    }
    $schemeMatch = [regex]::Match(($duplicateText -join " "), "[0-9a-fA-F-]{36}")
    if (-not $schemeMatch.Success) {
        throw "Could not determine the temporary Balanced power-plan GUID."
    }

    $schemeGuid = $schemeMatch.Value
    powercfg /changename $schemeGuid "Omni-CIO WP5 Temporary Node Test" | Out-Null
    powercfg /setacvalueindex $schemeGuid SUB_PROCESSOR PROCTHROTTLEMAX $MaximumProcessorPercent | Out-Null
    if ($LASTEXITCODE -ne 0) {
        powercfg /delete $schemeGuid | Out-Null
        throw "Could not apply the temporary maximum processor performance state."
    }
    powercfg /setactive $schemeGuid | Out-Null
    if ($LASTEXITCODE -ne 0) {
        powercfg /delete $schemeGuid | Out-Null
        throw "Could not activate the temporary WP5 node power plan."
    }
    return $schemeGuid
}

if (-not (Test-IsAdministrator)) {
    Write-Host "Administrator approval is required only for this local WP5 acceptance launcher."
    Invoke-SelfElevated
    exit 0
}

$gpuSampler = Join-Path $PSScriptRoot "measure_wp5_gpu_load.ps1"
if (-not (Test-Path -LiteralPath $gpuSampler)) {
    throw "GPU sampler not found: $gpuSampler"
}
if (-not (Test-Path -LiteralPath $Aida64Path)) {
    throw "AIDA64 Extreme not found at: $Aida64Path"
}
$nvidiaSmi = Get-NvidiaSmiPath

$runnerService = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "actions.runner*" -or $_.DisplayName -like "*Actions Runner*" } |
    Select-Object -First 1
if ($null -eq $runnerService -or $runnerService.Status -ne "Running") {
    throw "GitHub self-hosted runner service is not Running."
}

$ethernet = Get-NetAdapter -Name "Ethernet" -ErrorAction SilentlyContinue
if ($null -eq $ethernet -or $ethernet.Status -ne "Up") {
    throw "Physical Ethernet adapter is not Up."
}

$githubCheck = Test-NetConnection api.github.com -Port 443 -InformationLevel Quiet
if (-not $githubCheck) {
    throw "GitHub HTTPS connectivity check failed."
}

$powerOnline = $null
try {
    $batteryStatus = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction Stop | Select-Object -First 1
    if ($null -ne $batteryStatus) {
        $powerOnline = [bool]$batteryStatus.PowerOnline
    }
} catch {
    Write-Warning "AC status could not be read from BatteryStatus; verify AC is connected before continuing."
}
if ($powerOnline -eq $false) {
    throw "AC power is not connected. Connect the charger before the sustained-load acceptance test."
}

$activeSchemeText = powercfg /getactivescheme
$activeSchemeMatch = [regex]::Match(($activeSchemeText -join " "), "[0-9a-fA-F-]{36}")
$previousScheme = if ($activeSchemeMatch.Success) { $activeSchemeMatch.Value } else { $null }
$temporaryScheme = $null

$stateRoot = Join-Path $env:ProgramData "OmniCIO\wp5"
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
$gpuOutput = Join-Path $stateRoot "wp5-gpu-load.json"
$eventOutput = Join-Path $stateRoot "wp5-system-events.json"
Remove-Item -LiteralPath $gpuOutput -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $eventOutput -Force -ErrorAction SilentlyContinue

$testStart = $null
try {
    Write-Host ""
    Write-Host "=== WP5 OWNER ACCEPTANCE PREFLIGHT ===" -ForegroundColor Cyan
    Write-Host "Runner: Running"
    Write-Host "Ethernet: $($ethernet.LinkSpeed) / Up"
    Write-Host "GitHub HTTPS: PASS"
    if ($powerOnline -eq $true) { Write-Host "AC power: connected" }
    Write-Host ""
    Write-Host "Creating a temporary conservative 24/7 node power profile..."
    Write-Host "Maximum processor performance during this test: $MaxProcessorPerformancePercent%"
    $temporaryScheme = New-TemporaryNodePowerScheme -MaximumProcessorPercent $MaxProcessorPerformancePercent

    Write-Host "Launching AIDA64 Extreme..."
    Start-Process -FilePath $Aida64Path | Out-Null
    Write-Host ""
    Write-Host "In AIDA64 open: Tools/Service -> System Stability Test" -ForegroundColor Yellow
    Write-Host "Use exactly:" -ForegroundColor Yellow
    Write-Host "  Stress CPU           ON"
    Write-Host "  Stress FPU           OFF"
    Write-Host "  Stress cache         ON"
    Write-Host "  Stress system memory ON"
    Write-Host "  Stress local disks   OFF"
    Write-Host "  Stress GPU(s)        ON"
    Write-Host ""
    Write-Host "Configure the checkboxes, click Clear, then click Start in AIDA64." -ForegroundColor Yellow
    Write-Host "The launcher will detect the combined CPU+GPU load automatically. Do not press ENTER."

    Wait-ForCombinedLoadStart -NvidiaSmiPath $nvidiaSmi

    $testStart = Get-Date
    $durationSeconds = $DurationMinutes * 60
    Write-Host "Starting privacy-safe GPU telemetry for $DurationMinutes minutes..."
    $samplerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('\"{0}\"' -f $gpuSampler),
        "-DurationSeconds", $durationSeconds,
        "-SampleIntervalSeconds", 5,
        "-OutputPath", ('\"{0}\"' -f $gpuOutput)
    )
    $sampler = Start-Process -FilePath "powershell.exe" -ArgumentList ($samplerArgs -join " ") -WindowStyle Hidden -PassThru

    Write-Host ""
    Write-Host "Combined load confirmed. Keep AIDA64 running until the two completion beeps." -ForegroundColor Green
    Write-Host "The telemetry window is now running for $DurationMinutes minutes."
    Write-Host "Stop immediately for a crash, thermal shutdown, or sustained temperature beyond the WP5 guardrails."
    Write-Host ""

    $sampler.WaitForExit()
    $sampler.Refresh()
    $samplerExitCode = $sampler.ExitCode
    $gpuEvidence = Read-ValidatedGpuEvidence -Path $gpuOutput -ExpectedDurationSeconds $durationSeconds
    if ($samplerExitCode -ne 0) {
        Write-Warning "GPU sampler process reported exit code $samplerExitCode, but the complete file-backed evidence passed fail-closed validation."
    }

    [console]::Beep(1200, 500)
    [console]::Beep(1200, 500)
    Write-Host ""
    Write-Host "Telemetry duration complete. Click Stop in AIDA64 now, then open Statistics." -ForegroundColor Green
    Write-Host "Validated GPU peak: $($gpuEvidence.gpu_temperature_c.maximum) C; utilization max: $($gpuEvidence.gpu_utilization_percent.maximum)%"

    $eventEnd = Get-Date
    $events = @()
    try {
        $events = Get-WinEvent -FilterHashtable @{ LogName = "System"; StartTime = $testStart; EndTime = $eventEnd } -ErrorAction Stop |
            Where-Object {
                $_.ProviderName -in @("Microsoft-Windows-WHEA-Logger", "Microsoft-Windows-Kernel-Power") -or
                $_.Id -in @(41, 1001)
            } |
            Select-Object TimeCreated, ProviderName, Id, LevelDisplayName
    } catch {
        Write-Warning "System event scan could not be completed: $($_.Exception.Message)"
    }

    [ordered]@{
        schema_version = "1"
        started_utc = $testStart.ToUniversalTime().ToString("o")
        ended_utc = $eventEnd.ToUniversalTime().ToString("o")
        duration_minutes_requested = $DurationMinutes
        max_processor_performance_percent = $MaxProcessorPerformancePercent
        relevant_system_event_count = @($events).Count
        relevant_system_events = @($events)
        privacy = [ordered]@{
            usernames_collected = $false
            hostnames_collected = $false
            addresses_collected = $false
            stable_device_ids_collected = $false
            secrets_collected = $false
        }
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $eventOutput -Encoding UTF8

    Write-Host ""
    Write-Host "=== SANITIZED GPU TELEMETRY ===" -ForegroundColor Cyan
    Get-Content -LiteralPath $gpuOutput
    Write-Host ""
    Write-Host "=== SANITIZED SYSTEM EVENT SUMMARY ===" -ForegroundColor Cyan
    Get-Content -LiteralPath $eventOutput
    Write-Host ""
    Write-Host "Keep AIDA64 Statistics open. We still need only the CPU peak and average throttling values from that window." -ForegroundColor Yellow
} finally {
    if ($null -ne $previousScheme) {
        try {
            powercfg /setactive $previousScheme | Out-Null
            Write-Host "Previous Windows power plan restored."
        } catch {
            Write-Warning "Could not restore the previous power plan automatically."
        }
    }
    if ($null -ne $temporaryScheme) {
        try {
            powercfg /delete $temporaryScheme | Out-Null
            Write-Host "Temporary WP5 power plan removed."
        } catch {
            Write-Warning "Could not remove the temporary WP5 power plan automatically."
        }
    }
}
