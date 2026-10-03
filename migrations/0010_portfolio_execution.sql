BEGIN;

-- R5 proposals are immutable during normal operation, but broker disconnect and
-- authenticated account deletion must still be able to purge user-owned financial
-- data in the same transaction.  Replace the accepted R5 RESTRICT edges with
-- cleanup-safe cascades and keep DELETE fail-closed unless the server explicitly
-- enables one of the narrow transaction-local cleanup scopes.
ALTER TABLE portfolio_proposals
    DROP CONSTRAINT IF EXISTS portfolio_proposals_source_snapshot_id_user_id_fkey,
    DROP CONSTRAINT IF EXISTS portfolio_proposals_source_snapshot_tenant_fkey;
ALTER TABLE portfolio_proposals
    ADD CONSTRAINT portfolio_proposals_source_snapshot_tenant_fkey
    FOREIGN KEY (source_snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE;

ALTER TABLE portfolio_proposal_actions
    DROP CONSTRAINT IF EXISTS portfolio_proposal_actions_proposal_id_user_id_fkey,
    DROP CONSTRAINT IF EXISTS portfolio_proposal_actions_proposal_tenant_fkey;
ALTER TABLE portfolio_proposal_actions
    ADD CONSTRAINT portfolio_proposal_actions_proposal_tenant_fkey
    FOREIGN KEY (proposal_id, user_id)
        REFERENCES portfolio_proposals(id, user_id)
        ON DELETE CASCADE;

CREATE OR REPLACE FUNCTION omnicio_reject_immutable_proposal_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('omnicio.financial_cleanup', true) IN (
           'account_delete',
           'broker_disconnect'
       ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'immutable proposal rows cannot be updated or deleted';
END;
$$;

CREATE TABLE IF NOT EXISTS portfolio_execution_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    proposal_id uuid NOT NULL,
    confirmed_action_id bigint NOT NULL,
    proposal_version integer NOT NULL CHECK (proposal_version > 0),
    proposal_hash bytea NOT NULL,
    account_id text NOT NULL CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    ),
    mode text NOT NULL CHECK (mode IN ('shadow', 'sandbox')),
    provider_environment text CHECK (
        provider_environment IS NULL OR provider_environment = 'sandbox'
    ),
    status text NOT NULL DEFAULT 'created' CHECK (
        status IN (
            'created',
            'running',
            'reconciling',
            'succeeded',
            'cancelled',
            'failed'
        )
    ),
    created_session_digest bytea NOT NULL,
    error_code text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CONSTRAINT portfolio_execution_runs_hash_size CHECK (
        octet_length(proposal_hash) = 32
    ),
    CONSTRAINT portfolio_execution_runs_session_digest_size CHECK (
        octet_length(created_session_digest) = 32
    ),
    CONSTRAINT portfolio_execution_runs_mode_environment CHECK (
        (
            mode = 'shadow'
            AND provider_environment IS NULL
        )
        OR (
            mode = 'sandbox'
            AND provider_environment = 'sandbox'
        )
    ),
    CONSTRAINT portfolio_execution_runs_finished_shape CHECK (
        (
            status IN ('succeeded', 'cancelled', 'failed')
            AND finished_at IS NOT NULL
        )
        OR (
            status IN ('created', 'running', 'reconciling')
            AND finished_at IS NULL
        )
    ),
    UNIQUE (id, user_id),
    UNIQUE (proposal_id, mode),
    FOREIGN KEY (proposal_id, user_id)
        REFERENCES portfolio_proposals(id, user_id)
        ON DELETE CASCADE,
    FOREIGN KEY (confirmed_action_id)
        REFERENCES portfolio_proposal_actions(id)
        ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION omnicio_validate_execution_run_source()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF TG_OP = 'UPDATE' AND (
        NEW.user_id,
        NEW.proposal_id,
        NEW.confirmed_action_id,
        NEW.proposal_version,
        NEW.proposal_hash,
        NEW.account_id,
        NEW.mode,
        NEW.provider_environment,
        NEW.created_session_digest
    ) IS DISTINCT FROM (
        OLD.user_id,
        OLD.proposal_id,
        OLD.confirmed_action_id,
        OLD.proposal_version,
        OLD.proposal_hash,
        OLD.account_id,
        OLD.mode,
        OLD.provider_environment,
        OLD.created_session_digest
    ) THEN
        RAISE EXCEPTION 'execution source fields are immutable';
    END IF;

    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1
        FROM portfolio_proposals AS p
        JOIN portfolio_proposal_actions AS a
          ON a.proposal_id = p.id
         AND a.user_id = p.user_id
        WHERE p.id = NEW.proposal_id
          AND p.user_id = NEW.user_id
          AND p.version = NEW.proposal_version
          AND p.proposal_hash = NEW.proposal_hash
          AND p.account_id = NEW.account_id
          AND p.expires_at > now()
          AND (p.source_snapshot_id, p.account_id) = (
              SELECT s.id, s.account_id
              FROM portfolio_snapshots AS s
              WHERE s.user_id = NEW.user_id
              ORDER BY s.captured_at DESC, s.created_at DESC
              LIMIT 1
          )
          AND p.profile_version = (
              SELECT ip.version
              FROM investment_profile_versions AS ip
              WHERE ip.user_id = NEW.user_id
              ORDER BY ip.version DESC
              LIMIT 1
          )
          AND p.policy_version = (
              SELECT bp.version
              FROM balancing_policy_versions AS bp
              WHERE bp.user_id = NEW.user_id
              ORDER BY bp.version DESC
              LIMIT 1
          )
          AND a.id = NEW.confirmed_action_id
          AND a.action = 'confirmed'
          AND a.proposal_version = NEW.proposal_version
          AND a.proposal_hash = NEW.proposal_hash
    ) THEN
        RAISE EXCEPTION 'execution source is not an exact confirmed proposal';
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_execution_runs_source_guard
    ON portfolio_execution_runs;
