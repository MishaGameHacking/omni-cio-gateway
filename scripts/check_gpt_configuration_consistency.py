from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

CANONICAL_UI_NAME = "Omni-CIO API | Управляющий и аналитик v8.6.1"
CANONICAL_INSTRUCTIONS = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt"
V9_PROGRAM = "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
V9_BASELINE = "docs/architecture/V9_BASELINE_FREEZE_AND_MIGRATION.md"

KNOWLEDGE_FILES = (
    "02_GATEWAY_DATA_CONTRACT_V2_OPERATIONS.txt",
    "04_CIO_PORTFOLIO_MANAGER.txt",
    "05_ANALYST_NEWS_SIMPLE_LANGUAGE.txt",
    "06_EVIDENCE_CREDIT_BANKRUPTCY.txt",
    "07_PERSONAL_STRATEGY.txt",
    "08_DECISION_JOURNAL_AND_QUALITY_CONTROL.txt",
    "09_AUTONOMOUS_ACTION_ORCHESTRATOR.txt",
    "10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt",
    "11_RISK_DECOMPOSITION_AND_SIZING_GATES.txt",
    "13_COMMUNICATION_STYLE_2026.txt",
)

ACTIVE_RECOVERY_FILES = (
    "README.md",
    "AGENTS.md",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
    "gpt/PROJECT_INSTRUCTIONS.md",
    "gpt/NEW_CHAT_PROMPT.md",
)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing canonical file: {relative}")
    return path.read_text(encoding="utf-8")


def validate() -> list[str]:
    failures: list[str] = []

    required = (CANONICAL_INSTRUCTIONS, V9_PROGRAM, V9_BASELINE)
    for relative in required:
        if not (ROOT / relative).is_file():
            failures.append(f"missing required canonical path: {relative}")

    for name in KNOWLEDGE_FILES:
        if not (ROOT / "gpt" / "knowledge" / name).is_file():
            failures.append(f"missing production Knowledge file: {name}")

    try:
        config = read("gpt/CONFIGURATION.md")
        setup = read("gpt/SETUP_INDEX.md")
        manifest = read("gpt/BOT_ONLY_FILE_MANIFEST.md")
        status = read("knowledge/16_CURRENT_PROGRAM_STATUS.md")
        program = read(V9_PROGRAM)
    except AssertionError as exc:
        failures.append(str(exc))
        return failures

    for relative in ACTIVE_RECOVERY_FILES:
        try:
            text = read(relative)
        except AssertionError as exc:
            failures.append(str(exc))
            continue
        if "CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt" in text and relative in {
            "gpt/SETUP_INDEX.md",
            "gpt/PROJECT_INSTRUCTIONS.md",
            "gpt/NEW_CHAT_PROMPT.md",
        }:
            failures.append(
                f"stale v8.4.1 production instruction reference in {relative}"
            )

    for relative, text in {
        "gpt/CONFIGURATION.md": config,
        "gpt/SETUP_INDEX.md": setup,
        "gpt/BOT_ONLY_FILE_MANIFEST.md": manifest,
        "knowledge/16_CURRENT_PROGRAM_STATUS.md": status,
    }.items():
        if CANONICAL_UI_NAME not in text:
            failures.append(f"canonical UI name missing from {relative}")
        if CANONICAL_INSTRUCTIONS not in text:
            failures.append(f"canonical Instructions path missing from {relative}")

    for relative, text in {
        "gpt/SETUP_INDEX.md": setup,
        "gpt/BOT_ONLY_FILE_MANIFEST.md": manifest,
        "knowledge/16_CURRENT_PROGRAM_STATUS.md": status,
    }.items():
        if V9_PROGRAM not in text:
            failures.append(f"active v9 program link missing from {relative}")

    if "OWNER-APPROVED / PROGRAM LOCKED" not in program:
        failures.append("v9 program is not marked OWNER-APPROVED / PROGRAM LOCKED")

    if "100% complete" not in status:
        failures.append("current status does not preserve v8.6.1 release completion")

    if "Phase 4 remains" in config or "ONLY remaining release gate" in setup:
        failures.append("recovery docs still claim Phase 4 is incomplete")

    for name in KNOWLEDGE_FILES:
        if name not in config:
            failures.append(f"CONFIGURATION.md omits Knowledge file: {name}")
        if name not in setup:
            failures.append(f"SETUP_INDEX.md omits Knowledge file: {name}")
        if name not in manifest:
            failures.append(f"BOT_ONLY_FILE_MANIFEST.md omits Knowledge file: {name}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("GPT/configuration consistency check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("GPT/configuration consistency check passed.")
    print(f"Applied GPT baseline: {CANONICAL_UI_NAME}")
    print(f"Canonical Instructions: {CANONICAL_INSTRUCTIONS}")
    print(f"Production Knowledge files: {len(KNOWLEDGE_FILES)}")
    print(f"Active development program: {V9_PROGRAM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
