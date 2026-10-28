"""Malformed saved values never become readiness or crash normal status reads."""
from datetime import datetime, timezone
import pytest
from backend.source_observability import lane_inventory, news_inventory
from backend.workspace_readiness import build_status
NOW=datetime(2026,10,27,9,tzinfo=timezone.utc)

@pytest.mark.parametrize('value',[[],{},False,7])
def test_malformed_attempt_is_unknown_not_a_status_exception(value):
    data={'as_of':NOW.isoformat(),'event_monitor':{'news':value},'events':{'complete':True}}
    lane=next(row for row in lane_inventory(data,now=NOW) if row['id']=='events')
    assert lane['latest_attempt'] is None

@pytest.mark.parametrize('value',[[],{},False,7])
def test_malformed_account_identifier_is_not_selected(value):
    strategy={'config':{'mandate':{'account_id':value}}}
    result=build_status({'accounts':[{'id':'synthetic-owned'}],'positions':[]},strategy,connected=True,now=NOW)
    assert result['mandate']['selected_account_in_snapshot'] is False
    assert result['real_orders_enabled'] is False

def test_absent_news_are_not_reported_as_an_observation():
    assert news_inventory(None,now=NOW)['state']=='not_collected'

@pytest.mark.parametrize('identifier',['','x'*201])
def test_news_identity_must_be_nonempty_and_bounded(identifier):
    result=news_inventory({'events':{'items':[{'id':identifier,'published_at':NOW.isoformat()}]}},now=NOW)
    assert result['invalid_or_future_publications']==1

def test_empty_calendar_response_cannot_claim_complete_coverage():
    data={'calendar':{'state':'available','data':{'as_of':NOW.isoformat(),'exchanges':[]}}}
    lane=next(row for row in lane_inventory(data,now=NOW) if row['id']=='calendar')
    assert lane['coverage_complete'] is False
