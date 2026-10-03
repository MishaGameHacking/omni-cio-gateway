BEGIN;

CREATE TABLE IF NOT EXISTS portfolio_live_execution_mandates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id text NOT NULL CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    ),
    max_order_notional_rub numeric(18, 2) NOT NULL CHECK (
        max_order_notional_rub > 0
    ),
    max_daily_notional_rub numeric(18, 2) NOT NULL CHECK (
        max_daily_notional_rub >= max_order_notional_rub
    ),
    created_session_digest bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CONSTRAINT portfolio_live_execution_mandates_session_digest_size CHECK (
        octet_length(created_session_digest) = 32
    ),
    CONSTRAINT portfolio_live_execution_mandates_expiry CHECK (
        expires_at > created_at
    ),
    CONSTRAINT portfolio_live_execution_mandates_revocation CHECK (
        revoked_at IS NULL OR revoked_at >= created_at
    )
);

ALTER TABLE portfolio_live_execution_mandates
    DROP CONSTRAINT IF EXISTS portfolio_live_execution_mandates_expiry_window,
    ADD CONSTRAINT portfolio_live_execution_mandates_expiry_window CHECK (
        expires_at <= created_at + interval '24 hours'
    );

CREATE UNIQUE INDEX IF NOT EXISTS portfolio_live_execution_mandates_active_idx
    ON portfolio_live_execution_mandates (user_id)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS portfolio_live_execution_mandates_user_created_idx
    ON portfolio_live_execution_mandates (user_id, created_at DESC);

ALTER TABLE portfolio_live_execution_mandates ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_live_execution_mandates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_live_execution_mandates_tenant
    ON portfolio_live_execution_mandates;
CREATE POLICY portfolio_live_execution_mandates_tenant
    ON portfolio_live_execution_mandates
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

CREATE OR REPLACE FUNCTION omnicio_validate_live_execution_mandate_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF (
        NEW.user_id,
        NEW.account_id,
        NEW.max_order_notional_rub,
        NEW.max_daily_notional_rub,
        NEW.created_session_digest,
        NEW.created_at,
        NEW.expires_at
    ) IS DISTINCT FROM (
        OLD.user_id,
        OLD.account_id,
        OLD.max_order_notional_rub,
        OLD.max_daily_notional_rub,
        OLD.created_session_digest,
        OLD.created_at,
        OLD.expires_at
    ) THEN
        RAISE EXCEPTION 'live execution mandate source fields are immutable';
    END IF;
    IF OLD.revoked_at IS NOT NULL
       AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'revoked live execution mandate is immutable';
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_live_execution_mandates_update_guard
    ON portfolio_live_execution_mandates;
CREATE TRIGGER portfolio_live_execution_mandates_update_guard
BEFORE UPDATE ON portfolio_live_execution_mandates
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_live_execution_mandate_mutation();

DROP TRIGGER IF EXISTS portfolio_live_execution_mandates_no_delete
    ON portfolio_live_execution_mandates;
CREATE TRIGGER portfolio_live_execution_mandates_no_delete
BEFORE DELETE ON portfolio_live_execution_mandates
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_delete();

ALTER TABLE portfolio_execution_runs
    ADD COLUMN IF NOT EXISTS live_mandate_id uuid
        REFERENCES portfolio_live_execution_mandates(id) ON DELETE CASCADE;

ALTER TABLE portfolio_execution_runs
    DROP CONSTRAINT IF EXISTS portfolio_execution_runs_mode_check,
    DROP CONSTRAINT IF EXISTS portfolio_execution_runs_provider_environment_check,
    DROP CONSTRAINT IF EXISTS portfolio_execution_runs_mode_environment;

ALTER TABLE portfolio_execution_runs
    ADD CONSTRAINT portfolio_execution_runs_mode_check
        CHECK (mode IN ('shadow', 'sandbox', 'live')),
    ADD CONSTRAINT portfolio_execution_runs_provider_environment_check
        CHECK (
            provider_environment IS NULL
            OR provider_environment IN ('sandbox', 'prod')
        ),
    ADD CONSTRAINT portfolio_execution_runs_mode_environment CHECK (
        (
            mode = 'shadow'
            AND provider_environment IS NULL
            AND live_mandate_id IS NULL
        )
        OR (
            mode = 'sandbox'
            AND provider_environment = 'sandbox'
            AND live_mandate_id IS NULL
        )
        OR (
            mode = 'live'
            AND provider_environment = 'prod'
            AND live_mandate_id IS NOT NULL
        )
    );

CREATE UNIQUE INDEX IF NOT EXISTS portfolio_execution_runs_one_active_live_idx
    ON portfolio_execution_runs (user_id, account_id)
    WHERE mode = 'live'
      AND status IN ('created', 'running', 'reconciling');

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
        NEW.live_mandate_id,
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
        OLD.live_mandate_id,
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

    IF TG_OP = 'INSERT'
       AND NEW.mode = 'live'
       AND NOT EXISTS (
           SELECT 1
           FROM portfolio_live_execution_mandates AS m
           WHERE m.id = NEW.live_mandate_id
             AND m.user_id = NEW.user_id
             AND m.account_id = NEW.account_id
             AND m.revoked_at IS NULL
             AND m.expires_at > now()
       ) THEN
        RAISE EXCEPTION 'live execution requires an active exact-account mandate';
    END IF;

    RETURN NEW;
END;
$omnicio$;


CREATE OR REPLACE FUNCTION omnicio_validate_live_submission_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF NEW.status = 'submitting'
       AND OLD.status IS DISTINCT FROM NEW.status
       AND EXISTS (
           SELECT 1
           FROM portfolio_execution_runs AS r
           WHERE r.id = NEW.run_id
             AND r.user_id = NEW.user_id
             AND r.mode = 'live'
       ) THEN
        PERFORM 1
        FROM portfolio_execution_runs AS r
        JOIN portfolio_live_execution_mandates AS m
          ON m.id = r.live_mandate_id
         AND m.user_id = r.user_id
         AND m.account_id = r.account_id
        WHERE r.id = NEW.run_id
          AND r.user_id = NEW.user_id
          AND r.mode = 'live'
          AND m.revoked_at IS NULL
          AND m.expires_at > now()
        FOR SHARE OF m;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'live execution mandate is inactive before submission';
        END IF;
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_execution_legs_live_submission_guard
    ON portfolio_execution_legs;
CREATE TRIGGER portfolio_execution_legs_live_submission_guard
BEFORE UPDATE OF status ON portfolio_execution_legs
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_live_submission_authority();

COMMIT;
