-- WP22A Phase 2: generalize only the identity/session/broker persistence
-- boundaries required by the accepted public USER model. Historical OWNER-only
-- checks on portfolio/research/decision/job state remain fail-closed until the
-- later hosted private-state phase owns their generalization.

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
    ADD CONSTRAINT user_role_registry CHECK (role IN ('owner', 'user')),
    ADD CONSTRAINT user_owner_role_binding CHECK (
        (
            user_id = 'user:v1:owner' AND
            tenant_id = 'tenant:v1:owner' AND
            role = 'owner'
        ) OR (
            user_id <> 'user:v1:owner' AND
            tenant_id <> 'tenant:v1:owner' AND
            role = 'user'
        )
    ),
    ADD CONSTRAINT users_one_account_per_tenant UNIQUE (tenant_id);

-- Product sessions are a central account-plane relation. They resolve tenant
-- scope from an opaque token hash before a tenant is known, so they deliberately
-- do not use tenant RLS. The user/tenant composite FK remains the database scope
-- binding and plaintext browser tokens are never persisted.
ALTER TABLE omni_cio_v10.web_sessions
    DROP CONSTRAINT web_session_owner_only;

-- Broker state is the first tenant-private relation generalized by WP22A Phase 2.
-- Keep the existing composite scope FKs and add PostgreSQL RLS as a second,
-- database-enforced horizontal isolation boundary. FORCE RLS is intentionally
-- deferred until Phase 3 creates the final least-privilege hosted runtime role;
-- forcing it now would break the still-protected legacy OWNER persistence role.
ALTER TABLE omni_cio_v10.broker_accounts
    DROP CONSTRAINT broker_account_owner_only;
ALTER TABLE omni_cio_v10.broker_connections
    DROP CONSTRAINT broker_connection_owner_only;
ALTER TABLE omni_cio_v10.broker_connection_accounts
    DROP CONSTRAINT broker_connection_accounts_owner_only;

CREATE TABLE omni_cio_v10.external_identity_bindings (
    provider text NOT NULL,
    subject_binding_hmac_sha256 char(64) NOT NULL,
    user_id text NOT NULL,
    tenant_id text NOT NULL,
    linked_at timestamptz NOT NULL,
    last_verified_at timestamptz NOT NULL,
    PRIMARY KEY (provider, subject_binding_hmac_sha256),
    CONSTRAINT external_identity_provider CHECK (
        provider IN ('telegram', 'vk_id')
    ),
    CONSTRAINT external_identity_binding_hmac_sha256 CHECK (
        subject_binding_hmac_sha256 ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT external_identity_product_scope CHECK (
        user_id <> 'user:v1:owner' AND
        tenant_id <> 'tenant:v1:owner'
    ),
    CONSTRAINT external_identity_user_scope_fk
        FOREIGN KEY (user_id, tenant_id)
        REFERENCES omni_cio_v10.users (user_id, tenant_id)
        ON DELETE CASCADE,
    CONSTRAINT external_identity_time_order CHECK (
        last_verified_at >= linked_at
    ),
    CONSTRAINT external_identity_one_provider_per_user UNIQUE (user_id, provider)
);
CREATE INDEX external_identity_user_scope_idx
    ON omni_cio_v10.external_identity_bindings (tenant_id, user_id);

CREATE OR REPLACE FUNCTION omni_cio_v10.current_tenant_scope()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(pg_catalog.current_setting('omni_cio.tenant_id', true), '')
$$;

ALTER TABLE omni_cio_v10.broker_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY broker_accounts_tenant_isolation
    ON omni_cio_v10.broker_accounts
    USING (tenant_id = omni_cio_v10.current_tenant_scope())
    WITH CHECK (tenant_id = omni_cio_v10.current_tenant_scope());

ALTER TABLE omni_cio_v10.broker_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY broker_connections_tenant_isolation
    ON omni_cio_v10.broker_connections
    USING (tenant_id = omni_cio_v10.current_tenant_scope())
    WITH CHECK (tenant_id = omni_cio_v10.current_tenant_scope());

ALTER TABLE omni_cio_v10.broker_connection_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY broker_connection_accounts_tenant_isolation
    ON omni_cio_v10.broker_connection_accounts
    USING (tenant_id = omni_cio_v10.current_tenant_scope())
    WITH CHECK (tenant_id = omni_cio_v10.current_tenant_scope());
