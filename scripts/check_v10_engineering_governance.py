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

SUCCESS = "success"
GREEN_CHECKPOINT_LAW = "Green Checkpoint & Targeted CI Repair Law"
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
REQUIRED_REVIEW_OUTPUTS = {
    "INLINE_REVIEW_THREADS",
    "CHECK_ANNOTATIONS",
    "SONAR",
    "GITAR",
    "SAST_SECURITY_REVIEW",
    "OTHER_APPLICABLE_CODE_SECURITY_REVIEW",
}

SURFACE_MARKERS: dict[Path, tuple[str, ...]] = {
    AGENTS: (
        "CI is an independent verifier",
        "every **applicable** exact-head V10 check must actually execute and conclude `success`",
        "Changed-files + independent code-review merge gate",
        "OWNER participation / handoff law",
        "bounded failure domains rather than one fragile monolith",
        "WP22A — External Web Access / Product Authentication Security Gate",
        "managed-cloud production runtime",
        GREEN_CHECKPOINT_LAW,
    ),
    CONTRIBUTING: (
        "Files changed / independent code-review gate",
        "Bot approval is supporting evidence",
        "fresh Files changed + review evidence",
        GREEN_CHECKPOINT_LAW,
    ),
    AMENDMENT: (
        "Mandatory pre-CI engineering gate",
        "Exact-head GREEN merge law",
        "OWNER participation boundary",
        "Failure-learning law",
        'Fault-isolation / "spider" law',
    ),
    INDEX: (
        "Engineering Quality / Pre-CI / Green Merge",
        "OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md",
        "V10_ENGINEERING_QUALITY_GATE_CONTRACT.json",
        "V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md",
        "Public Free Multi-User Hosted Runtime",
        GREEN_CHECKPOINT_LAW,
    ),
    LEDGER: (
        "FL-001",
        "FL-004",
        "FL-005",
        "FL-006",
        "Why preflight missed it",
        "Permanent regression/guard",
        "Future prevention rule",
    ),
    OWNER_STANDARD: (
        "Direct-link-first law",
        "Mandatory OWNER handoff format",
        "V10 local runtime / rendering law",
        "Render.com boundary",
        "managed-cloud production runtime",
        "owner_must_not_be_required_to_discover_target_page",
    ),
    COPILOT_POLICY: (
        'applyTo: "**"',
        "OWNER help must be deterministic",
        "direct official HTTPS link",
        "Lenovo is engineering/recovery, not public production",
        "managed-cloud production runtime",
        "OWNER billing / CI cost control",
    ),
    PR_TEMPLATE: (
        "Focused preflight / root-cause engineering gate",
        "Root cause / blast radius",
        "Files changed / independent review evidence",
        "Exact-head CERTIFIED_GREEN merge gate",
        "OWNER product acceptance is post-merge",
        "RED_REPAIR_ONLY",
    ),
    COPILOT: (
        "Green Checkpoint / targeted CI repair",
        "All applicable exact-head checks must be SUCCESS",
        "OWNER product acceptance only after merge",
        "Failure Learning Ledger",
        "managed-cloud Omni-CIO Web/API",
        "RED_REPAIR_ONLY",
    ),
    WP_TEMPLATE: (
        "Focused preflight / checkpoint readiness",
        "Root-cause / blast-radius / targeted-repair plan",
        "Files changed / independent review evidence",
        "Fault isolation / degraded-mode contract",
        "Failure-learning update",
        "CERTIFIED_GREEN",
    ),
    WORKFLOW: (
        "name: V10 Engineering Governance",
        "python scripts/check_v10_engineering_governance.py",
        "python scripts/check_v10_green_checkpoint_ci_repair.py",
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
}


def _load_text(path: Path, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _load_json(path: Path, failures: list[str]) -> dict[str, Any]:
    text = _load_text(path, failures)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append(f"JSON root must be object: {path.relative_to(ROOT)}")
        return {}
    return payload


def _section(data: dict[str, Any], name: str, failures: list[str]) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        failures.append(f"engineering quality contract section must be object: {name}")
        return {}
    return value


def _expect_values(
    section: dict[str, Any],
    expected: dict[str, Any],
    context: str,
    failures: list[str],
) -> None:
    for key, expected_value in expected.items():
        if section.get(key) != expected_value:
            failures.append(f"{context}.{key} must be {expected_value!r}")


def _validate_markers(failures: list[str]) -> None:
    for path, markers in SURFACE_MARKERS.items():
        text = _load_text(path, failures)
        for marker in markers:
            if marker not in text:
                failures.append(
                    f"{path.relative_to(ROOT)} is missing governance marker: {marker}"
                )


def _validate_pre_ci(data: dict[str, Any], failures: list[str]) -> None:
    _expect_values(
        _section(data, "pre_ci", failures),
        {
            "required": True,
            "ci_is_primary_debugger": False,
            "root_cause_before_fix": True,
            "blast_radius_search": True,
            "regression_guard_required_for_material_defect": True,
        },
        "pre_ci",
        failures,
    )


def _validate_merge_gate(data: dict[str, Any], failures: list[str]) -> None:
    merge_gate = _section(data, "merge_gate", failures)
    if merge_gate.get("accepted_check_conclusions") != [SUCCESS]:
        failures.append("merge_gate accepts conclusions other than success")
    _expect_values(
        merge_gate,
        {
            "exact_head_only": True,
            "all_applicable_checks_must_run": True,
            "infrastructure_failure_blocks_merge": True,
            "billing_failure_blocks_merge": True,
            "new_commit_invalidates_final_green_evidence": True,
            "new_commit_invalidates_review_evidence": True,
            "zero_unresolved_blocking_review_threads": True,
            "full_diff_review_required": True,
            "complete_files_changed_review_required": True,
            "independent_review_outputs_required_when_applicable": True,
            "material_findings_require_engineering_classification": True,
            "bot_approval_is_supporting_not_substitute": True,
            "manual_engineering_diff_review_required": True,
            "correction_commit_requires_fresh_files_changed_and_review": True,
        },
        "merge_gate",
        failures,
    )
    rejected = merge_gate.get("rejected_as_green")
    rejected_set = set(rejected) if isinstance(rejected, list) else set()
    for required in sorted(REJECTED_GREEN_CONCLUSIONS - rejected_set):
        failures.append(f"merge_gate must reject {required!r} as GREEN evidence")

    outputs = merge_gate.get("review_outputs")
    if not isinstance(outputs, list):
        failures.append("merge_gate.review_outputs must be a list")
        return
    output_set = {item for item in outputs if isinstance(item, str)}
    for required in sorted(REQUIRED_REVIEW_OUTPUTS - output_set):
        failures.append(
            f"merge_gate.review_outputs missing required source: {required}"
        )


def _validate_owner(data: dict[str, Any], failures: list[str]) -> None:
    _expect_values(
        _section(data, "owner_participation", failures),
        {
            "product_acceptance_before_implementation_merge": False,
            "product_acceptance_before_post_merge_green": False,
            "pre_merge_exception": "GENUINELY_NON_DELEGABLE_PREREQUISITE_ONLY",
        },
        "owner_participation",
        failures,
    )


def _validate_owner_handoff(data: dict[str, Any], failures: list[str]) -> None:
    _expect_values(
        _section(data, "owner_handoff", failures),
        {
            "standard": "docs/operations/V10_OWNER_ACTION_HANDOFF_STANDARD.md",
            "direct_official_link_required_when_stable": True,
            "generic_navigation_without_link_sufficient": False,
            "current_official_ui_or_docs_verification_required_when_changeable": True,
            "expected_result_required": True,
            "stop_conditions_required": True,
            "do_not_do_warnings_required": True,
            "minimum_safe_return_required": True,
            "one_bounded_owner_action_at_a_time": True,
            "owner_must_not_be_required_to_discover_target_page": True,
            "secret_bearing_or_shortened_links_forbidden": True,
        },
        "owner_handoff",
        failures,
    )


def _validate_runtime_hosting(data: dict[str, Any], failures: list[str]) -> None:
    _expect_values(
        _section(data, "runtime_hosting", failures),
        {
            "v10_public_production_host": "TIMEWEB_APP_PLATFORM_AFTER_OWNING_CUTOVER_GATE",
            "managed_cloud_runtime_required_for_public_product": True,
            "owner_home_or_lenovo_public_dependency_allowed": False,
            "owner_home_power_or_internet_public_sla_dependency_allowed": False,
            "lenovo_role": "ENGINEERING_SELF_HOSTED_CI_ACCEPTANCE_RECOVERY_ROLLBACK",
            "lenovo_may_be_final_public_production_origin": False,
            "provider_selection_requires_owner_approved_gate": True,
            "provider_purchase_or_mutation_implied_by_planning": False,
            "render_com_v10_runtime_target_selected": False,
            "render_com_new_workspace_authoritative": False,
            "render_com_new_v10_service_without_owner_amendment_allowed": False,
            "render_com_new_v10_release_acceptance_allowed": False,
            "cloudru_new_v10_runtime_target_selected": False,
            "protected_v9_render_app_app_baseline_preserved": True,
            "timeweb_cloud_selected": True,
            "timeweb_role": "PRIMARY_V10_MANAGED_APPLICATION_DATABASE_DOMAIN_PLATFORM_NOT_PRODUCT_IDENTITY",
            "timeweb_governance_acceptance_mutates_provider": False,
            "timeweb_governance_acceptance_authorizes_production_cutover": False,
            "timeweb_exact_main_release_required": True,
            "cloudflare_role": "HISTORICAL_ACCEPTED_PLATFORM_RETIRED_BY_AMENDMENT_18",
            "cloudflare_workers_paid_selected": False,
            "cloudflare_governance_acceptance_mutates_provider": False,
            "cloudflare_governance_acceptance_authorizes_production_cutover": False,
            "cloudflare_home_lenovo_tunnel_satisfies_final_public_hosting": False,
            "continuous_exact_main_release_required": True,
            "hosted_tenant_private_state_allowed_after_security_privacy_legal_gates": True,
            "external_access_provider_may_become_product_identity": False,
        },
        "runtime_hosting",
        failures,
    )


def _validate_public_runtime_contract(failures: list[str]) -> None:
    data = _load_json(PUBLIC_CONTRACT, failures)
    checks = {
        "product_target": {
            "public_multi_user_target": True,
            "project_owner_is_special_product_role": False,
        },
        "production_hosting": {
            "managed_cloud_origin_required": True,
            "lenovo_as_public_production_origin_allowed": False,
        },
        "initial_access_model": {
            "billing_enabled": False,
            "trial_enabled": False,
            "subscription_enforcement": False,
            "premium_feature_gating": False,
        },
        "activation": {
            "implementation_default_public_multi_user_enabled": False,
            "target_after_exit_gates_public_multi_user_enabled": True,
        },
        "safety": {
            "app_entrypoint": "app:app",
            "trading_methods": False,
            "real_trading_enabled": False,
        },
    }
    for section_name, expected in checks.items():
        _expect_values(
            _section(data, section_name, failures),
            expected,
            f"public_runtime.{section_name}",
            failures,
        )
    _expect_values(
        _section(data, "broker_credentials", failures),
        {
            "ownership": "TENANT_SCOPED_BROKER_CONNECTION",
            "cross_tenant_secret_access_allowed": False,
        },
        "public_runtime.broker_credentials",
        failures,
    )


def _validate_failure_and_protected_invariants(
    data: dict[str, Any], failures: list[str]
) -> None:
    _expect_values(
        _section(data, "failure_learning", failures),
        {
            "confidence_postmortem_after_unexpected_red": True,
            "ledger": "docs/operations/V10_ENGINEERING_FAILURE_LEARNING_LEDGER.md",
        },
        "failure_learning",
        failures,
    )
    _expect_values(
        _section(data, "fault_isolation", failures),
        {
            "bounded_failure_domains": True,
            "money_and_security_authority_fail_closed": True,
        },
        "fault_isolation",
        failures,
    )
    _expect_values(
        _section(data, "protected_invariants", failures),
        {
            "gateway_entrypoint": "app:app",
            "trading_methods": False,
            "REAL_TRADING_ENABLED": False,
            "broker_write_authority_added": False,
            "transfer_withdrawal_authority": False,
            "v9_rollback_protected": True,
            "master_plan_sequence_preserved": True,
        },
        "protected_invariants",
        failures,
    )


def validate_contract(failures: list[str]) -> None:
    data = _load_json(CONTRACT, failures)
    if data.get("schema") != "omni-cio.v10.engineering-quality-gate.v5":
        failures.append("engineering quality contract schema mismatch")
    _validate_pre_ci(data, failures)
    _validate_merge_gate(data, failures)
    _validate_owner(data, failures)
    _validate_owner_handoff(data, failures)
    _validate_runtime_hosting(data, failures)
    _validate_public_runtime_contract(failures)
    _validate_failure_and_protected_invariants(data, failures)


def main() -> int:
    failures: list[str] = []
    _validate_markers(failures)
    validate_contract(failures)

    if failures:
        print("V10 engineering governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 engineering governance check passed.")
    print("Green Checkpoint + focused preflight/root-cause discipline: enforced")
    print("Exact-head applicable checks: SUCCESS-only project policy")
    print("Exact-head changed-files + independent review: enforced")
    print("OWNER product acceptance: post-merge/post-Regression-Shield")
    print("OWNER handoff: direct official link + bounded action contract enforced")
    print("V10 public runtime: Timeweb App Platform target after owning cutover gate")
    print("Failure-learning and bounded fault-isolation contracts: enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
