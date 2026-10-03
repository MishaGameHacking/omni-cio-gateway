BEGIN;

ALTER TABLE operation_observations
    ADD CONSTRAINT operation_observations_id_user_account_key
    UNIQUE (id, user_id, account_id);

CREATE TABLE IF NOT EXISTS portfolio_reinvestment_mandates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    profile_version integer NOT NULL CHECK (profile_version > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    allow_dividends boolean NOT NULL,
    allow_coupons boolean NOT NULL,
    cash_reserve_rub numeric(18, 2) NOT NULL CHECK (cash_reserve_rub >= 0),
    max_order_notional_rub numeric(18, 2) NOT NULL CHECK (max_order_notional_rub > 0),
    max_daily_notional_rub numeric(18, 2) NOT NULL CHECK (
        max_daily_notional_rub >= max_order_notional_rub
    ),
    max_monthly_notional_rub numeric(18, 2) NOT NULL CHECK (
        max_monthly_notional_rub >= max_daily_notional_rub
    ),
    max_slippage_bps integer NOT NULL CHECK (max_slippage_bps BETWEEN 0 AND 500),
    created_session_digest bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    UNIQUE (id, user_id, account_id),
    UNIQUE (user_id, version),
    CONSTRAINT portfolio_reinvestment_mandates_account_nonempty CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    ),
    CONSTRAINT portfolio_reinvestment_mandates_income_types CHECK (
        allow_dividends OR allow_coupons
    ),
    CONSTRAINT portfolio_reinvestment_mandates_session_digest_size CHECK (
        octet_length(created_session_digest) = 32
    ),
    CONSTRAINT portfolio_reinvestment_mandates_expiry CHECK (
        expires_at > created_at
        AND expires_at <= created_at + interval '90 days'
    ),
    CONSTRAINT portfolio_reinvestment_mandates_revocation CHECK (
        revoked_at IS NULL OR revoked_at >= created_at
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS portfolio_reinvestment_mandates_active_idx
    ON portfolio_reinvestment_mandates (user_id)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS portfolio_reinvestment_mandates_user_created_idx
    ON portfolio_reinvestment_mandates (user_id, created_at DESC);

ALTER TABLE portfolio_reinvestment_mandates ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_reinvestment_mandates FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_reinvestment_mandates_tenant
    ON portfolio_reinvestment_mandates;
CREATE POLICY portfolio_reinvestment_mandates_tenant
    ON portfolio_reinvestment_mandates
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

CREATE OR REPLACE FUNCTION omnicio_validate_reinvestment_mandate_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF (
        NEW.user_id,
        NEW.account_id,
        NEW.version,
        NEW.profile_version,
        NEW.policy_version,
        NEW.allow_dividends,
        NEW.allow_coupons,
        NEW.cash_reserve_rub,
        NEW.max_order_notional_rub,
        NEW.max_daily_notional_rub,
        NEW.max_monthly_notional_rub,
        NEW.max_slippage_bps,
        NEW.created_session_digest,
        NEW.created_at,
        NEW.expires_at
    ) IS DISTINCT FROM (
        OLD.user_id,
        OLD.account_id,
        OLD.version,
        OLD.profile_version,
        OLD.policy_version,
        OLD.allow_dividends,
        OLD.allow_coupons,
        OLD.cash_reserve_rub,
        OLD.max_order_notional_rub,
        OLD.max_daily_notional_rub,
        OLD.max_monthly_notional_rub,
        OLD.max_slippage_bps,
        OLD.created_session_digest,
        OLD.created_at,
        OLD.expires_at
    ) THEN
        RAISE EXCEPTION 'reinvestment mandate source fields are immutable';
    END IF;
    IF OLD.revoked_at IS NOT NULL
       AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
        RAISE EXCEPTION 'revoked reinvestment mandate is immutable';
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_reinvestment_mandates_update_guard
    ON portfolio_reinvestment_mandates;
CREATE TRIGGER portfolio_reinvestment_mandates_update_guard
BEFORE UPDATE ON portfolio_reinvestment_mandates
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_reinvestment_mandate_mutation();

DROP TRIGGER IF EXISTS portfolio_reinvestment_mandates_no_delete
    ON portfolio_reinvestment_mandates;
CREATE TRIGGER portfolio_reinvestment_mandates_no_delete
BEFORE DELETE ON portfolio_reinvestment_mandates
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_delete();

CREATE TABLE IF NOT EXISTS portfolio_reinvestment_income_credits (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mandate_id uuid NOT NULL,
    user_id uuid NOT NULL,
    account_id text NOT NULL,
    source_operation_observation_id bigint NOT NULL,
    operation_type text NOT NULL CHECK (
        operation_type IN ('OPERATION_TYPE_DIVIDEND', 'OPERATION_TYPE_COUPON')
    ),
    credited_at timestamptz NOT NULL,
    amount_rub numeric(24, 9) NOT NULL CHECK (amount_rub > 0),
    source_semantic_hash bytea NOT NULL,
    source_observed_at timestamptz NOT NULL,
    verification_status text NOT NULL DEFAULT 'provider_executed_unverified' CHECK (
        verification_status IN (
            'provider_executed_unverified',
            'verified',
            'ambiguous',
            'revoked'
        )
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_operation_observation_id),
    UNIQUE (mandate_id, source_semantic_hash),
    FOREIGN KEY (mandate_id, user_id, account_id)
        REFERENCES portfolio_reinvestment_mandates(id, user_id, account_id)
        ON DELETE CASCADE,
    FOREIGN KEY (source_operation_observation_id, user_id, account_id)
        REFERENCES operation_observations(id, user_id, account_id)
        ON DELETE CASCADE,
    CONSTRAINT portfolio_reinvestment_income_credits_hash_size CHECK (
        octet_length(source_semantic_hash) = 32
    )
);

CREATE INDEX IF NOT EXISTS portfolio_reinvestment_income_user_credit_idx
    ON portfolio_reinvestment_income_credits (user_id, credited_at DESC);

ALTER TABLE portfolio_reinvestment_income_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_reinvestment_income_credits FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_reinvestment_income_credits_tenant
    ON portfolio_reinvestment_income_credits;
CREATE POLICY portfolio_reinvestment_income_credits_tenant
    ON portfolio_reinvestment_income_credits
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

CREATE OR REPLACE FUNCTION omnicio_validate_reinvestment_income_credit()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'reinvestment income credits are immutable';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM operation_observations AS o
        JOIN portfolio_reinvestment_mandates AS m
          ON m.id = NEW.mandate_id
         AND m.user_id = NEW.user_id
         AND m.account_id = NEW.account_id
        WHERE o.id = NEW.source_operation_observation_id
          AND o.user_id = NEW.user_id
          AND o.account_id = NEW.account_id
          AND o.operation_type = NEW.operation_type
          AND o.operation_state = 'OPERATION_STATE_EXECUTED'
          AND lower(COALESCE(o.payment_currency, '')) = 'rub'
          AND o.payment_value = NEW.amount_rub
          AND o.payment_value > 0
          AND o.operation_date = NEW.credited_at
          AND o.semantic_hash = NEW.source_semantic_hash
          AND o.observed_at = NEW.source_observed_at
          AND o.operation_date >= m.created_at
          AND o.operation_date < m.expires_at
          AND (
              m.revoked_at IS NULL
              OR o.operation_date < m.revoked_at
          )
          AND (
              (o.operation_type = 'OPERATION_TYPE_DIVIDEND' AND m.allow_dividends)
              OR
              (o.operation_type = 'OPERATION_TYPE_COUPON' AND m.allow_coupons)
          )
    ) THEN
        RAISE EXCEPTION 'reinvestment income credit source is not eligible';
    END IF;
    RETURN NEW;
END;
$omnicio$;

DROP TRIGGER IF EXISTS portfolio_reinvestment_income_credits_guard
    ON portfolio_reinvestment_income_credits;
CREATE TRIGGER portfolio_reinvestment_income_credits_guard
BEFORE INSERT OR UPDATE ON portfolio_reinvestment_income_credits
FOR EACH ROW
EXECUTE FUNCTION omnicio_validate_reinvestment_income_credit();

DROP TRIGGER IF EXISTS portfolio_reinvestment_income_credits_no_delete
    ON portfolio_reinvestment_income_credits;
CREATE TRIGGER portfolio_reinvestment_income_credits_no_delete
BEFORE DELETE ON portfolio_reinvestment_income_credits
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_execution_delete();

COMMIT;
