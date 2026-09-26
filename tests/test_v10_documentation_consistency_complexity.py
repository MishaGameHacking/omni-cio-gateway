from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_documentation_consistency.py"
EXPECTED_LIVE_GUIDANCE_HELPERS = (
    "_validate_live_guidance_delegation",
    "_validate_transient_checkpoint_delegation",
    "_validate_readme_snapshot",
    "_validate_agents_snapshot",
    "_validate_master_context_snapshot",
)
EXPECTED_HIGH_RISK_HEADER_HELPERS = (
    "_validate_program_lock_header",
    "_validate_toolchain_baseline_header",
    "_validate_historical_record_headers",
    "_validate_engineering_amendment_header",
    "_validate_cloudflare_amendment_header",
)
EXPECTED_CLOUDFLARE_AMENDMENT_HEADER_HELPERS = (
    "_validate_cloudflare_amendment_markers",
    "_validate_cloudflare_contract_header",
)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def test_live_guidance_validation_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "validate_live_guidance")

    assert len(function.body) == len(EXPECTED_LIVE_GUIDANCE_HELPERS)
    for statement, helper_name in zip(
        function.body,
        EXPECTED_LIVE_GUIDANCE_HELPERS,
        strict=True,
    ):
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Call)
        assert isinstance(statement.value.func, ast.Name)
        assert statement.value.func.id == helper_name


def test_high_risk_header_validation_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "validate_high_risk_headers")

    assert len(function.body) == len(EXPECTED_HIGH_RISK_HEADER_HELPERS)
    for statement, helper_name in zip(
        function.body,
        EXPECTED_HIGH_RISK_HEADER_HELPERS,
        strict=True,
    ):
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Call)
        assert isinstance(statement.value.func, ast.Name)
        assert statement.value.func.id == helper_name


def test_cloudflare_amendment_header_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "_validate_cloudflare_amendment_header")

    assert len(function.body) == len(EXPECTED_CLOUDFLARE_AMENDMENT_HEADER_HELPERS)
    for statement, helper_name in zip(
        function.body,
        EXPECTED_CLOUDFLARE_AMENDMENT_HEADER_HELPERS,
        strict=True,
    ):
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Call)
        assert isinstance(statement.value.func, ast.Name)
        assert statement.value.func.id == helper_name
