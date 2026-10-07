from __future__ import annotations

import hashlib
import os
import re
import secrets
import subprocess
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from omnicio.db import ActiveLiveExecutionError, Database
from omnicio.execution_store import ExecutionLedgerError, ExecutionLegObservation, ExecutionStore
from omnicio.portfolio_store import PortfolioStore

DATABASE_URL = os.environ.get("OMNICIO_TEST_DATABASE_URL", "")

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = tuple(sorted((ROOT / "migrations").glob("*.sql")))
ACCEPTED_MIGRATION_SHA256 = {
    "0001_phone_auth.sql": ("b92bc06b42cf837cf15d6688edd0ed6b32afabb6ef645b271ca5db6e4a766796"),
    "0002_tbank_connection.sql": (
        "bd48f5bd0ce75abf43606005e40d72869b2881d4c7519af1f2fe9f17fcfe89d8"
    ),
    "0003_vkid_owner_identity.sql": (
        "df8d27cd03820a0ef62dcf2008a12aa0443791161061532a1d0412961e46d710"
    ),
    "0004_user_role.sql": ("fa57fd62d166c31dc9076451a1a4207d2f4fe1be0fc8d4ac8134b0f9a92f6b12"),
    "0005_drop_phone_auth.sql": (
        "0476926a6588b9b3e0e3d80214e059c936568d1d7f2e565a47ec5a388c943a80"
    ),
    "0006_portfolio_observer.sql": (
        "c4b94e1ee1f9f087e60d8eed9f063edd601b4d53ad7b17005d82e4a17e50e256"
    ),
    "0007_portfolio_evidence.sql": (
        "9f2cb4effa5d6293ce4988b0b932241f7470d0eb8f3eeeb5223b8db61ca4b544"
    ),
    "0008_balancing_policy.sql": (
        "f169e65c4cd653da5dc9560acea9244daf2f697ea9da96e04e2a87d340cddda0"
    ),
    "0009_portfolio_proposals.sql": (
        "588c0f098e0341ef9931a9292ed167c9e9f5acd31300d0f83bb27b48ffded46c"
    ),
    "0010_portfolio_execution.sql": (
        "73f2d2d30caf5c4a1bc8364940e36c99991649bd389bdd61abcd81a5b3d687c4"
    ),
    "0011_portfolio_live_execution.sql": (
        "9ce5a36321cb88542b46cca33e6ebe5e1a65f4bf84e0bf00598af262a5550dc8"
    ),
    "0012_strategy_drafts.sql": "eb025bbd52f34398ed4d394b26639ffe82076f9a4b2826f56aa15fdff1df0dd5",
    "0013_strategy_assessment_admission.sql": (
        "66e6fa53c70377be00981278dea31361dbb780c632e3fbb40b92b20056ab6089"
    ),
    "0014_workspace.sql": "f2fd5b344f02b445d7f7abdc119b45c706fc49d83d66f7f01eee88a8992f1305",
    "0015_tid_identity.sql": "6721ea1377018a610f4441dc18956844847e69197983d334c2a002cc8498aff9",
    "0016_portfolio_refresh.sql": (
        "f18abf898992751060f3befff5bc946daa8192ba1c2827ea2671318342eca295"
    ),
    "0017_notifications.sql": (
        "fb6a54daa5ab934a643466bb9ef987c69b4d637ef90a79ceda680c1b79d8b971"
    ),
    "0018_strategy_research.sql": (
        "c0ba3797fc59024584b024f56eb39a4020699e959a3038ee5ac688ac92b6e780"
    ),
    "0019_session_security.sql": (
        "e4c0e3c6d01c810c86a26d5d1a01e7daa965a3e1e193861407de67b8df329dab"
    ),
    "0020_goal_plans.sql": (
        "664e0eaa545cc5c74696605de1772f72c3a3c88d774d9358daafa1a0131bb5d2"
    ),
    "0021_assistant_workspace.sql": (
        "e50b592b4f422c47a9c97b5c450cf407f45895f135b772aa01a1005f55910c06"
    ),
    "0022_billing.sql": (
        "8432fa5fa2776900b29165a23b868213b2388dad16bf1a782d154d76e9b8ba0e"
    ),
    "0023_strategy_execution_guards.sql": (
        "0c4a3f29bc370d424aef7959cbee569f10adc0ad836572d7dc6428071a4e0efb"
    ),
    "0024_background_reliability.sql": (
        "24ab7ef2a42b928d13e445517e6961293272a67b6557b4aa865a8158825867a9"
    ),
    "0025_billing_recovery.sql": (
        "5d6ac08ba7312d09aa85ee895f4d66b8bef7b08c1b8af3ce1d52e0457552d3b1"
    ),
    "0026_strategy_research_capacity.sql": (
        "1cce5a0967c32a6ddd70c48986dd7dcf5074d23a1e8dfe60c7c5abbc72752288"
    ),
}
USER_ONE = UUID("00000000-0000-0000-0000-000000000101")
USER_TWO = UUID("00000000-0000-0000-0000-000000000102")
RUNTIME_PASSWORD = secrets.token_urlsafe(32)


