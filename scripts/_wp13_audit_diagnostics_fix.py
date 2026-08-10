from __future__ import annotations

from pathlib import Path


path = Path("infrastructure/windows/rehearse_wp13_persistence.ps1")
text = path.read_text(encoding="utf-8")

old_probe = '''        $raw = & $Python $Probe $Command 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "WP13_PROBE_FAILED"
        }
        try {
            return (($raw | Out-String) | ConvertFrom-Json)
        }
        catch {
            throw "WP13_PROBE_OUTPUT_INVALID"
        }
'''
new_probe = '''        $raw = & $Python $Probe $Command 2>$null
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
if old_probe not in text:
    raise SystemExit("Invoke-ProbeJson block not found")
text = text.replace(old_probe, new_probe, 1)

old_print = '''    Write-Output "Append-only rejection: $($Result.append_only_rejection)"
    Write-Output "Backup integrity: $($Result.backup_integrity_pass)"
'''
new_print = '''    Write-Output "Append-only rejection: $($Result.append_only_rejection)"
    Write-Output "Concurrent write idempotency: $($Result.concurrent_write_idempotency)"
    Write-Output "Backup integrity: $($Result.backup_integrity_pass)"
'''
if old_print not in text:
    raise SystemExit("Write-Result anchor not found")
text = text.replace(old_print, new_print, 1)

old_result = '''    conflicting_replay_rejected = $false
    owner_scope_rejection = $false
'''
new_result = '''    conflicting_replay_rejected = $false
    concurrent_write_idempotency = $false
    owner_scope_rejection = $false
'''
if old_result not in text:
    raise SystemExit("result map anchor not found")
text = text.replace(old_result, new_result, 1)

old_source = '''    $result.conflicting_replay_rejected = [bool]$source.conflicting_replay_rejected
    $result.owner_scope_rejection = [bool]$source.owner_scope_rejection
'''
new_source = '''    $result.conflicting_replay_rejected = [bool]$source.conflicting_replay_rejected
    $result.concurrent_write_idempotency = [bool]$source.concurrent_write_idempotency
    $result.owner_scope_rejection = [bool]$source.owner_scope_rejection
'''
if old_source not in text:
    raise SystemExit("source evidence anchor not found")
text = text.replace(old_source, new_source, 1)

old_assert = '''        -not $result.conflicting_replay_rejected -or
        -not $result.owner_scope_rejection -or
'''
new_assert = '''        -not $result.conflicting_replay_rejected -or
        -not $result.concurrent_write_idempotency -or
        -not $result.owner_scope_rejection -or
'''
if old_assert not in text:
    raise SystemExit("assertion anchor not found")
text = text.replace(old_assert, new_assert, 1)

path.write_text(text, encoding="utf-8", newline="\n")
