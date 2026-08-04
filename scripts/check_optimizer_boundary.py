from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
OPTIMIZER_ROOT = ROOT / "omni_cio" / "optimizer"
CONTRACT_PATH = (
    ROOT / "omni_cio" / "contracts" / "v1" / "portfolio_optimizer.py"
)

REQUIRED_PATHS = (
    "omni_cio/contracts/v1/portfolio_optimizer.py",
    "omni_cio/optimizer/__init__.py",
    "omni_cio/optimizer/engine_v1.py",
    "tests/test_portfolio_optimizer_v1.py",
    "tests/test_portfolio_optimizer_boundary_v1.py",
    "docs/architecture/V9_PORTFOLIO_OPTIMIZER.md",
)

FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "confirmMarginTrade",
    "PostOrder",
    "ReplaceOrder",
    "CancelOrder",
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

FORBIDDEN_OPTIMIZER_FIELDS = {
    "expected_return",
    "expected_alpha",
    "alpha",
    "forecast_return",
    "target_return",
    "predicted_return",
    "macro_regime_forecast",
    "execution_authorized",
    "order_created",
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
                f"optimizer runtime crosses protected boundary: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            _fail(
                "optimizer runtime references broker mutation surface: "
                f"{path.relative_to(ROOT)}:{node.lineno} ({node.attr})",
                failures,
            )
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in FORBIDDEN_OPTIMIZER_FIELDS:
                _fail(
                    "optimizer contract exposes forbidden forecast/execution field: "
                    f"{node.target.id}",
                    failures,
                )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP10 required path: {relative}", failures)

    if not OPTIMIZER_ROOT.is_dir():
        _fail("optimizer runtime directory is missing", failures)
    else:
        for path in sorted(OPTIMIZER_ROOT.glob("*.py")):
            _scan_python(path, failures)

    if CONTRACT_PATH.is_file():
        _scan_python(CONTRACT_PATH, failures)
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        if "trading_methods: Literal[False]" not in contract_text:
            _fail(
                "optimizer contract does not hard-code trading_methods=false",
                failures,
            )

    if failures:
        print("Portfolio optimizer boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Portfolio optimizer boundary check passed.")
    print("Runtime: internal/read-only")
    print("Trading methods: false")
    print("Expected-return/alpha fields: absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
