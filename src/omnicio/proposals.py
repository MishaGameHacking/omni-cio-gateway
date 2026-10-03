"""R5 immutable proposal construction and API serialization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from .portfolio_store import (
    PortfolioProposalActionRecord,
    PortfolioProposalRecord,
)

PROPOSAL_TTL = timedelta(minutes=10)
ProposalScenarioKind = Literal["deploy_cash", "replace"]


class ProposalBuildError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ProposalDraft:
    source_snapshot_id: UUID
    profile_version: int
    policy_version: int
    scenario_kind: ProposalScenarioKind
    target_instrument_uid: str | None
    replaced_instrument_uid: str | None
    payload: dict[str, object]
    proposal_hash: bytes
    expires_at: datetime


def build_proposal_draft(
    balancing: dict[str, object],
    *,
    scenario_kind: ProposalScenarioKind,
    replaced_instrument_uid: str | None,
    now: datetime | None = None,
) -> ProposalDraft:
    created_at = (now or datetime.now(UTC)).astimezone(UTC)
    if balancing.get("status") != "observed":
        raise ProposalBuildError("balancing_not_observed")
    if balancing.get("live_status") != "received":
        raise ProposalBuildError("live_evidence_not_received")
    if balancing.get("execution_enabled") is not False:
        raise ProposalBuildError("execution_boundary_invalid")
    if balancing.get("proposal_enabled") is not False:
        raise ProposalBuildError("r4_proposal_boundary_invalid")

    snapshot_raw = str(balancing.get("snapshot_id") or "")
    try:
        snapshot_id = UUID(snapshot_raw)
    except ValueError as exc:
        raise ProposalBuildError("snapshot_id_invalid") from exc
    profile_version = _positive_int(
        balancing.get("profile_version"),
        "profile_version_invalid",
    )
    policy_version = _positive_int(
        balancing.get("policy_version"),
        "policy_version_invalid",
    )

    scenarios = balancing.get("scenarios")
    if not isinstance(scenarios, dict):
        raise ProposalBuildError("scenario_set_missing")
    scenario = _select_scenario(
        cast(dict[str, object], scenarios),
        scenario_kind=scenario_kind,
        replaced_instrument_uid=replaced_instrument_uid,
    )
    if scenario.get("status") != "feasible":
        raise ProposalBuildError("scenario_not_feasible")
    trades = scenario.get("trades")
    if not isinstance(trades, list) or not trades:
        raise ProposalBuildError("scenario_has_no_trades")
    for trade in trades:
        if not isinstance(trade, dict):
            raise ProposalBuildError("scenario_trade_invalid")
        if trade.get("action") not in {"buy", "sell"}:
            raise ProposalBuildError("scenario_trade_invalid")
        if int(trade.get("lots") or 0) <= 0:
            raise ProposalBuildError("scenario_trade_invalid")

    target_uid = _optional_uid(scenario.get("target_instrument_uid"))
    replaced_uid = _optional_uid(scenario.get("replaced_instrument_uid"))
    if scenario_kind == "deploy_cash" and replaced_uid is not None:
        raise ProposalBuildError("scenario_shape_invalid")
    if scenario_kind == "replace":
        requested = _optional_uid(replaced_instrument_uid)
        if requested is None or replaced_uid != requested:
            raise ProposalBuildError("replacement_selection_changed")
        if target_uid is None:
            raise ProposalBuildError("scenario_shape_invalid")

    expires_at = created_at + PROPOSAL_TTL
    payload: dict[str, object] = {
        "schema": "omnicio.portfolio.proposal.v1",
        "stage": "r5_proposal",
        "source": {
            "snapshot_id": str(snapshot_id),
            "profile_version": profile_version,
            "policy_version": policy_version,
            "captured_at": balancing.get("captured_at"),
            "snapshot_age_seconds": balancing.get("snapshot_age_seconds"),
            "live_status": balancing.get("live_status"),
        },
        "scenario_kind": scenario_kind,
        "scenario": scenario,
        "evidence_sources": balancing.get("live_sources") or [],
        "methodology": balancing.get("methodology") or {},
        "created_at": created_at,
        "expires_at": expires_at,
        "execution_enabled": False,
    }
    normalized = cast(dict[str, object], _normalize(payload))
    proposal_hash = hashlib.sha256(
        _canonical_json(normalized).encode("utf-8"),
        usedforsecurity=False,
    ).digest()
    return ProposalDraft(
        source_snapshot_id=snapshot_id,
        profile_version=profile_version,
        policy_version=policy_version,
        scenario_kind=scenario_kind,
        target_instrument_uid=target_uid,
        replaced_instrument_uid=replaced_uid,
        payload=normalized,
        proposal_hash=proposal_hash,
        expires_at=expires_at,
    )


def proposal_payload(record: PortfolioProposalRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
        "version": record.version,
        "hash": record.proposal_hash.hex(),
        "source_snapshot_id": str(record.source_snapshot_id),
        "profile_version": record.profile_version,
        "policy_version": record.policy_version,
        "scenario_kind": record.scenario_kind,
        "target_instrument_uid": record.target_instrument_uid,
        "replaced_instrument_uid": record.replaced_instrument_uid,
        "payload": record.payload,
        "created_at": record.created_at,
        "expires_at": record.expires_at,
        "status": record.status,
        "decision_reason": record.decision_reason,
        "decided_at": record.decided_at,
        "execution_enabled": False,
    }


def proposal_action_payload(
    proposal: PortfolioProposalRecord,
    action: PortfolioProposalActionRecord,
) -> dict[str, object]:
    return {
        "proposal": {
            **proposal_payload(proposal),
            "status": action.action,
            "decision_reason": action.reason,
            "decided_at": action.acted_at,
        },
        "decision": {
            "action": action.action,
            "reason": action.reason,
            "acted_at": action.acted_at,
        },
        "execution_enabled": False,
    }


def parse_proposal_hash(value: str) -> bytes:
    clean = value.strip().lower()
    if len(clean) != 64:
        raise ValueError("proposal hash must contain 64 hexadecimal characters")
    try:
        parsed = bytes.fromhex(clean)
    except ValueError as exc:
        raise ValueError(
            "proposal hash must contain 64 hexadecimal characters"
        ) from exc
    if len(parsed) != 32:
        raise ValueError("proposal hash must be SHA-256")
    return parsed


def _select_scenario(
    scenarios: dict[str, object],
    *,
    scenario_kind: ProposalScenarioKind,
    replaced_instrument_uid: str | None,
) -> dict[str, object]:
    if scenario_kind == "deploy_cash":
        raw = scenarios.get("deploy_cash")
        if not isinstance(raw, dict):
            raise ProposalBuildError("scenario_not_found")
        return dict(cast(dict[str, object], raw))

    requested = _optional_uid(replaced_instrument_uid)
    if requested is None:
        raise ProposalBuildError("replacement_selection_required")
    replacements = scenarios.get("replacements")
    if not isinstance(replacements, list):
        raise ProposalBuildError("scenario_not_found")
    matches = [
        dict(cast(dict[str, object], item))
        for item in replacements
        if isinstance(item, dict)
        and str(item.get("replaced_instrument_uid") or "") == requested
    ]
    if len(matches) != 1:
        raise ProposalBuildError("scenario_not_found")
    return matches[0]


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool):
        raise ProposalBuildError(code)
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ProposalBuildError(code) from exc
    if parsed <= 0:
        raise ProposalBuildError(code)
    return parsed


def _optional_uid(value: object) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    if len(clean) > 128:
        raise ProposalBuildError("instrument_uid_invalid")
    return clean


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _normalize(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _normalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported proposal value: {type(value).__name__}")
