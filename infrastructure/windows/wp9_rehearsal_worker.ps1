[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StatePath,
    [string]$DependencyPath = "",
    [ValidateRange(5, 600)]
    [int]$HoldSeconds = 120
)

Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

function Write-State {
    param(
        [int]$RunCount,
        [string]$State,
        [int]$ProcessId = $PID
    )

    $payload = [ordered]@{
        schema_version = "1"
        run_count = $RunCount
        process_id = $ProcessId
        state = $State
        observed_at_utc = [datetime]::UtcNow.ToString("o")
    }
    $parent = Split-Path -Parent $StatePath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "WP9_REHEARSAL_STATE_DIRECTORY_MISSING"
    }
    $temporary = "$StatePath.tmp"
    $payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $StatePath -Force
}

$runCount = 0
if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    try {
        $existing = Get-Content -LiteralPath $StatePath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        $runCount = [int]$existing.run_count
    }
    catch {
        $runCount = 0
    }
}
$runCount += 1

if (-not [string]::IsNullOrWhiteSpace($DependencyPath)) {
    if (-not (Test-Path -LiteralPath $DependencyPath -PathType Leaf)) {
        Write-State -RunCount $runCount -State "BLOCKED"
        exit 42
    }
    Write-State -RunCount $runCount -State "RECOVERED"
    exit 0
}

if ($runCount -eq 1) {
    # Task Scheduler restart-on-failure is driven by the registered action's exit
    # status. The rehearsal therefore kills a synthetic child process while this
    # registered wrapper remains alive, observes that child exit, and then exits
    # non-zero. This proves both the required process-kill scenario and the actual
    # Scheduler restart policy instead of relying on how Scheduler classifies an
    # externally terminated registered action.
    $powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $childArguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds {0}"' -f $HoldSeconds
    $child = Start-Process `
        -FilePath $powershellExe `
        -ArgumentList $childArguments `
        -PassThru `
        -WindowStyle Hidden
    Write-State `
        -RunCount $runCount `
        -State "RUNNING_FIRST_ATTEMPT" `
        -ProcessId ([int]$child.Id)
    Wait-Process -Id $child.Id -ErrorAction Stop
    Write-State -RunCount $runCount -State "FIRST_ATTEMPT_FAILED_AFTER_CHILD_EXIT"
    exit 41
}

Write-State -RunCount $runCount -State "RECOVERED"
exit 0
