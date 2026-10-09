"""Explicit strategy planning and consent; bounded dispatch and existing-order recovery."""

from __future__ import annotations

import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, cast
from uuid import UUID

from .backtest import (
    ResearchCosts,
)
from .broker import (
    BrokerConnectionError,
    BrokerObservationBundle,
    BrokerPortfolioSnapshot,
    BrokerService,
)
from .execution import (
    ExecutionLegStatus,
    ExecutionStateError,
    execution_cash_reserve,
    execution_depth,
    execution_position_lots,
    execution_quote,
    provider_leg_status,
    strategy_order_plan,
)
from .execution_store import (
    ExecutionLegObservation,
    ExecutionLegRecord,
    ExecutionRunRecord,
    ExecutionStore,
    StrategyExecutionContext,
)
from .financial import RUB_QUANTUM
from .portfolio_store import PortfolioStore
from .research_policy import (
    MAX_RESEARCH_ASSETS,
    RESEARCH_ENGINE_VERSION,
)
from .research_store import ResearchStore
from .strategy import document_hash, normalize_document
from .strategy_assessment import StrategyCandidateFacts, select_strategy_candidates
from .strategy_service import current_research_candidate, research_assets_from_inputs
from .tbank import (
    TBankInstrumentMetadata,
    TBankMoney,
    TBankNotFound,
    TBankOrderState,
    TBankTokenRejected,
    TBankUnavailable,
)

_PLANNING_READ_WORKERS = 4
_PLANNING_DEADLINE_SECONDS = 35


class ExecutionServiceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _execution_snapshot_lots(
    snapshot: BrokerPortfolioSnapshot, lot_sizes: dict[str, Any]
) -> dict[str, int]:
    actual_lots = {}
    for row in snapshot.portfolio.positions:
        if row.instrument_type == "currency" or Decimal(row.quantity) == 0:
            continue
        uid = row.instrument_uid
        if uid in actual_lots or uid not in lot_sizes:
            raise ExecutionServiceError("execution_portfolio_changed")
        actual_lots[uid] = execution_position_lots(row, lot_sizes[uid])[0]
    return actual_lots


