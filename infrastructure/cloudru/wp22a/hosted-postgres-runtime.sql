-- WP22A Phase 3: source-only least-privilege hosted API database role.
-- This bootstrap is deliberately outside the ordinary per-database migration
-- series because PostgreSQL roles are cluster-scoped. Phase 4 may execute it
-- only on an accepted hosted database boundary with separately injected login
-- identity. It creates no provider resource, public ingress, or paid service.

DO $hosted_role$
DECLARE
    existing_role pg_catalog.pg_roles%ROWTYPE;
BEGIN
    SELECT *
    INTO existing_role
    FROM pg_catalog.pg_roles
    WHERE rolname = 'omni_cio_hosted_api';

    IF NOT FOUND THEN
        EXECUTE 'CREATE ROLE omni_cio_hosted_api ' ||
            'NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT ' ||
            'NOLOGIN NOREPLICATION NOBYPASSRLS';
    ELSIF
        existing_role.rolsuper OR
        existing_role.rolcreatedb OR
        existing_role.rolcreaterole OR
        existing_role.rolinherit OR
        existing_role.rolcanlogin OR
        existing_role.rolreplication OR
        existing_role.rolbypassrls
    THEN
        RAISE EXCEPTION 'HOSTED_API_ROLE_ATTRIBUTE_DRIFT'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles member_role
            ON member_role.oid = membership.member
        WHERE member_role.rolname = 'omni_cio_hosted_api'
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_ROLE_MEMBERSHIP_DRIFT'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        JOIN pg_catalog.pg_roles granted_role
            ON granted_role.oid = membership.roleid
        WHERE granted_role.rolname = 'omni_cio_hosted_api'
        AND (membership.inherit_option OR membership.set_option)
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_ROLE_MEMBER_AUTHORITY_PRESENT'
            USING ERRCODE = '42501';
    END IF;
END;
$hosted_role$;

ALTER ROLE omni_cio_hosted_api
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOLOGIN
    NOREPLICATION
    NOBYPASSRLS;

DO $database_privileges$
BEGIN
    EXECUTE pg_catalog.format(
        'REVOKE ALL PRIVILEGES ON DATABASE %I FROM omni_cio_hosted_api',
        pg_catalog.current_database()
    );
END;
$database_privileges$;

REVOKE ALL ON ALL TABLES IN SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
REVOKE CREATE ON SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
GRANT USAGE ON SCHEMA omni_cio_v10
    TO omni_cio_hosted_api;
GRANT EXECUTE ON FUNCTION omni_cio_v10.current_tenant_scope()
    TO omni_cio_hosted_api;

GRANT INSERT ON TABLE omni_cio_v10.tenants
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT ON TABLE omni_cio_v10.users
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT ON TABLE omni_cio_v10.external_identity_bindings
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE omni_cio_v10.web_sessions
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT ON TABLE omni_cio_v10.broker_accounts
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT, UPDATE ON TABLE omni_cio_v10.broker_connections
    TO omni_cio_hosted_api;
GRANT SELECT, INSERT ON TABLE omni_cio_v10.broker_connection_accounts
    TO omni_cio_hosted_api;

ALTER TABLE omni_cio_v10.broker_accounts
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE omni_cio_v10.broker_accounts
    FORCE ROW LEVEL SECURITY;
ALTER TABLE omni_cio_v10.broker_connections
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE omni_cio_v10.broker_connections
    FORCE ROW LEVEL SECURITY;
ALTER TABLE omni_cio_v10.broker_connection_accounts
    ENABLE ROW LEVEL SECURITY;
ALTER TABLE omni_cio_v10.broker_connection_accounts
    FORCE ROW LEVEL SECURITY;
