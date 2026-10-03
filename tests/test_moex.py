from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal

import pytest

import omnicio.moex as moex_module
from omnicio.moex import (
    MOEX_ISS_REFERENCE,
    MOEX_RUNTIME_BLOCK_REASON,
    MoexBondSnapshot,
    MoexError,
    MoexIssClient,
    MoexLiquiditySnapshot,
    MoexSecurityIdentity,
)


@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    (
        ("security_identity", ("RU000A000001",), {"expected_isin": "RU000A000001"}),
        (
            "bond_liquidity",
            ("RU000A000001", "TQCB"),
            {
                "from_date": date(2026, 9, 1),
                "till_date": date(2026, 10, 2),
            },
        ),
        ("bond_snapshot", ("RU000A000001", "TQCB"), {}),
    ),
)
def test_direct_moex_runtime_transport_fails_closed(
    method: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    client = MoexIssClient()

    with pytest.raises(MoexError, match=MOEX_RUNTIME_BLOCK_REASON):
        getattr(client, method)(*args, **kwargs)


def test_moex_runtime_module_contains_no_direct_network_transport() -> None:
    source = inspect.getsource(moex_module)

    for forbidden in (
        "http.client",
        "urllib.request",
        "socket.",
        "requests.",
        "httpx.",
        "urlopen(",
        "HTTPSConnection(",
    ):
        assert forbidden not in source


def test_moex_reference_is_official_https_source() -> None:
    assert MOEX_ISS_REFERENCE.startswith("https://www.moex.com/")


def test_moex_evidence_contracts_remain_available_for_verified_ingest() -> None:
    identity = MoexSecurityIdentity(
        secid="TESTBOND",
        isin="RU000A000001",
        issuer_id="1234",
        issuer_name="Issuer",
        issuer_inn="7700000000",
        primary_board_id="TQCB",
        is_traded=True,
        source_url="https://www.moex.com/a2920",
    )
    bond = MoexBondSnapshot(
        secid="TESTBOND",
        board_id="TQCB",
        yield_percent=Decimal("12"),
        yield_to_offer_percent=Decimal("11.5"),
        call_option_yield_percent=None,
        ytw_percent=Decimal("11.5"),
        duration_days=Decimal("700"),
        call_option_duration_days=None,
        accrued_interest_rub=Decimal("20"),
        value_today_rub=Decimal("1000000"),
        volume_today=Decimal("1000"),
        offer_date="",
        maturity_date="2027-10-03",
        source_url="https://www.moex.com/a2920",
    )
    liquidity = MoexLiquiditySnapshot(
        secid="TESTBOND",
        board_id="TQCB",
        observed_days=20,
        average_daily_value_rub=Decimal("1000000"),
        total_value_rub=Decimal("20000000"),
        source_url="https://www.moex.com/a2920",
    )

    assert identity.is_traded is True
    assert bond.ytw_percent == Decimal("11.5")
    assert liquidity.observed_days == 20
