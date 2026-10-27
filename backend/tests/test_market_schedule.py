"""Synthetic calendar contracts; no weekday assumptions or live broker calls."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from backend.market_schedule import polling_state, required_exchanges

NOW = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)  # Sunday, deliberately.


def calendar(*, now=NOW, trading=True):
    return {"state": "available", "data": {"timezone": "UTC", "as_of": (now - timedelta(seconds=10)).isoformat(),
        "exchanges": [{"exchange": "MOEX", "days": [{"date": now.replace(hour=0).isoformat(),
            "isTradingDay": trading, "startTime": now.replace(hour=7).isoformat(),
            "endTime": now.replace(hour=16).isoformat()}]}]}}


def day(value):
    return value["data"]["exchanges"][0]["days"][0]


def observe(value, now=NOW):
    return polling_state(value, ("MOEX",), now=now)


def test_explicit_broker_sunday_opens_only_read_only_polling():
    result = observe(calendar())
    assert result["state"] == "scheduled_window"
    assert result["regular_price_polling_allowed"] is True
    assert result["main_session_verified"] is result["trade_permission"] is False
    assert result["display_timezone"] == "Europe/Moscow"


def test_broker_holiday_overrides_an_ordinary_weekday():
    monday = NOW + timedelta(days=1)
    result = observe(calendar(now=monday, trading=False), monday)
    assert result["state"] == "closed" and result["regular_price_polling_allowed"] is False


@pytest.mark.parametrize("hour, allowed", [(6, False), (7, True), (15, True), (16, False), (17, False)])
def test_half_open_session_boundaries(hour, allowed):
    now = NOW.replace(hour=hour)
    result = observe(calendar(now=now), now)
    assert result["regular_price_polling_allowed"] is allowed


@pytest.mark.parametrize("start,end,expected", [
    ("openingAuctionStartTime", "openingAuctionEndTime", "opening_auction"),
    ("closingAuctionStartTime", "closingAuctionEndTime", "closing_auction"),
    ("clearingStartTime", "clearingEndTime", "clearing"),
    ("premarketStartTime", "premarketEndTime", "premarket"),
    ("eveningStartTime", "eveningEndTime", "evening"),
])
def test_known_auction_clearing_and_extra_windows_suspend_polling(start, end, expected):
    value = calendar()
    day(value).update({start: (NOW - timedelta(minutes=1)).isoformat(), end: (NOW + timedelta(minutes=1)).isoformat()})
    result = observe(value)
    assert result["state"] == expected and result["regular_price_polling_allowed"] is False
    assert result["next_transition_at"] == (NOW + timedelta(minutes=1)).isoformat()


@pytest.mark.parametrize("age", [900, 901, -1, 86400])
def test_stale_or_future_calendar_cannot_open_polling(age):
    value = calendar()
    value["data"]["as_of"] = (NOW - timedelta(seconds=age)).isoformat()
    assert observe(value)["reason"] == "calendar_stale_or_future"


@pytest.mark.parametrize("mutation", [
    "naive", "string_bool", "missing_end", "reversed", "duplicate_day", "duplicate_exchange",
    "missing_today", "partial_clearing", "bad_interval", "missing_exchange", "wrong_timezone",
])
def test_missing_malformed_or_conflicting_evidence_stays_unknown(mutation):
    value = calendar()
    if mutation == "naive":
        day(value)["startTime"] = "2026-10-25T07:00:00"
    elif mutation == "string_bool":
        day(value)["isTradingDay"] = "false"
    elif mutation == "missing_end":
        day(value).pop("endTime")
    elif mutation == "reversed":
        day(value)["endTime"] = day(value)["startTime"]
    elif mutation == "duplicate_day":
        value["data"]["exchanges"][0]["days"].append(deepcopy(day(value)))
    elif mutation == "duplicate_exchange":
        value["data"]["exchanges"].append(deepcopy(value["data"]["exchanges"][0]))
    elif mutation == "missing_today":
        day(value)["date"] = "2026-10-26T00:00:00Z"
        day(value)["startTime"] = "2026-10-26T07:00:00Z"
        day(value)["endTime"] = "2026-10-26T16:00:00Z"
    elif mutation == "partial_clearing":
        day(value)["clearingStartTime"] = NOW.isoformat()
    elif mutation == "bad_interval":
        day(value)["intervals"] = [{"type": "unspecified", "interval": {"startTs": NOW.isoformat()}}]
    elif mutation == "missing_exchange":
        value["data"]["exchanges"][0]["exchange"] = "another-venue"
    elif mutation == "wrong_timezone":
        value["data"]["timezone"] = "Europe/Moscow"
    result = observe(value)
    assert result["state"] == "unknown" and result["regular_price_polling_allowed"] is False
    assert result["trade_permission"] is False


def test_free_form_interval_is_not_relabelled_as_main_session():
    value = calendar()
    day(value)["intervals"] = [{"type": "MAIN_OR_OTHER_UNDOCUMENTED_NAME", "interval": {
        "startTs": day(value)["startTime"], "endTs": day(value)["endTime"]}}]
    result = observe(value)
    assert result["interval_classification"] == "unclassified"
    assert result["main_session_verified"] is result["trade_permission"] is False
    day(value).pop("startTime")
    day(value).pop("endTime")
    assert observe(value)["regular_price_polling_allowed"] is False


def test_previous_utc_day_window_crosses_midnight_without_guessing_a_weekday():
    now = NOW.replace(hour=0, minute=30)
    value = calendar(now=now, trading=False)
    previous = {"date": "2026-10-24T00:00:00Z", "isTradingDay": True,
                "startTime": "2026-10-24T23:00:00Z", "endTime": "2026-10-25T01:00:00Z"}
    value["data"]["exchanges"][0]["days"].insert(0, previous)
    result = observe(value, now)
    assert result["regular_price_polling_allowed"] is True
    assert result["next_transition_at"] == "2026-10-25T01:00:00+00:00"


def test_overlapping_day_windows_are_not_silently_chosen():
    value = calendar()
    value["data"]["exchanges"][0]["days"].append({"date": "2026-10-24T00:00:00Z", "isTradingDay": True,
        "startTime": "2026-10-24T23:00:00Z", "endTime": "2026-10-25T11:00:00Z"})
    assert observe(value)["state"] == "unknown"


def test_every_required_section_must_be_present_and_in_its_window():
    value = calendar()
    other = deepcopy(value["data"]["exchanges"][0])
    other.update(exchange="MOEX-other")
    other["days"][0]["isTradingDay"] = False
    value["data"]["exchanges"].append(other)
    result = polling_state(value, ("MOEX", "MOEX-other"), now=NOW)
    assert result["state"] == "mixed" and result["regular_price_polling_allowed"] is False


@pytest.mark.parametrize("metadata", [None, {}, {"exchange": []}, {"exchange": ""}])
def test_unknown_instrument_exchange_has_no_substituted_venue(metadata):
    assert required_exchanges({"positions": [{"instrument_type": "share", "metadata": metadata}]}) == ()


def test_cash_only_bootstrap_uses_moex_but_requires_actual_schedule():
    assert required_exchanges({"positions": [{"instrument_type": "cash"}]}) == ("MOEX",)
    assert polling_state(None, ("MOEX",), now=NOW)["regular_price_polling_allowed"] is False


def test_naive_dispatch_clock_is_rejected():
    with pytest.raises(ValueError, match="aware_calendar_clock_required"):
        observe(calendar(), NOW.replace(tzinfo=None))
