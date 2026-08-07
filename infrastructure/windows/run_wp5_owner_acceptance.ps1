[CmdletBinding()]
param(
    [ValidateRange(30, 60)]
    [int]$DurationMinutes = 30,
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
        "-File", ('"{0}"' -f $PSCommandPath),
        "-DurationMinutes", $DurationMinutes,
        "-Aida64Path", ('"{0}"' -f $Aida64Path)
    )
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList ($arguments -join " ")
}

if (-not (Test-IsAdministrator)) {
    Write-Host "Administrator approval is required only for this local WP5 acceptance launcher."
    Invoke-SelfElevated
    exit 0
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$gpuSampler = Join-Path $PSScriptRoot "measure_wp5_gpu_load.ps1"
if (-not (Test-Path -LiteralPath $gpuSampler)) {
    throw "GPU sampler not found: $gpuSampler"
}
if (-not (Test-Path -LiteralPath $Aida64Path)) {
    throw "AIDA64 Extreme not found at: $Aida64Path"
}

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
    Write-Host "Switching temporarily to the standard Windows Balanced power plan..."
    powercfg /setactive SCHEME_BALANCED | Out-Null

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
    Write-Host "Do not press Start yet. Configure the checkboxes, then return here."
    Read-Host "Press ENTER when AIDA64 is configured and ready"

    $testStart = Get-Date
    $durationSeconds = $DurationMinutes * 60
    Write-Host "Starting privacy-safe GPU telemetry for $DurationMinutes minutes..."
    $samplerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $gpuSampler),
        "-DurationSeconds", $durationSeconds,
        "-SampleIntervalSeconds", 5,
        "-OutputPath", ('"{0}"' -f $gpuOutput)
    )
    $sampler = Start-Process -FilePath "powershell.exe" -ArgumentList ($samplerArgs -join " ") -WindowStyle Hidden -PassThru

    Write-Host ""
    Write-Host "NOW click Start in AIDA64." -ForegroundColor Green
    Write-Host "The telemetry window is running for $DurationMinutes minutes."
    Write-Host "Stop immediately if there is a crash, thermal shutdown, or sustained temperature beyond the WP5 guardrails."
    Write-Host ""

    Wait-Process -Id $sampler.Id
    if ($sampler.ExitCode -ne 0) {
        throw "GPU telemetry sampler failed with exit code $($sampler.ExitCode)."
    }

    [console]::Beep(1200, 500)
    [console]::Beep(1200, 500)
    Write-Host ""
    Write-Host "Telemetry duration complete. Click Stop in AIDA64 now, then open Statistics." -ForegroundColor Green

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
}
