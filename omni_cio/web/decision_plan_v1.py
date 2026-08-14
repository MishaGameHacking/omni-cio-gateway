from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.decision import DecisionAction, DecisionSetV1
from omni_cio.contracts.v1.portfolio_plan import PortfolioPlanV1
from omni_cio.persistence.migration import ConnectionLike
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.session_v1 import SessionScopeV1


_MAX_BLOB_BYTES = 4 * 1024 * 1024
_DECISION_SCHEMA_REF = "omni_cio.contracts.v1.decision.DecisionSetV1"
_PLAN_SCHEMA_REF = "omni_cio.contracts.v1.portfolio_plan.PortfolioPlanV1"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP21 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _timestamp(value: datetime | None) -> str | None:
    return _utc(value).isoformat() if value is not None else None


def _decimal(value: object) -> str:
    return format(value, "f")


def _safe_payload_bytes(value: object | None) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, bytearray):
        return bytes(value)
    return None


def _payload_matches(payload: bytes, expected_sha256: str) -> bool:
    return hashlib.sha256(payload).hexdigest() == expected_sha256


def _decision_set(
    value: object | None,
    *,
    expected_sha256: str,
    schema_ref: str | None,
) -> DecisionSetV1 | None:
    payload = _safe_payload_bytes(value)
    if (
        payload is None
        or len(payload) > _MAX_BLOB_BYTES
        or schema_ref != _DECISION_SCHEMA_REF
        or not _payload_matches(payload, expected_sha256)
    ):
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"))
        return DecisionSetV1.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return None


