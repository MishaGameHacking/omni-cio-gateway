from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "app.py",
    "render.yaml",
    "requirements.in",
    "requirements.txt",
    "requirements-dev.in",
    "requirements-dev.txt",
    "pyproject.toml",
    ".env.example",
    "scripts/check_ci_security_baseline.py",
    "scripts/check_gpt_recovery_consistency.py",
    "scripts/check_repository_layout.py",
    "scripts/check_strategy_boundary.py",
    "tests/test_ci_security_baseline.py",
    "tests/test_gpt_recovery_consistency.py",
    "tests/test_natural_language_cio_router_v1.py",
    "tests/test_investment_policy_statement_v1.py",
    "tests/test_market_universe_v1.py",
    "tests/test_candidate_funnel_v1.py",
    "tests/test_research_binding_v1.py",
    "tests/test_research_evidence_v1.py",
    "tests/test_research_official_v1.py",
    "tests/test_credit_rating_default_engine_v1.py",
    "tests/test_credit_contract_integrity_v1.py",
    "tests/test_fund_xray_v1.py",
    "tests/test_fund_xray_integrity_v1.py",
    "tests/test_fund_xray_duration_credit_v1.py",
    "tests/test_portfolio_risk_engine_v1.py",
    "tests/test_portfolio_risk_hardening_v1.py",
    "tests/test_meta_strategy_selector_v1.py",
    "tests/test_meta_strategy_boundary_v1.py",
    "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    "knowledge/09_MARKET_DATA_AND_BUYING_POWER.txt",
    "knowledge/10_OPERATIONS_ANALYTICS_AND_RECONCILIATION.txt",
    "knowledge/11_BROKER_REPORT_ASYNC_INTEGRITY.txt",
    "knowledge/13_COMMUNICATION_STYLE_2026.txt",
    "knowledge/14_CI_SECURITY_BASELINE.txt",
    "knowledge/15_VERSIONED_DATA_CONTRACTS.txt",
    "knowledge/16_CURRENT_PROGRAM_STATUS.md",
    "docs/README.md",
    "docs/master-plan/README.md",
    "docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.pdf",
    "docs/master-plan/OMNI_CIO_MASTER_PROMPT_V9.txt",
    "docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md",
    "docs/architecture/SYSTEM_OVERVIEW.md",
    "docs/architecture/REPOSITORY_STRUCTURE.md",
    "docs/architecture/DECISIONS.md",
    "docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md",
    "docs/architecture/V9_NATURAL_LANGUAGE_CIO_ROUTER.md",
    "docs/architecture/V9_INVESTMENT_POLICY_STATEMENT.md",
    "docs/architecture/V9_MARKET_UNIVERSE_ENGINE.md",
    "docs/architecture/V9_DETERMINISTIC_CANDIDATE_FUNNEL.md",
    "docs/architecture/V9_RESEARCH_EVIDENCE_ENGINE.md",
    "docs/architecture/V9_CREDIT_RATING_DEFAULT_ENGINE.md",
    "docs/architecture/V9_FUND_XRAY_ENGINE.md",
    "docs/architecture/V9_PORTFOLIO_RISK_ENGINE.md",
    "docs/architecture/V9_META_STRATEGY_SELECTOR.md",
    "docs/operations/DEPLOYMENT_RUNBOOK.md",
    "docs/operations/RELEASE_CHECKLIST.md",
    "docs/operations/SANDBOX_TRADING_RUNBOOK.md",
    "docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md",
    "gpt/README.md",
    "gpt/SETUP_INDEX.md",
    "gpt/MY_GPT_SETUP_RUNBOOK.md",
    "gpt/CONFIGURATION.md",
    "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt",
    "gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt",
    "gpt/ACTIONS_CATALOG.md",
    "gpt/SECRETS_AND_RENDER.md",
    "gpt/BOT_ONLY_FILE_MANIFEST.md",
    "gpt/NEW_CHAT_PROMPT.md",
    "gpt/PROJECT_INSTRUCTIONS.md",
    "omni_cio/contracts/v1/intent_router.py",
    "omni_cio/contracts/v1/investment_policy.py",
    "omni_cio/contracts/v1/universe.py",
    "omni_cio/contracts/v1/candidate_funnel.py",
    "omni_cio/contracts/v1/research_evidence.py",
    "omni_cio/contracts/v1/credit.py",
    "omni_cio/contracts/v1/fund_xray.py",
    "omni_cio/contracts/v1/portfolio_risk.py",
    "omni_cio/contracts/v1/meta_strategy.py",
    "omni_cio/router/__init__.py",
    "omni_cio/router/intent_v1.py",
    "omni_cio/policy/__init__.py",
    "omni_cio/policy/ips_v1.py",
    "omni_cio/universe/__init__.py",
    "omni_cio/universe/cache_v1.py",
    "omni_cio/universe/engine_v1.py",
    "omni_cio/universe/service_v1.py",
    "omni_cio/universe/tinvest_v1.py",
    "omni_cio/candidates/__init__.py",
    "omni_cio/candidates/funnel_v1.py",
    "omni_cio/research/__init__.py",
    "omni_cio/research/binding_v1.py",
    "omni_cio/research/cache_v1.py",
    "omni_cio/research/engine_v1.py",
    "omni_cio/research/external_context_v1.py",
    "omni_cio/research/official_v1.py",
    "omni_cio/research/tinvest_v1.py",
    "omni_cio/credit/__init__.py",
    "omni_cio/credit/engine_v1.py",
    "omni_cio/funds/__init__.py",
    "omni_cio/funds/xray_v1.py",
    "omni_cio/risk/__init__.py",
    "omni_cio/risk/engine_v1.py",
    "omni_cio/risk/policy_v1.py",
    "omni_cio/strategy/__init__.py",
    "omni_cio/strategy/selector_v1.py",
    "omni_cio/sandbox/__init__.py",
    "omni_cio/sandbox/client_v1.py",
    "omni_cio/sandbox/service_v1.py",
    "omni_cio/sandbox/routes_v1.py",
    "omni_cio/real_trading/__init__.py",
    "tests/test_sandbox_trading_v1.py",
    ".github/CODEOWNERS",
    ".github/dependabot.yml",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/regression-shield.yml",
)

