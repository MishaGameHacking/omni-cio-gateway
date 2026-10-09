"""Real adapters with synthetic provider responses; never access a real account."""

from dataclasses import replace
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from test_broker import _strategy_broker

from omnicio.instrument_facts import instrument_facts
from omnicio.tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable

UID = "synthetic-instrument"
ASSET = "synthetic-asset"


def overview(**changes):
    return {"instrument": {
        "uid": UID, "name": "Synthetic Company", "ticker": "SYNTH",
        "instrumentType": "share", "currency": "rub", "lot": 10,
        "exchange": "MOEX", "assetUid": ASSET, **changes,
    }}


def fundamentals(**changes):
    return {"fundamentals": [{
        "assetUid": ASSET, "currency": "usd",
        "marketCapitalization": 123456789.5, "peRatioTtm": 11.25,
        "dividendYieldDailyTtm": 0.025, "forwardAnnualDividendYield": 3.25,
        "priceToSalesTtm": 2.5, "priceToBookTtm": 1.5,
        "revenueTtm": 1000000, "netIncomeTtm": -30000, "epsTtm": -2.25,
        "freeCashFlowTtm": -8000.5, "totalDebtToEbitdaMrq": 1.75,
        "dividendPayoutRatioFy": 45, "roe": 0.15,
        "fiscalPeriodStartDate": "2025-01-01T00:00:00Z",
        "fiscalPeriodEndDate": "2025-12-31T00:00:00Z",
        **changes,
    }]}


@pytest.fixture
def runtime():
    broker, database, _, owner = _strategy_broker()
    # Public facts use one server source regardless of the personal connection.
    # Keep the real market parser while making any private read fail the test.
    broker.market_tbank = TBankInvestClient(purpose="market")
    broker.tbank = Mock(spec=TBankInvestClient)
    database.tbank_connection = Mock(side_effect=AssertionError("private account read forbidden"))
    yield broker, database, owner
    assert not broker.tbank.mock_calls
    database.tbank_connection.assert_not_called()


def read_card(runtime):
    broker, _, owner = runtime
    return instrument_facts(user_id=owner, instrument_uid=UID, broker=broker)


def test_exact_uid_card_uses_two_reads_and_keeps_currency_scale_period_and_sources(runtime):
    _, database, _ = runtime
    before = database.record
    with patch.object(
        TBankInvestClient, "_post", side_effect=[overview(), fundamentals()],
    ) as provider:
        result = read_card(runtime)
    assert result["status"] == "available"
    assert result["instrument_uid"] == UID
    assert result["asset_uid"] == ASSET
    assert result["currency"] == "RUB"
    assert result["exchange"] == "MOEX"
    assert result["lot"] == 10
    assert result["ticker"] == "SYNTH"
    assert database.record == before
    rows = {row["key"]: row for row in result["metrics"]}
    assert Decimal(rows["market_capitalization"]["value"]) == Decimal("123456789.5")
    assert rows["market_capitalization"]["unit"] == "USD"
    assert rows["pe_ratio_ttm"]["unit"] == "×"
    assert Decimal(rows["pe_ratio_ttm"]["value"]) == Decimal("11.25")
    assert rows["eps_ttm"]["unit"] == "USD/акцию"
    assert Decimal(rows["net_income_ttm"]["value"]) == -30000
    assert Decimal(rows["dividend_yield_daily_ttm"]["value"]) == Decimal("0.025")
    assert rows["dividend_yield_daily_ttm"]["unit"] == "ед. источника"
    assert "Прогнозная" in rows["forward_annual_dividend_yield"]["label"]
    assert rows["forward_annual_dividend_yield"]["unit"] == "%"
    assert all(row["period"] and row["source_url"].startswith("https://") for row in rows.values())
    assert result["data_as_of"] is None
    assert result["observed_at"]
    assert result["limitations"]
    assert [call.kwargs["method"] for call in provider.call_args_list] == [
        "GetInstrumentBy", "GetAssetFundamentals",
    ]
    assert provider.call_args_list[0].kwargs["body"] == {
        "idType": "INSTRUMENT_ID_TYPE_UID", "id": UID,
    }
    assert provider.call_args_list[1].kwargs["body"] == {"assets": [ASSET]}
    assert all(call.kwargs["token"] == "synthetic-shared-market-token"
               for call in provider.call_args_list)
    assert "t.fake-owner-credential" not in repr(result)


@pytest.mark.parametrize("optional_result", [
    {"fundamentals": []},
    TBankUnavailable("a private provider error including t.fake-owner-credential"),
])
def test_optional_statistics_failure_keeps_only_verified_overview(runtime, optional_result):
    with patch.object(
        TBankInvestClient, "_post", side_effect=[overview(), optional_result],
    ) as provider:
        result = read_card(runtime)
    assert provider.call_count == 2
    assert result["status"] == "partial"
    assert result["ticker"] == "SYNTH"
    assert result["metrics"] == []
    assert "asset_fundamentals" in result["missing_requirements"]
    assert "private provider" not in repr(result)
    assert "t.fake" not in repr(result)


