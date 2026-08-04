from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = ROOT / "omni_cio" / "strategy"
CONTRACT_PATH = ROOT / "omni_cio" / "contracts" / "v1" / "meta_strategy.py"

REQUIRED_PATHS = (
    "omni_cio/contracts/v1/meta_strategy.py",
    "omni_cio/strategy/__init__.py",
    "omni_cio/strategy/selector_v1.py",
    "tests/test_meta_strategy_selector_v1.py",
    "tests/test_meta_strategy_boundary_v1.py",
    "docs/architecture/V9_META_STRATEGY_SELECTOR.md",
)

FORBIDDEN_TEXT = (
    "t_tech_investments",
    "t_tech.invest",
    "TINVEST_",
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

FORBIDDEN_STRATEGY_FIELDS = {
    "expected_return",
    "expected_alpha",
    "alpha",
    "forecast_return",
    "target_return",
    "predicted_return",
    "macro_regime_forecast",
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
                f"strategy runtime crosses protected boundary: {forbidden}",
                failures,
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            _fail(
                "strategy runtime references broker mutation surface: "
                f"{path.relative_to(ROOT)}:{node.lineno} ({node.attr})",
                failures,
            )
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in FORBIDDEN_STRATEGY_FIELDS:
                _fail(
                    "strategy contract exposes unsupported return forecast field: "
                    f"{node.target.id}",
                    failures,
                )


def main() -> int:
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).is_file():
            _fail(f"missing WP9 required path: {relative}", failures)

    if not STRATEGY_ROOT.is_dir():
        _fail("strategy runtime directory is missing", failures)
    else:
        for path in sorted(STRATEGY_ROOT.glob("*.py")):
            _scan_python(path, failures)

    if CONTRACT_PATH.is_file():
        _scan_python(CONTRACT_PATH, failures)
        contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
        if "trading_methods: Literal[False]" not in contract_text:
            _fail(
                "strategy contract does not hard-code trading_methods=false", failures
            )

    if failures:
        print("Meta-strategy boundary check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Meta-strategy boundary check passed.")
    print("Runtime: pure/internal/read-only")
    print("Trading methods: false")
    print("Expected-return forecast fields: absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
