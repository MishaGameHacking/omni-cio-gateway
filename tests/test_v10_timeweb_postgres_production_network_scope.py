from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
from typing import Any

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/timeweb_postgres_production_network_scope.py"
)
SPEC = importlib.util.spec_from_file_location(
    "timeweb_postgres_production_network_scope",
    SCRIPT,
)
assert SPEC is not None
assert SPEC.loader is not None
scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scope)

CIDR = "8.8.8.8/32"
HOST = "prod-db.twc1.net"
PROJECT_ID = "project-1"
DATABASE_ID = "901"
FLOATING_IP_ID = "float-1"
GROUP_ID = "group-1"
GROUP_ID_2 = "group-2"
PAGE = "?limit=100&offset=0"
PROJECT_DATABASES_PATH = f"/api/v1/projects/{PROJECT_ID}/resources/databases"
DATABASE_PATH = f"/api/v1/databases/{DATABASE_ID}"
FLOATING_IPS_PATH = "/api/v1/floating-ips"
FLOATING_IP_DETAIL_PATH = f"{FLOATING_IPS_PATH}/{FLOATING_IP_ID}"
SERVICE_GROUPS_PATH = f"/api/v1/firewall/service/dbaas/{DATABASE_ID}{PAGE}"
FIREWALL_GROUP_PATH = f"/api/v1/firewall/groups/{GROUP_ID}"
FIREWALL_RULES_PATH = f"{FIREWALL_GROUP_PATH}/rules{PAGE}"
FIREWALL_RESOURCES_PATH = f"{FIREWALL_GROUP_PATH}/resources{PAGE}"
FIREWALL_GROUP_PATH_2 = f"/api/v1/firewall/groups/{GROUP_ID_2}"
FIREWALL_RULES_PATH_2 = f"{FIREWALL_GROUP_PATH_2}/rules{PAGE}"
FIREWALL_RESOURCES_PATH_2 = f"{FIREWALL_GROUP_PATH_2}/resources{PAGE}"
DRIFT_IP = "1.1.1.1"
AVAILABILITY_ZONE_KEY = "availability_zone"
RESOURCE_ID_KEY = "resource_id"
CERT_STATUS_KEY = "cert_status"
DBAAS_RESOURCE_TYPE = "dbaas"
DOMAINS_KEY = "domains"
RULES_KEY = "rules"
GROUP_KEY = "group"
RESOURCES_KEY = "resources"
TOTAL_KEY = "total"
FIELD_VALUE_PARAMS = ("field", "value")
FIELD_VALUE_CODE_PARAMS = (*FIELD_VALUE_PARAMS, "code")


class FakeApi:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str, *, timeout: float = 30.0) -> Any:
        del timeout
        self.calls.append(path)
        return self.responses[path]


class DriftingApi(FakeApi):
    def __init__(self, responses: dict[str, Any]) -> None:
        super().__init__(responses)
        self._drifted = False

    def get(self, path: str, *, timeout: float = 30.0) -> Any:
        value = deepcopy(super().get(path, timeout=timeout))
        if path == FLOATING_IPS_PATH and self.calls.count(path) == 2:
            self._drifted = True
        if self._drifted and path == FLOATING_IPS_PATH:
            value["ips"][0]["ip"] = DRIFT_IP
        if self._drifted and path == FLOATING_IP_DETAIL_PATH:
            value["ip"]["ip"] = DRIFT_IP
        return value


class ReorderingFirewallApi(FakeApi):
    def get(self, path: str, *, timeout: float = 30.0) -> Any:
        value = deepcopy(super().get(path, timeout=timeout))
        if path == SERVICE_GROUPS_PATH and self.calls.count(path) == 2:
            value["groups"].reverse()
        if path == FIREWALL_RULES_PATH and self.calls.count(path) == 2:
            value[RULES_KEY].reverse()
        return value


