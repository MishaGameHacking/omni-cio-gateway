from __future__ import annotations

import pytest

from omni_cio.persistence.hosted_postgres_runtime_v1 import (
    BOOTSTRAP_PATH,
    CONTRACT_PATH,
    HostedPostgresRuntimeContractError,
    load_hosted_postgres_runtime_contract,
    validate_hosted_postgres_runtime_contract,
    validate_hosted_postgres_runtime_sql,
)


def _contract() -> dict[str, object]:
    return load_hosted_postgres_runtime_contract(CONTRACT_PATH)


def _bootstrap() -> str:
    return BOOTSTRAP_PATH.read_text(encoding="utf-8")


def test_hosted_postgres_contract_is_provider_neutral_and_fail_closed() -> None:
    payload = _contract()
    validate_hosted_postgres_runtime_contract(payload)

    authority = payload["authority"]
    provider_user = payload["provider_user"]
    bootstrap = payload["bootstrap"]
    assert isinstance(authority, dict)
    assert isinstance(provider_user, dict)
    assert isinstance(bootstrap, dict)
    assert authority["provider"] == "PROVIDER_NEUTRAL_POSTGRESQL_18"
    assert authority["provider_apply_authorized"] is False
    assert authority["public_database_ingress_allowed"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False
    assert provider_user["name"] == "omni_cio_hosted_api"
    assert provider_user["resource_type"] == "postgresql_runtime_login"
    assert provider_user["provisioning_phase"] == "PROVIDER_ADAPTER"
    assert provider_user["source_bootstrap_creates_user"] is False
    assert provider_user["login_required"] is True
    assert provider_user["credential_delivery"] == "external_non_source"
    assert provider_user["credential_value_in_source_allowed"] is False
    assert provider_user["predefined_roles"] == []
    assert provider_user["database_owner"] is False
    assert provider_user["schema_owner"] is False
    assert provider_user["object_owner"] is False
    assert provider_user["bypass_rls"] is False
    assert bootstrap["provider_user_must_preexist"] is True
    assert bootstrap["run_after_migrations"] is True
    assert bootstrap["reapply_after_every_migration"] is True


def test_hosted_postgres_contract_paths_are_provider_neutral() -> None:
    assert "infrastructure/postgres" in CONTRACT_PATH.as_posix()
    assert "infrastructure/postgres" in BOOTSTRAP_PATH.as_posix()
    assert "cloudru" not in CONTRACT_PATH.as_posix().lower()
    assert "cloudru" not in BOOTSTRAP_PATH.as_posix().lower()


def test_hosted_postgres_bootstrap_matches_exact_dml_matrix() -> None:
    validate_hosted_postgres_runtime_sql(_bootstrap(), _contract())

    payload = _contract()
    privileges = payload["relation_privileges"]
    forbidden = payload["forbidden_relations"]
    assert isinstance(privileges, dict)
    assert isinstance(forbidden, list)
    assert set(privileges) == {
        "tenants",
        "users",
        "external_identity_bindings",
        "web_sessions",
        "provider_auth_transactions",
        "broker_accounts",
        "broker_connections",
        "broker_connection_accounts",
    }
    assert set(privileges).isdisjoint(forbidden)
    assert payload["database_privileges"] == ["CONNECT"]
    assert payload["function_privileges"] == {
        "current_tenant_scope()": ["EXECUTE"]
    }


def test_hosted_postgres_bootstrap_forces_tenant_broker_rls() -> None:
    source = _bootstrap()
    payload = _contract()
    rls = payload["rls"]
    assert isinstance(rls, dict)
    assert rls["tenant_setting"] == "omni_cio.tenant_id"
    assert rls["transaction_local_required"] is True
    assert rls["unscoped_default_deny"] is True

    for relation in rls["forced_relations"]:
        qualified = f"ALTER TABLE omni_cio_v10.{relation}"
        assert source.count(qualified) == 2
        assert "FORCE ROW LEVEL SECURITY" in source


def test_hosted_postgres_bootstrap_checks_provider_user_and_ownership() -> None:
    source = _bootstrap()
    assert "pg_catalog.pg_roles" in source
    assert "pg_catalog.pg_auth_members" in source
    assert "HOSTED_API_USER_NOT_PROVISIONED" in source
    assert "HOSTED_API_USER_ATTRIBUTE_DRIFT" in source
    assert "HOSTED_API_USER_ROLE_MEMBERSHIP_PRESENT" in source
    assert "HOSTED_API_USER_MEMBERS_PRESENT" in source
    assert "HOSTED_API_DATABASE_OWNERSHIP_FORBIDDEN" in source
    assert "HOSTED_API_SCHEMA_OWNERSHIP_FORBIDDEN" in source
    assert "HOSTED_API_OBJECT_OWNERSHIP_FORBIDDEN" in source
    assert "CREATE ROLE" not in source
    assert "CREATE USER" not in source
    assert "ALTER ROLE" not in source
    assert "ALTER USER" not in source


def test_hosted_postgres_bootstrap_accepts_only_pg18_creator_admin_edge() -> None:
    source = _bootstrap()
    assert "runtime_member_count > 1" in source
    assert "membership.roleid = runtime_user.oid" in source
    assert "membership.member <> bootstrap_user_oid" in source
    assert "NOT membership.admin_option" in source
    assert "membership.inherit_option" in source
    assert "membership.set_option" in source
    assert "rolname = current_user" in source

    # Runtime authority is still stricter in the opposite direction: the
    # application login itself cannot be a member of any other role.
    assert "membership.member = runtime_user.oid" in source


def test_hosted_postgres_bootstrap_removes_public_privilege_paths() -> None:
    source = _bootstrap()
    for required in (
        "REVOKE CREATE, TEMPORARY ON DATABASE",
        "GRANT CONNECT ON DATABASE",
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        "REVOKE ALL ON SCHEMA omni_cio_v10 FROM PUBLIC",
        "REVOKE ALL ON ALL TABLES IN SCHEMA omni_cio_v10 FROM PUBLIC",
        "REVOKE ALL ON ALL SEQUENCES IN SCHEMA omni_cio_v10 FROM PUBLIC",
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA omni_cio_v10 FROM PUBLIC",
    ):
        assert required in source
    assert "GRANT EXECUTE ON FUNCTION" in source


def test_hosted_postgres_validator_rejects_unrelated_table_grant() -> None:
    unsafe = (
        _bootstrap()
        + "\nGRANT SELECT ON TABLE omni_cio_v10.portfolios "
        + "TO omni_cio_hosted_api;\n"
    )
    with pytest.raises(
        HostedPostgresRuntimeContractError,
        match="HOSTED_POSTGRES_SQL_GRANT_UNEXPECTED",
    ):
        validate_hosted_postgres_runtime_sql(unsafe, _contract())


def test_hosted_postgres_validator_requires_public_function_revoke() -> None:
    unsafe = _bootstrap().replace(
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA omni_cio_v10 FROM PUBLIC;\n",
        "",
    )
    with pytest.raises(
        HostedPostgresRuntimeContractError,
        match="HOSTED_POSTGRES_SQL_SAFETY_MARKER_MISSING",
    ):
        validate_hosted_postgres_runtime_sql(unsafe, _contract())


def test_hosted_postgres_validator_rejects_provider_or_broad_role_mutation() -> None:
    unsafe_inputs = (
        (
            _bootstrap() + "\nCREATE USER extra_login;\n",
            "HOSTED_POSTGRES_SQL_PROVIDER_USER_MANAGEMENT_FORBIDDEN",
        ),
        (
            _bootstrap()
            + "\nGRANT pg_read_all_data TO omni_cio_hosted_api;\n",
            "HOSTED_POSTGRES_SQL_BROAD_ROLE_GRANT",
        ),
        (
            _bootstrap()
            + "\nGRANT TEMPORARY ON DATABASE example TO omni_cio_hosted_api;\n",
            "HOSTED_POSTGRES_SQL_GRANT_UNEXPECTED",
        ),
    )
    for unsafe, expected in unsafe_inputs:
        with pytest.raises(HostedPostgresRuntimeContractError, match=expected):
            validate_hosted_postgres_runtime_sql(unsafe, _contract())
