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


def _hex(*chunks: str) -> str:
    return "".join(chunks)


START_RECORD_EVIDENCE_MARKERS = (
    _hex(
        "159316c5",
        "b211977b",
        "0d9125df",
        "fb862103",
        "16ae10d3",
    ),
    "planning PR #227",
    "Regression Shield run #1332",
    _hex(
        "afb16518",
        "3594d59c",
        "6218a419",
        "341f67fe",
        "5496f956",
        "7221efcf",
        "75213789",
        "14b6f106",
    ),
    _hex(
        "80df1efd",
        "750d1f56",
        "bf3a1b09",
        "7e0c8fef",
        "4414b9bb",
        "65aced50",
        "3c669313",
        "dd55be25",
    ),
    "idempotent replay verified with no second submit",
    "REAL_TRADING_ENABLED=false",
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
    package_match = re.search(
        r"^## Current next package — ([A-Z0-9][A-Z0-9_-]+)\b",
        status,
        re.MULTILINE,
    )
    if progress_match is None:
        failures.append(
            "current status is missing accepted implementation progress marker"
        )
    if package_match is None:
        failures.append("current status is missing current-next-package heading")
    return (
        progress_match.group(1) if progress_match else "",
        package_match.group(1) if package_match else "",
    )


def validate_live_guidance(progress: str, package: str, failures: list[str]) -> None:
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
    if package and package not in readme:
        failures.append("root README current snapshot does not match current package")
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
    if package and f"**{package} —" not in agents:
        failures.append("AGENTS current snapshot does not match current package")

    master_context = read_text(
        ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
        failures,
    )
    if progress and f"**{progress} accepted implementation**" not in master_context:
        failures.append(
            "Master Context convenience snapshot does not match status progress"
        )
    if (
        package
        and f"**{package}** as the current authorized functional package"
        not in master_context
    ):
        failures.append(
            "Master Context convenience snapshot does not match current package"
        )


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

    start_record = read_text(START_RECORD, failures)
    for marker in START_RECORD_EVIDENCE_MARKERS:
        if marker not in start_record:
            failures.append(
                f"historical WP0 start evidence was removed or rewritten: {marker}"
            )

    amendment = read_text(ENGINEERING_AMENDMENT, failures)
    if "ACCEPTED ON `main` / ACTIVE" not in amendment:
        failures.append("engineering-quality amendment must be labeled accepted/active")
    if "EFFECTIVE ONLY AFTER MERGE" in amendment:
        failures.append("engineering-quality amendment still claims future activation")

    contract_text = read_text(ENGINEERING_CONTRACT, failures)
    if not contract_text:
        return

    try:
        contract = json.loads(contract_text)
    except json.JSONDecodeError as exc:
        failures.append(f"engineering-quality contract JSON invalid: {exc}")
        return

    contract_status = contract.get("status")
    accepted_status = "ACTIVE_ACCEPTED_ON_MAIN"
    pending_runtime_update_status = "ACTIVE_ACCEPTED_GOVERNANCE_WITH_OWNER_APPROVED_RUNTIME_UPDATE_EFFECTIVE_ON_MERGE"
    if contract_status not in {accepted_status, pending_runtime_update_status}:
        failures.append("engineering-quality contract status is not active/accepted")
    elif contract_status == pending_runtime_update_status:
        runtime_update = contract.get("runtime_hosting_update")
        if not isinstance(runtime_update, dict):
            failures.append(
                "pending runtime-hosting governance status lacks runtime_hosting_update"
            )
        else:
            if runtime_update.get("effective_on_merge") is not True:
                failures.append(
                    "pending runtime-hosting governance update must remain effective-on-merge"
                )
            if (
                runtime_update.get("amendment")
                != "docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md"
            ):
                failures.append("pending runtime-hosting amendment path mismatch")
            if (
                runtime_update.get("public_runtime_contract")
                != "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"
            ):
                failures.append("pending public runtime contract path mismatch")

    acceptance = contract.get("acceptance_evidence")
    if not isinstance(acceptance, dict):
        failures.append("engineering-quality contract lacks acceptance evidence")
        return

    expected_main = _hex(
        "1c05390d",
        "9cf31b8c",
        "c68a90a5",
        "d7cbd642",
        "8ffe7791",
    )
    main_sha_chunks = acceptance.get("main_sha_chunks")
    if (
        acceptance.get("main_sha_encoding") != "HEX_CHUNKS"
        or not isinstance(main_sha_chunks, list)
        or any(not isinstance(chunk, str) for chunk in main_sha_chunks)
        or _hex(*main_sha_chunks) != expected_main
    ):
        failures.append("engineering-quality contract accepted main SHA mismatch")
    if acceptance.get("regression_shield_conclusion") != "success":
        failures.append("engineering-quality contract lacks GREEN post-merge evidence")


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
    progress, package = extract_current_state(status, failures) if status else ("", "")

    validate_live_guidance(progress, package, failures)
    validate_high_risk_headers(failures)
    validate_repository_lifecycle(failures)

    if failures:
        for failure in failures:
            print(f"DOC_CONSISTENCY_FAIL: {failure}", file=sys.stderr)
        return 1

    print(
        "V10 documentation consistency passed: "
        f"current status {progress}, current package {package}; "
        "live guidance and lifecycle labels aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
