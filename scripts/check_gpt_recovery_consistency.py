from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UI_NAME = "Omni-CIO API | Управляющий и аналитик v8.6.1"
INSTRUCTIONS_PATH = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt"
PROGRAM_PATH = "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
GATEWAY_URL = "https://omni-cio-gateway.onrender.com"
ENTRYPOINT = "app:app"

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

CANONICAL_FILES = (
    "README.md",
    "AGENTS.md",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
)

STALE_RELEASE_MARKERS = (
    "Only Phase 4 remains",
    "ONLY remaining release gate",
    "Phase 4 remains",
    "first controlled real order remains the only release gate",
    "no real broker order has been submitted",
)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing canonical file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, file_name: str) -> None:
    if needle not in text:
        raise AssertionError(f"{file_name}: missing canonical value {needle!r}")


def main() -> None:
    contents = {name: read(name) for name in CANONICAL_FILES}

    for name, text in contents.items():
        require(text, UI_NAME, name)
        require(text, INSTRUCTIONS_PATH, name)

    for name in ("README.md", "AGENTS.md", "gpt/SETUP_INDEX.md"):
        require(contents[name], GATEWAY_URL, name)

    for name in ("README.md", "AGENTS.md", "gpt/SETUP_INDEX.md"):
        require(contents[name], ENTRYPOINT, name)

    for name in (
        "AGENTS.md",
        "knowledge/16_CURRENT_PROGRAM_STATUS.md",
        "gpt/SETUP_INDEX.md",
        "gpt/BOT_ONLY_FILE_MANIFEST.md",
    ):
        require(contents[name], PROGRAM_PATH, name)

    config = contents["gpt/CONFIGURATION.md"]
    setup = contents["gpt/SETUP_INDEX.md"]
    manifest = contents["gpt/BOT_ONLY_FILE_MANIFEST.md"]
    for knowledge_file in KNOWLEDGE_FILES:
        for file_name, text in (
            ("gpt/CONFIGURATION.md", config),
            ("gpt/SETUP_INDEX.md", setup),
            ("gpt/BOT_ONLY_FILE_MANIFEST.md", manifest),
        ):
            require(text, knowledge_file, file_name)
        if not (ROOT / "gpt" / "knowledge" / knowledge_file).is_file():
            raise AssertionError(f"missing Knowledge file: {knowledge_file}")

    status = contents["knowledge/16_CURRENT_PROGRAM_STATUS.md"]
    require(status, "100% complete", "knowledge/16_CURRENT_PROGRAM_STATUS.md")
    require(status, "idempotent replay verified with no second submit", "knowledge/16_CURRENT_PROGRAM_STATUS.md")

    for file_name, text in contents.items():
        for marker in STALE_RELEASE_MARKERS:
            if marker.casefold() in text.casefold():
                raise AssertionError(f"{file_name}: stale release marker found: {marker!r}")

    print("GPT recovery consistency: OK")
    print(f"UI: {UI_NAME}")
    print(f"Instructions: {INSTRUCTIONS_PATH}")
    print(f"Knowledge files: {len(KNOWLEDGE_FILES)}")
    print(f"Active program: {PROGRAM_PATH}")


if __name__ == "__main__":
    main()
