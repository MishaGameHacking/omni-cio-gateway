from __future__ import annotations

from pathlib import Path


path = Path("infrastructure/windows/rehearse_wp13_persistence.ps1")
text = path.read_text(encoding="utf-8")

old_probe = '''        $raw = & $Python $Probe $Command 2>$null
        $probeExit = $LASTEXITCODE
        try {
            $parsed = (($raw | Out-String) | ConvertFrom-Json)
        }
        catch {
            throw "WP13_PROBE_OUTPUT_INVALID"
        }
        if ($probeExit -ne 0) {
            $probeReason = ([string]$parsed.reason).ToUpperInvariant()
            if ($probeReason -notmatch '^[A-Z0-9_.-]+$') {
                $probeReason = "UNKNOWN"
            }
            throw "WP13_PROBE_FAILED:$probeReason"
        }
        return $parsed
'''
new_probe = '''        $raw = & $Python $Probe $Command 2>$null
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
'''
if old_probe not in text:
    raise SystemExit("probe diagnostic block not found")
text = text.replace(old_probe, new_probe, 1)

old_catch = '''catch {
    $message = [string]$_.Exception.Message
    if ($message -notmatch '^[A-Z0-9_:\\-]+$') {
        $message = "WP13_AUDIT_ERROR"
    }
    $result.status = "FAIL"
    $result.reason_code = $message
}
'''
new_catch = '''catch {
    $message = [string]$_.Exception.Message
    if ($message -match '^[A-Z0-9_:\\-]+$') {
        $reasonCode = $message
    }
    else {
        $exceptionType = ([string]$_.Exception.GetType().Name).ToUpperInvariant()
        if ($exceptionType -notmatch '^[A-Z0-9_.-]+$') {
            $exceptionType = "UNKNOWN"
        }
        $errorId = ([string]$_.FullyQualifiedErrorId).ToUpperInvariant()
        if ([string]::IsNullOrWhiteSpace($errorId) -or $errorId -notmatch '^[A-Z0-9_.-]+$') {
            $errorId = "UNKNOWN"
        }
        $reasonCode = "WP13_AUDIT_ERROR:$exceptionType:$errorId"
    }
    $result.status = "FAIL"
    $result.reason_code = $reasonCode
}
'''
if old_catch not in text:
    raise SystemExit("outer catch block not found")
text = text.replace(old_catch, new_catch, 1)

path.write_text(text, encoding="utf-8", newline="\n")
