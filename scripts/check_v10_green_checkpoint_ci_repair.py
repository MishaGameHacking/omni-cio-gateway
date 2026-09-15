from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md"
)
CONTRACT = (
    ROOT / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
)
RUNBOOK = ROOT / "docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md"
TARGETED_WORKFLOW = ROOT / ".github/workflows/v10-targeted-repair.yml"
AUTHORITATIVE_WORKFLOW = ROOT / ".github/workflows/self-hosted-windows-smoke.yml"
EXTERNAL_REVIEW_GUARD = ROOT / "scripts/check_v10_pr_external_review_gate.py"
POSTMERGE_RELEASE_GATE = ROOT / "scripts/check_v10_cloudflare_postmerge_release_gate.py"
PRODUCTION_RELEASE_WORKFLOW = ROOT / ".github/workflows/v10-cloudflare-production-release.yml"

RED_REPAIR_ONLY = "RED_REPAIR_ONLY"
TARGET_REPAIRED = "TARGET_REPAIRED"
CERTIFIED_GREEN = "CERTIFIED_GREEN"
MAIN_RED_STOP = "MAIN_RED_STOP"
SUCCESS = "success"
GREEN_CHECKPOINT_LAW = "Green Checkpoint & Targeted CI Repair Law"
GREEN_CHECKPOINT_AMENDMENT = f"{GREEN_CHECKPOINT_LAW} / Amendment 16"
GREEN_CHECKPOINT_REPAIR = "Green Checkpoint / targeted CI repair"

CORE_SECTION = "core"
SAME_SHA_SECTION = "same_sha_rerun"
CODE_REPAIR_SECTION = "code_repair"
TARGETED_SECTION = "targeted_verifier"
SONAR_SECTION = "sonar_review"
GREEN_SECTION = "green"
MAIN_SECTION = "main"
TARGETED_WORKFLOW_PATH = ".github/workflows/v10-targeted-repair.yml"
TOOLCHAIN_BASELINE_PATH = "docs/architecture/V10_TOOLCHAIN_BASELINE.json"
AUTHORITATIVE_WORKFLOW_PATH = ".github/workflows/self-hosted-windows-smoke.yml"
EXTERNAL_REVIEW_GUARD_PATH = "scripts/check_v10_pr_external_review_gate.py"
AUTHORITATIVE_CHECK_NAME = "V10 authoritative merge gate"
SONAR_POSTMERGE_CHECK_NAME = "SonarCloud Code Analysis"
SONAR_POSTMERGE_APP_SLUG = "sonarqubecloud"

