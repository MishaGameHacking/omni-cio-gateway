"""R5 immutable proposal construction and API serialization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
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
    account_id: str
    profile_version: int
    policy_version: int
    scenario_kind: ProposalScenarioKind
    target_instrument_uid: str | None
    replaced_instrument_uid: str | None
    payload: dict[str, object]
    proposal_hash: bytes
    expires_at: datetime


def _validate_proposal_boundary(balancing: dict[str, object]) -> None:
    if balancing.get("status") != "observed":
        raise ProposalBuildError("balancing_not_observed")
    if balancing.get("live_status") != "received":
        raise ProposalBuildError("live_evidence_not_received")
    if balancing.get("execution_enabled") is not False:
        raise ProposalBuildError("execution_boundary_invalid")
    if balancing.get("proposal_enabled") is not False:
        raise ProposalBuildError("r4_proposal_boundary_invalid")


def _proposal_identity(
    balancing: dict[str, object],
) -> tuple[UUID, str, int, int]:
    snapshot_raw = str(balancing.get("snapshot_id") or "")
    try:
        snapshot_id = UUID(snapshot_raw)
    except ValueError as exc:
        raise ProposalBuildError("snapshot_id_invalid") from exc
    account_id = _required_text(
        balancing.get("account_id"),
        "account_id_invalid",
        max_length=128,
    )
    profile_version = _positive_int(
        balancing.get("profile_version"),
        "profile_version_invalid",
    )
    policy_version = _positive_int(
        balancing.get("policy_version"),
        "policy_version_invalid",
    )
    return snapshot_id, account_id, profile_version, policy_version


def _validated_scenario(
    balancing: dict[str, object],
    *,
    scenario_kind: ProposalScenarioKind,
    replaced_instrument_uid: str | None,
) -> tuple[dict[str, object], dict[str, object]]:
    scenarios_raw = balancing.get("scenarios")
    if not isinstance(scenarios_raw, dict):
        raise ProposalBuildError("scenario_set_missing")
    scenarios = cast(dict[str, object], scenarios_raw)
    scenario = _select_scenario(
        scenarios,
        scenario_kind=scenario_kind,
        replaced_instrument_uid=replaced_instrument_uid,
    )
    if scenario.get("status") != "feasible":
        raise ProposalBuildError("scenario_not_feasible")
    trades = scenario.get("trades")
    if not isinstance(trades, list) or not trades:
        raise ProposalBuildError("scenario_has_no_trades")
    for trade in trades:
        _validate_trade(trade)
    _validate_before_after(scenario.get("before_after"))
    return scenarios, scenario


def _validated_scenario_uids(
    scenario: dict[str, object],
    *,
    scenario_kind: ProposalScenarioKind,
    replaced_instrument_uid: str | None,
) -> tuple[str | None, str | None]:
    target_uid = _optional_uid(scenario.get("target_instrument_uid"))
    replaced_uid = _optional_uid(scenario.get("replaced_instrument_uid"))
    if scenario_kind == "deploy_cash":
        if replaced_uid is not None:
            raise ProposalBuildError("scenario_shape_invalid")
        return target_uid, replaced_uid

    requested = _optional_uid(replaced_instrument_uid)
    if requested is None or replaced_uid != requested:
        raise ProposalBuildError("replacement_selection_changed")
    if target_uid is None:
        raise ProposalBuildError("scenario_shape_invalid")
    return target_uid, replaced_uid


def build_proposal_draft(
    balancing: dict[str, object],
    *,
    scenario_kind: ProposalScenarioKind,
    replaced_instrument_uid: str | None,
    now: datetime | None = None,
) -> ProposalDraft:
    created_at = (now or datetime.now(UTC)).astimezone(UTC)
    _validate_proposal_boundary(balancing)
    snapshot_id, account_id, profile_version, policy_version = _proposal_identity(
        balancing
    )
    scenarios, scenario = _validated_scenario(
        balancing,
        scenario_kind=scenario_kind,
        replaced_instrument_uid=replaced_instrument_uid,
    )
    constraints = balancing.get("constraints")
    if not isinstance(constraints, dict) or not constraints:
        raise ProposalBuildError("proposal_constraints_missing")
    target_uid, replaced_uid = _validated_scenario_uids(
        scenario,
        scenario_kind=scenario_kind,
        replaced_instrument_uid=replaced_instrument_uid,
    )

    expires_at = created_at + PROPOSAL_TTL
    payload: dict[str, object] = {
        "schema": "omnicio.portfolio.proposal.v1",
        "stage": "r5_proposal",
        "source": {
            "snapshot_id": str(snapshot_id),
            "account_id": account_id,
            "profile_version": profile_version,
            "policy_version": policy_version,
            "captured_at": balancing.get("captured_at"),
            "snapshot_age_seconds": balancing.get("snapshot_age_seconds"),
            "live_status": balancing.get("live_status"),
        },
        "constraints": constraints,
        "scenario_kind": scenario_kind,
        "scenario": scenario,
        "alternatives": _alternative_summaries(
            scenarios,
            selected_kind=scenario_kind,
            selected_replaced_uid=replaced_uid,
        ),
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
        account_id=account_id,
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
        "account_id": record.account_id,
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
        "decision_user_reason": record.decision_user_reason,
        "deferred_until": record.deferred_until,
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
            "user_reason": action.user_reason,
            "deferred_until": action.deferred_until,
            "acted_at": action.acted_at,
        },
        "execution_enabled": False,
    }


def proposal_material_hash(payload: dict[str, object]) -> bytes:
    """Hash decision-relevant content while ignoring retrieval wall-clock noise."""
    evidence = payload.get("evidence_sources")
    material_sources: list[dict[str, object]] = []
    if isinstance(evidence, list):
        for raw in evidence:
            if not isinstance(raw, dict):
                continue
            evidence_source = cast(dict[str, object], raw)
            material_sources.append(
                {
                    key: evidence_source[key]
                    for key in sorted(evidence_source)
                    if key != "retrieved_at"
                }
            )
    material_sources.sort(
        key=lambda item: (
            str(item.get("id") or ""),
            str(item.get("provider") or ""),
            str(item.get("kind") or ""),
            str(item.get("url") or ""),
        )
    )
    source_raw = payload.get("source")
    source: dict[str, object] = {}
    if isinstance(source_raw, dict):
        source_data = cast(dict[str, object], source_raw)
        source = {
            key: source_data.get(key)
            for key in (
                "snapshot_id",
                "account_id",
                "profile_version",
                "policy_version",
                "captured_at",
                "live_status",
            )
        }
    material = {
        "schema": payload.get("schema"),
        "source": source,
        "constraints": payload.get("constraints"),
        "scenario_kind": payload.get("scenario_kind"),
        "scenario": payload.get("scenario"),
        "alternatives": payload.get("alternatives"),
        "evidence_sources": material_sources,
        "methodology": payload.get("methodology"),
        "execution_enabled": payload.get("execution_enabled"),
    }
    normalized = _normalize(material)
    return hashlib.sha256(
        _canonical_json(normalized).encode("utf-8"),
        usedforsecurity=False,
    ).digest()


def proposal_generated_at(record: PortfolioProposalRecord) -> datetime:
    raw = record.payload.get("created_at")
    if not isinstance(raw, str):
        raise ProposalBuildError("proposal_generated_at_invalid")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProposalBuildError("proposal_generated_at_invalid") from exc
    if value.tzinfo is None:
        raise ProposalBuildError("proposal_generated_at_invalid")
    return value.astimezone(UTC)


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


def _validate_trade(value: object) -> None:
    if not isinstance(value, dict):
        raise ProposalBuildError("scenario_trade_invalid")
    trade = cast(dict[str, object], value)
    action = trade.get("action")
    if action not in {"buy", "sell"}:
        raise ProposalBuildError("scenario_trade_invalid")
    _required_text(
        trade.get("instrument_uid"),
        "scenario_trade_invalid",
        max_length=128,
    )
    if _positive_int(trade.get("lots"), "scenario_trade_invalid") <= 0:
        raise ProposalBuildError("scenario_trade_invalid")
    _positive_decimal(trade.get("limit_price"), "scenario_limit_price_missing")
    if trade.get("limit_price_type") not in {"point", "currency"}:
        raise ProposalBuildError("scenario_limit_price_type_missing")
    if action == "buy":
        _positive_decimal(
            trade.get("max_spend_rub"),
            "scenario_max_spend_missing",
        )
        if trade.get("min_proceeds_rub") is not None:
            raise ProposalBuildError("scenario_trade_bounds_invalid")
    else:
        _positive_decimal(
            trade.get("min_proceeds_rub"),
            "scenario_min_proceeds_missing",
        )
        if trade.get("max_spend_rub") is not None:
            raise ProposalBuildError("scenario_trade_bounds_invalid")


def _validate_before_after(value: object) -> None:
    if not isinstance(value, dict):
        raise ProposalBuildError("scenario_before_after_missing")
    states = cast(dict[str, object], value)
    for name in ("before", "after"):
        raw = states.get(name)
        if not isinstance(raw, dict):
            raise ProposalBuildError("scenario_before_after_incomplete")
        state = cast(dict[str, object], raw)
        _nonnegative_decimal(
            state.get("nav_rub"),
            "scenario_before_after_incomplete",
        )
        _nonnegative_decimal(
            state.get("cash_rub"),
            "scenario_before_after_incomplete",
        )
        if not isinstance(state.get("positions"), list):
            raise ProposalBuildError("scenario_before_after_incomplete")
        exposures = state.get("exposures")
        if not isinstance(exposures, dict):
            raise ProposalBuildError("scenario_before_after_incomplete")
        exposure_map = cast(dict[str, object], exposures)
        for dimension in (
            "asset_class",
            "sector",
            "issuer_id",
            "group_id",
        ):
            if not isinstance(exposure_map.get(dimension), list):
                raise ProposalBuildError("scenario_before_after_incomplete")


def _alternative_summaries(
    scenarios: dict[str, object],
    *,
    selected_kind: ProposalScenarioKind,
    selected_replaced_uid: str | None,
) -> list[dict[str, object]]:
    alternatives: list[dict[str, object]] = []
    hold = scenarios.get("hold")
    if isinstance(hold, dict):
        alternatives.append(_scenario_summary(cast(dict[str, object], hold)))

    deploy = scenarios.get("deploy_cash")
    if selected_kind != "deploy_cash" and isinstance(deploy, dict):
        alternatives.append(_scenario_summary(cast(dict[str, object], deploy)))

    replacements = scenarios.get("replacements")
    if isinstance(replacements, list):
        for raw in replacements:
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, object], raw)
            replaced_uid = _optional_uid(item.get("replaced_instrument_uid"))
            if selected_kind == "replace" and replaced_uid == selected_replaced_uid:
                continue
            alternatives.append(_scenario_summary(item))
    return alternatives


def _scenario_summary(scenario: dict[str, object]) -> dict[str, object]:
    return {
        "kind": scenario.get("kind"),
        "status": scenario.get("status"),
        "reason": scenario.get("reason"),
        "target_instrument_uid": scenario.get("target_instrument_uid"),
        "replaced_instrument_uid": scenario.get("replaced_instrument_uid"),
        "residual_cash_rub": scenario.get("residual_cash_rub"),
        "turnover_rub": scenario.get("turnover_rub"),
        "expected_incremental_gain_rub": scenario.get(
            "expected_incremental_gain_rub"
        ),
    }


def _required_text(
    value: object,
    code: str,
    *,
    max_length: int,
) -> str:
    clean = str(value or "").strip()
    if not clean or len(clean) > max_length:
        raise ProposalBuildError(code)
    return clean


def _positive_decimal(value: object, code: str) -> Decimal:
    parsed = _decimal(value, code)
    if parsed <= 0:
        raise ProposalBuildError(code)
    return parsed


def _nonnegative_decimal(value: object, code: str) -> Decimal:
    parsed = _decimal(value, code)
    if parsed < 0:
        raise ProposalBuildError(code)
    return parsed


def _decimal(value: object, code: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProposalBuildError(code) from exc
    if not parsed.is_finite():
        raise ProposalBuildError(code)
    return parsed


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
