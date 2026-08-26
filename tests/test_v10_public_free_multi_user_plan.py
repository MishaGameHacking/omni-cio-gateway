from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PUBLIC_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md"
)
ROLE_AMENDMENT = (
    ROOT
    / "docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md"
)
CONTRACT = ROOT / "docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json"

LIVE_PRODUCT_AUTHORITY = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "knowledge/00_PROJECT_MASTER_CONTEXT.md",
    ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
    ROOT / "docs/master-plan/README.md",
    ROOT / "docs/master-plan/OMNI_CIO_V10_AMENDMENTS_INDEX.md",
    ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md",
    ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md",
    ROOT / "docs/architecture/V10_WP22_SYSTEM_ADMIN_UI_CONTRACT.md",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_hosted_amendments_and_contract_exist() -> None:
    assert PUBLIC_AMENDMENT.is_file()
    assert ROLE_AMENDMENT.is_file()
    assert CONTRACT.is_file()

    payload = json.loads(_text(CONTRACT))
    product_target = payload["product_target"]
    assert product_target["public_multi_user_target"] is True
    assert product_target["ordinary_browser_global_internet_access"] is True
    assert (
        product_target["internet_connection_required_for_registration_login_product_use"]
        is True
    )
    assert product_target["offline_registration_allowed"] is False
    assert product_target["offline_login_allowed"] is False
    assert product_target["offline_authenticated_product_mode_allowed"] is False
    assert product_target["native_client_required"] is False
    assert product_target["project_owner_is_special_product_role"] is False

    hosting = payload["production_hosting"]
    assert hosting["managed_cloud_origin_required"] is True
    assert hosting["home_public_ip_dependency_allowed"] is False
    assert hosting["home_wifi_dependency_allowed"] is False
    assert hosting["home_router_dependency_allowed"] is False
    assert hosting["owner_lan_dependency_allowed"] is False
    assert hosting["lenovo_as_public_production_origin_allowed"] is False
    assert hosting["owner_home_power_or_internet_may_be_public_sla_dependency"] is False

    access = payload["initial_access_model"]
    assert access == {
        "billing_enabled": False,
        "trial_enabled": False,
        "subscription_enforcement": False,
        "premium_feature_gating": False,
        "payment_method_required_for_registration": False,
        "future_monetization_state": "DEFERRED_OPTIONAL",
    }

    broker = payload["broker_credentials"]
    assert broker["ownership"] == "TENANT_SCOPED_BROKER_CONNECTION"
    assert broker["global_shared_read_token_allowed"] is False
    assert broker["global_shared_trade_token_allowed"] is False
    assert broker["cross_tenant_secret_access_allowed"] is False
    assert broker["cortex_raw_secret_access_allowed"] is False
    assert broker["encrypted_at_rest_required"] is True

    activation = payload["activation"]
    assert activation["implementation_default_public_multi_user_enabled"] is False
    assert activation["target_after_exit_gates_public_multi_user_enabled"] is True
    assert activation["payment_kkt_gate_required_while_billing_disabled"] is False

    safety = payload["safety"]
    assert safety["app_entrypoint"] == "app:app"
    assert safety["trading_methods"] is False
    assert safety["real_trading_enabled"] is False
    assert safety["transfer_withdrawal_allowed"] is False
    assert safety["protected_v9_rollback"] is True
    assert safety["wp23_locked_until_corrected_wp22a_exit_gate"] is True


def test_live_authority_uses_product_auth_not_owner_product_auth() -> None:
    forbidden = "WP22A — External Web Access / OWNER Authentication Security Gate"
    for path in LIVE_PRODUCT_AUTHORITY:
        text = _text(path)
        assert forbidden not in text, path

    for path in (
        ROOT / "AGENTS.md",
        ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md",
        ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md",
    ):
        assert "WP22A — External Web Access / Product Authentication Security Gate" in _text(path)

    readme = _text(ROOT / "README.md")
    assert "product authentication (Telegram Login / VK ID)" in readme
    assert "PROJECT OWNER is an ordinary product USER" in readme


