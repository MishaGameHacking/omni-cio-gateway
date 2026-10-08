"""Immutable proposals, exact consent, bounded mandates and execution recovery ledgers."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from .db import Database, live_execution_lock_key
from .execution import (
    ExecutionLegStatus,
    ExecutionMode,
    ExecutionRunStatus,
    run_status_for_legs,
)
from .strategy import POLICY_KEYS, PROFILE_LIMITS

_TERMINAL_RUNS = {"succeeded", "cancelled", "failed"}
_TERMINAL_LEGS = {"filled", "cancelled", "rejected", "failed", "shadow_filled"}


class ExecutionLedgerError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class StrategyExecutionContext:
    session_digest: bytes
    legal_versions: dict[str, str]
    payload: dict[str, Any]
    limits: tuple[Decimal, Decimal] | None = None


@dataclass(frozen=True, slots=True)
class ExecutionLegObservation:
    provider_order_id: str | None = None
    provider_status: str | None = None
    lots_executed: int | None = None
    executed_amount_rub: Decimal | None = None
    executed_commission_rub: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ExecutionRunRecord:
    id: UUID
    user_id: UUID
    proposal_id: UUID
    confirmed_action_id: int
    proposal_version: int
    proposal_hash: bytes
    account_id: str
    mode: ExecutionMode
    provider_environment: str | None
    live_mandate_id: UUID | None
    status: ExecutionRunStatus
    error_code: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class LiveExecutionMandateRecord:
    id: UUID
    user_id: UUID
    account_id: str
    max_order_notional_rub: Decimal
    max_daily_notional_rub: Decimal
    created_session_digest: bytes
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExecutionLegRecord:
    id: UUID
    run_id: UUID
    user_id: UUID
    leg_index: int
    action: str
    instrument_uid: str
    lots_requested: int
    lots_executed: int
    limit_price: Decimal
    limit_price_type: str
    max_spend_rub: Decimal | None
    min_proceeds_rub: Decimal | None
    request_id: UUID
    provider_order_id: str | None
    provider_status: str
    status: ExecutionLegStatus
    executed_amount_rub: Decimal
    executed_commission_rub: Decimal
    submitted_at: datetime | None
    last_checked_at: datetime | None
    terminal_at: datetime | None


@dataclass(frozen=True, slots=True)
class ExecutionEventRecord:
    id: int
    run_id: UUID
    leg_id: UUID | None
    user_id: UUID
    event_type: str
    details: dict[str, Any]
    created_at: datetime


def _validate_leg_transition_request(
    expected_statuses: tuple[ExecutionLegStatus, ...],
    event_type: str,
) -> None:
    if not expected_statuses:
        raise ValueError("execution transition requires expected status")
    if not event_type or len(event_type) > 128:
        raise ValueError("execution event type is invalid")


def _require_live_transition_mandate(
    cur: Any,
    *,
    user_id: UUID,
    run: ExecutionRunRecord,
    new_status: ExecutionLegStatus,
    observed_at: datetime,
) -> None:
    if run.mode != "live" or new_status != "submitting":
        return
    if run.live_mandate_id is None:
        raise ExecutionLedgerError("live_mandate_inactive")
    cur.execute(
        """
        SELECT 1
        FROM portfolio_live_execution_mandates
        WHERE id = %s
          AND user_id = %s
          AND account_id = %s
          AND revoked_at IS NULL
          AND expires_at > %s
        FOR SHARE
        """,
        (
            run.live_mandate_id,
            user_id,
            run.account_id,
            observed_at,
        ),
    )
    if cur.fetchone() is None:
        raise ExecutionLedgerError("live_mandate_inactive")


def _transition_values(
    leg: ExecutionLegRecord,
    *,
    lots_executed: int | None,
    executed_amount_rub: Decimal | None,
    executed_commission_rub: Decimal | None,
) -> tuple[int, Decimal, Decimal]:
    next_lots = leg.lots_executed if lots_executed is None else lots_executed
    if next_lots < 0 or next_lots > leg.lots_requested:
        raise ValueError("executed lots are outside requested bounds")
    # A delayed reconciliation cannot undo a fill already recorded under the
    # row lock. Monetary corrections remain allowed: provider fees may change.
    if next_lots < leg.lots_executed:
        raise ExecutionLedgerError("execution_leg_state_changed")
    next_amount = leg.executed_amount_rub if executed_amount_rub is None else executed_amount_rub
    next_commission = (
        leg.executed_commission_rub if executed_commission_rub is None else executed_commission_rub
    )
    if next_amount < 0 or next_commission < 0:
        raise ValueError("execution money values must be non-negative")
    return next_lots, next_amount, next_commission


class ExecutionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _tenant(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "SELECT set_config('omnicio.user_id', %s, true)",
            (str(user_id),),
        )

    @staticmethod
    def _strategy_authority(
        cur: Any,
        user_id: UUID,
        session_digest: bytes,
        legal_versions: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        if (
            len(session_digest) != 32
            or not legal_versions
            or any(not v for v in legal_versions.values())
        ):
            raise ExecutionLedgerError("execution_authority_missing")
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (live_execution_lock_key(user_id),),
        )
        cur.execute(
            "SELECT s.id FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.user_id = %s AND s.token_digest = %s AND s.revoked_at IS NULL "
            "AND s.expires_at > now() AND u.status = 'active' FOR SHARE OF s, u",
            (user_id, session_digest),
        )
        if cur.fetchone() is None:
            raise ExecutionLedgerError("execution_session_revoked")
        for kind, version in legal_versions.items():
            cur.execute(
                "SELECT 1 FROM legal_acceptances WHERE user_id=%s AND document_type=%s "
                "AND document_version=%s FOR SHARE",
                (user_id, kind, version),
            )
            if cur.fetchone() is None:
                raise ExecutionLedgerError("execution_consent_required")
        cur.execute(
            "SELECT account_id, environment, verified_at FROM tbank_connection "
            "WHERE user_id=%s FOR SHARE",
            (user_id,),
        )
        connection = cur.fetchone()
        cur.execute(
            "SELECT version, document FROM strategy_drafts WHERE user_id=%s FOR SHARE", (user_id,)
        )
        strategy = cur.fetchone()
        if (
            not connection
            or not strategy
            or connection["account_id"] != payload["account_id"]
            or connection["environment"] != payload["environment"]
            or connection["verified_at"].isoformat() != payload["connection_verified_at"]
            or strategy["version"] != payload["strategy_version"]
            or strategy["document"] != payload["document"]
        ):
            raise ExecutionLedgerError("execution_context_changed")
        if "evidence_version" in payload:
            cur.execute(
                "SELECT version FROM strategy_research_evidence WHERE user_id=%s FOR SHARE",
                (user_id,),
            )
            evidence = cur.fetchone()
            if (evidence["version"] if evidence else 0) != payload["evidence_version"]:
                raise ExecutionLedgerError("execution_research_evidence_changed")

    def authorize_strategy(
        self,
        user_id: UUID,
        *,
        session_digest: bytes,
        legal_versions: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        cur: Any
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            self._strategy_authority(cur, user_id, session_digest, legal_versions, payload)

    @staticmethod
    def _materialize_policy(cur: Any, user_id: UUID, document: dict[str, Any]) -> tuple[int, int]:
        versions = []
        for table, group, keys in (
            (
                "investment_profile_versions",
                "profile",
                (*PROFILE_LIMITS, "allow_below_investment_grade"),
            ),
            ("balancing_policy_versions", "policy", POLICY_KEYS),
        ):
            values = document[group]
            if any(values[key] is None for key in keys):
                raise ExecutionLedgerError("execution_policy_incomplete")
            # Table/column identifiers are compile-time constants, never request input.
            cur.execute(
                f"SELECT * FROM {table} WHERE user_id=%s ORDER BY version DESC LIMIT 1", (user_id,)
            )
            current = cur.fetchone()
            if current and all(
                str(current[key]) == str(values[key])
                or (
                    not isinstance(values[key], bool)
                    and Decimal(str(current[key])) == Decimal(str(values[key]))
                )
                for key in keys
            ):
                versions.append(current["version"])
                continue
            version = current["version"] + 1 if current else 1
            placeholders = ", ".join(["%s"] * (len(keys) + 2))
            cur.execute(
                f"INSERT INTO {table} (user_id, version, {', '.join(keys)}) "
                f"VALUES ({placeholders})",
                (user_id, version, *(values[key] for key in keys)),
            )
            versions.append(version)
        return versions[0], versions[1]

    def save_strategy_proposal(
        self,
        user_id: UUID,
        *,
        payload: dict[str, Any],
        session_digest: bytes,
        legal_versions: dict[str, str],
    ) -> dict[str, Any]:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode()).digest()
        ident = uuid4()
        cur: Any
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            self._strategy_authority(cur, user_id, session_digest, legal_versions, payload)
            profile, policy = self._materialize_policy(cur, user_id, payload["document"])
            cur.execute(
                "SELECT COALESCE(max(version), 0)+1 AS version FROM "
                "portfolio_proposals WHERE user_id=%s",
                (user_id,),
            )
            version = cur.fetchone()["version"]
            sell = next(
                (leg["instrument_uid"] for leg in payload["legs"] if leg["action"] == "sell"), None
            )
            buy = next(
                (leg["instrument_uid"] for leg in payload["legs"] if leg["action"] == "buy"), None
            )
            cur.execute(
                "INSERT INTO portfolio_proposals (id,user_id,version,source_snapshot_id,account_id,"
                "profile_version,policy_version,scenario_kind,target_instrument_uid,replaced_instrument_uid,"
                "proposal_hash,created_session_digest,payload,expires_at) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING "
                "created_at,expires_at",
                (
                    ident,
                    user_id,
                    version,
                    payload["source_snapshot_id"],
                    payload["account_id"],
                    profile,
                    policy,
                    "replace" if sell else "deploy_cash",
                    buy,
                    sell,
                    digest,
                    session_digest,
                    encoded,
                    datetime.fromisoformat(payload["expires_at"]),
                ),
            )
            dates = dict(cur.fetchone())
        return {
            "id": str(ident),
            "version": version,
            "proposal_hash": digest.hex(),
            **dates,
            "payload": payload,
            "status": "ready",
        }

    def strategy_proposal(self, user_id: UUID, proposal_id: UUID) -> dict[str, Any]:
        cur: Any
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                "SELECT * FROM portfolio_proposals WHERE id=%s AND user_id=%s",
                (proposal_id, user_id),
            )
            row = cur.fetchone()
            if row is None or row["payload"].get("engine") != "strategy_execution_1":
                raise ExecutionLedgerError("execution_proposal_not_found")
            return dict(row)

    def confirm_strategy_proposal(
        self,
        user_id: UUID,
        proposal_id: UUID,
        *,
        proposal_version: int,
        proposal_hash: str,
        expected_strategy_version: int,
        session_digest: bytes,
        legal_versions: dict[str, str],
        live_enabled: bool,
        sandbox_enabled: bool,
        global_max_order: Decimal,
        global_max_daily: Decimal,
    ) -> UUID:
        cur: Any
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            # Match disconnect/account deletion: owner lock precedes financial row locks.
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (live_execution_lock_key(user_id),),
            )
            cur.execute(
                "SELECT * FROM portfolio_proposals WHERE id=%s AND user_id=%s FOR SHARE",
                (proposal_id, user_id),
            )
            proposal = cur.fetchone()
            if not proposal or proposal["payload"].get("engine") != "strategy_execution_1":
                raise ExecutionLedgerError("execution_proposal_not_found")
            payload = proposal["payload"]
            self._strategy_authority(cur, user_id, session_digest, legal_versions, payload)
            if (
                proposal["version"] != proposal_version
                or not hmac.compare_digest(bytes(proposal["proposal_hash"]).hex(), proposal_hash)
                or payload["strategy_version"] != expected_strategy_version
                or not hmac.compare_digest(
                    bytes(proposal["created_session_digest"]), session_digest
                )
            ):
                raise ExecutionLedgerError("execution_confirmation_mismatch")
            mode = payload["mode"]
            if mode == "live" and not live_enabled or mode == "sandbox" and not sandbox_enabled:
                raise ExecutionLedgerError("execution_deployment_disabled")
            cur.execute(
                "SELECT id FROM portfolio_execution_runs WHERE proposal_id=%s AND user_id=%s",
                (proposal_id, user_id),
            )
            existing = cur.fetchone()
            if existing:
                return cast(UUID, existing["id"])
            if proposal["expires_at"] <= datetime.now(UTC):
                raise ExecutionLedgerError("execution_proposal_expired")
            cur.execute(
                "SELECT id FROM portfolio_execution_runs WHERE user_id=%s "
                "AND status IN ('created','running','reconciling') LIMIT 1",
                (user_id,),
            )
            if cur.fetchone():
                raise ExecutionLedgerError("execution_run_already_active")
            mandate = self._validate_plan_budget(
                cur, user_id, payload, global_max_order, global_max_daily
            )
            cur.execute(
                "INSERT INTO portfolio_proposal_actions "
                "(proposal_id,user_id,action,proposal_version,"
                "proposal_hash,session_digest) VALUES (%s,%s,'confirmed',%s,%s,%s) RETURNING id",
                (proposal_id, user_id, proposal_version, proposal["proposal_hash"], session_digest),
            )
            action_id = cur.fetchone()["id"]
            ident = uuid4()
            cur.execute(
                "INSERT INTO portfolio_execution_runs (id,user_id,proposal_id,confirmed_action_id,"
                "proposal_version,proposal_hash,account_id,mode,provider_environment,live_mandate_id,"
                "created_session_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ident,
                    user_id,
                    proposal_id,
                    action_id,
                    proposal_version,
                    proposal["proposal_hash"],
                    payload["account_id"],
                    mode,
                    None if mode == "shadow" else payload["environment"],
                    mandate,
                    session_digest,
                ),
            )
            for index, leg in enumerate(payload["legs"]):
                cur.execute(
                    "INSERT INTO portfolio_execution_legs (id,run_id,user_id,leg_index,action,"
                    "instrument_uid,lots_requested,limit_price,limit_price_type,max_spend_rub,"
                    "min_proceeds_rub,request_id) VALUES "
                    "(%s,%s,%s,%s,%s,%s,%s,%s,'currency',%s,%s,%s)",
                    (
                        uuid4(),
                        ident,
                        user_id,
                        index,
                        leg["action"],
                        leg["instrument_uid"],
                        leg["lots"],
                        leg["limit_price"],
                        leg["max_spend_rub"],
                        leg["min_proceeds_rub"],
                        uuid4(),
                    ),
                )
            self._append_event(
                cur,
                user_id=user_id,
                run_id=ident,
                leg_id=None,
                event_type="strategy_confirmed",
                details={"strategy_version": payload["strategy_version"], "mode": mode},
            )
            return ident

    @staticmethod
    def _validate_plan_budget(
        cur: Any,
        user_id: UUID,
        payload: dict[str, Any],
        global_order: Decimal,
        global_daily: Decimal,
        exclude_run_id: UUID | None = None,
    ) -> UUID | None:
        if payload["mode"] != "live":
            return None
        cur.execute(
            "SELECT * FROM portfolio_live_execution_mandates WHERE user_id=%s AND account_id=%s "
            "AND revoked_at IS NULL AND expires_at>now() ORDER BY created_at "
            "DESC LIMIT 1 FOR SHARE",
            (user_id, payload["account_id"]),
        )
        mandate = cur.fetchone()
        if not mandate:
            raise ExecutionLedgerError("live_mandate_inactive")
        order_cap = min(global_order, mandate["max_order_notional_rub"])
        daily_cap = min(global_daily, mandate["max_daily_notional_rub"])
        cur.execute(
            "WITH trading_day AS (SELECT date_trunc('day',now() AT TIME ZONE "
            "'Europe/Moscow') AT TIME ZONE 'Europe/Moscow' AS starts_at) "
            "SELECT COALESCE(sum(CASE WHEN p.payload->>'engine'='strategy_execution_1' "
            "THEN (p.payload->>'gross_turnover_rub')::numeric ELSE "
            "(SELECT COALESCE(sum(GREATEST(l.executed_amount_rub, "
            "COALESCE(l.max_spend_rub,l.min_proceeds_rub,0))+l.executed_commission_rub),0) "
            "FROM portfolio_execution_legs l WHERE l.run_id=r.id "
            "AND l.user_id=r.user_id) END),0) AS used "
            "FROM portfolio_execution_runs r JOIN portfolio_proposals p ON p.id=r.proposal_id "
            "CROSS JOIN trading_day d WHERE r.user_id=%s AND r.mode='live' AND "
            "(r.status IN ('created','running','reconciling') OR r.created_at>=d.starts_at "
            "OR EXISTS (SELECT 1 FROM portfolio_execution_legs activity "
            "WHERE activity.run_id=r.id AND activity.user_id=r.user_id AND "
            "(activity.submitted_at>=d.starts_at OR activity.terminal_at>=d.starts_at))) "
            "AND r.id<>%s",
            (user_id, exclude_run_id or UUID(int=0)),
        )
        used = cur.fetchone()["used"]
        if (
            any(Decimal(leg["gross_amount_rub"]) > order_cap for leg in payload["legs"])
            or used + Decimal(payload["gross_turnover_rub"]) > daily_cap
        ):
            raise ExecutionLedgerError("live_notional_cap_exceeded")
        return cast(UUID, mandate["id"])

    def create_strategy_mandate(
        self,
        user_id: UUID,
        *,
        payload: dict[str, Any],
        session_digest: bytes,
        legal_versions: dict[str, str],
        max_order: Decimal,
        max_daily: Decimal,
        expires_at: datetime,
        global_max_order: Decimal,
        global_max_daily: Decimal,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        if (
            not max_order.is_finite()
            or not max_daily.is_finite()
            or not 0 < max_order <= global_max_order
            or not max_order <= max_daily <= global_max_daily
            or expires_at.tzinfo is None
            or not now < expires_at <= now + timedelta(days=1)
        ):
            raise ExecutionLedgerError("live_mandate_bounds_invalid")
        cur: Any
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            self._strategy_authority(cur, user_id, session_digest, legal_versions, payload)
            cur.execute(
                "SELECT id FROM portfolio_live_execution_mandates WHERE "
                "user_id=%s AND revoked_at IS NULL "
                "AND expires_at>now()",
                (user_id,),
            )
            if cur.fetchone():
                raise ExecutionLedgerError("live_mandate_already_active")
            cur.execute(
                "UPDATE portfolio_live_execution_mandates SET revoked_at=now() "
                "WHERE user_id=%s AND revoked_at IS NULL AND expires_at<=now()",
                (user_id,),
            )
            cur.execute(
                "INSERT INTO portfolio_live_execution_mandates "
                "(user_id,account_id,max_order_notional_rub,"
                "max_daily_notional_rub,created_session_digest,expires_at) VALUES "
                "(%s,%s,%s,%s,%s,%s) RETURNING *",
                (user_id, payload["account_id"], max_order, max_daily, session_digest, expires_at),
            )
            result = dict(cur.fetchone())
            result.pop("created_session_digest")
            return result

    def live_mandate(
        self,
        user_id: UUID,
        *,
        account_id: str | None = None,
        now: datetime | None = None,
    ) -> LiveExecutionMandateRecord | None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            select_sql = """
                SELECT
                    id,
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at,
                    revoked_at
                FROM portfolio_live_execution_mandates
                WHERE user_id = %s
                  AND revoked_at IS NULL
                  AND expires_at > %s
            """
            if account_id is None:
                cur.execute(
                    select_sql + " ORDER BY created_at DESC LIMIT 1",
                    (user_id, observed_at),
                )
            else:
                cur.execute(
                    select_sql + " AND account_id = %s ORDER BY created_at DESC LIMIT 1",
                    (user_id, observed_at, account_id),
                )
            row = cur.fetchone()
            return _mandate_record(cast(dict[str, Any], row)) if row is not None else None

    def revoke_live_mandate(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
    ) -> LiveExecutionMandateRecord | None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                """
                UPDATE portfolio_live_execution_mandates
                SET revoked_at = %s
                WHERE user_id = %s
                  AND revoked_at IS NULL
                RETURNING
                    id,
                    user_id,
                    account_id,
                    max_order_notional_rub,
                    max_daily_notional_rub,
                    created_session_digest,
                    created_at,
                    expires_at,
                    revoked_at
                """,
                (observed_at, user_id),
            )
            row = cur.fetchone()
            return _mandate_record(cast(dict[str, Any], row)) if row is not None else None

    def has_active_live_execution(self, user_id: UUID) -> bool:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT 1
                FROM portfolio_execution_runs
                WHERE user_id = %s
                  AND mode = 'live'
                  AND status IN ('created', 'running', 'reconciling')
                LIMIT 1
                """,
                (user_id,),
            )
            return cur.fetchone() is not None

    def execution(
        self,
        user_id: UUID,
        run_id: UUID,
    ) -> (
        tuple[
            ExecutionRunRecord,
            tuple[ExecutionLegRecord, ...],
            tuple[ExecutionEventRecord, ...],
        ]
        | None
    ):
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE id = %s
                  AND user_id = %s
                """,
                (run_id, user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            run = _run_record(cast(dict[str, Any], row))
            legs = self._legs(cur, user_id, run.id)
            cur.execute(
                """
                SELECT
                    id,
                    run_id,
                    leg_id,
                    user_id,
                    event_type,
                    details,
                    created_at
                FROM portfolio_execution_events
                WHERE run_id = %s
                  AND user_id = %s
                ORDER BY id
                """,
                (run_id, user_id),
            )
            events = tuple(_event_record(cast(dict[str, Any], item)) for item in cur.fetchall())
            return run, legs, events

    def executions(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
    ) -> tuple[ExecutionRunRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("execution limit must be between 1 and 100")
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE user_id = %s
                ORDER BY (status IN ('created', 'running', 'reconciling')) DESC,
                         created_at DESC, id DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return tuple(_run_record(cast(dict[str, Any], row)) for row in cur.fetchall())

    def transition_leg(
        self,
        user_id: UUID,
        *,
        run_id: UUID,
        leg_id: UUID,
        expected_statuses: tuple[ExecutionLegStatus, ...],
        new_status: ExecutionLegStatus,
        event_type: str,
        details: dict[str, object],
        observation: ExecutionLegObservation | None = None,
        now: datetime | None = None,
        strategy_context: StrategyExecutionContext | None = None,
    ) -> tuple[ExecutionRunRecord, ExecutionLegRecord]:
        _validate_leg_transition_request(expected_statuses, event_type)
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        update = observation or ExecutionLegObservation()

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            if strategy_context is not None:
                self._strategy_authority(
                    cur,
                    user_id,
                    strategy_context.session_digest,
                    strategy_context.legal_versions,
                    strategy_context.payload,
                )
                if strategy_context.limits is not None:
                    self._validate_plan_budget(
                        cur,
                        user_id,
                        strategy_context.payload,
                        *strategy_context.limits,
                        exclude_run_id=run_id,
                    )
            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                FROM portfolio_execution_runs
                WHERE id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (run_id, user_id),
            )
            run_row = cur.fetchone()
            if run_row is None:
                raise ExecutionLedgerError("execution_not_found")
            run = _run_record(cast(dict[str, Any], run_row))
            if run.status in _TERMINAL_RUNS:
                raise ExecutionLedgerError("execution_already_terminal")

            _require_live_transition_mandate(
                cur,
                user_id=user_id,
                run=run,
                new_status=new_status,
                observed_at=observed_at,
            )

            cur.execute(
                """
                SELECT
                    id,
                    run_id,
                    user_id,
                    leg_index,
                    action,
                    instrument_uid,
                    lots_requested,
                    lots_executed,
                    limit_price,
                    limit_price_type,
                    max_spend_rub,
                    min_proceeds_rub,
                    request_id,
                    provider_order_id,
                    provider_status,
                    status,
                    executed_amount_rub,
                    executed_commission_rub,
                    submitted_at,
                    last_checked_at,
                    terminal_at
                FROM portfolio_execution_legs
                WHERE id = %s
                  AND run_id = %s
                  AND user_id = %s
                FOR UPDATE
                """,
                (leg_id, run_id, user_id),
            )
            leg_row = cur.fetchone()
            if leg_row is None:
                raise ExecutionLedgerError("execution_leg_not_found")
            leg = _leg_record(cast(dict[str, Any], leg_row))
            if leg.status not in expected_statuses:
                raise ExecutionLedgerError("execution_leg_state_changed")
            if (update.provider_status is not None and leg.last_checked_at is not None
                    and observed_at < leg.last_checked_at):
                raise ExecutionLedgerError("execution_leg_state_changed")

            next_lots, next_amount, next_commission = _transition_values(
                leg,
                lots_executed=update.lots_executed,
                executed_amount_rub=update.executed_amount_rub,
                executed_commission_rub=update.executed_commission_rub,
            )

            terminal_at = observed_at if new_status in _TERMINAL_LEGS else None
            cur.execute(
                """
                UPDATE portfolio_execution_legs
                SET
                    status = %s,
                    provider_order_id = COALESCE(%s, provider_order_id),
                    provider_status = COALESCE(%s, provider_status),
                    lots_executed = %s,
                    executed_amount_rub = %s,
                    executed_commission_rub = %s,
                    submitted_at = CASE
                        WHEN submitted_at IS NULL
                         AND %s IN (
                            'submitted',
                            'partially_filled',
                            'filled',
                            'reconciling'
                         )
                        THEN %s
                        ELSE submitted_at
                    END,
                    last_checked_at = CASE
                        WHEN %s::text IS NOT NULL THEN %s
                        ELSE last_checked_at
                    END,
                    terminal_at = COALESCE(%s, terminal_at)
                WHERE id = %s
                  AND run_id = %s
                  AND user_id = %s
                RETURNING
                    id,
                    run_id,
                    user_id,
                    leg_index,
                    action,
                    instrument_uid,
                    lots_requested,
                    lots_executed,
                    limit_price,
                    limit_price_type,
                    max_spend_rub,
                    min_proceeds_rub,
                    request_id,
                    provider_order_id,
                    provider_status,
                    status,
                    executed_amount_rub,
                    executed_commission_rub,
                    submitted_at,
                    last_checked_at,
                    terminal_at
                """,
                (
                    new_status,
                    update.provider_order_id,
                    update.provider_status,
                    next_lots,
                    next_amount,
                    next_commission,
                    new_status,
                    observed_at,
                    update.provider_status,
                    observed_at,
                    terminal_at,
                    leg_id,
                    run_id,
                    user_id,
                ),
            )
            updated_row = cur.fetchone()
            if updated_row is None:
                raise RuntimeError("execution leg update returned no row")
            updated_leg = _leg_record(cast(dict[str, Any], updated_row))

            self._append_event(
                cur,
                user_id=user_id,
                run_id=run_id,
                leg_id=leg_id,
                event_type=event_type,
                details=details,
            )

            legs = self._legs(cur, user_id, run_id)
            derived = run_status_for_legs(tuple(item.status for item in legs))
            finished_at = observed_at if derived in _TERMINAL_RUNS else None
            cur.execute(
                """
                UPDATE portfolio_execution_runs
                SET
                    status = %s,
                    updated_at = %s,
                    finished_at = %s,
                    error_code = CASE
                        WHEN %s = 'failed' AND error_code = ''
                        THEN %s
                        ELSE error_code
                    END
                WHERE id = %s
                  AND user_id = %s
                RETURNING
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                """,
                (
                    derived,
                    observed_at,
                    finished_at,
                    derived,
                    event_type,
                    run_id,
                    user_id,
                ),
            )
            updated_run_row = cur.fetchone()
            if updated_run_row is None:
                raise RuntimeError("execution run update returned no row")
            return (
                _run_record(cast(dict[str, Any], updated_run_row)),
                updated_leg,
            )

    def mark_run_reconciling(
        self,
        user_id: UUID,
        *,
        run_id: UUID,
        leg_id: UUID,
        error_code: str,
        details: dict[str, object],
        now: datetime | None = None,
    ) -> tuple[ExecutionRunRecord, ExecutionLegRecord]:
        run, leg = self.transition_leg(
            user_id,
            run_id=run_id,
            leg_id=leg_id,
            expected_statuses=(
                "submitting",
                "submitted",
                "partially_filled",
                "cancel_requested",
                "reconciling",
            ),
            new_status="reconciling",
            event_type=error_code,
            details=details,
            now=now,
        )
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                UPDATE portfolio_execution_runs
                SET error_code = %s, updated_at = %s
                WHERE id = %s
                  AND user_id = %s
                  AND status = 'reconciling'
                RETURNING
                    id,
                    user_id,
                    proposal_id,
                    confirmed_action_id,
                    proposal_version,
                    proposal_hash,
                    account_id,
                    mode,
                    provider_environment,
                    live_mandate_id,
                    status,
                    error_code,
                    created_at,
                    updated_at,
                    finished_at
                """,
                (
                    error_code[:128],
                    (now or datetime.now(UTC)).astimezone(UTC),
                    run_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            if row is not None:
                run = _run_record(cast(dict[str, Any], row))
        return run, leg

    @staticmethod
    def _append_event(
        cur: Any,
        *,
        user_id: UUID,
        run_id: UUID,
        leg_id: UUID | None,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        cur.execute(
            """
            INSERT INTO portfolio_execution_events (
                run_id,
                leg_id,
                user_id,
                event_type,
                details
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                run_id,
                leg_id,
                user_id,
                event_type,
                json.dumps(details, separators=(",", ":"), sort_keys=True),
            ),
        )

    @staticmethod
    def _legs(
        cur: Any,
        user_id: UUID,
        run_id: UUID,
    ) -> tuple[ExecutionLegRecord, ...]:
        cur.execute(
            """
            SELECT
                id,
                run_id,
                user_id,
                leg_index,
                action,
                instrument_uid,
                lots_requested,
                lots_executed,
                limit_price,
                limit_price_type,
                max_spend_rub,
                min_proceeds_rub,
                request_id,
                provider_order_id,
                provider_status,
                status,
                executed_amount_rub,
                executed_commission_rub,
                submitted_at,
                last_checked_at,
                terminal_at
            FROM portfolio_execution_legs
            WHERE run_id = %s
              AND user_id = %s
            ORDER BY leg_index
            """,
            (run_id, user_id),
        )
        return tuple(_leg_record(cast(dict[str, Any], row)) for row in cur.fetchall())


def _run_record(row: dict[str, Any]) -> ExecutionRunRecord:
    return ExecutionRunRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        proposal_id=cast(UUID, row["proposal_id"]),
        confirmed_action_id=int(row["confirmed_action_id"]),
        proposal_version=int(row["proposal_version"]),
        proposal_hash=bytes(row["proposal_hash"]),
        account_id=str(row["account_id"]),
        mode=cast(ExecutionMode, row["mode"]),
        provider_environment=cast(str | None, row["provider_environment"]),
        live_mandate_id=cast(UUID | None, row["live_mandate_id"]),
        status=cast(ExecutionRunStatus, row["status"]),
        error_code=str(row["error_code"]),
        created_at=cast(datetime, row["created_at"]),
        updated_at=cast(datetime, row["updated_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
    )


def _mandate_record(row: dict[str, Any]) -> LiveExecutionMandateRecord:
    return LiveExecutionMandateRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        account_id=str(row["account_id"]),
        max_order_notional_rub=Decimal(row["max_order_notional_rub"]),
        max_daily_notional_rub=Decimal(row["max_daily_notional_rub"]),
        created_session_digest=bytes(row["created_session_digest"]),
        created_at=cast(datetime, row["created_at"]),
        expires_at=cast(datetime, row["expires_at"]),
        revoked_at=cast(datetime | None, row["revoked_at"]),
    )


def _leg_record(row: dict[str, Any]) -> ExecutionLegRecord:
    return ExecutionLegRecord(
        id=cast(UUID, row["id"]),
        run_id=cast(UUID, row["run_id"]),
        user_id=cast(UUID, row["user_id"]),
        leg_index=int(row["leg_index"]),
        action=str(row["action"]),
        instrument_uid=str(row["instrument_uid"]),
        lots_requested=int(row["lots_requested"]),
        lots_executed=int(row["lots_executed"]),
        limit_price=Decimal(row["limit_price"]),
        limit_price_type=str(row["limit_price_type"]),
        max_spend_rub=(Decimal(row["max_spend_rub"]) if row["max_spend_rub"] is not None else None),
        min_proceeds_rub=(
            Decimal(row["min_proceeds_rub"]) if row["min_proceeds_rub"] is not None else None
        ),
        request_id=cast(UUID, row["request_id"]),
        provider_order_id=cast(str | None, row["provider_order_id"]),
        provider_status=str(row["provider_status"]),
        status=cast(ExecutionLegStatus, row["status"]),
        executed_amount_rub=Decimal(row["executed_amount_rub"]),
        executed_commission_rub=Decimal(row["executed_commission_rub"]),
        submitted_at=cast(datetime | None, row["submitted_at"]),
        last_checked_at=cast(datetime | None, row["last_checked_at"]),
        terminal_at=cast(datetime | None, row["terminal_at"]),
    )


def _event_record(row: dict[str, Any]) -> ExecutionEventRecord:
    return ExecutionEventRecord(
        id=int(row["id"]),
        run_id=cast(UUID, row["run_id"]),
        leg_id=cast(UUID | None, row["leg_id"]),
        user_id=cast(UUID, row["user_id"]),
        event_type=str(row["event_type"]),
        details=dict(cast(dict[str, Any], row["details"])),
        created_at=cast(datetime, row["created_at"]),
    )
