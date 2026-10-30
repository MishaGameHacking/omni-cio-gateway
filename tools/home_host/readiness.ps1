$ErrorActionPreference = 'Stop'
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$drives = @([System.IO.DriveInfo]::GetDrives() | Where-Object { $_.DriveType -eq 'Fixed' -and $_.IsReady } | ForEach-Object {
    [ordered]@{volume=$_.Name.Substring(0,1); free_bytes=$_.AvailableFreeSpace; total_bytes=$_.TotalSize}
})
$volume = $null
try {
    $dist = Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss' |
        ForEach-Object { Get-ItemProperty $_.PSPath } |
        Where-Object DistributionName -eq 'Ubuntu-24.04' | Select-Object -First 1
    if ($dist -and $dist.BasePath -match '([A-Za-z]):\\') { $volume = $Matches[1].ToUpperInvariant() }
} catch {}
$runner = @(Get-CimInstance Win32_Service -Filter "Name LIKE 'actions.runner.%'")
$vpn = Get-Service Tailscale -ErrorAction SilentlyContinue
$vpnState = $null
$cli = Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'
if ($vpn -and $vpn.Status -eq 'Running' -and (Test-Path -LiteralPath $cli)) {
    try {
        $ts = & $cli status --json 2>$null | Out-String | ConvertFrom-Json
        if ($LASTEXITCODE -eq 0) { $vpnState = [bool]($ts.BackendState -eq 'Running' -and $ts.Self.Online) }
    } catch {}
}
$task = $null
try { $task = [string](Get-ScheduledTask -TaskName 'AnalystAI-RestartAfter12Hours' -ErrorAction Stop).State } catch {}
function Get-AcSetting([string]$group, [string]$setting) {
    $text = (& powercfg.exe /qh SCHEME_CURRENT $group $setting 2>$null | Out-String)
    $indices = [regex]::Matches($text, '(?im)0x([0-9a-f]{8})\s*$')
    if ($LASTEXITCODE -eq 0 -and $indices.Count -ge 2) {
        return [Convert]::ToUInt32($indices[$indices.Count - 2].Groups[1].Value, 16)
    }
    return $null
}
[ordered]@{
    elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    cpu_model = $cpu.Name.Trim()
    cores = [int]$cpu.NumberOfCores
    threads = [int]$cpu.NumberOfLogicalProcessors
    win_available_mib = [int]($os.FreePhysicalMemory / 1024)
    installed_gib = [math]::Round(((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Sum Capacity).Sum / 1GB), 2)
    volumes = $drives
    wsl_host_volume = $volume
    runner_running = @($runner | Where-Object State -eq 'Running').Count
    runner_running_automatic = @($runner | Where-Object { $_.State -eq 'Running' -and $_.StartMode -eq 'Auto' }).Count
    vpn_service_running = [bool]($vpn -and $vpn.Status -eq 'Running')
    vpn_online = $vpnState
    restart_maintenance_task = $task
    ac_sleep_seconds = Get-AcSetting 'SUB_SLEEP' 'STANDBYIDLE'
    ac_lid_action = Get-AcSetting 'SUB_BUTTONS' 'LIDACTION'
    codex_on_service_path = [bool](Get-Command codex -ErrorAction SilentlyContinue)
} | ConvertTo-Json -Depth 5 -Compress
