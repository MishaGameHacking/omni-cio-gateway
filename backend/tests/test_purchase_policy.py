"""Adversarial financial constraints; all observations here are synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

import pytest
from fastapi import HTTPException

from backend.tests.test_volume_workspace import fixture
from backend import purchase_policy as policy
from backend import volume_catalogue as catalogue, volume_purchases as purchases
from backend.volume_contract import decimal, source


def quotation(amount, currency=None):
    value = Decimal(amount)
    row = {"units": str(int(value)), "nano": int((value - int(value)) * 1_000_000_000)}
    if currency:
        row["currency"] = currency
    return row


def inputs():
    now = datetime.now(timezone.utc)
    evidence = {"id": "synthetic-identity", "review_id": "test-review", "url": "https://example.invalid/review",
        "published_at": (now - timedelta(days=1)).isoformat(), "checked_at": now.isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat()}
    identity = {"issuer_id": "issuer-a", "group_id": "group-a", "source": evidence}
    row = {"account_id": "owned-a", "instrument_uid": "old", "instrument_type": "share",
           "value": {"amount": "1000", "currency": "RUB"}, "verified_identity": identity,
           "metadata": {"sector": "industry", "instrument_currency": "RUB"}}
    cash = {"account_id": "owned-a", "instrument_uid": "cash:RUB", "instrument_type": "cash",
            "value": {"amount": "9000", "currency": "RUB"}}
    return {"now": now, "observed_at": now.isoformat(), "lots": 1, "account_id": "owned-a",
        "snapshot": {"snapshot_id": "synthetic-snapshot", "as_of": now.isoformat(), "currency": "RUB",
            "positions": [row, cash], "capital": {"total": {"amount": "10000", "currency": "RUB"}},
            "position_coverage": {"complete": True}},
        "config": {"reserve": {"amount": "1000", "currency": "RUB"}, "allowed_markets": ["MOEX"],
            "limits": {axis + "_percent": "50" if axis != "currency" else "100" for axis in policy.AXES}},
        "meta": {"uid": "new", "instrumentType": "share", "currency": "RUB", "lot": 10,
            "buyAvailableFlag": True, "apiTradeAvailableFlag": True, "sector": "industry", "realExchange": "REAL_EXCHANGE_MOEX"},
        "identity": deepcopy(identity), "info": {},
        "credit": {"ratings": [{"subject_kind": "issuer", "level_within_agency": 9}], "warnings": []},
        "quote": {"lotsRequested": "1", "totalOrderAmount": quotation("1002", "RUB"),
            "initialOrderAmount": quotation("1000", "RUB")},
        "capacity": {"currency": "RUB", "buyLimits": {"buyMoneyAmount": quotation("9000"), "buyMaxLots": "8"},
            "buyMarginLimits": {"buyMoneyAmount": quotation("900000"), "buyMaxLots": "800"}}}


def test_costs_lots_and_concentration_use_decimal_and_all_accounts():
    data = inputs()
    other = deepcopy(data["snapshot"]["positions"][0])
    other.update(account_id="owned-b", instrument_uid="other-bond")
    other["value"]["amount"] = "3000"
    data["snapshot"]["positions"].append(other)
    data["snapshot"]["positions"][1]["value"]["amount"] = "6000"
    result = policy.assess_purchase(**data)
    assert "issuer_limit_exceeded" in result["reasons"]
    assert "group_limit_exceeded" in result["reasons"]
    assert result["quantity"] == "10"
    assert result["total_cost"]["amount"] == "1002"
    assert result["automatic_order"] is False


@pytest.mark.parametrize("target,key,value,reason", [
    ("meta", "buyAvailableFlag", False, "broker_purchase_unavailable"),
    ("meta", "blockedTcaFlag", True, "broker_purchase_unavailable"),
    ("meta", "forQualInvestorFlag", True, "broker_qualification_required"),
    ("meta", "requiredTests", ["bond-test"], "broker_tests_not_confirmed"),
    ("meta", "realExchange", "UNKNOWN", "market_not_allowed_or_unknown"),
    ("meta", "instrumentType", "etf", "instrument_requires_separate_risk_model"),
    ("meta", "subordinatedFlag", True, "complex_bond_not_allowed"),
    ("meta", "perpetualFlag", True, "complex_bond_not_allowed"),
    ("meta", "lot", "0.5", "instrument_lot_invalid"),
    ("meta", "currency", "USD", "currency_conversion_not_verified"),
    ("identity", "group_id", None, "candidate_identity_unverified"),
    ("quote", "lotsRequested", "2", "broker_cost_not_verified"),
    ("quote", "totalOrderAmount", None, "broker_cost_not_verified"),
    ("credit", "warnings", ["conflict"], "rating_evidence_incomplete_or_conflicting"),
    ("credit", "ratings", [], "issuer_rating_required"),
])
def test_each_hard_constraint_blocks(target, key, value, reason):
    data = inputs()
    data[target][key] = value
    assert reason in policy.assess_purchase(**data)["reasons"]


def test_bond_needs_issue_rating_and_worst_rating_cannot_be_averaged():
    data = inputs()
    data["meta"]["instrumentType"] = "bond"
    assert "issue_rating_required" in policy.assess_purchase(**data)["reasons"]
    data["credit"]["ratings"] += [{"subject_kind": "issue", "level_within_agency": 0},
                                 {"subject_kind": "issuer", "level_within_agency": 10}]
    assert "rating_below_bbb_minus_or_unknown" in policy.assess_purchase(**data)["reasons"]


def test_borrowed_capacity_and_reserve_cannot_fund_a_purchase():
    data = inputs()
    data["capacity"]["buyLimits"]["buyMaxLots"] = "0"
    assert "insufficient_own_money" in policy.assess_purchase(**data)["reasons"]
    data = inputs()
    data["capacity"]["buyLimits"]["buyMoneyAmount"] = quotation("1500")
    assert "protected_reserve_would_be_spent" in policy.assess_purchase(**data)["reasons"]


@pytest.mark.parametrize("age", [-1, 300, 86400])
def test_future_and_expired_snapshots_do_not_authorize_purchase(age):
    data = inputs()
    data["snapshot"]["as_of"] = (data["now"] - timedelta(seconds=age)).isoformat()
    assert "fresh_observations_required" in policy.assess_purchase(**data)["reasons"]


def test_calculation_cannot_renew_old_snapshot_book_or_broker_reads():
    now = datetime.now(timezone.utc)
    snapshot = {"as_of": (now - timedelta(seconds=299)).isoformat()}
    book = {"orderbookTs": (now - timedelta(seconds=58)).isoformat()}
    assert purchases.observation_expiry(now, snapshot, book, now) == now + timedelta(seconds=1)
    snapshot["as_of"] = now.isoformat()
    assert purchases.observation_expiry(now, snapshot, book, now) == now + timedelta(seconds=2)
    started = now - timedelta(seconds=61)
    assert purchases.observation_expiry(started, snapshot, book, now) < now
    data = inputs()
    data["observed_at"] = (data["now"] - timedelta(seconds=61)).isoformat()
    assert "fresh_observations_required" in policy.assess_purchase(**data)["reasons"]


def test_missing_or_duplicate_positions_do_not_appear_diversified():
    data = inputs()
    data["snapshot"]["positions"][0]["verified_identity"] = None
    assert "portfolio_identity_unverified" in policy.assess_purchase(**data)["reasons"]
    data = inputs()
    data["snapshot"]["positions"].append(deepcopy(data["snapshot"]["positions"][0]))
    assert "portfolio_values_incomplete_or_conflicting" in policy.assess_purchase(**data)["reasons"]


def test_financial_result_does_not_depend_on_callers_decimal_precision():
    data = inputs()
    expected = policy.assess_purchase(**data)
    assert expected["constraints_passed"]
    with localcontext() as context:
        context.prec = 4
        assert policy.assess_purchase(**data) == expected
        assert policy.margin_of_safety("75", "100") == "25.00"
    assert policy.margin_of_safety("0", "100") is None
    assert policy.margin_of_safety("120", "100") == "-20.0"


@pytest.mark.parametrize("value", [True, 0, -1, "1", 1.5])
def test_lots_are_positive_integers(value):
    data = inputs()
    data["lots"] = value
    with pytest.raises(ValueError, match="whole_positive_lots"):
        policy.assess_purchase(**data)


@pytest.mark.parametrize("value", [{"units": "1", "nano": -1}, {"units": "-1", "nano": 1},
                                   {"units": str(2**63), "nano": 0}, {"units": True, "nano": 0}])
def test_invalid_broker_quotations_never_become_money(value):
    assert decimal(value) is None


def test_exact_price_and_liquidity_do_not_use_margin_or_invent_quotes():
    assert purchases.price_quotation("12.123456789") == {"units": "12", "nano": 123456789}
    with pytest.raises(HTTPException):
        purchases.price_quotation("12.1234567891")
    now = datetime.now(timezone.utc)
    book = {"orderbookTs": now.isoformat(), "isConsistent": True, "asks": [{"price": quotation("10"), "quantity": "1"},
                                                        {"price": quotation("11"), "quantity": "100"}]}
    trading = {"limitOrderAvailableFlag": True, "apiTradeAvailableFlag": True}
    assert purchases.liquidity_reasons(book, trading, "10", 2, now) == ["insufficient_visible_liquidity_at_limit"]
    book["asks"].append(book["asks"][0])
    assert "order_book_invalid" in purchases.liquidity_reasons(book, trading, "10", 2, now)


def test_catalogue_search_is_complete_deterministic_and_revision_bound():
    rows = catalogue.normalize_catalogue({"instruments": [{"uid": str(i), "name": "Синтетическая компания", "ticker": "TEST" + str(i)} for i in range(2001)]}, "share")
    now = datetime.now(timezone.utc).isoformat()
    data = {"items": rows, "revision": "one", "as_of": now, "source": source("Shares", "all", now)}
    first = catalogue.search_page(data, "TEST2000", 0, 30, None)
    assert first["items"][0]["uid"] == "2000"
    first = catalogue.search_page(data, "", 0, 30, None)
    second = catalogue.search_page(data, "", 30, 30, first["revision"])
    assert not {r["uid"] for r in first["items"]} & {r["uid"] for r in second["items"]}
    with pytest.raises(HTTPException):
        catalogue.search_page({**data, "revision": "two"}, "", 30, 30, first["revision"])
    with pytest.raises(HTTPException):
        catalogue.search_page(data, "TEST", 30, 30, first["revision"])


def test_catalogue_conflicting_uid_and_control_characters_fail_closed():
    with pytest.raises(HTTPException):
        catalogue.normalize_catalogue({"instruments": [{"uid": "same", "ticker": "A"}, {"uid": "same", "ticker": "B"}]}, "share")
    with pytest.raises(HTTPException):
        catalogue.normalized_query("ticker\u202e")


def prepare_endpoint(fixture):
    from contextlib import closing
    from backend import app as backend, volume_state as state, volume_workspace as workspace
    data = inputs()
    snapshot = data['snapshot']
    snapshot['accounts'] = [{'id': 'owned-a', 'name': 'Synthetic account'}]
    workspace.persist(fixture['user'], snapshot)
    with closing(backend.connect()) as db:
        db.execute('INSERT INTO workspace_strategy_versions VALUES (?,?,?,?,?,?,?,?)',
                   (fixture['user']['id'], 1, state.encode(data['config']), snapshot['snapshot_id'], 0,
                    'synthetic test', 'test-strategy', 1))
        db.commit()
    calls = []
    class Reader:
        def __init__(self, user):
            self.user = user
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def account(self, account):
            calls.append(('ownership', account))
            if account != 'owned-a':
                raise HTTPException(404, 'account_not_found')
        def read(self, method, body):
            calls.append((method, body))
            return {'instrument': data['meta']}
    fixture['patch'].setattr(purchases.details, 'BrokerReader', Reader)
    fixture['patch'].setattr(purchases, 'reviewed_credit', lambda *_: (data['identity'], data['credit']))
    def read(reader, method, body):
        calls.append((method, body))
        return {'share_by': {'instrument': {**data['meta'], 'minPriceIncrement': quotation('0.01')}},
                'user_info': data['info'], 'max_lots': data['capacity'], 'order_price': data['quote'],
                'trading_status': {'instrumentUid': 'new', 'limitOrderAvailableFlag': True, 'apiTradeAvailableFlag': True},
                'order_book': {'instrumentUid': 'new', 'orderbookTs': datetime.now(timezone.utc).isoformat(),
                               'isConsistent': True, 'asks': [{'price': quotation('100'), 'quantity': '8'}]}}[method]
    fixture['patch'].setattr(purchases.market, 'broker_read', read)
    return {'account_id': 'owned-a', 'instrument_uid': 'new', 'lots': 1, 'limit_price': '100', 'strategy_version': 1}, data, calls


def test_purchase_endpoint_archives_encrypted_reproducible_evidence_and_isolates_users(fixture):
    from contextlib import closing
    from backend import app as backend
    payload, _, calls = prepare_endpoint(fixture)
    response = fixture['client'].post('/workspace/purchases/check', json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['constraints_passed'] is True
    assert result['suitability_complete'] is False
    assert calls[0] == ('ownership', 'owned-a')
    path = '/workspace/purchases/checks/' + result['check_id']
    archived = fixture['client'].get(path).json()
    assert archived['result'] == result
    assert purchases.digest(archived['inputs']) == result['input_digest']
    assert archived['historical_only']
    assert archived['requires_new_check']
    with closing(backend.connect()) as db:
        raw = db.execute("SELECT payload_json FROM workspace_records WHERE kind='purchase_check'").fetchone()[0]
    assert 'owned-a' not in raw
    assert 'encrypted' in raw
    backend.app.dependency_overrides[backend.current_user] = lambda: fixture['other']
    assert fixture['client'].get(path).status_code == 404


def test_expired_positive_result_cannot_be_committed(fixture):
    from contextlib import closing
    from backend import app as backend
    payload, _, _ = prepare_endpoint(fixture)
    original = purchases.archive_check
    def expired(user, result, observations):
        result["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        return original(user, result, observations)
    fixture["patch"].setattr(purchases, "archive_check", expired)
    response = fixture["client"].post("/workspace/purchases/check", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"] == "purchase_observations_expired"
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='purchase_check'").fetchone()[0] == 0


def test_purchase_foreign_account_is_rejected_before_account_specific_broker_reads(fixture):
    payload, _, calls = prepare_endpoint(fixture)
    response = fixture['client'].post('/workspace/purchases/check', json={**payload, 'account_id': 'someone-else'})
    assert response.status_code == 404
    assert calls == [('ownership', 'someone-else')]


@pytest.mark.parametrize('mutation', ['snapshot', 'strategy', 'broker_token'])
def test_purchase_input_races_never_archive_an_authorizing_result(fixture, mutation):
    from contextlib import closing
    from backend import app as backend, volume_workspace as workspace
    payload, data, _ = prepare_endpoint(fixture)
    original = purchases.market.broker_read
    def raced(reader, method, body):
        result = original(reader, method, body)
        if method == 'order_book':
            if mutation == 'snapshot':
                workspace.persist(fixture['user'], {**data['snapshot'], 'snapshot_id': 'changed'})
            else:
                with closing(backend.connect()) as db:
                    if mutation == 'strategy':
                        db.execute('UPDATE workspace_strategy_versions SET version=2 WHERE user_id=?', (fixture['user']['id'],))
                    else:
                        db.execute('UPDATE users SET tinvest_token_encrypted=NULL WHERE id=?', (fixture['user']['id'],))
                    db.commit()
        return result
    fixture['patch'].setattr(purchases.market, 'broker_read', raced)
    response = fixture['client'].post('/workspace/purchases/check', json=payload)
    assert response.status_code == 409, response.text
    with closing(backend.connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM workspace_records WHERE kind='purchase_check'").fetchone()[0] == 0


def test_market_identity_and_inconsistent_depth_do_not_pass(fixture):
    payload, _, _ = prepare_endpoint(fixture)
    original = purchases.market.broker_read
    def inconsistent(reader, method, body):
        result = original(reader, method, body)
        if method == 'order_book':
            result['isConsistent'] = False
        return result
    fixture['patch'].setattr(purchases.market, 'broker_read', inconsistent)
    result = fixture['client'].post('/workspace/purchases/check', json=payload).json()
    assert 'order_book_not_consistent' in result['reasons']
    def mismatched(reader, method, body):
        result = original(reader, method, body)
        if method == 'trading_status':
            result['instrumentUid'] = 'another'
        return result
    fixture['patch'].setattr(purchases.market, 'broker_read', mismatched)
    assert fixture['client'].post('/workspace/purchases/check', json=payload).status_code == 502


def test_bond_specific_metadata_must_explicitly_exclude_complex_structures():
    data = inputs()
    data['meta']['instrumentType'] = 'bond'
    assert 'complex_bond_not_excluded' in policy.assess_purchase(**data)['reasons']
    data['meta'].update(subordinatedFlag=False, perpetualFlag=False)
    assert 'complex_bond_not_excluded' not in policy.assess_purchase(**data)['reasons']


def test_overloaded_pacing_rejects_without_a_reservation_or_burst(monkeypatch):
    from backend import volume_market as market
    scope = ('synthetic-rate-test',)
    monkeypatch.setattr(market.time, 'monotonic', lambda: 10)
    monkeypatch.setattr(market, '_next_instrument_read', {scope: 15.5})
    with pytest.raises(HTTPException) as rejected:
        market.pace_instruments(scope)
    assert rejected.value.status_code == 429
    assert market._next_instrument_read[scope] == 15.5
    waits = []
    monkeypatch.setattr(market.time, 'sleep', waits.append)
    market._next_instrument_read[scope] = 14.9
    market.pace_instruments(scope)
    assert waits == [4.9]


@pytest.mark.parametrize('value', [{'units': None}, {'units': 'NaN'}, {'units': '1', 'nano': -1}, {'units': '1.5'}, {'units': '0', 'nano': 1000000000}])
def test_dashboard_number_does_not_turn_invalid_quotations_into_zero(value):
    assert purchases.details.number(value) is None


def test_future_observation_is_never_fresh_for_strategy_or_plans():
    from backend import volume_state as state
    assert state._observation_age((datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()) is None
    assert state._observation_age('2026-01-01T00:00:00') is None


def test_recovered_open_broker_request_cannot_revive_an_expired_plan(fixture):
    from backend import app as backend, volume_plans as plans, volume_state as state
    from backend.ai_budget import transaction
    request = plans.PlanCreate(request_id='stale-manual-create', title='Test plan', instrument_uid='aaa',
                               account_id='owned-account-a', side='buy', quantity='2', strategy_version=0)
    created = plans.create(request, user=fixture['user'])
    opening = state.RequestId(request_id='stale-manual-open')
    opened = plans.opened(created['id'], opening, user=fixture['user'])
    assert plans.opened(created['id'], opening, user=fixture['user']) == opened
    with transaction(backend.connect) as db:
        expired = {**opened, 'as_of': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
        state.record(db, fixture['user']['id'], 'manual_plan', created['id'], expired)
    with pytest.raises(HTTPException) as rejected:
        plans.opened(created['id'], opening, user=fixture['user'])
    assert rejected.value.detail == 'manual_plan_fresh_snapshot_required'


@pytest.mark.parametrize('value', [[], 'invalid', {'units': 'NaN'}, {'units': '1', 'nano': -1}, {'units': '1.5'}])
def test_legacy_portfolio_refuses_malformed_present_financial_values(value):
    from backend import tinvest_portfolio as portfolio
    with pytest.raises(HTTPException):
        portfolio._decimal(value)
    assert portfolio._decimal({'nano': 1}) == Decimal('0.000000001')
    assert portfolio._decimal({}) == 0  # Explicit proto3 default, not a missing observation.


def test_chat_links_do_not_claim_semantic_verification(fixture):
    from backend import volume_chat as chat
    from backend.ai_guarded_client import GuardError
    packet = chat.fact_packet(fixture['user'], {'mode': 'portfolio'})
    fact = packet['facts'][0]['id']
    result = chat.validate_response({'answer': 'Synthetic interpretation', 'claims': [
        {'text': 'Synthetic claim', 'fact_ids': [fact, fact]}]}, packet)
    assert result['financial_values_are_source_records'] is False
    assert result['source_facts_verified_separately'] is True
    assert result['claim_meaning_verified'] is False
    assert result['claims'][0]['fact_ids'] == [fact]
    for malformed in ([], {'answer': 'x', 'claims': [{'text': ' ', 'fact_ids': [fact]}]},
                      {'answer': 'x', 'claims': [{'text': 'a' * 4001, 'fact_ids': [fact]}]},
                      {'answer': 'x', 'actions': [{}] * 81}):
        with pytest.raises(GuardError):
            chat.validate_response(malformed, packet)


def test_bond_points_convert_to_settlement_currency_and_quote_must_reconcile():
    meta = {'instrumentType': 'bond', 'currency': 'RUB', 'nominal': quotation('1000', 'RUB'), 'lot': 2}
    points = purchases.price_quotation('95.5')
    assert purchases.settlement_price(meta, points) == quotation('955')
    assert purchases.quoted_principal_matches(meta, points, {'initialOrderAmount': quotation('1910', 'RUB')}, 1)
    assert not purchases.quoted_principal_matches(meta, points, {'initialOrderAmount': quotation('191', 'RUB')}, 1)
    meta['nominal']['currency'] = 'USD'
    with pytest.raises(HTTPException):
        purchases.settlement_price(meta, points)


def test_missing_test_in_instrument_cannot_be_overridden_by_an_older_user_info():
    data = inputs()
    data['meta']['requiredTests'] = ['bond']
    data['info']['qualifiedForWorkWith'] = ['bond']
    assert 'broker_tests_not_confirmed' in policy.assess_purchase(**data)['reasons']


def test_currency_includes_cash_without_double_counting_purchase():
    data = inputs()
    result = policy.assess_purchase(**data)
    currency = next(row for row in result["concentrations"] if row["axis"] == "currency")
    assert currency["amount_before"] == "10000"
    assert Decimal(currency["share_upper_bound_percent"]) == 100
    assert result["constraints_passed"]
    data["config"]["limits"]["currency_percent"] = "50"
    assert "currency_limit_exceeded" in policy.assess_purchase(**data)["reasons"]


def test_currency_denominations_do_not_follow_display_valuation():
    from backend import volume_state as state
    data = inputs()
    asset = data["snapshot"]["positions"][0]
    asset["metadata"]["instrument_currency"] = "USD"
    cash = data["snapshot"]["positions"][1]
    cash["instrument_uid"] = "cash:EUR"
    groups, errors = policy.exposure_amounts(data["snapshot"], data["now"])
    assert not errors
    assert groups["currency"] == {"USD": Decimal("1000"), "EUR": Decimal("9000")}
    assert state._axis_identity(asset, "currency")[:2] == ("USD", "USD")
    assert state._axis_identity(cash, "currency")[:2] == ("EUR", "EUR")
    assert "snapshot_cash_requires_refresh" in policy.assess_purchase(**data)["reasons"]
    del asset["metadata"]["instrument_currency"]
    assert state._axis_identity(asset, "currency")[:2] == (None, None)
    assert "portfolio_currency_unknown" in policy.assess_purchase(**data)["reasons"]


def test_cash_on_another_account_does_not_validate_stale_funding_snapshot():
    data = inputs()
    data["snapshot"]["positions"][1]["account_id"] = "owned-b"
    assert "snapshot_cash_requires_refresh" in policy.assess_purchase(**data)["reasons"]
