"""Canonical PostgreSQL readiness shared by runtime and deployment gate. No dependencies."""

READINESS_QUERY = """
SELECT
    to_regclass('public.users') IS NOT NULL
    AND to_regclass('public.sessions') IS NOT NULL
    AND to_regclass('public.legal_acceptances') IS NOT NULL
    AND to_regclass('public.vkid_identities') IS NOT NULL
    AND to_regclass('public.tid_identities') IS NOT NULL
    AND to_regclass('public.oauth_flow_claims') IS NOT NULL
    AND to_regclass('public.workspace_preferences') IS NOT NULL
    AND to_regclass('public.investment_goals') IS NOT NULL
    AND to_regclass('public.workspace_events') IS NOT NULL
    AND to_regclass('public.notification_channels') IS NOT NULL
    AND to_regclass('public.notification_outbox') IS NOT NULL
    AND to_regclass('public.notification_outbox_events') IS NOT NULL
    AND to_regclass('public.notification_outbox_events_message_idx') IS NOT NULL
    AND (
        SELECT count(*) = 5 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_outbox_events'
          AND column_name IN ('user_id', 'channel_id', 'event_id', 'event_revision', 'outbox_id')
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.notification_outbox') AND contype = 'u'
          AND convalidated AND conname = 'notification_outbox_owner_channel_id_key'
    )
    AND to_regclass('public.strategy_research_evidence') IS NOT NULL
    AND to_regclass('public.strategy_research_runs') IS NOT NULL
    AND to_regclass('public.strategy_research_requests') IS NOT NULL
    AND (
        SELECT count(*) = 9 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'strategy_research_requests'
          AND column_name IN ('user_id', 'id', 'input_hash', 'status', 'run_id', 'error_code',
                               'created_at', 'updated_at', 'expires_at')
    )
    AND to_regclass('public.goal_plans') IS NOT NULL
    AND to_regclass('public.assistant_memory') IS NOT NULL
    AND to_regclass('public.assistant_memory_recent') IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.assistant_messages') AND contype = 'c'
          AND convalidated AND conname = 'assistant_messages_source_refs_size'
    )
    AND (
        SELECT count(*) = 8 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'assistant_memory'
          AND column_name IN ('user_id', 'id', 'version', 'content', 'category', 'origin',
                              'created_at', 'updated_at')
    )
    AND (
        SELECT count(*) = 4 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'assistant_requests'
          AND column_name IN ('reply_prefix', 'stream_sequence', 'source_refs', 'updated_at')
          AND is_nullable = 'NO'
    )
    AND (
        SELECT count(*) = 5 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'billing_payments'
          AND column_name IN ('cancel_attempted_at', 'init_started_at', 'checkout_expires_at',
                              'absence_checked_at', 'resolution')
    )
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'billing_payments'
          AND column_name = 'checkout_expires_at' AND is_nullable = 'NO'
    )
    AND (
        SELECT count(*) = 2 FROM pg_constraint
        WHERE conrelid = to_regclass('public.billing_payments') AND contype = 'c'
          AND convalidated AND conname IN ('billing_payments_resolution_known',
                                           'billing_payments_checkout_expiry_valid')
    )
    AND (
        SELECT count(*) = 2 FROM pg_constraint
        WHERE conrelid = to_regclass('public.strategy_research_runs') AND contype = 'c'
          AND convalidated AND conname IN ('strategy_research_runs_result_size',
                                           'strategy_research_runs_inputs_size')
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.strategy_research_evidence') AND contype = 'c'
          AND convalidated AND conname = 'strategy_research_evidence_size'
    )
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_channels'
          AND column_name = 'digest_cursor_at'
    )
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_outbox'
          AND column_name = 'updated_at' AND is_nullable = 'NO'
    )
    AND (
        SELECT count(*) = 5 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'worker_heartbeats'
          AND column_name IN ('worker_name', 'checked_at', 'completed_at', 'status',
                               'completed_status')
    )
    AND (
        SELECT count(*) = 2 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'sessions'
          AND column_name IN ('authenticated_provider', 'authenticated_at')
    )
    AND (
        SELECT count(*) = 2 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'workspace_events'
          AND column_name IN ('revision', 'updated_at')
    )
    AND to_regclass('public.tbank_connection') IS NOT NULL
    AND to_regclass('public.instrument_catalog') IS NOT NULL
    AND to_regclass('public.account_instrument_access') IS NOT NULL
    AND to_regclass('public.issuer_groups') IS NOT NULL
    AND to_regclass('public.issuers') IS NOT NULL
    AND to_regclass('public.instrument_issuer_map') IS NOT NULL
    AND to_regclass('public.investment_profile_versions') IS NOT NULL
    AND to_regclass('public.job_runs') IS NOT NULL
    AND to_regclass('public.job_runs_daily_retry_attempt_idx') IS NOT NULL
    AND to_regclass('public.job_runs_daily_pending_idx') IS NOT NULL
    AND (
        SELECT count(*) = 2 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'job_runs'
          AND column_name IN ('retry_of', 'next_attempt_at')
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.job_runs')
          AND conname = 'job_runs_retry_owner_fkey' AND contype = 'f' AND convalidated
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.job_runs')
          AND conname = 'job_runs_user_id_job_type_scheduled_for_key'
          AND contype = 'u'
    )
    AND to_regclass('public.job_runs_refresh_active_idx') IS NOT NULL
    AND to_regclass('public.job_runs_refresh_requested_idx') IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'job_runs'
          AND column_name = 'requested_at' AND is_nullable = 'NO'
    )
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'job_runs'
          AND column_name = 'scheduled_for' AND is_nullable = 'YES'
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.job_runs')
          AND conname = 'job_runs_schedule_kind_consistent'
          AND contype = 'c' AND convalidated
    )
    AND to_regclass('public.portfolio_snapshots') IS NOT NULL
    AND to_regclass('public.portfolio_snapshot_positions') IS NOT NULL
    AND to_regclass('public.operation_observations') IS NOT NULL
    AND to_regclass('public.broker_sync_state') IS NOT NULL
    AND to_regclass('public.source_documents') IS NOT NULL
    AND to_regclass('public.source_retrievals') IS NOT NULL
    AND to_regclass('public.source_facts') IS NOT NULL
    AND to_regclass('public.payout_events') IS NOT NULL
    AND to_regclass('public.portfolio_risk_assessments') IS NOT NULL
    AND to_regclass('public.balancing_policy_versions') IS NOT NULL
    AND to_regclass('public.strategy_drafts') IS NOT NULL
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'strategy_drafts'
          AND column_name = 'next_assessment_at'
    )
    AND to_regclass('public.portfolio_proposals') IS NOT NULL
    AND to_regclass('public.portfolio_proposal_actions') IS NOT NULL
    AND to_regclass('public.portfolio_execution_runs') IS NOT NULL
    AND to_regclass('public.portfolio_execution_legs') IS NOT NULL
    AND to_regclass('public.portfolio_execution_events') IS NOT NULL
    AND to_regclass('public.portfolio_live_execution_mandates') IS NOT NULL
    AND to_regprocedure(
        'public.omnicio_current_strategy_execution_authority(uuid,bytea,jsonb)'
    ) IS NOT NULL
    AND (
        SELECT count(*) = 3 FROM pg_trigger
        WHERE NOT tgisinternal AND tgenabled IN ('O', 'A')
          AND tgfoid = to_regprocedure('public.omnicio_guard_new_strategy_execution()')
          AND (tgrelid, tgname) IN (
              (to_regclass('public.portfolio_proposals'), 'strategy_proposal_authority'),
              (to_regclass('public.portfolio_execution_runs'), 'strategy_run_authority'),
              (to_regclass('public.portfolio_execution_legs'), 'strategy_submission_authority')
          )
    )
    AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'users'
          AND column_name = 'role'
    )
    AND (
        SELECT count(*) = 8
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'instrument_catalog'
          AND column_name = ANY (
              ARRAY[
                  'nominal_value',
                  'nominal_currency',
                  'maturity_date',
                  'floating_coupon',
                  'perpetual',
                  'amortization',
                  'subordinated',
                  'liquidity'
              ]
          )
    )
    AND (
        SELECT count(*) = 3
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'portfolio_proposals'
          AND column_name = ANY (
              ARRAY[
                  'account_id',
                  'created_session_digest',
                  'proposal_hash'
              ]
          )
    )
    AND (
        SELECT count(*) = 3
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'portfolio_proposal_actions'
          AND column_name = ANY (
              ARRAY[
                  'session_digest',
                  'user_reason',
                  'deferred_until'
              ]
          )
    )
    AND (
        SELECT count(*) = 32
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
                  'strategy_drafts',
                  'workspace_preferences',
                  'investment_goals',
                  'workspace_events',
                  'notification_channels',
                  'notification_outbox',
                  'strategy_research_evidence',
                  'strategy_research_runs',
                  'strategy_research_requests', 'notification_outbox_events',
                  'goal_plans',
                  'assistant_connections',
                  'assistant_conversations',
                  'assistant_requests',
                  'assistant_messages',
                  'assistant_memory',
                  'billing_payments'
              ]
          )
          AND c.relrowsecurity
          AND c.relforcerowsecurity
    )
    AS ready
"""
