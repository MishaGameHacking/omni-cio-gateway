"""Regression for the real 2026-10-27 TradingSchedules HTTP 400.

Synthetic calendar payloads only. A successful calendar read never authorizes
trading and does not invent coverage for a previous UTC day.
"""
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
os.environ.setdefault('TELEGRAM_CLIENT_ID','123456')
os.environ.setdefault('TELEGRAM_CLIENT_SECRET','test-only')
os.environ.setdefault('BACKEND_PUBLIC_URL','https://example.invalid')
os.environ.setdefault('FERNET_KEY','AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
os.environ['ANALYSIS_SCHEDULER_ENABLED']='false'
from backend import app as backend
from backend import volume_market as market

@pytest.mark.parametrize('instant',[
    datetime(2026,10,27,6,59,tzinfo=timezone.utc),
    datetime(2026,10,27,0,0,tzinfo=timezone.utc),
    datetime(2026,10,27,23,59,59,tzinfo=timezone.utc),
    datetime(2026,12,31,23,59,59,tzinfo=timezone.utc),
    datetime(2028,2,29,12,tzinfo=timezone.utc),
])
def test_calendar_request_never_begins_in_previous_utc_day(monkeypatch,instant):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return instant.astimezone(tz or timezone.utc)
    monkeypatch.setattr(market,'datetime',Clock)
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    seen=[]
    def read(reader,method,body):
        assert method=='calendar'
        seen.append(body)
        assert datetime.fromisoformat(body['from']).date()==instant.date()
        return {'exchanges':[]}
    monkeypatch.setattr(market,'broker_read',read)
    result=market.load_calendar(object())
    assert len(seen)==1
    begin=datetime.fromisoformat(seen[0]['from'])
    finish=datetime.fromisoformat(seen[0]['to'])
    assert begin.utcoffset()==timedelta(0)
    assert timedelta(0)<finish-begin<timedelta(days=14)
    assert result['exchanges']==[]
    assert result['basis']=='broker_sections_not_guaranteed_instrument_availability'
    assert 'trade_permission' not in result

@pytest.mark.parametrize('payload',[{}, {'exchanges':None},{'exchanges':'MOEX'}])
def test_invalid_calendar_response_is_not_treated_as_closed_or_open(monkeypatch,payload):
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    monkeypatch.setattr(market,'broker_read',lambda *args:payload)
    with pytest.raises(HTTPException) as caught:market.load_calendar(object())
    assert caught.value.status_code==502
    assert caught.value.detail=='calendar_invalid_response'

def test_calendar_error_is_preserved_without_a_synthetic_schedule(monkeypatch):
    monkeypatch.setattr(market.details,'BrokerReader',MagicMock())
    def read(*args):raise HTTPException(502,'tinvest_unexpected_status')
    monkeypatch.setattr(market,'broker_read',read)
    with pytest.raises(HTTPException) as caught:market.load_calendar(object())
    assert caught.value.detail=='tinvest_unexpected_status'
