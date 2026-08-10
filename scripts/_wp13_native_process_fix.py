from __future__ import annotations

from pathlib import Path


path = Path("infrastructure/windows/rehearse_wp13_persistence.ps1")
text = path.read_text(encoding="utf-8")

old_probe = '''function Invoke-ProbeJson {
    param(
        [string]$Python,
        [string]$DatabaseName,
        [string]$Port,
        [string]$Command
    )

    $oldDsn = $env:OMNI_CIO_WP13_DSN
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=wp13_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
        $raw = & $Python $Probe $Command 2>$null
        $probeExit = $LASTEXITCODE
        $rawText = ($raw | Out-String)
        if ([string]::IsNullOrWhiteSpace($rawText)) {
            if ($probeExit -ne 0) {
                throw "WP13_PROBE_FAILED:NO_OUTPUT"
            }
            throw "WP13_PROBE_OUTPUT_EMPTY"
        }
        try {
            $parsed = ($rawText | ConvertFrom-Json)
        }
        catch {
            throw "WP13_PROBE_OUTPUT_INVALID"
        }
        if ($probeExit -ne 0) {
            $probeReason = ([string]$parsed.reason).ToUpperInvariant()
            if ([string]::IsNullOrWhiteSpace($probeReason)) {
                $probeReason = "UNKNOWN"
            }
            if ($probeReason -notmatch '^[A-Z0-9_.-]+$') {
                $probeReason = "UNKNOWN"
            }
            throw "WP13_PROBE_FAILED:$probeReason"
        }
        return $parsed
    }
    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
    }
}
'''

new_probe = '''function Invoke-ProbeJson {
    param(
        [string]$Python,
        [string]$DatabaseName,
        [string]$Port,
        [string]$Command
    )

    $oldDsn = $env:OMNI_CIO_WP13_DSN
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $env:OMNI_CIO_WP13_DSN = (
            "host=127.0.0.1 port=$Port user=wp13_owner " +
            "dbname=$DatabaseName connect_timeout=5"
        )
        $argumentLine = "`"$Probe`" $Command"
        $probeProcess = Start-Process `
            -FilePath $Python `
            -ArgumentList $argumentLine `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
        if ($null -eq $probeProcess) {
            throw "WP13_PROBE_PROCESS_MISSING"
        }
        $probeExit = $probeProcess.ExitCode
        $rawText = Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue
        if ([string]::IsNullOrWhiteSpace($rawText)) {
            if ($probeExit -ne 0) {
                throw "WP13_PROBE_FAILED:NO_OUTPUT"
            }
            throw "WP13_PROBE_OUTPUT_EMPTY"
        }
        try {
            $parsed = ($rawText | ConvertFrom-Json)
        }
        catch {
            throw "WP13_PROBE_OUTPUT_INVALID"
        }
        if ($probeExit -ne 0) {
            $probeReason = ([string]$parsed.reason).ToUpperInvariant()
            if ([string]::IsNullOrWhiteSpace($probeReason)) {
                $probeReason = "UNKNOWN"
            }
            if ($probeReason -notmatch '^[A-Z0-9_.-]+$') {
                $probeReason = "UNKNOWN"
            }
            throw "WP13_PROBE_FAILED:$probeReason"
        }
        return $parsed
    }
    finally {
        $env:OMNI_CIO_WP13_DSN = $oldDsn
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}
'''

if old_probe not in text:
    raise SystemExit("Invoke-ProbeJson block not found")
text = text.replace(old_probe, new_probe, 1)

old_corruption = '''    & $PythonPath $BundleTool verify `
        --archive $corruptArchive --manifest $corruptManifest *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "CORRUPT_ARCHIVE_ACCEPTED"
    }
    $result.corruption_rejected = $true
'''

new_corruption = '''    $corruptStdout = [System.IO.Path]::GetTempFileName()
    $corruptStderr = [System.IO.Path]::GetTempFileName()
    try {
        $corruptArguments = (
            "`"$BundleTool`" verify --archive `"$corruptArchive`" " +
            "--manifest `"$corruptManifest`""
        )
        $corruptCheck = Start-Process `
            -FilePath $PythonPath `
            -ArgumentList $corruptArguments `
            -RedirectStandardOutput $corruptStdout `
            -RedirectStandardError $corruptStderr `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
        if ($null -eq $corruptCheck) {
            throw "CORRUPT_CHECK_PROCESS_MISSING"
        }
        if ($corruptCheck.ExitCode -eq 0) {
            throw "CORRUPT_ARCHIVE_ACCEPTED"
        }
    }
    finally {
        Remove-Item `
            -LiteralPath $corruptStdout, $corruptStderr `
            -Force `
            -ErrorAction SilentlyContinue
    }
    $result.corruption_rejected = $true
'''

if old_corruption not in text:
    raise SystemExit("corruption verification block not found")
text = text.replace(old_corruption, new_corruption, 1)

path.write_text(text, encoding="utf-8", newline="\n")
