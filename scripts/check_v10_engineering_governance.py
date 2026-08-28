from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md"
)
INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
CONTRACT = ROOT / "docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
PUBLIC_CONTRACT = (
    ROOT / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"
)
LEDGER = ROOT / "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md"
OWNER_STANDARD = ROOT / "docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md"
COPILOT_POLICY = ROOT / ".github/instructions/owner-handoff-and-runtime.instructions.md"
PR_TEMPLATE = ROOT / ".github/pull_request_template.md"
COPILOT = ROOT / ".github/copilot-instructions.md"
WP_TEMPLATE = ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md"
WORKFLOW = ROOT / ".github/workflows/v10-engineering-governance.yml"

REVIEW_GATE_BOOL_KEYS = (
    "new_commit_invalidates_final_green_evidence",
    "new_commit_invalidates_review_evidence",
    "zero_unresolved_blocking_review_threads",
    "full_diff_review_required",
    "complete_files_changed_review_required",
    "independent_review_outputs_required_when_applicable",
    "material_findings_require_engineering_classification",
    "bot_approval_is_supporting_not_substitute",
    "manual_engineering_diff_review_required",
    "correction_commit_requires_fresh_files_changed_and_review",
)
REQUIRED_REVIEW_OUTPUTS = {
    "INLINE_REVIEW_THREADS",
    "CHECK_ANNOTATIONS",
    "SONAR",
    "GITAR",
    "SAST_SECURITY_REVIEW",
    "OTHER_APPLICABLE_CODE_SECURITY_REVIEW",
}
REJECTED_GREEN_CONCLUSIONS = {
    "failure",
    "cancelled",
    "queued",
    "pending",
    "in_progress",
    "timed_out",
    "action_required",
    "stale",
    "neutral",
    "skipped",
}


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


def _load_json(path: Path, failures: list[str]) -> dict[str, Any] | None:
    text = _load_text(path, failures)
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return None
    if not isinstance(payload, dict):
        failures.append(f"JSON root must be object: {path.relative_to(ROOT)}")
        return None
    return payload


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


def _require_section(
    data: dict[str, Any], name: str, failures: list[str]
) -> dict[str, Any]:
    section = data.get(name)
    if not isinstance(section, dict):
        failures.append(f"engineering quality contract section must be object: {name}")
        return {}
    return section


def _validate_pre_ci(pre_ci: dict[str, Any], failures: list[str]) -> None:
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


def _validate_merge_review_gate(
    merge_gate: dict[str, Any], failures: list[str]
) -> None:
    for key in REVIEW_GATE_BOOL_KEYS:
        _expect_bool(merge_gate, key, True, "merge_gate", failures)

    review_outputs = merge_gate.get("review_outputs", [])
    if not isinstance(review_outputs, list):
        failures.append("merge_gate.review_outputs must be a list")
        return

    present_review_outputs = {item for item in review_outputs if isinstance(item, str)}
    for required in sorted(REQUIRED_REVIEW_OUTPUTS - present_review_outputs):
        failures.append(
            f"merge_gate.review_outputs missing required source: {required}"
        )


def _validate_merge_gate(merge_gate: dict[str, Any], failures: list[str]) -> None:
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
    _validate_merge_review_gate(merge_gate, failures)

    rejected = set(merge_gate.get("rejected_as_green", []))
    for required in sorted(REJECTED_GREEN_CONCLUSIONS - rejected):
        failures.append(f"merge_gate must reject {required!r} as GREEN evidence")


def _validate_owner(owner: dict[str, Any], failures: list[str]) -> None:
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


def _validate_owner_handoff(owner_handoff: dict[str, Any], failures: list[str]) -> None:
    if (
        owner_handoff.get("standard")
        != "docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md"
    ):
        failures.append("OWNER handoff standard path mismatch")
    for key in (
        "direct_official_link_required_when_stable",
        "current_official_ui_or_docs_verification_required_when_changeable",
        "expected_result_required",
        "stop_conditions_required",
        "do_not_do_warnings_required",
        "minimum_safe_return_required",
        "one_bounded_owner_action_at_a_time",
        "owner_must_not_be_required_to_discover_target_page",
    ):
        _expect_bool(owner_handoff, key, True, "owner_handoff", failures)
    _expect_bool(
        owner_handoff,
        "generic_navigation_without_link_sufficient",
        False,
        "owner_handoff",
        failures,
    )
    _expect_bool(
        owner_handoff,
        "secret_bearing_or_shortened_links_forbidden",
        True,
        "owner_handoff",
        failures,
    )


