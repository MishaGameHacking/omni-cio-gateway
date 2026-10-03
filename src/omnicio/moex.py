"""MOEX ISS evidence contracts with fail-closed runtime transport.

R4 keeps the public data contract explicit, but the direct HTTP transport is
intentionally disabled until the repository security gate can certify it.
The balancing service treats this as missing evidence and never as permission
to trade or to infer a positive investment state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MOEX_ISS_REFERENCE = "https://www.moex.com/a2920"
MOEX_RUNTIME_BLOCK_REASON = "moex_runtime_transport_security_gate"


class MoexError(RuntimeError):
    """MOEX ISS evidence is unavailable or cannot be used safely."""


@dataclass(frozen=True, slots=True)
class MoexSecurityIdentity:
    secid: str
    isin: str
    issuer_id: str
    issuer_name: str
    issuer_inn: str
    primary_board_id: str
    is_traded: bool
    source_url: str


@dataclass(frozen=True, slots=True)
class MoexBondSnapshot:
    secid: str
    board_id: str
    yield_percent: Decimal | None
    yield_to_offer_percent: Decimal | None
    call_option_yield_percent: Decimal | None
    ytw_percent: Decimal | None
    duration_days: Decimal | None
    call_option_duration_days: Decimal | None
    accrued_interest_rub: Decimal | None
    value_today_rub: Decimal | None
    volume_today: Decimal | None
    offer_date: str
    maturity_date: str
    source_url: str


@dataclass(frozen=True, slots=True)
class MoexLiquiditySnapshot:
    secid: str
    board_id: str
    observed_days: int
    average_daily_value_rub: Decimal
    total_value_rub: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class MoexIssClient:
    """Fail-closed placeholder for the suspended direct MOEX HTTP transport."""

    timeout_seconds: int = 10

    def security_identity(
        self,
        query: str,
        *,
        expected_isin: str = "",
    ) -> MoexSecurityIdentity | None:
        del query, expected_isin
        raise MoexError(MOEX_RUNTIME_BLOCK_REASON)

    def bond_liquidity(
        self,
        secid: str,
        board_id: str,
        *,
        from_date: date,
        till_date: date,
    ) -> MoexLiquiditySnapshot | None:
        del secid, board_id, from_date, till_date
        raise MoexError(MOEX_RUNTIME_BLOCK_REASON)

    def bond_snapshot(
        self,
        secid: str,
        board_id: str,
    ) -> MoexBondSnapshot | None:
        del secid, board_id
        raise MoexError(MOEX_RUNTIME_BLOCK_REASON)
