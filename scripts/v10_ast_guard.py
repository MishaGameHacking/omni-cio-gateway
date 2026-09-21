from __future__ import annotations

import ast


def call_lines(
    function: ast.FunctionDef,
    *,
    owner: str | None,
    name: str,
) -> tuple[int, ...]:
    """Return source lines for exact direct or one-owner method calls."""
    lines: list[int] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if owner is None:
            if isinstance(node.func, ast.Name) and node.func.id == name:
                lines.append(node.lineno)
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == owner
            and node.func.attr == name
        ):
            lines.append(node.lineno)
    return tuple(lines)
