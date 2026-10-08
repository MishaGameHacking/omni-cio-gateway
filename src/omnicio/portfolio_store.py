"""Persistence boundary for durable portfolio observation and user policy data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Any, Literal, cast
from uuid import UUID

from psycopg import DatabaseError

from .broker import AnalysisSource, BrokerObservationBundle
from .db import Database, live_execution_lock_key
from .freshness import PORTFOLIO_MAX_AGE
from .intelligence import (
    EVIDENCE_RETRIEVAL_MAX_AGE,
    EvidenceDocument,
    InstrumentRiskAssessment,
)
from .payouts import PAYOUT_READ_CTES
from .portfolio import SecurityExposure, analyze_portfolio
from .strategy import document_hash, normalize_document
from .tbank import (
    TBankAccount,
    TBankInstrumentMetadata,
    TBankMoney,
    TBankOperation,
    TBankOperationsPage,
    TBankPortfolioPosition,
    TBankUserInfo,
)

_ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))"
REFRESH_JOB_TYPE = "portfolio_refresh"
REFRESH_COOLDOWN_SECONDS = 60
REFRESH_MAX_ATTEMPTS = 3
DAILY_MAX_ATTEMPTS = 3
MONITORING_FULL_INTERVAL = timedelta(hours=1)


def _has_refresh_legal(cur: Any, user_id: UUID, versions: object) -> bool:
    if not isinstance(versions, dict) or set(versions) != {
        "privacy_policy", "personal_data_consent", "terms",
    } or any(not isinstance(value, str) or not value for value in versions.values()):
        return False
    cur.execute(
        "SELECT NOT EXISTS (SELECT 1 FROM jsonb_each_text(%s::jsonb) AS v "
        "WHERE NOT EXISTS (SELECT 1 FROM legal_acceptances a WHERE a.user_id = %s "
        "AND a.document_type = v.key AND a.document_version = v.value)) AS accepted",
        (_json(versions), user_id),
    )
    row = cur.fetchone()
    return row is not None and bool(row["accepted"])


def _refresh_context_matches(context: object, connection: Mapping[str, Any]) -> bool:
    if not isinstance(context, dict):
        return False
    return context == {
        "account_id": connection["account_id"],
        "environment": connection["environment"],
        "verified_at": connection["verified_at"].astimezone(UTC).isoformat(),
    }


def _require_observation_context(cur: Any, user_id: UUID, connection: Mapping[str, Any]) -> None:
    details = connection["details"]
    if connection["job_type"] != REFRESH_JOB_TYPE and "connection" not in details:
        # Accepted legacy daily records remain readable on rollback. Every new
        # scheduled run records the same connection/consent context as refresh.
        return
    if not _refresh_context_matches(details.get("connection"), connection):
        raise ObservationCancelled("observation_connection_changed")
    if not _has_refresh_legal(cur, user_id, details.get("legal_versions")):
        raise ObservationCancelled("observation_consent_changed")


class SettingsVersionConflict(ValueError):
    """The user's draft was based on a different saved settings version."""


class ObservationCancelled(ValueError):
    """The observation lost its connected account or its running job."""


def _require_observation_job(
    cur: Any,
    user_id: UUID,
    job_run_id: UUID,
    *,
    account_id: str | None = None,
    environment: str | None = None,
    snapshot_id: UUID | None = None,
) -> None:
    # Cleanup and these short writes share one lock. Never hold it across broker I/O.
    cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
    cur.execute(
        """
        SELECT c.account_id, c.environment, c.verified_at, j.job_type, j.details
        FROM job_runs AS j
        JOIN users AS u ON u.id = j.user_id
        JOIN tbank_connection AS c ON c.user_id = j.user_id
        WHERE j.id = %s AND j.user_id = %s
          AND j.job_type IN ('portfolio_daily', 'portfolio_refresh') AND j.status = 'running'
          AND u.status = 'active'
        FOR SHARE OF u
        """,
        (job_run_id, user_id),
    )
    connection = cur.fetchone()
    if connection is None or (
        account_id is not None and connection["account_id"] != account_id
    ) or (environment is not None and connection["environment"] != environment):
        raise ObservationCancelled("observation_connection_changed")
    _require_observation_context(cur, user_id, connection)
    if snapshot_id is not None:
        cur.execute(
            """
            SELECT id FROM portfolio_snapshots
            WHERE id = %s AND user_id = %s AND job_run_id = %s
              AND account_id = %s AND environment = %s
            """,
            (snapshot_id, user_id, job_run_id, connection["account_id"], connection["environment"]),
        )
        if cur.fetchone() is None:
            raise ObservationCancelled("observation_snapshot_changed")


def _require_settings_version(expected: int, actual: int, *, unchanged: bool = False) -> None:
    # A retry after a lost response may acknowledge exactly one identical save.
    if expected != actual and not (unchanged and expected + 1 == actual):
        raise SettingsVersionConflict("settings_version_conflict")


JobStatus = Literal["queued", "running", "succeeded", "degraded", "failed"]
@dataclass(frozen=True, slots=True)
class InvestmentProfileRecord:
    id: int
    user_id: UUID
    version: int
    reserve_rub: Decimal
    planned_withdrawal_rub: Decimal
    horizon_months: int
    max_drawdown_percent: Decimal
    liquidity_horizon_days: int
    allow_below_investment_grade: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BalancingPolicyRecord:
    id: int
    user_id: UUID
    version: int
    max_instrument_percent: Decimal
    max_sector_percent: Decimal
    max_issuer_percent: Decimal
    max_group_percent: Decimal
    max_share_percent: Decimal
    max_bond_percent: Decimal
    max_etf_percent: Decimal
    max_below_grade_percent: Decimal
    max_unknown_percent: Decimal
    max_term_months: int
    turnover_budget_percent: Decimal
    max_daily_turnover_participation_percent: Decimal
    securities_tax_rate_percent: Decimal
    uncertainty_haircut_percent: Decimal
    credit_loss_haircut_percent: Decimal
    no_trade_band_percent: Decimal
    min_replace_benefit_rub: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PortfolioProposalRecord:
    id: UUID
    user_id: UUID
    version: int
    source_snapshot_id: UUID
    account_id: str
    profile_version: int
    policy_version: int
    scenario_kind: str
    target_instrument_uid: str | None
    replaced_instrument_uid: str | None
    proposal_hash: bytes
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    status: str = "pending"
    decision_reason: str = ""
    decision_user_reason: str = ""
    deferred_until: datetime | None = None
    decided_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class JobRunRecord:
    id: UUID
    user_id: UUID
    job_type: str
    scheduled_for: date | None
    status: JobStatus
    attempt: int
    started_at: datetime
    finished_at: datetime | None
    refresh_scope: str = "full"


@dataclass(frozen=True, slots=True)
class BrokerSyncState:
    user_id: UUID
    account_id: str
    history_window_from: datetime | None
    history_window_to: datetime | None
    pending_cursor: str
    last_complete_watermark: datetime | None
    updated_at: datetime


def _source_document_id(
    cur: Any,
    document: EvidenceDocument,
    retrieved_at: datetime,
) -> tuple[UUID, bool]:
    content_hash = _hash_json(document.payload)
    cur.execute(
        """
        INSERT INTO source_documents (
            provider,
            document_type,
            subject_uid,
            provider_key,
            source_url,
            published_at,
            effective_at,
            first_retrieved_at,
            content_hash,
            payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (
            provider,
            document_type,
            subject_uid,
            provider_key,
            content_hash
        ) DO NOTHING
        RETURNING id
        """,
        (
            document.provider,
            document.document_type,
            document.subject_uid,
            document.provider_key,
            document.source_url,
            document.published_at,
            document.effective_at,
            retrieved_at,
            content_hash,
            _json(document.payload),
        ),
    )
    inserted = cur.fetchone()
    created = inserted is not None
    if inserted is None:
        cur.execute(
            """
            SELECT id
            FROM source_documents
            WHERE provider = %s
              AND document_type = %s
              AND subject_uid = %s
              AND provider_key = %s
              AND content_hash = %s
            """,
            (
                document.provider,
                document.document_type,
                document.subject_uid,
                document.provider_key,
                content_hash,
            ),
        )
        inserted = cur.fetchone()
        if inserted is None:
            raise RuntimeError("evidence document conflict could not be resolved")
    return cast(UUID, cast(dict[str, Any], inserted)["id"]), created


def _save_source_retrieval(
    cur: Any,
    document_id: UUID,
    retrieved_at: datetime,
) -> None:
    cur.execute(
        """
        INSERT INTO source_retrievals (source_document_id, retrieved_at)
        VALUES (%s, %s)
        ON CONFLICT (source_document_id, retrieved_at) DO NOTHING
        """,
        (document_id, retrieved_at),
    )


def _save_source_facts(
    cur: Any,
    document_id: UUID,
    document: EvidenceDocument,
) -> None:
    for fact in document.facts:
        fact_payload = {
            "subject_uid": fact.subject_uid,
            "fact_type": fact.fact_type,
            "fact_key": fact.fact_key,
            "value_numeric": fact.value_numeric,
            "value_text": fact.value_text,
            "currency": fact.currency,
            "unit": fact.unit,
            "effective_at": fact.effective_at,
            "published_at": fact.published_at,
            "payload": fact.payload or {},
        }
        cur.execute(
            """
            INSERT INTO source_facts (
                source_document_id,
                subject_uid,
                fact_type,
                fact_key,
                value_numeric,
                value_text,
                currency,
                unit,
                effective_at,
                published_at,
                payload,
                semantic_hash
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
            )
            ON CONFLICT (source_document_id, semantic_hash) DO NOTHING
            """,
            (
                document_id,
                fact.subject_uid,
                fact.fact_type,
                fact.fact_key,
                fact.value_numeric,
                fact.value_text,
                fact.currency,
                fact.unit,
                fact.effective_at,
                fact.published_at,
                _json(fact.payload or {}),
                _hash_json(fact_payload),
            ),
        )


def _save_payout_event(
    cur: Any,
    document_id: UUID,
    document: EvidenceDocument,
) -> None:
    payout = document.payout
    if payout is None:
        return
    payout_payload = {
        "provider": document.provider,
        "instrument_uid": payout.instrument_uid,
        "event_type": payout.event_type,
        "provider_key": payout.provider_key,
        "announced_at": payout.announced_at,
        "record_at": payout.record_at,
        "expected_at": payout.expected_at,
        "actual_at": payout.actual_at,
        "amount": payout.amount,
        "currency": payout.currency,
        "status": payout.status,
        "payload": payout.payload,
    }
    cur.execute(
        """
        INSERT INTO payout_events (
            source_document_id,
            provider,
            instrument_uid,
            event_type,
            provider_key,
            announced_at,
            record_at,
            expected_at,
            actual_at,
            amount,
            currency,
            status,
            payload,
            semantic_hash
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
        )
        ON CONFLICT (
            provider,
            instrument_uid,
            event_type,
            provider_key,
            semantic_hash
        ) DO NOTHING
        """,
        (
            document_id,
            document.provider,
            payout.instrument_uid,
            payout.event_type,
            payout.provider_key,
            payout.announced_at,
            payout.record_at,
            payout.expected_at,
            payout.actual_at,
            payout.amount,
            payout.currency,
            payout.status,
            _json(payout.payload),
            _hash_json(payout_payload),
        ),
    )


