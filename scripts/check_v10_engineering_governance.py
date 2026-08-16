from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
CONTRACT = ROOT / "docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
LEDGER = ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
COPILOT = ROOT / ".github/copilot-instructions.md"
WP_TEMPLATE = ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"


def _load_text(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(
            f"missing engineering governance file: {path.relative_to(ROOT)}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _require_markers(
    path: Path,
    text: str,
    markers: tuple[str, ...],
    failures: list[str],
) -> None:
    for marker in markers:
        if marker not in text:
            failures.append(
                f"{path.relative_to(ROOT)} is missing governance marker: {marker}"
            )


def _expect_bool(
    obj: dict[str, Any],
    key: str,
    expected: bool,
    context: str,
    failures: list[str],
) -> None:
    if obj.get(key) is not expected:
        failures.append(f"{context}.{key} must be {expected!r}")


def validate_contract(failures: list[str]) -> None:
    text = _load_text(CONTRACT, failures)
    if not text:
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid engineering quality contract JSON: {exc}")
        return

    if data.get("schema") != "omni-cio.v10.engineering-quality-gate.v1":
        failures.append("engineering quality contract schema mismatch")

    pre_ci = data.get("pre_ci")
    merge_gate = data.get("merge_gate")
    owner = data.get("owner_participation")
    learning = data.get("failure_learning")
    isolation = data.get("fault_isolation")
    protected = data.get("protected_invariants")

    for name, section in (
        ("pre_ci", pre_ci),
        ("merge_gate", merge_gate),
        ("owner_participation", owner),
        ("failure_learning", learning),
        ("fault_isolation", isolation),
        ("protected_invariants", protected),
    ):
        if not isinstance(section, dict):
            failures.append(
                f"engineering quality contract section must be object: {name}"
            )
            return

    assert isinstance(pre_ci, dict)
    assert isinstance(merge_gate, dict)
    assert isinstance(owner, dict)
    assert isinstance(learning, dict)
    assert isinstance(isolation, dict)
    assert isinstance(protected, dict)

    _expect_bool(pre_ci, "required", True, "pre_ci", failures)
    _expect_bool(pre_ci, "ci_is_primary_debugger", False, "pre_ci", failures)
    _expect_bool(pre_ci, "root_cause_before_fix", True, "pre_ci", failures)
    _expect_bool(pre_ci, "blast_radius_search", True, "pre_ci", failures)
    _expect_bool(
        pre_ci,
        "regression_guard_required_for_material_defect",
        True,
        "pre_ci",
        failures,
    )

    if merge_gate.get("accepted_check_conclusions") != ["success"]:
        failures.append("merge_gate accepts conclusions other than success")
    _expect_bool(merge_gate, "exact_head_only", True, "merge_gate", failures)
    _expect_bool(
        merge_gate,
        "all_applicable_checks_must_run",
        True,
        "merge_gate",
        failures,
    )
    _expect_bool(
        merge_gate,
        "infrastructure_failure_blocks_merge",
        True,
        "merge_gate",
        failures,
    )
    _expect_bool(
        merge_gate,
        "billing_failure_blocks_merge",
        True,
        "merge_gate",
        failures,
    )
    rejected = set(merge_gate.get("rejected_as_green", []))
    for required in {"failure", "cancelled", "neutral", "skipped", "pending"}:
        if required not in rejected:
            failures.append(f"merge_gate must reject {required!r} as GREEN evidence")

    _expect_bool(
        owner,
        "product_acceptance_before_implementation_merge",
        False,
        "owner_participation",
        failures,
    )
    _expect_bool(
        owner,
        "product_acceptance_before_post_merge_green",
        False,
        "owner_participation",
        failures,
    )
    if owner.get("pre_merge_exception") != "GENUINELY_NON_DELEGABLE_PREREQUISITE_ONLY":
        failures.append("OWNER pre-merge exception is wider than prerequisite-only")

    _expect_bool(
        learning,
        "confidence_postmortem_after_unexpected_red",
        True,
        "failure_learning",
        failures,
    )
    if (
        learning.get("ledger")
        != "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md"
    ):
        failures.append("failure-learning ledger path mismatch")

    _expect_bool(
        isolation,
        "bounded_failure_domains",
        True,
        "fault_isolation",
        failures,
    )
    _expect_bool(
        isolation,
        "money_and_security_authority_fail_closed",
        True,
        "fault_isolation",
        failures,
    )

    if protected.get("gateway_entrypoint") != "app:app":
        failures.append("protected gateway entrypoint must remain app:app")
    if protected.get("trading_methods") is not False:
        failures.append("trading_methods must remain false")
    if protected.get("REAL_TRADING_ENABLED") is not False:
        failures.append("REAL_TRADING_ENABLED must remain false")
    if protected.get("broker_write_authority_added") is not False:
        failures.append("engineering governance must not add broker-write authority")


def main() -> int:
    failures: list[str] = []

    amendment = _load_text(AMENDMENT, failures)
    index = _load_text(INDEX, failures)
    ledger = _load_text(LEDGER, failures)
    pr_template = _load_text(PR_TEMPLATE, failures)
    copilot = _load_text(COPILOT, failures)
    wp_template = _load_text(WP_TEMPLATE, failures)
    workflow = _load_text(WORKFLOW, failures)

    _require_markers(
        AMENDMENT,
        amendment,
        (
            "Mandatory pre-CI engineering gate",
            "Exact-head GREEN merge law",
            "OWNER participation boundary",
            "Failure-learning law",
            'Fault-isolation / "spider" law',
        ),
        failures,
    )
    _require_markers(
        INDEX,
        index,
        (
            "Engineering Quality / Pre-CI / Green Merge",
            "OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md",
            "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json",
            "V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md",
        ),
        failures,
    )
    _require_markers(
        LEDGER,
        ledger,
        (
            "FL-001",
            "Why preflight missed it",
            "Permanent regression/guard",
            "Future prevention rule",
        ),
        failures,
    )
    _require_markers(
        PR_TEMPLATE,
        pr_template,
        (
            "Pre-CI engineering gate",
            "Root cause / blast radius",
            "All applicable exact-head checks = SUCCESS",
            "OWNER product acceptance is post-merge",
        ),
        failures,
    )
    _require_markers(
        COPILOT,
        copilot,
        (
            "Pre-CI Engineering Gate",
            "All applicable exact-head checks must be SUCCESS",
            "OWNER product acceptance only after merge",
            "Failure Learning Ledger",
        ),
        failures,
    )
    _require_markers(
        WP_TEMPLATE,
        wp_template,
        (
            "Pre-CI readiness",
            "Root-cause / blast-radius plan",
            "Fault isolation / degraded-mode contract",
            "Failure-learning update",
        ),
        failures,
    )
    _require_markers(
        WORKFLOW,
        workflow,
        (
            "name: V10 Engineering Governance",
            "python scripts/check_v10_engineering_governance.py",
            "persist-credentials: false",
        ),
        failures,
    )

    validate_contract(failures)

    if failures:
        print("V10 engineering governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 engineering governance check passed.")
    print("Pre-CI root-cause and blast-radius discipline: enforced")
    print("Exact-head applicable checks: SUCCESS-only project policy")
    print("OWNER product acceptance: post-merge/post-Regression-Shield")
    print("Failure-learning ledger: present")
    print("Fault-isolation contract: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