def test_accepted_production_migrations_are_content_immutable() -> None:
    for name, expected_digest in ACCEPTED_MIGRATION_SHA256.items():
        content = (ROOT / "migrations" / name).read_text(encoding="utf-8")
        normalized = content.replace("\r\n", "\n").encode()
        assert hashlib.sha256(normalized).hexdigest() == expected_digest


@pytest.mark.skipif(
    not DATABASE_URL or not os.environ.get("OMNICIO_TEST_POSTGRES_BIN"),
    reason="disposable PostgreSQL client and database are required",
)
def test_native_psql_reports_only_sqlstate_and_stdin_line() -> None:
    binary = Path(os.environ["OMNICIO_TEST_POSTGRES_BIN"])
    executable = binary / ("psql.exe" if os.name == "nt" else "psql")
    result = subprocess.run(
        [
            str(executable),
            "-X",
            "-d",
            DATABASE_URL,
            "-q",
            "-f",
            "-",
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            "VERBOSITY=sqlstate",
            "-v",
            "SHOW_CONTEXT=never",
        ],
        input="-- Input values must not appear in diagnostics.\n"
        "SELECT 'omnicio-private-error-canary'::integer;\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 3
    assert re.fullmatch(r"psql:<stdin>:2: ERROR:\s+22P02", result.stderr.strip())
    assert result.stdout == ""


def _runtime_url() -> str:
    values = conninfo_to_dict(DATABASE_URL)
    values["user"] = "omnicio_runtime_test"
    values["password"] = RUNTIME_PASSWORD
    return make_conninfo(**values)


def _apply_all_migrations() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))


def _seed_legacy_policy(runtime, version: int) -> None:
    """Existing financial settings are fixtures, not a current write API."""
    runtime.execute(
        "INSERT INTO balancing_policy_versions (user_id, version, max_instrument_percent, "
        "max_sector_percent, max_issuer_percent, max_group_percent, max_share_percent, "
        "max_bond_percent, max_etf_percent, max_below_grade_percent, max_unknown_percent, "
        "max_term_months, turnover_budget_percent, max_daily_turnover_participation_percent, "
        "securities_tax_rate_percent, uncertainty_haircut_percent, credit_loss_haircut_percent, "
        "no_trade_band_percent, min_replace_benefit_rub) "
        "VALUES (%s, %s, 20, 30, 20, 25, 70, 80, 70, 5, 0, 120, 25, 5, 15, 3, 2, 1, 500)",
        (USER_ONE, version),
    )


def _seed_legacy_proposal(runtime, snapshot_id: UUID, version: int) -> tuple[UUID, int]:
    """Persist synthetic old history through the actual immutable schema guards."""
    proposal_id = runtime.execute(
        "INSERT INTO portfolio_proposals (user_id, version, source_snapshot_id, account_id, "
        "profile_version, policy_version, scenario_kind, target_instrument_uid, proposal_hash, "
        "created_session_digest, payload, expires_at) "
        "VALUES (%s, %s, %s, 'account-1', 1, 1, 'deploy_cash', 'provider-bond-uid', %s, %s, "
        '\'{"schema":"omnicio.portfolio.proposal.v1","execution_enabled":false}\'::jsonb, '
        "now() + interval '30 minutes') RETURNING id",
        (USER_ONE, version, snapshot_id, b"p" * 32, b"s" * 32),
    ).fetchone()[0]
    action_id = runtime.execute(
        "INSERT INTO portfolio_proposal_actions (proposal_id, user_id, action, proposal_version, "
        "proposal_hash, session_digest) VALUES (%s, %s, 'confirmed', %s, %s, %s) RETURNING id",
        (proposal_id, USER_ONE, version, b"p" * 32, b"d" * 32),
    ).fetchone()[0]
    return proposal_id, action_id