def _page(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {key: rows, "meta": {TOTAL_KEY: len(rows)}}


def _floating_ip_row() -> dict[str, Any]:
    return {
        "id": FLOATING_IP_ID,
        "ip": "8.8.4.4",
        AVAILABILITY_ZONE_KEY: "msk-1",
        "is_ddos_guard": False,
        "resource_type": DBAAS_RESOURCE_TYPE,
        RESOURCE_ID_KEY: DATABASE_ID,
        "comment": "",
    }


def _responses() -> dict[str, Any]:
    floating_ip = _floating_ip_row()
    return {
        PROJECT_DATABASES_PATH: {"databases": [{"id": DATABASE_ID}]},
        DATABASE_PATH: {
            "db": {
                "id": DATABASE_ID,
                "name": "omni-cio-v10-production",
                "status": "started",
                "port": 5432,
                AVAILABILITY_ZONE_KEY: "msk-1",
                "project_id": PROJECT_ID,
                "is_enabled_public_network": True,
                "is_enabled_public_ipv6": False,
                "is_secure_connection_enabled": True,
                DOMAINS_KEY: [{"fqdn": HOST, CERT_STATUS_KEY: "issued"}],
            }
        },
        FLOATING_IPS_PATH: _page("ips", [floating_ip]),
        FLOATING_IP_DETAIL_PATH: {
            "ip": dict(floating_ip),
        },
        SERVICE_GROUPS_PATH: _page(
            "groups",
            [{"id": GROUP_ID}],
        ),
        FIREWALL_GROUP_PATH: {GROUP_KEY: {"id": GROUP_ID, "policy": "DROP"}},
        FIREWALL_RULES_PATH: _page(
            RULES_KEY,
            [
                {
                    "id": "rule-1",
                    "direction": "ingress",
                    "protocol": "tcp",
                    "port": "5432",
                    "cidr": CIDR,
                }
            ],
        ),
        FIREWALL_RESOURCES_PATH: _page(
            RESOURCES_KEY,
            [{"id": DATABASE_ID, "type": DBAAS_RESOURCE_TYPE}],
        ),
    }


def _verify(responses: dict[str, Any]) -> FakeApi:
    api = FakeApi(responses)
    scope.verify_network_scope(
        api,
        project_id=PROJECT_ID,
        target_host=HOST,
        verifier_cidr=CIDR,
    )
    return api


def test_hostname_accepts_dotted_ascii_fqdn() -> None:
    assert scope._hostname(HOST) == HOST


@pytest.mark.parametrize(
    "hostname",
    [
        "localhost",
        r"prod-db\.twc1.net",
        "prod-db..twc1.net",
        "-prod.twc1.net",
        "prod-.twc1.net",
    ],
)
def test_hostname_rejects_non_fqdn_shapes(hostname: str) -> None:
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_HOST_INVALID",
    ):
        scope._hostname(hostname)


def test_accepts_exact_fail_closed_network_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    api = _verify(_responses())
    output = capsys.readouterr().out
    assert "TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=READY" in output
    assert HOST not in output
    assert CIDR not in output
    assert DATABASE_ID not in output
    assert GROUP_ID not in output
    assert "8.8.4.4" not in output
    assert api.calls.count(FLOATING_IPS_PATH) == 2


def test_rejects_provider_snapshot_drift_between_valid_passes() -> None:
    api = DriftingApi(_responses())
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_SNAPSHOT_DRIFT",
    ):
        scope.verify_network_scope(
            api,
            project_id=PROJECT_ID,
            target_host=HOST,
            verifier_cidr=CIDR,
        )


def test_rejects_malformed_domain_entry_even_with_exact_target() -> None:
    responses = _responses()
    domains = responses[DATABASE_PATH]["db"][DOMAINS_KEY]
    domains.append({"fqdn": None, CERT_STATUS_KEY: "issued"})
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_DOMAINS_INVALID",
    ):
        _verify(responses)


