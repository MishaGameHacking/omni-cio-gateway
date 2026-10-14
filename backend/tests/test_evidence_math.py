"""Synthetic isolated mathematics/evidence tests; no production quotes or trades."""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backend import risk_math as risk, research_store as store
from backend.credit_evidence import EvidenceError, Source, Rating, Statement, credit_assessment, statement_analysis
from backend.investment_links import instrument_link, valid_instrument_link

NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


def source(**kwargs):
    fields = dict(id='synthetic-source', url='https://acra-ratings.ru/ratings/example',
                  published_at=(NOW-timedelta(days=1)).isoformat(), checked_at=(NOW-timedelta(hours=1)).isoformat(),
                  expires_at=(NOW+timedelta(days=10)).isoformat(), review_id='test-review')
    return Source(**{**fields, **kwargs})


def rating(**kwargs):
    return Rating(**{**dict(agency='ACRA', scale='RU_NATIONAL_LONG_TERM', grade='AA(RU)',
                           subject_kind='issue', subject_id='A', status='active', outlook='stable', source=source()), **kwargs})


class RiskMathTests(unittest.TestCase):
    def test_fractional_es_not_naive_threshold_average(self):
        answer=risk.tail_loss([0,1,2,3],.625)
        self.assertAlmostEqual(answer['expected_shortfall'], 8/3)
        self.assertEqual(answer['var'],2)
    def test_tied_tail(self):
        self.assertAlmostEqual(risk.tail_loss([1,1,1,2],.5)['expected_shortfall'],1.5)
    def test_negative_loss_is_not_forced_to_positive(self):
        self.assertLess(risk.tail_loss([-3,-2,-1])['expected_shortfall'],0)
    def test_nan_and_bool_fail(self):
        for value in [float('nan'), float('inf'),True,'1']:
            with self.subTest(value=value), self.assertRaises(risk.RiskDataError): risk.finite(value)
    def test_unaligned_dates_are_not_imputed(self):
        with self.assertRaises(risk.RiskDataError): risk.aligned_returns({'a':{'2026-01-01':0,'2026-01-02':0},'b':{'2026-01-02':0,'2026-01-03':0}},minimum=2)
    def test_aligned_order_is_stable(self):
        names,days,rows=risk.aligned_returns({'b':{'2026-01-02':.2,'2026-01-01':.1},'a':{'2026-01-01':0,'2026-01-02':0}},minimum=2)
        self.assertEqual(names,('a','b'));self.assertEqual(rows,((0,.1),(0,.2)))
    def test_return_below_total_loss_rejected(self):
        with self.assertRaises(risk.RiskDataError): risk.aligned_returns({'a':{'2026-01-01':-1.1,'2026-01-02':0}},minimum=2)
    def test_covariance_and_shrinkage(self):
        rows=[[-1,-2],[0,0],[1,2]]
        self.assertEqual(risk.covariance(rows,0),[[1,2],[2,4]])
        self.assertEqual(risk.covariance(rows,1),[[1,0],[0,4]])
        self.assertAlmostEqual(risk.portfolio_variance(rows,[.5,.5],0),2.25)
    def test_leverage_and_short_weights_rejected(self):
        for weights in [[.8,.8],[-.1,.8],[1]]:
            with self.assertRaises(risk.RiskDataError):risk.long_only_weights(weights,2)
    def test_effective_number_is_not_asset_count(self):
        self.assertEqual(risk.effective_positions([1,1,1,1]),4)
        self.assertAlmostEqual(risk.effective_positions([.9,.1]),1/.82)
    def test_drawdown_uses_running_peak(self):
        self.assertAlmostEqual(risk.drawdown([100,120,90,130,100]),.25)
    def test_zero_observed_events_not_zero_upper_bound(self):
        low,high=risk.wilson_interval(0,100)
        self.assertLess(low,1e-12);self.assertGreater(high,0)
    def test_bootstrap_joint_identical_assets(self):
        one=[[x] for x in [-.02,.01,.005]*40]
        two=[[row[0],row[0]] for row in one]
        a=risk.bootstrap_floor_risk(one,[1],paths=100)
        b=risk.bootstrap_floor_risk(two,[.5,.5],paths=100)
        self.assertEqual(a,b)
    def test_bootstrap_reproducible_no_guarantee(self):
        rows=[[-.05],[.01]]*60
        a=risk.bootstrap_floor_risk(rows,[.8],paths=100)
        self.assertEqual(a,risk.bootstrap_floor_risk(rows,[.8],paths=100))
        self.assertFalse(a['guarantee']);self.assertFalse(a['is_default_probability'])
    def test_bootstrap_total_loss_retains_cash(self):
        a=risk.bootstrap_floor_risk([[-1]]*120,[.5],horizon=1,paths=100,floor_fraction=.4)
        self.assertEqual(a['conditional_breach_frequency'],0)
        self.assertAlmostEqual(a['expected_shortfall'],.5)
    def test_credit_duplicate_issuer_same_default(self):
        item={'issuer_id':'x','exposure':100,'pd':.1,'lgd':.6,'horizon_days':365,'calibration_source':'test-only'}
        value=risk.credit_loss([item,item],365)
        self.assertEqual(value['expected_loss'],12)
        self.assertEqual(value['any_default_probability_bounds'],[.1,.1])
    def test_credit_dependent_bounds(self):
        items=[{'issuer_id':str(i),'exposure':100,'pd':p,'lgd':.5,'horizon_days':365,'calibration_source':'test'} for i,p in enumerate([.1,.2])]
        value=risk.credit_loss(items,365)
        self.assertAlmostEqual(value['any_default_probability_bounds'][1],.3)
        self.assertFalse(value['independence_assumed'])
    def test_credit_requires_calibration_and_horizon(self):
        with self.assertRaises(risk.RiskDataError):risk.credit_loss([{'horizon_days':365}],365)
        with self.assertRaises(risk.RiskDataError):risk.credit_loss([],0)


