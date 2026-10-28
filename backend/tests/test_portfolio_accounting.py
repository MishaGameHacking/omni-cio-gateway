"""Synthetic arithmetic evidence only, never the owner's financial records."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, Inexact, localcontext
import pytest
from backend.portfolio_accounting import (
    AccountingError, Scope, CashBalance, CashMovement, ObservedWindow,
    FlowValuation, InvestorCashFlow, reconcile_cash,
    time_weighted_return, money_weighted_return,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=31)
SCOPE = Scope('synthetic-owner', 'synthetic-broker-v1', 'synthetic-account')


def balances():
    return (CashBalance(SCOPE,START,'RUB','1000','independent-opening',independent_of_operation_ledger=True),
            CashBalance(SCOPE,END,'RUB','1100','independent-closing',independent_of_operation_ledger=True))


def movement(identifier='coupon',amount='100',at=END,state='settled'):
    return CashMovement(SCOPE,identifier,at,'RUB',amount,'synthetic-op-proof-'+identifier,state)


def window(start=START,end=END,complete=True):
    return ObservedWindow(SCOPE,start,end,'synthetic-complete-settlements',complete)


def twr(points,**kwargs):
    return time_weighted_return(points,currency='RUB',all_external_flows_observed=True,
                               all_valuations_reconciled=kwargs.get('reconciled',True))


def xirr(flows,**kwargs):
    return money_weighted_return(flows,currency='RUB',all_external_flows_observed=True,
                                terminal_value_reconciled=kwargs.get('reconciled',True))


def test_cash_coupon_reconciliation_with_duplicate_observation():
    result=reconcile_cash(*balances(),[movement(),movement()],[window()])
    assert result['reconciled'] is True
    assert result['settled_movements']==1
    assert Decimal(result['difference'])==0
    assert result['tax_liability_estimated'] is False


def test_cash_trade_fee_tax_are_each_counted_once_without_annotations():
    opening,closing=balances()
    closing=replace(closing,amount='498')
    result=reconcile_cash(opening,closing,[movement('buy','-500'),movement('fee','-1'),movement('tax','-1')],[window()])
    assert result['expected_closing']=='498'
    assert result['reconciled'] is True


def test_real_cash_mismatch_is_exposed_not_forced_to_zero():
    result=reconcile_cash(*balances(),[movement(amount='99')],[window()])
    assert result['state']=='mismatch' and result['difference']=='1'


@pytest.mark.parametrize('windows',[
    [],[window(complete=False)],
    [window(end=START+timedelta(days=10)),window(start=START+timedelta(days=11))],
])
def test_incomplete_or_gapped_settlement_windows_block_reconciliation(windows):
    result=reconcile_cash(*balances(),[movement()],windows)
    assert result['reconciled'] is False and result['expected_closing'] is None
    assert 'settlement_coverage_incomplete' in result['reasons']


def test_adjacent_and_overlapping_windows_merge_without_gap():
    split=START+timedelta(days=10)
    assert reconcile_cash(*balances(),[movement()],[window(end=split),window(start=split)])['reconciled']


@pytest.mark.parametrize('state',['pending','unknown'])
def test_unresolved_movements_do_not_make_a_reconciled_cash_balance(state):
    result=reconcile_cash(*balances(),[movement(state=state)],[window()])
    assert 'unresolved_cash_movements' in result['reasons']


def test_cancelled_operation_is_not_cash_and_boundaries_are_start_exclusive():
    opening,closing=balances()
    result=reconcile_cash(opening,closing,[movement(),movement('old','900',START),
        movement('cancelled','800',state='cancelled')],[window()])
    assert result['reconciled'] and result['settled_movements']==1


def test_conflicting_duplicates_block_arithmetic():
    result=reconcile_cash(*balances(),[movement(),movement(amount='101')],[window()])
    assert result['expected_closing'] is None
    assert 'conflicting_movement_versions' in result['reasons']


@pytest.mark.parametrize('field,value',[
    ('scope',Scope('other','synthetic-broker-v1','synthetic-account')),
    ('scope',Scope('synthetic-owner','changed-token','synthetic-account')),
    ('scope',Scope('synthetic-owner','synthetic-broker-v1','other-account')),
    ('currency','USD'),
])
def test_cross_scope_and_cross_currency_input_is_rejected(field,value):
    with pytest.raises(AccountingError):
        reconcile_cash(*balances(),[replace(movement(),**{field:value})],[window()])


def test_buying_power_or_ledger_generated_balance_is_not_independent_reconciliation():
    opening,closing=balances()
    result=reconcile_cash(replace(opening,basis='buying_power'),
        replace(closing,independent_of_operation_ledger=False),[movement()],[window()])
    assert result['reconciled'] is False
    assert set(result['reasons'])=={'settled_cash_basis_required','independent_cash_balances_required'}


@pytest.mark.parametrize('amount',[True,False,1.0,'NaN','Infinity','-Infinity','1e25','1e-10','9'*81])
def test_invalid_money_is_not_coerced_or_silently_rounded(amount):
    opening, closing = balances()
    cash_movement = movement(amount=amount)
    observed_window = window()
    with pytest.raises(AccountingError):
        reconcile_cash(opening, closing, [cash_movement], [observed_window])


def test_exact_flow_twr_separates_deposit_from_gain():
    points=[FlowValuation(START,'100','100','0','opening'),
            FlowValuation(START+timedelta(days=10),'110','210','100','deposit'),
            FlowValuation(END,'231','231','0','closing')]
    result=twr(points)
    assert Decimal(result['return'])==Decimal('.21')
    assert result['annualized'] is False
    assert result['segments']==2


def test_withdrawal_is_not_a_loss_and_coupon_stays_inside_nav():
    points=[FlowValuation(START,'100','100','0','opening'),
            FlowValuation(START+timedelta(days=10),'110','60','-50','withdrawal'),
            FlowValuation(END,'66','66','0','closing')]
    assert Decimal(twr(points)['return'])==Decimal('.21')


def test_unreconciled_flow_and_misordered_valuations_are_rejected():
    with pytest.raises(AccountingError):
        twr([FlowValuation(START,'100','100','1','wrong'),FlowValuation(END,'100','100','0','closing')])
    with pytest.raises(AccountingError):
        twr([FlowValuation(END,'100','100','0','later'),FlowValuation(START,'100','100','0','earlier')])


def test_missing_evidence_or_zero_denominator_produces_unknown_not_zero_return():
    points=[FlowValuation(START,'0','0','0','opening'),FlowValuation(END,'100','100','0','closing')]
    assert twr(points)['return'] is None
    assert twr(points,reconciled=False)['return'] is None


@pytest.mark.parametrize('terminal,expected',[('1100','.1'),('900','-.1'),('1000','0')])
def test_xirr_known_one_year_solution(terminal,expected):
    result=xirr([InvestorCashFlow(date(2025,1,1),'-1000','deposit'),InvestorCashFlow(date(2026,1,1),terminal,'closing')])
    assert abs(Decimal(result['return'])-Decimal(expected))<Decimal('1e-25')
    assert abs(Decimal(result['npv_residual']))<Decimal('1e-20')


def test_xirr_leap_year_uses_actual_days_not_assumed_year_length():
    result=xirr([InvestorCashFlow(date(2024,1,1),'-1000','deposit'),InvestorCashFlow(date(2025,1,1),'1100','closing')])
    rate=Decimal(result['return'])
    assert Decimal('.099')<rate<Decimal('.1')


def test_multiple_irr_roots_are_not_chosen_by_an_initial_guess():
    flows=[InvestorCashFlow(date(2023,1,1),'-100','first'),
           InvestorCashFlow(date(2024,1,1),'230','second'),InvestorCashFlow(date(2025,1,1),'-132','third')]
    assert xirr(flows)['return'] is None
    assert xirr(flows)['reason']=='xirr_unique_investment_root_not_established'


def test_same_day_cashflows_are_aggregated_before_sign_changes():
    flows=[InvestorCashFlow(date(2025,1,1),'-1200','deposit'),InvestorCashFlow(date(2025,1,1),'200','withdrawal'),
           InvestorCashFlow(date(2026,1,1),'1100','closing')]
    assert abs(Decimal(xirr(flows)['return'])-Decimal('.1'))<Decimal('1e-25')


def test_return_inputs_are_not_mutated_and_decimal_context_is_isolated():
    flows=[InvestorCashFlow(date(2025,1,1),'-1000','deposit'),InvestorCashFlow(date(2026,1,1),'1100','closing')]
    expected=xirr(flows)
    with localcontext() as ctx:
        ctx.prec=3
        ctx.traps[Inexact]=True
        actual=xirr(flows)
    assert actual==expected
    assert flows[0].amount=='-1000'


def test_same_day_or_missing_terminal_evidence_is_not_an_annualized_number():
    flows=[InvestorCashFlow(date(2025,1,1),'-1000','deposit'),InvestorCashFlow(date(2025,1,1),'1100','closing')]
    assert xirr(flows)['return'] is None
    assert xirr(flows,reconciled=False)['return'] is None