def _seed_legacy_run(
    runtime, proposal_id: UUID, action_id: int, mode: str, mandate_id: UUID | None = None
) -> UUID:
    environment = {"shadow": None, "sandbox": "sandbox", "live": "prod"}[mode]
    return runtime.execute(
        "INSERT INTO portfolio_execution_runs (user_id, proposal_id, confirmed_action_id, "
        "proposal_version, proposal_hash, account_id, mode, provider_environment, "
        "live_mandate_id, created_session_digest) "
        "SELECT user_id, id, %s, version, proposal_hash, account_id, %s, %s, %s, %s "
        "FROM portfolio_proposals WHERE id = %s RETURNING id",
        (action_id, mode, environment, mandate_id, b"e" * 32, proposal_id),
    ).fetchone()[0]


def _seed_legacy_leg(runtime, run_id: UUID, state: str) -> UUID:
    return runtime.execute(
        "INSERT INTO portfolio_execution_legs (run_id, user_id, leg_index, action, "
        "instrument_uid, lots_requested, limit_price, limit_price_type, max_spend_rub, "
        "request_id, status) VALUES (%s, %s, 0, 'buy', 'provider-bond-uid', 2, 101.25, "
        "'point', 2500, gen_random_uuid(), %s) RETURNING id",
        (run_id, USER_ONE, state),
    ).fetchone()[0]


