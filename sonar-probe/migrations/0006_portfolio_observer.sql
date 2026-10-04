BEGIN;

CREATE TABLE IF NOT EXISTS instrument_catalog (
    provider text NOT NULL,
    instrument_uid text NOT NULL,
    figi text NOT NULL DEFAULT '',
    asset_uid text NOT NULL DEFAULT '',
    position_uid text NOT NULL DEFAULT '',
    ticker text NOT NULL DEFAULT '',
    name text NOT NULL DEFAULT '',
    isin text NOT NULL DEFAULT '',
    instrument_type text NOT NULL,
    currency text NOT NULL DEFAULT '',
    class_code text NOT NULL DEFAULT '',
    lot integer NOT NULL DEFAULT 0 CHECK (lot >= 0),
    sector text NOT NULL DEFAULT '',
    country_of_risk text NOT NULL DEFAULT '',
    for_qual_investor boolean,
    for_iis boolean,
    api_trade_available boolean,
    buy_available boolean,
    sell_available boolean,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    provider_retrieved_at timestamptz NOT NULL,
    PRIMARY KEY (provider, instrument_uid),
    CONSTRAINT instrument_catalog_uid_nonempty CHECK (char_length(instrument_uid) BETWEEN 1 AND 128)
);

CREATE INDEX IF NOT EXISTS instrument_catalog_isin_idx
    ON instrument_catalog (isin)
    WHERE isin <> '';

CREATE INDEX IF NOT EXISTS instrument_catalog_ticker_idx
    ON instrument_catalog (ticker)
    WHERE ticker <> '';

CREATE TABLE IF NOT EXISTS account_instrument_access (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id text NOT NULL,
    provider text NOT NULL,
    instrument_uid text NOT NULL,
    required_tests jsonb NOT NULL DEFAULT '[]'::jsonb,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (user_id, account_id, provider, instrument_uid),
    FOREIGN KEY (provider, instrument_uid)
        REFERENCES instrument_catalog(provider, instrument_uid)
        ON DELETE CASCADE,
    CONSTRAINT account_instrument_access_account_nonempty CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    )
);

CREATE INDEX IF NOT EXISTS account_instrument_access_user_account_idx
    ON account_instrument_access (user_id, account_id);

CREATE TABLE IF NOT EXISTS issuer_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name text NOT NULL,
    source_url text NOT NULL,
    effective_at timestamptz,
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT issuer_groups_name_nonempty CHECK (char_length(canonical_name) BETWEEN 1 AND 512),
    CONSTRAINT issuer_groups_source_nonempty CHECK (char_length(source_url) BETWEEN 1 AND 2048)
);

CREATE TABLE IF NOT EXISTS issuers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    legal_name text NOT NULL,
    country_code text,
    registration_id text,
    group_id uuid REFERENCES issuer_groups(id) ON DELETE SET NULL,
    source_url text NOT NULL,
    effective_at timestamptz,
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT issuers_legal_name_nonempty CHECK (char_length(legal_name) BETWEEN 1 AND 512),
    CONSTRAINT issuers_source_nonempty CHECK (char_length(source_url) BETWEEN 1 AND 2048)
);

CREATE TABLE IF NOT EXISTS instrument_issuer_map (
    provider text NOT NULL,
    instrument_uid text NOT NULL,
    issuer_id uuid NOT NULL REFERENCES issuers(id) ON DELETE RESTRICT,
    source_url text NOT NULL,
    effective_at timestamptz,
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, instrument_uid),
    FOREIGN KEY (provider, instrument_uid)
        REFERENCES instrument_catalog(provider, instrument_uid)
        ON DELETE CASCADE,
    CONSTRAINT instrument_issuer_map_source_nonempty CHECK (char_length(source_url) BETWEEN 1 AND 2048)
);

CREATE TABLE IF NOT EXISTS investment_profile_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    reserve_rub numeric(24, 8) NOT NULL CHECK (reserve_rub >= 0),
    planned_withdrawal_rub numeric(24, 8) NOT NULL CHECK (planned_withdrawal_rub >= 0),
    horizon_months integer NOT NULL CHECK (horizon_months BETWEEN 1 AND 1200),
    max_drawdown_percent numeric(7, 4) NOT NULL CHECK (
        max_drawdown_percent >= 0 AND max_drawdown_percent <= 100
    ),
    liquidity_horizon_days integer NOT NULL CHECK (liquidity_horizon_days BETWEEN 0 AND 36500),
    allow_below_investment_grade boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, version)
);

CREATE TABLE IF NOT EXISTS job_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_type text NOT NULL,
    scheduled_for date NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'succeeded', 'degraded', 'failed')),
    attempt integer NOT NULL DEFAULT 1 CHECK (attempt > 0),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (user_id, job_type, scheduled_for),
    CONSTRAINT job_runs_type_nonempty CHECK (char_length(job_type) BETWEEN 1 AND 128),
    CONSTRAINT job_runs_finish_state_consistent CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS job_runs_user_started_idx
    ON job_runs (user_id, started_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_run_id uuid REFERENCES job_runs(id) ON DELETE SET NULL,
    account_id text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('prod', 'sandbox')),
    captured_at timestamptz NOT NULL,
    analysis_status text NOT NULL CHECK (
        analysis_status IN ('observed', 'partial', 'needs_reconciliation')
    ),
    nav_rub numeric(24, 8) NOT NULL,
    rub_cash_total numeric(24, 8) NOT NULL,
    rub_cash_blocked numeric(24, 8) NOT NULL,
    rub_cash_unblocked numeric(24, 8),
    limits_loading_in_progress boolean NOT NULL,
    evidence jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    UNIQUE (job_run_id),
    CONSTRAINT portfolio_snapshots_account_nonempty CHECK (char_length(account_id) BETWEEN 1 AND 128)
);