LIVE_GUIDANCE_MARKERS: dict[Path, tuple[str, ...]] = {
    ROOT / "AGENTS.md": (
        GREEN_CHECKPOINT_LAW,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
        MAIN_RED_STOP,
    ),
    ROOT / "CONTRIBUTING.md": (
        GREEN_CHECKPOINT_LAW,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "README.md": (
        "Amendment 16 governs Green Checkpoint / targeted CI repair",
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / ".github/copilot-instructions.md": (
        GREEN_CHECKPOINT_REPAIR,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "gpt/PROJECT_INSTRUCTIONS.md": (
        GREEN_CHECKPOINT_AMENDMENT,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "gpt/NEW_CHAT_PROMPT.md": (
        GREEN_CHECKPOINT_AMENDMENT,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "docs/master-plan/README.md": (
        GREEN_CHECKPOINT_REPAIR,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md": (
        GREEN_CHECKPOINT_LAW,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md": (
        "Green Checkpoint certification",
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md": (
        "Green Checkpoint verification",
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / ".github/pull_request_template.md": (
        GREEN_CHECKPOINT_REPAIR,
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
    ROOT / ".github/ISSUE_TEMPLATE/v10_integrated_system_update.yml": (
        "Green Checkpoint / targeted repair evidence",
        RED_REPAIR_ONLY,
        CERTIFIED_GREEN,
    ),
}

SUPERSEDED_OPERATIONAL_MARKERS: dict[Path, tuple[str, ...]] = {
    ROOT / "CONTRIBUTING.md": ("## Pre-CI / HEAD FREEZE",),
    ROOT / "README.md": (
        "After a verification SHA is published, **HEAD FREEZE** applies",
        "one published head -> HEAD FREEZE",
    ),
    ROOT / ".github/copilot-instructions.md": (
        "After publishing a verification head, HEAD FREEZE applies",
    ),
    ROOT / "gpt/PROJECT_INSTRUCTIONS.md": ("\nHEAD FREEZE:\n",),
    ROOT / "gpt/NEW_CHAT_PROMPT.md": ("\nHEAD FREEZE:\n",),
    ROOT / "docs/master-plan/README.md": (
        "Integrated work is published only after `INTEGRATION_READY`",
        "After a verification SHA is published, `HEAD FREEZE` applies",
    ),
    ROOT / "docs/master-plan/OMNI_CIO_V10_WP_EXECUTION_TEMPLATE.md": (
        "apply **HEAD FREEZE**",
        "After a verification SHA is published, **HEAD FREEZE** applies",
    ),
    ROOT / "docs/updates/INTEGRATED_SYSTEM_UPDATE_EXECUTION_LEDGER_TEMPLATE.md": (
        "## 7. Verification batches / HEAD FREEZE",
    ),
    ROOT / "docs/updates/CLOUDFLARE_PUBLIC_PRODUCT_INTEGRATED_EXECUTION_LEDGER.md": (
        "## 7. Verification batches / HEAD FREEZE",
        "HEAD FREEZE begins after publication",
    ),
    ROOT / ".github/pull_request_template.md": ("## HEAD FREEZE / verification batch",),
}

REQUIRED_STATES = {
    "PENDING",
    RED_REPAIR_ONLY,
    TARGET_REPAIRED,
    CERTIFIED_GREEN,
    MAIN_RED_STOP,
}
REJECTED_GREEN = {
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


def _fail(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _read(path: Path, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _mapping(payload: dict[str, Any], key: str, failures: list[str]) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        failures.append(f"contract section must be object: {key}")
        return {}
    return value


def _expect(
    section: dict[str, Any],
    key: str,
    expected: Any,
    prefix: str,
    failures: list[str],
) -> None:
    _fail(section.get(key) == expected, f"{prefix}.{key} mismatch", failures)


def _load_contract(failures: list[str]) -> dict[str, Any]:
    raw = _read(CONTRACT, failures)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"invalid contract JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        failures.append("contract root must be an object")
        return {}
    return payload


def _validate_core(payload: dict[str, Any], failures: list[str]) -> None:
    core = _mapping(payload, CORE_SECTION, failures)
    expected = {
        "next_functional_checkpoint_requires_certified_green": True,
        "known_red_may_be_carried_forward": False,
        "repair_starts_immediately_on_material_red": True,
        "must_wait_for_all_independent_jobs_before_starting_repair": False,
        "root_cause_required": True,
        "blast_radius_required": True,
        "analogous_pattern_search_required": True,
        "coupled_surface_review_required": True,
        "adjacent_failure_review_required": True,
        "regression_guard_required_for_reusable_defect_class": True,
    }
    for key, value in expected.items():
        _expect(core, key, value, CORE_SECTION, failures)


def _validate_rerun_and_repair(payload: dict[str, Any], failures: list[str]) -> None:
    same_sha = _mapping(payload, SAME_SHA_SECTION, failures)
    for key in (
        "allowed_only_when_source_unchanged",
        "specific_failed_job_preferred",
        "same_github_sha_and_ref_required",
        "blind_repeat_until_green_forbidden",
    ):
        _expect(same_sha, key, True, SAME_SHA_SECTION, failures)

    repair = _mapping(payload, CODE_REPAIR_SECTION, failures)
    expected = {
        "changed_content_requires_replacement_sha": True,
        "repair_commit_does_not_authorize_new_feature_scope": True,
        "old_final_evidence_stale_after_content_change": True,
        "targeted_proof_before_full_certification_preferred": True,
        "full_certification_required_before_next_checkpoint": True,
        "protected_main_force_rewrite_allowed": False,
    }
    for key, value in expected.items():
        _expect(repair, key, value, CODE_REPAIR_SECTION, failures)


def _validate_targeted_verifier(payload: dict[str, Any], failures: list[str]) -> None:
    targeted = _mapping(payload, TARGETED_SECTION, failures)
    expected = {
        "workflow": TARGETED_WORKFLOW_PATH,
        "expected_sha_format": "LOWERCASE_FULL_40_HEX",
        "expected_sha_must_equal_dispatch_ref_head": True,
        "exact_checkout_verified_before_and_after_lane": True,
        "frontend_toolchain_authority": TOOLCHAIN_BASELINE_PATH,
        "frontend_dependency_lifecycle_scripts_disabled": True,
        "workspace_cleanup_required": True,
    }
    for key, value in expected.items():
        _expect(targeted, key, value, TARGETED_SECTION, failures)


def _validate_sonar(payload: dict[str, Any], failures: list[str]) -> None:
    sonar = _mapping(payload, SONAR_SECTION, failures)
    expected = {
        "quality_gate_pass_required_when_applicable": True,
        "new_issues_default": 0,
        "unresolved_new_security_hotspots": 0,
        "material_new_reliability_security_maintainability_findings": 0,
        "independent_review_findings_must_be_inspected": True,
        "bot_approval_is_not_engineering_judgment": True,
        "authoritative_merge_gate_enforces_exact_head": True,
        "authoritative_workflow": AUTHORITATIVE_WORKFLOW_PATH,
        "required_check_name": AUTHORITATIVE_CHECK_NAME,
        "external_review_guard": EXTERNAL_REVIEW_GUARD_PATH,
        "github_checks_permission": "read",
        "bounded_wait_required": True,
        "annotation_count_must_be_zero": True,
        "post_merge_exact_main_check_required": True,
        "post_merge_check_name": SONAR_POSTMERGE_CHECK_NAME,
        "post_merge_check_app_slug": SONAR_POSTMERGE_APP_SLUG,
        "post_merge_check_success_only": True,
    }
    for key, value in expected.items():
        _expect(sonar, key, value, SONAR_SECTION, failures)


def _validate_green_and_main(payload: dict[str, Any], failures: list[str]) -> None:
    green = _mapping(payload, GREEN_SECTION, failures)
    _expect(green, "accepted_check_conclusions", [SUCCESS], GREEN_SECTION, failures)
    rejected = green.get("rejected_as_green")
    rejected_set = set(rejected) if isinstance(rejected, list) else set()
    _fail(
        REJECTED_GREEN.issubset(rejected_set),
        f"{GREEN_SECTION}.rejected_as_green incomplete",
        failures,
    )
    _expect(green, "exact_current_sha_only", True, GREEN_SECTION, failures)
    _expect(
        green,
        "zero_unresolved_blocking_review_threads",
        True,
        GREEN_SECTION,
        failures,
    )
    _expect(
        green,
        "post_merge_regression_shield_required",
        True,
        GREEN_SECTION,
        failures,
    )

    main_policy = _mapping(payload, MAIN_SECTION, failures)
    _expect(main_policy, "post_merge_red_state", MAIN_RED_STOP, MAIN_SECTION, failures)
    _expect(
        main_policy,
        "ordinary_feature_progress_allowed_while_main_red",
        False,
        MAIN_SECTION,
        failures,
    )
    _expect(
        main_policy,
        "main_amend_or_force_rewrite_allowed",
        False,
        MAIN_SECTION,
        failures,
    )


def _validate_contract(payload: dict[str, Any], failures: list[str]) -> None:
    _fail(
        payload.get("schema") == "omni-cio.v10.green-checkpoint-targeted-ci-repair.v1",
        "schema mismatch",
        failures,
    )
    _fail(payload.get("amendment") == 16, "amendment number mismatch", failures)
    _fail(
        set(payload.get("checkpoint_states", [])) == REQUIRED_STATES,
        "checkpoint state set mismatch",
        failures,
    )
    _validate_core(payload, failures)
    _validate_rerun_and_repair(payload, failures)
    _validate_targeted_verifier(payload, failures)
    _validate_sonar(payload, failures)
    _validate_green_and_main(payload, failures)


def _validate_markers(path: Path, markers: tuple[str, ...], failures: list[str]) -> str:
    content = _read(path, failures)
    for marker in markers:
        _fail(
            marker in content,
            f"{path.relative_to(ROOT)} missing marker: {marker}",
            failures,
        )
    return content


def _validate_static_surfaces(failures: list[str]) -> None:
    surfaces = {
        AMENDMENT: (
            GREEN_CHECKPOINT_AMENDMENT,
            RED_REPAIR_ONLY,
            TARGET_REPAIRED,
            CERTIFIED_GREEN,
            MAIN_RED_STOP,
            "Same-SHA targeted rerun",
            "Code/config repair requires a replacement SHA",
        ),
        RUNBOOK: (
            "ONE CHECKPOINT",
            "RED = REPAIR ONLY",
            "TARGETED RECHECK",
            "FULL CERTIFICATION",
            TARGETED_WORKFLOW_PATH,
            "dispatch-ref head",
            "V10_TOOLCHAIN_BASELINE.json",
        ),
        TARGETED_WORKFLOW: (
            "workflow_dispatch",
            "expected_sha",
            "^[0-9a-f]{40}$",
            "DISPATCH_HEAD",
            "expected_sha must equal the workflow-dispatch ref head",
            "V10_TOOLCHAIN_BASELINE.json",
            "Verify exact Node and npm baseline",
            "--ignore-scripts --no-audit --no-fund",
        ),
        AUTHORITATIVE_WORKFLOW: (
            "checks: read",
            AUTHORITATIVE_CHECK_NAME,
            "Verify exact-head Sonar review gate",
            f"python {EXTERNAL_REVIEW_GUARD_PATH}",
        ),
        EXTERNAL_REVIEW_GUARD: (
            SONAR_POSTMERGE_CHECK_NAME,
            "new issues must be 0",
            "Security Hotspots must be 0",
            "annotations/new findings must be 0",
        ),
        POSTMERGE_RELEASE_GATE: (
            "post_merge_exact_main_check_required",
            "post_merge_check_name",
            "post_merge_check_app_slug",
            "CLOUDFLARE_POSTMERGE_EXTERNAL_CHECK_NOT_SUCCESS",
            "/check-runs?",
        ),
        PRODUCTION_RELEASE_WORKFLOW: (
            "actions: read",
            "checks: read",
            "check_v10_cloudflare_postmerge_release_gate",
        ),
    }
    for path, markers in surfaces.items():
        _validate_markers(path, markers, failures)


def _validate_live_guidance(failures: list[str]) -> None:
    contents: dict[Path, str] = {}
    for path, markers in LIVE_GUIDANCE_MARKERS.items():
        contents[path] = _validate_markers(path, markers, failures)
    for path, markers in SUPERSEDED_OPERATIONAL_MARKERS.items():
        content = contents.get(path) or _read(path, failures)
        for marker in markers:
            _fail(
                marker not in content,
                f"{path.relative_to(ROOT)} still contains superseded operational marker: {marker}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    _validate_contract(_load_contract(failures), failures)
    _validate_static_surfaces(failures)
    _validate_live_guidance(failures)

    if failures:
        print("V10 Green Checkpoint governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 Green Checkpoint governance check passed.")
    print(
        "Flow: CHECKPOINT -> RED_REPAIR_ONLY -> TARGETED_RECHECK -> "
        "FULL_CERTIFICATION -> CERTIFIED_GREEN"
    )
    print("Live guidance: synchronized with Amendment 16")
    print(
        "Targeted verifier: exact dispatch head + accepted frontend toolchain enforced"
    )
    print("Required merge gate: exact-head Sonar zero-issue enforcement enabled")
    print("Post-merge release gate: exact-main Sonar success enforcement enabled")
    print("Next functional checkpoint requires CERTIFIED_GREEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