@pytest.mark.parametrize(
    FIELD_VALUE_CODE_PARAMS,
    [
        ("status", "starting", "TIMEWEB_PG_PRODUCTION_NETWORK_CLUSTER_NOT_READY"),
        ("port", 5433, "TIMEWEB_PG_PRODUCTION_NETWORK_PORT_DRIFT"),
        (
            "is_enabled_public_network",
            False,
            "TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_DISABLED",
        ),
        (
            "is_enabled_public_ipv6",
            True,
            "TIMEWEB_PG_PRODUCTION_PUBLIC_IPV6_FORBIDDEN",
        ),
        (
            "is_secure_connection_enabled",
            False,
            "TIMEWEB_PG_PRODUCTION_TLS_NOT_READY",
        ),
    ],
)
def test_rejects_unready_cluster_state(field: str, value: object, code: str) -> None:
    responses = _responses()
    responses[DATABASE_PATH]["db"][field] = value
    with pytest.raises(scope.NetworkScopeStopped, match=code):
        _verify(responses)


def test_rejects_synthetic_cluster() -> None:
    responses = _responses()
    responses[DATABASE_PATH]["db"]["name"] = scope.SYNTHETIC_CLUSTER_NAME
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_SYNTHETIC_TARGET_FORBIDDEN",
    ):
        _verify(responses)


def test_rejects_unissued_target_certificate() -> None:
    responses = _responses()
    responses[DATABASE_PATH]["db"][DOMAINS_KEY][0][CERT_STATUS_KEY] = "pending"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_TLS_CERTIFICATE_NOT_READY",
    ):
        _verify(responses)


def test_rejects_target_domain_not_found() -> None:
    responses = _responses()
    responses[DATABASE_PATH]["db"][DOMAINS_KEY][0]["fqdn"] = "different.twc1.net"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_TARGET_NOT_FOUND",
    ):
        _verify(responses)


def test_rejects_database_project_identity_drift() -> None:
    responses = _responses()
    responses[DATABASE_PATH]["db"]["project_id"] = "project-2"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_PROJECT_DRIFT",
    ):
        _verify(responses)


def test_rejects_public_ipv4_zone_mismatch() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["ips"][0][AVAILABILITY_ZONE_KEY] = "spb-1"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_INVALID",
    ):
        _verify(responses)


def test_rejects_floating_ipv4_list_detail_drift() -> None:
    responses = _responses()
    responses[FLOATING_IP_DETAIL_PATH]["ip"]["ip"] = DRIFT_IP
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FLOATING_IP_LIST_DETAIL_DRIFT",
    ):
        _verify(responses)


def test_rejects_malformed_database_binding_state() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["ips"][0][RESOURCE_ID_KEY] = True
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FLOATING_IP_RESOURCE_ID_INVALID",
    ):
        _verify(responses)


def test_rejects_malformed_bound_public_ipv4_id() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["ips"][0]["id"] = True
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FLOATING_IP_ID_INVALID",
    ):
        _verify(responses)


def test_rejects_missing_bound_public_ipv4() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["ips"][0][RESOURCE_ID_KEY] = "902"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_MISSING",
    ):
        _verify(responses)


def test_rejects_multiple_bound_public_ipv4s() -> None:
    responses = _responses()
    duplicate = dict(responses[FLOATING_IPS_PATH]["ips"][0])
    duplicate["id"] = "float-2"
    duplicate["ip"] = DRIFT_IP
    responses[FLOATING_IPS_PATH]["ips"].append(duplicate)
    responses[FLOATING_IPS_PATH]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_NOT_UNIQUE",
    ):
        _verify(responses)


@pytest.mark.parametrize(
    FIELD_VALUE_PARAMS,
    [
        ("ip", "10.0.0.1"),
        ("is_ddos_guard", True),
    ],
)
def test_rejects_invalid_bound_public_ipv4(field: str, value: object) -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["ips"][0][field] = value
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_INVALID",
    ):
        _verify(responses)


def test_rejects_boolean_meta_total() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["meta"][TOTAL_KEY] = True
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FLOATING_IP_INVENTORY_INVALID",
    ):
        _verify(responses)


