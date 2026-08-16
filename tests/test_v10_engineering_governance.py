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
OWNER_STANDARD_PATH = (
    ROOT / "docs" / "operations" / "V10_OWNER_ACTION_HANDOFF_STANDARD.md"
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
    assert "OWNER handoff: direct official link" in completed.stdout
    assert "Render.com not V10 hosting target" in completed.stdout


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


def test_owner_handoff_requires_direct_verified_link_and_stop_contract() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    handoff = contract["owner_handoff"]

    assert handoff["direct_official_link_required_when_stable"] is True
    assert handoff["generic_navigation_without_link_sufficient"] is False
    assert handoff["owner_must_not_be_required_to_discover_target_page"] is True
    assert handoff["expected_result_required"] is True
    assert handoff["stop_conditions_required"] is True
    assert handoff["do_not_do_warnings_required"] is True
    assert handoff["minimum_safe_return_required"] is True

    text = OWNER_STANDARD_PATH.read_text(encoding="utf-8")
    assert "Direct-link-first law" in text
    assert "Mandatory OWNER handoff format" in text


def test_v10_runtime_is_personal_node_not_render_com() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    runtime = contract["runtime_hosting"]

    assert runtime["v10_primary_host"] == "APPROVED_LENOVO_OR_REPLACEMENT_PERSONAL_NODE"
    assert runtime["v10_web_built_and_served_on_personal_node"] is True
    assert runtime["separate_paid_cloud_web_host_required_for_v10"] is False
    assert runtime["render_com_v10_runtime_target"] is False
    assert runtime["render_com_new_workspace_authoritative"] is False
    assert runtime["render_com_new_v10_service_without_owner_amendment_allowed"] is False
    assert runtime["protected_v9_render_app_app_baseline_preserved"] is True
    assert runtime["external_access_provider_may_become_private_state_host"] is False


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


def test_validator_rejects_owner_handoff_without_direct_link_requirement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["owner_handoff"]["direct_official_link_required_when_stable"] = False
    modified = tmp_path / "quality-contract.json"
    modified.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(governance, "CONTRACT", modified)
    failures: list[str] = []

    governance.validate_contract(failures)

    assert any(
        "direct_official_link_required_when_stable must be True" in failure
        for failure in failures
    )


def test_validator_rejects_render_com_as_v10_runtime_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["runtime_hosting"]["render_com_v10_runtime_target"] = True
    modified = tmp_path / "quality-contract.json"
    modified.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setattr(governance, "CONTRACT", modified)
    failures: list[str] = []

    governance.validate_contract(failures)

    assert any(
        "render_com_v10_runtime_target must be False" in failure
        for failure in failures
    )
