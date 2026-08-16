from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
STANDARD_PATH = ROOT / "docs" / "operations" / "V10_CI_COST_CONTROL_STANDARD.md"


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
    assert cost["known_budget_blocked_hosted_job_must_not_be_triggered_as_applicable_gate"] is True


def test_budget_state_is_explicitly_mutable_external_state() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    cost = contract["ci_cost_control"]
    standard = STANDARD_PATH.read_text(encoding="utf-8")

    assert cost["mutable_external_budget_state_must_be_reverified"] is True
    assert "time-bounded external-state observation" in standard
    assert "USD 0" in standard
    assert "Stop usage = Yes" in standard
    assert "not an immutable architecture constant" in standard


def test_standard_forbids_predictable_hosted_red_and_implicit_spend() -> None:
    standard = STANDARD_PATH.read_text(encoding="utf-8")

    assert "do not silently increase the budget" in standard
    assert "do not disable `Stop usage when budget limit is reached`" in standard
    assert "do not repeatedly trigger a hosted workflow" in standard
    assert "do not merge around the RED check" in standard
    assert "explicit OWNER decision" in standard
