CREATE SCHEMA IF NOT EXISTS omni_cio_v10;

CREATE OR REPLACE FUNCTION omni_cio_v10.reject_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable relation % rejects %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = '55000';
END;
$$;

CREATE TABLE omni_cio_v10.tenants (
    tenant_id text PRIMARY KEY,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    mode text NOT NULL,
    created_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT owner_tenant_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT tenant_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE omni_cio_v10.users (
    user_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    role text NOT NULL,
    created_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT owner_user_only CHECK (user_id = 'user:v1:owner'),
    CONSTRAINT owner_user_tenant_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT users_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT user_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE omni_cio_v10.broker_accounts (
    broker_account_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    provider text NOT NULL,
    account_fingerprint_sha256 char(64) NOT NULL,
    masked_label text NOT NULL,
    created_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT broker_account_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT broker_account_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT broker_fingerprint_sha256 CHECK (account_fingerprint_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT broker_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT broker_masked_label CHECK (
        position('*' in masked_label) > 0 OR
        position('x' in lower(masked_label)) > 0 OR
        position('•' in masked_label) > 0 OR
        position('…' in masked_label) > 0
    ),
    UNIQUE (broker_account_id, tenant_id)
);

CREATE TABLE omni_cio_v10.portfolios (
    portfolio_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    broker_account_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    base_currency char(3) NOT NULL,
    created_at timestamptz NOT NULL,
    label text,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT portfolio_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT portfolio_account_fk FOREIGN KEY (broker_account_id, tenant_id)
        REFERENCES omni_cio_v10.broker_accounts (broker_account_id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT portfolio_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (portfolio_id, tenant_id)
);

CREATE TABLE omni_cio_v10.instruments (
    instrument_id text PRIMARY KEY,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    primary_identity_kind text NOT NULL,
    broker_uid text,
    figi text,
    isin text,
    class_code text,
    ticker text,
    name text,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT instrument_primary_kind CHECK (primary_identity_kind IN ('broker_uid', 'figi', 'isin')),
    CONSTRAINT instrument_requires_strong_identity CHECK (
        broker_uid IS NOT NULL OR figi IS NOT NULL OR isin IS NOT NULL
    ),
    CONSTRAINT instrument_ticker_class_pair CHECK ((ticker IS NULL) = (class_code IS NULL)),
    CONSTRAINT instrument_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);
CREATE UNIQUE INDEX instrument_broker_uid_uq ON omni_cio_v10.instruments (broker_uid) WHERE broker_uid IS NOT NULL;
CREATE UNIQUE INDEX instrument_figi_uq ON omni_cio_v10.instruments (figi) WHERE figi IS NOT NULL;
CREATE UNIQUE INDEX instrument_isin_uq ON omni_cio_v10.instruments (isin) WHERE isin IS NOT NULL;
CREATE UNIQUE INDEX instrument_ticker_class_uq ON omni_cio_v10.instruments (ticker, class_code)
    WHERE ticker IS NOT NULL AND class_code IS NOT NULL;

CREATE TABLE omni_cio_v10.policies (
    policy_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    source_policy_id text NOT NULL,
    source_policy_sha256 char(64) NOT NULL,
    effective_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT policy_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT policy_portfolio_fk FOREIGN KEY (portfolio_id, tenant_id)
        REFERENCES omni_cio_v10.portfolios (portfolio_id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT policy_source_sha256 CHECK (source_policy_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT policy_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (policy_id, tenant_id, portfolio_id)
);

CREATE TABLE omni_cio_v10.portfolio_snapshots (
    snapshot_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    broker_account_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    source_payload_sha256 char(64) NOT NULL,
    broker_server_at timestamptz,
    local_received_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT snapshot_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT snapshot_policy_fk FOREIGN KEY (policy_id, tenant_id, portfolio_id)
        REFERENCES omni_cio_v10.policies (policy_id, tenant_id, portfolio_id) ON DELETE RESTRICT,
    CONSTRAINT snapshot_account_fk FOREIGN KEY (broker_account_id, tenant_id)
        REFERENCES omni_cio_v10.broker_accounts (broker_account_id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT snapshot_source_sha256 CHECK (source_payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT snapshot_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (snapshot_id, tenant_id, portfolio_id, policy_id)
);
CREATE INDEX portfolio_snapshots_portfolio_time_idx
    ON omni_cio_v10.portfolio_snapshots (tenant_id, portfolio_id, local_received_at DESC);

CREATE TABLE omni_cio_v10.positions (
    position_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    snapshot_id text NOT NULL,
    instrument_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    quantity numeric(38,18) NOT NULL,
    blocked_quantity numeric(38,18) NOT NULL DEFAULT 0,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT position_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT position_nonnegative CHECK (quantity >= 0 AND blocked_quantity >= 0 AND blocked_quantity <= quantity),
    CONSTRAINT position_snapshot_fk FOREIGN KEY (snapshot_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.portfolio_snapshots (snapshot_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT position_instrument_fk FOREIGN KEY (instrument_id)
        REFERENCES omni_cio_v10.instruments (instrument_id) ON DELETE RESTRICT,
    CONSTRAINT position_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (snapshot_id, instrument_id)
);
CREATE INDEX positions_portfolio_snapshot_idx
    ON omni_cio_v10.positions (tenant_id, portfolio_id, snapshot_id);

CREATE TABLE omni_cio_v10.evidence (
    evidence_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    instrument_id text,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    source_kind text NOT NULL,
    payload_sha256 char(64) NOT NULL,
    published_at timestamptz,
    retrieved_at timestamptz NOT NULL,
    broker_server_at timestamptz,
    local_received_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT evidence_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT evidence_policy_fk FOREIGN KEY (policy_id, tenant_id, portfolio_id)
        REFERENCES omni_cio_v10.policies (policy_id, tenant_id, portfolio_id) ON DELETE RESTRICT,
    CONSTRAINT evidence_instrument_fk FOREIGN KEY (instrument_id)
        REFERENCES omni_cio_v10.instruments (instrument_id) ON DELETE RESTRICT,
    CONSTRAINT evidence_source_kind CHECK (source_kind IN ('broker', 'exchange', 'regulator', 'issuer', 'research', 'system')),
    CONSTRAINT evidence_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT evidence_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (evidence_id, tenant_id, portfolio_id, policy_id)
);
CREATE INDEX evidence_scope_retrieved_idx
    ON omni_cio_v10.evidence (tenant_id, portfolio_id, retrieved_at DESC);
CREATE INDEX evidence_instrument_retrieved_idx
    ON omni_cio_v10.evidence (instrument_id, retrieved_at DESC) WHERE instrument_id IS NOT NULL;

CREATE TABLE omni_cio_v10.incidents (
    incident_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    opened_at timestamptz NOT NULL,
    identity_sha256 char(64) NOT NULL,
    CONSTRAINT incident_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT incident_policy_fk FOREIGN KEY (policy_id, tenant_id, portfolio_id)
        REFERENCES omni_cio_v10.policies (policy_id, tenant_id, portfolio_id) ON DELETE RESTRICT,
    CONSTRAINT incident_identity_sha256 CHECK (identity_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (incident_id, tenant_id, portfolio_id, policy_id)
);

CREATE TABLE omni_cio_v10.incident_revisions (
    incident_id text NOT NULL,
    revision bigint NOT NULL,
    status text NOT NULL,
    revised_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    PRIMARY KEY (incident_id, revision),
    CONSTRAINT incident_revision_parent_fk FOREIGN KEY (incident_id)
        REFERENCES omni_cio_v10.incidents (incident_id) ON DELETE RESTRICT,
    CONSTRAINT incident_revision_positive CHECK (revision > 0),
    CONSTRAINT incident_revision_status CHECK (status IN ('open', 'acknowledged', 'closed')),
    CONSTRAINT incident_revision_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);
CREATE UNIQUE INDEX incident_revision_record_uq
    ON omni_cio_v10.incident_revisions (incident_id, record_sha256);

CREATE TABLE omni_cio_v10.incident_evidence (
    incident_id text NOT NULL,
    incident_revision bigint NOT NULL,
    evidence_id text NOT NULL,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    PRIMARY KEY (incident_id, incident_revision, evidence_id),
    CONSTRAINT incident_evidence_revision_fk FOREIGN KEY (incident_id, incident_revision)
        REFERENCES omni_cio_v10.incident_revisions (incident_id, revision) ON DELETE RESTRICT,
    CONSTRAINT incident_evidence_incident_scope_fk FOREIGN KEY (incident_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.incidents (incident_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT incident_evidence_evidence_scope_fk FOREIGN KEY (evidence_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.evidence (evidence_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT
);

CREATE TABLE omni_cio_v10.decisions (
    decision_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    snapshot_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    payload_sha256 char(64) NOT NULL,
    decided_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT decision_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT decision_snapshot_fk FOREIGN KEY (snapshot_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.portfolio_snapshots (snapshot_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT decision_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT decision_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (decision_id, tenant_id, portfolio_id, policy_id),
    UNIQUE (decision_id, tenant_id, portfolio_id, policy_id, snapshot_id)
);

CREATE TABLE omni_cio_v10.decision_evidence (
    decision_id text NOT NULL,
    evidence_id text NOT NULL,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    PRIMARY KEY (decision_id, evidence_id),
    CONSTRAINT decision_evidence_decision_scope_fk FOREIGN KEY (decision_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.decisions (decision_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT decision_evidence_evidence_scope_fk FOREIGN KEY (evidence_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.evidence (evidence_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT
);

CREATE TABLE omni_cio_v10.plans (
    plan_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    snapshot_id text NOT NULL,
    decision_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    payload_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT plan_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT plan_decision_fk FOREIGN KEY (decision_id, tenant_id, portfolio_id, policy_id, snapshot_id)
        REFERENCES omni_cio_v10.decisions (decision_id, tenant_id, portfolio_id, policy_id, snapshot_id) ON DELETE RESTRICT,
    CONSTRAINT plan_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT plan_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (plan_id, tenant_id, portfolio_id, policy_id),
    UNIQUE (plan_id, tenant_id, portfolio_id, policy_id, snapshot_id)
);

CREATE TABLE omni_cio_v10.executions (
    execution_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    snapshot_id text NOT NULL,
    plan_id text NOT NULL,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    payload_sha256 char(64) NOT NULL,
    recorded_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT execution_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT execution_plan_fk FOREIGN KEY (plan_id, tenant_id, portfolio_id, policy_id, snapshot_id)
        REFERENCES omni_cio_v10.plans (plan_id, tenant_id, portfolio_id, policy_id, snapshot_id) ON DELETE RESTRICT,
    CONSTRAINT execution_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT execution_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (execution_id, tenant_id, portfolio_id, policy_id)
);

CREATE TABLE omni_cio_v10.journal (
    journal_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text NOT NULL,
    policy_id text NOT NULL,
    decision_id text,
    plan_id text,
    execution_id text,
    incident_id text,
    schema_version text NOT NULL,
    identity_version integer NOT NULL,
    payload_sha256 char(64) NOT NULL,
    recorded_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT journal_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT journal_policy_fk FOREIGN KEY (policy_id, tenant_id, portfolio_id)
        REFERENCES omni_cio_v10.policies (policy_id, tenant_id, portfolio_id) ON DELETE RESTRICT,
    CONSTRAINT journal_decision_fk FOREIGN KEY (decision_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.decisions (decision_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT journal_plan_fk FOREIGN KEY (plan_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.plans (plan_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT journal_execution_fk FOREIGN KEY (execution_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.executions (execution_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT journal_incident_fk FOREIGN KEY (incident_id, tenant_id, portfolio_id, policy_id)
        REFERENCES omni_cio_v10.incidents (incident_id, tenant_id, portfolio_id, policy_id) ON DELETE RESTRICT,
    CONSTRAINT journal_subject_required CHECK (
        decision_id IS NOT NULL OR plan_id IS NOT NULL OR execution_id IS NOT NULL OR incident_id IS NOT NULL
    ),
    CONSTRAINT journal_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT journal_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);
CREATE INDEX journal_scope_time_idx ON omni_cio_v10.journal (tenant_id, portfolio_id, recorded_at DESC);

CREATE TABLE omni_cio_v10.research_cache (
    cache_key text PRIMARY KEY,
    tenant_id text NOT NULL,
    portfolio_id text,
    instrument_id text,
    source_identity text NOT NULL,
    content_sha256 char(64) NOT NULL,
    published_at timestamptz,
    retrieved_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT research_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT research_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT research_portfolio_fk FOREIGN KEY (portfolio_id, tenant_id)
        REFERENCES omni_cio_v10.portfolios (portfolio_id, tenant_id) ON DELETE RESTRICT,
    CONSTRAINT research_instrument_fk FOREIGN KEY (instrument_id)
        REFERENCES omni_cio_v10.instruments (instrument_id) ON DELETE RESTRICT,
    CONSTRAINT research_content_sha256 CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT research_expiry_order CHECK (expires_at >= retrieved_at)
);
CREATE INDEX research_cache_expiry_idx ON omni_cio_v10.research_cache (expires_at);
CREATE INDEX research_cache_instrument_time_idx
    ON omni_cio_v10.research_cache (instrument_id, retrieved_at DESC) WHERE instrument_id IS NOT NULL;

CREATE TABLE omni_cio_v10.jobs (
    job_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    job_type text NOT NULL,
    idempotency_key text NOT NULL,
    payload_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT job_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT job_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT job_payload_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (tenant_id, job_type, idempotency_key)
);
CREATE INDEX jobs_created_idx ON omni_cio_v10.jobs (tenant_id, created_at DESC);

CREATE TABLE omni_cio_v10.system_health (
    observation_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    component text NOT NULL,
    status text NOT NULL,
    details_sha256 char(64) NOT NULL,
    observed_at timestamptz NOT NULL,
    CONSTRAINT health_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT health_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT health_status CHECK (status IN (
        'READY', 'PARTIAL', 'STALE', 'DEGRADED', 'BLOCKED', 'ERROR',
        'OFFLINE', 'RECOVERING', 'OWNER_ACTION_REQUIRED'
    )),
    CONSTRAINT health_details_sha256 CHECK (details_sha256 ~ '^[a-f0-9]{64}$')
);
CREATE INDEX system_health_component_time_idx
    ON omni_cio_v10.system_health (tenant_id, component, observed_at DESC);

CREATE TABLE omni_cio_v10.content_blobs (
    tenant_id text NOT NULL,
    payload_sha256 char(64) NOT NULL,
    media_type text NOT NULL,
    schema_ref text,
    payload bytea NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, payload_sha256),
    CONSTRAINT content_blob_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT content_blob_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT content_blob_sha256 CHECK (payload_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE TABLE omni_cio_v10.state_revisions (
    revision bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL,
    catalog_sha256 char(64) NOT NULL,
    generated_at timestamptz NOT NULL,
    persisted_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    CONSTRAINT state_revision_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT state_revision_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT state_revision_catalog_sha256 CHECK (catalog_sha256 ~ '^[a-f0-9]{64}$'),
    UNIQUE (tenant_id, catalog_sha256)
);

DO $$
DECLARE
    relation_name text;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'tenants', 'users', 'broker_accounts', 'portfolios', 'instruments',
        'policies', 'portfolio_snapshots', 'positions', 'evidence', 'incidents',
        'incident_revisions', 'incident_evidence', 'decisions', 'decision_evidence',
        'plans', 'executions', 'journal', 'content_blobs', 'state_revisions'
    ]
    LOOP
        EXECUTE format(
            'CREATE TRIGGER %I_reject_mutation BEFORE UPDATE OR DELETE ON omni_cio_v10.%I FOR EACH ROW EXECUTE FUNCTION omni_cio_v10.reject_immutable_mutation()',
            relation_name,
            relation_name
        );
    END LOOP;
END;
$$;
