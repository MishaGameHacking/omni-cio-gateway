"""Explain missing suitability evidence without changing the owner's mandate."""
import copy

import pytest

from backend import decision_cycle as cycle
from backend.tests.test_decision_cycle import inputs, NOW


@pytest.mark.parametrize('field,value,reason', [
    ('loss_capacity_confirmed', False, 'loss_capacity_not_confirmed'),
    ('loss_capacity_confirmed', 1, 'loss_capacity_not_confirmed'),
    ('income_stability', 'unknown', 'income_stability_unknown'),
    ('income_stability', None, 'income_stability_unknown'),
])
def test_individual_unconfirmed_fields_remain_blocking(field, value, reason):
    active, snapshot, discovery, revision = inputs()
    active['config']['construction'][field] = value
    original = copy.deepcopy(active)
    result = cycle.evaluate(active, snapshot, discovery, revision, NOW, 'connection-one')
    codes = {row['code'] for row in result['blockers']}
    assert codes == {'real_order_execution_disabled', 'investment_profile_incomplete', reason}
    assert active == original
    assert result['proposed_action'] is None
    assert result['no_op'] is True


@pytest.mark.parametrize('capacity', [None, 'NaN', '-1', '101', True, 'unavailable'])
def test_invalid_capacity_is_explained_and_fails_closed(capacity):
    active, snapshot, discovery, revision = inputs()
    active['config']['mandate']['loss_capacity_percent'] = capacity
    result = cycle.evaluate(active, snapshot, discovery, revision, NOW, 'connection-one')
    codes = {row['code'] for row in result['blockers']}
    assert codes == {'real_order_execution_disabled', 'investment_profile_incomplete', 'loss_capacity_invalid'}
    assert result['proposed_action'] is None


def test_zero_capacity_is_an_explicit_constraint_not_a_missing_profile():
    active, snapshot, discovery, revision = inputs()
    active['config']['mandate']['loss_capacity_percent'] = '0'
    result = cycle.evaluate(active, snapshot, discovery, revision, NOW, 'connection-one')
    assert {row['code'] for row in result['blockers']} == {
        'zero_loss_capacity_blocks_new_risk', 'real_order_execution_disabled'}
    assert result['proposed_action'] is None
    assert result['execution']['real_orders_enabled'] is False


def test_all_missing_fields_are_explained_separately():
    assert set(cycle._profile_blockers({'config': {}})) == {
        'investment_profile_incomplete', 'loss_capacity_not_confirmed',
        'income_stability_unknown', 'loss_capacity_invalid'}
