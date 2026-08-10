ALTER TABLE omni_cio_v10.jobs
    ADD COLUMN state text,
    ADD COLUMN correlation_id text,
    ADD COLUMN lease_owner text,
    ADD COLUMN lease_expires_at timestamptz,
    ADD COLUMN heartbeat_at timestamptz,
    ADD COLUMN attempts integer,
    ADD COLUMN max_attempts integer,
    ADD COLUMN next_run_at timestamptz,
    ADD COLUMN started_at timestamptz,
    ADD COLUMN completed_at timestamptz,
    ADD COLUMN error_class text,
    ADD COLUMN recovery_policy text;

UPDATE omni_cio_v10.jobs
SET
    state = 'QUEUED',
    correlation_id = job_id,
    attempts = 0,
    max_attempts = 3,
    next_run_at = created_at,
    recovery_policy = 'RETRY_SAFE';

ALTER TABLE omni_cio_v10.jobs
    ALTER COLUMN state SET NOT NULL,
    ALTER COLUMN state SET DEFAULT 'QUEUED',
    ALTER COLUMN correlation_id SET NOT NULL,
    ALTER COLUMN attempts SET NOT NULL,
    ALTER COLUMN attempts SET DEFAULT 0,
    ALTER COLUMN max_attempts SET NOT NULL,
    ALTER COLUMN max_attempts SET DEFAULT 3,
    ALTER COLUMN recovery_policy SET NOT NULL,
    ALTER COLUMN recovery_policy SET DEFAULT 'RETRY_SAFE';

ALTER TABLE omni_cio_v10.jobs
    ADD CONSTRAINT job_type_registry CHECK (job_type IN (
        'PORTFOLIO_REFRESH',
        'MARKET_REFRESH',
        'RESEARCH',
        'WATCHTOWER',
        'AI_RESEARCH',
        'RECONCILIATION',
        'BACKUP',
        'HEALTH'
    )),
    ADD CONSTRAINT job_state_registry CHECK (state IN (
        'QUEUED',
        'RUNNING',
        'RETRY_WAIT',
        'SUCCEEDED',
        'FAILED_PERMANENT',
        'RECONCILIATION_REQUIRED',
        'CANCELLED'
    )),
    ADD CONSTRAINT job_attempt_bounds CHECK (
        attempts >= 0 AND max_attempts >= 1 AND max_attempts <= 100 AND attempts <= max_attempts
    ),
    ADD CONSTRAINT job_recovery_policy CHECK (
        recovery_policy IN ('RETRY_SAFE', 'RECONCILE')
    ),
    ADD CONSTRAINT job_error_class_registry CHECK (
        error_class IS NULL OR error_class IN (
            'RETRYABLE',
            'RETRY_EXHAUSTED',
            'PERMANENT',
            'VALIDATION',
            'AMBIGUOUS',
            'LEASE_EXPIRED',
            'LEASE_EXPIRED_ATTEMPTS_EXHAUSTED'
        )
    ),
    ADD CONSTRAINT job_lease_shape CHECK (
        (
            state = 'RUNNING'
            AND lease_owner IS NOT NULL
            AND lease_expires_at IS NOT NULL
            AND heartbeat_at IS NOT NULL
            AND started_at IS NOT NULL
            AND completed_at IS NULL
        )
        OR
        (
            state <> 'RUNNING'
            AND lease_owner IS NULL
            AND lease_expires_at IS NULL
            AND heartbeat_at IS NULL
        )
    ),
    ADD CONSTRAINT job_schedule_shape CHECK (
        (
            state IN ('QUEUED', 'RETRY_WAIT')
            AND next_run_at IS NOT NULL
            AND completed_at IS NULL
        )
        OR
        (
            state = 'RUNNING'
            AND next_run_at IS NULL
            AND completed_at IS NULL
        )
        OR
        (
            state IN ('SUCCEEDED', 'FAILED_PERMANENT', 'RECONCILIATION_REQUIRED', 'CANCELLED')
            AND next_run_at IS NULL
            AND completed_at IS NOT NULL
        )
    ),
    ADD CONSTRAINT job_lease_time_order CHECK (
        lease_expires_at IS NULL OR heartbeat_at IS NULL OR lease_expires_at > heartbeat_at
    );

CREATE INDEX jobs_due_claim_idx
    ON omni_cio_v10.jobs (tenant_id, next_run_at, created_at, job_id)
    WHERE state IN ('QUEUED', 'RETRY_WAIT');

CREATE INDEX jobs_expired_lease_idx
    ON omni_cio_v10.jobs (tenant_id, lease_expires_at, job_id)
    WHERE state = 'RUNNING';

CREATE INDEX jobs_correlation_idx
    ON omni_cio_v10.jobs (tenant_id, correlation_id, created_at DESC);

CREATE TABLE omni_cio_v10.job_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id text NOT NULL,
    tenant_id text NOT NULL,
    event_type text NOT NULL,
    from_state text,
    to_state text NOT NULL,
    attempt integer NOT NULL,
    worker_id text,
    error_class text,
    occurred_at timestamptz NOT NULL,
    record_sha256 char(64) NOT NULL,
    CONSTRAINT job_event_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT job_event_parent_fk FOREIGN KEY (job_id)
        REFERENCES omni_cio_v10.jobs (job_id) ON DELETE RESTRICT,
    CONSTRAINT job_event_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT job_event_type_registry CHECK (event_type IN (
        'SCHEDULED',
        'CLAIMED',
        'HEARTBEAT',
        'SUCCEEDED',
        'RETRY_SCHEDULED',
        'FAILED_PERMANENT',
        'RECONCILIATION_REQUIRED',
        'LEASE_RECOVERED',
        'CANCELLED'
    )),
    CONSTRAINT job_event_from_state_registry CHECK (
        from_state IS NULL OR from_state IN (
            'QUEUED',
            'RUNNING',
            'RETRY_WAIT',
            'SUCCEEDED',
            'FAILED_PERMANENT',
            'RECONCILIATION_REQUIRED',
            'CANCELLED'
        )
    ),
    CONSTRAINT job_event_to_state_registry CHECK (to_state IN (
        'QUEUED',
        'RUNNING',
        'RETRY_WAIT',
        'SUCCEEDED',
        'FAILED_PERMANENT',
        'RECONCILIATION_REQUIRED',
        'CANCELLED'
    )),
    CONSTRAINT job_event_attempt_nonnegative CHECK (attempt >= 0),
    CONSTRAINT job_event_error_class_registry CHECK (
        error_class IS NULL OR error_class IN (
            'RETRYABLE',
            'RETRY_EXHAUSTED',
            'PERMANENT',
            'VALIDATION',
            'AMBIGUOUS',
            'LEASE_EXPIRED',
            'LEASE_EXPIRED_ATTEMPTS_EXHAUSTED'
        )
    ),
    CONSTRAINT job_event_record_sha256 CHECK (record_sha256 ~ '^[a-f0-9]{64}$')
);

CREATE INDEX job_events_job_time_idx
    ON omni_cio_v10.job_events (job_id, event_id);

CREATE INDEX job_events_scope_time_idx
    ON omni_cio_v10.job_events (tenant_id, occurred_at DESC, event_id DESC);

CREATE TRIGGER job_events_reject_mutation
BEFORE UPDATE OR DELETE ON omni_cio_v10.job_events
FOR EACH ROW EXECUTE FUNCTION omni_cio_v10.reject_immutable_mutation();