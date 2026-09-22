-- V10 provider-neutral PostgreSQL 18 runtime object grants.
-- A provider adapter creates or rotates the least-privilege login separately with
-- injected credentials and no predefined broad PostgreSQL roles.
-- Run this idempotent bootstrap after migrations and after every later migration.
-- This SQL never creates or alters users and never applies provider resources.

DO $hosted_user$
DECLARE
    runtime_user pg_catalog.pg_roles%ROWTYPE;
    bootstrap_user_oid oid;
    runtime_member_count bigint;
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

    -- The runtime role itself must never inherit from or SET ROLE to any other
    -- role. This is the effective-authority boundary used by the application.
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        WHERE membership.member = runtime_user.oid
    ) THEN
        RAISE EXCEPTION 'HOSTED_API_USER_ROLE_MEMBERSHIP_PRESENT'
            USING ERRCODE = '42501';
    END IF;

    -- PostgreSQL 18 gives a non-superuser CREATEROLE creator one administrative
    -- membership back to a role it creates. The system grant is ADMIN only and
    -- deliberately has INHERIT=FALSE and SET=FALSE, so it does not let the
    -- bootstrap login exercise runtime privileges. Accept only that exact edge
    -- to the current bootstrap login; reject every wider/member relationship.
    SELECT oid
    INTO bootstrap_user_oid
    FROM pg_catalog.pg_roles
    WHERE rolname = current_user;

    SELECT count(*)
    INTO runtime_member_count
    FROM pg_catalog.pg_auth_members membership
    WHERE membership.roleid = runtime_user.oid;

    IF runtime_member_count > 1 OR EXISTS (
        SELECT 1
        FROM pg_catalog.pg_auth_members membership
        WHERE membership.roleid = runtime_user.oid
        AND (
            membership.member <> bootstrap_user_oid OR
            NOT membership.admin_option OR
            membership.inherit_option OR
            membership.set_option
        )
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
        'REVOKE CREATE, TEMPORARY ON DATABASE %I FROM PUBLIC',
        pg_catalog.current_database()
    );
    EXECUTE pg_catalog.format(
        'REVOKE ALL PRIVILEGES ON DATABASE %I FROM %I',
        pg_catalog.current_database(),
        'omni_cio_hosted_api'
    );
    EXECUTE pg_catalog.format(
        'GRANT CONNECT ON DATABASE %I TO %I',
        pg_catalog.current_database(),
        'omni_cio_hosted_api'
    );
END;
$database_privileges$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA omni_cio_v10 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA omni_cio_v10 FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA omni_cio_v10 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA omni_cio_v10 FROM PUBLIC;

REVOKE ALL ON SCHEMA omni_cio_v10 FROM omni_cio_hosted_api;
REVOKE ALL ON ALL TABLES IN SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA omni_cio_v10
    FROM omni_cio_hosted_api;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA omni_cio_v10
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
GRANT SELECT, INSERT, DELETE ON TABLE omni_cio_v10.provider_auth_transactions
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