class CreditEvidenceTests(unittest.TestCase):
    def assess(self,ratings,bond=True):
        return credit_assessment(ratings,issuer_id='ISSUER',instrument_id='A',at=NOW,bond=bond)
    def test_issue_rating_kept_with_agency(self):
        value=self.assess([rating()]);self.assertTrue(value['has_required_rating']);self.assertIsNone(value['default_probability'])
    def test_issuer_is_not_bond_rating(self):
        value=self.assess([rating(subject_kind='issuer',subject_id='ISSUER')])
        self.assertFalse(value['has_required_rating']);self.assertEqual(len(value['ratings']),1)
    def test_no_cross_scale_conversion(self):
        self.assertIsNone(rating(scale='INTERNATIONAL',grade='AA').level())
        self.assertIsNone(rating(grade='AAA(ru.sf)').level())
    def test_fake_agency_domain_is_rejected(self):
        self.assertIsNone(rating(source=source(url='https://acra-ratings.ru.evil.test/')).level())
    def test_withdrawal_overrides_old_rating(self):
        withdrawn=rating(status='withdrawn',source=source(published_at=(NOW-timedelta(minutes=30)).isoformat(),checked_at=NOW.isoformat()))
        self.assertFalse(self.assess([withdrawn,rating()])['has_required_rating'])
    def test_expired_latest_does_not_resurrect_old(self):
        stale=rating(source=source(published_at=(NOW-timedelta(hours=4)).isoformat(),checked_at=(NOW-timedelta(hours=3)).isoformat(),expires_at=(NOW-timedelta(minutes=1)).isoformat()))
        self.assertFalse(self.assess([rating(),stale])['has_required_rating'])
    def test_future_information_excluded(self):
        future=rating(source=source(published_at=(NOW+timedelta(days=1)).isoformat(),checked_at=(NOW+timedelta(days=1)).isoformat()))
        self.assertFalse(self.assess([future])['has_required_rating'])
    def test_agencies_remain_separate(self):
        other=rating(agency='EXPERT_RA',grade='ruA',source=source(url='https://raexpert.ru/ratings/example'))
        self.assertEqual(len(self.assess([rating(),other])['ratings']),2)
    def test_negative_outlook_is_not_ignored(self):
        self.assertTrue(self.assess([rating(outlook='negative')])['watch'])
    def test_evidence_needs_review_and_time(self):
        self.assertFalse(source(review_id='').valid(NOW))
        self.assertFalse(source(url='http://acra-ratings.ru/').valid(NOW))
        self.assertFalse(source(url='https://acra-ratings.ru:invalid/').valid(NOW))
        self.assertFalse(source().valid(NOW.replace(tzinfo=None)))
    def statement(self,**kwargs):
        return Statement(**{**dict(issuer_id='ISSUER',sector='industry',standard='IFRS',currency='RUB',period_start='2025-01-01T00:00:00Z',period_end='2025-12-31T00:00:00Z',values={'net_debt':'100','ebitda':'20','ebit':'10','interest_expense':'20','free_cash_flow':'-1'},source=source(),audited=True),**kwargs})
    def test_statement_same_basis_ratios(self):
        value=statement_analysis(self.statement(),issuer_id='ISSUER',at=NOW)
        self.assertEqual(value['ratios']['net_debt_to_ebitda'],'5')
        self.assertEqual(value['ratios']['interest_coverage'],'0.5')
        self.assertTrue(value['messages'])
    def test_negative_ebitda_does_not_mean_safe_leverage(self):
        value=statement_analysis(self.statement(values={'net_debt':'100','ebitda':'-10'}),issuer_id='ISSUER',at=NOW)
        self.assertNotIn('net_debt_to_ebitda',value['ratios']);self.assertTrue(value['messages'])
    def test_bank_needs_sector_model(self):
        self.assertEqual(statement_analysis(self.statement(sector='banks'),issuer_id='ISSUER',at=NOW)['state'],'sector_model_required')
    def test_wrong_issuer_missing(self):
        self.assertEqual(statement_analysis(self.statement(),issuer_id='OTHER',at=NOW)['state'],'missing')


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'store.sqlite'
    def tearDown(self):self.temp.cleanup()
    def connect(self):return sqlite3.connect(self.path)
    def test_identical_import_deduplicated(self):
        payload=asdict(rating())
        a=store.import_record(self.connect,kind='rating',subject='A',payload=payload,at=NOW)
        b=store.import_record(self.connect,kind='rating',subject='A',payload=payload,at=NOW)
        self.assertEqual(a,b);self.assertEqual(len(store.records(self.connect,'rating','A')),1)
    def test_wrong_rating_subject_rejected(self):
        payload = asdict(rating())
        with self.assertRaises(EvidenceError):
            store.import_record(self.connect,kind='rating',subject='B',payload=payload,at=NOW)
    def test_real_instants_not_lexical_offsets(self):
        a={'issuer_id':'old','instrument_uid':'A','source':asdict(source(published_at='2026-10-12T13:00:00+03:00'))}
        b={'issuer_id':'new','instrument_uid':'A','source':asdict(source(published_at='2026-10-12T11:00:00+00:00'))}
        for p in [b,a]:store.import_record(self.connect,kind='issuer_identity',subject='A',payload=p,at=NOW)
        self.assertEqual(store.latest_verified(self.connect,'issuer_identity','A',NOW)['issuer_id'],'new')
    def test_returns_need_total_return_basis(self):
        p={'source':asdict(source()),'instrument_uid':'A','currency':'RUB','basis':'raw_close','values':{}}
        with self.assertRaises(EvidenceError):store.import_record(self.connect,kind='total_returns',subject='A',payload=p,at=NOW)
    def test_returns_cannot_include_future_data(self):
        values={(date(2026,7,1)+timedelta(days=i)).isoformat():0 for i in range(120)}
        p={'source':asdict(source()),'instrument_uid':'A','currency':'RUB','basis':'total_return','values':values}
        with self.assertRaises(EvidenceError):store.import_record(self.connect,kind='total_returns',subject='A',payload=p,at=NOW)


