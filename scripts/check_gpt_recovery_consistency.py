from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TARGET_RELEASE = "v9.0.0"
TARGET_UI_NAME = "Omni-CIO API | Управляющий и аналитик v9.0.0"
TARGET_INSTRUCTIONS = "gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt"
TARGET_KNOWLEDGE_MANIFEST = "gpt/KNOWLEDGE_MANIFEST_V9_0_0.md"
PROTECTED_UI_NAME = "Omni-CIO API | Управляющий и аналитик v8.6.1"
PROTECTED_INSTRUCTIONS = "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt"
PROGRAM_PATH = "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md"
BASELINE_CONTRACT = "docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md"
WP15_ARCH = "docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_AND_RECOVERY.md"
WP15_THREAT = "docs/architecture/V9_CUSTOM_GPT_CONFIGURATION_THREAT_MODEL.md"
BASELINE_COMMIT = "baba0fb73e0483fc82b3f0bc7c2f15cbd71d804e"  # pragma: allowlist secret
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

BASELINE_ACTIONS = (
    "gatewayHealth",
    "getConnection",
    "getPortfolioSnapshot",
    "getEnrichedPortfolioSnapshot",
    "findInstrument",
    "getOperationsHistory",
    "getMarketSnapshot",
    "getPortfolioMarketSnapshot",
    "getPortfolioAnalytics",
    "getCashLiquiditySnapshot",
    "getPurchaseCapacityPreview",
    "getOperationsAnalytics",
    "getBrokerReportReconciliation",
    "getFinalDecisionReview",
)

REAL_ACTIONS = (
    "getRealTradingStatus",
    "prepareRealTrade",
    "executeRealTrade",
    "getRealOrderState",
)

SANDBOX_ACTIONS = (
    "getSandboxTradingStatus",
    "openSandboxAccount",
    "fundSandboxAccount",
    "getSandboxPortfolio",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "getSandboxOrderState",
    "cancelSandboxOrder",
)

TARGET_DOCS = (
    "gpt/SETUP_INDEX.md",
    "gpt/CONFIGURATION.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
    "gpt/MY_GPT_SETUP_RUNBOOK.md",
)

RECOVERY_DOCS = TARGET_DOCS + (
    "gpt/ACTIONS_CATALOG.md",
    "gpt/SECRETS_AND_RENDER.md",
)


class GptRecoveryConsistencyError(AssertionError):
    pass


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise GptRecoveryConsistencyError(f"missing canonical file: {relative}")
    return path.read_text(encoding="utf-8")


def require(text: str, needle: str, file_name: str) -> None:
    if needle not in text:
        raise GptRecoveryConsistencyError(
            f"{file_name}: missing canonical value {needle!r}"
        )


def reject(text: str, needle: str, file_name: str) -> None:
    if needle.casefold() in text.casefold():
        raise GptRecoveryConsistencyError(
            f"{file_name}: forbidden/stale canonical value {needle!r}"
        )


def check_instruction_payload() -> None:
    instructions = read(TARGET_INSTRUCTIONS)
    if len(instructions) > INSTRUCTIONS_MAX_CHARS:
        raise GptRecoveryConsistencyError(
            f"{TARGET_INSTRUCTIONS}: {len(instructions)} characters exceed "
            f"the {INSTRUCTIONS_MAX_CHARS}-character repository limit"
        )
    for marker in (
        "Instructions v9.0.0 Compact",
        "REAL READ-ONLY",
        "REAL EXECUTION",
        "SANDBOX",
        "NO_ACTION",
        "getRealTradingStatus",
        "prepareRealTrade",
        "executeRealTrade",
        "getRealOrderState",
        "Реальная заявка ещё не отправлена",
        "не притворяйся, что вызвал",
    ):
        require(instructions, marker, TARGET_INSTRUCTIONS)
    reject(instructions, "Thinking 5.6", TARGET_INSTRUCTIONS)


def check_knowledge_registry() -> None:
    expected = set(KNOWLEDGE_FILES)
    actual = {
        path.name
        for path in (ROOT / "gpt" / "knowledge").glob("*.txt")
        if path.is_file()
    }
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise GptRecoveryConsistencyError(
            "gpt/knowledge registry mismatch: "
            f"missing={missing or 'none'}, extra={extra or 'none'}"
        )

    manifest = read(TARGET_KNOWLEDGE_MANIFEST)
    require(manifest, "Exact upload set — 10 files", TARGET_KNOWLEDGE_MANIFEST)
    for file_name in KNOWLEDGE_FILES:
        if manifest.count(f"`{file_name}`") != 1:
            raise GptRecoveryConsistencyError(
                f"{TARGET_KNOWLEDGE_MANIFEST}: {file_name!r} must appear exactly once"
            )


def check_target_registry() -> None:
    for file_name in TARGET_DOCS:
        text = read(file_name)
        require(text, TARGET_UI_NAME, file_name)
        require(text, TARGET_INSTRUCTIONS, file_name)
        require(text, TARGET_KNOWLEDGE_MANIFEST, file_name)
        require(text, PROTECTED_INSTRUCTIONS, file_name)
        require(text, "existing", file_name)

    configuration = read("gpt/CONFIGURATION.md")
    for marker in (
        "Repository target config: **v9.0.0**",
        "Applied external GPT: **v9.0.0**",
        "Actions: **ON**",
        "Apps: **OFF**",
        "non-Pro model that supports Custom GPT Actions",
    ):
        require(configuration, marker, "gpt/CONFIGURATION.md")
    reject(
        configuration, "Applied external GPT remains **v8.6.1**", "gpt/CONFIGURATION.md"
    )
    reject(configuration, "Recommended model: `Thinking 5.6`", "gpt/CONFIGURATION.md")


