from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


# Absolute code ceilings for the first real-money release. Render-configured
# limits must be <= these values and are expected to be much lower during owner
# acceptance. Raising these ceilings requires a new reviewed code release.
REAL_V1_ABSOLUTE_MAX_ORDER_RUB = Decimal("100000")
REAL_V1_ABSOLUTE_MAX_DAILY_RUB = Decimal("300000")


ProposalState = Literal[
    "prepared",
    "submitting",
    "submitted",
    "failed",
    "unknown",
    "expired",
]


@dataclass(frozen=True, slots=True)
class RealTradingPolicyV1:
    max_order_rub: Decimal
    max_daily_rub: Decimal
    confirmation_ttl_seconds: int
    market_max_age_seconds: int
    allowed_instrument_types: frozenset[str] = frozenset({"share", "etf"})

    def validate(self) -> None:
        if not self.max_order_rub.is_finite() or self.max_order_rub <= 0:
            raise ValueError("max_order_rub must be a positive finite Decimal")
        if not self.max_daily_rub.is_finite() or self.max_daily_rub <= 0:
            raise ValueError("max_daily_rub must be a positive finite Decimal")
        if self.max_daily_rub < self.max_order_rub:
            raise ValueError("max_daily_rub must be >= max_order_rub")
        if self.max_order_rub > REAL_V1_ABSOLUTE_MAX_ORDER_RUB:
            raise ValueError("max_order_rub exceeds the v1 absolute code ceiling")
        if self.max_daily_rub > REAL_V1_ABSOLUTE_MAX_DAILY_RUB:
            raise ValueError("max_daily_rub exceeds the v1 absolute code ceiling")
        if not 30 <= self.confirmation_ttl_seconds <= 600:
            raise ValueError("confirmation TTL must be between 30 and 600 seconds")
        if not 1 <= self.market_max_age_seconds <= 60:
            raise ValueError("market_max_age_seconds must be between 1 and 60")
        if not self.allowed_instrument_types:
            raise ValueError("allowed_instrument_types must not be empty")


@dataclass(frozen=True, slots=True)
class RealMarketContextV1:
    instrument_uid: str
    ticker: str
    isin: str | None
    instrument_type: str
    lot: int
    currency: str
    min_price_increment: Decimal
    api_trade_available: bool
    limit_orders_available: bool
    trading_status: str
    retrieved_at: datetime
    complete: bool


@dataclass(frozen=True, slots=True)
class RealTradeProposalV1:
    proposal_id: str
    order_id: str
    account_id: str
    instrument_uid: str
    ticker: str
    isin: str | None
    direction: Literal["BUY", "SELL"]
    quantity_lots: int
    limit_price: Decimal
    rationale: str
    preview_total_rub: Decimal
    preview_commission_rub: Decimal
    available_lots: int
    market_retrieved_at: datetime
    created_at: datetime
    expires_at: datetime
    confirmation_code: str
    state: ProposalState = "prepared"
    submitted_at: datetime | None = None
    confirmation_evidence_hash: str | None = None
    broker_response_json: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None

    @property
    def confirmation_phrase(self) -> str:
        return f"ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ {self.confirmation_code}"