CREATE TRIGGER portfolio_execution_runs_source_guard
BEFORE INSERT OR UPDATE ON portfolio_execution_runs
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_execution_run_source();

CREATE INDEX IF NOT EXISTS portfolio_execution_runs_user_created_idx
    ON portfolio_execution_runs (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_execution_legs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL,
    user_id uuid NOT NULL,
    leg_index integer NOT NULL CHECK (leg_index >= 0),
    action text NOT NULL CHECK (action IN ('buy', 'sell')),
    instrument_uid text NOT NULL CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    ),
    lots_requested bigint NOT NULL CHECK (lots_requested > 0),
    lots_executed bigint NOT NULL DEFAULT 0 CHECK (
        lots_executed >= 0 AND lots_executed <= lots_requested
    ),
    limit_price numeric(24, 9) NOT NULL CHECK (limit_price > 0),
    limit_price_type text NOT NULL CHECK (
        limit_price_type IN ('point', 'currency')
    ),
    max_spend_rub numeric(24, 9),
    min_proceeds_rub numeric(24, 9),
    request_id uuid NOT NULL,
    provider_order_id text,
    provider_status text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'pending' CHECK (
        status IN (
            'pending',
            'submitting',
            'submitted',
            'partially_filled',
            'filled',
            'cancel_requested',
            'cancelled',
            'rejected',
            'reconciling',
            'failed',
            'shadow_filled'
        )
    ),
    executed_amount_rub numeric(24, 9) NOT NULL DEFAULT 0 CHECK (
        executed_amount_rub >= 0
    ),
    executed_commission_rub numeric(24, 9) NOT NULL DEFAULT 0 CHECK (
        executed_commission_rub >= 0
    ),
    submitted_at timestamptz,
    last_checked_at timestamptz,
    terminal_at timestamptz,
    CONSTRAINT portfolio_execution_legs_trade_bounds CHECK (
        (
            action = 'buy'
            AND max_spend_rub IS NOT NULL
            AND max_spend_rub > 0
            AND min_proceeds_rub IS NULL
        )
        OR (
            action = 'sell'
            AND min_proceeds_rub IS NOT NULL
            AND min_proceeds_rub > 0
            AND max_spend_rub IS NULL
        )
    ),
    CONSTRAINT portfolio_execution_legs_provider_order_id CHECK (
        provider_order_id IS NULL
        OR char_length(provider_order_id) BETWEEN 1 AND 128
    ),
    UNIQUE (id, user_id),
    UNIQUE (id, run_id, user_id),
    UNIQUE (run_id, leg_index),
    UNIQUE (request_id),
    FOREIGN KEY (run_id, user_id)
        REFERENCES portfolio_execution_runs(id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS portfolio_execution_legs_run_idx
    ON portfolio_execution_legs (run_id, leg_index);

CREATE OR REPLACE FUNCTION omnicio_validate_execution_leg_source()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF (
        NEW.run_id,
        NEW.user_id,
        NEW.leg_index,
        NEW.action,
        NEW.instrument_uid,
        NEW.lots_requested,
        NEW.limit_price,
        NEW.limit_price_type,
        NEW.max_spend_rub,
        NEW.min_proceeds_rub,
        NEW.request_id
    ) IS DISTINCT FROM (
        OLD.run_id,
        OLD.user_id,
        OLD.leg_index,
        OLD.action,
        OLD.instrument_uid,
        OLD.lots_requested,
        OLD.limit_price,
        OLD.limit_price_type,
        OLD.max_spend_rub,
        OLD.min_proceeds_rub,
        OLD.request_id
    ) THEN
        RAISE EXCEPTION 'execution leg source fields are immutable';
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_execution_legs_source_guard
    ON portfolio_execution_legs;
CREATE TRIGGER portfolio_execution_legs_source_guard
BEFORE UPDATE ON portfolio_execution_legs
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_execution_leg_source();

CREATE TABLE IF NOT EXISTS portfolio_execution_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL,
    leg_id uuid,
    user_id uuid NOT NULL,
    event_type text NOT NULL CHECK (
        char_length(event_type) BETWEEN 1 AND 128
    ),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (run_id, user_id)
        REFERENCES portfolio_execution_runs(id, user_id)
        ON DELETE CASCADE,
    FOREIGN KEY (leg_id, run_id, user_id)
        REFERENCES portfolio_execution_legs(id, run_id, user_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS portfolio_execution_events_run_idx
    ON portfolio_execution_events (run_id, id);

ALTER TABLE portfolio_execution_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_execution_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_execution_runs_tenant
    ON portfolio_execution_runs;
CREATE POLICY portfolio_execution_runs_tenant
    ON portfolio_execution_runs
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

ALTER TABLE portfolio_execution_legs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_execution_legs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_execution_legs_tenant
    ON portfolio_execution_legs;
CREATE POLICY portfolio_execution_legs_tenant
    ON portfolio_execution_legs
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

ALTER TABLE portfolio_execution_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_execution_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_execution_events_tenant
    ON portfolio_execution_events;
CREATE POLICY portfolio_execution_events_tenant
    ON portfolio_execution_events
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

CREATE OR REPLACE FUNCTION omnicio_reject_execution_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio_cleanup$
BEGIN
    IF current_setting('omnicio.financial_cleanup', true) IN (
        'account_delete',
        'broker_disconnect'
    ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'execution ledger rows cannot be deleted';
END;
$omnicio_cleanup$;

DROP TRIGGER IF EXISTS portfolio_execution_runs_no_delete
    ON portfolio_execution_runs;
CREATE TRIGGER portfolio_execution_runs_no_delete
BEFORE DELETE ON portfolio_execution_runs
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_delete();

DROP TRIGGER IF EXISTS portfolio_execution_legs_no_delete
    ON portfolio_execution_legs;
CREATE TRIGGER portfolio_execution_legs_no_delete
BEFORE DELETE ON portfolio_execution_legs
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_delete();

CREATE OR REPLACE FUNCTION omnicio_reject_execution_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio_cleanup$
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('omnicio.financial_cleanup', true) IN (
           'account_delete',
           'broker_disconnect'
       ) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'execution events are immutable';
END;
$omnicio_cleanup$;

DROP TRIGGER IF EXISTS portfolio_execution_events_immutable
    ON portfolio_execution_events;
CREATE TRIGGER portfolio_execution_events_immutable
BEFORE UPDATE OR DELETE ON portfolio_execution_events
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_event_mutation();

COMMIT;
