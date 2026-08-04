from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_ROOT = ROOT / "omni_cio" / "plan_execution"
CONTRACT_PATH = ROOT / "omni_cio" / "contracts" / "v1" / "plan_execution.py"
ADAPTER_PATH = EXECUTION_ROOT / "adapter_v1.py"
PUBLIC_SERVICE_PATH = EXECUTION_ROOT / "service_v1.py"
GUARD_PATH = Path(__file__).resolve()
CORE_MODULE = "service_core_v1"

REQUIRED_PATHS = (
    "omni_cio/contracts/v1/plan_execution.py",
    "omni_cio/plan_execution/__init__.py",
    "omni_cio/plan_execution/adapter_v1.py",
    "omni_cio/plan_execution/broker_reconciliation_v1.py",
    "omni_cio/plan_execution/journal_v1.py",
    "omni_cio/plan_execution/service_core_v1.py",
    "omni_cio/plan_execution/service_v1.py",
    "omni_cio/plan_execution/upstash_journal_v1.py",
    "tests/v9_execution_fixture.py",
    "tests/test_plan_execution_boundary_v1.py",
    "tests/test_plan_execution_broker_reconciliation_v1.py",
    "tests/test_plan_execution_upstash_journal_v1.py",
    "tests/test_safe_plan_execution_bindings_v1.py",
    "tests/test_safe_plan_execution_v1.py",
    "docs/architecture/V9_SAFE_PLAN_EXECUTION.md",
    "docs/architecture/V9_SAFE_PLAN_EXECUTION_THREAT_MODEL.md",
    "docs/architecture/V9_SAFE_PLAN_EXECUTION_DATA_CONTRACT.md",
)

FORBIDDEN_TEXT = (
    "TINVEST_TOKEN",
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "SandboxTradingServiceV1",
    "RealTradingRestClientV1",
    "PostOrder",
    "PostOrderAsync",
    "ReplaceOrder",
    "CancelOrder",
    "StopOrder",
    "confirmMarginTrade=True",
    "confirmMarginTrade\": true",
    "ORDER_TYPE_MARKET",
    "ORDER_TYPE_BESTPRICE",
    "securities_transfer",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "omni_cio.sandbox",
    "t_tech.invest",
    "t_tech_investments",
)

FORBIDDEN_CALL_ATTRIBUTES = {
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


def _scan_python(path: Path, failures: list[str]) -> None:
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
                f"WP12 runtime crosses protected authority boundary: {relative}: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [item.name for item in node.names]
            for name in names:
                if name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    _fail(
                        f"WP12 imports forbidden broker/Sandbox package: {relative}: {name}",
                        failures,
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                _fail(
                    f"WP12 imports forbidden broker/Sandbox package: {relative}: {module}",
                    failures,
                )
            if module == "omni_cio.real_trading.service_v1" and path != ADAPTER_PATH:
                _fail(
                    f"only WP12 adapter may import RealTradingServiceV1: {relative}",
                    failures,
                )
            if module == "omni_cio.real_trading.client_v1":
                imported = {item.name for item in node.names}
                if imported - {"RealTradingApiFailure"}:
                    _fail(
                        f"WP12 may import only RealTradingApiFailure from client_v1: {relative}",
                        failures,
                    )
            if CORE_MODULE in module and path != PUBLIC_SERVICE_PATH:
                _fail(
                    f"frozen WP12 core may be imported only by service_v1.py: {relative}",
                    failures,
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALL_ATTRIBUTES:
                _fail(
                    "WP12 directly calls forbidden mutation method: "
                    f"{relative}:{node.lineno} ({node.func.attr})",
                    failures,
                )


def _scan_core_imports(failures: list[str]) -> None:
    """Prevent the frozen compatibility core from becoming a second public API."""

    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT)
        if any(part in {".git", ".venv", "__pycache__"} for part in relative.parts):
            continue
        if path in {PUBLIC_SERVICE_PATH, GUARD_PATH}:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            _fail(f"cannot inspect core import boundary {relative}: {exc}", failures)
            continue
        if CORE_MODULE in source:
            _fail(
                f"frozen WP12 core referenced outside audited facade: {relative}",
                failures,
            )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP12 required path: {relative}", failures)

    if not EXECUTION_ROOT.is_dir():
        _fail("WP12 execution runtime directory is missing", failures)
    else:
        for path in sorted(EXECUTION_ROOT.glob("*.py")):
            _scan_python(path, failures)
    _scan_core_imports(failures)

    if CONTRACT_PATH.is_file():
        _scan_python(CONTRACT_PATH, failures)
        contract = CONTRACT_PATH.read_text(encoding="utf-8")
        required_literals = (
            "autonomous_execution: Literal[False] = False",
            "margin_allowed: Literal[False] = False",
            "short_allowed: Literal[False] = False",
            "withdrawal_allowed: Literal[False] = False",
            "transfer_allowed: Literal[False] = False",
            "autonomous_recurring_execution: Literal[False] = False",
        )
        for literal in required_literals:
            if literal not in contract:
                _fail(f"WP12 safety literal missing: {literal}", failures)

    if ADAPTER_PATH.is_file():
        adapter = ADAPTER_PATH.read_text(encoding="utf-8")
        required_adapter_methods = (
            "def prepare_trade(",
            "def execute_trade(",
            "def reconcile_proposal(",
            "def get_proposal(",
        )
        for method in required_adapter_methods:
            if method not in adapter:
                _fail(f"WP12 legacy adapter method missing: {method}", failures)
        for forbidden_method in ("cancel", "replace", "withdraw", "transfer"):
            if f"def {forbidden_method}" in adapter:
                _fail(f"WP12 adapter exposes forbidden method: {forbidden_method}", failures)

    if PUBLIC_SERVICE_PATH.is_file():
        public_service = PUBLIC_SERVICE_PATH.read_text(encoding="utf-8")
        for required in (
            "class SafePlanExecutionServiceV1(_core.SafePlanExecutionServiceV1)",
            "def advance_execution(",
            "def _runtime_guard(",
            "def _reconcile_broker(",
            "PlanExecutionHaltCode.PLAN_EXPIRED",
            "_core._tax_allowance(plan, stage, snapshot.lots_executed)",
        ):
            if required not in public_service:
                _fail(f"WP12 audited facade hardening missing: {required}", failures)

    package_init = EXECUTION_ROOT / "__init__.py"
    if package_init.is_file() and CORE_MODULE in package_init.read_text(encoding="utf-8"):
        _fail("frozen WP12 core must not be exported by package __init__", failures)

    if failures:
        print("Safe plan execution boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Safe plan execution boundary check passed.")
    print("Broker submit implementation: existing v8.6.1 primitive only")
    print("Frozen compatibility core: private behind audited facade")
    print("Direct broker/Sandbox mutation surface: absent")
    print("Transfer/withdraw/margin/short/autonomous recurring execution: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
