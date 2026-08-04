from __future__ import annotations

from datetime import timedelta

from tests.v9_execution_fixture import NOW, build_execution_fixture
from tests.v9_plan_fixture import build_fixture


def test_staged_plan_validity_covers_optimizer_execution_horizon() -> None:
    fixture = build_execution_fixture()
    execution_days = max(
        row.optimizer_leg.required_execution_days
        for row in fixture.plan.legs
        if row.optimizer_leg is not None
    )
    assert execution_days >= 2
    assert fixture.plan.expires_at == NOW + timedelta(
        days=execution_days - 1,
        seconds=900,
    )


def test_single_day_plan_keeps_short_owner_validity_window() -> None:
    fixture = build_fixture()
    assert all(
        row.required_execution_days == 1
        for row in fixture.optimizer.legs
    )
    assert fixture.plan.expires_at == NOW + timedelta(seconds=900)
