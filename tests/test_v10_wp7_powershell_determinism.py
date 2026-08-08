from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_ASSETS = (
    ROOT / "infrastructure" / "windows" / "bootstrap-v10.ps1",
    ROOT / "infrastructure" / "windows" / "rollback_wp7_bootstrap.ps1",
    ROOT / "scripts" / "check_v10_wp7_runner_health.ps1",
)


def test_wp7_powershell_strict_mode_is_version_pinned() -> None:
    for path in POWERSHELL_ASSETS:
        text = path.read_text(encoding="utf-8")
        assert "Set-StrictMode -Version 3.0" in text, path
        assert "Set-StrictMode -Version Latest" not in text, path