FORBIDDEN_TRACKED_NAMES = {".env", "pytest-results.xml"}
FORBIDDEN_WORKFLOWS = {
    "apply-v390.yml",
    "pr03-bootstrap.yml",
    "upgrade-v390.yml",
}
RETIRED_DUPLICATE_SCENARIO_PUBLISHER_PATHS = (
    "omni_cio/release/final_decision_review_calculator_publication_v1.py",
    "omni_cio/release/final_decision_review_calculator_registration_v1.py",
    "tests/test_final_decision_review_calculator_publication_v1.py",
    "tests/test_final_decision_review_calculator_registration_v1.py",
    "docs/architecture/FINAL_DECISION_REVIEW_CALCULATOR_PUBLICATION_V1.md",
    "docs/architecture/FINAL_DECISION_REVIEW_CALCULATOR_REGISTRATION_V1.md",
)
FORBIDDEN_BROKER_METHOD_PREFIXES = (
    "post_order",
    "replace_order",
    "cancel_order",
    "create_order",
    "execute_order",
    "post_stop_order",
    "cancel_stop_order",
    "withdraw",
    "transfer",
)
FORBIDDEN_BROKER_METHODS = {
    "pay_in",
    "sandbox_pay_in",
    "open_sandbox_account",
    "close_sandbox_account",
}
FORBIDDEN_BROKER_SERVICES = {"stop_orders", "sandbox"}

SANDBOX_RUNTIME_ROOT = Path("omni_cio/sandbox")
SANDBOX_ALLOWED_HOST = "https://sandbox-invest-public-api.tbank.ru/rest"
SANDBOX_FORBIDDEN_TEXT = (
    "https://invest-public-api.tbank.ru/rest",
    "OrdersService/PostOrder",
    'os.environ.get("TINVEST_TOKEN"',
    "TINVEST_TRADING_TOKEN",
    "TINVEST_TRANSFER_TOKEN",
)

UNIVERSE_RUNTIME_ROOT = Path("omni_cio/universe")
UNIVERSE_REQUIRED_TEXT = (
    "InstrumentStatus.INSTRUMENT_STATUS_BASE",
    '"shares"',
    '"bonds"',
    '"etfs"',
)
UNIVERSE_FORBIDDEN_TEXT = (
    "find_instrument",
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
)

CANDIDATE_RUNTIME_ROOT = Path("omni_cio/candidates")
CANDIDATE_FORBIDDEN_TEXT = (
    "t_tech_investments",
    "TINVEST_",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
)

