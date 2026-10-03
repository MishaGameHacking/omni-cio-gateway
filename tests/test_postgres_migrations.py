from __future__ import annotations

from dataclasses import replace
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
from omnicio.portfolio_store import (
    PortfolioStore,
    ProposalStateError,
    ReinvestmentMandateError,
    ReinvestmentMandateSpec,
)

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")

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


def test_r8_reinvestment_migration_is_fail_closed_and_evidence_only() -> None:
    migration = (
        ROOT / "migrations" / "0012_portfolio_reinvestment.sql"
    ).read_text(encoding="utf-8")
    store = (ROOT / "src" / "omnicio" / "portfolio_store.py").read_text(
        encoding="utf-8"
    )
    observer = (ROOT / "src" / "omnicio" / "observer.py").read_text(
        encoding="utf-8"
    )

    for table in (
        "portfolio_reinvestment_mandates",
        "portfolio_reinvestment_income_credits",
    ):
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in migration
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in migration
    assert "portfolio_reinvestment_mandates_active_idx" in migration
    assert "source_operation_observation_id" in migration
    assert "OPERATION_TYPE_DIVIDEND" in migration
    assert "OPERATION_TYPE_COUPON" in migration
    assert "OPERATION_STATE_EXECUTED" in migration
    assert "provider_executed_unverified" in migration
    assert "reinvestment income credit source is not eligible" in migration
    assert "o.operation_date >= m.created_at" in migration
    assert "m.revoked_at IS NULL" in migration
    assert "portfolio-reinvestment-mandate:" in store
    assert "sync_reinvestment_income_credits" in store
    assert "history_result[2] == \"complete\"" in observer
    assert "PostOrder" not in migration
    assert "PostOrder" not in store


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="ephemeral PostgreSQL is required for migration integration coverage",
)
def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-1] == "0012_portfolio_reinvestment.sql"
    _apply_all_migrations()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive latest migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute(
            (
                ROOT / "migrations" / "0012_portfolio_reinvestment.sql"
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
            "portfolio_reinvestment_mandates",
            "portfolio_reinvestment_income_credits",
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
                          'portfolio_live_execution_mandates',
                          'portfolio_reinvestment_mandates',
                          'portfolio_reinvestment_income_credits'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 17
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

        with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
            admin.execute(
                """
                INSERT INTO tbank_connection (
                    user_id,
                    environment,
                    account_id,
                    account_name,
                    token_ciphertext
                )
                VALUES (%s, 'prod', 'account-1', 'R8 test account', %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    environment = EXCLUDED.environment,
                    account_id = EXCLUDED.account_id,
                    account_name = EXCLUDED.account_name,
                    token_ciphertext = EXCLUDED.token_ciphertext
                """,
                (USER_ONE, b"r8-test-ciphertext"),
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

            reinvestment_spec = ReinvestmentMandateSpec(
                account_id="account-1",
                profile_version=1,
                policy_version=2,
                allow_dividends=True,
                allow_coupons=True,
                cash_reserve_rub=Decimal("1000.00"),
                max_order_notional_rub=Decimal("100.00"),
                max_daily_notional_rub=Decimal("500.00"),
                max_monthly_notional_rub=Decimal("2000.00"),
                max_slippage_bps=50,
                expires_at=created_at + timedelta(days=30),
            )
            with pytest.raises(
                ReinvestmentMandateError,
                match="reinvestment_account_changed",
            ):
                store.create_reinvestment_mandate(
                    USER_ONE,
                    spec=replace(
                        reinvestment_spec,
                        account_id="stale-account",
                    ),
                    session_digest=b"i" * 32,
                    now=created_at,
                )
            reinvestment = store.create_reinvestment_mandate(
                USER_ONE,
                spec=reinvestment_spec,
                session_digest=b"i" * 32,
                now=created_at,
            )

            def insert_r8_operation(
                *,
                marker_byte: int,
                operation_date: datetime,
                operation_type: str,
                operation_state: str,
                payment_value: Decimal,
                payment_currency: str,
            ) -> int:
                return int(
                    runtime.execute(
                        """
                        INSERT INTO operation_observations (
                            user_id,
                            account_id,
                            observation_hash,
                            semantic_hash,
                            provider_operation_id,
                            operation_date,
                            operation_type,
                            operation_state,
                            payment_value,
                            payment_currency,
                            normalized,
                            observed_at
                        )
                        VALUES (
                            %s,
                            'account-1',
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            '{}'::jsonb,
                            %s
                        )
                        RETURNING id
                        """,
                        (
                            USER_ONE,
                            bytes([marker_byte]) * 32,
                            bytes([marker_byte + 64]) * 32,
                            f"r8-{marker_byte}",
                            operation_date,
                            operation_type,
                            operation_state,
                            payment_value,
                            payment_currency,
                            operation_date + timedelta(seconds=1),
                        ),
                    ).fetchone()[0]
                )

            insert_r8_operation(
                marker_byte=1,
                operation_date=created_at - timedelta(minutes=1),
                operation_type="OPERATION_TYPE_DIVIDEND",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("9.00"),
                payment_currency="RUB",
            )
            dividend_observation_id = insert_r8_operation(
                marker_byte=2,
                operation_date=created_at + timedelta(minutes=1),
                operation_type="OPERATION_TYPE_DIVIDEND",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("50.00"),
                payment_currency="RUB",
            )
            insert_r8_operation(
                marker_byte=3,
                operation_date=created_at + timedelta(minutes=2),
                operation_type="OPERATION_TYPE_COUPON",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("25.50"),
                payment_currency="RUB",
            )
            insert_r8_operation(
                marker_byte=4,
                operation_date=created_at + timedelta(minutes=3),
                operation_type="OPERATION_TYPE_INPUT",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("1000.00"),
                payment_currency="RUB",
            )
            insert_r8_operation(
                marker_byte=5,
                operation_date=created_at + timedelta(minutes=4),
                operation_type="OPERATION_TYPE_DIVIDEND",
                operation_state="OPERATION_STATE_PROGRESS",
                payment_value=Decimal("10.00"),
                payment_currency="RUB",
            )
            insert_r8_operation(
                marker_byte=6,
                operation_date=created_at + timedelta(minutes=5),
                operation_type="OPERATION_TYPE_COUPON",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("5.00"),
                payment_currency="USD",
            )
            insert_r8_operation(
                marker_byte=7,
                operation_date=created_at + timedelta(minutes=6),
                operation_type="OPERATION_TYPE_DIVIDEND",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("-1.00"),
                payment_currency="RUB",
            )

            assert store.sync_reinvestment_income_credits(
                USER_ONE,
                account_id="account-1",
                observed_at=created_at + timedelta(minutes=10),
            ) == 2
            assert store.sync_reinvestment_income_credits(
                USER_ONE,
                account_id="account-1",
                observed_at=created_at + timedelta(minutes=10),
            ) == 0
            reinvestment_summary = store.reinvestment_income_summary(
                USER_ONE,
                reinvestment.id,
            )
            assert reinvestment_summary.observed_count == 2
            assert reinvestment_summary.observed_rub == Decimal("75.500000000")
            assert reinvestment_summary.dividends_rub == Decimal("50.000000000")
            assert reinvestment_summary.coupons_rub == Decimal("25.500000000")
            assert reinvestment_summary.verified_rub == Decimal("0")

            with pytest.raises(
                psycopg.errors.RaiseException,
                match="reinvestment income credits are immutable",
            ):
                runtime.execute(
                    """
                    UPDATE portfolio_reinvestment_income_credits
                    SET amount_rub = 999
                    WHERE source_operation_observation_id = %s
                    """,
                    (dividend_observation_id,),
                )

            runtime.execute(
                "SELECT set_config('omnicio.user_id', %s, false)",
                (str(USER_TWO),),
            )
            assert runtime.execute(
                "SELECT count(*) FROM portfolio_reinvestment_mandates"
            ).fetchone()[0] == 0
            assert runtime.execute(
                "SELECT count(*) FROM portfolio_reinvestment_income_credits"
            ).fetchone()[0] == 0
            runtime.execute(
                "SELECT set_config('omnicio.user_id', %s, false)",
                (str(USER_ONE),),
            )

            revoked_reinvestment = store.revoke_reinvestment_mandate(
                USER_ONE,
                now=created_at + timedelta(hours=1),
            )
            assert revoked_reinvestment is not None
            assert revoked_reinvestment.revoked_at is not None
            insert_r8_operation(
                marker_byte=8,
                operation_date=created_at + timedelta(hours=2),
                operation_type="OPERATION_TYPE_DIVIDEND",
                operation_state="OPERATION_STATE_EXECUTED",
                payment_value=Decimal("100.00"),
                payment_currency="RUB",
            )
            assert store.sync_reinvestment_income_credits(
                USER_ONE,
                account_id="account-1",
                observed_at=created_at + timedelta(hours=3),
            ) == 0

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
            invalid_mandate_expiry = created_at + timedelta(minutes=30)
            invalid_mandate_now = created_at + timedelta(minutes=5)
            invalid_order_cap = Decimal("3000.001")
            invalid_daily_cap = Decimal("5000")
            with pytest.raises(ValueError, match="kopeck precision"):
                execution_store.create_live_mandate(
                    USER_ONE,
                    account_id="account-1",
                    max_order_notional_rub=invalid_order_cap,
                    max_daily_notional_rub=invalid_daily_cap,
                    session_digest=b"l" * 32,
                    expires_at=invalid_mandate_expiry,
                    now=invalid_mandate_now,
                )
            live_mandate = execution_store.create_live_mandate(
                USER_ONE,
                account_id="account-1",
                max_order_notional_rub=Decimal("3000"),
                max_daily_notional_rub=Decimal("5000"),
                session_digest=b"l" * 32,
                expires_at=created_at + timedelta(minutes=30),
                now=created_at + timedelta(minutes=5),
            )
            live_run, live_legs = execution_store.create_run(
                USER_ONE,
                proposal_id=execution_proposal.id,
                expected_version=execution_proposal.version,
                expected_hash=execution_proposal.proposal_hash,
                mode="live",
                session_digest=b"e" * 32,
            )
            competing_live_proposal = store.create_proposal(
                USER_ONE,
                source_snapshot_id=execution_proposal.source_snapshot_id,
                account_id=execution_proposal.account_id,
                profile_version=execution_proposal.profile_version,
                policy_version=execution_proposal.policy_version,
                scenario_kind=execution_proposal.scenario_kind,
                target_instrument_uid=execution_proposal.target_instrument_uid,
                replaced_instrument_uid=execution_proposal.replaced_instrument_uid,
                proposal_hash=b"w" * 32,
                session_digest=b"w" * 32,
                payload=execution_proposal.payload,
                expires_at=created_at + timedelta(minutes=12),
            )
            competing_live_proposal, _ = store.decide_proposal(
                USER_ONE,
                proposal_id=competing_live_proposal.id,
                expected_version=competing_live_proposal.version,
                expected_hash=competing_live_proposal.proposal_hash,
                action="confirmed",
                session_digest=b"w" * 32,
                user_reason="",
                deferred_until=None,
                material_current=True,
                now=created_at + timedelta(minutes=5, seconds=30),
            )
            with pytest.raises(
                ExecutionLedgerError,
                match="live_execution_already_active",
            ):
                execution_store.create_run(
                    USER_ONE,
                    proposal_id=competing_live_proposal.id,
                    expected_version=competing_live_proposal.version,
                    expected_hash=competing_live_proposal.proposal_hash,
                    mode="live",
                    session_digest=b"w" * 32,
                )
            revoked_mandate = execution_store.revoke_live_mandate(
                USER_ONE,
                now=created_at + timedelta(minutes=6),
            )
            live_run_id = live_run.id
            live_leg_id = live_legs[0].id
            live_submit_details = {"request_id": str(live_legs[0].request_id)}
            live_submit_now = created_at + timedelta(minutes=6)
            with pytest.raises(ExecutionLedgerError, match="live_mandate_inactive"):
                execution_store.transition_leg(
                    USER_ONE,
                    run_id=live_run_id,
                    leg_id=live_leg_id,
                    expected_statuses=("pending",),
                    new_status="submitting",
                    event_type="live_preflight_passed",
                    details=live_submit_details,
                    now=live_submit_now,
                )
            cancelled_live_run, cancelled_live_leg = execution_store.transition_leg(
                USER_ONE,
                run_id=live_run.id,
                leg_id=live_legs[0].id,
                expected_statuses=("pending",),
                new_status="cancelled",
                event_type="cancelled_before_submission",
                details={"reason": "kill_switch_regression"},
                now=created_at + timedelta(minutes=7),
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
        assert live_run.mode == "live"
        assert live_run.provider_environment == "prod"
        assert live_run.live_mandate_id == live_mandate.id
        assert revoked_mandate is not None
        assert revoked_mandate.id == live_mandate.id
        assert revoked_mandate.revoked_at is not None
        assert cancelled_live_run.status == "cancelled"
        assert cancelled_live_leg.status == "cancelled"
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


    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(
            """
            INSERT INTO vkid_identities (user_id, vk_user_id, verified_at)
            VALUES (%s, 'r6-delete-regression', now())
            """,
            (USER_ONE,),
        )

    database = Database(DATABASE_URL)
    database.open()
    try:
        assert database.delete_user_account(USER_ONE) is True
    finally:
        database.close()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        assert admin.execute(
            "SELECT count(*) FROM users WHERE id = %s",
            (USER_ONE,),
        ).fetchone()[0] == 0
        for table in (
            "portfolio_proposals",
            "portfolio_proposal_actions",
            "portfolio_execution_runs",
            "portfolio_execution_legs",
            "portfolio_execution_events",
        ):
            assert admin.execute(
                sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                    sql.Identifier(table)
                ),
                (USER_ONE,),
            ).fetchone()[0] == 0