def _portfolio_plan(
    value: object | None,
    *,
    expected_sha256: str,
    schema_ref: str | None,
) -> PortfolioPlanV1 | None:
    payload = _safe_payload_bytes(value)
    if (
        payload is None
        or len(payload) > _MAX_BLOB_BYTES
        or schema_ref != _PLAN_SCHEMA_REF
        or not _payload_matches(payload, expected_sha256)
    ):
        return None
    try:
        decoded = json.loads(payload.decode("utf-8"))
        return PortfolioPlanV1.model_validate(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return None


def _model_sha256(value: DecisionSetV1) -> str:
    canonical = json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _preferred_option(decision: DecisionSetV1):
    return next(
        item for item in decision.options if item.option_id == decision.preferred_option_id
    )


def _main_decision(decision: DecisionSetV1, plan: PortfolioPlanV1 | None) -> str | None:
    action = _preferred_option(decision).action
    if action is DecisionAction.HOLD:
        return "HOLD"
    if action is DecisionAction.WAIT_FOR_DATA:
        return "NO_ACTION"
    if action is DecisionAction.REVIEW_STRATEGIC_REBALANCE:
        return "REALLOCATE"
    if action is not DecisionAction.REVIEW_LIMITED_CHANGE or plan is None:
        return None

    actionable = tuple(row for row in plan.legs if row.optimizer_leg is not None)
    if not actionable:
        return None
    if all(row.action.value == "sell" for row in actionable):
        target_map = {row.stable_key: row for row in plan.targets}
        if all(
            target_map[row.optimizer_leg.stable_key].target_lots == 0
            for row in actionable
            if row.optimizer_leg is not None
        ):
            return "EXIT"
        return "REDUCE"
    return "REALLOCATE"


def _decision_view(decision: DecisionSetV1) -> dict[str, Any]:
    preferred = _preferred_option(decision)
    evidence = {
        row.evidence_id: {
            "evidence_id": row.evidence_id,
            "kind": row.kind.value,
            "statement": row.statement,
            "source_schema": row.source_schema,
            "source_id": row.source_id,
            "observed_value": (
                None if row.observed_value is None else _decimal(row.observed_value)
            ),
            "limit_value": None if row.limit_value is None else _decimal(row.limit_value),
            "currency": row.currency,
            "instrument_key": row.instrument_key,
        }
        for row in decision.evidence
    }
    return {
        "decision_set_sha256": _model_sha256(decision),
        "decided_at": _timestamp(decision.metadata.retrieved_at),
        "abstain": decision.abstain,
        "recommendation_ready": decision.recommendation_ready,
        "confidence": decision.confidence.value,
        "global_blockers": [item.value for item in decision.global_blockers],
        "preferred": {
            "option_id": preferred.option_id,
            "kind": preferred.kind.value,
            "status": preferred.status.value,
            "action": preferred.action.value,
            "title": preferred.title,
            "rationale": preferred.rationale,
            "confidence": preferred.confidence.value,
            "blockers": [item.value for item in preferred.blockers],
            "review_conditions": list(preferred.review_conditions),
            "evidence": [evidence[item] for item in preferred.evidence_ids],
        },
        "alternatives": [
            {
                "option_id": item.option_id,
                "kind": item.kind.value,
                "status": item.status.value,
                "action": item.action.value,
                "title": item.title,
                "rationale": item.rationale,
                "confidence": item.confidence.value,
                "blockers": [blocker.value for blocker in item.blockers],
                "review_conditions": list(item.review_conditions),
                "evidence_ids": list(item.evidence_ids),
            }
            for item in decision.options
            if item.option_id != preferred.option_id
        ],
        "evidence": list(evidence.values()),
        "trading_methods": False,
    }


def _risk_state_view(state: Any) -> dict[str, Any]:
    return {
        "total_value_base": _decimal(state.total_value_base),
        "cash_base": _decimal(state.cash_base),
        "cash_weight": _decimal(state.cash_weight),
        "policy_compliant": state.policy_compliant,
        "blockers": [item.value for item in state.blockers],
        "concentration": {
            "top_1_weight": _decimal(state.concentration.top_1_weight),
            "top_3_weight": _decimal(state.concentration.top_3_weight),
            "top_5_weight": _decimal(state.concentration.top_5_weight),
            "rows": [
                {
                    "dimension": row.dimension.value,
                    "bucket_key": row.bucket_key,
                    "weight": _decimal(row.weight),
                    "applicable_limit": (
                        None
                        if row.applicable_limit is None
                        else _decimal(row.applicable_limit)
                    ),
                    "limit_source": (
                        None if row.limit_source is None else row.limit_source.value
                    ),
                    "hard_limit": row.hard_limit,
                    "breached": row.breached,
                }
                for row in state.concentration.rows
            ],
        },
        "vectors": [
            {
                "kind": row.kind.value,
                "severity": row.severity.value,
                "hard_breach": row.hard_breach,
                "metrics": list(row.metrics),
                "evidence_codes": list(row.evidence_codes),
            }
            for row in state.vectors
        ],
        "liquidity": [
            {
                "stable_key": row.stable_key,
                "position_weight": _decimal(row.position_weight),
                "exit_days": None if row.exit_days is None else _decimal(row.exit_days),
                "spread_bps": None if row.spread_bps is None else _decimal(row.spread_bps),
                "stale": row.stale,
                "unknown": row.unknown,
            }
            for row in state.liquidity
        ],
        "stress": [
            {
                "scenario_id": row.scenario_id,
                "portfolio_change_base": _decimal(row.portfolio_change_base),
                "portfolio_change_weight": _decimal(row.portfolio_change_weight),
                "max_drawdown_limit": (
                    None
                    if row.max_drawdown_limit is None
                    else _decimal(row.max_drawdown_limit)
                ),
                "drawdown_breach": row.drawdown_breach,
            }
            for row in state.stress
        ],
    }


def _plan_view(plan: PortfolioPlanV1, *, now: datetime) -> dict[str, Any]:
    expired = plan.expires_at <= now
    return {
        "schema_version": plan.schema_version,
        "object_type": plan.object_type,
        "created_at": _timestamp(plan.created_at),
        "expires_at": _timestamp(plan.expires_at),
        "expired": expired,
        "plan_sha256": plan.plan_sha256,
        "selected_regime": plan.selected_regime.value,
        "approval_required": plan.approval_required,
        "approval_subject": {
            "state": (
                "EXPIRED"
                if expired
                else "PREVIEW_ONLY"
                if plan.approval_required
                else "NOT_REQUIRED"
            ),
            "phrase": (
                plan.owner_approval_phrase
                if plan.approval_required and not expired
                else None
            ),
            "can_approve": False,
            "mutation_invalidates": True,
        },
        "upstream": {
            "portfolio_snapshot_sha256": plan.portfolio_snapshot_sha256,
            "policy_id": plan.policy_reference.policy_id,
            "policy_version": plan.policy_reference.version,
            "policy_fingerprint_sha256": plan.policy_reference.fingerprint_sha256,
            "current_risk_assessment_sha256": plan.current_risk_assessment_sha256,
            "strategy_selection_sha256": plan.strategy_selection_sha256,
            "optimizer_sha256": plan.optimizer_sha256,
            "target_risk_assessment_sha256": plan.target_risk_assessment_sha256,
        },
        "values": {
            "current_value_base": _decimal(plan.current_value_base),
            "target_value_base": _decimal(plan.target_value_base),
            "current_cash_base": _decimal(plan.current_cash_base),
            "target_cash_base": _decimal(plan.target_cash_base),
            "total_clean_turnover_base": _decimal(plan.total_clean_turnover_base),
            "total_accrued_interest_base": _decimal(plan.total_accrued_interest_base),
            "total_settlement_turnover_base": _decimal(plan.total_settlement_turnover_base),
            "total_commission_base": _decimal(plan.total_commission_base),
            "total_estimated_tax_base": _decimal(plan.total_estimated_tax_base),
        },
        "risk": {
            "before": _risk_state_view(plan.risk_before),
            "after": _risk_state_view(plan.risk_after),
        },
        "targets": [
            {
                "stable_key": row.stable_key,
                "component": row.component.value,
                "current_lots": row.current_lots,
                "target_lots": row.target_lots,
                "lot_size": row.lot_size,
                "desired_weight": _decimal(row.desired_weight),
                "current_value_base": _decimal(row.current_value_base),
                "target_value_base": _decimal(row.target_value_base),
                "target_weight": _decimal(row.target_weight),
            }
            for row in plan.targets
        ],
        "legs": [
            {
                "sequence": row.sequence,
                "action": row.action.value,
                "trade": (
                    None
                    if row.optimizer_leg is None
                    else {
                        "trade_id": row.optimizer_leg.trade_id,
                        "stable_key": row.optimizer_leg.stable_key,
                        "component": row.optimizer_leg.component.value,
                        "side": row.optimizer_leg.side.value,
                        "current_lots": row.optimizer_leg.current_lots,
                        "target_lots": row.optimizer_leg.target_lots,
                        "quantity_lots": row.optimizer_leg.quantity_lots,
                        "lot_size": row.optimizer_leg.lot_size,
                        "reference_clean_unit_price_base": _decimal(
                            row.optimizer_leg.reference_clean_unit_price_base
                        ),
                        "gross_notional_base": _decimal(
                            row.optimizer_leg.gross_notional_base
                        ),
                        "accrued_interest_base": _decimal(
                            row.optimizer_leg.accrued_interest_base
                        ),
                        "settlement_notional_base": _decimal(
                            row.optimizer_leg.settlement_notional_base
                        ),
                        "commission_base": _decimal(row.optimizer_leg.commission_base),
                        "estimated_tax_base": _decimal(
                            row.optimizer_leg.estimated_tax_base
                        ),
                        "cash_delta_base": _decimal(row.optimizer_leg.cash_delta_base),
                        "required_execution_days": (
                            row.optimizer_leg.required_execution_days
                        ),
                        "staged_execution_required": (
                            row.optimizer_leg.staged_execution_required
                        ),
                        "partial_fill_aware": row.optimizer_leg.partial_fill_aware,
                        "market_source_sha256": row.optimizer_leg.market_source_sha256,
                        "friction_source_sha256s": list(
                            row.optimizer_leg.friction_source_sha256s
                        ),
                    }
                ),
            }
            for row in plan.legs
        ],
        "cancellation_conditions": [
            {"code": row.code.value, "hard_cancel": row.hard_cancel}
            for row in plan.cancellation_conditions
        ],
        "execution_authorized": False,
        "trading_methods": False,
    }


def _change_action_requires_plan(decision: DecisionSetV1) -> bool:
    return _preferred_option(decision).action in {
        DecisionAction.REVIEW_LIMITED_CHANGE,
        DecisionAction.REVIEW_STRATEGIC_REBALANCE,
    }


def _no_change_action(decision: DecisionSetV1) -> bool:
    return _preferred_option(decision).action in {
        DecisionAction.HOLD,
        DecisionAction.WAIT_FOR_DATA,
    }


def _invalid_payload(
    *,
    now: datetime,
    reason: str,
    decision: DecisionSetV1 | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_at": now.isoformat(),
        "state": "INVALID",
        "reason": reason,
        "main_decision": None,
        "decision": None if decision is None else _decision_view(decision),
        "plan": None,
        "execution_authorized": False,
        "trading_methods": False,
    }


class DecisionPlanReadServiceV1:
    """Tenant-scoped WP21 projection over accepted decision and immutable-plan DTOs."""

    def __init__(
        self,
        connection: ConnectionLike,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._connection = connection
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        now = _utc(self._clock())
        row = self._connection.execute(
            "SELECT d.decision_id, d.portfolio_id, d.policy_id, d.snapshot_id, "
            "d.schema_version, d.identity_version, d.payload_sha256, d.decided_at, "
            "db.schema_ref, "
            "CASE WHEN octet_length(db.payload) <= %s THEN db.payload ELSE NULL END, "
            "p.plan_id, p.schema_version, p.identity_version, p.payload_sha256, "
            "p.created_at, pb.schema_ref, "
            "CASE WHEN octet_length(pb.payload) <= %s THEN pb.payload ELSE NULL END, "
            "s.source_payload_sha256 "
            "FROM omni_cio_v10.decisions d "
            "JOIN omni_cio_v10.portfolio_snapshots s "
            "ON s.tenant_id = d.tenant_id AND s.portfolio_id = d.portfolio_id "
            "AND s.policy_id = d.policy_id AND s.snapshot_id = d.snapshot_id "
            "LEFT JOIN omni_cio_v10.content_blobs db "
            "ON db.tenant_id = d.tenant_id AND db.payload_sha256 = d.payload_sha256 "
            "LEFT JOIN LATERAL ("
            "SELECT p0.plan_id, p0.schema_version, p0.identity_version, "
            "p0.payload_sha256, p0.created_at "
            "FROM omni_cio_v10.plans p0 "
            "WHERE p0.tenant_id = d.tenant_id AND p0.decision_id = d.decision_id "
            "AND p0.portfolio_id = d.portfolio_id AND p0.policy_id = d.policy_id "
            "AND p0.snapshot_id = d.snapshot_id "
            "ORDER BY p0.created_at DESC, p0.plan_id LIMIT 1"
            ") p ON TRUE "
            "LEFT JOIN omni_cio_v10.content_blobs pb "
            "ON pb.tenant_id = d.tenant_id AND pb.payload_sha256 = p.payload_sha256 "
            "WHERE d.tenant_id = %s "
            "ORDER BY d.decided_at DESC, d.decision_id LIMIT 1",
            (_MAX_BLOB_BYTES, _MAX_BLOB_BYTES, tenant_id),
        ).fetchone()

        if row is None:
            return {
                "schema_version": "1.0.0",
                "generated_at": now.isoformat(),
                "state": "EMPTY",
                "main_decision": None,
                "decision": None,
                "plan": None,
                "execution_authorized": False,
                "trading_methods": False,
            }

        decision_payload_sha = str(row[6])
        decision = _decision_set(
            row[9],
            expected_sha256=decision_payload_sha,
            schema_ref=None if row[8] is None else str(row[8]),
        )
        if decision is None:
            return _invalid_payload(now=now, reason="DECISION_PAYLOAD_INVALID")

        decided_at = row[7]
        if not isinstance(decided_at, datetime):
            raise ValueError("WP21 decisions.decided_at must be datetime")
        if _utc(decided_at) != decision.metadata.retrieved_at:
            return _invalid_payload(
                now=now,
                reason="DECISION_RECORD_BINDING_INVALID",
                decision=decision,
            )

        plan_id = None if row[10] is None else str(row[10])
        plan: PortfolioPlanV1 | None = None
        if plan_id is not None:
            plan_payload_sha = str(row[13])
            plan = _portfolio_plan(
                row[16],
                expected_sha256=plan_payload_sha,
                schema_ref=None if row[15] is None else str(row[15]),
            )
            if plan is None:
                return _invalid_payload(
                    now=now,
                    reason="PLAN_PAYLOAD_INVALID",
                    decision=decision,
                )
            plan_created_at = row[14]
            if not isinstance(plan_created_at, datetime):
                raise ValueError("WP21 plans.created_at must be datetime")
            if (
                _utc(plan_created_at) != plan.created_at
                or plan.policy_reference.policy_id != str(row[2])
                or plan.portfolio_snapshot_sha256 != str(row[17])
            ):
                return _invalid_payload(
                    now=now,
                    reason="PLAN_RECORD_BINDING_INVALID",
                    decision=decision,
                )

        preferred_action = _preferred_option(decision).action
        if preferred_action is DecisionAction.WAIT_FOR_DATA:
            state = "PARTIAL"
            reason = "DECISION_ABSTAINS_WAIT_FOR_DATA"
        elif _change_action_requires_plan(decision) and plan is None:
            state = "PARTIAL"
            reason = "ACTIONABLE_DECISION_PLAN_MISSING"
        elif _no_change_action(decision) and plan is not None:
            state = "INVALID"
            reason = "NO_CHANGE_DECISION_CANNOT_BIND_PLAN"
        else:
            reason = None
            state = "EXPIRED" if plan is not None and plan.expires_at <= now else "READY"

        main_decision = _main_decision(decision, plan)
        if state == "READY" and main_decision is None:
            state = "INVALID"
            reason = "MAIN_DECISION_PROJECTION_UNAVAILABLE"

        return {
            "schema_version": "1.0.0",
            "generated_at": now.isoformat(),
            "state": state,
            "reason": reason,
            "main_decision": main_decision,
            "record": {
                "decision_id": str(row[0]),
                "portfolio_id": str(row[1]),
                "policy_id": str(row[2]),
                "snapshot_id": str(row[3]),
                "snapshot_source_payload_sha256": str(row[17]),
                "decision_schema_version": str(row[4]),
                "decision_identity_version": int(row[5]),
                "decision_payload_sha256": decision_payload_sha,
                "decided_at": _timestamp(_utc(decided_at)),
                "plan_id": plan_id,
                "plan_schema_version": None if row[11] is None else str(row[11]),
                "plan_identity_version": None if row[12] is None else int(row[12]),
                "plan_payload_sha256": None if row[13] is None else str(row[13]),
                "plan_created_at": (
                    _timestamp(_utc(row[14])) if isinstance(row[14], datetime) else None
                ),
            },
            "decision": _decision_view(decision),
            "plan": None if plan is None else _plan_view(plan, now=now),
            "execution_authorized": False,
            "trading_methods": False,
        }


def install_decision_plan_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: DecisionPlanReadServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/decision-plan")
    def read_decision_plan(request: Request) -> JSONResponse:
        raw_session = request.cookies.get(SESSION_COOKIE)
        scope: SessionScopeV1 | None = sessions.resolve(
            raw_session,
            now=_utc(clock()),
        )
        if scope is None:
            raise HTTPException(status_code=401, detail="WEB_SESSION_REQUIRED")
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(
            payload,
            headers={
                "Cache-Control": "no-store",
                "Pragma": "no-cache",
            },
        )
