from __future__ import annotations

import os
import secrets
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import Database
from omnicio.portfolio_store import PortfolioStore

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


def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-1] == "0008_balancing_policy.sql"
    _apply_all_migrations()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive R4 migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute((ROOT / "migrations" / "0008_balancing_policy.sql").read_text())

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
                          'balancing_policy_versions'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 9
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
                no_trade_band_percent=Decimal("1"),
                min_replace_benefit_rub=Decimal("500"),
            )
            current_policy = store.current_balancing_policy(USER_ONE)
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
                    no_trade_band_percent,
                    min_replace_benefit_rub
                )
                VALUES (
                    %s, 3, 10, 20, 10, 15, 60, 80, 60, 0, 0, 120, 20, 1, 500
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
