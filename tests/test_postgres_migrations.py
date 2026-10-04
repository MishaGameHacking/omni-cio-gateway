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
from omnicio.portfolio_store import BalancingPolicyInput, PortfolioStore, ProposalStateError

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(sorted((ROOT / "migrations").glob("*.sql")))
USER_ONE = UUID("00000000-0000-0000-0000-000000000101")
USER_TWO = UUID("00000000-0000-0000-0000-000000000102")
RUNTIME_PASSWORD = secrets.token_urlsafe(32)


def _balancing_policy_input(
    max_instrument_percent: str = "20",
) -> BalancingPolicyInput:
    return BalancingPolicyInput(
        max_instrument_percent=Decimal(max_instrument_percent),
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


def _runtime_url() -> str:
    values = conninfo_to_dict(DATABASE_URL)
    values["user"] = "omnicio_runtime_test"
    values["password"] = RUNTIME_PASSWORD
    return make_conninfo(**values)


def _apply_all_migrations() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))


def test_r6_execution_migration_has_valid_guards_and_event_lineage() -> None:
    migration = (ROOT / "migrations" / "0010_portfolio_execution.sql").read_text(encoding="utf-8")

    assert "omnicio_validate_execution_run_source" in migration
    assert "AS $omnicio$" in migration
    assert "execution leg source fields are immutable" in migration
    assert "portfolio_execution_legs_source_guard" in migration
    assert "UNIQUE (id, run_id, user_id)" in migration
    assert "FOREIGN KEY (leg_id, run_id, user_id)" in migration
    assert "REFERENCES portfolio_execution_legs(id, run_id, user_id)" in migration
    assert "TG_OP = 'INSERT' AND NOT EXISTS" in migration
    assert "p.expires_at > now()" in migration
    assert "p.source_snapshot_id, p.account_id" in migration
    assert "omnicio.financial_cleanup" in migration
    assert "'account_delete'" in migration
    assert "'broker_disconnect'" in migration
    assert "portfolio_proposals_source_snapshot_tenant_fkey" in migration
    assert "AS $omnicio_cleanup$" in migration
    assert "\nAS $\n" not in migration
    database_source = (ROOT / "src" / "omnicio" / "db.py").read_text(encoding="utf-8")
    assert "set_config('omnicio.financial_cleanup', 'account_delete', true)" in database_source
    assert "set_config('omnicio.financial_cleanup', 'broker_disconnect', true)" in database_source


def test_r7_live_execution_migration_requires_exact_mandate_and_fail_closed_mode() -> None:
    migration = (
        ROOT / "migrations" / "0011_portfolio_live_execution.sql"
    ).read_text(encoding="utf-8")

    assert "portfolio_live_execution_mandates" in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "live_mandate_id" in migration
    assert "mode IN ('shadow', 'sandbox', 'live')" in migration
    assert "mode = 'live'" in migration
    assert "provider_environment = 'prod'" in migration
    assert "live execution requires an active exact-account mandate" in migration
    assert "portfolio_execution_runs_one_active_live_idx" in migration
    assert "portfolio_live_execution_mandates_active_idx" in migration
    assert "portfolio_live_execution_mandates_expiry_window" in migration
    assert "expires_at <= created_at + interval '24 hours'" in migration
    assert "omnicio_validate_live_submission_authority" in migration
    assert "portfolio_execution_legs_live_submission_guard" in migration
    assert "FOR SHARE OF m" in migration
    assert "live execution mandate is inactive before submission" in migration
    execution_store_source = (
        ROOT / "src" / "omnicio" / "execution_store.py"
    ).read_text(encoding="utf-8")
    assert 'run.mode == "live" and new_status == "submitting"' in execution_store_source
    assert 'raise ExecutionLedgerError("live_mandate_inactive")' in execution_store_source
    assert "portfolio_execution_runs_one_active_live_idx" in execution_store_source
    assert "live_execution_already_active" in execution_store_source
    assert "live_execution_lock_key(user_id)" in execution_store_source
    assert "FOR SHARE" in execution_store_source
    database_source = (
        ROOT / "src" / "omnicio" / "db.py"
    ).read_text(encoding="utf-8")
    assert "class ActiveLiveExecutionError" in database_source
    assert database_source.count("live_execution_lock_key(user_id)") >= 2


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="ephemeral PostgreSQL is required for migration integration coverage",
)
def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-1] == "0011_portfolio_live_execution.sql"
    _apply_all_migrations()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive latest migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute(
            (
                ROOT / "migrations" / "0011_portfolio_live_execution.sql"
            ).read_text(encoding="utf-8")
        )

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
            "portfolio_live_execution_mandates",
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
                          'portfolio_execution_events',
                          'portfolio_live_execution_mandates'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 15
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

            visualization = store.portfolio_visualization(
                USER_ONE,
                history_limit=30,
            )
            assert visualization["status"] == "observed"
            latest_visualization = visualization["latest"]
            assert isinstance(latest_visualization, dict)
            assert latest_visualization["account_id"] == "account-1"
            assert latest_visualization["environment"] == "prod"
            assert latest_visualization["nav_rub"] == Decimal("1000")
            assert len(visualization["history"]) == 1
            positions = latest_visualization["positions"]
            assert isinstance(positions, list)
            assert any(
                item["instrument_uid"] == "FIGI-ONLY"
                and item["catalog_instrument_uid"] == "provider-bond-uid"
                for item in positions
            )

            other_tenant_visualization = store.portfolio_visualization(
                USER_TWO,
                history_limit=30,
            )
            assert other_tenant_visualization == {
                "status": "pending",
                "history": [],
                "latest": None,
            }

            instrument_visualization = store.instrument_visualization(
                USER_ONE,
                "FIGI-ONLY",
                history_limit=30,
            )
            assert instrument_visualization is not None
            assert instrument_visualization["account_id"] == "account-1"
            assert len(instrument_visualization["history"]) == 1
            assert instrument_visualization["latest"]["ticker"] == "TESTBOND"
            assert any(
                item["instrument_uid"] == "provider-bond-uid"
                and item["event_type"] == "coupon"
                for item in instrument_visualization["payouts"]
            )
            assert any(
                item["subject_uid"] == "provider-bond-uid"
                and item["document_type"] == "bond_coupon"
                for item in instrument_visualization["sources"]
            )
            assert store.instrument_visualization(
                USER_TWO,
                "FIGI-ONLY",
                history_limit=30,
            ) is None

            first_policy = store.save_balancing_policy(
            first_policy =     USER_ONE,
            first_policy =     _balancing_policy_input("20"),
            first_policy = )