class InstrumentLinkTests(unittest.TestCase):
    def test_only_instrument_pages(self):
        for kind,ticker in [('share','SBER'),('bond','SU26232RMFS7'),('etf','TPAY'),('etf','TOFZ@')]:
            url=instrument_link(kind,ticker)
            self.assertTrue(valid_instrument_link(url))
    def test_isin_fallback_is_search_identifier(self):
        self.assertEqual(instrument_link('bond',None,'RU000A105RH2'),'https://www.tbank.ru/invest/bonds/RU000A105RH2/')
    def test_url_injection_rejected(self):
        for url in ['http://www.tbank.ru/invest/stocks/SBER/','https://www.tbank.ru.evil.test/invest/stocks/SBER/',
                    'https://evil@www.tbank.ru/invest/stocks/SBER/','https://www.tbank.ru/invest/stocks/SBER/?action=buy',
                    'https://www.tbank.ru/invest/stocks/../','https://www.tbank.ru/invest/stocks/%53BER/',
                    'intent://buy', 'https://www.tbank.ru:444/invest/stocks/SBER/']:
            with self.subTest(url=url):self.assertFalse(valid_instrument_link(url))
    def test_unknown_type_or_unsafe_ticker_has_no_link(self):
        self.assertIsNone(instrument_link('future','TEST'))
        self.assertIsNone(instrument_link('share','SBER/?buy=1'))


if __name__=='__main__':unittest.main()
