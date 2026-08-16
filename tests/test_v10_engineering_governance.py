from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "check_v10_engineering_governance.py"
CONTRACT_PATH = (
    ROOT / "docs" / "architecture" / "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
)
SPEC = importlib.util.spec_from_file_location(
    "check_v10_engineering_governance",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
governance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(governance)


def test_current_repository_satisfies_engineering_governance() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert (
        "Exact-head applicable checks: SUCCESS-only project policy"
        in completed.stdout
    )
    assert (
        "OWNER product acceptance: post-merge/post-Regression-Shield"
        in completed.stdout
    )


def test_contract_accepts_only_success_for_applicable_merge_checks() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract["merge_gate"]["accepted_check_conclusions"] == ["success"]
    assert {"skipped", "neutral", "cancelled", "failure"} <= set(
        contract["merge_gate"]["rejected_as_green"]
    )
    assert contract["merge_gate"]["infrastructure_failure_blocks_merge"] is True
    assert contract["merge_gate"]["billing_failure_blocks_merge"] is True


def test_contract_forbids_owner_product_acceptance_before_merge() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    owner = contract["owner_participation"]

    assert owner["product_acceptance_before_implementation_merge"] is False
    assert owner["product_acceptance_before_post_merge_green"] is False
    assert owner["pre_merge_exception"] == "GENUINELY_NON_DELEGABLE_PREREQUISITE_ONLY"


def test_validator_rejects_neutral_as_accepted_green(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["merge_gate"]["accepted_check_conclusions"] = ["success", "neutral"]
    modified = tmp_path / "quality-contract.json"
    modified.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(governance, "CONTRACT", modified)
    failures: list[str] = []

    governance.validate_contract(failures)

    assert "merge_gate accepts conclusions other than success" in failures


def test_validator_rejects_premature_owner_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["owner_participation"][
        "product_acceptance_before_implementation_merge"
    ] = True
    modified = tmp_path / "quality-contract.json"
    modified.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(governance, "CONTRACT", modified)
    failures: list[str] = []

    governance.validate_contract(failures)

    assert any(
        "product_acceptance_before_implementation_merge must be False" in failure
        for failure in failures
    )
