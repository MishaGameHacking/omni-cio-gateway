from __future__ import annotations

import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md"
LIFECYCLE = ROOT / "docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md"
PROGRAM_LOCK = ROOT / "docs/master-plan/OMNI_CIO_V10_PROGRAM_LOCK.md"
AMENDMENTS_INDEX = ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md"
TOOLCHAIN = ROOT / "docs/architecture/V10_TOOLCHAIN_BASELINE.md"
START_RECORD = ROOT / "docs/master-plan/OMNI_CIO_V10_START_RECORD.md"
READINESS_AUDIT = ROOT / "docs/master-plan/OMNI_CIO_V10_PLAN_READINESS_AUDIT.md"
ENGINEERING_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_ENGINEERING_QUALITY_AND_GREEN_MERGE_AMENDMENT.md"
)
ENGINEERING_CONTRACT = (
    ROOT / "docs/architecture/V10_ENGINEERING_QUALITY_GATE_CONTRACT.json"
)

LIVE_GUIDANCE = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "CHANGELOG.md",
    ROOT / "docs/README.md",
    ROOT / "docs/master-plan/README.md",
    PROGRAM_LOCK,
    AMENDMENTS_INDEX,
    ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    ROOT / "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    ROOT / "gpt/PROJECT_INSTRUCTIONS.md",
    ROOT / "gpt/NEW_CHAT_PROMPT.md",
    ROOT / ".github/copilot-instructions.md",
)

STATUS_REFERENCE = "17_V10_CURRENT_PROGRAM_STATUS.md"
CANONICAL_STATUS_RELATIVE = Path("knowledge/17_V10_CURRENT_PROGRAM_STATUS.md")

STALE_LIVE_MARKERS = (
    "WP3 COMPLETE / WP4 NEXT",
    "Overall accepted V10 progress remains **5%**",
    "Current accepted V10 implementation progress remains **5%**",
    "accepted V10 progress remains 5%",
    "accepted progress = 5%",
    "WP4 — следующий work package",
    "WP4 is NEXT until",
    "WP2 will freeze",
    "Until WP2 acceptance",
    "reserved V10 adapters: future",
    "becomes authority only after its own exact-head GREEN merge",
    "must finish its own lifecycle",
)