def _save_risk_assessment(
    cur: Any,
    *,
    user_id: UUID,
    snapshot_id: UUID,
    assessment: InstrumentRiskAssessment,
    retrieved_at: datetime,
) -> bool:
    cur.execute(
        """
        INSERT INTO portfolio_risk_assessments (
            user_id,
            snapshot_id,
            instrument_uid,
            state,
            rating_status,
            fundamental_status,
            source_status,
            reasons,
            evidence,
            assessed_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s
        )
        ON CONFLICT (snapshot_id, instrument_uid) DO NOTHING
        RETURNING id
        """,
        (
            user_id,
            snapshot_id,
            assessment.instrument_uid,
            assessment.state,
            assessment.rating_status,
            assessment.fundamental_status,
            assessment.source_status,
            _json(list(assessment.reasons)),
            _json(assessment.evidence),
            retrieved_at,
        ),
    )
    return cur.fetchone() is not None


def _save_operation_observation(
    cur: Any,
    *,
    user_id: UUID,
    account_id: str,
    operation: TBankOperation,
    observed_at: datetime,
) -> bool:
    normalized = _operation_payload(operation)
    semantic = _semantic_operation_payload(normalized)
    semantic_hash = _hash_json(semantic)
    cur.execute(
        """
        INSERT INTO operation_observations (
            user_id,
            account_id,
            observation_hash,
            semantic_hash,
            provider_operation_id,
            provider_cursor,
            operation_date,
            operation_type,
            operation_state,
            instrument_uid,
            figi,
            instrument_type,
            payment_value,
            payment_currency,
            price_value,
            price_currency,
            commission_value,
            commission_currency,
            accrued_int_value,
            accrued_int_currency,
            quantity,
            quantity_rest,
            quantity_done,
            normalized,
            observed_at
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
        )
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            user_id,
            account_id,
            _hash_json(normalized),
            semantic_hash,
            operation.id,
            operation.cursor,
            operation.date,
            operation.operation_type,
            operation.state,
            operation.instrument_uid,
            operation.figi,
            operation.instrument_type,
            _money_decimal(operation.payment),
            operation.payment.currency if operation.payment else None,
            _money_decimal(operation.price),
            operation.price.currency if operation.price else None,
            _money_decimal(operation.commission),
            operation.commission.currency if operation.commission else None,
            _money_decimal(operation.accrued_int),
            operation.accrued_int.currency if operation.accrued_int else None,
            Decimal(operation.quantity),
            Decimal(operation.quantity_rest),
            Decimal(operation.quantity_done),
            _json(normalized),
            observed_at,
        ),
    )
    if cur.fetchone() is not None:
        return True
    if operation.id:
        # A provider correction can return to a previously observed exact fact
        # (10 -> 12 -> 10). Keep the immutable financial payload and its source
        # date, but make this later confirmation current within the same typed ID.
        # An unchanged latest replay and an older/renamed observation do not move it.
        cur.execute(
            "WITH current_fact AS (SELECT id, observed_at FROM operation_observations "
            "WHERE user_id = %s AND account_id = %s AND provider_operation_id = %s "
            "AND operation_type = %s ORDER BY observed_at DESC, id DESC LIMIT 1) "
            "UPDATE operation_observations AS prior SET observed_at = %s FROM current_fact "
            "WHERE prior.user_id = %s AND prior.account_id = %s AND prior.semantic_hash = %s "
            "AND prior.provider_operation_id = %s AND prior.id <> current_fact.id "
            "AND current_fact.observed_at < %s",
            (user_id, account_id, operation.id, operation.operation_type, observed_at,
             user_id, account_id, semantic_hash, operation.id, observed_at),
        )
    return False


def _save_history_sync_state(
    cur: Any,
    *,
    user_id: UUID,
    account_id: str,
    window_from: datetime,
    window_to: datetime,
    page: TBankOperationsPage,
) -> None:
    if page.has_next:
        if not page.next_cursor:
            raise RuntimeError("history page has_next without a cursor")
        cur.execute(
            """
            INSERT INTO broker_sync_state (
                user_id,
                account_id,
                history_window_from,
                history_window_to,
                pending_cursor
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, account_id) DO UPDATE SET
                history_window_from = EXCLUDED.history_window_from,
                history_window_to = EXCLUDED.history_window_to,
                pending_cursor = EXCLUDED.pending_cursor,
                updated_at = now()
            """,
            (
                user_id,
                account_id,
                window_from,
                window_to,
                page.next_cursor,
            ),
        )
        return

    cur.execute(
        """
        INSERT INTO broker_sync_state (
            user_id,
            account_id,
            last_complete_watermark
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, account_id) DO UPDATE SET
            history_window_from = NULL,
            history_window_to = NULL,
            pending_cursor = NULL,
            last_complete_watermark = EXCLUDED.last_complete_watermark,
            updated_at = now()
        """,
        (user_id, account_id, window_to),
    )


class PortfolioStore:
    """Store immutable observation facts behind explicit tenant context."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _tenant(cur: Any, user_id: UUID) -> None:
        cur.execute(
            "SELECT set_config('omnicio.user_id', %s, true)",
            (str(user_id),),
        )

    @contextmanager
    def observer_lock(self, user_id: UUID | None = None) -> Iterator[bool]:
        # Shared legacy lock allows distinct owners to progress concurrently and
        # still excludes a pre-1.3 worker holding the global exclusive lock.
        locks = [("omnicio-portfolio-observer", user_id is not None)]
        if user_id is not None:
            locks.append((f"omnicio-portfolio-observer:{user_id}", False))
        with self.database.pool.connection() as conn:
            acquired: list[tuple[str, bool]] = []
            try:
                for lock_name, shared in locks:
                    function = "pg_try_advisory_lock_shared" if shared else "pg_try_advisory_lock"
                    with conn.transaction(), conn.cursor() as cur:
                        cur.execute(
                            f"SELECT {function}(hashtextextended(%s, 0)) AS locked", (lock_name,),
                        )
                        row = cur.fetchone()
                    if row is None or not cast(dict[str, Any], row)["locked"]:
                        break
                    acquired.append((lock_name, shared))
                # A session lock excludes other workers without keeping a
                # database transaction open throughout provider requests.
                yield len(acquired) == len(locks)
            finally:
                for lock_name, shared in reversed(acquired):
                    function = "pg_advisory_unlock_shared" if shared else "pg_advisory_unlock"
                    try:
                        with conn.transaction(), conn.cursor() as cur:
                            cur.execute(
                                f"SELECT {function}(hashtextextended(%s, 0)) AS unlocked",
                                (lock_name,),
                            )
                            released = cur.fetchone()
                            if released is None or not cast(dict[str, Any], released)["unlocked"]:
                                raise RuntimeError("portfolio observer lock was not released")
                    except (DatabaseError, RuntimeError):
                        conn.close()
                        raise

    def observer_user_ids(self) -> tuple[UUID, ...]:
        with self.database.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.user_id
                FROM tbank_connection AS t
                JOIN users AS u ON u.id = t.user_id
                WHERE u.status = 'active'
                ORDER BY t.user_id
                """
            )
            candidates = tuple(
                cast(UUID, cast(dict[str, Any], row)["user_id"])
                for row in cur.fetchall()
            )
        # Claiming each queued run rechecks current legal versions in its owner
        # transaction. Keeping unconsented connections here lets that boundary
        # settle revoked work instead of leaving an abandoned running/queued row.
        return candidates

    def current_strategy_draft(self, user_id: UUID) -> dict[str, Any] | None:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                "SELECT version, document, custom_document, fingerprint, updated_at "
                "FROM strategy_drafts WHERE user_id = %s", (user_id,),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            return dict(row) if row is not None else None

    def save_strategy_draft(
        self, user_id: UUID, document: dict[str, Any], *, expected_version: int,
    ) -> dict[str, Any]:
        # Same authority/version boundary as existing profile editors. A saved
        # working copy never changes a mandate, confirmed policy or broker state.
        document = normalize_document(document)
        fingerprint = document_hash(document)
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (f"strategy-draft:{user_id}",))
            cur.execute(
                "SELECT version, document, custom_document, fingerprint, updated_at "
                "FROM strategy_drafts WHERE user_id = %s FOR UPDATE", (user_id,),
            )
            row = cast(dict[str, Any] | None, cur.fetchone())
            actual = int(row["version"]) if row else 0
            unchanged = bool(row and row["fingerprint"] == fingerprint)
            _require_settings_version(expected_version, actual, unchanged=unchanged)
            if unchanged and row is not None:
                return dict(row)
            if actual == 2_147_483_647:
                raise SettingsVersionConflict("settings_version_conflict")
            custom = row["custom_document"] if row else None
            if document["customized"]:
                custom = document
            serialized_custom = (
                json.dumps(custom, ensure_ascii=False) if custom is not None else None
            )
            cur.execute(
                "INSERT INTO strategy_drafts (user_id, version, document, "
                    "custom_document, fingerprint) "
                "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET version = EXCLUDED.version, "
                "document = EXCLUDED.document, custom_document = EXCLUDED.custom_document, "
                "fingerprint = EXCLUDED.fingerprint, "
                "updated_at = now() RETURNING version, document, custom_document, "
                    "fingerprint, updated_at",
                (user_id, actual + 1, json.dumps(document, ensure_ascii=False),
                 serialized_custom, fingerprint),
            )
            saved = cur.fetchone()
            if saved is None:
                raise RuntimeError("strategy draft save returned no row")
            return dict(cast(dict[str, Any], saved))

    def current_profile(self, user_id: UUID) -> InvestmentProfileRecord | None:
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
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade,
                    created_at
                FROM investment_profile_versions
                WHERE user_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _profile(cast(dict[str, Any], fetched))

    def current_balancing_policy(
        self,
        user_id: UUID,
    ) -> BalancingPolicyRecord | None:
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
                    version,
                    max_instrument_percent,
                    max_sector_percent,
                    max_issuer_percent,
                    max_group_percent,
                    max_share_percent,
                    max_bond_percent,
                    max_etf_percent,
                    max_below_grade_percent,
                    max_unknown_percent,
                    max_term_months,
                    turnover_budget_percent,
                    max_daily_turnover_participation_percent,
                    securities_tax_rate_percent,
                    uncertainty_haircut_percent,
                    credit_loss_haircut_percent,
                    no_trade_band_percent,
                    min_replace_benefit_rub,
                    created_at
                FROM balancing_policy_versions
                WHERE user_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _balancing_policy(cast(dict[str, Any], fetched))

    def proposals(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
    ) -> tuple[PortfolioProposalRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("proposal limit must be between 1 and 100")
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    p.id,
                    p.user_id,
                    p.version,
                    p.source_snapshot_id,
                    p.account_id,
                    p.profile_version,
                    p.policy_version,
                    p.scenario_kind,
                    p.target_instrument_uid,
                    p.replaced_instrument_uid,
                    p.proposal_hash,
                    p.payload,
                    p.created_at,
                    p.expires_at,
                    COALESCE(
                        a.action,
                        CASE
                            WHEN p.expires_at <= now() THEN 'expired'
                            ELSE 'pending'
                        END
                    ) AS status,
                    COALESCE(a.reason, '') AS decision_reason,
                    COALESCE(a.user_reason, '') AS decision_user_reason,
                    a.deferred_until,
                    a.acted_at AS decided_at
                FROM portfolio_proposals AS p
                LEFT JOIN portfolio_proposal_actions AS a
                  ON a.proposal_id = p.id
                WHERE p.user_id = %s
                ORDER BY p.created_at DESC, p.version DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return tuple(
                _proposal_record(dict(cast(dict[str, Any], row)))
                for row in cur.fetchall()
            )

    @staticmethod
    def _refresh_connection(cur: Any, user_id: UUID) -> dict[str, Any] | None:
        cur.execute(
            "SELECT c.account_id, c.environment, c.verified_at, clock_timestamp() AS server_now "
            "FROM tbank_connection c JOIN users u ON u.id = c.user_id "
            "WHERE c.user_id = %s AND u.status = 'active' FOR SHARE OF u",
            (user_id,),
        )
        return cast(dict[str, Any] | None, cur.fetchone())

    @staticmethod
    def _refresh_row(
        cur: Any, user_id: UUID, *, active_only: bool = False,
    ) -> dict[str, Any] | None:
        cur.execute(
            "SELECT j.*, s.captured_at AS snapshot_at FROM job_runs j "
            "LEFT JOIN portfolio_snapshots s ON s.job_run_id = j.id AND s.user_id = j.user_id "
            "WHERE j.user_id = %s AND j.job_type = 'portfolio_refresh' "
            "AND (NOT %s OR j.status IN ('queued', 'running')) "
            "ORDER BY j.requested_at DESC, j.started_at DESC, j.id DESC LIMIT 1",
            (user_id, active_only),
        )
        return cast(dict[str, Any] | None, cur.fetchone())

    def _refresh_status(
        self, cur: Any, user_id: UUID, connection: dict[str, Any] | None,
        *, reason: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "not_connected", "job_id": None, "requested_at": None,
            "started_at": None, "finished_at": None, "observed_at": None,
            "snapshot_saved": False, "history_status": None, "history_pages": 0,
            "news": {"status": "not_requested", "observed_at": None,
                     "scope": "held_instrument_links"},
            "can_refresh": False, "retry_after_seconds": 0, "cooldown_until": None,
            "reason": "broker_not_connected",
        }
        if connection is None:
            return result
        result.update(status="idle", can_refresh=reason is None, reason=reason)
        cur.execute(
            "SELECT captured_at FROM portfolio_snapshots WHERE user_id = %s "
            "AND account_id = %s AND environment = %s ORDER BY captured_at DESC LIMIT 1",
            (user_id, connection["account_id"], connection["environment"]),
        )
        snapshot = cur.fetchone()
        if snapshot is not None:
            result["observed_at"] = snapshot["captured_at"].isoformat()
        job = self._refresh_row(cur, user_id)
        if job is None or not _refresh_context_matches(
            job["details"].get("connection"), connection,
        ):
            return result
        cooldown = job["requested_at"] + timedelta(seconds=REFRESH_COOLDOWN_SECONDS)
        retry = max(0, ceil((cooldown - connection["server_now"]).total_seconds()))
        active = job["status"] in {"queued", "running"}
        result.update(
            status=job["status"], job_id=str(job["id"]),
            requested_at=job["requested_at"].isoformat(),
            started_at=job["started_at"].isoformat() if job["status"] != "queued" else None,
            finished_at=job["finished_at"].isoformat() if job["finished_at"] else None,
            snapshot_saved=job["snapshot_at"] is not None,
            history_status=job["details"].get("history_status"),
            history_pages=job["details"].get("history_pages", 0),
            scope=job["details"].get("refresh_scope", "full"),
            valuation_status=job["details"].get("valuation_status", "unknown"),
            can_refresh=not active and retry == 0 and reason is None,
            retry_after_seconds=max(2, retry) if active else retry,
            cooldown_until=cooldown.isoformat(),
            reason=reason or job["details"].get("stage_error"),
        )
        news = job["details"].get("news")
        if isinstance(news, dict):
            result["news"] = {key: news[key] for key in (
                "status", "observed_at", "pages", "scanned_items", "documents_new", "scope",
            ) if key in news}
        return result

    def refresh_status(self, user_id: UUID) -> dict[str, Any]:
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            return self._refresh_status(cur, user_id, self._refresh_connection(cur, user_id))

    @staticmethod
    def _fail_refresh(cur: Any, user_id: UUID, job_id: UUID, reason: str) -> None:
        cur.execute(
            "UPDATE job_runs SET status = 'failed', finished_at = clock_timestamp(), "
            "details = details || %s::jsonb WHERE id = %s AND user_id = %s "
            "AND job_type = 'portfolio_refresh' AND status IN ('queued', 'running')",
            (_json({"stage_error": reason}), job_id, user_id),
        )

    def fail_refresh_job(self, user_id: UUID, job_id: UUID, reason: str) -> None:
        """Settle an interrupted run without authorizing any financial fact writes."""
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            self._fail_refresh(cur, user_id, job_id, reason)

    def request_refresh(
        self, user_id: UUID, legal_versions: dict[str, str], *, scope: str = "full",
    ) -> dict[str, Any]:
        """One durable pending run per owner; cooldown uses the database clock."""
        if scope not in {"quick", "full"}:
            raise ValueError("portfolio_refresh_scope_invalid")
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            connection = self._refresh_connection(cur, user_id)
            if connection is None:
                return self._refresh_status(cur, user_id, None)
            if not _has_refresh_legal(cur, user_id, legal_versions):
                return self._refresh_status(cur, user_id, connection, reason="consent_required")
            active = self._refresh_row(cur, user_id, active_only=True)
            if active is not None and (
                not _refresh_context_matches(active["details"].get("connection"), connection)
                or active["details"].get("legal_versions") != legal_versions
            ):
                self._fail_refresh(cur, user_id, active["id"], "observation_context_changed")
            elif active is not None and active["status"] == "queued" and scope == "full":
                # A queued quick observation may have been scheduled without the
                # browser. An explicit full request upgrades it before any reads.
                cur.execute(
                    "UPDATE job_runs SET details = details || %s::jsonb "
                    "WHERE id = %s AND user_id = %s AND status = 'queued'",
                    (_json({"refresh_scope": "full", "trigger": "manual"}), active["id"], user_id),
                )
            current = self._refresh_status(cur, user_id, connection)
            if not current["can_refresh"]:
                if current["status"] not in {"queued", "running"}:
                    current["reason"] = "refresh_cooldown"
                return current
            self._enqueue_refresh(cur, user_id, connection, legal_versions,
                                  scope=scope, trigger="manual")
            return self._refresh_status(cur, user_id, connection)

    @staticmethod
    def _enqueue_refresh(
        cur: Any, user_id: UUID, connection: Mapping[str, Any], legal_versions: dict[str, str],
        *, scope: str, trigger: str,
    ) -> dict[str, Any]:
        context = {key: connection[key] for key in ("account_id", "environment", "verified_at")}
        cur.execute(
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, details) "
            "VALUES (%s, 'portfolio_refresh', NULL, 'queued', %s::jsonb) RETURNING *",
            (user_id, _json({"connection": context, "legal_versions": legal_versions,
                             "refresh_scope": scope, "trigger": trigger})),
        )
        return cast(dict[str, Any], cur.fetchone())

    @staticmethod
    def _monitoring_scope(
        cur: Any, user_id: UUID, connection: Mapping[str, Any], legal_versions: dict[str, str],
    ) -> str | None:
        """Use durable attempt times; a restart or outage cannot create a hot loop."""
        context = {key: connection[key] for key in ("account_id", "environment", "verified_at")}
        now = connection["server_now"]
        cur.execute(
            "SELECT max(GREATEST(requested_at, started_at, finished_at)) AS last_attempt_at, "
            "max(GREATEST(requested_at, started_at, finished_at)) FILTER "
            "(WHERE COALESCE(details->>'refresh_scope', 'full') "
            "= 'full') AS last_full_at FROM job_runs WHERE user_id = %s "
            "AND job_type IN ('portfolio_daily', 'portfolio_refresh') "
            "AND details->'connection' = %s::jsonb AND details->'legal_versions' = %s::jsonb "
            "AND GREATEST(requested_at, started_at, finished_at) >= %s",
            (user_id, _json(context), _json(legal_versions), now - MONITORING_FULL_INTERVAL),
        )
        row = cast(dict[str, Any], cur.fetchone())
        last_attempt = row["last_attempt_at"]
        if last_attempt is not None and now < last_attempt + PORTFOLIO_MAX_AGE:
            return None
        last_full = row["last_full_at"]
        return ("full" if last_full is None or now >= last_full + MONITORING_FULL_INTERVAL
                else "quick")

    def _resume_refresh(
        self, cur: Any, user_id: UUID, row: dict[str, Any],
    ) -> JobRunRecord | None:
        # A new run owns a new immutable snapshot. Reusing a crashed run's ID
        # would attach newly fetched evidence to its already persisted old NAV.
        self._fail_refresh(cur, user_id, row["id"], "worker_interrupted")
        if row["attempt"] >= REFRESH_MAX_ATTEMPTS:
            return None
        details = {
            "connection": row["details"]["connection"],
            "legal_versions": row["details"]["legal_versions"],
            "resumed_from": str(row["id"]),
            "refresh_scope": row["details"].get("refresh_scope", "full"),
            "trigger": row["details"].get("trigger", "manual"),
        }
        cur.execute(
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, attempt, "
            "requested_at, details) VALUES (%s, 'portfolio_refresh', NULL, "
            "'running', %s, %s, %s::jsonb) "
            "RETURNING *",
            (user_id, row["attempt"] + 1, row["requested_at"], _json(details)),
        )
        return _job_run(cast(dict[str, Any], cur.fetchone()))

    def claim_refresh_job(
        self, user_id: UUID, legal_versions: dict[str, str], *, schedule_if_due: bool = False,
    ) -> JobRunRecord | None:
        """Claim/recover only while the caller holds this owner's observer session lock."""
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            connection = self._refresh_connection(cur, user_id)
            row = self._refresh_row(cur, user_id, active_only=True)
            if connection is None or not _has_refresh_legal(cur, user_id, legal_versions):
                if row is not None:
                    self._fail_refresh(cur, user_id, row["id"], "observation_context_changed")
                return None
            if row is None and schedule_if_due:
                scope = self._monitoring_scope(cur, user_id, connection, legal_versions)
                if scope is not None:
                    row = self._enqueue_refresh(cur, user_id, connection, legal_versions,
                                                scope=scope, trigger="automatic")
            if row is None:
                return None
            if (not _refresh_context_matches(row["details"].get("connection"), connection)
                    or row["details"].get("legal_versions") != legal_versions):
                self._fail_refresh(cur, user_id, row["id"], "observation_context_changed")
                return None
            if row["status"] == "running":
                return self._resume_refresh(cur, user_id, row)
            cur.execute(
                "UPDATE job_runs SET status = 'running', started_at = clock_timestamp() "
                "WHERE id = %s AND user_id = %s AND status = 'queued' RETURNING *",
                (row["id"], user_id),
            )
            claimed = cur.fetchone()
            return _job_run(cast(dict[str, Any], claimed)) if claimed is not None else None

    def schedule_daily_job(
        self, user_id: UUID, *, scheduled_for: date, legal_versions: dict[str, str],
    ) -> bool:
        """Persist the dated request before competing for the provider session lock."""
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            connection = self._refresh_connection(cur, user_id)
            if connection is None or not _has_refresh_legal(cur, user_id, legal_versions):
                return False
            context = {key: connection[key] for key in ("account_id", "environment", "verified_at")}
            cur.execute(
                "INSERT INTO job_runs (user_id, job_type, scheduled_for, status, details) "
                "VALUES (%s, 'portfolio_daily', %s, 'queued', %s::jsonb) "
                "ON CONFLICT (user_id, job_type, scheduled_for) DO NOTHING RETURNING id",
                (user_id, scheduled_for,
                 _json({"connection": context, "legal_versions": legal_versions,
                        "scheduled_for": scheduled_for.isoformat()})),
            )
            return cur.fetchone() is not None

    @staticmethod
    def _fail_daily_active(cur: Any, user_id: UUID, reason: str) -> None:
        cur.execute(
            "UPDATE job_runs SET status = 'failed', finished_at = clock_timestamp(), "
            "details = details || %s::jsonb WHERE user_id = %s "
            "AND job_type = 'portfolio_daily' AND status IN ('queued', 'running')",
            (_json({"stage_error": reason, "retryable": False}), user_id),
        )

    @staticmethod
    def _settle_daily_retry(
        cur: Any, user_id: UUID, row: dict[str, Any], now: datetime, *,
        context_matches: bool, recover_running: bool,
    ) -> bool:
        if row["status"] == "running":
            if not recover_running and row["started_at"] >= now - timedelta(minutes=30):
                return False
        elif context_matches and (
            not row["details"].get("retryable", row["status"] == "failed")
            or row["next_attempt_at"] > now
        ):
            return False
        if row["status"] in {"queued", "running"}:
            # Only the holder of the global observer lock may declare another
            # process interrupted. Its immutable facts remain tied to that run.
            reason = ("worker_interrupted" if row["status"] == "running"
                      else "observation_context_changed")
            cur.execute(
                "UPDATE job_runs SET status = 'failed', finished_at = clock_timestamp(), "
                "details = details || %s::jsonb WHERE id = %s AND user_id = %s",
                (_json({"stage_error": reason, "retryable": row["status"] == "running"}),
                 row["id"], user_id),
            )
        return bool(row["attempt"] < DAILY_MAX_ATTEMPTS)

    @staticmethod
    def _claim_daily_row(
        cur: Any, user_id: UUID, root: dict[str, Any], row: dict[str, Any],
        connection: dict[str, Any], legal_versions: dict[str, str], *, recover_running: bool,
    ) -> JobRunRecord | None:
        now = connection["server_now"]
        context_matches = (_refresh_context_matches(row["details"].get("connection"), connection)
                           and row["details"].get("legal_versions") == legal_versions)
        if row["status"] == "succeeded" and context_matches:
            return None
        if row["status"] == "queued" and context_matches:
            if row["next_attempt_at"] > now:
                return None
            cur.execute(
                "UPDATE job_runs SET status = 'running', started_at = clock_timestamp(), "
                "next_attempt_at = clock_timestamp() WHERE id = %s AND user_id = %s "
                "AND status = 'queued' RETURNING *", (row["id"], user_id),
            )
            found = cur.fetchone()
            return _job_run(found) if found is not None else None
        if not PortfolioStore._settle_daily_retry(
            cur, user_id, row, now, context_matches=context_matches,
            recover_running=recover_running,
        ):
            return None
        context = {key: connection[key] for key in ("account_id", "environment", "verified_at")}
        details = {"connection": context, "legal_versions": legal_versions,
                   "scheduled_for": root["scheduled_for"].isoformat(),
                   "resumed_from": str(row["id"])}
        cur.execute(
            "INSERT INTO job_runs (user_id, job_type, scheduled_for, retry_of, status, "
            "attempt, requested_at, details) VALUES (%s, 'portfolio_daily', NULL, %s, "
            "'running', %s, %s, %s::jsonb) RETURNING *",
            (user_id, root["id"], row["attempt"] + 1, root["requested_at"], _json(details)),
        )
        return _job_run(cur.fetchone())

    def claim_pending_daily_job(
        self, user_id: UUID, legal_versions: dict[str, str], *,
        scheduled_for: date | None = None, recover_running: bool = True,
    ) -> JobRunRecord | None:
        """Consume a durable daily request while holding the global observer lock."""
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            cur.execute(_ADVISORY_LOCK_SQL, (live_execution_lock_key(user_id),))
            connection = self._refresh_connection(cur, user_id)
            if connection is None or not _has_refresh_legal(cur, user_id, legal_versions):
                self._fail_daily_active(cur, user_id, "observation_context_changed")
                return None
            cur.execute(
                "SELECT * FROM job_runs WHERE user_id = %s AND job_type = 'portfolio_daily' "
                "AND scheduled_for IS NOT NULL AND (%s::date IS NULL OR scheduled_for = %s) "
                "ORDER BY scheduled_for DESC LIMIT 1 FOR UPDATE",
                (user_id, scheduled_for, scheduled_for),
            )
            root = cast(dict[str, Any] | None, cur.fetchone())
            if root is None:
                return None
            # A later daily snapshot cannot recreate missed historical NAV. Keep
            # old attempts as explicit failures and collect the latest due one.
            cur.execute(
                "UPDATE job_runs j SET status = 'failed', finished_at = clock_timestamp(), "
                "details = j.details || %s::jsonb WHERE j.user_id = %s "
                "AND j.job_type = 'portfolio_daily' AND j.status IN ('queued', 'running') "
                "AND EXISTS (SELECT 1 FROM job_runs older WHERE older.user_id = j.user_id "
                "AND older.scheduled_for < %s AND (older.id = j.id OR older.id = j.retry_of))",
                (_json({"stage_error": "schedule_superseded", "retryable": False}),
                 user_id, root["scheduled_for"]),
            )
            cur.execute(
                "SELECT * FROM job_runs WHERE user_id = %s AND (id = %s OR retry_of = %s) "
                "ORDER BY attempt DESC LIMIT 1 FOR UPDATE", (user_id, root["id"], root["id"]),
            )
            row = cast(dict[str, Any], cur.fetchone())
            return self._claim_daily_row(cur, user_id, root, row, connection, legal_versions,
                                         recover_running=recover_running)

    def claim_daily_job(
        self, user_id: UUID, *, job_type: str, scheduled_for: date,
        legal_versions: dict[str, str], recover_running: bool = False,
    ) -> JobRunRecord | None:
        if job_type != "portfolio_daily":
            raise ValueError("daily_job_type_invalid")
        self.schedule_daily_job(user_id, scheduled_for=scheduled_for, legal_versions=legal_versions)
        return self.claim_pending_daily_job(user_id, legal_versions, scheduled_for=scheduled_for,
                                            recover_running=recover_running)

    def finish_job(
        self,
        user_id: UUID,
        job_run_id: UUID,
        *,
        status: Literal["succeeded", "degraded", "failed"],
        details: dict[str, object],
    ) -> bool:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            try:
                _require_observation_job(cur, user_id, job_run_id)
            except ObservationCancelled:
                cur.execute(
                    "UPDATE job_runs SET status = 'failed', finished_at = clock_timestamp(), "
                    "details = details || %s::jsonb WHERE id = %s AND user_id = %s "
                    "AND status = 'running'",
                    (_json({"stage_error": "observation_context_changed", "retryable": False}),
                     job_run_id, user_id),
                )
                return False
            cur.execute(
                """
                UPDATE job_runs
                SET
                    status = %s,
                    finished_at = now(),
                    next_attempt_at = CASE WHEN job_type = 'portfolio_daily'
                        THEN now() + make_interval(
                            secs => 300 * power(2, LEAST(attempt, 3) - 1)::integer)
                        ELSE next_attempt_at END,
                    details = details || %s::jsonb
                WHERE id = %s
                  AND user_id = %s
                  AND status = 'running'
                RETURNING id
                """,
                (status, _json(details), job_run_id, user_id),
            )
            if cur.fetchone() is None:
                raise RuntimeError("observation job is no longer running")
            return True

    def sync_state(self, user_id: UUID, account_id: str) -> BrokerSyncState | None:
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT
                    user_id,
                    account_id,
                    history_window_from,
                    history_window_to,
                    COALESCE(pending_cursor, '') AS pending_cursor,
                    last_complete_watermark,
                    updated_at
                FROM broker_sync_state
                WHERE user_id = %s
                  AND account_id = %s
                """,
                (user_id, account_id),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            return _sync_state(cast(dict[str, Any], fetched))

    def reuse_snapshot_metadata(
        self, user_id: UUID, *, job_run_id: UUID, bundle: BrokerObservationBundle,
    ) -> BrokerObservationBundle:
        """Restore held-instrument descriptions after restart without provider reads.

        This is historical catalog evidence for observation, never renewed market
        or execution authority. Its original retrieval time remains on the bundle.
        """
        known = {item.uid for item in bundle.metadata}
        missing = sorted({position.instrument_uid for position in bundle.portfolio.positions
                          if position.instrument_uid and position.instrument_uid not in known
                          and position.instrument_type != "currency"})
        if not missing:
            return bundle
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            _require_observation_job(
                cur, user_id, job_run_id,
                account_id=bundle.account_id, environment=bundle.environment,
            )
            cur.execute(
                "SELECT instrument_uid AS uid, name, ticker, isin, instrument_type, sector, "
                "country_of_risk, for_qual_investor, figi, provider_retrieved_at "
                "FROM instrument_catalog WHERE provider = 'tbank' "
                "AND instrument_uid = ANY (%s)", (missing,),
            )
            rows = [dict(row) for row in cur.fetchall()]
        if not rows:
            return bundle
        times = [row.pop("provider_retrieved_at") for row in rows]
        metadata = (*bundle.metadata, *(TBankInstrumentMetadata(**row) for row in rows))
        if bundle.metadata:
            times.extend(source.retrieved_at for source in bundle.sources if source.id == "catalog")
        sources = tuple(AnalysisSource(
            id=source.id, name=source.name, url=source.url,
            retrieved_at=min(times), status="cached", methods=(),
        ) if source.id == "catalog" else source for source in bundle.sources)
        return BrokerObservationBundle(
            account_id=bundle.account_id, account_name=bundle.account_name,
            environment=bundle.environment, refreshed_at=bundle.refreshed_at,
            portfolio=bundle.portfolio, positions=bundle.positions,
            metadata=metadata, sources=sources,
            analysis=analyze_portfolio(bundle.portfolio, bundle.positions, metadata),
        )

    def _save_snapshot_catalog(
        self,
        cur: Any,
        user_id: UUID,
        bundle: BrokerObservationBundle,
        catalog_retrieved_at: datetime,
    ) -> None:
        if bundle.metadata and any(
            source.id == "catalog" and source.status in {"received", "partial"}
            for source in bundle.sources
        ):
            catalog_rows = [
                (
                    item.uid,
                    item.figi,
                    item.asset_uid,
                    item.position_uid,
                    item.ticker,
                    item.name,
                    item.isin,
                    item.instrument_type,
                    item.currency,
                    item.class_code,
                    item.lot,
                    item.sector,
                    item.country_of_risk,
                    item.for_qual_investor,
                    item.for_iis,
                    item.api_trade_available,
                    item.buy_available,
                    item.sell_available,
                    _money_decimal(item.nominal),
                    item.nominal.currency if item.nominal else None,
                    item.maturity_date,
                    item.floating_coupon,
                    item.perpetual,
                    item.amortization,
                    item.subordinated,
                    item.liquidity,
                    catalog_retrieved_at,
                )
                for item in bundle.metadata
            ]
            cur.executemany(
                """
                INSERT INTO instrument_catalog (
                    provider,
                    instrument_uid,
                    figi,
                    asset_uid,
                    position_uid,
                    ticker,
                    name,
                    isin,
                    instrument_type,
                    currency,
                    class_code,
                    lot,
                    sector,
                    country_of_risk,
                    for_qual_investor,
                    for_iis,
                    api_trade_available,
                    buy_available,
                    sell_available,
                    nominal_value,
                    nominal_currency,
                    maturity_date,
                    floating_coupon,
                    perpetual,
                    amortization,
                    subordinated,
                    liquidity,
                    provider_retrieved_at
                )
                VALUES (
                    'tbank', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (provider, instrument_uid) DO UPDATE SET
                    figi = EXCLUDED.figi,
                    asset_uid = EXCLUDED.asset_uid,
                    position_uid = EXCLUDED.position_uid,
                    ticker = EXCLUDED.ticker,
                    name = EXCLUDED.name,
                    isin = EXCLUDED.isin,
                    instrument_type = EXCLUDED.instrument_type,
                    currency = EXCLUDED.currency,
                    class_code = EXCLUDED.class_code,
                    lot = EXCLUDED.lot,
                    sector = EXCLUDED.sector,
                    country_of_risk = EXCLUDED.country_of_risk,
                    for_qual_investor = EXCLUDED.for_qual_investor,
                    for_iis = EXCLUDED.for_iis,
                    api_trade_available = EXCLUDED.api_trade_available,
                    buy_available = EXCLUDED.buy_available,
                    sell_available = EXCLUDED.sell_available,
                    nominal_value = EXCLUDED.nominal_value,
                    nominal_currency = EXCLUDED.nominal_currency,
                    maturity_date = EXCLUDED.maturity_date,
                    floating_coupon = EXCLUDED.floating_coupon,
                    perpetual = EXCLUDED.perpetual,
                    amortization = EXCLUDED.amortization,
                    subordinated = EXCLUDED.subordinated,
                    liquidity = EXCLUDED.liquidity,
                    last_seen_at = now(),
                    provider_retrieved_at = EXCLUDED.provider_retrieved_at
                """,
                catalog_rows,
            )

            access_rows = [
                (
                    user_id,
                    bundle.account_id,
                    item.uid,
                    _json(list(item.required_tests)),
                    catalog_retrieved_at,
                )
                for item in bundle.metadata
            ]
            cur.executemany(
                """
                INSERT INTO account_instrument_access (
                    user_id,
                    account_id,
                    provider,
                    instrument_uid,
                    required_tests,
                    observed_at
                )
                VALUES (%s, %s, 'tbank', %s, %s::jsonb, %s)
                ON CONFLICT (user_id, account_id, provider, instrument_uid)
                DO UPDATE SET
                    required_tests = EXCLUDED.required_tests,
                    observed_at = EXCLUDED.observed_at
                """,
                access_rows,
            )



    @staticmethod
    def _snapshot_position_row(
        snapshot_id: UUID,
        user_id: UUID,
        position: TBankPortfolioPosition,
        exposure: SecurityExposure | None,
        info: TBankInstrumentMetadata | None,
    ) -> tuple[object, ...]:
        current_price_currency = (
            position.current_price.currency if position.current_price else None
        )
        current_nkd_currency = (
            position.current_nkd.currency if position.current_nkd else None
        )
        average_price_currency = (
            position.average_price_fifo.currency
            if position.average_price_fifo
            else None
        )
        value_rub = (
            Decimal(exposure.value_rub)
            if exposure is not None and exposure.value_rub is not None
            else None
        )
        nav_percent = (
            Decimal(exposure.nav_percent)
            if exposure is not None and exposure.nav_percent is not None
            else None
        )
        sector = exposure.sector if exposure is not None else ""
        country_of_risk = info.country_of_risk if info else ""
        for_qual_investor = info.for_qual_investor if info else None
        return (
            snapshot_id,
            user_id,
            position.instrument_uid or position.figi,
            position.figi,
            position.ticker,
            position.instrument_type,
            Decimal(position.quantity),
            Decimal(position.quantity_lots),
            _money_decimal(position.current_price),
            current_price_currency,
            _money_decimal(position.current_nkd),
            current_nkd_currency,
            _money_decimal(position.average_price_fifo),
            average_price_currency,
            position.blocked,
            Decimal(position.blocked_lots),
            value_rub,
            nav_percent,
            sector,
            country_of_risk,
            for_qual_investor,
        )

    def _save_snapshot_positions(
        self,
        cur: Any,
        snapshot_id: UUID,
        user_id: UUID,
        bundle: BrokerObservationBundle,
        securities: dict[str, SecurityExposure],
        metadata: dict[str, TBankInstrumentMetadata],
    ) -> None:
        for position in bundle.portfolio.positions:
            if Decimal(position.quantity) == 0 or position.instrument_type == "currency":
                continue
            uid = position.instrument_uid or position.figi
            exposure = securities.get(uid)
            info = metadata.get(position.instrument_uid)
            cur.execute(
                """
                INSERT INTO portfolio_snapshot_positions (
                    snapshot_id,
                    user_id,
                    instrument_uid,
                    figi,
                    ticker,
                    instrument_type,
                    quantity,
                    quantity_lots,
                    current_price_value,
                    current_price_currency,
                    current_nkd_value,
                    current_nkd_currency,
                    average_price_fifo_value,
                    average_price_fifo_currency,
                    blocked,
                    blocked_lots,
                    value_rub,
                    nav_percent,
                    sector,
                    country_of_risk,
                    for_qual_investor
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                """,
                self._snapshot_position_row(
                    snapshot_id,
                    user_id,
                    position,
                    exposure,
                    info,
                ),
            )


    def save_snapshot(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        bundle: BrokerObservationBundle,
        account: TBankAccount | None = None,
        user_info: TBankUserInfo | None = None,
    ) -> UUID:
        if account is not None and account.id != bundle.account_id:
            raise ObservationCancelled("observation_account_mismatch")
        evidence: dict[str, object] = {
            "analysis": asdict(bundle.analysis),
            "sources": [asdict(source) for source in bundle.sources],
        }
        if account is not None:
            evidence["account"] = {
                "type": account.type,
                "status": account.status,
                "access_level": account.access_level,
                "opened_at": account.opened_at,
            }
        if user_info is not None:
            evidence["broker_user"] = {
                "premium": user_info.premium,
                "qualified": user_info.qualified,
                "qualified_for_work_with": list(user_info.qualified_for_work_with),
                "tariff": user_info.tariff,
                "risk_level_code": user_info.risk_level_code,
            }
        securities = {item.uid: item for item in bundle.analysis.securities}
        metadata = {item.uid: item for item in bundle.metadata}
        catalog_retrieved_at = next(
            (
                source.retrieved_at
                for source in bundle.sources
                if source.id == "catalog"
            ),
            bundle.refreshed_at,
        )

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            _require_observation_job(
                cur, user_id, job_run_id,
                account_id=bundle.account_id, environment=bundle.environment,
            )
            self._save_snapshot_catalog(
                cur,
                user_id,
                bundle,
                catalog_retrieved_at,
            )
            cur.execute(
                """
                INSERT INTO portfolio_snapshots (
                    user_id,
                    job_run_id,
                    account_id,
                    environment,
                    captured_at,
                    analysis_status,
                    nav_rub,
                    rub_cash_total,
                    rub_cash_blocked,
                    rub_cash_unblocked,
                    limits_loading_in_progress,
                    evidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (job_run_id) DO NOTHING
                RETURNING id
                """,
                (
                    user_id,
                    job_run_id,
                    bundle.account_id,
                    bundle.environment,
                    bundle.refreshed_at,
                    bundle.analysis.status,
                    Decimal(bundle.analysis.nav_rub),
                    Decimal(bundle.analysis.rub_cash_total),
                    Decimal(bundle.analysis.rub_cash_blocked),
                    (
                        Decimal(bundle.analysis.rub_cash_unblocked)
                        if bundle.analysis.rub_cash_unblocked is not None
                        else None
                    ),
                    bundle.positions.limits_loading_in_progress,
                    _json(evidence),
                ),
            )
            snapshot_row = cur.fetchone()
            if snapshot_row is None:
                cur.execute(
                    """
                    SELECT id
                    FROM portfolio_snapshots
                    WHERE job_run_id = %s
                      AND user_id = %s
                    """,
                    (job_run_id, user_id),
                )
                existing = cur.fetchone()
                if existing is None:
                    raise RuntimeError("portfolio snapshot conflict could not be resolved")
                return cast(UUID, cast(dict[str, Any], existing)["id"])
            snapshot_id = cast(UUID, cast(dict[str, Any], snapshot_row)["id"])

            self._save_snapshot_positions(
                cur,
                snapshot_id,
                user_id,
                bundle,
                securities,
                metadata,
            )
            return snapshot_id

    def news_state(self, user_id: UUID, *, job_run_id: UUID) -> dict[str, Any]:
        """Resume only evidence collected under this exact connection and consent."""
        with self.database.pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            self._tenant(cur, user_id)
            _require_observation_job(cur, user_id, job_run_id)
            cur.execute(
                "SELECT prior.details -> 'news' AS news FROM job_runs prior "
                "JOIN job_runs current ON current.user_id = prior.user_id AND current.id = %s "
                "WHERE prior.user_id = %s AND jsonb_typeof(prior.details -> 'news') = 'object' "
                "AND prior.details -> 'connection' = current.details -> 'connection' "
                "AND prior.details -> 'legal_versions' = current.details -> 'legal_versions' "
                "ORDER BY prior.started_at DESC, prior.id DESC LIMIT 1",
                (job_run_id, user_id),
            )
            row = cast(Mapping[str, Any] | None, cur.fetchone())
            return dict(row["news"]) if row is not None else {}

    def save_evidence(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        snapshot_id: UUID,
        documents: tuple[EvidenceDocument, ...],
        assessments: tuple[InstrumentRiskAssessment, ...],
        retrieved_at: datetime,
        news_checkpoint: dict[str, object] | None = None,
    ) -> tuple[int, int]:
        if retrieved_at.tzinfo is None:
            raise ValueError("evidence retrieval time must be timezone-aware")

        documents_written = 0
        assessments_written = 0
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            _require_observation_job(cur, user_id, job_run_id, snapshot_id=snapshot_id)
            for document in documents:
                document_id, created = _source_document_id(
                    cur,
                    document,
                    retrieved_at,
                )
                documents_written += int(created)
                _save_source_retrieval(cur, document_id, retrieved_at)
                _save_source_facts(cur, document_id, document)
                _save_payout_event(cur, document_id, document)

            for assessment in assessments:
                assessments_written += int(
                    _save_risk_assessment(
                        cur,
                        user_id=user_id,
                        snapshot_id=snapshot_id,
                        assessment=assessment,
                        retrieved_at=retrieved_at,
                    )
                )
            if news_checkpoint is not None:
                checkpoint = {
                    **news_checkpoint,
                    "documents_new": cast(int, news_checkpoint.get("documents_new", 0))
                    + documents_written,
                }
                cur.execute(
                    "UPDATE job_runs SET details = details || %s::jsonb "
                    "WHERE user_id = %s AND id = %s AND status = 'running'",
                    (_json({"news": checkpoint}), user_id, job_run_id),
                )
        return documents_written, assessments_written

    def portfolio_visualization(
        self,
        user_id: UUID,
        *,
        history_limit: int = 90,
        now: datetime | None = None,
    ) -> dict[str, object]:
        if not 2 <= history_limit <= 365:
            raise ValueError("history_limit must be between 2 and 365")
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            raise ValueError("visualization time must be timezone-aware")
        observed_at = observed_at.astimezone(UTC)

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
                    account_id,
                    environment,
                    captured_at,
                    created_at,
                    analysis_status,
                    nav_rub,
                    rub_cash_total,
                    rub_cash_blocked,
                    rub_cash_unblocked,
                    limits_loading_in_progress,
                    evidence
                FROM portfolio_snapshots
                JOIN tbank_connection USING (user_id, account_id, environment)
                WHERE user_id = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            latest_row = cur.fetchone()
            if latest_row is None:
                return {
                    "status": "pending",
                    "history": [],
                    "latest": None,
                }

            latest = dict(cast(dict[str, Any], latest_row))
            snapshot_id = cast(UUID, latest["id"])
            account_id = str(latest["account_id"])
            environment = str(latest["environment"])

            cur.execute(
                """
                SELECT
                    id,
                    captured_at,
                    created_at,
                    analysis_status,
                    nav_rub
                FROM portfolio_snapshots
                WHERE user_id = %s
                  AND account_id = %s
                  AND environment = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT %s
                """,
                (user_id, account_id, environment, history_limit),
            )
            history_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    p.instrument_uid,
                    p.figi,
                    p.ticker,
                    p.instrument_type,
                    p.quantity,
                    p.current_price_value,
                    p.current_price_currency,
                    p.average_price_fifo_value,
                    p.average_price_fifo_currency,
                    p.blocked,
                    p.blocked_lots,
                    p.value_rub,
                    p.nav_percent,
                    p.sector,
                    p.country_of_risk,
                    p.for_qual_investor,
                    COALESCE(c.instrument_uid, '') AS catalog_instrument_uid,
                    COALESCE(c.asset_uid, '') AS asset_uid,
                    COALESCE(c.name, '') AS name,
                    COALESCE(c.currency, p.current_price_currency, '') AS currency,
                    c.provider_retrieved_at AS catalog_retrieved_at,
                    COALESCE(r.state, 'data_missing') AS risk_state,
                    COALESCE(r.rating_status, 'data_missing') AS rating_status,
                    COALESCE(r.fundamental_status, 'data_missing') AS fundamental_status,
                    COALESCE(r.source_status, 'data_missing') AS source_status,
                    COALESCE(r.reasons, '[]'::jsonb) AS risk_reasons,
                    r.assessed_at
                FROM portfolio_snapshot_positions AS p
                LEFT JOIN instrument_catalog AS c
                  ON c.provider = 'tbank'
                 AND (
                     c.instrument_uid = p.instrument_uid
                     OR (p.figi <> '' AND c.figi = p.figi)
                 )
                LEFT JOIN LATERAL (
                    SELECT assessment.* FROM portfolio_risk_assessments assessment
                    JOIN portfolio_snapshots assessed ON assessed.id = assessment.snapshot_id
                        AND assessed.user_id = assessment.user_id
                    WHERE assessment.user_id = p.user_id
                        AND assessment.instrument_uid = p.instrument_uid
                        AND assessed.account_id = %s AND assessed.environment = %s
                        AND assessed.captured_at <= %s
                    ORDER BY assessment.assessed_at DESC, assessment.id DESC LIMIT 1
                ) AS r ON true
                WHERE p.snapshot_id = %s
                  AND p.user_id = %s
                ORDER BY p.nav_percent DESC NULLS LAST, p.value_rub DESC NULLS LAST, p.ticker
                """,
                (account_id, environment, latest["captured_at"], snapshot_id, user_id),
            )
            positions = [dict(row) for row in cur.fetchall()]

        captured_at = cast(datetime, latest["captured_at"]).astimezone(UTC)
        evidence = latest.get("evidence")
        analysis: dict[str, object] = {}
        if isinstance(evidence, dict):
            raw_analysis = evidence.get("analysis")
            if isinstance(raw_analysis, dict):
                analysis = dict(cast(dict[str, object], raw_analysis))

        for position in positions:
            assessed_at = cast(datetime | None, position.get("assessed_at"))
            position["assessment_freshness"] = _freshness_status(
                assessed_at,
                now=observed_at,
            )

        history = [
            {
                "snapshot_id": str(row["id"]),
                "captured_at": row["captured_at"],
                "recorded_at": row["created_at"],
                "analysis_status": row["analysis_status"],
                "nav_rub": row["nav_rub"],
            }
            for row in reversed(history_rows)
        ]
        return {
            "status": "observed",
            "history": history,
            "latest": {
                "snapshot_id": str(snapshot_id),
                "account_id": account_id,
                "environment": environment,
                "captured_at": captured_at,
                "recorded_at": latest["created_at"],
                "snapshot_freshness": _freshness_status(
                    captured_at,
                    now=observed_at,
                    max_age=PORTFOLIO_MAX_AGE,
                ),
                "analysis_status": latest["analysis_status"],
                "nav_rub": latest["nav_rub"],
                "rub_cash_total": latest["rub_cash_total"],
                "rub_cash_blocked": latest["rub_cash_blocked"],
                "rub_cash_unblocked": latest["rub_cash_unblocked"],
                "limits_loading_in_progress": latest["limits_loading_in_progress"],
                "sector_coverage_percent": analysis.get("sector_coverage_percent"),
                "valued_security_count": analysis.get("valued_security_count"),
                "security_count": analysis.get("security_count"),
                "positions": positions,
            },
        }

    def instrument_visualization(
        self,
        user_id: UUID,
        instrument_uid: str,
        *,
        history_limit: int = 90,
        now: datetime | None = None,
    ) -> dict[str, object] | None:
        if not 1 <= len(instrument_uid) <= 128 or instrument_uid != instrument_uid.strip():
            raise ValueError("instrument_uid must contain 1 to 128 non-padded characters")
        if not 2 <= history_limit <= 365:
            raise ValueError("history_limit must be between 2 and 365")
        observed_at = now or datetime.now(UTC)
        if observed_at.tzinfo is None:
            raise ValueError("visualization time must be timezone-aware")
        observed_at = observed_at.astimezone(UTC)

        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            cur.execute(
                """
                SELECT id AS current_snapshot_id, captured_at AS current_snapshot_at,
                    account_id, environment
                FROM portfolio_snapshots
                JOIN tbank_connection USING (user_id, account_id, environment)
                WHERE user_id = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            account_row = cur.fetchone()
            if account_row is None:
                return None
            account = cast(dict[str, Any], account_row)
            account_id = str(account["account_id"])
            environment = str(account["environment"])

            cur.execute(
                """
                SELECT
                    s.id AS snapshot_id,
                    s.captured_at,
                    s.created_at AS recorded_at,
                    s.analysis_status,
                    p.instrument_uid,
                    p.figi,
                    p.ticker,
                    p.instrument_type,
                    p.quantity,
                    p.current_price_value,
                    p.current_price_currency,
                    p.average_price_fifo_value,
                    p.average_price_fifo_currency,
                    p.blocked,
                    p.blocked_lots,
                    p.value_rub,
                    p.nav_percent,
                    p.sector,
                    p.country_of_risk,
                    p.for_qual_investor,
                    COALESCE(c.instrument_uid, '') AS catalog_instrument_uid,
                    COALESCE(c.asset_uid, '') AS asset_uid,
                    COALESCE(c.name, '') AS name,
                    COALESCE(c.currency, p.current_price_currency, '') AS currency,
                    c.provider_retrieved_at AS catalog_retrieved_at,
                    COALESCE(r.state, 'data_missing') AS risk_state,
                    COALESCE(r.rating_status, 'data_missing') AS rating_status,
                    COALESCE(r.fundamental_status, 'data_missing') AS fundamental_status,
                    COALESCE(r.source_status, 'data_missing') AS source_status,
                    COALESCE(r.reasons, '[]'::jsonb) AS risk_reasons,
                    COALESCE(r.evidence, '{}'::jsonb) AS risk_evidence,
                    r.assessed_at
                FROM portfolio_snapshot_positions AS p
                JOIN portfolio_snapshots AS s
                  ON s.id = p.snapshot_id
                 AND s.user_id = p.user_id
                LEFT JOIN instrument_catalog AS c
                  ON c.provider = 'tbank'
                 AND (
                     c.instrument_uid = p.instrument_uid
                     OR (p.figi <> '' AND c.figi = p.figi)
                 )
                LEFT JOIN LATERAL (
                    SELECT assessment.* FROM portfolio_risk_assessments assessment
                    JOIN portfolio_snapshots assessed ON assessed.id = assessment.snapshot_id
                        AND assessed.user_id = assessment.user_id
                    WHERE assessment.user_id = p.user_id
                        AND assessment.instrument_uid = p.instrument_uid
                        AND assessed.account_id = s.account_id
                        AND assessed.environment = s.environment
                        AND assessed.captured_at <= s.captured_at
                    ORDER BY assessment.assessed_at DESC, assessment.id DESC LIMIT 1
                ) AS r ON true
                WHERE p.user_id = %s
                  AND p.instrument_uid = %s
                  AND s.account_id = %s
                  AND s.environment = %s
                ORDER BY s.captured_at DESC, s.created_at DESC
                LIMIT %s
                """,
                (user_id, instrument_uid, account_id, environment, history_limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            if not rows:
                return None

            latest = rows[0]
            subjects = [
                value
                for value in (
                    instrument_uid,
                    str(latest.get("catalog_instrument_uid") or ""),
                    str(latest.get("asset_uid") or ""),
                )
                if value
            ]
            subjects = list(dict.fromkeys(subjects))

            cur.execute(
                f"""
                WITH payout_scope AS (
                    SELECT unnest(%s::text[]) AS instrument_uid
                ), {PAYOUT_READ_CTES}
                SELECT DISTINCT ON (
                    pe.provider,
                    pe.instrument_uid,
                    pe.event_type,
                    pe.anchor_key,
                    pe.logical_key
                )
                    pe.provider,
                    pe.instrument_uid,
                    pe.event_type,
                    pe.provider_key,
                    pe.announced_at,
                    pe.record_at,
                    pe.expected_at,
                    pe.actual_at,
                    pe.amount,
                    pe.currency,
                    pe.status,
                    pe.source_url,
                    pe.first_retrieved_at,
                    pe.retrieved_at,
                    pe.identity_ambiguous
                FROM payout_observations AS pe
                WHERE NOT pe.identity_ambiguous OR pe.retrieved_at = pe.latest_positive_at
                ORDER BY
                    pe.provider,
                    pe.instrument_uid,
                    pe.event_type,
                    pe.anchor_key,
                    pe.logical_key,
                    pe.retrieved_at DESC,
                    pe.id DESC
                LIMIT 100
                """,
                (subjects,),
            )
            payouts = [_payout_payload(dict(row)) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    sd.provider,
                    sd.document_type,
                    sd.subject_uid,
                    sd.source_url,
                    sd.published_at,
                    sd.effective_at,
                    max(sr.retrieved_at) AS retrieved_at,
                    count(DISTINCT sd.id) AS versions
                FROM source_documents AS sd
                JOIN source_retrievals AS sr
                  ON sr.source_document_id = sd.id
                WHERE sd.subject_uid = ANY (%s)
                GROUP BY
                    sd.provider,
                    sd.document_type,
                    sd.subject_uid,
                    sd.source_url,
                    sd.published_at,
                    sd.effective_at
                ORDER BY max(sr.retrieved_at) DESC
                LIMIT 100
                """,
                (subjects,),
            )
            sources = [dict(row) for row in cur.fetchall()]

        latest_captured_at = cast(datetime, latest["captured_at"]).astimezone(UTC)
        for source in sources:
            retrieved_at = cast(datetime | None, source.get("retrieved_at"))
            source["freshness_status"] = _freshness_status(
                retrieved_at,
                now=observed_at,
            )
        history = [
            {
                "snapshot_id": str(row["snapshot_id"]),
                "captured_at": row["captured_at"],
                "recorded_at": row["recorded_at"],
                "analysis_status": row["analysis_status"],
                "quantity": row["quantity"],
                "price_value": row["current_price_value"],
                "price_currency": row["current_price_currency"],
                "value_rub": row["value_rub"],
                "nav_percent": row["nav_percent"],
                "blocked": row["blocked"],
                "blocked_lots": row["blocked_lots"],
            }
            for row in reversed(rows)
        ]
        return {
            "status": "observed",
            "account_id": account_id,
            "environment": environment,
            "snapshot_freshness": _freshness_status(
                latest_captured_at,
                now=observed_at,
                max_age=PORTFOLIO_MAX_AGE,
            ),
            "latest": {
                key: value
                for key, value in latest.items()
                if key not in {"risk_evidence"}
            },
            "current_holding": {
                "status": "held" if latest["snapshot_id"] == account["current_snapshot_id"]
                and latest["quantity"] != 0 else "not_held",
                "quantity": str(latest["quantity"])
                if latest["snapshot_id"] == account["current_snapshot_id"] else "0",
                "observed_at": account["current_snapshot_at"].isoformat(),
            },
            "risk_evidence": latest.get("risk_evidence") or {},
            "history": history,
            "payouts": payouts,
            "sources": sources,
        }

    def latest_balancing_context(
        self,
        user_id: UUID,
        *,
        candidate_limit: int = 100,
    ) -> dict[str, object] | None:
        if not 1 <= candidate_limit <= 500:
            raise ValueError("candidate_limit must be between 1 and 500")
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
                    account_id,
                    environment,
                    captured_at,
                    analysis_status,
                    nav_rub,
                    rub_cash_unblocked,
                    limits_loading_in_progress,
                    evidence
                FROM portfolio_snapshots
                JOIN tbank_connection USING (user_id, account_id, environment)
                WHERE user_id = %s
                ORDER BY captured_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            fetched = cur.fetchone()
            if fetched is None:
                return None
            snapshot = dict(cast(dict[str, Any], fetched))
            snapshot_id = cast(UUID, snapshot["id"])
            account_id = str(snapshot["account_id"])

            # Quick NAV snapshots intentionally omit UsersService/GetInfo. Keep
            # the last actual response and its own time within this account.
            cur.execute(
                "SELECT captured_at, evidence->'broker_user' AS document "
                "FROM portfolio_snapshots WHERE user_id = %s AND account_id = %s "
                "AND environment = %s AND captured_at <= %s "
                "AND jsonb_typeof(evidence->'broker_user') = 'object' "
                "ORDER BY captured_at DESC, created_at DESC, id DESC LIMIT 1",
                (user_id, account_id, snapshot["environment"], snapshot["captured_at"]),
            )
            broker_user_source = cast(dict[str, Any] | None, cur.fetchone())

            cur.execute(
                """
                SELECT
                    p.instrument_uid,
                    p.figi,
                    p.ticker,
                    p.instrument_type,
                    p.quantity,
                    p.quantity_lots,
                    p.average_price_fifo_value,
                    p.average_price_fifo_currency,
                    p.blocked,
                    p.blocked_lots,
                    p.value_rub,
                    p.sector,
                    COALESCE(c.asset_uid, '') AS asset_uid,
                    COALESCE(c.name, '') AS name,
                    COALESCE(c.isin, '') AS isin,
                    COALESCE(c.class_code, '') AS class_code,
                    COALESCE(c.lot, 0) AS lot,
                    COALESCE(c.currency, '') AS currency,
                    c.nominal_value,
                    COALESCE(c.nominal_currency, '') AS nominal_currency,
                    c.maturity_date,
                    c.floating_coupon,
                    c.perpetual,
                    c.amortization,
                    c.subordinated,
                    c.liquidity,
                    c.provider_retrieved_at,
                    COALESCE(i.id::text, '') AS issuer_id,
                    COALESCE(i.group_id::text, '') AS group_id,
                    COALESCE(i.country_code, '') AS issuer_country_code,
                    COALESCE(i.source_url, '') AS issuer_source_url,
                    i.verified_at AS issuer_verified_at,
                    i.effective_at AS issuer_effective_at,
                    COALESCE(m.source_url, '') AS mapping_source_url,
                    COALESCE(g.source_url, '') AS group_source_url,
                    m.verified_at AS mapping_verified_at,
                    m.effective_at AS mapping_effective_at,
                    g.verified_at AS group_verified_at,
                    g.effective_at AS group_effective_at,
                    COALESCE(r.state, 'data_missing') AS risk_state,
                    COALESCE(r.rating_status, 'data_missing') AS rating_status
                FROM portfolio_snapshot_positions AS p
                LEFT JOIN instrument_catalog AS c
                  ON c.provider = 'tbank'
                 AND (
                     c.instrument_uid = p.instrument_uid
                     OR (p.figi <> '' AND c.figi = p.figi)
                 )
                LEFT JOIN instrument_issuer_map AS m
                  ON m.provider = 'tbank'
                 AND m.instrument_uid = c.instrument_uid
                LEFT JOIN issuers AS i
                  ON i.id = m.issuer_id
                LEFT JOIN issuer_groups AS g ON g.id = i.group_id
                LEFT JOIN LATERAL (
                    SELECT assessment.* FROM portfolio_risk_assessments assessment
                    JOIN portfolio_snapshots assessed ON assessed.id = assessment.snapshot_id
                        AND assessed.user_id = assessment.user_id
                    JOIN portfolio_snapshots current_snapshot
                        ON current_snapshot.id = p.snapshot_id
                        AND current_snapshot.user_id = p.user_id
                    WHERE assessment.user_id = p.user_id
                        AND assessment.instrument_uid = p.instrument_uid
                        AND assessed.account_id = current_snapshot.account_id
                        AND assessed.environment = current_snapshot.environment
                        AND assessed.captured_at <= current_snapshot.captured_at
                    ORDER BY assessment.assessed_at DESC, assessment.id DESC LIMIT 1
                ) AS r ON true
                WHERE p.snapshot_id = %s
                  AND p.user_id = %s
                ORDER BY p.value_rub DESC NULLS LAST, p.ticker
                """,
                (snapshot_id, user_id),
            )
            holdings = [dict(row) for row in cur.fetchall()]

            cur.execute(
                "SELECT evidence.version, evidence.received_at, asset->>'instrument_uid' "
                "AS instrument_uid, asset->'facts'->'issuer_id' AS issuer, "
                "asset->'facts'->'group_id' AS issuer_group "
                "FROM strategy_research_evidence evidence, "
                "LATERAL jsonb_array_elements(evidence.document->'assets') asset "
                "WHERE evidence.user_id = %s AND asset->>'instrument_uid' = ANY (%s) "
                "AND (asset->'facts' ? 'issuer_id' OR asset->'facts' ? 'group_id')",
                (user_id, [row["instrument_uid"] for row in holdings]),
            )
            issuer_imports = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT
                    c.instrument_uid,
                    c.figi,
                    c.asset_uid,
                    c.ticker,
                    c.name,
                    c.isin,
                    c.instrument_type,
                    c.currency,
                    c.class_code,
                    c.lot,
                    c.sector,
                    c.country_of_risk,
                    c.for_qual_investor,
                    c.for_iis,
                    c.api_trade_available,
                    c.buy_available,
                    c.sell_available,
                    c.nominal_value,
                    c.nominal_currency,
                    c.maturity_date,
                    c.floating_coupon,
                    c.perpetual,
                    c.amortization,
                    c.subordinated,
                    c.liquidity,
                    c.provider_retrieved_at,
                    a.required_tests,
                    a.observed_at AS access_observed_at,
                    COALESCE(i.id::text, '') AS issuer_id,
                    COALESCE(i.group_id::text, '') AS group_id,
                    COALESCE(i.country_code, '') AS issuer_country_code,
                    COALESCE(i.source_url, '') AS issuer_source_url,
                    i.verified_at AS issuer_verified_at,
                    i.effective_at AS issuer_effective_at,
                    COALESCE(m.source_url, '') AS mapping_source_url,
                    m.verified_at AS mapping_verified_at,
                    m.effective_at AS mapping_effective_at,
                    COALESCE(g.source_url, '') AS group_source_url,
                    g.verified_at AS group_verified_at,
                    g.effective_at AS group_effective_at
                FROM instrument_catalog AS c
                JOIN account_instrument_access AS a
                  ON a.user_id = %s
                 AND a.account_id = %s
                 AND a.provider = c.provider
                 AND a.instrument_uid = c.instrument_uid
                LEFT JOIN instrument_issuer_map AS m
                  ON m.provider = c.provider
                 AND m.instrument_uid = c.instrument_uid
                LEFT JOIN issuers AS i
                  ON i.id = m.issuer_id
                LEFT JOIN issuer_groups AS g ON g.id = i.group_id
                WHERE c.provider = 'tbank'
                  AND c.instrument_type = ANY (ARRAY['share', 'bond', 'etf'])
                  AND c.currency = 'RUB'
                ORDER BY
                    row_number() OVER (PARTITION BY c.instrument_type
                        ORDER BY c.ticker, c.instrument_uid),
                    CASE c.instrument_type
                        WHEN 'bond' THEN 0
                        WHEN 'share' THEN 1
                        ELSE 2
                    END,
                    c.ticker,
                    c.instrument_uid
                LIMIT %s
                """,
                (user_id, account_id, candidate_limit),
            )
            candidates = [dict(row) for row in cur.fetchall()]

        evidence = snapshot.get("evidence")
        broker_user: dict[str, object] = {}
        broker_user_as_of = None
        account: dict[str, object] = {}
        if broker_user_source is not None:
            broker_user = dict(broker_user_source["document"])
            broker_user_as_of = broker_user_source["captured_at"]
        if isinstance(evidence, dict):
            account_raw = evidence.get("account")
            if isinstance(account_raw, dict):
                account = dict(cast(dict[str, object], account_raw))

        return {
            "snapshot_id": str(snapshot_id),
            "account_id": account_id,
            "captured_at": snapshot["captured_at"],
            "analysis_status": snapshot["analysis_status"],
            "nav_rub": snapshot["nav_rub"],
            "rub_cash_unblocked": snapshot["rub_cash_unblocked"],
            "limits_loading_in_progress": snapshot["limits_loading_in_progress"],
            "broker_user": broker_user,
            "broker_user_as_of": broker_user_as_of,
            "broker_user_time_basis": "source_snapshot",
            "broker_user_freshness": _freshness_status(
                broker_user_as_of, now=datetime.now(UTC), max_age=PORTFOLIO_MAX_AGE,
            ),
            "account": account,
            "holdings": holdings,
            "candidates": candidates,
            "issuer_imports": issuer_imports,
        }

    def save_history_page(
        self,
        user_id: UUID,
        *,
        job_run_id: UUID,
        account_id: str,
        environment: str,
        window_from: datetime,
        window_to: datetime,
        page: TBankOperationsPage,
        observed_at: datetime,
    ) -> int:
        if window_from.tzinfo is None or window_to.tzinfo is None:
            raise ValueError("history window must be timezone-aware")

        inserted = 0
        with (
            self.database.pool.connection() as conn,
            conn.transaction(),
            conn.cursor() as cur,
        ):
            self._tenant(cur, user_id)
            _require_observation_job(
                cur, user_id, job_run_id, account_id=account_id, environment=environment,
            )
            for operation in page.items:
                inserted += int(
                    _save_operation_observation(
                        cur,
                        user_id=user_id,
                        account_id=account_id,
                        operation=operation,
                        observed_at=observed_at,
                    )
                )
            _save_history_sync_state(
                cur,
                user_id=user_id,
                account_id=account_id,
                window_from=window_from,
                window_to=window_to,
                page=page,
            )
        return inserted


def _payout_payload(payout: dict[str, Any]) -> dict[str, Any]:
    if payout.pop("identity_ambiguous"):
        payout.update(
            identity_status="ambiguous",
            identity_reason="co_observed_anchor_collision",
        )
    return payout


def _age_seconds(value: datetime | None, *, now: datetime) -> int | None:
    if value is None or value.tzinfo is None or now.tzinfo is None:
        return None
    delta = now.astimezone(UTC) - value.astimezone(UTC)
    if delta.total_seconds() < 0:
        return None
    return int(delta.total_seconds())


def _freshness_status(
    value: datetime | None,
    *,
    now: datetime,
    max_age: timedelta = EVIDENCE_RETRIEVAL_MAX_AGE,
) -> Literal["fresh", "stale", "data_missing"]:
    if value is None:
        return "data_missing"
    age = _age_seconds(value, now=now)
    if age is None:
        return "stale"
    return (
        "stale"
        if age >= int(max_age.total_seconds())
        else "fresh"
    )


def _profile(row: dict[str, Any]) -> InvestmentProfileRecord:
    return InvestmentProfileRecord(
        id=int(row["id"]),
        user_id=cast(UUID, row["user_id"]),
        version=int(row["version"]),
        reserve_rub=Decimal(row["reserve_rub"]),
        planned_withdrawal_rub=Decimal(row["planned_withdrawal_rub"]),
        horizon_months=int(row["horizon_months"]),
        max_drawdown_percent=Decimal(row["max_drawdown_percent"]),
        liquidity_horizon_days=int(row["liquidity_horizon_days"]),
        allow_below_investment_grade=bool(row["allow_below_investment_grade"]),
        created_at=cast(datetime, row["created_at"]),
    )


def _balancing_policy(row: dict[str, Any]) -> BalancingPolicyRecord:
    return BalancingPolicyRecord(
        id=int(row["id"]),
        user_id=cast(UUID, row["user_id"]),
        version=int(row["version"]),
        max_instrument_percent=Decimal(row["max_instrument_percent"]),
        max_sector_percent=Decimal(row["max_sector_percent"]),
        max_issuer_percent=Decimal(row["max_issuer_percent"]),
        max_group_percent=Decimal(row["max_group_percent"]),
        max_share_percent=Decimal(row["max_share_percent"]),
        max_bond_percent=Decimal(row["max_bond_percent"]),
        max_etf_percent=Decimal(row["max_etf_percent"]),
        max_below_grade_percent=Decimal(row["max_below_grade_percent"]),
        max_unknown_percent=Decimal(row["max_unknown_percent"]),
        max_term_months=int(row["max_term_months"]),
        turnover_budget_percent=Decimal(row["turnover_budget_percent"]),
        max_daily_turnover_participation_percent=Decimal(
            row["max_daily_turnover_participation_percent"]
        ),
        securities_tax_rate_percent=Decimal(row["securities_tax_rate_percent"]),
        uncertainty_haircut_percent=Decimal(row["uncertainty_haircut_percent"]),
        credit_loss_haircut_percent=Decimal(row["credit_loss_haircut_percent"]),
        no_trade_band_percent=Decimal(row["no_trade_band_percent"]),
        min_replace_benefit_rub=Decimal(row["min_replace_benefit_rub"]),
        created_at=cast(datetime, row["created_at"]),
    )


def _proposal_record(row: dict[str, Any]) -> PortfolioProposalRecord:
    return PortfolioProposalRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        version=int(row["version"]),
        source_snapshot_id=cast(UUID, row["source_snapshot_id"]),
        account_id=str(row["account_id"]),
        profile_version=int(row["profile_version"]),
        policy_version=int(row["policy_version"]),
        scenario_kind=str(row["scenario_kind"]),
        target_instrument_uid=cast(str | None, row.get("target_instrument_uid")),
        replaced_instrument_uid=cast(
            str | None,
            row.get("replaced_instrument_uid"),
        ),
        proposal_hash=bytes(row["proposal_hash"]),
        payload=dict(cast(dict[str, Any], row["payload"])),
        created_at=cast(datetime, row["created_at"]),
        expires_at=cast(datetime, row["expires_at"]),
        status=str(row.get("status") or "pending"),
        decision_reason=str(row.get("decision_reason") or ""),
        decision_user_reason=str(row.get("decision_user_reason") or ""),
        deferred_until=cast(datetime | None, row.get("deferred_until")),
        decided_at=cast(datetime | None, row.get("decided_at")),
    )


def _job_run(row: dict[str, Any]) -> JobRunRecord:
    scheduled_for = row["scheduled_for"]
    if scheduled_for is None and row["job_type"] == "portfolio_daily":
        scheduled_for = date.fromisoformat(row["details"]["scheduled_for"])
    return JobRunRecord(
        id=cast(UUID, row["id"]),
        user_id=cast(UUID, row["user_id"]),
        job_type=str(row["job_type"]),
        scheduled_for=cast(date | None, scheduled_for),
        status=cast(JobStatus, str(row["status"])),
        attempt=int(row["attempt"]),
        started_at=cast(datetime, row["started_at"]),
        finished_at=cast(datetime | None, row["finished_at"]),
        refresh_scope="quick" if row["details"].get("refresh_scope") == "quick" else "full",
    )


def _sync_state(row: dict[str, Any]) -> BrokerSyncState:
    return BrokerSyncState(
        user_id=cast(UUID, row["user_id"]),
        account_id=str(row["account_id"]),
        history_window_from=cast(datetime | None, row["history_window_from"]),
        history_window_to=cast(datetime | None, row["history_window_to"]),
        pending_cursor=str(row["pending_cursor"]),
        last_complete_watermark=cast(datetime | None, row["last_complete_watermark"]),
        updated_at=cast(datetime, row["updated_at"]),
    )


def _money_decimal(value: TBankMoney | None) -> Decimal | None:
    return Decimal(value.value) if value is not None else None


def _money_payload(value: TBankMoney | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"currency": value.currency, "value": value.value}


def _operation_payload(operation: TBankOperation) -> dict[str, object]:
    return {
        "provider_operation_id": operation.id,
        "parent_operation_id": operation.parent_operation_id,
        "broker_account_id": operation.broker_account_id,
        "name": operation.name,
        "date": operation.date.astimezone(UTC).isoformat(),
        "operation_type": operation.operation_type,
        "description": operation.description,
        "state": operation.state,
        "instrument_uid": operation.instrument_uid,
        "figi": operation.figi,
        "instrument_type": operation.instrument_type,
        "position_uid": operation.position_uid,
        "ticker": operation.ticker,
        "class_code": operation.class_code,
        "payment": _money_payload(operation.payment),
        "price": _money_payload(operation.price),
        "commission": _money_payload(operation.commission),
        "accrued_int": _money_payload(operation.accrued_int),
        "quantity": operation.quantity,
        "quantity_rest": operation.quantity_rest,
        "quantity_done": operation.quantity_done,
        "asset_uid": operation.asset_uid,
        "trades": [
            {
                "num": trade.num,
                "date": trade.date.astimezone(UTC).isoformat(),
                "quantity": trade.quantity,
                "price": _money_payload(trade.price),
            }
            for trade in operation.trades
        ],
    }


def _semantic_operation_payload(normalized: dict[str, object]) -> dict[str, object]:
    # T-Invest documents that operation IDs may change over time. The provider ID
    # is retained as provenance but excluded from this semantic lineage hash.
    return {
        key: value
        for key, value in normalized.items()
        if key not in {"provider_operation_id", "parent_operation_id"}
    }


def _hash_json(value: Mapping[str, object]) -> bytes:
    return hashlib.sha256(
        _json(value).encode("utf-8"),
        usedforsecurity=False,
    ).digest()


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    )


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")
