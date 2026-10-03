from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database
from omnicio.execution_store import ExecutionLedgerError, ExecutionStore
from omnicio.portfolio_store import PortfolioStore, ProposalStateError

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="ephemeral PostgreSQL is only available in the hosted migration gate",
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(sorted((ROOT / "migrations").glob("*.sql")))
USER_ONE = UUID("00000000-0000-0000-0000-000000000101")
USER_TWO = UUID("00000000-0000-0000-0000-000000000102")
RUNTIME_PASSWORD = secrets.token_urlsafe(32)


def _runtime_url() -> str:
    values = conninfo_to_dict(DATABASE_URL)
    values["user"] = "omnicio_runtime_test"
    values["password"] = RUNTIME_PASSWORD
    return make_conninfo(**values)


def _apply_all_migrations() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text())


def test_r6_execution_migration_has_valid_guards_and_event_lineage() -> None:
    migration = (ROOT / "migrations" / "0010_portfolio_execution.sql").read_text()

    assert "omnicio_validate_execution_run_source" in migration
    assert "AS $omnicio$" in migration
    assert "execution leg source fields are immutable" in migration
    assert "portfolio_execution_legs_source_guard" in migration
    assert "UNIQUE (id, run_id, user_id)" in migration
    assert "FOREIGN KEY (leg_id, run_id, user_id)" in migration
    assert "REFERENCES portfolio_execution_legs(id, run_id, user_id)" in migration
    assert "p.expires_at > now()" in migration
    assert "p.source_snapshot_id, p.account_id" in migration


