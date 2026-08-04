from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_ROOT = ROOT / "omni_cio" / "research"

FORBIDDEN_TEXT = (
    "TINVEST_TRADING_TOKEN",
    "TINVEST_SANDBOX_TOKEN",
    "TINVEST_TRANSFER_TOKEN",
    "prepareRealTrade",
    "executeRealTrade",
    "prepareSandboxTrade",
    "executeSandboxTrade",
    "execution_authorized=true",
    '"execution_authorized": true',
)

FORBIDDEN_ATTRIBUTES = {
    "orders",
    "stop_orders",
    "sandbox",
    "post_order",
    "replace_order",
    "cancel_order",
    "post_stop_order",
    "cancel_stop_order",
    "withdraw",
    "transfer",
}


def test_research_runtime_is_read_only_and_execution_inert() -> None:
    assert RESEARCH_ROOT.is_dir()

    inspected = 0
    for path in sorted(RESEARCH_ROOT.glob("*.py")):
        inspected += 1
        source = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_TEXT:
            assert forbidden not in source, f"forbidden research boundary text in {path}: {forbidden}"

        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in FORBIDDEN_ATTRIBUTES, (
                    f"forbidden broker mutation surface in {path}:{node.lineno}: {node.attr}"
                )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                assert node.args[1].value not in FORBIDDEN_ATTRIBUTES, (
                    f"dynamic forbidden broker mutation surface in {path}:{node.lineno}: "
                    f"{node.args[1].value}"
                )

    assert inspected >= 5
