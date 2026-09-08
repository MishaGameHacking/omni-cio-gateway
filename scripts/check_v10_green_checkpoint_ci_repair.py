from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT = ROOT / "docs/master-plan/OMNI_CIO_V10_GREEN_CHECKPOINT_AND_TARGETED_CI_REPAIR_AMENDMENT.md"
CONTRACT = ROOT / "docs/architecture/V10_GREEN_CHECKPOINT_TARGETED_CI_REPAIR_CONTRACT.json"
RUNBOOK = ROOT / "docs/operations/V10_GREEN_CHECKPOINT_CI_RUNBOOK.md"
TARGETED_WORKFLOW = ROOT / ".github/workflows/v10-targeted-repair.yml"

REQUIRED_STATES = {
    "PENDING",
    "RED_REPAIR_ONLY",
    "TARGET_REPAIRED",
    "CERTIFIED_GREEN",
    "MAIN_RED_STOP",
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


def main() -> int:
    failures: list[str] = []
    raw = _read(CONTRACT, failures)
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        failures.append(f"invalid contract JSON: {exc}")
        payload = {}

    _fail(payload.get("schema") == "omni-cio.v10.green-checkpoint-targeted-ci-repair.v1", "schema mismatch", failures)
    _fail(payload.get("amendment") == 16, "amendment number mismatch", failures)
    _fail(set(payload.get("checkpoint_states", [])) == REQUIRED_STATES, "checkpoint state set mismatch", failures)

    core = payload.get("core", {})
    _fail(core.get("next_functional_checkpoint_requires_certified_green") is True, "next checkpoint must require certified green", failures)
    _fail(core.get("known_red_may_be_carried_forward") is False, "known RED may not be carried forward", failures)
    _fail(core.get("repair_starts_immediately_on_material_red") is True, "repair must start immediately", failures)
    _fail(core.get("must_wait_for_all_independent_jobs_before_starting_repair") is False, "repair must not wait for all jobs", failures)

    same_sha = payload.get("same_sha_rerun", {})
    _fail(same_sha.get("allowed_only_when_source_unchanged") is True, "same-SHA rerun source rule missing", failures)
    _fail(same_sha.get("specific_failed_job_preferred") is True, "specific failed-job rerun must be preferred", failures)
    _fail(same_sha.get("blind_repeat_until_green_forbidden") is True, "blind rerun must be forbidden", failures)

    repair = payload.get("code_repair", {})
    _fail(repair.get("changed_content_requires_replacement_sha") is True, "content-changing repair must require replacement SHA", failures)
    _fail(repair.get("full_certification_required_before_next_checkpoint") is True, "replacement SHA full certification required", failures)
    _fail(repair.get("protected_main_force_rewrite_allowed") is False, "protected main rewrite must remain forbidden", failures)

    sonar = payload.get("sonar_review", {})
    _fail(sonar.get("quality_gate_pass_required_when_applicable") is True, "Sonar Quality Gate requirement missing", failures)
    _fail(sonar.get("new_issues_default") == 0, "Sonar new issues must default to zero", failures)
    _fail(sonar.get("unresolved_new_security_hotspots") == 0, "Sonar hotspots must be zero", failures)

    green = payload.get("green", {})
    _fail(green.get("accepted_check_conclusions") == ["success"], "only success may be GREEN", failures)
    _fail(REJECTED_GREEN.issubset(set(green.get("rejected_as_green", []))), "rejected GREEN state set incomplete", failures)

    main_policy = payload.get("main", {})
    _fail(main_policy.get("post_merge_red_state") == "MAIN_RED_STOP", "MAIN_RED_STOP policy missing", failures)
    _fail(main_policy.get("ordinary_feature_progress_allowed_while_main_red") is False, "feature work must stop on RED main", failures)

    surfaces = {
        AMENDMENT: (
            "Green Checkpoint & Targeted CI Repair Law / Amendment 16",
            "RED_REPAIR_ONLY",
            "TARGET_REPAIRED",
            "CERTIFIED_GREEN",
            "MAIN_RED_STOP",
            "Same-SHA targeted rerun",
            "Code/config repair requires a replacement SHA",
        ),
        RUNBOOK: (
            "ONE CHECKPOINT",
            "RED = REPAIR ONLY",
            "TARGETED RECHECK",
            "FULL CERTIFICATION",
        ),
        TARGETED_WORKFLOW: (
            "workflow_dispatch",
            "expected_sha",
            "lane",
            "^[0-9a-fA-F]{40}$",
            'git fetch --no-tags --depth=1 origin "$EXPECTED_HEAD"',
            "git rev-parse HEAD",
        ),
    }
    for path, markers in surfaces.items():
        content = _read(path, failures)
        for marker in markers:
            _fail(marker in content, f"{path.relative_to(ROOT)} missing marker: {marker}", failures)

    if failures:
        print("V10 Green Checkpoint governance check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("V10 Green Checkpoint governance check passed.")
    print("Flow: CHECKPOINT -> VERIFY -> RED_REPAIR_ONLY -> TARGETED_RECHECK -> FULL_CERTIFICATION -> CERTIFIED_GREEN")
    print("Next functional checkpoint requires CERTIFIED_GREEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
