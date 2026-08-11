from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVISIONER = (
    ROOT / "infrastructure" / "windows" / "provision_wp15_live_web_acceptance.ps1"
)


def test_wp15_live_provisioner_scopes_nonfatal_npm_stderr_compatibility() -> None:
    text = PROVISIONER.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in text

    marker = "# Windows PowerShell 5.1 maps native stderr into its Error stream."
    start = text.index(marker)
    end = text.index("& $pythonMachine -m venv $venvRoot", start)
    npm_block = text[start:end]

    assert "$previousNativeErrorActionPreference = $ErrorActionPreference" in npm_block
    assert '$ErrorActionPreference = "Continue"' in npm_block
    assert (
        "$ErrorActionPreference = $previousNativeErrorActionPreference" in npm_block
    )
    assert "& $npmCmd ci --ignore-scripts --no-audit --no-fund *> $null" in npm_block
    assert "& $npmCmd run typecheck *> $null" in npm_block
    assert "& $npmCmd run build *> $null" in npm_block
    assert npm_block.count("*> $null") == 3

    restore_at = npm_block.index(
        "$ErrorActionPreference = $previousNativeErrorActionPreference"
    )
    build_at = npm_block.index("& $npmCmd run build *> $null")
    assert restore_at > build_at


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 compatibility probe")
def test_windows_powershell_native_stderr_exit_zero_does_not_terminate_scope() -> None:
    script = r'''
$ErrorActionPreference = "Stop"
$previousNativeErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & $env:ComSpec /d /c "echo npm notice 1>&2 & exit /b 0" *> $null
    $nativeExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousNativeErrorActionPreference
}
if ($nativeExitCode -ne 0) { exit 10 }
if ($ErrorActionPreference -ne "Stop") { exit 11 }
exit 0
'''
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