def _assert_legacy_source_guards(runtime, runs: dict[str, UUID], legs: dict[str, UUID]) -> None:
    with pytest.raises(
        psycopg.errors.RaiseException,
        match="execution source fields are immutable",
    ):
        runtime.execute(
            "UPDATE portfolio_execution_runs SET account_id = 'other' WHERE id = %s",
            (runs["live"],),
        )
    with pytest.raises(psycopg.errors.RaiseException, match="execution leg source fields"):
        runtime.execute(
            "UPDATE portfolio_execution_legs SET request_id = gen_random_uuid() WHERE id = %s",
            (legs["live"],),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        runtime.execute(
            "INSERT INTO portfolio_execution_events (run_id, leg_id, user_id, event_type) "
            "VALUES (%s, %s, %s, 'invalid_lineage')",
            (runs["live"], legs["sandbox"], USER_ONE),
        )


def _exercise_legacy_recovery(database: Database, runtime, snapshot_id: UUID) -> tuple[UUID, int]:
    """Read and settle saved records; no runtime creation helper or broker I/O."""
    _seed_legacy_policy(runtime, 1)
    proposal_id, action_id = _seed_legacy_proposal(runtime, snapshot_id, 1)
    mandate_id = runtime.execute(
        "INSERT INTO portfolio_live_execution_mandates (user_id, account_id, "
        "max_order_notional_rub, max_daily_notional_rub, created_session_digest, expires_at) "
        "VALUES (%s, 'account-1', 3000, 5000, %s, now() + interval '30 minutes') RETURNING id",
        (USER_ONE, b"m" * 32),
    ).fetchone()[0]
    runs = {
        mode: _seed_legacy_run(
            runtime, proposal_id, action_id, mode, mandate_id if mode == "live" else None
        )
        for mode in ("shadow", "sandbox", "live")
    }
    legs = {
        mode: _seed_legacy_leg(runtime, run, "submitted" if mode == "sandbox" else "pending")
        for mode, run in runs.items()
    }
    _assert_legacy_source_guards(runtime, runs, legs)
    competing_id, competing_action = _seed_legacy_proposal(runtime, snapshot_id, 2)
    with pytest.raises(psycopg.errors.UniqueViolation, match="one_active_live"):
        _seed_legacy_run(runtime, competing_id, competing_action, "live", mandate_id)
    ledger = ExecutionStore(database)
    assert {run.mode for run in ledger.executions(USER_ONE)} == {"shadow", "sandbox", "live"}
    assert ledger.execution(USER_TWO, runs["live"]) is None
    assert ledger.executions(USER_TWO) == ()
    assert ledger.has_active_live_execution(USER_ONE)
    assert not ledger.has_active_live_execution(USER_TWO)
    with pytest.raises(ActiveLiveExecutionError):
        database.upsert_tbank_connection(
            user_id=USER_ONE,
            environment="prod",
            account_id="account-1",
            account_name="Synthetic",
            encrypted_credential=b"replacement",
            terms_version="test",
        )
    with pytest.raises(ActiveLiveExecutionError):
        database.delete_tbank_connection(USER_ONE)
    _settle_legacy_records(ledger, runs, legs, mandate_id)
    _seed_legacy_policy(runtime, 2)
    with pytest.raises(psycopg.errors.RaiseException, match="not an exact confirmed proposal"):
        _seed_legacy_run(runtime, competing_id, competing_action, "shadow")
    return proposal_id, action_id


def _settle_legacy_records(
    ledger: ExecutionStore, runs: dict[str, UUID], legs: dict[str, UUID], mandate_id: UUID
) -> None:
    revoked = ledger.revoke_live_mandate(USER_ONE)
    assert revoked is not None
    assert revoked.id == mandate_id
    assert ledger.live_mandate(USER_ONE) is None
    assert ledger.has_active_live_execution(USER_ONE)
    with pytest.raises(ExecutionLedgerError, match="live_mandate_inactive"):
        ledger.transition_leg(
            USER_ONE,
            run_id=runs["live"],
            leg_id=legs["live"],
            expected_statuses=("pending",),
            new_status="submitting",
            event_type="forbidden_new_submission",
            details={},
        )
    run, leg = ledger.transition_leg(
        USER_ONE,
        run_id=runs["live"],
        leg_id=legs["live"],
        expected_statuses=("pending",),
        new_status="cancelled",
        event_type="cancelled_before_submission",
        details={},
    )
    assert run.status == "cancelled"
    assert leg.status == "cancelled"
    assert not ledger.has_active_live_execution(USER_ONE)
    pending, _ = ledger.mark_run_reconciling(
        USER_ONE,
        run_id=runs["sandbox"],
        leg_id=legs["sandbox"],
        error_code="provider_read_unavailable",
        details={"retry_post_order": False},
    )
    assert pending.status == "reconciling"
    run, leg = ledger.transition_leg(
        USER_ONE,
        run_id=runs["sandbox"],
        leg_id=legs["sandbox"],
        expected_statuses=("reconciling",),
        new_status="filled",
        event_type="provider_state_reconciled",
        details={},
        observation=ExecutionLegObservation(
            lots_executed=2,
            executed_amount_rub=Decimal("2000"),
            executed_commission_rub=Decimal("3"),
        ),
    )
    assert run.status == "succeeded"
    assert leg.status == "filled"
    assert leg.executed_amount_rub == Decimal("2000")
    assert leg.executed_commission_rub == Decimal("3")
    saved = ledger.execution(USER_ONE, runs["sandbox"])
    assert saved is not None
    assert [event.event_type for event in saved[2]] == [
        "provider_read_unavailable",
        "provider_state_reconciled",
    ]


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
    migration = (ROOT / "migrations" / "0011_portfolio_live_execution.sql").read_text(
        encoding="utf-8"
    )

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
    execution_store_source = (ROOT / "src" / "omnicio" / "execution_store.py").read_text(
        encoding="utf-8"
    )
    assert "def _require_live_transition_mandate(" in execution_store_source
    assert 'run.mode != "live" or new_status != "submitting"' in execution_store_source
    assert 'raise ExecutionLedgerError("live_mandate_inactive")' in execution_store_source
    assert "FOR SHARE" in execution_store_source
    database_source = (ROOT / "src" / "omnicio" / "db.py").read_text(encoding="utf-8")
    assert "class ActiveLiveExecutionError" in database_source
    assert database_source.count("live_execution_lock_key(user_id)") >= 2


@pytest.mark.skipif(
    not DATABASE_URL,
    reason="ephemeral PostgreSQL is required for migration integration coverage",
)
def test_migrations_apply_reapply_and_enforce_observer_rls() -> None:
    assert [item.name for item in MIGRATIONS][-1] == "0027_assistant_stream_memory.sql"
    _apply_all_migrations()

    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        # The additive latest migration is safe to retry before release. Once
        # accepted on main it becomes immutable migration history.
        admin.execute(
            (ROOT / "migrations" / "0011_portfolio_live_execution.sql").read_text(encoding="utf-8")
        )

        admin.execute(
            (ROOT / "migrations" / "0012_strategy_drafts.sql").read_text(encoding="utf-8")
        )

        admin.execute(
            (ROOT / "migrations" / "0013_strategy_assessment_admission.sql").read_text(
                encoding="utf-8"
            )
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
            "strategy_drafts",
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
                          'strategy_drafts'
                      ]
                  )
                """
            ).fetchall()
        }
        assert len(protected) == 16
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
            INSERT INTO tbank_connection (user_id, account_id, environment, token_ciphertext)
            VALUES (%s, 'account-1', 'prod', %s), (%s, 'account-1', 'prod', %s)
            """,
            (USER_ONE, b"synthetic-one", USER_TWO, b"synthetic-two"),
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
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO omnicio_runtime_test"
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
        assert (
            runtime.execute("SELECT count(*) FROM investment_profile_versions").fetchone()[0] == 0
        )
        assert runtime.execute("SELECT count(*) FROM account_instrument_access").fetchone()[0] == 0

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
                item["instrument_uid"] == "provider-bond-uid" and item["event_type"] == "coupon"
                for item in instrument_visualization["payouts"]
            )
            assert any(
                item["subject_uid"] == "provider-bond-uid"
                and item["document_type"] == "bond_coupon"
                for item in instrument_visualization["sources"]
            )
            assert (
                store.instrument_visualization(
                    USER_TWO,
                    "FIGI-ONLY",
                    history_limit=30,
                )
                is None
            )

            proposal_id, action_id = _exercise_legacy_recovery(database, runtime, snapshot_id)
            current_policy = store.current_balancing_policy(USER_ONE)
            assert current_policy is not None
            assert current_policy.version == 2
            assert current_policy.max_instrument_percent == Decimal("20")
            proposal_history = store.proposals(USER_ONE)
            assert len(proposal_history) == 2
            assert all(item.status == "confirmed" for item in proposal_history)
            assert store.proposals(USER_TWO) == ()

            # The user-facing journal filters both owner and event type, and
            # never serializes audit metadata (which is for server use only).
            with psycopg.connect(DATABASE_URL, autocommit=True) as audit_admin:
                audit_admin.execute(
                    "INSERT INTO audit_events (user_id, event_type, metadata) "
                    "VALUES (%s, 'login_succeeded', %s::jsonb), "
                    "(%s, 'internal_test_event', '{}'::jsonb)",
                    (USER_TWO, '{"private_marker": "not-for-the-journal"}', USER_ONE),
                )
            own_activity = database.recent_activity(USER_ONE)
            other_activity = database.recent_activity(USER_TWO)
            assert own_activity == []
            assert [item["event_type"] for item in other_activity] == ["login_succeeded"]
            assert all(set(item) == {"event_type", "created_at"} for item in other_activity)
            assert len(database.recent_activity(USER_TWO, limit=1)) == 1
        finally:
            database.close()
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
        assert runtime.execute("SELECT count(*) FROM portfolio_risk_assessments").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM balancing_policy_versions").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_proposals").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_proposal_actions").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_runs").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_legs").fetchone()[0] == 0
        assert runtime.execute("SELECT count(*) FROM portfolio_execution_events").fetchone()[0] == 0

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
        assert (
            admin.execute(
                "SELECT count(*) FROM users WHERE id = %s",
                (USER_ONE,),
            ).fetchone()[0]
            == 0
        )
        for table in (
            "portfolio_proposals",
            "portfolio_proposal_actions",
            "portfolio_execution_runs",
            "portfolio_execution_legs",
            "portfolio_execution_events",
        ):
            assert (
                admin.execute(
                    sql.SQL("SELECT count(*) FROM {} WHERE user_id = %s").format(
                        sql.Identifier(table)
                    ),
                    (USER_ONE,),
                ).fetchone()[0]
                == 0
            )
