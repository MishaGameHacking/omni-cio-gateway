from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CURRENT_RELEASE = "v8.6.1"
CURRENT_INSTRUCTIONS = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt"
V9_PROGRAM = "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
V9_RESEARCH = "docs/architecture/V9_RESEARCH_AND_ENGINEERING_PRINCIPLES.md"

REQUIRED_REFERENCES = {
    "AGENTS.md": (CURRENT_INSTRUCTIONS, V9_PROGRAM, V9_RESEARCH),
    "knowledge/00_PROJECT_MASTER_CONTEXT.md": (
        CURRENT_RELEASE,
        CURRENT_INSTRUCTIONS,
        V9_PROGRAM,
    ),
    "knowledge/16_CURRENT_PROGRAM_STATUS.md": (
        CURRENT_RELEASE,
        CURRENT_INSTRUCTIONS,
        V9_PROGRAM,
    ),
    "docs/master-plan/README.md": (V9_PROGRAM,),
    "gpt/SETUP_INDEX.md": (CURRENT_RELEASE, CURRENT_INSTRUCTIONS, V9_PROGRAM),
    "gpt/BOT_ONLY_FILE_MANIFEST.md": (
        CURRENT_RELEASE,
        CURRENT_INSTRUCTIONS,
        V9_PROGRAM,
    ),
}

FORBIDDEN_STALE_CLAIMS = {
    "knowledge/00_PROJECT_MASTER_CONTEXT.md": (
        "**Only remaining release gate:** Phase 4",
        "Only remaining release gate: Phase 4",
    ),
    "gpt/SETUP_INDEX.md": (
        "ONLY remaining release gate — Phase 4",
        "ONLY remaining release gate",
    ),
    "gpt/BOT_ONLY_FILE_MANIFEST.md": (
        "CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt` | Единственные production Instructions",
        "Для production Instructions есть один файл — `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`",
    ),
}

PROGRAM_LOCK_MARKERS = {
    "AGENTS.md": (
        "ACTIVE PROGRAM LOCK",
        "earliest incomplete v9 work package",
        "protected production/recovery baseline",
    ),
    V9_PROGRAM: (
        "OWNER-APPROVED / PROGRAM LOCKED",
        "Definition of Done",
        "stable v8.6.1 production contour",
    ),
    "knowledge/16_CURRENT_PROGRAM_STATUS.md": (
        "Active development program — LOCKED",
        "WP0 — Baseline freeze and recovery correctness",
    ),
}


def read_text(relative: str, failures: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        failures.append(f"missing canonical file: {relative}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"cannot read {relative}: {exc}")
        return ""


def validate_required_files(failures: list[str]) -> None:
    for relative in (
        CURRENT_INSTRUCTIONS,
        "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt",
        V9_PROGRAM,
        V9_RESEARCH,
    ):
        if not (ROOT / relative).is_file():
            failures.append(f"required source-of-truth file is missing: {relative}")


def validate_references(failures: list[str]) -> None:
    for relative, tokens in REQUIRED_REFERENCES.items():
        text = read_text(relative, failures)
        for token in tokens:
            if text and token not in text:
                failures.append(f"{relative} is missing canonical reference: {token}")


def validate_no_stale_claims(failures: list[str]) -> None:
    for relative, phrases in FORBIDDEN_STALE_CLAIMS.items():
        text = read_text(relative, failures)
        for phrase in phrases:
            if text and phrase in text:
                failures.append(f"{relative} contains stale production claim: {phrase}")


def validate_program_lock(failures: list[str]) -> None:
    for relative, markers in PROGRAM_LOCK_MARKERS.items():
        text = read_text(relative, failures)
        for marker in markers:
            if text and marker not in text:
                failures.append(f"{relative} does not enforce v9 program lock: {marker}")


def validate_unfinished_v9_not_promoted(failures: list[str]) -> None:
    setup = read_text("gpt/SETUP_INDEX.md", failures).lower()
    if setup and not (
        "v8.6.1" in setup
        and "not unfinished v9 behavior" in setup
        and "recovery" in setup
    ):
        failures.append("gpt/SETUP_INDEX.md must preserve v8.6.1 as the recovery baseline")


def validate_repository() -> list[str]:
    failures: list[str] = []
    validate_required_files(failures)
    validate_references(failures)
    validate_no_stale_claims(failures)
    validate_program_lock(failures)
    validate_unfinished_v9_not_promoted(failures)
    return failures


def main() -> int:
    failures = validate_repository()
    if failures:
        print("Canonical configuration consistency check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Canonical configuration consistency check passed.")
    print(f"Current production: {CURRENT_RELEASE}")
    print(f"Current Instructions: {CURRENT_INSTRUCTIONS}")
    print(f"Active program: {V9_PROGRAM}")
    print("Unfinished v9 is not promoted over the protected v8.6.1 fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