def test_no_linked_asset_never_triggers_search_or_a_guessed_fundamental_request(runtime):
    with patch.object(TBankInvestClient, "_post", return_value=overview(assetUid="")) as provider:
        result = read_card(runtime)
    provider.assert_called_once()
    assert result["status"] == "partial"
    assert result["asset_uid"] is None
    assert "instrument:asset_uid" in result["missing_requirements"]


def test_zero_missing_statistics_are_not_rendered_as_observed_zero(runtime):
    response = fundamentals(marketCapitalization=0, peRatioTtm=0, dividendYieldDailyTtm=0, roe=0)
    with patch.object(TBankInvestClient, "_post", side_effect=[overview(), response]):
        result = read_card(runtime)
    keys = {row["key"] for row in result["metrics"]}
    assert not keys & {"market_capitalization", "pe_ratio_ttm", "dividend_yield_daily_ttm", "roe"}
    assert result["status"] == "partial"
    assert "metric:pe_ratio_ttm" in result["missing_requirements"]


def test_financial_currency_is_never_inferred_from_the_trading_currency(runtime):
    with patch.object(
        TBankInvestClient, "_post", side_effect=[overview(), fundamentals(currency="")],
    ):
        result = read_card(runtime)
    assert result["currency"] == "RUB"
    assert "fundamental_currency" in result["missing_requirements"]
    keys = {row["key"] for row in result["metrics"]}
    assert "market_capitalization" not in keys
    assert "pe_ratio_ttm" in keys


def test_overview_uid_mismatch_fails_before_any_statistical_read(runtime):
    with patch.object(
        TBankInvestClient, "_post", return_value=overview(uid="different-uid"),
    ) as provider, pytest.raises(TBankUnavailable, match="identity"):
        read_card(runtime)
    provider.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"assetUid": "different-asset"}, {"peRatioTtm": float("nan")}, {"marketCapitalization": True},
])
def test_invalid_statistics_cannot_enter_a_verified_instrument_card(runtime, changes):
    with patch.object(
        TBankInvestClient, "_post", side_effect=[overview(), fundamentals(**changes)],
    ):
        result = read_card(runtime)
    assert result["status"] == "partial"
    assert result["metrics"] == []
    assert result["asset_uid"] == ASSET
    assert "different-asset" not in repr(result)


@pytest.mark.parametrize("surface", ["overview", "fundamentals"])
@pytest.mark.parametrize("mutation", ["account", "credential", "disconnect"])
def test_public_facts_ignore_changes_to_a_private_connection(runtime, surface, mutation):
    _, database, _ = runtime

    def respond(**request):
        matching = (surface == "overview") == (request["method"] == "GetInstrumentBy")
        if matching:
            if mutation == "disconnect":
                database.record = None
            elif mutation == "account":
                database.record = replace(database.record, account_id="changed-account")
            else:
                database.record = replace(
                    database.record, encrypted_credential=b"changed-credential",
                )
        return overview() if request["method"] == "GetInstrumentBy" else fundamentals()

    with patch.object(TBankInvestClient, "_post", side_effect=respond) as provider:
        result = read_card(runtime)
    assert result["status"] == "available"
    assert provider.call_count == 2
    assert all(call.kwargs["token"] == "synthetic-shared-market-token"
               for call in provider.call_args_list)


def test_private_connection_change_does_not_invalidate_public_partial_statistics(runtime):
    _, database, _ = runtime

    def respond(**request):
        if request["method"] == "GetInstrumentBy":
            return overview()
        database.record = replace(database.record, account_id="changed-account")
        raise TBankUnavailable("provider unavailable")

    with patch.object(TBankInvestClient, "_post", side_effect=respond):
        result = read_card(runtime)
    assert result["status"] == "partial"
    assert result["metrics"] == []
    assert result["instrument_uid"] == UID


def test_missing_shared_source_never_falls_back_to_the_connected_personal_token(runtime):
    broker, _, _ = runtime
    broker._market_credential = ""
    with patch.object(TBankInvestClient, "_post") as provider, pytest.raises(TBankUnavailable):
        read_card(runtime)
    provider.assert_not_called()


def test_rejected_broker_credential_is_not_reported_as_merely_missing_metrics(runtime):
    with patch.object(
        TBankInvestClient, "_post", side_effect=[overview(), TBankTokenRejected("rejected")],
    ), pytest.raises(TBankTokenRejected):
        read_card(runtime)


@pytest.mark.parametrize("lot", [True, -1, "1.5"])
def test_malformed_overview_lot_is_not_coerced_into_a_tradeable_quantity(runtime, lot):
    with patch.object(TBankInvestClient, "_post", return_value=overview(lot=lot)), pytest.raises(
        TBankUnavailable, match="lot",
    ):
        read_card(runtime)