CREATE INDEX IF NOT EXISTS portfolio_snapshots_user_captured_idx
    ON portfolio_snapshots (user_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_snapshot_positions (
    snapshot_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instrument_uid text NOT NULL,
    figi text NOT NULL DEFAULT '',
    ticker text NOT NULL DEFAULT '',
    instrument_type text NOT NULL,
    quantity numeric(38, 9) NOT NULL,
    current_price_value numeric(24, 9),
    current_price_currency text,
    current_nkd_value numeric(24, 9),
    current_nkd_currency text,
    blocked boolean NOT NULL,
    blocked_lots numeric(38, 9) NOT NULL,
    value_rub numeric(24, 8),
    nav_percent numeric(12, 8),
    sector text NOT NULL DEFAULT '',
    country_of_risk text NOT NULL DEFAULT '',
    for_qual_investor boolean,
    PRIMARY KEY (snapshot_id, instrument_uid),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    CONSTRAINT portfolio_snapshot_positions_uid_nonempty CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    )
);

CREATE INDEX IF NOT EXISTS portfolio_snapshot_positions_user_uid_idx
    ON portfolio_snapshot_positions (user_id, instrument_uid);

CREATE TABLE IF NOT EXISTS operation_observations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id text NOT NULL,
    observation_hash bytea NOT NULL,
    semantic_hash bytea NOT NULL,
    provider_operation_id text NOT NULL DEFAULT '',
    provider_cursor text NOT NULL DEFAULT '',
    operation_date timestamptz NOT NULL,
    operation_type text NOT NULL,
    operation_state text NOT NULL,
    instrument_uid text NOT NULL DEFAULT '',
    figi text NOT NULL DEFAULT '',
    instrument_type text NOT NULL DEFAULT '',
    payment_value numeric(24, 9),
    payment_currency text,
    price_value numeric(24, 9),
    price_currency text,
    commission_value numeric(24, 9),
    commission_currency text,
    accrued_int_value numeric(24, 9),
    accrued_int_currency text,
    quantity numeric(38, 9),
    quantity_rest numeric(38, 9),
    quantity_done numeric(38, 9),
    normalized jsonb NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, account_id, observation_hash),
    CONSTRAINT operation_observations_account_nonempty CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    ),
    CONSTRAINT operation_observations_hash_size CHECK (
        octet_length(observation_hash) = 32 AND octet_length(semantic_hash) = 32
    )
);

CREATE INDEX IF NOT EXISTS operation_observations_user_date_idx
    ON operation_observations (user_id, operation_date DESC);

CREATE UNIQUE INDEX IF NOT EXISTS operation_observations_semantic_unique_idx
    ON operation_observations (user_id, account_id, semantic_hash);

CREATE TABLE IF NOT EXISTS broker_sync_state (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id text NOT NULL,
    history_window_from timestamptz,
    history_window_to timestamptz,
    pending_cursor text,
    last_complete_watermark timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, account_id),
    CONSTRAINT broker_sync_state_account_nonempty CHECK (char_length(account_id) BETWEEN 1 AND 128),
    CONSTRAINT broker_sync_state_cursor_window_consistent CHECK (
        (
            pending_cursor IS NULL
            AND history_window_from IS NULL
            AND history_window_to IS NULL
        )
        OR (
            pending_cursor IS NOT NULL
            AND history_window_from IS NOT NULL
            AND history_window_to IS NOT NULL
            AND history_window_from <= history_window_to
        )
    )
);

ALTER TABLE account_instrument_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_instrument_access FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS account_instrument_access_tenant ON account_instrument_access;
CREATE POLICY account_instrument_access_tenant
    ON account_instrument_access
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE investment_profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_profile_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS investment_profile_versions_tenant ON investment_profile_versions;
CREATE POLICY investment_profile_versions_tenant
    ON investment_profile_versions
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE job_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS job_runs_tenant ON job_runs;
CREATE POLICY job_runs_tenant
    ON job_runs
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_snapshots_tenant ON portfolio_snapshots;
CREATE POLICY portfolio_snapshots_tenant
    ON portfolio_snapshots
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE portfolio_snapshot_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshot_positions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_snapshot_positions_tenant ON portfolio_snapshot_positions;
CREATE POLICY portfolio_snapshot_positions_tenant
    ON portfolio_snapshot_positions
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE operation_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_observations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS operation_observations_tenant ON operation_observations;
CREATE POLICY operation_observations_tenant
    ON operation_observations
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE broker_sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE broker_sync_state FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS broker_sync_state_tenant ON broker_sync_state;
CREATE POLICY broker_sync_state_tenant
    ON broker_sync_state
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
