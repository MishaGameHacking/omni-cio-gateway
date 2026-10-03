from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from omnicio.moex import MoexError, MoexIssClient


class FakeResponse:
    def __init__(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class FakeConnection:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    def close(self) -> None:
        return None

    def request(
        self,
        method: str,
        target: str,
        *,
        headers: dict[str, str],
    ) -> None:
        self.requests.append((method, target, headers))

    def getresponse(self) -> FakeResponse:
        return self.response


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

    connection = FakeConnection(response)
    with patch("http.client.HTTPSConnection", return_value=connection) as client:
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
    client.assert_called_once()
    method, target, headers = connection.requests[0]
    assert method == "GET"
    assert target.startswith(
        "/iss/engines/stock/markets/bonds/boards/"
        "TQCB/securities/RU000A000001.json?"
    )
    assert "YIELDTOOFFER" in target
    assert "CALLOPTIONDURATION" in target
    assert headers["Accept"] == "application/json"


def test_security_identity_matches_exact_isin_and_exposes_official_issuer() -> None:
    response = FakeResponse(
        {
            "securities": {
                "columns": [
                    "secid",
                    "isin",
                    "is_traded",
                    "emitent_id",
                    "emitent_title",
                    "emitent_inn",
                    "primary_boardid",
                ],
                "data": [
                    [
                        "TESTBOND",
                        "RU000A000001",
                        1,
                        1234,
                        "Тестовый эмитент",
                        "7700000000",
                        "TQCB",
                    ],
                    [
                        "OTHER",
                        "RU000A000002",
                        1,
                        9999,
                        "Другой эмитент",
                        "7800000000",
                        "TQCB",
                    ],
                ],
            }
        }
    )
    connection = FakeConnection(response)
    with patch("http.client.HTTPSConnection", return_value=connection):
        identity = MoexIssClient().security_identity(
            "RU000A000001",
            expected_isin="RU000A000001",
        )

    assert identity is not None
    assert identity.secid == "TESTBOND"
    assert identity.isin == "RU000A000001"
    assert identity.issuer_id == "1234"
    assert identity.issuer_inn == "7700000000"
    assert identity.primary_board_id == "TQCB"
    assert identity.is_traded is True
    assert "/iss/securities.json?" in connection.requests[0][1]


def test_security_identity_does_not_accept_near_isin_match() -> None:
    response = FakeResponse(
        {
            "securities": {
                "columns": [
                    "secid",
                    "isin",
                    "is_traded",
                    "emitent_id",
                    "emitent_title",
                    "emitent_inn",
                    "primary_boardid",
                ],
                "data": [
                    ["OTHER", "RU000A000002", 1, 9999, "Other", "7800000000", "TQCB"]
                ],
            }
        }
    )
    connection = FakeConnection(response)
    with patch("http.client.HTTPSConnection", return_value=connection):
        assert (
            MoexIssClient().security_identity(
                "RU000A000001",
                expected_isin="RU000A000001",
            )
            is None
        )


def test_bond_liquidity_averages_history_value_without_hidden_participation() -> None:
    response = FakeResponse(
        {
            "history": {
                "columns": ["TRADEDATE", "SECID", "BOARDID", "VALUE"],
                "data": [
                    ["2026-10-01", "RU000A000001", "TQCB", 1_000_000],
                    ["2026-10-02", "RU000A000001", "TQCB", 3_000_000],
                ],
            }
        }
    )
    connection = FakeConnection(response)
    with patch("http.client.HTTPSConnection", return_value=connection):
        snapshot = MoexIssClient().bond_liquidity(
            "RU000A000001",
            "TQCB",
            from_date=date(2026, 9, 1),
            till_date=date(2026, 10, 2),
        )

    assert snapshot is not None
    assert snapshot.observed_days == 2
    assert snapshot.total_value_rub == Decimal("4000000")
    assert snapshot.average_daily_value_rub == Decimal("2000000")
    target = connection.requests[0][1]
    assert "/history/engines/stock/markets/bonds/boards/" in target
    assert "VALUE" in target


def test_bond_liquidity_requires_ordered_window() -> None:
    with (
        patch("http.client.HTTPSConnection") as client,
        pytest.raises(ValueError, match="window"),
    ):
        MoexIssClient().bond_liquidity(
                "RU000A000001",
                "TQCB",
                from_date=date(2026, 10, 3),
                till_date=date(2026, 10, 2),
            )
    client.assert_not_called()


def test_bond_snapshot_returns_none_when_iss_has_no_security() -> None:
    response = FakeResponse(
        {
            "securities": {"columns": ["SECID"], "data": []},
            "marketdata": {"columns": ["SECID"], "data": []},
        }
    )
    connection = FakeConnection(response)
    with patch("http.client.HTTPSConnection", return_value=connection):
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
    with (
        patch(
            "http.client.HTTPSConnection",
            return_value=FakeConnection(response),
        ),
        pytest.raises(MoexError, match="different security"),
    ):
        MoexIssClient().bond_snapshot("RU000A000001", "TQCB")


@pytest.mark.parametrize("value", ["", "bad/value", " "])
def test_iss_identifiers_are_validated_before_network(value: str) -> None:
    with (
        patch("http.client.HTTPSConnection") as client,
        pytest.raises(ValueError),
    ):
        MoexIssClient().bond_snapshot(value, "TQCB")
    client.assert_not_called()



def test_moex_fetch_rejects_off_origin_url_before_network() -> None:
    with (
        patch("http.client.HTTPSConnection") as client,
        pytest.raises(MoexError, match="fixed provider origin"),
    ):
        MoexIssClient()._get_payload(
            "https://evil.example/iss/securities.json?q=RU000A000001"
        )
    client.assert_not_called()


def test_moex_fetch_rejects_non_success_http_status() -> None:
    connection = FakeConnection(FakeResponse({}, status=302))
    with (
        patch("http.client.HTTPSConnection", return_value=connection),
        pytest.raises(MoexError, match="HTTP 302"),
    ):
        MoexIssClient().security_identity(
            "RU000A000001",
            expected_isin="RU000A000001",
        )