def check_recovery_docs() -> None:
    for file_name in RECOVERY_DOCS:
        text = read(file_name)
        require(text, GATEWAY_URL, file_name)
        if file_name != "gpt/SECRETS_AND_RENDER.md":
            require(text, OPENAPI_URL, file_name)
        require(text, ENTRYPOINT, file_name)

    setup = read("gpt/SETUP_INDEX.md")
    runbook = read("gpt/MY_GPT_SETUP_RUNBOOK.md")
    for text, file_name in (
        (setup, "gpt/SETUP_INDEX.md"),
        (runbook, "gpt/MY_GPT_SETUP_RUNBOOK.md"),
    ):
        require(text, HEALTH_URL, file_name)
        require(text, "Do not", file_name)
        require(text, "Update", file_name)

    require(
        runbook, "Owner Preview acceptance — mandatory", "gpt/MY_GPT_SETUP_RUNBOOK.md"
    )
    require(runbook, "Do not Create a new GPT", "gpt/MY_GPT_SETUP_RUNBOOK.md")
    require(runbook, "Internal v9 capability honesty", "gpt/MY_GPT_SETUP_RUNBOOK.md")


def check_actions() -> None:
    catalog = read("gpt/ACTIONS_CATALOG.md")
    instructions = read(TARGET_INSTRUCTIONS)
    for action in BASELINE_ACTIONS + SANDBOX_ACTIONS + REAL_ACTIONS:
        require(catalog, action, "gpt/ACTIONS_CATALOG.md")
    for action in REAL_ACTIONS:
        require(instructions, action, TARGET_INSTRUCTIONS)
    for marker in (
        "not automatically GPT Actions",
        "effective imported OpenAPI",
        "14 GET Actions",
        "include_in_schema=False",
    ):
        require(catalog, marker, "gpt/ACTIONS_CATALOG.md")


def check_program_and_rollback() -> None:
    program = read(PROGRAM_PATH)
    require(program, "OWNER-APPROVED / PROGRAM LOCKED", PROGRAM_PATH)
    require(program, "Baseline protected: **Omni-CIO v8.6.1**", PROGRAM_PATH)
    for number in range(16):
        require(program, f"### WP{number} —", PROGRAM_PATH)

    baseline = read(BASELINE_CONTRACT)
    require(baseline, BASELINE_COMMIT, BASELINE_CONTRACT)
    require(baseline, PROTECTED_INSTRUCTIONS, BASELINE_CONTRACT)

    for relative in (WP15_ARCH, WP15_THREAT):
        text = read(relative)
        require(text, TARGET_RELEASE, relative)
        require(text, PROTECTED_INSTRUCTIONS, relative)

    status = read("knowledge/16_CURRENT_PROGRAM_STATUS.md")
    require(
        status,
        "Applied external GPT: **v9.0.0**",
        "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    )
    require(status, "100% complete", "knowledge/16_CURRENT_PROGRAM_STATUS.md")
    require(
        status,
        "idempotent replay verified with no second submit",
        "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    )
    require(status, PROGRAM_PATH, "knowledge/16_CURRENT_PROGRAM_STATUS.md")


def check_external_secret_boundary() -> None:
    text = read("gpt/SECRETS_AND_RENDER.md")
    for marker in (
        "TINVEST_TOKEN",
        "TINVEST_SANDBOX_TOKEN",
        "TINVEST_TRADING_TOKEN",
        "GATEWAY_API_KEY",
        "UPSTASH_REDIS_REST_URL",
        "UPSTASH_REDIS_REST_TOKEN",
        "WATCHTOWER_ENABLED",
        "QSTASH_CURRENT_SIGNING_KEY",
        "QSTASH_NEXT_SIGNING_KEY",
        "QSTASH_TOKEN",
        "WATCHTOWER_JOURNAL_SECRET",
        "WATCHTOWER_CRON",
    ):
        require(text, marker, "gpt/SECRETS_AND_RENDER.md")
    require(text, "REAL_TRADING_ENABLED=false", "gpt/SECRETS_AND_RENDER.md")
    require(text, "WATCHTOWER_ENABLED=false", "gpt/SECRETS_AND_RENDER.md")


def main() -> None:
    check_instruction_payload()
    check_knowledge_registry()
    check_target_registry()
    check_recovery_docs()
    check_actions()
    check_program_and_rollback()
    check_external_secret_boundary()

    print("GPT v9 recovery/configuration consistency: OK")
    print(f"Applied UI: {TARGET_UI_NAME}")
    print(f"Applied Instructions: {TARGET_INSTRUCTIONS}")
    print(
        f"Instructions chars: {len(read(TARGET_INSTRUCTIONS))}/{INSTRUCTIONS_MAX_CHARS}"
    )
    print(f"Knowledge files: {len(KNOWLEDGE_FILES)}")
    print(f"Protected rollback UI: {PROTECTED_UI_NAME}")
    print(f"Protected baseline commit: {BASELINE_COMMIT}")
    print(f"Gateway: {GATEWAY_URL}")


if __name__ == "__main__":
    main()
