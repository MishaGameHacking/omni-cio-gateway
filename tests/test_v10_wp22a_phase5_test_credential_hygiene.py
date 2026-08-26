from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "tests/test_v10_wp22a_phase5_runtime_composition.py",
    "tests/test_v10_wp22a_phase5_runtime_verifier_wiring.py",
    "tests/test_v10_wp22a_phase5_telegram_fixed_endpoints.py",
    "tests/test_v10_wp22a_phase5_provider_start_authority.py",
    "tests/test_v10_wp22a_phase5_telegram_jwks.py",
)
SECRET_ENV_KEYS = frozenset(
    {
        "OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET",
        "OMNI_V10_CSRF_BINDING_KEY_HEX",
        "OMNI_V10_IDENTITY_BINDING_KEY_HEX",
    }
)
_SECRET_NAME_MARKERS = ("SECRET", "PASSWORD", "TOKEN", "KEY")


def _is_static_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (str, bytes))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
        return _is_static_literal(node.left) and _is_static_literal(node.right)
    return False


def _assignment_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def test_phase5_auth_test_credentials_are_not_hard_coded() -> None:
    violations: list[str] = []
    for relative in TARGETS:
        path = ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is not None and _is_static_literal(value):
                    for name in _assignment_names(node):
                        if any(marker in name.upper() for marker in _SECRET_NAME_MARKERS):
                            violations.append(f"{relative}:{node.lineno}:{name}")
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if keyword.arg == "client_secret" and _is_static_literal(keyword.value):
                        violations.append(
                            f"{relative}:{node.lineno}:client_secret"
                        )
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values, strict=True):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value in SECRET_ENV_KEYS
                        and _is_static_literal(value)
                    ):
                        violations.append(f"{relative}:{node.lineno}:{key.value}")

    assert violations == []
