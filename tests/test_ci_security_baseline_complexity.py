from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ci_security_baseline.py"
EXPECTED_DETECT_SECRETS_HELPERS = (
    "_validate_detect_secrets_file",
    "_validate_detect_secrets_findings",
    "_validate_detect_secrets_finding",
)


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing function: {name}")


def test_detect_secrets_report_validation_remains_decomposed() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    function = _function(tree, "validate_detect_secrets_report")

    for helper_name in EXPECTED_DETECT_SECRETS_HELPERS:
        _function(tree, helper_name)

    assert len(function.body) == 3
    assert isinstance(function.body[0], ast.Assign)
    assert isinstance(function.body[1], ast.If)
    assert isinstance(function.body[2], ast.For)

    loop = function.body[2]
    assert len(loop.body) == 1
    statement = loop.body[0]
    assert isinstance(statement, ast.Expr)
    assert isinstance(statement.value, ast.Call)
    assert isinstance(statement.value.func, ast.Name)
    assert statement.value.func.id == "_validate_detect_secrets_file"
