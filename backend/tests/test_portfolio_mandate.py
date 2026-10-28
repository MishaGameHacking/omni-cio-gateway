"""Synthetic isolated contracts; no broker or paid model calls."""
from copy import deepcopy
from decimal import localcontext
import pytest
from fastapi import HTTPException
from backend import volume_state as state, volume_workspace as workspace
from backend.portfolio_mandate import validated_mandate, mandate_purchase_reasons
from backend.tests.test_volume_workspace import fixture, config, activate

def mandate():
    return dict(asset_mode="mixed", base_currency="RUB", account_id="owned-account-a",
        loss_capacity_percent="5", bond_target_percent="60.125", share_target_percent="39.875",
        minimum_rating_level=6, max_discretionary_turnover_percent="10", turnover_window_days=30,
        max_trade_cost_percent="0.25", rebalance_cooldown_days=30,
        reinvest_coupons=True, reinvest_dividends=False, allowed_sessions=["main"])

def configured():
    return {**config(), "mandate": mandate()}

def test_legacy_edit_cannot_erase_mandate_and_readback_returns_only_owned_accounts(fixture):
    activate(fixture, configured())
    legacy = config()
    legacy['horizon_months'] = 48
    _, _, result = activate(fixture, legacy, expected=1, request='legacy-2')
    assert result['active']['config']['mandate'] == mandate()
    assert result['active']['config']['horizon_months'] == 48
    response = fixture['client'].get('/workspace/strategy')
    assert response.status_code == 200
    assert {row['id'] for row in response.json()['available_accounts']} == {'owned-account-a', 'owned-account-b'}
    assert response.json()['mandate_execution_mode'] == 'read_only'
    assert state.get_strategy(user=fixture['other'])['available_accounts'] == []

def test_explicit_null_cannot_remove_existing_mandate(fixture):
    activate(fixture, configured())
    response = fixture['client'].post('/workspace/strategy/preview', json={
        'expected_version':1, 'config':{**config(), 'mandate':None}})
    assert response.status_code == 409
    assert state.active_strategy(fixture['user']['id'])['version'] == 1

def test_rollback_to_legacy_version_preserves_current_mandate(fixture):
    activate(fixture)
    activate(fixture, configured(), expected=1, request='mandate-2')
    preview = state.preview_strategy(state.StrategyPreview(expected_version=2, rollback_to_version=1), user=fixture['user'])
    result = state.confirm_strategy(state.StrategyConfirm(preview_id=preview['preview_id'],expected_version=2,request_id='rollback-3'),user=fixture['user'])
    assert result['active']['config']['mandate'] == mandate()

def test_account_revocation_between_preview_and_commit_blocks_same_snapshot_identifier(fixture):
    preview = state.preview_strategy(state.StrategyPreview(expected_version=0, config=configured()), user=fixture['user'])
    snapshot = deepcopy(fixture['snapshot'])
    snapshot['accounts'] = [row for row in snapshot['accounts'] if row['id'] != 'owned-account-a']
    workspace.persist(fixture['user'], snapshot)
    assert snapshot['snapshot_id'] == fixture['snapshot']['snapshot_id']
    with pytest.raises(HTTPException) as error:
        state.confirm_strategy(state.StrategyConfirm(preview_id=preview['preview_id'],expected_version=0,request_id='revoked-account'),user=fixture['user'])
    assert error.value.status_code == 409
    assert error.value.detail == 'mandate_account_not_in_current_verified_snapshot'
    assert state.active_strategy(fixture['user']['id']) is None

def test_mandate_exact_percentages_ignore_external_decimal_precision():
    with localcontext() as ctx:
        ctx.prec = 3
        assert validated_mandate(mandate()) == mandate()

@pytest.mark.parametrize('field,value', [
    ('asset_mode','funds'), ('base_currency','USD'), ('minimum_rating_level',10),
    ('minimum_rating_level',True), ('rebalance_cooldown_days',True), ('rebalance_cooldown_days',-1),
    ('turnover_window_days',0), ('allowed_sessions',['weekend']), ('reinvest_coupons','false'),
    ('loss_capacity_percent','NaN'), ('max_trade_cost_percent','-0.1'),
    ('bond_target_percent','60.126'), ('asset_mode','bonds')])
def test_invalid_mandate_never_becomes_active(fixture,field,value):
    cfg = configured(); cfg['mandate'][field] = value
    response = fixture['client'].post('/workspace/strategy/preview',json={'expected_version':0,'config':cfg})
    assert response.status_code == 422
    assert state.active_strategy(fixture['user']['id']) is None

@pytest.mark.parametrize('account', ['foreign-account', 'owned-account-b-not-present'])
def test_unverified_account_is_rejected(fixture,account):
    cfg=configured(); cfg['mandate']['account_id']=account
    response=fixture['client'].post('/workspace/strategy/preview',json={'expected_version':0,'config':cfg})
    assert response.status_code == 409

def test_owner_floor_class_and_zero_risk_are_independent_constraints():
    cfg=configured(); cfg['mandate'].update(asset_mode='bonds',bond_target_percent='100',share_target_percent='0',loss_capacity_percent='0')
    reasons=mandate_purchase_reasons(cfg,'share','other',{'ratings':[{'level_within_agency':7}]})
    assert set(reasons)=={'instrument_class_outside_mandate','account_outside_mandate','zero_loss_capacity_blocks_new_risk','rating_below_owner_mandate'}
    assert mandate_purchase_reasons(config(),'share','owned-account-a',{}) == []
