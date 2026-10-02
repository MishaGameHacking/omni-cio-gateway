BEGIN;

CREATE TABLE IF NOT EXISTS risk_source_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    source_id text NOT NULL,
    scope_key text NOT NULL,
    status text NOT NULL CHECK (
        status IN ('received', 'partial', 'unavailable', 'not_configured')
    ),
    source_url text NOT NULL,
    retrieved_at timestamptz NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_id, source_id, scope_key),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    CONSTRAINT risk_source_runs_source_nonempty CHECK (
        char_length(source_id) BETWEEN 1 AND 128
    ),
    CONSTRAINT risk_source_runs_scope_nonempty CHECK (
        char_length(scope_key) BETWEEN 1 AND 256
    ),
    CONSTRAINT risk_source_runs_url_nonempty CHECK (
        char_length(source_url) BETWEEN 1 AND 2048
    )
);

CREATE INDEX IF NOT EXISTS risk_source_runs_user_retrieved_idx
    ON risk_source_runs (user_id, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS risk_facts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    instrument_uid text NOT NULL,
    asset_uid text NOT NULL DEFAULT '',
    source_id text NOT NULL,
    source_url text NOT NULL,
    fact_kind text NOT NULL,
    fact_key text NOT NULL,
    effective_at timestamptz,
    publication_at timestamptz,
    retrieved_at timestamptz NOT NULL,
    value_json jsonb NOT NULL,
    semantic_hash bytea NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    UNIQUE (
        user_id,
        instrument_uid,
        source_id,
        fact_key,
        semantic_hash
    ),
    CONSTRAINT risk_facts_instrument_nonempty CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    ),
    CONSTRAINT risk_facts_source_nonempty CHECK (
        char_length(source_id) BETWEEN 1 AND 128
    ),
    CONSTRAINT risk_facts_kind_nonempty CHECK (
        char_length(fact_kind) BETWEEN 1 AND 128
    ),
    CONSTRAINT risk_facts_key_nonempty CHECK (
        char_length(fact_key) BETWEEN 1 AND 512
    ),
    CONSTRAINT risk_facts_hash_size CHECK (octet_length(semantic_hash) = 32)
);

CREATE INDEX IF NOT EXISTS risk_facts_user_instrument_idx
    ON risk_facts (user_id, instrument_uid, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS payout_observations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    instrument_uid text NOT NULL,
    event_kind text NOT NULL CHECK (
        event_kind IN ('dividend', 'coupon', 'bond_event')
    ),
    event_key text NOT NULL,
    event_date timestamptz NOT NULL,
    record_date timestamptz,
    declared_at timestamptz,
    provider_payment_at timestamptz,
    amount_value numeric(38, 9),
    amount_currency text,
    status text NOT NULL,
    source_id text NOT NULL,
    source_url text NOT NULL,
    normalized jsonb NOT NULL,
    semantic_hash bytea NOT NULL,
    observed_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    UNIQUE (
        user_id,
        instrument_uid,
        event_kind,
        event_key,
        semantic_hash
    ),
    CONSTRAINT payout_observations_instrument_nonempty CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    ),
    CONSTRAINT payout_observations_event_key_nonempty CHECK (
        char_length(event_key) BETWEEN 1 AND 512
    ),
    CONSTRAINT payout_observations_status_nonempty CHECK (
        char_length(status) BETWEEN 1 AND 128
    ),
    CONSTRAINT payout_observations_hash_size CHECK (
        octet_length(semantic_hash) = 32
    )
);

CREATE INDEX IF NOT EXISTS payout_observations_user_event_idx
    ON payout_observations (user_id, event_date DESC);

CREATE TABLE IF NOT EXISTS risk_assessments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    instrument_uid text NOT NULL,
    ticker text NOT NULL DEFAULT '',
    state text NOT NULL CHECK (
        state IN (
            'data_missing',
            'normal',
            'watch',
            'elevated',
            'critical',
            'confirmed_default'
        )
    ),
    sector_model text NOT NULL,
    coverage text NOT NULL CHECK (coverage IN ('complete', 'partial', 'missing')),
    reasons jsonb NOT NULL,
    evaluated_at timestamptz NOT NULL,
    latest_fundamental_period_end timestamptz,
    latest_report_date timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_id, instrument_uid),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    CONSTRAINT risk_assessments_instrument_nonempty CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    ),
    CONSTRAINT risk_assessments_model_nonempty CHECK (
        char_length(sector_model) BETWEEN 1 AND 128
    )
);

CREATE INDEX IF NOT EXISTS risk_assessments_user_evaluated_idx
    ON risk_assessments (user_id, evaluated_at DESC);

ALTER TABLE risk_source_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_source_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS risk_source_runs_tenant ON risk_source_runs;
CREATE POLICY risk_source_runs_tenant
    ON risk_source_runs
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE risk_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_facts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS risk_facts_tenant ON risk_facts;
CREATE POLICY risk_facts_tenant
    ON risk_facts
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE payout_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE payout_observations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS payout_observations_tenant ON payout_observations;
CREATE POLICY payout_observations_tenant
    ON payout_observations
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS risk_assessments_tenant ON risk_assessments;
CREATE POLICY risk_assessments_tenant
    ON risk_assessments
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
