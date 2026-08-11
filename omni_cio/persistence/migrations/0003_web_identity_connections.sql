ALTER TABLE omni_cio_v10.users
    ADD CONSTRAINT users_user_tenant_uq UNIQUE (user_id, tenant_id);

CREATE TABLE omni_cio_v10.web_sessions (
    token_sha256 char(64) PRIMARY KEY,
    user_id text NOT NULL,
    tenant_id text NOT NULL,
    created_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    idle_expires_at timestamptz NOT NULL,
    absolute_expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CONSTRAINT web_session_owner_only CHECK (
        user_id = 'user:v1:owner' AND tenant_id = 'tenant:v1:owner'
    ),
    CONSTRAINT web_session_token_sha256 CHECK (token_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT web_session_user_scope_fk FOREIGN KEY (user_id, tenant_id)
        REFERENCES omni_cio_v10.users (user_id, tenant_id) ON DELETE CASCADE,
    CONSTRAINT web_session_time_order CHECK (
        last_seen_at >= created_at AND
        idle_expires_at > last_seen_at AND
        absolute_expires_at > created_at AND
        absolute_expires_at >= idle_expires_at AND
        (revoked_at IS NULL OR revoked_at >= created_at)
    )
);
CREATE INDEX web_sessions_scope_expiry_idx
    ON omni_cio_v10.web_sessions (tenant_id, user_id, absolute_expires_at);

CREATE TABLE omni_cio_v10.broker_connections (
    connection_id text PRIMARY KEY,
    tenant_id text NOT NULL,
    provider text NOT NULL,
    credential_role text NOT NULL,
    state text NOT NULL,
    secret_ref text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    last_verified_at timestamptz,
    revoked_at timestamptz,
    CONSTRAINT broker_connection_owner_only CHECK (tenant_id = 'tenant:v1:owner'),
    CONSTRAINT broker_connection_id_shape CHECK (
        connection_id ~ '^broker-connection:v1:[a-f0-9]{64}$'
    ),
    CONSTRAINT broker_connection_secret_ref_shape CHECK (
        secret_ref ~ '^read-connection:v1:[a-f0-9]{64}$'
    ),
    CONSTRAINT broker_connection_provider CHECK (provider = 't_invest'),
    CONSTRAINT broker_connection_role CHECK (credential_role = 'read'),
    CONSTRAINT broker_connection_state CHECK (state IN ('ACTIVE', 'REVOKED', 'ERROR')),
    CONSTRAINT broker_connection_tenant_fk FOREIGN KEY (tenant_id)
        REFERENCES omni_cio_v10.tenants (tenant_id) ON DELETE RESTRICT,
    CONSTRAINT broker_connection_time_order CHECK (
        (last_verified_at IS NULL OR last_verified_at >= created_at) AND
        (revoked_at IS NULL OR revoked_at >= created_at)
    ),
    UNIQUE (connection_id, tenant_id)
);
CREATE INDEX broker_connections_scope_state_idx
    ON omni_cio_v10.broker_connections (tenant_id, state, created_at DESC);

CREATE TABLE omni_cio_v10.broker_connection_accounts (
    connection_id text NOT NULL,
    tenant_id text NOT NULL,
    broker_account_id text NOT NULL,
    linked_at timestamptz NOT NULL,
    PRIMARY KEY (connection_id, broker_account_id),
    CONSTRAINT broker_connection_accounts_owner_only CHECK (
        tenant_id = 'tenant:v1:owner'
    ),
    CONSTRAINT broker_connection_accounts_connection_fk
        FOREIGN KEY (connection_id, tenant_id)
        REFERENCES omni_cio_v10.broker_connections (connection_id, tenant_id)
        ON DELETE CASCADE,
    CONSTRAINT broker_connection_accounts_account_fk
        FOREIGN KEY (broker_account_id, tenant_id)
        REFERENCES omni_cio_v10.broker_accounts (broker_account_id, tenant_id)
        ON DELETE RESTRICT
);
CREATE INDEX broker_connection_accounts_scope_idx
    ON omni_cio_v10.broker_connection_accounts (tenant_id, connection_id);
