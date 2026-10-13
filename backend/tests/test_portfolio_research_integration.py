"""Actual backend integration, all external data synthetic and transports mocked."""
from __future__ import annotations
import copy
from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault('TELEGRAM_CLIENT_ID','123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET','test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL','https://example.invalid')
os.environ.setdefault('FERNET_KEY','AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED']='false'

from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import app as backend, portfolio_research as research, portfolio_details as details
from backend.tests.test_autonomous_ai import sample_snapshot


class ResearchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path=patch.object(backend,'DATABASE_PATH',Path(self.temp.name)/'test.sqlite')
        self.path.start();backend.init_db()
        with closing(backend.connect()) as db:
            db.execute("INSERT INTO users(telegram_sub,telegram_id,tinvest_token_encrypted,created_at,updated_at) VALUES ('research-test','99',?,1,1)",(b'encrypted-test-only',))
            db.commit()
            self.user=db.execute("SELECT * FROM users WHERE telegram_sub='research-test'").fetchone()
        self.at=datetime(2026,10,13,10,tzinfo=timezone.utc)
    def tearDown(self):
        self.path.stop();self.temp.cleanup()
    def snapshot(self):
        result=sample_snapshot(cash_share=20,stock_share=80)
        result['accounts'][0]['positions'][0].update(instrumentType='share',assetUid='asset-1',isin='RU000A000001',sector='industry')
        result['accounts'][0]['positions'][1]['instrumentType']='cash'
        return result
    def collect(self,snapshot=None,profile=None):
        with patch.object(details,'load_dashboard',return_value=snapshot or self.snapshot()), \
             patch.object(details,'BrokerReader'), \
             patch.object(research,'optional_broker_read',return_value=({},None)), \
             patch.object(research,'get_profile',return_value=profile or {'configured':True,'max_position_percent':25}):
            return research.collect_research(self.user)
    def test_authenticated_route_registered(self):
        with TestClient(backend.app) as client, patch.object(research,'collect_research') as collect:
            response=client.get('/analysis/research')
            self.assertEqual(response.status_code,401)
            collect.assert_not_called()
    def test_configured_concentration_explained_without_order(self):
        result=self.collect()
        card=result['cards'][0]
        self.assertEqual(card['action'],'review_reduce')
        self.assertIn('100',card['explanation'])
        self.assertFalse(card['order_created']);self.assertEqual(result['paid_model_calls'],0)
    def test_default_profile_is_not_user_agreement(self):
        card=self.collect(profile={'configured':False,'max_position_percent':25})['cards'][0]
        self.assertEqual(card['action'],'watch');self.assertNotIn('Ваш предел',card['explanation'])
    def test_no_agency_import_means_no_rating_guess(self):
        card=self.collect()['cards'][0]
        self.assertEqual(card['credit']['ratings'],[])
        self.assertIsNone(card['credit']['default_probability'])
        self.assertEqual(card['statement']['state'],'missing')
    def test_missing_history_does_not_create_probability(self):
        value=self.collect()['risk']
        self.assertEqual(value['state'],'insufficient_verified_history')
        self.assertIsNone(value['default_probability'])
    def test_partial_duplicate_valuation_not_understated(self):
        snapshot=self.snapshot()
        extra=copy.deepcopy(snapshot['accounts'][0]);extra['id']='another-account'
        extra['positions'][0]['currentValue']=None
        snapshot['accounts'].append(extra)
        card=self.collect(snapshot)['cards'][0]
        self.assertIsNone(card['share_percent']);self.assertEqual(card['action'],'watch')
    def test_margin_cash_does_not_allow_total_risk_estimate(self):
        snapshot=self.snapshot();snapshot['accounts'][0]['positions'][1]['currentValue']['value']['units']=-100
        self.assertEqual(self.collect(snapshot)['risk']['state'],'incomplete_valuation')
    def test_unpriced_virtual_position_not_ignored(self):
        snapshot=self.snapshot();snapshot['accounts'][0]['virtualPositions']=[{'id':'virtual'}]
        self.assertEqual(self.collect(snapshot)['risk']['state'],'incomplete_valuation')
    def test_news_matches_uid_not_similar_ticker(self):
        item={'id':1,'title':'Test','source':'Test-source','ts':self.at.isoformat(),'instrumentId':[{'instrument':{'instrumentUid':'A','ticker':'TEST'}}]}
        self.assertEqual(len(research.relevant_news([item],'A',self.at)),1)
        self.assertEqual(research.relevant_news([item],'B',self.at),[])
    def test_future_news_not_used(self):
        item={'id':1,'title':'Future','ts':(self.at+timedelta(hours=1)).isoformat(),'instrumentId':[{'instrument':{'instrumentUid':'A'}}]}
        self.assertEqual(research.relevant_news([item],'A',self.at),[])
    def test_news_does_not_return_full_article(self):
        item={'id':1,'title':'Test','content':'private whole article','summary':'long','ts':self.at.isoformat(),'instrumentId':[{'instrument':{'instrumentUid':'A'}}]}
        result=research.relevant_news([item],'A',self.at)[0]
        self.assertNotIn('content',result);self.assertNotIn('summary',result)
    def test_missing_metric_not_zero(self):
        result=research.broker_company_summary({'netIncomeTtm':-1},'industry')
        self.assertIsNone(result['metrics']['revenueTtm']);self.assertFalse(result['full_statement_reviewed'])
        self.assertTrue(result['messages'])
    def test_optional_broker_failure_not_false_safety(self):
        reader=Mock()
        with patch.object(details.portfolio,'_post_tinvest',side_effect=HTTPException(503,'unavailable')):
            result,error=research.optional_broker_read(reader,'news',{'limit':100})
        self.assertEqual(result,{});self.assertIsNotNone(error)
    def test_missing_token_denied_before_research(self):
        with patch.object(research,'collect_research') as collect, self.assertRaises(HTTPException):
            research.research(user={'id':3,'tinvest_token_encrypted':None})
        collect.assert_not_called()
    def test_status_uses_real_response_not_demo(self):
        self.assertFalse(self.collect()['analysis_is_complete'])
        self.assertFalse(self.collect()['autotrading'])


if __name__=='__main__':unittest.main()
