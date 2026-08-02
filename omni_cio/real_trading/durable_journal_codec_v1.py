from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from typing import Any, cast

from .models_v1 import ProposalState, RealTradeProposalV1


VALID_STATES = frozenset(
    {"prepared", "submitting", "submitted", "failed", "unknown", "expired"}
)
COUNTED_STATES = frozenset({"submitting", "submitted", "unknown"})


class JournalIntegrityError(RuntimeError):
    pass


class JournalStorageError(RuntimeError):
    pass


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _aware_datetime(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise JournalIntegrityError(f"invalid datetime: {field}") from exc
    if parsed.tzinfo is None:
        raise JournalIntegrityError(f"naive datetime: {field}")
    return parsed


def _optional_datetime(value: Any, field: str) -> datetime | None:
    return None if value is None else _aware_datetime(value, field)


def encode_proposal(proposal: RealTradeProposalV1) -> str:
    payload = {
        "proposal_id": proposal.proposal_id,
        "order_id": proposal.order_id,
        "account_id": proposal.account_id,
        "instrument_uid": proposal.instrument_uid,
        "ticker": proposal.ticker,
        "isin": proposal.isin,
        "direction": proposal.direction,
        "quantity_lots": proposal.quantity_lots,
        "limit_price": format(proposal.limit_price, "f"),
        "rationale": proposal.rationale,
        "preview_total_rub": format(proposal.preview_total_rub, "f"),
        "preview_commission_rub": format(proposal.preview_commission_rub, "f"),
        "available_lots": proposal.available_lots,
        "market_retrieved_at": _iso(proposal.market_retrieved_at),
        "created_at": _iso(proposal.created_at),
        "expires_at": _iso(proposal.expires_at),
        "confirmation_code": proposal.confirmation_code,
        "state": proposal.state,
        "submitted_at": _iso(proposal.submitted_at),
        "confirmation_evidence_hash": proposal.confirmation_evidence_hash,
        "broker_response_json": proposal.broker_response_json,
        "failure_code": proposal.failure_code,
        "failure_message": proposal.failure_message,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_proposal(raw: str) -> RealTradeProposalV1:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("payload must be an object")
        state = str(data["state"])
        direction = str(data["direction"])
        proposal = RealTradeProposalV1(
            proposal_id=str(data["proposal_id"]),
            order_id=str(data["order_id"]),
            account_id=str(data["account_id"]),
            instrument_uid=str(data["instrument_uid"]),
            ticker=str(data["ticker"]),
            isin=None if data.get("isin") is None else str(data["isin"]),
            direction=cast(Any, direction),
            quantity_lots=int(data["quantity_lots"]),
            limit_price=Decimal(str(data["limit_price"])),
            rationale=str(data["rationale"]),
            preview_total_rub=Decimal(str(data["preview_total_rub"])),
            preview_commission_rub=Decimal(str(data["preview_commission_rub"])),
            available_lots=int(data["available_lots"]),
            market_retrieved_at=_aware_datetime(
                data["market_retrieved_at"], "market_retrieved_at"
            ),
            created_at=_aware_datetime(data["created_at"], "created_at"),
            expires_at=_aware_datetime(data["expires_at"], "expires_at"),
            confirmation_code=str(data["confirmation_code"]),
            state=cast(ProposalState, state),
            submitted_at=_optional_datetime(data.get("submitted_at"), "submitted_at"),
            confirmation_evidence_hash=(
                None
                if data.get("confirmation_evidence_hash") is None
                else str(data["confirmation_evidence_hash"])
            ),
            broker_response_json=(
                None
                if data.get("broker_response_json") is None
                else str(data["broker_response_json"])
            ),
            failure_code=(
                None if data.get("failure_code") is None else str(data["failure_code"])
            ),
            failure_message=(
                None
                if data.get("failure_message") is None
                else str(data["failure_message"])
            ),
        )
    except (ArithmeticError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise JournalIntegrityError("invalid durable proposal payload") from exc
    if proposal.state not in VALID_STATES or proposal.direction not in {"BUY", "SELL"}:
        raise JournalIntegrityError("invalid durable proposal state or direction")
    if proposal.quantity_lots < 1 or proposal.limit_price <= 0:
        raise JournalIntegrityError("invalid durable proposal quantity or price")
    if proposal.preview_total_rub <= 0 or proposal.preview_commission_rub < 0:
        raise JournalIntegrityError("invalid durable proposal preview")
    return proposal
