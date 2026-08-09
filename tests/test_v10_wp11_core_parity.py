from __future__ import annotations

import ast
from pathlib import Path

from omni_cio.core import compile_portfolio_plan
from tests.v9_plan_fixture import NOW, PlanFixture, build_fixture, build_no_action_fixture


ROOT = Path(__file__).resolve().parents[1]
CORE_SOURCES = (
    ROOT / "omni_cio" / "core" / "__init__.py",
    ROOT / "omni_cio" / "core" / "planning_v1.py",
    ROOT / "omni_cio" / "contracts" / "v1" / "core_planning.py",
)
FORBIDDEN_IMPORTS = (
    "app",
    "app_v360",
    "app_v371",
    "main",
    "fastapi",
    "openai",
    "omni_cio.real_trading",
    "omni_cio.plan_execution",
)


def _assert_planning_parity(fixture: PlanFixture) -> None:
    result = compile_portfolio_plan(
        portfolio=fixture.portfolio,
        policy=fixture.policy,
        policy_assessment=fixture.assessment,
        strategy=fixture.strategy,
        optimizer_assets=fixture.assets,
        evaluated_at=NOW,
    )

    assert result.current_risk.model_dump(mode="json") == fixture.current_risk.model_dump(
        mode="json"
    )
    assert result.optimizer.model_dump(mode="json") == fixture.optimizer.model_dump(
        mode="json"
    )
    assert result.plan.model_dump(mode="json") == fixture.plan.model_dump(mode="json")


def _import_names(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return tuple(names)


def test_wp11_core_matches_accepted_v9_golden_plan() -> None:
    _assert_planning_parity(build_fixture())


def test_wp11_core_matches_accepted_v9_no_action_plan() -> None:
    _assert_planning_parity(build_no_action_fixture())


def test_wp11_core_has_no_presentation_ai_or_execution_imports() -> None:
    for path in CORE_SOURCES:
        assert path.is_file(), path
        for imported in _import_names(path):
            assert not any(
                imported == forbidden or imported.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_IMPORTS
            ), (path, imported)
