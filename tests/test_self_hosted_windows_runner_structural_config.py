from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_self_hosted_windows_runner_service.ps1"


def _run(powershell: str, runner_root: Path) -> dict[str, object]:
    result = subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-RunnerRoot",
            str(runner_root),
            "-ExpectedRunnerName",
            "omni-ci-test-fixture",
            "-AsJson",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 2
    return json.loads(result.stdout.strip())


def test_null_or_empty_array_runner_configuration_has_typed_failure(
    tmp_path: Path,
) -> None:
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        return

    (tmp_path / "run.cmd").write_text("@echo off\n", encoding="utf-8")

    for raw_json in ("null", "[]"):
        (tmp_path / ".runner").write_text(raw_json, encoding="utf-8")
        payload = _run(powershell, tmp_path)
        assert payload["error_code"] == "RUNNER_CONFIGURATION_INVALID"
        assert payload["runner_configuration_error_detail"] == "AGENT_NAME_INVALID"
        assert payload["runner_configuration_valid"] is False
        assert payload["runner_ephemeral"] is None