def test_rejects_incomplete_floating_ip_inventory() -> None:
    responses = _responses()
    responses[FLOATING_IPS_PATH]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FLOATING_IP_INVENTORY_INVALID_INCOMPLETE",
    ):
        _verify(responses)


def _add_second_firewall_group(
    responses: dict[str, Any],
    *,
    cidr: str = CIDR,
    include_rule: bool = True,
) -> None:
    responses[SERVICE_GROUPS_PATH]["groups"].append({"id": GROUP_ID_2})
    responses[SERVICE_GROUPS_PATH]["meta"][TOTAL_KEY] = 2
    responses[FIREWALL_GROUP_PATH_2] = {GROUP_KEY: {"id": GROUP_ID_2, "policy": "DROP"}}
    rules = []
    if include_rule:
        rules.append(
            {
                "id": "rule-2",
                "direction": "ingress",
                "protocol": "tcp",
                "port": "5432",
                "cidr": cidr,
            }
        )
    responses[FIREWALL_RULES_PATH_2] = _page(RULES_KEY, rules)
    responses[FIREWALL_RESOURCES_PATH_2] = _page(
        RESOURCES_KEY,
        [{"id": DATABASE_ID, "type": DBAAS_RESOURCE_TYPE}],
    )


def test_accepts_multiple_equivalent_firewall_groups() -> None:
    responses = _responses()
    _add_second_firewall_group(responses)

    api = _verify(responses)

    assert api.calls.count(FIREWALL_GROUP_PATH_2) == 2
    assert api.calls.count(FIREWALL_RULES_PATH_2) == 2
    assert api.calls.count(FIREWALL_RESOURCES_PATH_2) == 2


def test_accepts_provider_group_and_rule_reordering() -> None:
    responses = _responses()
    _add_second_firewall_group(responses)
    responses[FIREWALL_RULES_PATH][RULES_KEY].append(
        {
            "id": "rule-3",
            "direction": "ingress",
            "protocol": "tcp",
            "port": "5432",
            "cidr": CIDR,
        }
    )
    responses[FIREWALL_RULES_PATH]["meta"][TOTAL_KEY] = 2
    api = ReorderingFirewallApi(responses)

    scope.verify_network_scope(
        api,
        project_id=PROJECT_ID,
        target_host=HOST,
        verifier_cidr=CIDR,
    )


def test_accepts_empty_same_type_group_when_effective_union_stays_exact() -> None:
    responses = _responses()
    _add_second_firewall_group(responses, include_rule=False)

    _verify(responses)


def test_rejects_multiple_firewall_groups_when_effective_scope_widens() -> None:
    responses = _responses()
    _add_second_firewall_group(responses, cidr="1.1.1.1/32")

    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_DRIFT",
    ):
        _verify(responses)


def test_rejects_non_drop_policy_on_second_firewall_group() -> None:
    responses = _responses()
    _add_second_firewall_group(responses)
    responses[FIREWALL_GROUP_PATH_2][GROUP_KEY]["policy"] = "ACCEPT"

    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_DEFAULT_DROP_REQUIRED",
    ):
        _verify(responses)


def test_rejects_extra_resource_on_second_firewall_group() -> None:
    responses = _responses()
    _add_second_firewall_group(responses)
    responses[FIREWALL_RESOURCES_PATH_2][RESOURCES_KEY].append(
        {"id": "902", "type": DBAAS_RESOURCE_TYPE}
    )
    responses[FIREWALL_RESOURCES_PATH_2]["meta"][TOTAL_KEY] = 2

    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED",
    ):
        _verify(responses)


def test_rejects_missing_effective_firewall_rule() -> None:
    responses = _responses()
    responses[FIREWALL_RULES_PATH] = _page(RULES_KEY, [])
    _add_second_firewall_group(responses, include_rule=False)

    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_EFFECTIVE_RULE_MISSING",
    ):
        _verify(responses)


