from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "architecture" / "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
STANDARD = ROOT / "docs" / "operations" / "V10_CI_COST_CONTROL_STANDARD.md"
COPILOT_POLICY = (
    ROOT / ".github" / "instructions" / "owner-handoff-and-runtime.instructions.md"
)
LEDGER = ROOT / "docs" / "operations" / "V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md"
FAST_WORKFLOW = ROOT / ".github" / "workflows" / "v10-pr-fast-checks.yml"
TOOLCHAIN_WORKFLOW = ROOT / ".github" / "workflows" / "v10-toolchain-compat.yml"
LIVE_WORKFLOW = ROOT / ".github" / "workflows" / "live-gateway-authority.yml"
WARM_LIVE_SCRIPT = ROOT / "scripts" / "warm_live_gateway.ps1"


def main() -> int:
    failures: list[str] = []

    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(
            f"V10 CI cost-control guard failed: cannot load contract: {exc}",
            file=sys.stderr,
        )
        return 1

    cost = contract.get("ci_cost_control")
    if not isinstance(cost, dict):
        failures.append("ci_cost_control contract section is missing")
    else:
        expected_true = (
            "owner_budget_or_payment_mutation_requires_explicit_approval",
            "known_budget_blocked_hosted_job_must_not_be_triggered_as_applicable_gate",
            "scheduled_hosted_jobs_while_blocked_forbidden",
            "zero_cost_routing_preferred_when_semantically_equivalent",
            "self_hosted_lenovo_preferred_for_heavy_repeatable_validation",
            "hosted_clean_room_semantics_may_not_be_silently_dropped",
            "billing_red_may_not_be_merged_around",
            "mutable_external_budget_state_must_be_reverified",
            "fast_policy_self_hosted_fallback_allowed_when_blocked",
            "hosted_compatibility_absence_blocks_stable_release_evidence",
            "non_applicable_or_capacity_deferred_job_must_execute_and_report",
            "restore_hosted_lanes_requires_state_reverification",
        )
        for key in expected_true:
            if cost.get(key) is not True:
                failures.append(f"ci_cost_control.{key} must be True")

        expected_false = (
            "known_zero_budget_hard_stop_is_code_failure",
            "disable_stop_usage_without_owner_approval_allowed",
            "hosted_compatibility_absence_blocks_pr_merge",
            "job_level_skipped_is_green_evidence",
        )
        for key in expected_false:
            if cost.get(key) is not False:
                failures.append(f"ci_cost_control.{key} must be False")

        if cost.get("standard") != "docs/operations/V10_CI_COST_CONTROL_STANDARD.md":
            failures.append("ci_cost_control standard path mismatch")
        if (
            cost.get("if_paid_hosted_execution_is_required")
            != "EXPLICIT_OWNER_DECISION_WITH_COST_AND_REASON_BEFORE_MUTATION"
        ):
            failures.append(
                "paid hosted execution must require explicit OWNER cost decision"
            )
        if (
            cost.get("current_hosted_capacity_state")
            != "BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP"
        ):
            failures.append(
                "current hosted capacity state must match the OWNER-observed hard stop"
            )
        if (
            cost.get("hosted_compatibility_check_mode_when_blocked")
            != "EXECUTED_CAPACITY_ROUTING_NO_CLEAN_ROOM_PASS"
        ):
            failures.append(
                "blocked hosted compatibility must use executed routing without "
                "claiming clean-room PASS"
            )

    merge = contract.get("merge_gate")
    if (
        not isinstance(merge, dict)
        or merge.get("billing_failure_blocks_merge") is not True
    ):
        failures.append("billing RED must remain merge-blocking")
    if not isinstance(merge, dict) or merge.get("accepted_check_conclusions") != [
        "success"
    ]:
        failures.append("applicable merge checks must remain SUCCESS-only")

    for path, markers in (
        (
            STANDARD,
            (
                "Zero-budget law",
                "do not silently increase the budget",
                "do not repeatedly trigger a hosted workflow",
                "do not merge around the RED check",
                "explicit OWNER decision",
                "Capacity-deferred compatibility mode",
                "REQUIRED_BY_PATH_BUT_CAPACITY_BLOCKED",
                "must not claim",
                "job-level GitHub `skipped` result is not accepted",
                "STABLE release",
            ),
        ),
        (
            COPILOT_POLICY,
            (
                "OWNER billing / CI cost control",
                "Never silently increase a GitHub/provider budget",
                "do not merge around the RED applicable check",
            ),
        ),
        (
            LEDGER,
            (
                "FL-006",
                "Zero-budget hard stop is a CI-routing constraint, not a merge bypass",
                "FL-009",
                "Self-hosted PowerShell steps must respect the node execution policy",
                "FL-010",
                "Windows cleanup must not depend on implicit Bash PATH",
            ),
        ),
        (
            FAST_WORKFLOW,
            (
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
                "Fast frontend substantive checks NOT_APPLICABLE",
                "process.version !== 'v24.18.0'",
                "11.16.0",
            ),
        ),
        (
            TOOLCHAIN_WORKFLOW,
            (
                "Python 3.14.6 clean-room applicability contract",
                "Node 24.18.0 clean-room applicability contract",
                "CURRENTLY_CAPACITY_BLOCKED",
                "does NOT claim",
                "Stable release provenance must not fabricate",
            ),
        ),
        (
            LIVE_WORKFLOW,
            (
                "schedule:",
                "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
                "Bootstrap protected runner Python 3.12.10",
                "Build strict Windows runtime dependency projection",
                "python scripts\\windows_ci_lock.py project requirements.txt windows-requirements.txt",
                "--require-hashes -r windows-requirements.txt",
                "Warm protected V9 gateway across bounded Render cold start",
                "powershell.exe -NoProfile -ExecutionPolicy Bypass",
                "-File scripts\\warm_live_gateway.ps1",
                "Verify deployed v9 Action authority without broker mutation",
                "persist-credentials: false",
            ),
        ),
        (
            WARM_LIVE_SCRIPT,
            (
                '$baseUri.Scheme -ne "https"',
                '$baseUri.Host -ne "omni-cio-gateway.onrender.com"',
                "AddSeconds($DeadlineSeconds)",
                "Invoke-WebRequest",
                "-TimeoutSec $RequestTimeoutSeconds",
                "Start-Sleep -Seconds $RetryDelaySeconds",
                "exit 41",
            ),
        ),
    ):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        for marker in markers:
            if marker not in text:
                failures.append(f"{path.relative_to(ROOT)} missing marker: {marker}")

    try:
        fast_workflow = FAST_WORKFLOW.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {FAST_WORKFLOW.relative_to(ROOT)}: {exc}")
    else:
        for cleanup_name in (
            "Clean routing workspace",
            "Clean policy workspace",
            "Clean frontend workspace",
        ):
            cleanup_contract = (
                f"- name: {cleanup_name}\n"
                "        if: always()\n"
                "        shell: cmd"
            )
            if cleanup_contract not in fast_workflow:
                failures.append(
                    f"{FAST_WORKFLOW.relative_to(ROOT)} must use native cmd cleanup for {cleanup_name}"
                )

    try:
        live_workflow = LIVE_WORKFLOW.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {LIVE_WORKFLOW.relative_to(ROOT)}: {exc}")
    else:
        if "--require-hashes -r requirements.txt" in live_workflow:
            failures.append(
                "Windows live-authority workflow must not install the POSIX runtime lock directly"
            )

    if failures:
        print("V10 CI cost-control guard failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 CI cost-control guard passed.")
    print("OWNER billing mutation: explicit approval only")
    print("Hosted capacity state: BLOCKED_OWNER_ZERO_BUDGET_HARD_STOP")
    print("Fast deterministic checks: zero-cost Lenovo continuity mode")
    print("Windows fast cleanup: native cmd; no cross-job Bash PATH dependency")
    print("Scheduled live-authority probe: zero-cost Lenovo continuity mode")
    print("Windows live probe dependencies: projected from the canonical runtime lock")
    print("Render cold-start wake window: bounded before strict live authority verification")
    print("Hosted compatibility: executed routing check; no clean-room PASS fabricated")
    print("Stable release compatibility evidence: still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