class PortfolioExecutionService:
    def __init__(
        self,
        *,
        store: ExecutionStore,
        broker: BrokerService,
        portfolio_store: PortfolioStore | None = None,
        research_store: ResearchStore | None = None,
        legal_versions: dict[str, str] | None = None,
        live_enabled: bool = False,
        sandbox_enabled: bool = False,
        max_order_rub: Decimal = Decimal(0),
        max_daily_rub: Decimal = Decimal(0),
    ) -> None:
        self.store = store
        self.broker = broker
        self.portfolio_store = portfolio_store
        self.research_store = research_store
        self.legal_versions = legal_versions or {}
        self.live_enabled, self.sandbox_enabled = live_enabled, sandbox_enabled
        self.max_order_rub, self.max_daily_rub = max_order_rub, max_daily_rub

    def _current_strategy_context(self, user_id: UUID, expected_version: int) -> dict[str, Any]:
        if self.portfolio_store is None:
            raise ExecutionServiceError("execution_planning_unavailable")
        draft = self.portfolio_store.current_strategy_draft(user_id)
        connection = self.broker.status(user_id)
        if not draft or draft["version"] != expected_version:
            raise ExecutionServiceError("strategy_version_conflict")
        if not connection.connected or not connection.verified_at:
            raise ExecutionServiceError("execution_connection_required")
        document = normalize_document(draft["document"])
        if any(
            value is None for group in ("profile", "policy") for value in document[group].values()
        ):
            raise ExecutionServiceError("execution_policy_incomplete")
        return {
            "engine": "strategy_execution_1",
            "strategy_version": expected_version,
            "strategy_hash": document_hash(document),
            "document": document,
            "account_id": connection.account_id,
            "environment": connection.environment,
            "connection_verified_at": connection.verified_at.isoformat(),
            "legal_versions": self.legal_versions,
        }

    def plan(
        self,
        user_id: UUID,
        *,
        expected_version: int,
        research_run_id: UUID,
        session_digest: bytes,
        commission_bps: Decimal,
        slippage_bps: Decimal,
        mode: str = "shadow",
    ) -> dict[str, Any]:
        deadline = monotonic() + _PLANNING_DEADLINE_SECONDS
        if mode not in {"shadow", "sandbox", "live"} or any(
            not cost.is_finite() or not 0 <= cost <= 1000 for cost in (commission_bps, slippage_bps)
        ):
            raise ExecutionServiceError("execution_plan_parameters_invalid")
        payload = self._current_strategy_context(user_id, expected_version)
        self.store.authorize_strategy(
            user_id,
            session_digest=session_digest,
            legal_versions=self.legal_versions,
            payload=payload,
        )
        archive, evidence, now = self._planning_archive(
            user_id, research_run_id, payload, commission_bps, slippage_bps, mode
        )
        inputs = archive["inputs"]
        assets = research_assets_from_inputs(inputs)
        try:
            candidates = [
                current_research_candidate(
                    asset,
                    as_of=now,
                    document=payload["document"],
                    costs=ResearchCosts(commission_bps, slippage_bps),
                )
                for asset in assets
            ]
        except ValueError as exc:
            raise ExecutionServiceError("execution_current_research_required") from exc
        selection = select_strategy_candidates(payload["document"], candidates, as_of=now)
        if not selection["candidate_selection_ready"]:
            return {
                "status": "blocked",
                "blockers": selection["missing_requirements"],
                "selection": selection,
            }
        self._require_planning_budget(deadline)
        context, bundle = self._planning_snapshot(user_id, payload, now)
        quotes = self._planning_quotes(
            user_id,
            selection,
            bundle,
            candidates,
            slippage_bps,
            deadline=deadline,
        )
        cash = sum(
            (
                Decimal(value.value)
                for value in bundle.positions.money
                if value.currency.upper() == "RUB"
            ),
            Decimal(0),
        )
        blocked = sum(
            (
                Decimal(value.value)
                for value in bundle.positions.blocked_money
                if value.currency.upper() == "RUB"
            ),
            Decimal(0),
        )
        max_order, max_daily = self._planning_caps(mode, Decimal(bundle.analysis.nav_rub))
        result = strategy_order_plan(
            payload["document"],
            candidates,
            selection["selected"],
            bundle.portfolio.positions,
            quotes,
            cash=cash,
            blocked_cash=blocked,
            commission_bps=commission_bps,
            now=now,
            max_order=max_order,
            max_daily=max_daily,
        )
        if result["blockers"] or not result["legs"]:
            return {
                "status": "blocked" if result["blockers"] else "no_change",
                **result,
                "selection": selection,
            }
        with ThreadPoolExecutor(max_workers=_PLANNING_READ_WORKERS) as reads:
            estimates = [
                reads.submit(self._check_order_estimate, user_id, leg, deadline)
                for leg in result["legs"]
            ]
            for estimate in estimates:
                estimate.result()
        # All read side-effects are complete before the short authority transaction.
        self._require_planning_budget(deadline)
        issued = datetime.now(UTC)
        if any(
            issued - datetime.fromisoformat(quote["quote_at"]) > timedelta(seconds=30)
            for quote in quotes.values()
        ):
            raise ExecutionServiceError("execution_quote_expired_during_plan")
        payload.update(result)
        payload.update(
            {
                "mode": mode,
                "research_run_id": str(research_run_id),
                "evidence_version": evidence["version"],
                "source_snapshot_id": context["snapshot_id"],
                "commission_bps": str(commission_bps),
                "slippage_bps": str(slippage_bps),
                "created_at": issued.isoformat(),
                "expires_at": (issued + timedelta(minutes=2)).isoformat(),
                "input_provenance": archive["result"].get("input_provenance", {}),
                "selection": selection,
                "execution_enabled": False,
                "limitations": [
                    "Лимитная заявка может не исполниться или исполниться частично.",
                    "Налоговый резерв — модель без зачёта убытков и льгот.",
                    "Теневой режим не изменяет брокерский счёт.",
                ],
            }
        )
        return self.store.save_strategy_proposal(
            user_id,
            payload=payload,
            session_digest=session_digest,
            legal_versions=self.legal_versions,
        )

    def _planning_caps(self, mode: str, observed_nav: Decimal) -> tuple[Decimal, Decimal]:
        order = observed_nav if mode == "shadow" and self.max_order_rub == 0 else self.max_order_rub
        daily = observed_nav if mode == "shadow" and self.max_daily_rub == 0 else self.max_daily_rub
        return order, daily

    def _planning_archive(
        self,
        user_id: UUID,
        research_run_id: UUID,
        payload: dict[str, Any],
        commission_bps: Decimal,
        slippage_bps: Decimal,
        mode: str,
    ) -> tuple[dict[str, Any], dict[str, Any], datetime]:
        if (
            mode == "live"
            and payload["environment"] != "prod"
            or mode == "sandbox"
            and payload["environment"] != "sandbox"
        ):
            raise ExecutionServiceError("execution_mode_account_mismatch")
        if self.research_store is None or self.portfolio_store is None:
            raise ExecutionServiceError("execution_planning_unavailable")
        archive = self.research_store.run(user_id, research_run_id)
        inputs = archive["inputs"]
        now = datetime.now(UTC)
        if (
            archive.get("result", {}).get("status") != "computed"
            or not isinstance(archive.get("result", {}).get("metrics"), dict)
            or archive["result"].get("engine_version") != RESEARCH_ENGINE_VERSION
            or inputs.get("engine_version") != RESEARCH_ENGINE_VERSION
        ):
            raise ExecutionServiceError("execution_computed_research_required")
        if (
            archive["account_id"] != payload["account_id"]
            or archive["environment"] != payload["environment"]
            or archive["strategy_version"] != payload["strategy_version"]
            or inputs["document"] != payload["document"]
            or not 0
            <= (now - datetime.fromisoformat(inputs["observed_at"])).total_seconds()
            <= 86400
            or not 0 <= (now - datetime.fromisoformat(inputs["to_at"])).total_seconds() <= 4 * 86400
            or Decimal(inputs["commission_bps"]) != commission_bps
            or Decimal(inputs["slippage_bps"]) != slippage_bps
        ):
            raise ExecutionServiceError("execution_current_research_required")
        self._require_current_selection(archive["result"].get("current_selection"), now)
        evidence = self.research_store.evidence(user_id)
        if evidence["version"] != archive["evidence_version"]:
            raise ExecutionServiceError("execution_research_evidence_changed")
        return archive, evidence, now

    @staticmethod
    def _require_current_selection(selection: object, now: datetime) -> None:
        # A historical basket cannot override an explicitly unavailable current
        # catalog/evidence assessment, even when its backtest itself is computed.
        if (
            not isinstance(selection, dict)
            or selection.get("status") != "ready"
            or selection.get("candidate_selection_ready") is not True
        ):
            raise ExecutionServiceError("execution_current_research_required")
        try:
            observed = datetime.fromisoformat(selection["as_of"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionServiceError("execution_current_research_required") from exc
        if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 86400:
            raise ExecutionServiceError("execution_current_research_required")

    def _planning_snapshot(
        self,
        user_id: UUID,
        payload: dict[str, Any],
        now: datetime,
    ) -> tuple[dict[str, Any], BrokerObservationBundle]:
        if self.portfolio_store is None:
            raise ExecutionServiceError("execution_planning_unavailable")
        context = self.portfolio_store.latest_balancing_context(user_id)
        if (
            context is None
            or context["account_id"] != payload["account_id"]
            or not 0 <= (now - cast(datetime, context["captured_at"])).total_seconds() <= 300
        ):
            raise ExecutionServiceError("execution_refresh_snapshot_required")
        bundle = self.broker.observation_bundle(user_id)
        if (
            bundle.account_id != payload["account_id"]
            or bundle.environment != payload["environment"]
            or bundle.positions.limits_loading_in_progress
            or bundle.analysis.status == "needs_reconciliation"
            or any(
                item.currency.upper() != "RUB" and Decimal(item.value) != 0
                for item in bundle.positions.money
            )
        ):
            raise ExecutionServiceError("execution_portfolio_incomplete")
        return context, bundle

    def _planning_quotes(
        self,
        user_id: UUID,
        selection: dict[str, Any],
        bundle: BrokerObservationBundle,
        candidates: list[StrategyCandidateFacts],
        slippage_bps: Decimal,
        *,
        deadline: float | None = None,
    ) -> dict[str, Any]:
        uids = {row["instrument_uid"] for row in selection["selected"]}
        uids.update(
            position.instrument_uid
            for position in bundle.portfolio.positions
            if position.instrument_type != "currency" and Decimal(position.quantity) != 0
        )
        if len(uids) > MAX_RESEARCH_ASSETS or not uids <= {
            row.instrument_uid for row in candidates
        }:
            raise ExecutionServiceError("execution_held_evidence_missing")
        deadline = deadline if deadline is not None else monotonic() + _PLANNING_DEADLINE_SECONDS
        self._require_planning_budget(deadline)
        qualification = self.broker.user_info(user_id)
        by_uid = {row.instrument_uid: row for row in candidates}
        # The just-read full catalog already contains the execution metadata.
        # Finish exceptional individual fallbacks before starting fresh books.
        metadata = {row.uid: row for row in bundle.metadata if row.uid in uids}
        with ThreadPoolExecutor(max_workers=_PLANNING_READ_WORKERS) as reads:
            fallback = {
                uid: reads.submit(self._planning_metadata, user_id, uid, deadline)
                for uid in sorted(uids - metadata.keys())
            }
            metadata.update({uid: future.result() for uid, future in fallback.items()})
            self._require_planning_budget(deadline)
            pending = {
                uid: reads.submit(
                    self._planning_quote,
                    user_id,
                    by_uid[uid],
                    metadata[uid],
                    qualification.qualified,
                    slippage_bps,
                    deadline,
                )
                for uid in sorted(uids)
            }
            return {uid: future.result() for uid, future in pending.items()}

    @staticmethod
    def _require_planning_budget(deadline: float) -> None:
        if monotonic() >= deadline:
            raise ExecutionServiceError("execution_planning_read_budget_exhausted")

    def _planning_metadata(
        self,
        user_id: UUID,
        instrument_uid: str,
        deadline: float,
    ) -> TBankInstrumentMetadata:
        self._require_planning_budget(deadline)
        metadata = self.broker.execution_instrument(user_id, instrument_uid)
        self._require_planning_budget(deadline)
        return metadata

    def _planning_quote(
        self,
        user_id: UUID,
        candidate: StrategyCandidateFacts,
        metadata: TBankInstrumentMetadata,
        qualified: bool,
        slippage_bps: Decimal,
        deadline: float,
    ) -> dict[str, Any]:
        uid = candidate.instrument_uid
        self._require_planning_budget(deadline)
        status = self.broker.market_trading_status(user_id, uid)
        if (
            not status.limit_order_available
            or not status.api_trade_available
            or status.only_best_price
            or metadata.api_trade_available is not True
            or metadata.buy_available is not True
            or metadata.sell_available is not True
            or metadata.for_qual_investor is None
            or metadata.for_qual_investor
            and not qualified
            or metadata.required_tests
        ):
            raise ExecutionServiceError("execution_instrument_permission_unverified")
        if candidate.lot_size != metadata.lot:
            raise ExecutionServiceError("execution_lot_changed")
        self._require_planning_budget(deadline)
        book = self.broker.candidate_order_book(user_id, uid, depth=50)
        return execution_quote(metadata, book, slippage_bps=slippage_bps, now=datetime.now(UTC))

    def _check_order_estimate(
        self,
        user_id: UUID,
        leg: dict[str, Any],
        deadline: float | None = None,
    ) -> None:
        if deadline is not None:
            self._require_planning_budget(deadline)
        estimate = self.broker.estimate_limit_order(
            user_id,
            instrument_uid=leg["instrument_uid"],
            lots=leg["lots"],
            price=Decimal(leg["limit_price"]),
            action=leg["action"],
        )
        if (
            Decimal(estimate.commission.value) > Decimal(leg["commission_cap_rub"])
            or abs(
                Decimal(estimate.initial_order_amount.value)
                - Decimal(leg["limit_price"]) * leg["lot_size"] * leg["lots"]
            )
            > RUB_QUANTUM
            or leg["action"] == "buy"
            and Decimal(estimate.total_order_amount.value) > Decimal(leg["max_spend_rub"])
            or leg["action"] == "sell"
            and Decimal(estimate.total_order_amount.value) < Decimal(leg["min_proceeds_rub"])
        ):
            raise ExecutionServiceError("execution_provider_cost_exceeds_cap")

    def confirm(
        self,
        user_id: UUID,
        proposal_id: UUID,
        *,
        proposal_version: int,
        proposal_hash: str,
        expected_strategy_version: int,
        session_digest: bytes,
    ) -> dict[str, Any]:
        run_id = self.store.confirm_strategy_proposal(
            user_id,
            proposal_id,
            proposal_version=proposal_version,
            proposal_hash=proposal_hash,
            expected_strategy_version=expected_strategy_version,
            session_digest=session_digest,
            legal_versions=self.legal_versions,
            live_enabled=self.live_enabled,
            sandbox_enabled=self.sandbox_enabled,
            global_max_order=self.max_order_rub,
            global_max_daily=self.max_daily_rub,
        )
        return self._run_payload(user_id, run_id)

    def create_mandate(
        self,
        user_id: UUID,
        *,
        expected_version: int,
        session_digest: bytes,
        max_order_notional_rub: Decimal,
        max_daily_notional_rub: Decimal,
        expires_at: datetime,
    ) -> dict[str, Any]:
        if not self.live_enabled:
            raise ExecutionServiceError("execution_deployment_disabled")
        payload = self._current_strategy_context(user_id, expected_version)
        if payload["environment"] != "prod":
            raise ExecutionServiceError("live_account_mismatch")
        self.broker.live_account(user_id)
        return self.store.create_strategy_mandate(
            user_id,
            payload=payload,
            session_digest=session_digest,
            legal_versions=self.legal_versions,
            max_order=max_order_notional_rub,
            max_daily=max_daily_notional_rub,
            expires_at=expires_at,
            global_max_order=self.max_order_rub,
            global_max_daily=self.max_daily_rub,
        )

    def _run_payload(self, user_id: UUID, run_id: UUID) -> dict[str, Any]:
        run, legs = self._execution_snapshot(user_id, run_id)
        record = {**asdict(run), "proposal_hash": run.proposal_hash.hex()}
        return {
            "run": json.loads(json.dumps(record, default=str)),
            "legs": json.loads(json.dumps([asdict(leg) for leg in legs], default=str)),
            "dispatch_enabled": {
                "shadow": True,
                "live": self.live_enabled,
                "sandbox": self.sandbox_enabled,
            }[run.mode],
        }

    def dispatch(
        self, user_id: UUID, run_id: UUID, *, session_digest: bytes, expected_leg_id: UUID
    ) -> dict[str, Any]:
        run, legs = self._execution_snapshot(user_id, run_id)
        requested = next((leg for leg in legs if leg.id == expected_leg_id), None)
        if requested is None:
            raise ExecutionServiceError("execution_leg_not_found")
        if requested.status in {"filled", "shadow_filled", "cancelled", "rejected", "failed"}:
            return self._run_payload(user_id, run_id)
        if run.status in {"succeeded", "cancelled", "failed"}:
            return self._run_payload(user_id, run_id)
        proposal = self._dispatch_authority(user_id, run, session_digest)
        payload = proposal["payload"]
        current = next((leg for leg in legs if leg.status not in {"filled", "shadow_filled"}), None)
        if current is None:
            return self._run_payload(user_id, run_id)
        if current.id != expected_leg_id:
            raise ExecutionServiceError("execution_leg_not_current")
        if current.status != "pending":
            # Unknown or partial outcomes never trigger another PostOrder or next leg.
            if run.mode != "shadow":
                self.reconcile(user_id, run_id)
            return self._run_payload(user_id, run_id)
        if datetime.now(UTC) >= proposal["expires_at"]:
            raise ExecutionServiceError("execution_proposal_expired")
        if (
            self.research_store is None
            or self.research_store.evidence(user_id)["version"] != payload["evidence_version"]
        ):
            raise ExecutionServiceError("execution_research_evidence_changed")
        leg_payload = payload["legs"][current.leg_index]
        self._dispatch_preflight(user_id, current, leg_payload, payload, legs, run.mode)
        authority = StrategyExecutionContext(session_digest, self.legal_versions, payload)
        if run.mode == "shadow":
            self._fill_shadow_leg(user_id, run_id, current, leg_payload, authority)
        else:
            self._submit_pending_leg(user_id, run, current, payload, authority)
        return self._run_payload(user_id, run_id)

    def _fill_shadow_leg(
        self,
        user_id: UUID,
        run_id: UUID,
        current: ExecutionLegRecord,
        leg_payload: dict[str, Any],
        authority: StrategyExecutionContext,
    ) -> None:
        self.store.transition_leg(
            user_id,
            run_id=run_id,
            leg_id=current.id,
            expected_statuses=("pending",),
            new_status="shadow_filled",
            event_type="explicit_shadow_fill",
            details={"broker_order_submitted": False},
            observation=ExecutionLegObservation(
                lots_executed=current.lots_requested,
                executed_amount_rub=Decimal(
                    leg_payload["max_spend_rub"]
                    if current.action == "buy"
                    else leg_payload["min_proceeds_rub"]
                ),
                executed_commission_rub=Decimal(leg_payload["commission_cap_rub"]),
            ),
            strategy_context=authority,
        )

    def _dispatch_authority(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        session_digest: bytes,
    ) -> dict[str, Any]:
        proposal = self.store.strategy_proposal(user_id, run.proposal_id)
        payload = proposal["payload"]
        if not hmac.compare_digest(bytes(proposal["created_session_digest"]), session_digest):
            raise ExecutionServiceError("execution_confirmation_session_mismatch")
        self.store.authorize_strategy(
            user_id,
            session_digest=session_digest,
            legal_versions=self.legal_versions,
            payload=payload,
        )
        if (
            run.mode == "live"
            and not self.live_enabled
            or run.mode == "sandbox"
            and not self.sandbox_enabled
        ):
            raise ExecutionServiceError("execution_deployment_disabled")
        return proposal

    def _submit_pending_leg(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        current: ExecutionLegRecord,
        payload: dict[str, Any],
        authority: StrategyExecutionContext,
    ) -> None:
        run_id = run.id
        self.store.transition_leg(
            user_id,
            run_id=run_id,
            leg_id=current.id,
            expected_statuses=("pending",),
            new_status="submitting",
            event_type="explicit_limit_submission_claimed",
            details={"request_id": str(current.request_id)},
            strategy_context=replace(authority, limits=(self.max_order_rub, self.max_daily_rub)),
        )
        try:
            state = self.broker.submit_limit_order(
                user_id,
                expected_account_id=run.account_id,
                expected_verified_at=datetime.fromisoformat(payload["connection_verified_at"]),
                instrument_uid=current.instrument_uid,
                lots=current.lots_requested,
                price=current.limit_price,
                action=current.action,
                request_id=str(current.request_id),
            )
        except (TBankUnavailable, TBankTokenRejected, BrokerConnectionError):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run_id,
                leg_id=current.id,
                error_code="submission_outcome_unknown",
                details={"request_id": str(current.request_id), "retry_post_order": False},
                now=datetime.now(UTC),
            )
        else:
            self._record_provider_state(
                user_id,
                run,
                current,
                state,
                datetime.now(UTC),
                expected_statuses=("submitting",),
                event_type="explicit_limit_submitted",
            )

    def _dispatch_preflight(
        self,
        user_id: UUID,
        leg: ExecutionLegRecord,
        leg_payload: dict[str, Any],
        payload: dict[str, Any],
        legs: tuple[ExecutionLegRecord, ...],
        mode: str,
    ) -> None:
        self._dispatch_market_preflight(user_id, leg, leg_payload)
        snapshot = self.broker.portfolio(user_id)
        if (
            snapshot.account_id != payload["account_id"]
            or snapshot.positions.limits_loading_in_progress
            or any(
                row.currency.upper() != "RUB" and Decimal(row.value) != 0
                for row in snapshot.positions.money
            )
        ):
            raise ExecutionServiceError("execution_account_changed")
        cash = sum(
            (
                Decimal(row.value)
                for row in snapshot.positions.money
                if row.currency.upper() == "RUB"
            ),
            Decimal(0),
        )
        blocked = sum(
            (
                Decimal(row.value)
                for row in snapshot.positions.blocked_money
                if row.currency.upper() == "RUB"
            ),
            Decimal(0),
        )
        if not 0 <= blocked <= cash:
            raise ExecutionServiceError("execution_cash_inconsistent")
        position = next(
            (
                row
                for row in snapshot.portfolio.positions
                if row.instrument_uid == leg.instrument_uid
            ),
            None,
        )
        available_lots = Decimal(
            execution_position_lots(position, leg_payload["lot_size"])[1]
            if position is not None else 0
        )
        self._check_execution_balances(snapshot, cash, payload, legs, mode)
        if mode == "shadow":
            cash, available_lots = self._shadow_execution_balances(
                cash, available_lots, leg.instrument_uid, legs
            )
        if leg.action == "sell" and available_lots < leg.lots_requested:
            raise ExecutionServiceError("execution_free_inventory_changed")
        if leg.action == "buy" and cash - Decimal(leg_payload["max_spend_rub"]) < (
            execution_cash_reserve(
                payload["document"], nav=Decimal(payload["nav_rub"]), blocked_cash=blocked,
            )
        ):
            raise ExecutionServiceError("execution_free_cash_changed")

    def _dispatch_market_preflight(
        self,
        user_id: UUID,
        leg: ExecutionLegRecord,
        leg_payload: dict[str, Any],
    ) -> None:
        metadata = self.broker.execution_instrument(user_id, leg.instrument_uid)
        status = self.broker.market_trading_status(user_id, leg.instrument_uid)
        if (
            metadata.lot != leg_payload["lot_size"]
            or metadata.api_trade_available is not True
            or not status.limit_order_available
            or not status.api_trade_available
            or status.only_best_price
            or (
                metadata.buy_available is not True
                if leg.action == "buy"
                else metadata.sell_available is not True
            )
        ):
            raise ExecutionServiceError("execution_instrument_changed")
        book = self.broker.candidate_order_book(user_id, leg.instrument_uid, depth=50)
        quote = execution_quote(metadata, book, slippage_bps=Decimal(0), now=datetime.now(UTC))
        acceptable = (
            quote["buy_limit"] <= leg.limit_price
            if leg.action == "buy"
            else quote["sell_limit"] >= leg.limit_price
        )
        depth = execution_depth(
            book,
            action=leg.action,
            limit_price=leg.limit_price,
            cash_price_factor=quote["cash_price_factor"],
        )
        if not acceptable or depth < leg.lots_requested:
            raise ExecutionServiceError("execution_quote_moved_outside_limit")
        self._check_order_estimate(user_id, leg_payload)

    @staticmethod
    def _check_execution_balances(
        snapshot: BrokerPortfolioSnapshot,
        cash: Decimal,
        payload: dict[str, Any],
        legs: tuple[ExecutionLegRecord, ...],
        mode: str,
    ) -> None:
        expected_lots = dict(payload["initial_lots"])
        expected_cash = Decimal(payload["cash_before_rub"])
        if mode != "shadow":
            for previous in legs:
                if previous.status != "filled":
                    continue
                sign = 1 if previous.action == "buy" else -1
                expected_lots[previous.instrument_uid] = (
                    expected_lots.get(previous.instrument_uid, 0) + sign * previous.lots_executed
                )
                expected_cash -= sign * previous.executed_amount_rub
        actual_lots = _execution_snapshot_lots(snapshot, payload.get("lot_sizes", {}))
        if actual_lots != {uid: count for uid, count in expected_lots.items() if count} or abs(
            cash - expected_cash
        ) > RUB_QUANTUM:
            raise ExecutionServiceError("execution_portfolio_changed")

    @staticmethod
    def _shadow_execution_balances(
        cash: Decimal,
        available_lots: Decimal,
        instrument_uid: str,
        legs: tuple[ExecutionLegRecord, ...],
    ) -> tuple[Decimal, Decimal]:
        for previous in legs:
            if previous.status != "shadow_filled":
                continue
            cash += (
                previous.executed_amount_rub
                if previous.action == "sell"
                else -previous.executed_amount_rub
            )
            if previous.instrument_uid == instrument_uid:
                available_lots += (
                    previous.lots_executed if previous.action == "buy" else -previous.lots_executed
                )
        return cash, available_lots

    def _execution_snapshot(
        self,
        user_id: UUID,
        run_id: UUID,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        snapshot = self.store.execution(user_id, run_id)
        if snapshot is None:
            raise ExecutionServiceError("execution_not_found")
        run, legs, _events = snapshot
        return run, legs

    def _require_execution_connection(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        if run.mode == "sandbox":
            self._require_sandbox_account(user_id, run)
            return
        if run.mode == "live":
            self._require_live_connection(user_id, run)
            return
        raise ExecutionServiceError("execution_mode_invalid")

    def reconcile(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        """Read at most one previously submitted request; never submit or cancel.

        A durable submitting/reconciling status may represent an ambiguous old
        request whose provider response was lost. It is safe to query that exact
        request ID, but a pending leg must never cause a provider call here.
        """
        run, legs = self._execution_snapshot(user_id, run_id)
        if run.mode == "shadow" or run.status in {"succeeded", "cancelled", "failed"}:
            return run, legs
        current = next(
            (
                leg
                for leg in legs
                if leg.status
                in {
                    "submitting",
                    "submitted",
                    "partially_filled",
                    "cancel_requested",
                    "reconciling",
                }
            ),
            None,
        )
        if current is None:
            return run, legs
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        self._require_execution_connection(user_id, run)
        self._reconcile_leg(user_id, run, current, observed_at)
        self._require_execution_connection(user_id, run)
        return self._execution_snapshot(user_id, run_id)

    def cancel(
        self,
        user_id: UUID,
        run_id: UUID,
        *,
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, tuple[ExecutionLegRecord, ...]]:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        snapshot = self.store.execution(user_id, run_id)
        if snapshot is None:
            raise ExecutionServiceError("execution_not_found")
        run, legs, _events = snapshot
        if run.mode == "sandbox":
            self._require_sandbox_account(user_id, run)
        elif run.mode == "live":
            self._require_live_connection(user_id, run)
        elif run.mode != "shadow":
            raise ExecutionServiceError("execution_mode_invalid")
        current = _current_leg(legs)
        if current is None or current.status in {
            "cancelled",
            "rejected",
            "failed",
        }:
            raise ExecutionServiceError("execution_has_no_cancellable_leg")
        if current.status == "pending":
            self.store.transition_leg(
                user_id,
                run_id=run.id,
                leg_id=current.id,
                expected_statuses=("pending",),
                new_status="cancelled",
                event_type="cancelled_before_submission",
                details={"reason": "user_cancel"},
                now=observed_at,
            )
        else:
            self._request_cancel(user_id, run, current, observed_at)
        refreshed = self.store.execution(user_id, run_id)
        if refreshed is None:
            raise ExecutionServiceError("execution_not_found")
        return refreshed[0], refreshed[1]

    def _require_sandbox_account(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        status = self.broker.status(user_id)
        if (
            not status.connected
            or status.environment != "sandbox"
            or status.account_id != run.account_id
            or run.provider_environment != "sandbox"
        ):
            raise ExecutionServiceError("sandbox_account_mismatch")

    def _require_live_connection(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
    ) -> None:
        status = self.broker.status(user_id)
        if (
            not status.connected
            or status.environment != "prod"
            or status.account_id != run.account_id
            or run.provider_environment != "prod"
            or run.live_mandate_id is None
        ):
            raise ExecutionServiceError("live_account_mismatch")

    def _reconcile_leg(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> ExecutionLegStatus:
        prefix = run.mode
        try:
            if run.mode == "live":
                state = self.broker.live_order_state(
                    user_id,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
            elif run.mode == "sandbox":
                state = self.broker.sandbox_order_state(
                    user_id,
                    request_id=str(leg.request_id),
                    price_type=leg.limit_price_type,
                )
            else:
                raise ExecutionServiceError("provider_execution_mode_invalid")
        except TBankNotFound:
            code = f"{prefix}_order_not_found_yet"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return "reconciling"
        except (TBankUnavailable, BrokerConnectionError):
            code = f"{prefix}_reconcile_unavailable"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return "reconciling"

        self._require_execution_connection(user_id, run)
        return self._record_provider_state(
            user_id,
            run,
            leg,
            state,
            observed_at,
            expected_statuses=(
                "submitting",
                "submitted",
                "partially_filled",
                "cancel_requested",
                "reconciling",
            ),
            event_type=f"{prefix}_order_reconciled",
        )

    def _request_cancel(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        observed_at: datetime,
    ) -> None:
        if leg.status not in {
            "submitting",
            "submitted",
            "partially_filled",
            "reconciling",
            "cancel_requested",
        }:
            raise ExecutionServiceError("execution_leg_not_cancellable")
        prefix = run.mode
        if leg.status != "cancel_requested":
            self.store.transition_leg(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                expected_statuses=(
                    "submitting",
                    "submitted",
                    "partially_filled",
                    "reconciling",
                ),
                new_status="cancel_requested",
                event_type=f"{prefix}_cancel_requested",
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
        try:
            if run.mode == "live":
                result = self.broker.cancel_live_order(
                    user_id,
                    request_id=str(leg.request_id),
                )
            elif run.mode == "sandbox":
                result = self.broker.cancel_sandbox_order(
                    user_id,
                    request_id=str(leg.request_id),
                )
            else:
                raise ExecutionServiceError("provider_execution_mode_invalid")
        except TBankNotFound:
            code = f"{prefix}_cancel_order_not_found"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={
                    "request_id": str(leg.request_id),
                    "retry_post_order": False,
                },
                now=observed_at,
            )
            return
        except (TBankUnavailable, BrokerConnectionError):
            code = f"{prefix}_cancel_ambiguous"
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=code,
                details={"request_id": str(leg.request_id)},
                now=observed_at,
            )
            return

        self.store.mark_run_reconciling(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            error_code=f"{prefix}_cancel_acknowledged",
            details={
                "request_id": str(leg.request_id),
                "cancelled_at": result.cancelled_at.isoformat(),
            },
            now=observed_at,
        )

    def _record_provider_state(
        self,
        user_id: UUID,
        run: ExecutionRunRecord,
        leg: ExecutionLegRecord,
        state: TBankOrderState,
        observed_at: datetime,
        *,
        expected_statuses: tuple[ExecutionLegStatus, ...],
        event_type: str,
    ) -> ExecutionLegStatus:
        prefix = run.mode
        try:
            _validate_state_matches_leg(leg, state, prefix=prefix)
        except ExecutionServiceError as exc:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=exc.code,
                details={
                    "request_id": str(leg.request_id),
                    "provider_order_id": state.order_id,
                },
                now=observed_at,
            )
            return "reconciling"
        try:
            local_status = provider_leg_status(state.execution_report_status)
        except ExecutionStateError as exc:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=exc.code,
                details={
                    "provider_status": state.execution_report_status,
                    "request_id": str(leg.request_id),
                },
                now=observed_at,
            )
            return "reconciling"

        amount = _executed_amount(state)
        commission = _executed_commission(state)
        if leg.action == "buy" and leg.max_spend_rub is not None and amount > leg.max_spend_rub:
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=f"{prefix}_provider_overspend_detected",
                details={
                    "request_id": str(leg.request_id),
                    "amount_rub": str(amount),
                    "commission_rub": str(commission),
                },
                now=observed_at,
            )
            return "reconciling"
        if (
            leg.action == "sell"
            and local_status == "filled"
            and leg.min_proceeds_rub is not None
            and amount < leg.min_proceeds_rub
        ):
            self.store.mark_run_reconciling(
                user_id,
                run_id=run.id,
                leg_id=leg.id,
                error_code=f"{prefix}_provider_min_proceeds_breach",
                details={
                    "request_id": str(leg.request_id),
                    "amount_rub": str(amount),
                    "min_proceeds_rub": str(leg.min_proceeds_rub),
                },
                now=observed_at,
            )
            return "reconciling"

        self.store.transition_leg(
            user_id,
            run_id=run.id,
            leg_id=leg.id,
            expected_statuses=expected_statuses,
            new_status=local_status,
            event_type=event_type,
            details={
                "request_id": str(leg.request_id),
                "provider_order_id": state.order_id,
                "provider_status": state.execution_report_status,
                "lots_requested": state.lots_requested,
                "lots_executed": state.lots_executed,
                "amount_rub": str(amount),
                "commission_rub": str(commission),
            },
            observation=ExecutionLegObservation(
                provider_order_id=state.order_id,
                provider_status=state.execution_report_status,
                lots_executed=state.lots_executed,
                executed_amount_rub=amount,
                executed_commission_rub=commission,
            ),
            now=observed_at,
        )
        return local_status


def _current_leg(
    legs: tuple[ExecutionLegRecord, ...],
) -> ExecutionLegRecord | None:
    for leg in legs:
        if leg.status in {"filled", "shadow_filled"}:
            continue
        return leg
    return None


def _validate_state_matches_leg(
    leg: ExecutionLegRecord,
    state: TBankOrderState,
    *,
    prefix: str,
) -> None:
    if state.order_request_id != str(leg.request_id):
        raise ExecutionServiceError(f"{prefix}_request_id_mismatch")
    if state.instrument_uid != leg.instrument_uid:
        raise ExecutionServiceError(f"{prefix}_instrument_mismatch")
    if state.lots_requested != leg.lots_requested:
        raise ExecutionServiceError(f"{prefix}_lot_count_mismatch")
    expected_direction = {
        "buy": "ORDER_DIRECTION_BUY",
        "sell": "ORDER_DIRECTION_SELL",
    }[leg.action]
    if state.direction and state.direction != expected_direction:
        raise ExecutionServiceError(f"{prefix}_direction_mismatch")
    if state.order_type and state.order_type != "ORDER_TYPE_LIMIT":
        raise ExecutionServiceError(f"{prefix}_order_type_mismatch")


def _executed_amount(state: TBankOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.total_order_amount is None:
        raise ExecutionServiceError("provider_executed_amount_missing")
    return _rub(state.total_order_amount)


def _executed_commission(state: TBankOrderState) -> Decimal:
    if state.lots_executed <= 0:
        return Decimal("0")
    if state.executed_commission is None:
        raise ExecutionServiceError("provider_executed_commission_missing")
    return _rub(state.executed_commission)


def _rub(value: TBankMoney) -> Decimal:
    if value.currency.upper() != "RUB":
        raise ExecutionServiceError("provider_money_not_rub")
    amount = Decimal(value.value)
    if not amount.is_finite() or amount < 0:
        raise ExecutionServiceError("provider_money_invalid")
    return amount
