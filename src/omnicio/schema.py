"""Canonical PostgreSQL readiness shared by runtime and deployment gate. No dependencies."""

READINESS_QUERY = """
SELECT
    to_regclass('public.users') IS NOT NULL
    AND to_regclass('public.sessions') IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM (VALUES
            ('email_identities', 'user_id', 'uuid', true, NULL),
            ('email_identities', 'email', 'text', true, NULL),
            ('email_identities', 'password_hash', 'text', true, NULL),
            ('email_identities', 'password_version', 'integer', true, '1'),
            ('email_identities', 'verified_at', 'timestamp with time zone', true, 'now()'),
            ('email_identities', 'password_changed_at', 'timestamp with time zone', true, 'now()'),
            ('email_auth_challenges', 'id', 'uuid', true, NULL),
            ('email_auth_challenges', 'purpose', 'text', true, NULL),
            ('email_auth_challenges', 'email', 'text', true, NULL),
            ('email_auth_challenges', 'user_id', 'uuid', false, NULL),
            ('email_auth_challenges', 'enrollment_session_digest', 'bytea', false, NULL),
            ('email_auth_challenges', 'password_hash', 'text', false, NULL),
            ('email_auth_challenges', 'password_version', 'integer', false, NULL),
            ('email_auth_challenges', 'flow_digest', 'bytea', true, NULL),
            ('email_auth_challenges', 'code_digest', 'bytea', true, NULL),
            ('email_auth_challenges', 'client_ip_hash', 'bytea', true, NULL),
            ('email_auth_challenges', 'legal_versions', 'jsonb', true, '''{}''::jsonb'),
            ('email_auth_challenges', 'attempts_remaining', 'smallint', true, NULL),
            ('email_auth_challenges', 'suppressed', 'boolean', true, 'false'),
            ('email_auth_challenges', 'created_at', 'timestamp with time zone', true, 'now()'),
            ('email_auth_challenges', 'expires_at', 'timestamp with time zone', true, NULL),
            ('email_auth_challenges', 'consumed_at', 'timestamp with time zone', false, NULL),
            ('email_auth_challenges', 'resend_at', 'timestamp with time zone', true, NULL),
            ('email_auth_challenges', 'delivery_ciphertext', 'bytea', false, NULL),
            ('email_auth_challenges', 'delivery_state', 'text', true, NULL),
            ('email_auth_challenges', 'delivery_attempts', 'smallint', true, '0'),
            ('email_auth_challenges', 'next_delivery_at',
             'timestamp with time zone', true, 'now()'),
            ('email_auth_challenges', 'delivery_started_at',
             'timestamp with time zone', false, NULL),
            ('email_auth_challenges', 'delivery_code', 'text', false, NULL),
            ('email_auth_rate_limits', 'bucket_digest', 'bytea', true, NULL),
            ('email_auth_rate_limits', 'window_started_at',
             'timestamp with time zone', true, 'now()'),
            ('email_auth_rate_limits', 'expires_at', 'timestamp with time zone', true, NULL),
            ('email_auth_rate_limits', 'attempts', 'integer', true, NULL)
        ) AS expected(table_name, column_name, type_name, required, default_expression)
        LEFT JOIN pg_class AS relation
          ON relation.oid = to_regclass('public.' || expected.table_name)
        LEFT JOIN pg_attribute AS attribute
          ON attribute.attrelid = relation.oid AND attribute.attname = expected.column_name
          AND attribute.attnum > 0 AND NOT attribute.attisdropped
        LEFT JOIN pg_attrdef AS defaults
          ON defaults.adrelid = relation.oid AND defaults.adnum = attribute.attnum
        WHERE relation.relkind IS DISTINCT FROM 'r'
          OR relation.relrowsecurity IS DISTINCT FROM false
          OR relation.relforcerowsecurity IS DISTINCT FROM false
          OR attribute.atttypid IS DISTINCT FROM to_regtype(expected.type_name)
          OR attribute.attnotnull IS DISTINCT FROM expected.required
          OR (expected.default_expression IS NOT NULL
              AND pg_get_expr(defaults.adbin, defaults.adrelid)
                  IS DISTINCT FROM expected.default_expression)
          OR EXISTS (
              SELECT 1 FROM aclexplode(COALESCE(relation.relacl,
                  acldefault('r', relation.relowner))) AS privileges WHERE privileges.grantee = 0
          )
    )
    AND NOT EXISTS (
        SELECT 1
        FROM (VALUES
            ('email_identities', 'email_identities_pkey', 'p', ARRAY['user_id']),
            ('email_identities', 'email_identities_email_key', 'u', ARRAY['email']),
            ('email_identities', 'email_identities_user_id_fkey', 'f', ARRAY['user_id']),
            ('email_auth_challenges', 'email_auth_challenges_pkey', 'p', ARRAY['id']),
            ('email_auth_challenges', 'email_auth_challenges_user_id_fkey', 'f', ARRAY['user_id']),
            ('email_auth_rate_limits', 'email_auth_rate_limits_pkey', 'p', ARRAY['bucket_digest'])
        ) AS expected(table_name, constraint_name, kind, columns)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_constraint AS constraint_definition
            WHERE constraint_definition.conrelid = to_regclass('public.' || expected.table_name)
              AND constraint_definition.conname = expected.constraint_name
              AND constraint_definition.contype::text = expected.kind
              AND constraint_definition.convalidated AND constraint_definition.conenforced
              AND NOT constraint_definition.condeferrable
              AND ARRAY(
                  SELECT attribute.attname::text
                  FROM unnest(constraint_definition.conkey) WITH ORDINALITY AS key(number, position)
                  JOIN pg_attribute AS attribute
                    ON attribute.attrelid = constraint_definition.conrelid
                    AND attribute.attnum = key.number
                  ORDER BY key.position
              ) = expected.columns
              AND (expected.kind <> 'f' OR (
                  constraint_definition.confrelid = to_regclass('public.users')
                  AND constraint_definition.confdeltype = 'c'
                  AND constraint_definition.confkey = ARRAY(
                      SELECT attnum FROM pg_attribute
                      WHERE attrelid = to_regclass('public.users') AND attname = 'id'
                  )
              ))
              AND (expected.kind = 'f' OR EXISTS (
                  SELECT 1 FROM pg_index WHERE indexrelid = constraint_definition.conindid
                    AND indisunique AND indisvalid AND indisready
              ))
        )
    )
    AND NOT EXISTS (
        SELECT 1
        FROM (VALUES
            ('email_identities', 'email_identities_password_version_check',
             $check$(password_version > 0)$check$),
            ('email_identities', 'email_identity_address_valid',
             $check$((char_length(email) >= 3) AND (char_length(email) <= 254)
                 AND (split_part(email, '@'::text, 2)
                     = ANY (ARRAY['gmail.com'::text, 'mail.ru'::text, 'xmail.ru'::text])))$check$),
            ('email_identities', 'email_identity_hash_valid',
             $check$((password_hash ~~ '$argon2id$%'::text)
                 AND (char_length(password_hash) <= 512))$check$),
            ('email_auth_challenges', 'email_auth_challenges_purpose_check',
             $check$(purpose = ANY (
                 ARRAY['register'::text, 'enroll'::text, 'reset'::text]))$check$),
            ('email_auth_challenges', 'email_auth_challenges_email_check',
             $check$((char_length(email) >= 3) AND (char_length(email) <= 254))$check$),
            ('email_auth_challenges', 'email_auth_challenges_flow_digest_check',
             $check$(octet_length(flow_digest) = 32)$check$),
            ('email_auth_challenges', 'email_auth_challenges_code_digest_check',
             $check$(octet_length(code_digest) = 32)$check$),
            ('email_auth_challenges', 'email_auth_challenges_client_ip_hash_check',
             $check$(octet_length(client_ip_hash) = 32)$check$),
            ('email_auth_challenges', 'email_auth_challenges_attempts_remaining_check',
             $check$((attempts_remaining >= 0) AND (attempts_remaining <= 5))$check$),
            ('email_auth_challenges', 'email_auth_challenges_delivery_state_check',
             $check$(delivery_state = ANY (ARRAY['pending'::text, 'sending'::text,
                 'accepted'::text, 'failed'::text, 'uncertain'::text, 'suppressed'::text]))$check$),
            ('email_auth_challenges', 'email_auth_challenges_delivery_attempts_check',
             $check$((delivery_attempts >= 0) AND (delivery_attempts <= 3))$check$),
            ('email_auth_challenges', 'email_challenge_expiry',
             $check$(expires_at > created_at)$check$),
            ('email_auth_challenges', 'email_challenge_enrollment',
             $check$(((purpose = 'enroll'::text) AND (user_id IS NOT NULL)
                 AND (enrollment_session_digest IS NOT NULL)
                 AND (octet_length(enrollment_session_digest) = 32))
                 OR ((purpose <> 'enroll'::text) AND (enrollment_session_digest IS NULL)))$check$),
            ('email_auth_challenges', 'email_challenge_password',
             $check$(((purpose = ANY (ARRAY['register'::text, 'enroll'::text]))
                 AND (password_hash IS NOT NULL) AND (password_hash ~~ '$argon2id$%'::text))
                 OR ((purpose = 'reset'::text) AND (password_hash IS NULL)))$check$),
            ('email_auth_rate_limits', 'email_auth_rate_limits_bucket_digest_check',
             $check$(octet_length(bucket_digest) = 32)$check$),
            ('email_auth_rate_limits', 'email_auth_rate_limits_attempts_check',
             $check$((attempts >= 1) AND (attempts <= 1000000000))$check$),
            ('sessions', 'sessions_authentication_evidence',
             $check$(((authenticated_provider IS NULL) AND (authenticated_at IS NULL))
                 OR ((authenticated_provider IS NOT NULL)
                     AND (authenticated_provider
                         = ANY (ARRAY['vkid'::text, 'tid'::text, 'email'::text]))
                     AND (authenticated_at IS NOT NULL)))$check$)
        ) AS expected(table_name, constraint_name, expression)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_constraint AS constraint_definition
            WHERE constraint_definition.conrelid = to_regclass('public.' || expected.table_name)
              AND constraint_definition.conname = expected.constraint_name
              AND constraint_definition.contype = 'c'
              AND constraint_definition.convalidated AND constraint_definition.conenforced
              AND regexp_replace(pg_get_expr(constraint_definition.conbin,
                  constraint_definition.conrelid), '[[:space:]]', '', 'g')
                  = regexp_replace(expected.expression, '[[:space:]]', '', 'g')
        )
    )
    AND NOT EXISTS (
        SELECT 1
        FROM (VALUES
            ('email_auth_challenges', 'email_auth_challenges_email_idx',
             ARRAY['email', 'purpose', 'created_at'], NULL),
            ('email_auth_challenges', 'email_auth_challenges_delivery_idx',
             ARRAY['next_delivery_at', 'created_at'],
             $predicate$((delivery_state = 'pending'::text) AND (consumed_at IS NULL))$predicate$),
            ('email_auth_challenges', 'email_auth_challenges_expiry_idx',
             ARRAY['expires_at'], NULL),
            ('email_auth_rate_limits', 'email_auth_rate_limits_expiry_idx',
             ARRAY['expires_at'], NULL)
        ) AS expected(table_name, index_name, columns, predicate)
        WHERE NOT EXISTS (
            SELECT 1 FROM pg_index AS index_definition
            WHERE index_definition.indexrelid = to_regclass('public.' || expected.index_name)
              AND index_definition.indrelid = to_regclass('public.' || expected.table_name)
              AND index_definition.indisvalid AND index_definition.indisready
              AND index_definition.indexprs IS NULL
              AND index_definition.indnkeyatts = cardinality(expected.columns)
              AND ARRAY(
                  SELECT attribute.attname::text
                  FROM unnest(index_definition.indkey) WITH ORDINALITY AS key(number, position)
                  JOIN pg_attribute AS attribute
                    ON attribute.attrelid = index_definition.indrelid
                    AND attribute.attnum = key.number
                  WHERE key.position <= index_definition.indnkeyatts ORDER BY key.position
              ) = expected.columns
              AND regexp_replace(pg_get_expr(index_definition.indpred,
                  index_definition.indrelid), '[[:space:]]', '', 'g')
                  IS NOT DISTINCT FROM regexp_replace(expected.predicate, '[[:space:]]', '', 'g')
        )
    )
    AND (
        SELECT count(*) = 3 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'portfolio_snapshots'
          AND column_name IN ('nav_rub', 'rub_cash_total', 'rub_cash_blocked')
          AND is_nullable = 'YES' AND data_type = 'numeric'
          AND numeric_precision = 24 AND numeric_scale = 8
    )
    AND to_regclass('public.legal_acceptances') IS NOT NULL
    AND to_regclass('public.vkid_identities') IS NOT NULL
    AND to_regclass('public.tid_identities') IS NOT NULL
    AND to_regclass('public.oauth_flow_claims') IS NOT NULL
    AND to_regclass('public.workspace_preferences') IS NOT NULL
    AND to_regclass('public.investment_goals') IS NOT NULL
    AND to_regclass('public.workspace_events') IS NOT NULL
    AND to_regclass('public.notification_channels') IS NOT NULL
    AND to_regclass('public.notification_outbox') IS NOT NULL
    AND (
        SELECT count(*) = 5 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_push_authorizations'
          AND column_name IN ('origin', 'identity_hash', 'issued_at', 'expires_at',
                               'authorization_ciphertext') AND is_nullable = 'NO'
    )
    AND EXISTS (
        SELECT 1 FROM pg_index
        WHERE indexrelid = to_regclass('public.notification_push_active_destination_key')
          AND indisunique AND indisvalid AND indisready
    )
    AND (
        SELECT count(*) = 2 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_channels'
          AND column_name IN ('session_id', 'binding_id')
    )
    AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'notification_outbox'
          AND column_name = 'binding_id'
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.notification_channels') AND contype = 'f'
          AND convalidated AND conname = 'notification_channels_session_owner_fkey'
    )
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
