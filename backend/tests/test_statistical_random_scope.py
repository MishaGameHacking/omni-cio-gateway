"""Offline synthetic tests for the exact locally reviewed statistical RNG sink."""
import ast
from datetime import datetime, timedelta, timezone
import inspect
import json
from unittest.mock import patch
import unittest

from backend import portfolio_risk as risk


NOW = datetime(2026, 10, 14, tzinfo=timezone.utc)
EVIDENCE = risk.Evidence('synthetic-test-only', NOW - timedelta(days=1), NOW + timedelta(days=1))


def simulate(**overrides):
    options = dict(floor_fraction=.99, horizon_steps=3, block_size=2,
                   paths=100, seed=81426, evidence=EVIDENCE, now=NOW)
    return risk.bootstrap_capital_floor([.5], [[-.03], [.01], [-.02], [.02]], **{**options, **overrides})


class StatisticalRandomScopeTests(unittest.TestCase):
    def test_seed_reproduces_after_another_simulation(self):
        first = simulate()
        simulate(seed=42)
        self.assertEqual(simulate(), first)

    def test_simulation_does_not_advance_global_rng(self):
        before = risk.random.getstate()
        simulate()
        self.assertEqual(risk.random.getstate(), before)

    def test_generator_used_only_for_bounded_row_index(self):
        class RowSampler:
            def __init__(self):
                self.bounds = []
            def randrange(self, limit):
                self.bounds.append(limit)
                return 0
        sampler = RowSampler()
        with patch.object(risk.random, 'Random', return_value=sampler) as factory:
            result = simulate()
        factory.assert_called_once_with(81426)
        self.assertTrue(sampler.bounds)
        self.assertEqual(set(sampler.bounds), {3})
        self.assertEqual(result['paths'], 100)

    def test_result_is_statistics_not_generator_or_security_token(self):
        result = simulate()
        self.assertEqual(set(result), {'scenario_breach_frequency', 'sampling_interval_95', 'paths',
                                      'horizon_steps', 'block_size', 'seed', 'source_id',
                                      'guaranteed_safety', 'explanation'})
        self.assertEqual(result['seed'], 81426)
        self.assertFalse(result['guaranteed_safety'])
        json.dumps(result, allow_nan=False)

    def test_invalid_seed_rejected_before_rng(self):
        with patch.object(risk.random, 'Random') as factory:
            with self.assertRaises(risk.ResearchDataError):
                simulate(seed=True)
            factory.assert_not_called()

    def test_work_limit_rejected_before_rng(self):
        with patch.object(risk.random, 'Random') as factory:
            with self.assertRaises(risk.ResearchDataError):
                simulate(paths=10000, horizon_steps=756)
            factory.assert_not_called()

    def test_reviewed_constructor_is_single_local_expression(self):
        source = inspect.getsource(risk)
        tree = ast.parse(source)
        constructors = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == 'random' and n.func.attr == 'Random']
        self.assertEqual(len(constructors), 1)
        constructor = constructors[0]
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'bootstrap_capital_floor')
        self.assertIn(constructor, list(ast.walk(function)))
        self.assertEqual(ast.unparse(constructor), 'random.Random(seed)')
        annotated = [line for line in source.splitlines() if '# NOSONAR' in line]
        self.assertEqual(len(annotated), 1)
        self.assertIn('rng = random.Random(seed)', annotated[0])
        self.assertIn('STATISTICAL_RANDOM_REVIEW.md', annotated[0])

    def test_rng_reference_does_not_escape_its_local_sampling_call(self):
        function = ast.parse(inspect.getsource(risk.bootstrap_capital_floor)).body[0]
        parents = {child: node for node in ast.walk(function) for child in ast.iter_child_nodes(node)}
        references = [n for n in ast.walk(function) if isinstance(n, ast.Name) and n.id == 'rng']
        self.assertEqual(len(references), 2)
        stores = [n for n in references if isinstance(n.ctx, ast.Store)]
        self.assertEqual(len(stores), 1)
        for node in references:
            if isinstance(node.ctx, ast.Load):
                parent = parents[node]
                self.assertIsInstance(parent, ast.Attribute)
                self.assertEqual(parent.attr, 'randrange')
                self.assertIsInstance(parents[parent], ast.Call)


if __name__ == '__main__':
    unittest.main()
