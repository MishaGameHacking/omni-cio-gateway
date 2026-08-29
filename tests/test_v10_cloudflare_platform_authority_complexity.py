from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_cloudflare_platform_authority.py"
EXPECTED_BUILDS_AND_SEQUENCE_HELPERS = (
    "_validate_builds_reference_values_and_flags",
    "_validate_implementation_sequence",
)
EXPECTED_REPOSITORY_HELPERS_PREFIX = (
    "_validate_repository_markers",
    "_validate_retired_workflow_guards",
    "_validate_quality_contract_overlay",
)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def _call_names(statements: list[ast.stmt]) -> list[str]:
    names: list[str] = []
    for statement in statements:
        if not isinstance(statement, ast.Expr):
            continue
        if not isinstance(statement.value, ast.Call):
            continue
        if not isinstance(statement.value.func, ast.Name):
            continue
        names.append(statement.value.func.id)
    return names


def test_builds_and_sequence_validation_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "_validate_builds_and_sequence")

    assert len(function.body) == len(EXPECTED_BUILDS_AND_SEQUENCE_HELPERS)
    for statement, helper_name in zip(
        function.body,
        EXPECTED_BUILDS_AND_SEQUENCE_HELPERS,
        strict=True,
    ):
        assert isinstance(statement, ast.Expr)
        assert isinstance(statement.value, ast.Call)
        assert isinstance(statement.value.func, ast.Name)
        assert statement.value.func.id == helper_name


def test_validate_repository_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "validate_repository")

    call_names = _call_names(function.body)
    for helper_name in EXPECTED_REPOSITORY_HELPERS_PREFIX:
        assert helper_name in call_names, f"missing decomposed call: {helper_name}"
