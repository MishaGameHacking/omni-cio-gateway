-- WP22A Phase 3: source-only object grants for the Cloud.ru-managed API user.
-- Phase 4 creates the login user through the accepted provider boundary with
-- separately injected credentials and no predefined broad PostgreSQL roles.
-- This SQL never creates or alters users and never applies provider resources.

DO $hosted_user$
DECLARE
    runtime_user pg_catalog.pg_roles%ROWTYPE;
BEGIN
    SELECT *
    INTO runtime_user
    FROM pg_catalog.pg_roles
    WHERE rolname = 'omni_cio_hosted_api';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'HOSTED_API_USER_NOT_PROVISIONED'
            USING ERRCODE = '42704';
    END IF;

    IF
        NOT runtime_user.rolcanlogin OR
        runtime_user.rolsuper OR
        runtime_user.rolcreatedb OR
        runtime_user.rolcreaterole OR
        runtime_user.rolreplication OR
        runtime_user.rolbypassrls
    THEN
        RAISE EXCEPTION 'HOSTED_API_USER_ATTRIBUTE_DRIFT'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        WHERE membership.member = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_USER_ROLE_MEMBERSHIP_PRESENT'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_USER_MEMBERS_PRESENT'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_database database_record
        WHERE database_record.datname = pg_catalog.current_database()
        AND database_record.datdba = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_DATABASE_OWNERSHIP_FORBIDDEN'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_namespace schema_record
        WHERE schema_record.nspname = 'omni_cio_v10'
        AND schema_record.nspowner = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_SCHEMA_OWNERSHIP_FORBIDDEN'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class relation_record
        JOIN pg_catalog.pg_namespace schema_record
            ON schema_record.oid = relation_record.relnamespace
        WHERE schema_record.nspname = 'omni_cio_v10'
        AND relation_record.relowner = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_OBJECT_OWNERSHIP_FORBIDDEN'
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_proc function_record
        JOIN pg_catalog.pg_namespace schema_record
            ON schema_record.oid = function_record.pronamespace
        WHERE schema_record.nspname = 'omni_cio_v10'
        AND function_record.proowner = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_OBJECT_OWNERSHIP_FORBIDDEN'
            USING ERRCODE = '42501';
    END IF;
END;
$hosted_user$;

DO $database_privileges$
BEGIN
    EXECUTE pg_catalog.format(
        'REVOKE ALL PRIVILEGES ON DATABASE %I FROM %I',
        pg_catalog.current_database(),
        'omni_cio_hosted_api'
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
