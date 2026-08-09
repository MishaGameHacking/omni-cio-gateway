[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$StatePath,
    [string]$DependencyPath = "",
    [ValidateRange(5, 600)]
    [int]$HoldSeconds = 120,
    [ValidateRange(1, 10)]
    [int]$MaxAttempts = 3,
    [ValidateRange(1, 600)]
    [int]$BackoffSeconds = 60
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

function Start-SyntheticChild {
    param([int]$Seconds)

    $powershellExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds {0}"' -f $Seconds
    return Start-Process `
        -FilePath $powershellExe `
        -ArgumentList $arguments `
        -PassThru `
        -WindowStyle Hidden
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

# The registered Task Scheduler action stays alive as a bounded supervisor while
# the provisioner kills a synthetic child process. This directly proves the
# required kill/recover behavior with an explicit backoff/max-attempt boundary,
# independent of how Task Scheduler classifies an externally terminated action.
if ($runCount -eq 1) {
    $firstStartedUtc = [datetime]::UtcNow
    $child = Start-SyntheticChild -Seconds $HoldSeconds
    Write-State `
        -RunCount 1 `
        -State "RUNNING_FIRST_ATTEMPT" `
        -ProcessId ([int]$child.Id)
    Wait-Process -Id $child.Id -ErrorAction Stop

    $elapsedSeconds = ([datetime]::UtcNow - $firstStartedUtc).TotalSeconds
    if ($elapsedSeconds -ge ($HoldSeconds - 2)) {
        Write-State -RunCount 1 -State "FIRST_ATTEMPT_COMPLETED_UNEXPECTEDLY"
        exit 41
    }

    for ($attempt = 2; $attempt -le $MaxAttempts; $attempt += 1) {
        Start-Sleep -Seconds $BackoffSeconds
        $replacement = Start-SyntheticChild -Seconds 2
        Write-State `
            -RunCount $attempt `
            -State "RECOVERED" `
            -ProcessId ([int]$replacement.Id)
        Wait-Process -Id $replacement.Id -ErrorAction Stop
        $replacement.Refresh()
        if ([int]$replacement.ExitCode -eq 0) {
            exit 0
        }
    }

    Write-State -RunCount $MaxAttempts -State "RECOVERY_ATTEMPTS_EXHAUSTED"
    exit 41
}

Write-State -RunCount $runCount -State "RECOVERED"
exit 0