RESEARCH_RUNTIME_ROOT = Path("omni_cio/research")
RESEARCH_FORBIDDEN_TEXT = (
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
)

CREDIT_RUNTIME_ROOT = Path("omni_cio/credit")
CREDIT_FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
)

FUND_RUNTIME_ROOT = Path("omni_cio/funds")
FUND_FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
)

RISK_RUNTIME_ROOT = Path("omni_cio/risk")
RISK_FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
)

STRATEGY_RUNTIME_ROOT = Path("omni_cio/strategy")
STRATEGY_FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
)


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def is_forbidden_broker_attribute(name: str) -> bool:
    return (
        name in FORBIDDEN_BROKER_METHODS
        or name in FORBIDDEN_BROKER_SERVICES
        or any(name.startswith(prefix) for prefix in FORBIDDEN_BROKER_METHOD_PREFIXES)
    )


def is_sandbox_runtime(relative: Path) -> bool:
    try:
        relative.relative_to(SANDBOX_RUNTIME_ROOT)
    except ValueError:
        return False
    return True


def scan_runtime_broker_egress(failures: list[str]) -> None:
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(
            part in {".git", ".venv", "tests", "scripts", "__pycache__"}
            for part in relative.parts
        ):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(relative))
        except (OSError, SyntaxError) as exc:
            fail(f"cannot inspect runtime Python source {relative}: {exc}", failures)
            continue
        if is_sandbox_runtime(relative):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and is_forbidden_broker_attribute(
                node.attr
            ):
                fail(
                    "forbidden real broker write surface referenced: "
                    f"{relative}:{node.lineno} ({node.attr})",
                    failures,
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and is_forbidden_broker_attribute(node.args[1].value)
            ):
                fail(
                    "dynamic forbidden real broker write surface referenced: "
                    f"{relative}:{node.lineno} ({node.args[1].value})",
                    failures,
                )


def scan_sandbox_execution_boundary(failures: list[str]) -> None:
    sandbox_root = ROOT / SANDBOX_RUNTIME_ROOT
    if not sandbox_root.is_dir():
        fail("sandbox runtime directory is missing", failures)
        return
    source_parts: list[str] = []
    for path in sorted(sandbox_root.glob("*.py")):
        try:
            source_parts.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            fail(f"cannot inspect sandbox source {path}: {exc}", failures)
    source = "\n".join(source_parts)
    if SANDBOX_ALLOWED_HOST not in source:
        fail(
            "sandbox runtime does not declare the canonical sandbox REST host", failures
        )
    if "TINVEST_SANDBOX_TOKEN" not in source:
        fail("sandbox runtime does not require TINVEST_SANDBOX_TOKEN", failures)
    if "SANDBOX_TRADING_ENABLED" not in source:
        fail("sandbox runtime has no explicit kill switch", failures)
    if (
        "confirmMarginTrade" not in source
        or '"confirmMarginTrade": False' not in source
    ):
        fail("sandbox runtime does not hard-disable margin confirmation", failures)
    if "x-openai-isConsequential" not in source:
        fail("sandbox mutation Actions are not marked consequential", failures)
    for forbidden in SANDBOX_FORBIDDEN_TEXT:
        if forbidden in source:
            fail(
                f"sandbox runtime crosses production execution boundary: {forbidden}",
                failures,
            )


