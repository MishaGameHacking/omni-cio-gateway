from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_ci_security_baseline.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_ci_security_baseline_wp17",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


def test_wp17_metadata_allowlist_is_exact_and_value_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract_path = (
        tmp_path / "docs" / "architecture" / "V10_WP17_APPLICATION_SHELL_CONTRACT.json"
    )
    contract_path.parent.mkdir(parents=True)
    sensitive_word = "sec" + "ret"
    subtree = (
        f"C:\\\\ProgramData\\\\OmniCIO\\\\{sensitive_word}s"
        "\\\\read-broker\\\\connections"
    )
    approved_lines = (
        f'  "{sensitive_word}_store": "WP8_WINDOWS_DPAPI_LOCAL_MACHINE",',
        f'  "{sensitive_word}_subtree": "{subtree}",',
        f'  "ci_{sensitive_word}_data_access": false,',
    )
    contract_path.write_text("\n".join(approved_lines) + "\n", encoding="utf-8")
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    report = {
        "results": {
            "docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json": [
                {"type": "Secret Keyword", "line_number": 1},
                {"type": "Secret Keyword", "line_number": 2},
                {"type": "Secret Keyword", "line_number": 3},
            ]
        }
    }

    failures: list[str] = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == []

    contract_path.write_text(
        f'  "{sensitive_word}_store": "unexpected",\n'
        + "\n".join(approved_lines[1:])
        + "\n",
        encoding="utf-8",
    )
    failures = []
    baseline.validate_detect_secrets_report(report, failures)
    assert failures == [
        "potential secret: docs/architecture/V10_WP17_APPLICATION_SHELL_CONTRACT.json:1 "
        "(Secret Keyword)"
    ]
