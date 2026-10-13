from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import unittest
from backend.portfolio_risk import (Evidence, CreditEstimate, Asset, BuyLimits, ResearchDataError,
    expected_shortfall, portfolio_scenarios, wilson_interval, bootstrap_capital_floor,
    exposure_groups, statement_metrics, reduction_plan, official_instrument_url, preview_one_lot_buy)

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
SOURCE = Evidence('synthetic:test:quote', NOW-timedelta(hours=1), NOW+timedelta(days=1))
CREDIT = CreditEstimate('TestAgency', 'RU-national', 'TEST', 365, .01, .4, 'synthetic:calibration:v1', SOURCE)


def asset(uid='a', units=100, issuer='company-a', sector='energy'):
    return Asset(uid, uid.upper(), None, 'Synthetic', issuer, sector, 'share', 'RUB', D(100), 10,
                 units, 0, True, True, False, SOURCE, CREDIT)


class PortfolioRiskTests(unittest.TestCase):
    def test_credit_loss_requires_matched_horizon_and_calibration(self):
        self.assertEqual(CREDIT.expected_loss(D(10000), 365, NOW), D('60.000'))
        with self.assertRaises(ResearchDataError): CREDIT.expected_loss(D(1), 30, NOW)
        with self.assertRaises(ResearchDataError): replace(CREDIT, withdrawn=True).expected_loss(D(1), 365, NOW)

    def test_rating_scales_never_silently_merge(self):
        self.assertNotEqual(CREDIT.bucket, replace(CREDIT, scale='global').bucket)
        self.assertNotEqual(CREDIT.bucket, replace(CREDIT, agency='Other').bucket)

    def test_stale_or_future_or_naive_evidence_rejected(self):
        for source in (replace(SOURCE, valid_until=NOW-timedelta(minutes=1)),
                       replace(SOURCE, as_of=NOW+timedelta(minutes=1)),
                       replace(SOURCE, as_of=NOW.replace(tzinfo=None))):
            with self.assertRaises(ResearchDataError): source.check(NOW)

    def test_company_is_aggregated_across_securities(self):
        items=[asset(), asset('bond', issuer='company-a')]
        result=exposure_groups(items,D(10000),'RUB',NOW)
        self.assertEqual(result['groups']['issuer']['company-a'],D(2)/D(3))

    def test_duplicates_unknown_metadata_or_foreign_currency_fail_closed(self):
        for items in ([asset(),asset()], [replace(asset(),issuer='')], [replace(asset(),currency='USD')]):
            with self.assertRaises(ResearchDataError): exposure_groups(items,D(1),'RUB',NOW)

    def test_fund_lookthrough_not_assumed(self):
        with self.assertRaises(ResearchDataError): exposure_groups([replace(asset(),asset_class='etf')], D(1), 'RUB', NOW)

    def test_fractional_tail_expected_shortfall(self):
        result=expected_shortfall([10,8,2,0],.625)
        self.assertAlmostEqual(result['expected_shortfall'], (10+8*.5)/1.5)
        self.assertEqual(result['var'],8)
        self.assertIsNotNone(result['warning'])

    def test_empirical_var_uses_cdf_quantile_at_exact_rank(self):
        result=expected_shortfall(list(range(1,101)),.95)
        self.assertEqual(result['var'],95)
        self.assertEqual(result['expected_shortfall'],98)

    def test_expired_rating_exposure_is_unknown(self):
        credit=replace(CREDIT, evidence=replace(SOURCE, valid_until=NOW-timedelta(minutes=1)))
        result=exposure_groups([replace(asset(),credit=credit)],D(10000),'RUB',NOW)
        self.assertIn('UNRATED', result['groups']['rating_bucket'])

    def test_all_equal_losses_have_identical_tail(self):
        self.assertAlmostEqual(expected_shortfall([2]*100,.95)['expected_shortfall'],2)

    def test_joint_scenarios_preserve_hedge(self):
        self.assertEqual(portfolio_scenarios([.5,.5], [[.2,-.2],[-.1,.1]]), [0,0])

    def test_bad_returns_and_leverage_rejected(self):
        for weights,rows in (([1.1],[[0]]), ([-1],[[.2]]), ([1],[[float('nan')]]), ([1],[[-2]]), ([1],[[0,1]])):
            with self.assertRaises(ResearchDataError): portfolio_scenarios(weights, rows)

    def test_zero_simulation_events_still_has_nonzero_upper_bound(self):
        lo,hi=wilson_interval(0,1000)
        self.assertEqual(lo,0)
        self.assertGreater(hi,0)

    def test_bootstrap_reproducible_and_no_zero_risk_promise(self):
        kwargs=dict(floor_fraction=.5,horizon_steps=10,block_size=2,paths=100,seed=7,evidence=SOURCE,now=NOW)
        a=bootstrap_capital_floor([.5],[[.01],[-.02],[0]],**kwargs)
        self.assertEqual(a,bootstrap_capital_floor([.5],[[.01],[-.02],[0]],**kwargs))
        self.assertFalse(a['guaranteed_safety'])
        self.assertGreater(a['sampling_interval_95'][1],0)

    def test_default_scenario_can_exhaust_invested_capital(self):
        result=bootstrap_capital_floor([1],[[-1],[-1]],floor_fraction=.1,horizon_steps=1,block_size=1,paths=100,seed=4,evidence=SOURCE,now=NOW)
        self.assertEqual(result['scenario_breach_frequency'],1)

    def test_fundamentals_do_not_divide_by_nonpositive_ebitda(self):
        args=dict(debt=100,cash=20,ebitda=0,ebit=0,interest=0,operating_cashflow=-10,net_income=None,evidence=SOURCE,now=NOW)
        result=statement_metrics(**args,financial_sector=False)
        self.assertIsNone(result['net_debt_to_ebitda'])
        self.assertIsNone(result['interest_coverage'])
        self.assertTrue(result['warnings'])
        result=statement_metrics(**args,financial_sector=True)
        self.assertIn('банков', result['warnings'][0])

    def test_reductions_do_not_sell_blocked_units_or_odd_lots(self):
        item=replace(asset(units=100),blocked_units=75)
        result=reduction_plan([item],D(0),base_currency='RUB',issuer_cap=D('.25'),minimum_trade_value=D(0),fee_rate=D('.01'),now=NOW)
        self.assertEqual(result['actions'][0]['units'],20)
        self.assertTrue(result['warnings'])
        self.assertFalse(result['automatic_trading'])

    def test_cash_only_portfolio_no_sell_suggestion(self):
        result=reduction_plan([],D(100),base_currency='RUB',issuer_cap=D('.25'),minimum_trade_value=D(0),fee_rate=D(0),now=NOW)
        self.assertFalse(result['actions'])

    def test_links_are_read_only_and_do_not_accept_arbitrary_paths(self):
        self.assertEqual(official_instrument_url('share','SBER'),'https://www.tbank.ru/invest/stocks/SBER/')
        for text in ('../../', 'SBER?order=buy', 'https://evil', '..'):
            self.assertIsNone(official_instrument_url('share', text))

    def limits(self):
        return BuyLimits(D('.1'),D('.4'),D('.8'),{CREDIT.bucket:D(1)}, {'share':D(1)}, .02, D('.5'),D('.01'),365)

    def preview(self, candidate=None, **kwargs):
        return preview_one_lot_buy(candidate or asset('new',0,'company-b','retail'),[asset()],D(10000),base_currency='RUB',
            limits=kwargs.get('limits',self.limits()), fee_rate=D('.003'),daily_traded_value=D(1000000),
            liquidity_evidence=SOURCE,fundamentals_evidence=SOURCE,now=NOW)

    def test_new_candidate_can_pass_funded_single_lot(self):
        self.assertTrue(self.preview()['eligible'])

    def test_no_rating_means_no_buy(self):
        self.assertFalse(self.preview(replace(asset('new',0),credit=None))['eligible'])

    def test_reserved_cash_not_spent(self):
        self.assertFalse(self.preview(limits=replace(self.limits(),min_cash_fraction=D('.9')))['eligible'])

    def test_same_company_concentration_blocks_buy(self):
        self.assertFalse(self.preview(asset('new',0))['eligible'])

    def test_rating_bucket_budget_blocks_buy(self):
        self.assertFalse(self.preview(limits=replace(self.limits(),max_rating_fraction={CREDIT.bucket:D('.1')}))['eligible'])


if __name__=='__main__': unittest.main()
