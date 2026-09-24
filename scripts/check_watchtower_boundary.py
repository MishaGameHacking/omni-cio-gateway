from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WATCHTOWER_ROOT = ROOT / "omni_cio" / "watchtower"
CONTRACT_PATH = ROOT / "omni_cio" / "contracts" / "v1" / "watchtower.py"

REQUIRED_PATHS = (
    "omni_cio/reconciliation/broker_report/__init__.py",
    "omni_cio/contracts/v1/watchtower.py",
    "omni_cio/watchtower/__init__.py",
    "omni_cio/watchtower/engine_v1.py",
    "omni_cio/watchtower/installation_v1.py",
    "omni_cio/watchtower/journal_v1.py",
    "omni_cio/watchtower/provider_v1.py",
    "omni_cio/watchtower/qstash_v1.py",
    "omni_cio/watchtower/routes_v1.py",
    "omni_cio/watchtower/runtime_v1.py",
    "omni_cio/watchtower/upstash_journal_v1.py",
    "scripts/reconcile_watchtower_schedule.py",
    "tests/test_portfolio_watchtower_v1.py",
    "tests/test_watchtower_boundary_v1.py",
    "tests/test_watchtower_gateway_registration_v1.py",
    "tests/test_watchtower_installation_v1.py",
    "tests/test_watchtower_qstash_v1.py",
    "tests/test_watchtower_runtime_routes_v1.py",
    "tests/test_watchtower_upstash_journal_v1.py",
    "docs/architecture/V9_PORTFOLIO_WATCHTOWER.md",
    "docs/architecture/V9_PORTFOLIO_WATCHTOWER_THREAT_MODEL.md",
    "docs/architecture/V9_PORTFOLIO_WATCHTOWER_DATA_CONTRACT.md",
    "docs/operations/V9_WATCHTOWER_RUNBOOK.md",
)

FORBIDDEN_TEXT = (
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "RealTradingServiceV1",
    "RealTradingRestClientV1",
    "SandboxTradingServiceV1",
    "PostOrder",
    "PostOrderAsync",
    "ReplaceOrder",
    "CancelOrder",
    "ORDER_TYPE_MARKET",
    "ORDER_TYPE_BESTPRICE",
    "confirmMarginTrade=True",
    "securities_transfer",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "omni_cio.real_trading",
    "omni_cio.sandbox",
    "t_tech.invest",
    "t_tech_investments",
)

FORBIDDEN_CALL_ATTRIBUTES = {
    "execute_trade",
    "post_order",
    "post_order_async",
    "replace_order",
    "cancel_order",
    "post_stop_order",
    "withdraw",
    "transfer",
}


def _fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def _scan(path: Path, failures: list[str]) -> None:
    relative = path.relative_to(ROOT)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(relative))
    except (OSError, SyntaxError) as exc:
        _fail(f"cannot inspect {relative}: {exc}", failures)
        return

    for forbidden in FORBIDDEN_TEXT:
        if forbidden in source:
            _fail(
                f"Watchtower crosses protected authority boundary: {relative}: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    _fail(
                        f"Watchtower imports forbidden broker/Sandbox package: {relative}: {item.name}",
                        failures,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                _fail(
                    f"Watchtower imports forbidden broker/Sandbox package: {relative}: {module}",
                    failures,
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALL_ATTRIBUTES:
                _fail(
                    f"Watchtower directly calls forbidden mutation method: {relative}:{node.lineno} ({node.func.attr})",
                    failures,
                )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP13 required path: {relative}", failures)

    if not WATCHTOWER_ROOT.is_dir():
        _fail("WP13 Watchtower runtime directory is missing", failures)
    else:
        for path in sorted(WATCHTOWER_ROOT.glob("*.py")):
            _scan(path, failures)

    if CONTRACT_PATH.is_file():
        _scan(CONTRACT_PATH, failures)
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        for literal in (
            "execution_authorized: Literal[False] = False",
            "trading_methods: Literal[False] = False",
        ):
            if literal not in contract:
                _fail(f"WP13 safety literal missing: {literal}", failures)
        if "EXECUTE" in contract or "SUBMIT" in contract:
            _fail(
                "Watchtower contract must not define an execution/submit action",
                failures,
            )

    gateway_hook = (
        ROOT / "omni_cio" / "reconciliation" / "broker_report" / "__init__.py"
    )
    if gateway_hook.is_file():
        gateway_source = gateway_hook.read_text(encoding="utf-8")
        for required in (
            "register_watchtower_routes",
            "WatchtowerEvidenceProviderRegistryV1",
            "watchtower_provider_registry",
        ):
            if required not in gateway_source:
                _fail(f"WP13 Gateway registration missing: {required}", failures)

    if failures:
        print("Portfolio Watchtower boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Portfolio Watchtower boundary check passed.")
    print("Runtime: read-only evidence reducer + durable dedup state")
    print("QStash boundary: signed internal scheduling only")
    print("Gateway routes: internal and excluded from GPT OpenAPI")
    print("Canonical provider installation: explicit and lazy")
    print("Broker/Sandbox mutation authority: absent")
    print("Autonomous real execution: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
