from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "check_v10_toolchain_baseline.py"
)
SPEC = importlib.util.spec_from_file_location(
    "check_v10_toolchain_baseline", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
toolchain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(toolchain)


def test_current_repository_satisfies_v10_toolchain_contract() -> None:
    failures: list[str] = []
    baseline = toolchain._load_json(toolchain.BASELINE_PATH, failures)

    toolchain.validate_python_baseline(baseline, failures)
    toolchain.validate_frontend_baseline(baseline, failures)
    toolchain.validate_database_baseline(baseline, failures)

    assert failures == []


@pytest.mark.parametrize("version", ["^19.2.8", "~19.2.8", ">=19", "latest"])
def test_frontend_direct_versions_must_be_exact(version: str) -> None:
    failures: list[str] = []

    toolchain._require_exact_direct_version("react", version, failures)

    assert failures
    assert "must use exact version" in failures[0]


def test_python_direct_requirements_reject_unpinned_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requirements = tmp_path / "requirements.in"
    requirements.write_text("fastapi>=0.141.1\n", encoding="utf-8")
    monkeypatch.setattr(toolchain, "REQUIREMENTS_IN", requirements)
    failures: list[str] = []

    pins = toolchain._requirements_pins(failures)

    assert pins == {}
    assert failures == [
        "requirements.in:1 must use an exact == direct pin: fastapi>=0.141.1"
    ]