def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-1] == "0010_portfolio_execution.sql"
    _apply_all_migrations()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive R6 migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute((ROOT / "migrations" / "0010_portfolio_execution.sql").read_text())

        table_names = {
            row[0]
            for row in admin.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            ).fetchall()
        }
        assert {
            "instrument_catalog",
            "account_instrument_access",
            "investment_profile_versions",
            "job_runs",
            "portfolio_snapshots",
            "portfolio_snapshot_positions",
            "operation_observations",
            "broker_sync_state",
            "source_documents",
            "source_retrievals",
            "source_facts",
            "payout_events",
            "portfolio_risk_assessments",
            "balancing_policy_versions",
            "portfolio_proposals",
            "portfolio_proposal_actions",
            "portfolio_execution_runs",
            "portfolio_execution_legs",
            "portfolio_execution_events",
        } <= table_names

        protected = {
            row[0]: (row[1], row[2])
            for row in admin.execute(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = ANY (
                      ARRAY[
                          'account_instrument_access',
                          'investment_profile_versions',
                          'job_runs',
                          'portfolio_snapshots',
                          'portfolio_snapshot_positions',
                          'operation_observations',
                          'broker_sync_state',
                          'portfolio_risk_assessments',
                          'balancing_policy_versions',
                          'portfolio_proposals',
                          'portfolio_proposal_actions',
                          'portfolio_execution_runs',
                          'portfolio_execution_legs',
                          'portfolio_execution_events'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 14
        assert all(rls and forced for rls, forced in protected.values())

        catalog_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'instrument_catalog'
                """
            ).fetchall()
        }
        assert "required_tests" not in catalog_columns
        assert {
            "nominal_value",
            "nominal_currency",
            "maturity_date",
            "floating_coupon",
            "perpetual",
            "amortization",
            "subordinated",
            "liquidity",
        } <= catalog_columns

        proposal_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'portfolio_proposals'
                """
            ).fetchall()
        }
        assert {
            "account_id",
            "created_session_digest",
            "proposal_hash",
            "payload",
            "expires_at",
        } <= proposal_columns

        proposal_action_columns = {
            row[0]
            for row in admin.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'portfolio_proposal_actions'
                """
            ).fetchall()
        }
        assert {
            "session_digest",
            "user_reason",
            "deferred_until",
            "proposal_hash",
        } <= proposal_action_columns

        semantic_indexes = {
            row[0]
            for row in admin.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'operation_observations'
                """
            ).fetchall()
        }
        assert "operation_observations_semantic_unique_idx" in semantic_indexes

        admin.execute(
            """
            INSERT INTO users (id)
            VALUES (%s), (%s)
            """,
            (USER_ONE, USER_TWO),
        )
        admin.execute(
            """
            INSERT INTO instrument_catalog (
                provider,
                instrument_uid,
                instrument_type,
                provider_retrieved_at
            )
            VALUES ('tbank', 'instrument-1', 'share', now())
            """
        )

        admin.execute("DROP ROLE IF EXISTS omnicio_runtime_test")
        admin.execute(
            sql.SQL(
                """
                CREATE ROLE {}
                LOGIN
                PASSWORD {}
                NOSUPERUSER
                NOCREATEDB
                NOCREATEROLE
                NOINHERIT
                NOREPLICATION
                """
            ).format(
                sql.Identifier("omnicio_runtime_test"),
                sql.Literal(RUNTIME_PASSWORD),
            )
        )
        admin.execute("GRANT CONNECT ON DATABASE omnicio_test TO omnicio_runtime_test")
        admin.execute("GRANT USAGE ON SCHEMA public TO omnicio_runtime_test")
        admin.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            "TO omnicio_runtime_test"
        )
        admin.execute(
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public "
            "TO omnicio_runtime_test"
        )

    with psycopg.connect(_runtime_url(), autocommit=True) as runtime:
        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_ONE),),
        )
        runtime.execute(
            """
            INSERT INTO investment_profile_versions (
                user_id,
                version,
                reserve_rub,
                planned_withdrawal_rub,
                horizon_months,
                max_drawdown_percent,
                liquidity_horizon_days,
                allow_below_investment_grade
            )
            VALUES (%s, 1, 100000, 0, 60, 20, 30, false)
            """,
            (USER_ONE,),
        )
        runtime.execute(
            """
            INSERT INTO account_instrument_access (
                user_id,
                account_id,
                provider,
                instrument_uid,
                required_tests,
                observed_at
            )
            VALUES (%s, 'account-1', 'tbank', 'instrument-1', '["test-one"]'::jsonb, now())
            """,
            (USER_ONE,),
        )
        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_TWO),),
        )
        assert runtime.execute(
            "SELECT count(*) FROM investment_profile_versions"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM account_instrument_access"
        ).fetchone()[0] == 0

        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_ONE),),
        )
        job_id = runtime.execute(
            """
            INSERT INTO job_runs (
                user_id,
                job_type,
                scheduled_for,
                status,
                attempt,
                started_at
            )
            VALUES (%s, 'portfolio_daily', current_date, 'running', 1, now())
            RETURNING id
            """,
            (USER_ONE,),
        ).fetchone()[0]
        snapshot_id = runtime.execute(
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
            VALUES (
                %s, %s, 'account-1', 'prod', now(), 'observed',
                1000, 100, 0, 100, false, '{}'::jsonb
            )
            RETURNING id
            """,
            (USER_ONE, job_id),
        ).fetchone()[0]
        runtime.execute(
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
                %s, %s, 'instrument-1', 'data_missing', 'data_missing',
                'received', 'received', '[]'::jsonb, '{}'::jsonb, now()
            )
            """,
            (USER_ONE, snapshot_id),
        )

        source_id = runtime.execute(
            """
            INSERT INTO source_documents (
                provider,
                document_type,
                subject_uid,
                provider_key,
                source_url,
                first_retrieved_at,
                content_hash,
                payload
            )
            VALUES (
                'test', 'fundamental', 'asset-1', 'v1',
                'https://example.invalid/evidence', now(),
                decode(repeat('00', 32), 'hex'), '{"value": 1}'::jsonb
            )
            RETURNING id
            """
        ).fetchone()[0]
        with pytest.raises(psycopg.errors.RaiseException, match="immutable evidence"):
            runtime.execute(
                "UPDATE source_documents SET provider_key = 'changed' WHERE id = %s",
                (source_id,),
            )

        runtime.execute(
            """
            INSERT INTO instrument_catalog (
                provider,
                instrument_uid,
                figi,
                asset_uid,
                instrument_type,
                provider_retrieved_at
            )
            VALUES (
                'tbank',
                'provider-bond-uid',
                'FIGI-ONLY',
                'asset-fallback',
                'bond',
                now()
            )
            """
        )
        runtime.execute(
            """
            INSERT INTO portfolio_snapshot_positions (
                snapshot_id,
                user_id,
                instrument_uid,
                figi,
                ticker,
                instrument_type,
                quantity,
                blocked,
                blocked_lots,
                sector,
                country_of_risk
            )
            VALUES (
                %s,
                %s,
                'FIGI-ONLY',
                'FIGI-ONLY',
                'TESTBOND',
                'bond',
                1,
                false,
                0,
                'finance',
                'RU'
            )
            """,
            (snapshot_id, USER_ONE),
        )
        payout_source_id = runtime.execute(
            """
            INSERT INTO source_documents (
                provider,
                document_type,
                subject_uid,
                provider_key,
                source_url,
                first_retrieved_at,
                content_hash,
                payload
            )
            VALUES (
                'tbank',
                'bond_coupon',
                'provider-bond-uid',
                'coupon-1',
                'https://developer.tbank.ru/invest/services/instruments/methods',
                now(),
                decode(repeat('11', 32), 'hex'),
                '{"coupon": 1}'::jsonb
            )
            RETURNING id
            """
        ).fetchone()[0]
        runtime.execute(
            """
            INSERT INTO source_retrievals (source_document_id, retrieved_at)
            VALUES (%s, now())
            """,
            (payout_source_id,),
        )
        runtime.execute(
            """
            INSERT INTO payout_events (
                source_document_id,
                provider,
                instrument_uid,
                event_type,
                provider_key,
                expected_at,
                amount,
                currency,
                status,
                payload,
                semantic_hash
            )
            VALUES (
                %s,
                'tbank',
                'provider-bond-uid',
                'coupon',
                'coupon-1',
                now() + interval '30 days',
                42,
                'RUB',
                'scheduled',
                '{"coupon": 1}'::jsonb,
                decode(repeat('22', 32), 'hex')
            )
            """,
            (payout_source_id,),
        )

        database = Database(_runtime_url())
        database.open()
        try:
            store = PortfolioStore(database)
            first_policy = store.save_balancing_policy(
                USER_ONE,
                max_instrument_percent=Decimal("20"),
                max_sector_percent=Decimal("30"),
                max_issuer_percent=Decimal("20"),
                max_group_percent=Decimal("25"),
                max_share_percent=Decimal("70"),
                max_bond_percent=Decimal("80"),
                max_etf_percent=Decimal("70"),
                max_below_grade_percent=Decimal("5"),
                max_unknown_percent=Decimal("0"),
                max_term_months=120,
                turnover_budget_percent=Decimal("25"),
                max_daily_turnover_participation_percent=Decimal("5"),
                securities_tax_rate_percent=Decimal("15"),
                uncertainty_haircut_percent=Decimal("3"),
                credit_loss_haircut_percent=Decimal("2"),
                no_trade_band_percent=Decimal("1"),
                min_replace_benefit_rub=Decimal("500"),
            )
            duplicate_policy = store.save_balancing_policy(
                USER_ONE,
                max_instrument_percent=Decimal("20"),
                max_sector_percent=Decimal("30"),
                max_issuer_percent=Decimal("20"),
                max_group_percent=Decimal("25"),
                max_share_percent=Decimal("70"),
                max_bond_percent=Decimal("80"),
                max_etf_percent=Decimal("70"),
                max_below_grade_percent=Decimal("5"),
                max_unknown_percent=Decimal("0"),
                max_term_months=120,
                turnover_budget_percent=Decimal("25"),
                max_daily_turnover_participation_percent=Decimal("5"),
                securities_tax_rate_percent=Decimal("15"),
                uncertainty_haircut_percent=Decimal("3"),
                credit_loss_haircut_percent=Decimal("2"),
                no_trade_band_percent=Decimal("1"),
                min_replace_benefit_rub=Decimal("500"),
            )
            revised_policy = store.save_balancing_policy(
                USER_ONE,
                max_instrument_percent=Decimal("15"),
                max_sector_percent=Decimal("30"),
                max_issuer_percent=Decimal("20"),
                max_group_percent=Decimal("25"),
                max_share_percent=Decimal("70"),
                max_bond_percent=Decimal("80"),
                max_etf_percent=Decimal("70"),
                max_below_grade_percent=Decimal("5"),
                max_unknown_percent=Decimal("0"),
                max_term_months=120,
                turnover_budget_percent=Decimal("25"),
                max_daily_turnover_participation_percent=Decimal("5"),
                securities_tax_rate_percent=Decimal("15"),
                uncertainty_haircut_percent=Decimal("3"),
                credit_loss_haircut_percent=Decimal("2"),
                no_trade_band_percent=Decimal("1"),
                min_replace_benefit_rub=Decimal("500"),
            )
            current_policy = store.current_balancing_policy(USER_ONE)
            created_at = datetime.now(UTC)
            first_proposal = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="instrument-1",
                replaced_instrument_uid=None,
                proposal_hash=b"p" * 32,
                session_digest=b"s" * 32,
                payload={"schema": "omnicio.portfolio.proposal.v1", "trades": []},
                expires_at=created_at + timedelta(minutes=10),
            )
            proposal_before = store.proposals(USER_ONE)
            decided_proposal, confirmed = store.decide_proposal(
                USER_ONE,
                proposal_id=first_proposal.id,
                expected_version=first_proposal.version,
                expected_hash=first_proposal.proposal_hash,
                action="confirmed",
                session_digest=b"d" * 32,
                user_reason="",
                deferred_until=None,
                material_current=True,
                now=created_at + timedelta(minutes=1),
            )
            with pytest.raises(
                ProposalStateError,
                match="proposal_already_decided",
            ):
                store.decide_proposal(
                    USER_ONE,
                    proposal_id=first_proposal.id,
                    expected_version=first_proposal.version,
                    expected_hash=first_proposal.proposal_hash,
                    action="confirmed",
                    session_digest=b"d" * 32,
                    user_reason="",
                    deferred_until=None,
                    material_current=True,
                    now=created_at + timedelta(minutes=2),
                )

            stale_material = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="instrument-1",
                replaced_instrument_uid=None,
                proposal_hash=b"m" * 32,
                session_digest=b"s" * 32,
                payload={"schema": "omnicio.portfolio.proposal.v1", "trades": []},
                expires_at=created_at + timedelta(minutes=10),
            )
            stale_proposal, stale_action = store.decide_proposal(
                USER_ONE,
                proposal_id=stale_material.id,
                expected_version=stale_material.version,
                expected_hash=stale_material.proposal_hash,
                action="confirmed",
                session_digest=b"d" * 32,
                user_reason="",
                deferred_until=None,
                material_current=False,
                now=created_at + timedelta(minutes=2),
            )

            pending = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="instrument-1",
                replaced_instrument_uid=None,
                proposal_hash=b"q" * 32,
                session_digest=b"s" * 32,
                payload={"schema": "omnicio.portfolio.proposal.v1", "trades": []},
                expires_at=created_at + timedelta(minutes=10),
            )
            newest = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="instrument-1",
                replaced_instrument_uid=None,
                proposal_hash=b"r" * 32,
                session_digest=b"s" * 32,
                payload={"schema": "omnicio.portfolio.proposal.v1", "trades": []},
                expires_at=created_at + timedelta(minutes=10),
            )
            proposal_after_supersede = store.proposals(USER_ONE)
            expired_proposal, expired_action = store.decide_proposal(
                USER_ONE,
                proposal_id=newest.id,
                expected_version=newest.version,
                expected_hash=newest.proposal_hash,
                action="deferred",
                session_digest=b"d" * 32,
                user_reason="wait",
                deferred_until=created_at + timedelta(hours=2),
                material_current=True,
                now=created_at + timedelta(hours=1),
            )
            execution_ready = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="provider-bond-uid",
                replaced_instrument_uid=None,
                proposal_hash=b"x" * 32,
                session_digest=b"s" * 32,
                payload={
                    "schema": "omnicio.portfolio.proposal.v1",
                    "execution_enabled": False,
                    "source": {
                        "snapshot_id": str(snapshot_id),
                        "account_id": "account-1",
                        "profile_version": 1,
                        "policy_version": 2,
                    },
                    "scenario": {
                        "status": "feasible",
                        "trades": [
                            {
                                "action": "buy",
                                "instrument_uid": "provider-bond-uid",
                                "ticker": "BOND",
                                "lots": 2,
                                "limit_price": "101.25",
                                "limit_price_type": "point",
                                "max_spend_rub": "2500",
                                "min_proceeds_rub": None,
                            }
                        ],
                    },
                },
                expires_at=created_at + timedelta(minutes=10),
            )
            execution_proposal, execution_confirmation = store.decide_proposal(
                USER_ONE,
                proposal_id=execution_ready.id,
                expected_version=execution_ready.version,
                expected_hash=execution_ready.proposal_hash,
                action="confirmed",
                session_digest=b"d" * 32,
                user_reason="",
                deferred_until=None,
                material_current=True,
                now=created_at + timedelta(minutes=3),
            )
            execution_store = ExecutionStore(database)
            shadow_run, shadow_legs = execution_store.create_run(
                USER_ONE,
                proposal_id=execution_proposal.id,
                expected_version=execution_proposal.version,
                expected_hash=execution_proposal.proposal_hash,
                mode="shadow",
                session_digest=b"e" * 32,
            )
            duplicate_run, duplicate_legs = execution_store.create_run(
                USER_ONE,
                proposal_id=execution_proposal.id,
                expected_version=execution_proposal.version,
                expected_hash=execution_proposal.proposal_hash,
                mode="shadow",
                session_digest=b"e" * 32,
            )
            sandbox_run, sandbox_legs = execution_store.create_run(
                USER_ONE,
                proposal_id=execution_proposal.id,
                expected_version=execution_proposal.version,
                expected_hash=execution_proposal.proposal_hash,
                mode="sandbox",
                session_digest=b"e" * 32,
            )

            stale_execution_ready = store.create_proposal(
                USER_ONE,
                source_snapshot_id=snapshot_id,
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                scenario_kind="deploy_cash",
                target_instrument_uid="provider-bond-uid",
                replaced_instrument_uid=None,
                proposal_hash=b"z" * 32,
                session_digest=b"s" * 32,
                payload={
                    "schema": "omnicio.portfolio.proposal.v1",
                    "execution_enabled": False,
                    "source": {
                        "snapshot_id": str(snapshot_id),
                        "account_id": "account-1",
                        "profile_version": 1,
                        "policy_version": 2,
                    },
                    "scenario": {
                        "status": "feasible",
                        "trades": [
                            {
                                "action": "buy",
                                "instrument_uid": "provider-bond-uid",
                                "ticker": "BOND",
                                "lots": 1,
                                "limit_price": "101.25",
                                "limit_price_type": "point",
                                "max_spend_rub": "1300",
                                "min_proceeds_rub": None,
                            }
                        ],
                    },
                },
                expires_at=created_at + timedelta(minutes=10),
            )
            stale_execution_proposal, _ = store.decide_proposal(
                USER_ONE,
                proposal_id=stale_execution_ready.id,
                expected_version=stale_execution_ready.version,
                expected_hash=stale_execution_ready.proposal_hash,
                action="confirmed",
                session_digest=b"d" * 32,
                user_reason="",
                deferred_until=None,
                material_current=True,
                now=created_at + timedelta(minutes=4),
            )
            policy_after_confirmation = store.save_balancing_policy(
                USER_ONE,
                max_instrument_percent=Decimal("14"),
                max_sector_percent=Decimal("30"),
                max_issuer_percent=Decimal("20"),
                max_group_percent=Decimal("25"),
                max_share_percent=Decimal("70"),
                max_bond_percent=Decimal("80"),
                max_etf_percent=Decimal("70"),
                max_below_grade_percent=Decimal("5"),
                max_unknown_percent=Decimal("0"),
                max_term_months=120,
                turnover_budget_percent=Decimal("25"),
                max_daily_turnover_participation_percent=Decimal("5"),
                securities_tax_rate_percent=Decimal("15"),
                uncertainty_haircut_percent=Decimal("3"),
                credit_loss_haircut_percent=Decimal("2"),
                no_trade_band_percent=Decimal("1"),
                min_replace_benefit_rub=Decimal("500"),
            )
            with pytest.raises(
                ExecutionLedgerError,
                match="proposal_policy_stale",
            ):
                execution_store.create_run(
                    USER_ONE,
                    proposal_id=stale_execution_proposal.id,
                    expected_version=stale_execution_proposal.version,
                    expected_hash=stale_execution_proposal.proposal_hash,
                    mode="shadow",
                    session_digest=b"e" * 32,
                )

            intelligence = store.latest_intelligence(USER_ONE)
        finally:
            database.close()
        assert first_policy.version == 1
        assert duplicate_policy.id == first_policy.id
        assert duplicate_policy.version == 1
        assert revised_policy.version == 2
        assert current_policy is not None
        assert current_policy.version == 2
        assert current_policy.max_instrument_percent == Decimal("15")
        assert current_policy.max_daily_turnover_participation_percent == Decimal("5")
        assert current_policy.securities_tax_rate_percent == Decimal("15")
        assert current_policy.uncertainty_haircut_percent == Decimal("3")
        assert current_policy.credit_loss_haircut_percent == Decimal("2")
        assert proposal_before[0].id == first_proposal.id
        assert proposal_before[0].status == "pending"
        assert decided_proposal.id == first_proposal.id
        assert confirmed.action == "confirmed"
        assert stale_proposal.id == stale_material.id
        assert stale_action.action == "revoked"
        assert stale_action.reason == "proposal_material_changed"
        superseded = next(
            item
            for item in proposal_after_supersede
            if item.id == pending.id
        )
        assert superseded.status == "superseded"
        assert superseded.decision_reason == "superseded_by_new_proposal"
        assert expired_proposal.id == newest.id
        assert expired_action.action == "expired"
        assert expired_action.deferred_until is None
        assert execution_confirmation.action == "confirmed"
        assert shadow_run.mode == "shadow"
        assert shadow_run.provider_environment is None
        assert shadow_legs[0].request_id == duplicate_legs[0].request_id
        assert duplicate_run.id == shadow_run.id
        assert sandbox_run.id != shadow_run.id
        assert sandbox_run.provider_environment == "sandbox"
        assert sandbox_legs[0].request_id != shadow_legs[0].request_id
        assert policy_after_confirmation.version == 3
        assert intelligence is not None
        assert intelligence["snapshot_freshness"] == "fresh"
        assert [item["instrument_uid"] for item in intelligence["payouts"]] == [
            "provider-bond-uid"
        ]
        assert any(
            item["document_type"] == "bond_coupon"
            and item["freshness_status"] == "fresh"
            for item in intelligence["sources"]
        )

        proposal_id = first_proposal.id
        action_id = confirmed.id
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="immutable proposal",
        ):
            runtime.execute(
                "UPDATE portfolio_proposals SET version = version + 1 WHERE id = %s",
                (proposal_id,),
            )
        with pytest.raises(
            psycopg.errors.RaiseException,
            match="immutable proposal",
        ):
            runtime.execute(
                "DELETE FROM portfolio_proposal_actions WHERE id = %s",
                (action_id,),
            )

        runtime.execute(
            "SELECT set_config('omnicio.user_id', %s, false)",
            (str(USER_TWO),),
        )
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_risk_assessments"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM balancing_policy_versions"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_proposals"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_proposal_actions"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_execution_runs"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_execution_legs"
        ).fetchone()[0] == 0
        assert runtime.execute(
            "SELECT count(*) FROM portfolio_execution_events"
        ).fetchone()[0] == 0

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute(
                """
                INSERT INTO balancing_policy_versions (
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
                    min_replace_benefit_rub
                )
                VALUES (
                    %s, 3, 10, 20, 10, 15, 60, 80, 60, 0, 0, 120,
                    20, 5, 15, 3, 2, 1, 500
                )
                """,
                (USER_ONE,),
            )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute(
                """
                INSERT INTO investment_profile_versions (
                    user_id,
                    version,
                    reserve_rub,
                    planned_withdrawal_rub,
                    horizon_months,
                    max_drawdown_percent,
                    liquidity_horizon_days,
                    allow_below_investment_grade
                )
                VALUES (%s, 2, 100000, 0, 60, 20, 30, false)
                """,
                (USER_ONE,),
            )
