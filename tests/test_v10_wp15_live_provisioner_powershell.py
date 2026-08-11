from __future__ import annotations

from pathlib import Path


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