def _validate_runtime_hosting(
    runtime_hosting: dict[str, Any], failures: list[str]
) -> None:
    if (
        runtime_hosting.get("v10_public_production_host")
        != "APPROVED_MANAGED_CLOUD_RUNTIME_SELECTED_BY_OWNING_GATE"
    ):
        failures.append(
            "V10 public production host must be selected by the managed-cloud owning gate"
        )
    _expect_bool(
        runtime_hosting,
        "managed_cloud_runtime_required_for_public_product",
        True,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "owner_home_or_lenovo_public_dependency_allowed",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "owner_home_power_or_internet_public_sla_dependency_allowed",
        False,
        "runtime_hosting",
        failures,
    )
    if (
        runtime_hosting.get("lenovo_role")
        != "ENGINEERING_SELF_HOSTED_CI_ACCEPTANCE_RECOVERY_ROLLBACK"
    ):
        failures.append(
            "Lenovo role must remain engineering/CI/acceptance/recovery/rollback"
        )
    _expect_bool(
        runtime_hosting,
        "lenovo_may_be_final_public_production_origin",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "provider_selection_requires_owner_approved_gate",
        True,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "provider_purchase_or_mutation_implied_by_planning",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "render_com_v10_runtime_target_selected",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "render_com_new_workspace_authoritative",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "render_com_new_v10_service_without_owner_amendment_allowed",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "protected_v9_render_app_app_baseline_preserved",
        True,
        "runtime_hosting",
        failures,
    )
    if (
        runtime_hosting.get("cloudflare_role")
        != "EDGE_DNS_TLS_WAF_DDOS_ORIGIN_PROTECTION_CANDIDATE_NOT_PRODUCT_IDENTITY"
    ):
        failures.append(
            "Cloudflare role must remain edge/origin protection, not product identity"
        )
    _expect_bool(
        runtime_hosting,
        "cloudflare_home_lenovo_tunnel_satisfies_final_public_hosting",
        False,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "hosted_tenant_private_state_allowed_after_security_privacy_legal_gates",
        True,
        "runtime_hosting",
        failures,
    )
    _expect_bool(
        runtime_hosting,
        "external_access_provider_may_become_product_identity",
        False,
        "runtime_hosting",
        failures,
    )


def _validate_public_runtime_contract(failures: list[str]) -> None:
    public_contract = _load_json(PUBLIC_CONTRACT, failures)
    if public_contract is None:
        return

    product = public_contract.get("product_target", {})
    production = public_contract.get("production_hosting", {})
    access = public_contract.get("initial_access_model", {})
    broker = public_contract.get("broker_credentials", {})
    activation = public_contract.get("activation", {})
    safety = public_contract.get("safety", {})
    sections = (product, production, access, broker, activation, safety)
    if not all(isinstance(item, dict) for item in sections):
        failures.append("public runtime contract sections must be objects")
        return

    _expect_bool(product, "public_multi_user_target", True, "public_product", failures)
    _expect_bool(
        product,
        "project_owner_is_special_product_role",
        False,
        "public_product",
        failures,
    )
    _expect_bool(
        production,
        "managed_cloud_origin_required",
        True,
        "public_production",
        failures,
    )
    _expect_bool(
        production,
        "lenovo_as_public_production_origin_allowed",
        False,
        "public_production",
        failures,
    )
    _expect_bool(access, "billing_enabled", False, "initial_access", failures)
    _expect_bool(access, "trial_enabled", False, "initial_access", failures)
    _expect_bool(access, "subscription_enforcement", False, "initial_access", failures)
    _expect_bool(access, "premium_feature_gating", False, "initial_access", failures)
    if broker.get("ownership") != "TENANT_SCOPED_BROKER_CONNECTION":
        failures.append("public broker credentials must remain tenant-scoped")
    _expect_bool(
        broker,
        "cross_tenant_secret_access_allowed",
        False,
        "broker_credentials",
        failures,
    )
    _expect_bool(
        activation,
        "implementation_default_public_multi_user_enabled",
        False,
        "activation",
        failures,
    )
    _expect_bool(
        activation,
        "target_after_exit_gates_public_multi_user_enabled",
        True,
        "activation",
        failures,
    )
    if safety.get("app_entrypoint") != "app:app":
        failures.append("public plan must preserve app:app")
    _expect_bool(safety, "trading_methods", False, "public_safety", failures)
    _expect_bool(safety, "real_trading_enabled", False, "public_safety", failures)


def _validate_failure_and_protected_invariants(
    learning: dict[str, Any],
    isolation: dict[str, Any],
    protected: dict[str, Any],
    failures: list[str],
) -> None:
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
        isolation, "bounded_failure_domains", True, "fault_isolation", failures
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
    if protected.get("transfer_withdrawal_authority") is not False:
        failures.append(
            "engineering governance must not add transfer/withdrawal authority"
        )
    if protected.get("v9_rollback_protected") is not True:
        failures.append("V9 rollback must remain protected")
    if protected.get("master_plan_sequence_preserved") is not True:
        failures.append("Master Plan sequence must remain protected")