def read_text(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(
            f"missing documentation authority file: {path.relative_to(ROOT)}"
        )
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def validate_status_uniqueness(failures: list[str]) -> None:
    candidates = sorted(
        path.relative_to(ROOT)
        for path in ROOT.rglob("*V10*CURRENT*PROGRAM*STATUS*")
        if path.is_file() and ".git" not in path.parts
    )
    if candidates != [CANONICAL_STATUS_RELATIVE]:
        rendered = ", ".join(str(path) for path in candidates) or "<none>"
        failures.append(
            f"V10 current-status authority is not unique; found: {rendered}"
        )


def extract_current_state(status: str, failures: list[str]) -> tuple[str, str]:
    progress_match = re.search(
        r"Accepted implementation progress is \*\*(\d+%)\*\*",
        status,
    )
    wp_match = re.search(
        r"^## Current next package — (WP[0-9A-Z]+)\b",
        status,
        re.MULTILINE,
    )
    if progress_match is None:
        failures.append(
            "current status is missing accepted implementation progress marker"
        )
    if wp_match is None:
        failures.append("current status is missing current-next-package heading")
    return (
        progress_match.group(1) if progress_match else "",
        wp_match.group(1) if wp_match else "",
    )


def validate_live_guidance(progress: str, wp: str, failures: list[str]) -> None:
    for path in LIVE_GUIDANCE:
        text = read_text(path, failures)
        if not text:
            continue
        if STATUS_REFERENCE not in text:
            failures.append(
                "live guidance does not delegate dynamic V10 state: "
                f"{path.relative_to(ROOT)}"
            )
        for marker in STALE_LIVE_MARKERS:
            if marker in text:
                failures.append(
                    f"stale live-state marker in {path.relative_to(ROOT)}: {marker}"
                )

    readme = read_text(ROOT / "README.md", failures)
    if progress and f"**{progress}**" not in readme:
        failures.append("root README current snapshot does not match status progress")
    if wp and wp not in readme:
        failures.append("root README current snapshot does not match current WP")
    for marker in (
        "## Current V10 snapshot",
        "WP23+ remains locked",
        "public Internet ingress remains OFF",
    ):
        if marker not in readme:
            failures.append(f"root README is missing current-snapshot marker: {marker}")

    agents = read_text(ROOT / "AGENTS.md", failures)
    if progress and f"accepted V10 progress is **{progress}**" not in agents:
        failures.append("AGENTS current snapshot does not match status progress")
    if wp and f"**{wp} —" not in agents:
        failures.append("AGENTS current snapshot does not match current WP")

    master_context = read_text(
        ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
        failures,
    )
    if progress and f"**{progress} accepted implementation**" not in master_context:
        failures.append(
            "Master Context convenience snapshot does not match status progress"
        )
    if (
        wp
        and f"**{wp}** as the current authorized functional package"
        not in master_context
    ):
        failures.append("Master Context convenience snapshot does not match current WP")


def validate_high_risk_headers(failures: list[str]) -> None:
    program_lock = read_text(PROGRAM_LOCK, failures)
    if "SCOPE-SEQUENCE LOCK" not in program_lock:
        failures.append("Program Lock must be labeled as scope-sequence lock")
    if (
        "Dynamic current WP/progress is intentionally not duplicated here"
        not in program_lock
    ):
        failures.append("Program Lock must explicitly delegate dynamic current state")

    toolchain = read_text(TOOLCHAIN, failures)
    if "WP2 ACCEPTED BASELINE" not in toolchain:
        failures.append("WP2 toolchain baseline must be labeled accepted")
    if "FINAL EXIT GATE PENDING" in toolchain:
        failures.append(
            "accepted WP2 toolchain baseline still claims pending exit gate"
        )

    for path in (START_RECORD, READINESS_AUDIT):
        text = read_text(path, failures)
        if "HISTORICAL SNAPSHOT — NOT CURRENT-STATE AUTHORITY" not in text:
            failures.append(
                "high-risk historical record lacks lifecycle banner: "
                f"{path.relative_to(ROOT)}"
            )

    amendment = read_text(ENGINEERING_AMENDMENT, failures)
    if "ACCEPTED ON `main` / ACTIVE" not in amendment:
        failures.append(
            "engineering-quality amendment must be labeled accepted/active"
        )
    if "EFFECTIVE ONLY AFTER MERGE" in amendment:
        failures.append(
            "engineering-quality amendment still claims future activation"
        )

    contract_text = read_text(ENGINEERING_CONTRACT, failures)
    if not contract_text:
        return

    try:
        contract = json.loads(contract_text)
    except json.JSONDecodeError as exc:
        failures.append(f"engineering-quality contract JSON invalid: {exc}")
        return

    if contract.get("status") != "ACTIVE_ACCEPTED_ON_MAIN":
        failures.append("engineering-quality contract status is not active/accepted")

    acceptance = contract.get("acceptance_evidence")
    if not isinstance(acceptance, dict):
        failures.append("engineering-quality contract lacks acceptance evidence")
        return

    expected_main = "1c05390d9cf31b8cc68a90a5d7cbd6428ffe7791"
    if acceptance.get("main_sha") != expected_main:
        failures.append("engineering-quality contract accepted main SHA mismatch")
    if acceptance.get("regression_shield_conclusion") != "success":
        failures.append(
            "engineering-quality contract lacks GREEN post-merge evidence"
        )


def validate_repository_lifecycle(failures: list[str]) -> None:
    lifecycle = read_text(LIFECYCLE, failures)
    for marker in (
        "Live current-authority layer",
        "Stable program and architecture contracts",
        "Work-Package execution and runbook records",
        "Historical audit/start/acceptance records",
        "Applied V9 recovery/configuration records",
        "Permanent automated guard",
    ):
        if marker not in lifecycle:
            failures.append(
                f"documentation lifecycle is missing section marker: {marker}"
            )

    repo_structure = read_text(
        ROOT / "docs/architecture/REPOSITORY_STRUCTURE.md",
        failures,
    )
    if "apps/api/" not in repo_structure or "apps/web/" not in repo_structure:
        failures.append("repository structure does not show accepted V10 API/Web roots")
    if "accepted/active V10 adapter roots" not in repo_structure:
        failures.append(
            "repository structure still lacks current accepted-root lifecycle wording"
        )


def main() -> int:
    failures: list[str] = []
    validate_status_uniqueness(failures)

    status = read_text(STATUS, failures)
    progress, wp = extract_current_state(status, failures) if status else ("", "")

    validate_live_guidance(progress, wp, failures)
    validate_high_risk_headers(failures)
    validate_repository_lifecycle(failures)

    if failures:
        for failure in failures:
            print(f"DOC_CONSISTENCY_FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "V10 documentation consistency passed: "
        f"current status {progress}, current WP {wp}; "
        "live guidance and lifecycle labels aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
