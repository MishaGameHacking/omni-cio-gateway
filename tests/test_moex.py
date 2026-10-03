from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

import pytest

from omnicio.moex import MoexError, MoexIssClient


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_bond_snapshot_uses_official_iss_fields_and_conservative_ytw() -> None:
    response = FakeResponse(
        {
            "securities": {
                "columns": [
                    "SECID",
                    "BOARDID",
                    "MATDATE",
                    "ACCRUEDINT",
                    "DURATION",
                    "CALLOPTIONYIELD",
                    "CALLOPTIONDURATION",
                ],
                "data": [
                    [
                        "RU000A000001",
                        "TQCB",
                        "2028-10-03",
                        17.25,
                        720.0,
                        11.8,
                        640.0,
                    ]
                ],
            },
            "marketdata": {
                "columns": [
                    "SECID",
                    "BOARDID",
                    "YIELD",
                    "YIELDTOOFFER",
                    "OFFERDATE",
                    "VALTODAY",
                    "VOLTODAY",
                ],
                "data": [
                    [
                        "RU000A000001",
                        "TQCB",
                        13.4,
                        12.2,
                        "2027-10-03",
                        15_000_000.0,
                        14_500.0,
                    ]
                ],
            },
        }
    )

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        snapshot = MoexIssClient().bond_snapshot("ru000a000001", "tqcb")

    assert snapshot is not None
    assert snapshot.secid == "RU000A000001"
    assert snapshot.board_id == "TQCB"
    assert snapshot.yield_percent == Decimal("13.4")
    assert snapshot.yield_to_offer_percent == Decimal("12.2")
    assert snapshot.call_option_yield_percent == Decimal("11.8")
    assert snapshot.ytw_percent == Decimal("11.8")
    assert snapshot.duration_days == Decimal("720.0")
    assert snapshot.call_option_duration_days == Decimal("640.0")
    assert snapshot.accrued_interest_rub == Decimal("17.25")
    assert snapshot.value_today_rub == Decimal("15000000.0")
    assert snapshot.volume_today == Decimal("14500.0")
    request = urlopen.call_args.args[0]
    assert request.full_url.startswith(
        "https://iss.moex.com/iss/engines/stock/markets/bonds/boards/"
        "TQCB/securities/RU000A000001.json?"
    )
    assert "YIELDTOOFFER" in request.full_url
    assert "CALLOPTIONDURATION" in request.full_url


def test_bond_snapshot_returns_none_when_iss_has_no_security() -> None:
    response = FakeResponse(
        {
            "securities": {"columns": ["SECID"], "data": []},
            "marketdata": {"columns": ["SECID"], "data": []},
        }
    )
    with patch("urllib.request.urlopen", return_value=response):
        assert MoexIssClient().bond_snapshot("RU000A000001", "TQCB") is None


def test_bond_snapshot_rejects_mismatched_security() -> None:
    response = FakeResponse(
        {
            "securities": {
                "columns": ["SECID", "BOARDID"],
                "data": [["OTHER", "TQCB"]],
            },
            "marketdata": {"columns": ["SECID"], "data": []},
        }
    )
    with patch("urllib.request.urlopen", return_value=response):
        with pytest.raises(MoexError, match="different security"):
            MoexIssClient().bond_snapshot("RU000A000001", "TQCB")


@pytest.mark.parametrize("value", ["", "bad/value", " "])
def test_iss_identifiers_are_validated_before_network(value: str) -> None:
    with patch("urllib.request.urlopen") as urlopen:
        with pytest.raises(ValueError):
            MoexIssClient().bond_snapshot(value, "TQCB")
    urlopen.assert_not_called()
