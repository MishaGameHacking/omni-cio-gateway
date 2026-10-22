"""Date inputs must be rejected before arithmetic, job creation or broker calls."""
from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
import pytest

from backend.tests.test_volume_workspace import fixture
from backend import portfolio_details as details, volume_jobs as jobs, volume_market as market
from backend.volume_contract import date_range


@pytest.mark.parametrize("end", [date.min, date(1, 1, 30), date(1969, 12, 31), date.max])
def test_out_of_bounds_end_is_a_validation_error_without_start(end):
    with pytest.raises(HTTPException) as error:
        date_range(None, end)
    assert error.value.status_code == 422
    assert error.value.detail == "invalid_date_range"


def test_valid_explicit_lower_boundary_is_preserved():
    begin, finish = date_range(date(1970, 1, 1), date(1970, 1, 1))
    assert begin == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert finish == datetime(1970, 1, 2, tzinfo=timezone.utc)


def test_valid_omitted_start_keeps_the_requested_lookback():
    begin, finish = date_range(None, date(2000, 2, 1))
    assert begin == datetime(2000, 1, 2, tzinfo=timezone.utc)
    assert finish == datetime(2000, 2, 2, tzinfo=timezone.utc)


def test_refresh_rejects_early_end_without_creating_a_job(fixture):
    with patch.object(jobs, "enqueue") as enqueue:
        response = fixture["client"].post(
            "/workspace/refresh", json={"request_id": "early-date-fixture", "end": "0001-01-01"}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_date_range"}
    enqueue.assert_not_called()


def test_candles_reject_early_end_before_broker_access(fixture):
    with patch.object(market, "instrument") as instrument, patch.object(details, "BrokerReader") as reader:
        response = fixture["client"].get(
            "/workspace/instruments/date-range-fixture/candles", params={"end": "0001-01-01"}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_date_range"}
    instrument.assert_not_called()
    reader.assert_not_called()
