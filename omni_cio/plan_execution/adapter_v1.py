from __future__ import annotations

from datetime import datetime
from typing import Protocol

from omni_cio.real_trading.journal_v1 import RealExecutionJournalV1
from omni_cio.real_trading.models_v1 import RealTradeProposalV1
from omni_cio.real_trading.service_v1 import RealTradingServiceV1


class SingleOrderExecutionPrimitiveV1(Protocol):
    def prepare_trade(
        self,
        *,
        instrument_uid: str,
        direction: str,
        quantity_lots: int,
        limit_price: str,
        rationale: str,
        now: datetime | None = None,
    ) -> RealTradeProposalV1: ...

    def execute_trade(
        self,
        proposal_id: str,
        confirmation_phrase: str,
        *,
        now: datetime | None = None,
    ) -> tuple[RealTradeProposalV1, bool]: ...

    def reconcile_proposal(self, proposal_id: str) -> RealTradeProposalV1: ...

    def get_proposal(self, proposal_id: str) -> RealTradeProposalV1: ...


class RealTradingPlanAdapterV1:
    """Thin adapter over the already accepted v8.6.1 single-order lifecycle.

    WP12 deliberately owns no direct broker submit implementation. Every real
    order remains a normal RealTradingServiceV1 proposal with its durable
    idempotency journal, repeated preflight and broker reconciliation gates.
    """

    def __init__(
        self,
        *,
        service: RealTradingServiceV1,
        journal: RealExecutionJournalV1,
    ) -> None:
        self._service = service
        self._journal = journal

    def prepare_trade(
        self,
        *,
        instrument_uid: str,
        direction: str,
        quantity_lots: int,
        limit_price: str,
        rationale: str,
        now: datetime | None = None,
    ) -> RealTradeProposalV1:
        return self._service.prepare_trade(
            instrument_uid=instrument_uid,
            direction=direction,
            quantity_lots=quantity_lots,
            limit_price=limit_price,
            rationale=rationale,
            now=now,
        )

    def execute_trade(
        self,
        proposal_id: str,
        confirmation_phrase: str,
        *,
        now: datetime | None = None,
    ) -> tuple[RealTradeProposalV1, bool]:
        return self._service.execute_trade(
            proposal_id,
            confirmation_phrase,
            now=now,
        )

    def reconcile_proposal(self, proposal_id: str) -> RealTradeProposalV1:
        return self._service.reconcile_proposal(proposal_id)

    def get_proposal(self, proposal_id: str) -> RealTradeProposalV1:
        return self._journal.get(proposal_id)
