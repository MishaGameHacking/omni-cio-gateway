from __future__ import annotations

import copy

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


def test_hosted_postgres_contract_preserves_phase3_authority() -> None:
    payload = _contract()
    validate_hosted_postgres_runtime_contract(payload)

    authority = payload["authority"]
    role = payload["runtime_role"]
    assert isinstance(authority, dict)
    assert isinstance(role, dict)
    assert authority["provider_apply_authorized"] is False
    assert authority["public_database_ingress_allowed"] is False
    assert authority["authorized_recurring_rub"] == 0
    assert authority["public_multi_user_enabled"] is False
    assert authority["trading_methods_enabled"] is False
    assert authority["real_trading_enabled"] is False
    assert authority["protected_v9_entrypoint"] == "app:app"
    assert authority["wp23_unlocked"] is False
    assert role["name"] == "omni_cio_hosted_api"
    assert role["cluster_scoped"] is True
    assert role["login_identity_bound"] is False
    assert role["preexisting_exact_role_reuse_allowed"] is True
    assert role["membership_in_other_roles_allowed"] is False
    assert role["bypass_rls"] is False


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
        "broker_accounts",
        "broker_connections",
        "broker_connection_accounts",
    }
    assert set(privileges).isdisjoint(forbidden)


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


def test_hosted_postgres_bootstrap_reuses_only_exact_cluster_role() -> None:
    source = _bootstrap()
    assert "pg_catalog.pg_roles" in source
    assert "pg_catalog.pg_auth_members" in source
    assert "HOSTED_API_ROLE_ATTRIBUTE_DRIFT" in source
    assert "HOSTED_API_ROLE_MEMBERSHIP_DRIFT" in source
    assert "CREATE ROLE omni_cio_hosted_api" in source
    assert "ALTER ROLE omni_cio_hosted_api" in source


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


def test_hosted_postgres_validator_rejects_login_or_rls_bypass() -> None:
    for unsafe in (
        _bootstrap().replace("NOLOGIN", "LOGIN"),
        _bootstrap().replace("NOBYPASSRLS", "BYPASSRLS"),
    ):
        with pytest.raises(
            HostedPostgresRuntimeContractError,
            match="HOSTED_POSTGRES_SQL_ROLE_OPTION_DRIFT",
        ):
            validate_hosted_postgres_runtime_sql(
                unsafe,
                copy.deepcopy(_contract()),
            )