def validate_contract(failures: list[str]) -> None:
    data = _load_json(CONTRACT, failures)
    if data is None:
        return

    if data.get("schema") != "omni-cio.v10.engineering-quality-gate.v4":
        failures.append("engineering quality contract schema mismatch")

    pre_ci = _require_section(data, "pre_ci", failures)
    merge_gate = _require_section(data, "merge_gate", failures)
    owner = _require_section(data, "owner_participation", failures)
    owner_handoff = _require_section(data, "owner_handoff", failures)
    runtime_hosting = _require_section(data, "runtime_hosting", failures)
    learning = _require_section(data, "failure_learning", failures)
    isolation = _require_section(data, "fault_isolation", failures)
    protected = _require_section(data, "protected_invariants", failures)

    _validate_pre_ci(pre_ci, failures)
    _validate_merge_gate(merge_gate, failures)
    _validate_owner(owner, failures)
    _validate_owner_handoff(owner_handoff, failures)
    _validate_runtime_hosting(runtime_hosting, failures)
    _validate_public_runtime_contract(failures)
    _validate_failure_and_protected_invariants(
        learning,
        isolation,
        protected,
        failures,
    )


def main() -> int:
    failures: list[str] = []

    agents = _load_text(AGENTS, failures)
    contributing = _load_text(CONTRIBUTING, failures)
    amendment = _load_text(AMENDMENT, failures)
    index = _load_text(INDEX, failures)
    ledger = _load_text(LEDGER, failures)
    owner_standard = _load_text(OWNER_STANDARD, failures)
    copilot_policy = _load_text(COPILOT_POLICY, failures)
    pr_template = _load_text(PR_TEMPLATE, failures)
    copilot = _load_text(COPILOT, failures)
    wp_template = _load_text(WP_TEMPLATE, failures)
    workflow = _load_text(WORKFLOW, failures)

    _require_markers(
        AGENTS,
        agents,
        (
            "CI is an independent verifier",
            "every **applicable** exact-head V10 check must actually execute and conclude `success`",
            "Changed-files + independent code-review merge gate",
            "OWNER participation / handoff law",
            "bounded failure domains rather than one fragile monolith",
            "WP22A — External Web Access / Product Authentication Security Gate",
            "managed-cloud production runtime",
        ),
        failures,
    )
    _require_markers(
        CONTRIBUTING,
        contributing,
        (
            "Files changed / independent code-review gate",
            "Bot approval is supporting evidence",
            "fresh Files changed + review evidence",
        ),
        failures,
    )
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
            "Public Free Multi-User Hosted Runtime",
        ),
        failures,
    )
    _require_markers(
        LEDGER,
        ledger,
        (
            "FL-001",
            "FL-004",
            "FL-005",
            "FL-006",
            "Why preflight missed it",
            "Permanent regression/guard",
            "Future prevention rule",
        ),
        failures,
    )
    _require_markers(
        OWNER_STANDARD,
        owner_standard,
        (
            "Direct-link-first law",
            "Mandatory OWNER handoff format",
            "V10 local runtime / rendering law",
            "Render.com boundary",
            "managed-cloud production runtime",
            "owner_must_not_be_required_to_discover_target_page",
        ),
        failures,
    )
    _require_markers(
        COPILOT_POLICY,
        copilot_policy,
        (
            'applyTo: "**"',
            "OWNER help must be deterministic",
            "direct official HTTPS link",
            "Lenovo is engineering/recovery, not public production",
            "managed-cloud production runtime",
            "OWNER billing / CI cost control",
        ),
        failures,
    )
    _require_markers(
        PR_TEMPLATE,
        pr_template,
        (
            "Pre-CI engineering gate",
            "Root cause / blast radius",
            "Files changed / independent review evidence",
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
            "managed-cloud Omni-CIO Web/API",
        ),
        failures,
    )
    _require_markers(
        WP_TEMPLATE,
        wp_template,
        (
            "Pre-CI readiness",
            "Root-cause / blast-radius plan",
            "Files changed / independent review evidence",
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
            "python scripts/check_v10_documentation_consistency.py",
            "python scripts/check_v10_public_product_plan.py",
            "python scripts/check_v10_ci_cost_control.py",
            "python scripts/check_v10_regression_shield.py",
            "contents: read",
            'GIT_TERMINAL_PROMPT: "0"',
            'GCM_INTERACTIVE: "0"',
            'git config --local credential.helper ""',
            "git config --local --add credential.helper",
            "git config --local --unset-all credential.helper",
            'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"',
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
    print("AGENTS engineering law: present")
    print("Pre-CI root-cause and blast-radius discipline: enforced")
    print("Exact-head applicable checks: SUCCESS-only project policy")
    print("Exact-head changed-files + independent review: enforced")
    print("OWNER product acceptance: post-merge/post-Regression-Shield")
    print("OWNER handoff: direct official link + bounded action contract enforced")
    print(
        "V10 public runtime: managed-cloud target; OWNER home/Lenovo not public origin"
    )
    print("Failure-learning ledger: present")
    print("Fault-isolation contract: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
