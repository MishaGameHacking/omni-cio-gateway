"""Scenario arithmetic must not inherit a caller's financial rounding policy."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import (
    Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow,
    ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, Rounded, localcontext,
)

import pytest

from backend.portfolio_scenarios import JointScenario, ScenarioError, assess_scenarios

NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
NUMERIC_RESULTS = (
    "expected_net_return", "expected_real_return", "probability_of_loss",
    "value_at_risk", "expected_shortfall",
)


def evaluate():
    return assess_scenarios(
        {"A": Decimal("0.4"), "B": Decimal("0.6")},
        [JointScenario(Decimal("0.6"), {"A": Decimal("1000"), "B": Decimal("0.02")}),
         JointScenario(Decimal("0.4"), {"A": Decimal("-0.5"), "B": Decimal("-0.2")})],
        horizon_days=10, as_of=NOW, now=NOW, max_age_seconds=60,
        all_in_cost_rate="0.001", inflation_rate="0.03",
    )


def reference():
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN, Emin=-999999,
                              Emax=999999, capitals=1, clamp=0, flags=[],
                              traps=[InvalidOperation, DivisionByZero, Overflow])):
        return evaluate()


def fingerprint(ctx):
    return (ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax, ctx.capitals, ctx.clamp,
            dict(ctx.traps), dict(ctx.flags))


def evaluate_with_policy(index):
    with localcontext() as ctx:
        ctx.prec = 7
        ctx.rounding = (ROUND_CEILING, ROUND_FLOOR, ROUND_DOWN)[index % 3]
        ctx.Emax = 2 if index % 2 else 999999
        ctx.Emin = -2 if index % 2 else -999999
        ctx.capitals = index % 2
        ctx.clamp = index % 2
        ctx.traps[Inexact] = bool(index % 2)
        ctx.traps[Rounded] = bool(index % 3)
        ctx.traps[Overflow] = False
        ctx.flags[Inexact] = True
        before = fingerprint(ctx)
        result = evaluate()
        assert fingerprint(ctx) == before
        assert all(Decimal(result[key]).is_finite() for key in NUMERIC_RESULTS)
        return result


@pytest.mark.parametrize("index", range(12))
def test_scenarios_are_independent_of_callers_decimal_policy(index):
    expected = reference()
    assert evaluate_with_policy(index) == expected


def test_concurrent_requests_have_identical_results_and_preserve_contexts():
    expected = reference()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(evaluate_with_policy, range(64)))
    assert results == [expected] * 64


def test_invalid_input_does_not_modify_callers_decimal_context():
    rows = [JointScenario(Decimal(1), {"A": "NaN"})]
    with localcontext() as ctx:
        ctx.prec = 5
        ctx.traps[InvalidOperation] = False
        before = fingerprint(ctx)
        with pytest.raises(ScenarioError):
            assess_scenarios({"A": "1"}, rows, horizon_days=1, as_of=NOW,
                             now=NOW, max_age_seconds=60)
        assert fingerprint(ctx) == before
