from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

UI_NAME = "Omni-CIO API | Управляющий и аналитик v8.6.1"
INSTRUCTIONS_PATH = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt"
ENGINEERING_REFERENCE = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt"
PROGRAM_PATH = "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
BASELINE_CONTRACT = "docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md"
BASELINE_COMMIT = (  # pragma: allowlist secret
    "baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e"
)
GATEWAY_URL = "https://omni-cio-gateway.onrender.com"
OPENAPI_URL = f"{GATEWAY_URL}/openapi.json"
HEALTH_URL = f"{GATEWAY_URL}/health"
ENTRYPOINT = "app:app"
INSTRUCTIONS_MAX_CHARS = 8000

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

RECOVERY_DOCS = (
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
    "gpt/MY_GPT_SETUP_RUNBOOK.md",
)

IDENTITY_DOCS = (
    "README.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/MY_GPT_SETUP_RUNBOOK.md",
)

STATUS_DOCS = (
    "AGENTS.md",
    "README.md",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/MY_GPT_SETUP_RUNBOOK.md",
)

REAL_ACTIONS = (
    "getRealTradingStatus",
    "prepareRealTrade",
    "executeRealTrade",
    "getRealOrderState",
)

STALE_RELEASE_MARKERS = (
    "Only Phase 4 remains",
    "ONLY remaining release gate",
    "Phase 4 remains",
    "the only remaining definition-of-done gate is phase 4",
    "first controlled real order remains the only release gate",
    "no real broker order has been submitted",
    "ui name may still show `omni-cio api | управляющий и аналитик v8.4`",
    "canonical instructions behavior: `gpt/custom_gpt_instructions_v8_6_0.txt`",
)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"missing canonical file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, file_name: str) -> None:
    if needle not in text:
        raise AssertionError(f"{file_name}: missing canonical value {needle!r}")


def reject_stale_markers(file_name: str, text: str) -> None:
    folded = text.casefold()
    for marker in STALE_RELEASE_MARKERS:
        if marker.casefold() in folded:
            raise AssertionError(
                f"{file_name}: stale recovery marker found: {marker!r}"
            )


def check_knowledge_registry(contents: dict[str, str]) -> None:
    expected = set(KNOWLEDGE_FILES)
    knowledge_root = ROOT / "gpt" / "knowledge"
    actual = {path.name for path in knowledge_root.glob("*.txt") if path.is_file()}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise AssertionError(
            "gpt/knowledge registry mismatch: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )

    for knowledge_file in KNOWLEDGE_FILES:
        for file_name in (
            "gpt/CONFIGURATION.md",
            "gpt/SETUP_INDEX.md",
            "gpt/BOT_ONLY_FILE_MANIFEST.md",
        ):
            require(contents[file_name], knowledge_file, file_name)


def check_instruction_payload() -> None:
    instructions = read(INSTRUCTIONS_PATH)
    if len(instructions) > INSTRUCTIONS_MAX_CHARS:
        raise AssertionError(
            f"{INSTRUCTIONS_PATH}: {len(instructions)} characters exceed "
            f"the {INSTRUCTIONS_MAX_CHARS}-character GPT Editor limit"
        )
    require(instructions, "v8.6.1 Compact", INSTRUCTIONS_PATH)


def check_program_lock() -> None:
    program = read(PROGRAM_PATH)
    require(program, "OWNER-APPROVED / PROGRAM LOCKED", PROGRAM_PATH)
    require(program, "Baseline protected: **Omni-CIO v8.6.1**", PROGRAM_PATH)
    for number in range(16):
        require(program, f"### WP{number} —", PROGRAM_PATH)

    contract = read(BASELINE_CONTRACT)
    require(contract, BASELINE_COMMIT, BASELINE_CONTRACT)
    require(contract, INSTRUCTIONS_PATH, BASELINE_CONTRACT)
    require(contract, PROGRAM_PATH, BASELINE_CONTRACT)

    agent_rules = read("AGENTS.md")
    require(agent_rules, PROGRAM_PATH, "AGENTS.md")
    require(agent_rules, BASELINE_CONTRACT, "AGENTS.md")
    require(agent_rules, BASELINE_COMMIT, "AGENTS.md")
    require(agent_rules, "самый ранний незавершённый work package", "AGENTS.md")


def check_action_registry() -> None:
    catalog = read("gpt/ACTIONS_CATALOG.md")
    config = read("gpt/CONFIGURATION.md")
    for action in REAL_ACTIONS:
        require(catalog, action, "gpt/ACTIONS_CATALOG.md")
        require(config, action, "gpt/CONFIGURATION.md")


def main() -> None:
    file_names = set(RECOVERY_DOCS + IDENTITY_DOCS + STATUS_DOCS)
    contents = {name: read(name) for name in file_names}

    for name in IDENTITY_DOCS:
        require(contents[name], UI_NAME, name)
        require(contents[name], INSTRUCTIONS_PATH, name)

    for name in RECOVERY_DOCS:
        require(contents[name], GATEWAY_URL, name)
        require(contents[name], OPENAPI_URL, name)
        require(contents[name], ENTRYPOINT, name)
        reject_stale_markers(name, contents[name])

    for name in STATUS_DOCS:
        reject_stale_markers(name, contents[name])

    status_name = "knowledge/16_CURRENT_PROGRAM_STATUS.md"
    status = contents[status_name]
    require(status, "100% complete", status_name)
    require(status, "idempotent replay verified with no second submit", status_name)
    require(status, PROGRAM_PATH, status_name)

    for name in ("gpt/SETUP_INDEX.md", "gpt/MY_GPT_SETUP_RUNBOOK.md"):
        require(contents[name], HEALTH_URL, name)

    require(
        contents["gpt/SETUP_INDEX.md"],
        ENGINEERING_REFERENCE,
        "gpt/SETUP_INDEX.md",
    )
    require(
        contents["gpt/CONFIGURATION.md"],
        ENGINEERING_REFERENCE,
        "gpt/CONFIGURATION.md",
    )
    require(
        contents["gpt/BOT_ONLY_FILE_MANIFEST.md"],
        PROGRAM_PATH,
        "gpt/BOT_ONLY_FILE_MANIFEST.md",
    )

    check_knowledge_registry(contents)
    check_instruction_payload()
    check_program_lock()
    check_action_registry()

    print("GPT recovery consistency: OK")
    print(f"UI: {UI_NAME}")
    print(f"Instructions: {INSTRUCTIONS_PATH}")
    print(f"Instructions chars: {len(read(INSTRUCTIONS_PATH))}/{INSTRUCTIONS_MAX_CHARS}")
    print(f"Knowledge files: {len(KNOWLEDGE_FILES)}")
    print(f"Protected baseline commit: {BASELINE_COMMIT}")
    print(f"Active program: {PROGRAM_PATH}")


if __name__ == "__main__":
    main()
