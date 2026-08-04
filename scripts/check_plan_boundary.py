from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
PLAN_ROOT = ROOT / "omni_cio" / "plans"
CONTRACT_PATH = ROOT / "omni_cio" / "contracts" / "v1" / "portfolio_plan.py"

REQUIRED_PATHS = (
    "omni_cio/contracts/v1/portfolio_plan.py",
    "omni_cio/plans/__init__.py",
    "omni_cio/plans/protocol_v1.py",
    "tests/v9_plan_fixture.py",
    "tests/test_portfolio_plan_v1.py",
    "tests/test_portfolio_plan_boundary_v1.py",
    "docs/architecture/V9_IMMUTABLE_PORTFOLIO_PLAN.md",
)

FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "RealTradingServiceV1",
    "SandboxTradingServiceV1",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
    "PostOrder",
    "ReplaceOrder",
    "CancelOrder",
    "omni_cio.real_trading",
    "omni_cio.sandbox",
)

FORBIDDEN_ATTRIBUTES = {
    "orders",
    "stop_orders",
    "sandbox",
    "post_order",
    "replace_order",
    "cancel_order",
    "withdraw",
    "transfer",
}

FORBIDDEN_AUTHORITY_FIELDS = {
    "broker_order_id",
    "order_id",
    "request_id",
    "submission_id",
    "submitted_at",
    "filled_at",
    "fill_price",
    "broker_response",
    "confirmation_code",
}


def _fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def _scan_python(path: Path, failures: list[str]) -> None:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path.relative_to(ROOT)))
    except (OSError, SyntaxError) as exc:
        _fail(f"cannot inspect {path.relative_to(ROOT)}: {exc}", failures)
        return

    for forbidden in FORBIDDEN_TEXT:
        if forbidden in source:
            _fail(
                f"portfolio plan runtime crosses protected boundary: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            _fail(
                "portfolio plan runtime references broker mutation surface: "
                f"{path.relative_to(ROOT)}:{node.lineno} ({node.attr})",
                failures,
            )
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in FORBIDDEN_AUTHORITY_FIELDS:
                _fail(
                    "portfolio plan contract exposes execution-state field: "
                    f"{node.target.id}",
                    failures,
                )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP11 required path: {relative}", failures)

    if not PLAN_ROOT.is_dir():
        _fail("portfolio plan runtime directory is missing", failures)
    else:
        for path in sorted(PLAN_ROOT.glob("*.py")):
            _scan_python(path, failures)

    if CONTRACT_PATH.is_file():
        _scan_python(CONTRACT_PATH, failures)
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        if "execution_authorized: Literal[False]" not in contract_text:
            _fail(
                "portfolio plan contract does not hard-code execution_authorized=false",
                failures,
            )
        if "trading_methods: Literal[False]" not in contract_text:
            _fail(
                "portfolio plan contract does not hard-code trading_methods=false",
                failures,
            )
        if 'object_type: Literal["PORTFOLIO_PLAN"]' not in contract_text:
            _fail("portfolio plan immutable object type is missing", failures)

    if failures:
        print("Immutable portfolio plan boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Immutable portfolio plan boundary check passed.")
    print("Runtime: internal/read-only")
    print("Execution authorized: false")
    print("Trading methods: false")
    print("Broker/Sandbox mutation authority: absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
