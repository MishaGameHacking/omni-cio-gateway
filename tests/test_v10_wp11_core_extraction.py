from __future__ import annotations

import ast
from pathlib import Path

from omni_cio.contracts.v1.meta_strategy import (
    StrategyFrictionEvidenceV1,
    StrategyRegime,
)
from omni_cio.core import CorePlanRequestV1, run_core_plan_pipeline
from tests.v9_plan_fixture import NOW, build_fixture


ROOT = Path(__file__).resolve().parents[1]
WP11_DETERMINISTIC_SOURCES = (
    Path("omni_cio/core/service_v1.py"),
    Path("omni_cio/policy/ips_v1.py"),
    Path("omni_cio/risk/engine_v1.py"),
    Path("omni_cio/strategy/selector_v1.py"),
    Path("omni_cio/optimizer/engine_v1.py"),
    Path("omni_cio/plans/protocol_v1.py"),
)
FORBIDDEN_IMPORT_PREFIXES = (
    "app",
    "app_v360",
    "app_v371",
    "gpt",
    "openai",
    "omni_cio.real_trading",
    "omni_cio.plan_execution",
)


def _friction_evidence() -> tuple[StrategyFrictionEvidenceV1, ...]:
    return tuple(
        StrategyFrictionEvidenceV1(
            regime=regime,
            transition_cost_weight="0.003",
            tax_cost_weight="0.001",
            as_of=NOW,
            source_sha256s=(source,),
        )
        for regime, source in (
            (StrategyRegime.CAPITAL_PRESERVATION, "a" * 64),
            (StrategyRegime.DEFENSIVE_BALANCED, "b" * 64),
            (StrategyRegime.BALANCED_CORE, "f" * 64),
            (StrategyRegime.GROWTH_CORE, "9" * 64),
        )
    )


def _request():
    legacy = build_fixture()
    return legacy, CorePlanRequestV1(
        portfolio=legacy.portfolio,
        policy=legacy.policy,
        assets=legacy.assets,
        friction_evidence=_friction_evidence(),
        evaluated_at=NOW,
    )


def test_wp11_core_pipeline_matches_golden_v9_fixture_exactly() -> None:
    legacy, request = _request()

    result = run_core_plan_pipeline(request)

    assert result.policy_assessment == legacy.assessment
    assert result.risk == legacy.current_risk
    assert result.strategy == legacy.strategy
    assert result.optimizer == legacy.optimizer
    assert result.plan == legacy.plan
    assert result.optimizer.trading_methods is False


def test_wp11_core_pipeline_is_reproducible_for_same_versioned_inputs() -> None:
    _, request = _request()

    first = run_core_plan_pipeline(request)
    second = run_core_plan_pipeline(request)

    assert second == first


def test_wp11_core_path_has_no_presentation_or_execution_import_dependency() -> None:
    for relative in WP11_DETERMINISTIC_SOURCES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(relative))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)

        for module in imported:
            assert not module.startswith(FORBIDDEN_IMPORT_PREFIXES), (
                f"WP11 deterministic path depends on forbidden layer: "
                f"{relative} -> {module}"
            )