def test_project_owner_is_not_a_product_superuser() -> None:
    role = _text(ROLE_AMENDMENT)
    assert "PROJECT OWNER is not a special Omni-CIO product user" in role
    assert "PROJECT OWNER using Omni-CIO == ordinary USER using Omni-CIO" in role
    assert "engineering authority to operate the service != product authority to read/use a tenant" in role

    agents = _text(ROOT / "AGENTS.md")
    assert "PROJECT OWNER is not a special Omni-CIO product role" in agents
    assert "OmniCIOUserAccount -> Tenant -> Session" in agents


def test_public_product_requires_internet_and_has_no_offline_auth_mode() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    assert "The normal requirement for product use is an Internet connection" in amendment

    contract = json.loads(_text(CONTRACT))
    target = contract["product_target"]
    assert target["internet_connection_required_for_registration_login_product_use"] is True
    assert target["offline_registration_allowed"] is False
    assert target["offline_login_allowed"] is False
    assert target["offline_authenticated_product_mode_allowed"] is False


def test_public_production_cannot_depend_on_owner_home_or_lenovo() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    for marker in (
        "home public IP address",
        "home Wi-Fi",
        "Lenovo laptop as the public production origin",
        "approved managed cloud production runtime",
        "not the public-product availability anchor",
    ):
        assert marker in amendment

    service_selection = _text(ROOT / "docs/architecture/V10_WP22A_SERVICE_SELECTION.md")
    assert "managed-cloud production origin independent of OWNER home infrastructure" in service_selection
    assert "sole production origin is the PROJECT OWNER's home Lenovo/network" in service_selection

    execution = _text(ROOT / "docs/architecture/V10_WP22A_EXECUTION_CONTRACT.md")
    assert "managed-cloud Omni-CIO Web/API" in execution
    assert "must not depend on PROJECT OWNER home public IP" in execution


def test_initial_launch_is_free_but_public_activation_remains_gated() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    for marker in (
        "`BILLING_ENABLED=false`",
        "`TRIAL_ENABLED=false`",
        "`SUBSCRIPTION_ENFORCEMENT=false`",
        "`PREMIUM_FEATURE_GATING=false`",
        "`DEFERRED_OPTIONAL`",
        "`PUBLIC_MULTI_USER_ENABLED=false` remains the safe implementation default",
    ):
        assert marker in amendment

    status = _text(ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md")
    assert (
        "public multi-user activation — **APPROVED TARGET / IMPLEMENTATION FLAG REMAINS OFF UNTIL"
        in status
    )
    assert "`PUBLIC_MULTI_USER_ENABLED=false` remains the safe default" in status
    assert "WP23+ remains locked" in status


def test_broker_credentials_are_tenant_owned_not_global() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    assert "USER -> Tenant -> BrokerConnection -> credential role" in amendment
    assert "There is no application-global READ token" in amendment
    assert "There is no application-global READ token and no application-global TRADE token" in amendment
    assert "credentials are never returned to the browser after submission" in amendment
    assert "credentials are encrypted at rest" in amendment

    readme = _text(ROOT / "README.md")
    assert (
        "USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> "
        "verified broker-account bindings" in readme
    )
    assert "no shared/global user broker token is allowed" in readme

    status = _text(ROOT / "knowledge/17_V10_CURRENT_PROGRAM_STATUS.md")
    assert (
        "Public T-Invest-backed production functionality remains "
        "**FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION**" in status
    )
    assert "tenant READ/optional TRADE credential separation remains mandatory" in status
    assert "broker write OFF" in status
    assert "`REAL_TRADING_ENABLED=false`" in status


def test_t_invest_public_connector_stays_separate_fail_closed_gate() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    assert "public Omni-CIO account/Web activation and public T-Invest connector activation are separate gates" in amendment
    assert "user-supplied tokens do not by themselves waive" in amendment

    contract = json.loads(_text(CONTRACT))
    assert contract["t_invest"]["public_connector_default"] == "FAIL_CLOSED_PENDING_BROKER_TERMS_PERMISSION"
    assert contract["t_invest"]["user_supplied_token_waives_broker_terms"] is False


def test_planning_change_does_not_expand_money_authority() -> None:
    amendment = _text(PUBLIC_AMENDMENT)
    for marker in (
        "`trading_methods=false`",
        "`REAL_TRADING_ENABLED=false`",
        "no transfer/withdrawal authority",
        "no margin/leverage/uncovered short",
        "protected V9 rollback",
    ):
        assert marker in amendment
