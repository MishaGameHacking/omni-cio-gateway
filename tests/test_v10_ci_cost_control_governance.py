from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
STANDARD_PATH = ROOT / "docs" / "operations" / "V10_CI_COST_CONTROL_STANDARD.md"
FAST_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "v10-pr-fast-checks.yml"
TOOLCHAIN_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "v10-toolchain-compat.yml"
LIVE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "live-gateway-authority.yml"
LIVE_CONTRACT_WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "v10-live-gateway-authority-contract.yml"
)


def test_ci_cost_control_requires_explicit_owner_spend_approval() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]

    assert cost["standard"] == "docs/operations/V10_CI_COST_CONTROL_STANDARD.md"
    assert cost["owner_budget_or_payment_mutation_requires_explicit_approval"] is True
    assert cost["disable_stop_usage_without_owner_approval_allowed"] is False
    assert (
        cost["if_paid_hosted_execution_is_required"]
        == "EXPLICIT_OWNER_DECISION_WITH_COST_AND_REASON_BEFORE_MUTATION"
    )


def test_budget_block_is_not_code_failure_and_not_merge_bypass() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]
    merge = contract["merge_gate"]

    assert cost["known_zero_budget_hard_stop_is_code_failure"] is False
    assert cost["billing_red_may_not_be_merged_around"] is True
    assert merge["billing_failure_blocks_merge"] is True
    assert merge["accepted_check_conclusions"] == ["success"]


def test_zero_cost_routing_cannot_silently_remove_clean_room_semantics() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]

    assert cost["zero_cost_routing_preferred_when_semantically_equivalent"] is True
    assert cost["self_hosted_lenovo_preferred_for_heavy_repeatable_validation"] is True
    assert cost["hosted_clean_room_semantics_may_not_be_silently_dropped"] is True
    assert (
        cost["known_budget_blocked_hosted_job_must_not_be_triggered_as_applicable_gate"]
        is True
    )
    assert cost["scheduled_hosted_jobs_while_blocked_forbidden"] is True
    assert cost["hosted_compatibility_absence_blocks_pr_merge"] is False
    assert cost["hosted_compatibility_absence_blocks_stable_release_evidence"] is True


def test_capacity_deferred_jobs_execute_without_fabricating_clean_room_pass() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]
    fast = FAST_WORKFLOW_PATH.read_text(encoding="utf-8")
    toolchain = TOOLCHAIN_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert cost["current_hosted_capacity_state"] == "BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP"
    assert (
        cost["hosted_compatibility_check_mode_when_blocked"]
        == "EXECUTED_CAPACITY_ROUTING_NO_CLEAN_ROOM_PASS"
    )
    assert cost["non_applicable_or_capacity_deferred_job_must_execute_and_report"] is True
    assert cost["job_level_skipped_is_green_evidence"] is False
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in fast
    assert "Fast frontend substantive checks NOT_APPLICABLE" in fast
    assert "CURRENTLY_CAPACITY_BLOCKED" in toolchain
    assert "does NOT claim Python 3.14.6 clean-room compatibility PASS" in toolchain
    assert "does NOT claim disposable hosted Node compatibility PASS" in toolchain
    assert "runs-on: windows-latest" not in toolchain


def test_windows_fast_cleanup_uses_job_local_native_shell() -> None:
    fast = FAST_WORKFLOW_PATH.read_text(encoding="utf-8")

    for cleanup_name in (
        "Clean routing workspace",
        "Clean policy workspace",
        "Clean frontend workspace",
    ):
        assert (
            f"- name: {cleanup_name}\n"
            "        if: always()\n"
            "        shell: cmd"
            in fast
        )


def test_live_v9_authority_is_deferred_not_fabricated_on_lenovo() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]
    live = LIVE_WORKFLOW_PATH.read_text(encoding="utf-8")
    routing = LIVE_CONTRACT_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert (
        cost["live_v9_authority_current_evidence_state"]
        == "DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS"
    )
    assert cost["live_v9_authority_lenovo_route_semantically_equivalent"] is False
    assert cost["live_v9_authority_actual_probe_must_not_run_on_personal_node"] is True
    assert cost["live_v9_authority_automatic_schedule_while_deferred_forbidden"] is True
    assert cost["live_v9_authority_manual_hosted_workflow_preserved"] is True
    assert cost["live_v9_authority_pr_contract_workflow_required"] is True
    assert cost["live_v9_authority_missing_blocks_v9_runtime_or_authority_release"] is True
    assert cost["live_v9_authority_missing_blocks_governance_only_pr_merge"] is False
    assert cost["restore_live_v9_automation_requires_trusted_route_reverification"] is True

    assert "workflow_dispatch:" in live
    assert "schedule:" not in live
    assert "pull_request:" not in live
    assert "runs-on: ubuntu-latest" in live
    assert "self-hosted" not in live
    assert "python scripts/check_live_gateway_authority.py" in live

    assert "pull_request:" in routing
    assert "runs-on: [self-hosted, Windows, X64, omni-cio-ci]" in routing
    assert "ACTUAL_V9_LIVE_AUTHORITY_EVIDENCE=DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE" in routing
    assert "SUCCESS_DOES_NOT_CLAIM_DEPLOYED_LIVE_PASS" in routing
    # The probe source belongs in pull_request.paths so changes retrigger this
    # contract. What must remain absent is an execution command on Lenovo.
    assert "python scripts/check_live_gateway_authority.py" not in routing
    assert "python scripts\\check_live_gateway_authority.py" not in routing


def test_budget_state_is_explicitly_mutable_external_state() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]
    standard = STANDARD_PATH.read_text(encoding="utf-8")

    assert cost["mutable_external_budget_state_must_be_reverified"] is True
    assert cost["restore_hosted_lanes_requires_state_reverification"] is True
    assert "time-bounded external-state observation" in standard
    assert "USD 0" in standard
    assert "Stop usage = Yes" in standard
    assert "not an immutable architecture constant" in standard


def test_standard_forbids_predictable_red_and_false_live_evidence() -> None:
    standard = STANDARD_PATH.read_text(encoding="utf-8")

    assert "do not silently increase the budget" in standard
    assert "do not disable `Stop usage when budget limit is reached`" in standard
    assert "do not repeatedly trigger a hosted workflow" in standard
    assert "do not merge around the RED check" in standard
    assert "explicit OWNER decision" in standard
    assert "Capacity-deferred compatibility mode" in standard
    assert "job-level GitHub `skipped` result is not accepted" in standard
    assert "Live V9 authority evidence while capacity is blocked" in standard
    assert "DEFERRED_NO_TRUSTED_ZERO_COST_ROUTE_NOT_PASS" in standard
    assert "must never be presented as PASS" in standard
    assert "V9 runtime/deployment/Action-authority release" in standard
    assert "STABLE release" in standard