def test_rejects_duplicate_firewall_group_identity() -> None:
    responses = _responses()
    responses[SERVICE_GROUPS_PATH]["groups"].append({"id": GROUP_ID})
    responses[SERVICE_GROUPS_PATH]["meta"][TOTAL_KEY] = 2

    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_ID_DUPLICATE",
    ):
        _verify(responses)


def test_rejects_truncated_firewall_group_page() -> None:
    responses = _responses()
    path = SERVICE_GROUPS_PATH
    responses[path]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match=(
            "TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUPS_INVALID_PAGINATION_INCOMPLETE"
        ),
    ):
        _verify(responses)


def test_rejects_firewall_group_identity_drift() -> None:
    responses = _responses()
    responses[FIREWALL_GROUP_PATH][GROUP_KEY]["id"] = "group-2"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_DRIFT",
    ):
        _verify(responses)


def test_rejects_allow_default_policy() -> None:
    responses = _responses()
    responses[FIREWALL_GROUP_PATH][GROUP_KEY]["policy"] = "ACCEPT"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_DEFAULT_DROP_REQUIRED",
    ):
        _verify(responses)


def test_rejects_verifier_cidr_drift() -> None:
    responses = _responses()
    path = FIREWALL_RULES_PATH
    responses[path][RULES_KEY][0]["cidr"] = "1.1.1.1/32"
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_DRIFT",
    ):
        _verify(responses)


def test_rejects_malformed_firewall_rule_id() -> None:
    responses = _responses()
    path = FIREWALL_RULES_PATH
    responses[path][RULES_KEY][0]["id"] = True
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RULE_ID_INVALID",
    ):
        _verify(responses)


@pytest.mark.parametrize(
    FIELD_VALUE_PARAMS,
    [("direction", "egress"), ("protocol", "udp"), ("port", "5433")],
)
def test_rejects_widened_or_wrong_rule(field: str, value: str) -> None:
    responses = _responses()
    path = FIREWALL_RULES_PATH
    responses[path][RULES_KEY][0][field] = value
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RULESET_WIDENED",
    ):
        _verify(responses)


def test_accepts_duplicate_semantic_rule_across_groups() -> None:
    responses = _responses()
    _add_second_firewall_group(responses)

    _verify(responses)


def test_rejects_truncated_firewall_rule_page() -> None:
    responses = _responses()
    path = FIREWALL_RULES_PATH
    responses[path]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RULES_INVALID_PAGINATION_INCOMPLETE",
    ):
        _verify(responses)


def test_rejects_malformed_firewall_resource_id() -> None:
    responses = _responses()
    path = FIREWALL_RESOURCES_PATH
    responses[path][RESOURCES_KEY][0]["id"] = True
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_ID_INVALID",
    ):
        _verify(responses)


def test_rejects_extra_firewall_resource() -> None:
    responses = _responses()
    path = FIREWALL_RESOURCES_PATH
    responses[path][RESOURCES_KEY].append({"id": "902", "type": DBAAS_RESOURCE_TYPE})
    responses[path]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED",
    ):
        _verify(responses)


def test_rejects_truncated_firewall_resource_page() -> None:
    responses = _responses()
    path = FIREWALL_RESOURCES_PATH
    responses[path]["meta"][TOTAL_KEY] = 2
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCES_INVALID_PAGINATION_INCOMPLETE",
    ):
        _verify(responses)


@pytest.mark.parametrize(
    "cidr",
    ["0.0.0.0/0", "10.0.0.1/32", "8.8.8.0/24", "8.8.8.8", "::1/128"],
)
def test_rejects_non_exact_global_ipv4_32(cidr: str) -> None:
    api = FakeApi(_responses())
    with pytest.raises(
        scope.NetworkScopeStopped,
        match="TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_INVALID",
    ):
        scope.verify_network_scope(
            api,
            project_id=PROJECT_ID,
            target_host=HOST,
            verifier_cidr=cidr,
        )