def scan_universe_execution_boundary(failures: list[str]) -> None:
    universe_root = ROOT / UNIVERSE_RUNTIME_ROOT
    if not universe_root.is_dir():
        fail("market universe runtime directory is missing", failures)
        return
    source_parts: list[str] = []
    for path in sorted(universe_root.glob("*.py")):
        try:
            source_parts.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            fail(f"cannot inspect universe source {path}: {exc}", failures)
    source = "\n".join(source_parts)
    for required in UNIVERSE_REQUIRED_TEXT:
        if required not in source:
            fail(f"market universe source contract missing: {required}", failures)
    for forbidden in UNIVERSE_FORBIDDEN_TEXT:
        if forbidden in source:
            fail(f"market universe crosses read-only boundary: {forbidden}", failures)
    for path in sorted(universe_root.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            fail(f"cannot parse universe source {path}: {exc}", failures)
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {
                "orders",
                "stop_orders",
                "sandbox",
            }:
                fail(
                    f"market universe references forbidden broker service: {node.attr}",
                    failures,
                )


def _scan_pure_or_read_only_package(
    *,
    root: Path,
    label: str,
    forbidden_text: tuple[str, ...],
    failures: list[str],
) -> None:
    package_root = ROOT / root
    if not package_root.is_dir():
        fail(f"{label} runtime directory is missing", failures)
        return
    for path in sorted(package_root.glob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError) as exc:
            fail(f"cannot inspect {label} source {path}: {exc}", failures)
            continue
        for forbidden in forbidden_text:
            if forbidden in source:
                fail(f"{label} crosses protected boundary: {forbidden}", failures)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {
                "orders",
                "stop_orders",
                "sandbox",
            }:
                fail(
                    f"{label} references forbidden broker service: {node.attr}",
                    failures,
                )
            if isinstance(node, ast.Attribute) and is_forbidden_broker_attribute(
                node.attr
            ):
                fail(
                    f"{label} references forbidden broker method: {node.attr}",
                    failures,
                )


def scan_candidate_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=CANDIDATE_RUNTIME_ROOT,
        label="candidate funnel",
        forbidden_text=CANDIDATE_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_research_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=RESEARCH_RUNTIME_ROOT,
        label="research engine",
        forbidden_text=RESEARCH_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_credit_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=CREDIT_RUNTIME_ROOT,
        label="credit engine",
        forbidden_text=CREDIT_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_fund_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=FUND_RUNTIME_ROOT,
        label="fund X-Ray engine",
        forbidden_text=FUND_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_risk_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=RISK_RUNTIME_ROOT,
        label="portfolio risk engine",
        forbidden_text=RISK_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_strategy_execution_boundary(failures: list[str]) -> None:
    _scan_pure_or_read_only_package(
        root=STRATEGY_RUNTIME_ROOT,
        label="meta-strategy selector",
        forbidden_text=STRATEGY_FORBIDDEN_TEXT,
        failures=failures,
    )


def scan_retired_duplicate_scenario_publishers(failures: list[str]) -> None:
    for relative_path in RETIRED_DUPLICATE_SCENARIO_PUBLISHER_PATHS:
        if (ROOT / relative_path).exists():
            fail(
                f"retired duplicate scenario publisher path is present: {relative_path}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).is_file():
            fail(f"missing required file: {relative_path}", failures)

    render_path = ROOT / "render.yaml"
    if render_path.is_file():
        render_text = render_path.read_text(encoding="utf-8")
        expected = "uvicorn app:app --host 0.0.0.0 --port $PORT"
        if expected not in render_text:
            fail("render.yaml does not preserve the app:app entrypoint", failures)

    app_path = ROOT / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8")
        if 'ENTRYPOINT = "app:app"' not in app_text:
            fail("app.py does not declare ENTRYPOINT = app:app", failures)
        if "trading_methods" not in app_text:
            fail("app.py does not expose the trading surface marker", failures)

    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.name in FORBIDDEN_TRACKED_NAMES:
            fail(
                f"forbidden generated or secret file present: {path.relative_to(ROOT)}",
                failures,
            )
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            fail(
                f"generated Python artifact present: {path.relative_to(ROOT)}",
                failures,
            )

    workflow_dir = ROOT / ".github" / "workflows"
    for name in FORBIDDEN_WORKFLOWS:
        if (workflow_dir / name).exists():
            fail(f"obsolete one-time workflow still present: {name}", failures)

    scan_runtime_broker_egress(failures)
    scan_sandbox_execution_boundary(failures)
    scan_universe_execution_boundary(failures)
    scan_candidate_execution_boundary(failures)
    scan_research_execution_boundary(failures)
    scan_credit_execution_boundary(failures)
    scan_fund_execution_boundary(failures)
    scan_risk_execution_boundary(failures)
    scan_strategy_execution_boundary(failures)
    scan_retired_duplicate_scenario_publishers(failures)

    if failures:
        print("Repository layout check failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Repository layout check passed.")
    print(f"Required files checked: {len(REQUIRED_PATHS)}")
    print("Product surface: one Custom GPT + one production Gateway")
    print("Execution contours: read-only + isolated Sandbox + confirmed Real v1")
    print("Protected production release: Omni-CIO v8.6.1")
    print("Active development program: Omni-CIO v9 Portfolio Autopilot")
    print("Gateway entrypoint: app:app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
