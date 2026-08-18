ALTER TABLE omni_cio_v10.tenants
    DROP CONSTRAINT owner_tenant_only,
    ADD CONSTRAINT tenant_id_shape CHECK (
        tenant_id ~ '^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$'
    ),
    ADD CONSTRAINT tenant_mode_registry CHECK (
        mode IN ('owner_personal', 'product_user')
    ),
    ADD CONSTRAINT tenant_owner_mode_binding CHECK (
        (tenant_id = 'tenant:v1:owner' AND mode = 'owner_personal') OR
        (tenant_id <> 'tenant:v1:owner' AND mode = 'product_user')
    );

ALTER TABLE omni_cio_v10.users
    DROP CONSTRAINT owner_user_only,
    DROP CONSTRAINT owner_user_tenant_only,
    ADD CONSTRAINT user_id_shape CHECK (
        user_id ~ '^user:v1:[a-z0-9][a-z0-9_-]{2,63}$'
    ),
    ADD CONSTRAINT user_role_registry CHECK (
        role IN ('owner', 'user')
    ),
    ADD CONSTRAINT user_owner_role_binding CHECK (
        (
            user_id = 'user:v1:owner'
            AND tenant_id = 'tenant:v1:owner'
            AND role = 'owner'
        ) OR (
            user_id <> 'user:v1:owner'
            AND tenant_id <> 'tenant:v1:owner'
            AND role = 'user'
        )
    ),
    ADD CONSTRAINT users_one_account_per_tenant_uq UNIQUE (tenant_id);

ALTER TABLE omni_cio_v10.broker_accounts
    DROP CONSTRAINT broker_account_owner_only;

ALTER TABLE omni_cio_v10.web_sessions
    DROP CONSTRAINT web_session_owner_only;

ALTER TABLE omni_cio_v10.broker_connections
    DROP CONSTRAINT broker_connection_owner_only;

ALTER TABLE omni_cio_v10.broker_connection_accounts
    DROP CONSTRAINT broker_connection_accounts_owner_only;

CREATE TABLE omni_cio_v10.external_identity_bindings (
    provider text NOT NULL,
    subject_binding_sha256 char(64) NOT NULL,
    binding_key_version integer NOT NULL,
    user_id text NOT NULL,
    tenant_id text NOT NULL,
    linked_at timestamptz NOT NULL,
    last_verified_at timestamptz NOT NULL,
    PRIMARY KEY (provider, subject_binding_sha256),
    CONSTRAINT external_identity_provider CHECK (
        provider IN ('telegram', 'vk_id')
    ),
    CONSTRAINT external_identity_binding_sha256 CHECK (
        subject_binding_sha256 ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT external_identity_key_version_positive CHECK (
        binding_key_version > 0
    ),
    CONSTRAINT external_identity_time_order CHECK (
        last_verified_at >= linked_at
    ),
    CONSTRAINT external_identity_user_scope_fk
        FOREIGN KEY (user_id, tenant_id)
        REFERENCES omni_cio_v10.users (user_id, tenant_id)
        ON DELETE CASCADE,
    CONSTRAINT external_identity_user_provider_uq
        UNIQUE (user_id, provider)
);

CREATE INDEX external_identity_scope_idx
    ON omni_cio_v10.external_identity_bindings (tenant_id, user_id, provider);
