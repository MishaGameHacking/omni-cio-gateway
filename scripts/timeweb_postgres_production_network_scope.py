from __future__ import annotations

import ipaddress
import re
import sys
from typing import Any, NoReturn, Protocol


TOKEN_ENV = "TIMEWEB_CLOUD_API_TOKEN"
BOOTSTRAP_DSN_ENV = "OMNI_V10_TIMEWEB_PROD_BOOTSTRAP_DSN"
VERIFIER_CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"
POSTGRES_PORT = "5432"
SYNTHETIC_CLUSTER_NAME = "omni-cio-v10-ru-pg-synthetic"
_VERIFIER_CIDR_INVALID = "TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_INVALID"
_PAGE_SIZE = 100
_MAX_PAGES = 10
_MAX_DATABASES = 1000
_MAX_DOMAINS = 32
_NETWORK_SCOPE_STABILITY_PASSES = 2
_FIREWALL_RESOURCE_TYPES = frozenset({"dbaas", "database"})
_HOST_LABEL_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.ASCII,
)
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,96}$", re.ASCII)


class NetworkScopeStopped(RuntimeError):
    pass


class ReadOnlyApi(Protocol):
    def get(self, path: str, *, timeout: float = 30.0) -> Any: ...


def _stop(code: str) -> NoReturn:
    raise NetworkScopeStopped(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _stop(code)
    return value


def _list(value: object, code: str) -> list[Any]:
    if not isinstance(value, list):
        _stop(code)
    return value


def _meta_total(body: dict[str, Any], code: str) -> int:
    meta = _mapping(body.get("meta"), code)
    total = meta.get("total")
    if type(total) is not int or total < 0:
        _stop(code)
    return total


def _rows(value: object, key: str, code: str) -> list[dict[str, Any]]:
    body = _mapping(value, code)
    raw = _list(body.get(key), code)
    if "meta" in body and _meta_total(body, code) != len(raw):
        _stop(f"{code}_INCOMPLETE")
    return [_mapping(item, code) for item in raw]


def _paged_rows(
    api: ReadOnlyApi,
    path: str,
    key: str,
    code: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expected_total: int | None = None
    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        payload = _mapping(
            api.get(f"{path}?limit={_PAGE_SIZE}&offset={offset}"),
            code,
        )
        page_rows = [_mapping(item, code) for item in _list(payload.get(key), code)]
        total = _meta_total(payload, code)
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            _stop(f"{code}_PAGINATION_DRIFT")
        if len(page_rows) > _PAGE_SIZE or len(rows) + len(page_rows) > total:
            _stop(f"{code}_PAGINATION_INVALID")
        rows.extend(page_rows)
        if len(rows) == total:
            return rows
        if not page_rows or len(page_rows) < _PAGE_SIZE:
            _stop(f"{code}_PAGINATION_INCOMPLETE")
    _stop(f"{code}_PAGINATION_INCOMPLETE")


def _safe_id(value: object, code: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        _stop(code)
    text = str(value).strip()
    if not text or _ID_RE.fullmatch(text) is None:
        _stop(code)
    return text


def _hostname(value: object) -> str:
    if not isinstance(value, str):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_HOST_INVALID")
    host = value.strip().lower().rstrip(".")
    labels = host.split(".")
    if (
        len(host) > 253
        or len(labels) < 2
        or any(_HOST_LABEL_RE.fullmatch(label) is None for label in labels)
    ):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_HOST_INVALID")
    return host


def _verifier_cidr(value: object) -> str:
    if not isinstance(value, str):
        _stop(_VERIFIER_CIDR_INVALID)
    raw = value.strip()
    try:
        network = ipaddress.ip_network(raw, strict=True)
    except ValueError:
        _stop(_VERIFIER_CIDR_INVALID)
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or network.prefixlen != 32
        or raw != str(network)
        or not network.network_address.is_global
    ):
        _stop(_VERIFIER_CIDR_INVALID)
    return str(network)


def _database_ids(api: ReadOnlyApi, project_id: str) -> tuple[str, ...]:
    safe_project_id = _safe_id(
        project_id,
        "TIMEWEB_PG_PRODUCTION_NETWORK_PROJECT_ID_INVALID",
    )
    rows = _rows(
        api.get(f"/api/v1/projects/{safe_project_id}/resources/databases"),
        "databases",
        "TIMEWEB_PG_PRODUCTION_NETWORK_DATABASES_INVALID",
    )
    if len(rows) > _MAX_DATABASES:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DATABASES_OVER_LIMIT")
    identifiers = tuple(
        _safe_id(row.get("id"), "TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_ID_INVALID")
        for row in rows
    )
    if len(set(identifiers)) != len(identifiers):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_ID_DUPLICATE")
    return identifiers


def _cluster(api: ReadOnlyApi, database_id: str) -> dict[str, Any]:
    payload = _mapping(
        api.get(f"/api/v1/databases/{database_id}"),
        "TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_INVALID",
    )
    cluster = _mapping(
        payload.get("db"),
        "TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_INVALID",
    )
    if (
        _safe_id(
            cluster.get("id"),
            "TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_ID_INVALID",
        )
        != database_id
    ):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DATABASE_ID_DRIFT")
    return cluster


def _domain_rows(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    raw = cluster.get("domains")
    if raw is None:
        return []
    if not isinstance(raw, list):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DOMAINS_INVALID")
    if len(raw) > _MAX_DOMAINS:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DOMAINS_OVER_LIMIT")
    return [
        _mapping(item, "TIMEWEB_PG_PRODUCTION_NETWORK_DOMAINS_INVALID") for item in raw
    ]


def _domain_fqdn(row: dict[str, Any]) -> str:
    raw = row.get("fqdn")
    if not isinstance(raw, str):
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_DOMAINS_INVALID")
    return _hostname(raw)


def _domain_matches(cluster: dict[str, Any], target_host: str) -> bool:
    return any(_domain_fqdn(row) == target_host for row in _domain_rows(cluster))


def _select_target_cluster(
    api: ReadOnlyApi,
    project_id: str,
    target_host: str,
) -> tuple[str, dict[str, Any]]:
    matches: list[tuple[str, dict[str, Any]]] = []
    for database_id in _database_ids(api, project_id):
        cluster = _cluster(api, database_id)
        if _domain_matches(cluster, target_host):
            matches.append((database_id, cluster))
    if not matches:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_TARGET_NOT_FOUND")
    if len(matches) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_TARGET_NOT_UNIQUE")
    return matches[0]


def _require_target_network(cluster: dict[str, Any], target_host: str) -> str:
    if cluster.get("name") == SYNTHETIC_CLUSTER_NAME:
        _stop("TIMEWEB_PG_PRODUCTION_SYNTHETIC_TARGET_FORBIDDEN")
    if cluster.get("status") != "started":
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_CLUSTER_NOT_READY")
    if str(cluster.get("port", "")) != POSTGRES_PORT:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_PORT_DRIFT")
    availability_zone = _safe_id(
        cluster.get("availability_zone"),
        "TIMEWEB_PG_PRODUCTION_NETWORK_ZONE_INVALID",
    )
    if cluster.get("is_enabled_public_network") is not True:
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_DISABLED")
    if cluster.get("is_enabled_public_ipv6") is not False:
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV6_FORBIDDEN")
    if cluster.get("is_secure_connection_enabled") is not True:
        _stop("TIMEWEB_PG_PRODUCTION_TLS_NOT_READY")

    domain_matches = [
        row for row in _domain_rows(cluster) if _domain_fqdn(row) == target_host
    ]
    if len(domain_matches) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_TARGET_DOMAIN_DRIFT")
    if domain_matches[0].get("cert_status") != "issued":
        _stop("TIMEWEB_PG_PRODUCTION_TLS_CERTIFICATE_NOT_READY")
    return availability_zone


def _require_bound_public_ipv4(
    api: ReadOnlyApi,
    database_id: str,
    availability_zone: str,
) -> tuple[str, str]:
    rows = _rows(
        api.get("/api/v1/floating-ips"),
        "ips",
        "TIMEWEB_PG_PRODUCTION_FLOATING_IP_INVENTORY_INVALID",
    )
    bound: list[dict[str, Any]] = []
    for row in rows:
        resource_type = row.get("resource_type")
        if resource_type not in _FIREWALL_RESOURCE_TYPES:
            continue
        resource_id = _safe_id(
            row.get("resource_id"),
            "TIMEWEB_PG_PRODUCTION_FLOATING_IP_RESOURCE_ID_INVALID",
        )
        if resource_id == database_id:
            bound.append(row)
    if not bound:
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_MISSING")
    if len(bound) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_NOT_UNIQUE")
    floating_ip_id = _safe_id(
        bound[0].get("id"),
        "TIMEWEB_PG_PRODUCTION_FLOATING_IP_ID_INVALID",
    )
    try:
        address = ipaddress.ip_address(str(bound[0].get("ip", "")))
    except ValueError:
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_INVALID")
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or not address.is_global
        or bound[0].get("availability_zone") != availability_zone
        or bound[0].get("is_ddos_guard") is not False
    ):
        _stop("TIMEWEB_PG_PRODUCTION_PUBLIC_IPV4_BINDING_INVALID")
    return floating_ip_id, str(address)


def _service_group_id(api: ReadOnlyApi, database_id: str) -> str:
    rows = _paged_rows(
        api,
        f"/api/v1/firewall/service/dbaas/{database_id}",
        "groups",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUPS_INVALID",
    )
    if len(rows) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_NOT_EXCLUSIVE")
    return _safe_id(
        rows[0].get("id"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_INVALID",
    )


def _require_default_drop(api: ReadOnlyApi, group_id: str) -> None:
    payload = _mapping(
        api.get(f"/api/v1/firewall/groups/{group_id}"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_INVALID",
    )
    group = _mapping(
        payload.get("group"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_INVALID",
    )
    if (
        _safe_id(
            group.get("id"),
            "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_INVALID",
        )
        != group_id
    ):
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_DRIFT")
    if group.get("policy") != "DROP":
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_DEFAULT_DROP_REQUIRED")


def _require_exact_rule(
    api: ReadOnlyApi,
    group_id: str,
    verifier_cidr: str,
) -> str:
    rules = _paged_rows(
        api,
        f"/api/v1/firewall/groups/{group_id}/rules",
        "rules",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RULES_INVALID",
    )
    if len(rules) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RULESET_WIDENED")
    rule = rules[0]
    rule_id = _safe_id(
        rule.get("id"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RULE_ID_INVALID",
    )
    shape = (
        str(rule.get("direction", "")).lower(),
        str(rule.get("protocol", "")).lower(),
        str(rule.get("port", "")),
    )
    if shape != ("ingress", "tcp", POSTGRES_PORT):
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RULESET_WIDENED")
    observed_cidr = str(rule.get("cidr", "")).strip()
    if observed_cidr != verifier_cidr:
        _stop("TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_DRIFT")
    if _verifier_cidr(observed_cidr) != verifier_cidr:
        _stop("TIMEWEB_PG_PRODUCTION_VERIFIER_CIDR_DRIFT")
    return rule_id


def _require_exact_resource(api: ReadOnlyApi, group_id: str, database_id: str) -> str:
    resources = _paged_rows(
        api,
        f"/api/v1/firewall/groups/{group_id}/resources",
        "resources",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCES_INVALID",
    )
    if len(resources) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED")
    resource = resources[0]
    resource_id = _safe_id(
        resource.get("id"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_ID_INVALID",
    )
    if (
        resource_id != database_id
        or resource.get("type") not in _FIREWALL_RESOURCE_TYPES
    ):
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED")
    return resource_id


def _collect_network_scope_witness(
    api: ReadOnlyApi,
    *,
    project_id: str,
    target_host: str,
    verifier_cidr: str,
) -> tuple[str, str, str, str, str, str, str, str]:
    database_id, cluster = _select_target_cluster(api, project_id, target_host)
    availability_zone = _require_target_network(cluster, target_host)
    floating_ip_id, public_ipv4 = _require_bound_public_ipv4(
        api,
        database_id,
        availability_zone,
    )
    group_id = _service_group_id(api, database_id)
    _require_default_drop(api, group_id)
    rule_id = _require_exact_rule(api, group_id, verifier_cidr)
    resource_id = _require_exact_resource(api, group_id, database_id)
    return (
        database_id,
        availability_zone,
        floating_ip_id,
        public_ipv4,
        group_id,
        rule_id,
        resource_id,
        verifier_cidr,
    )


def verify_network_scope(
    api: ReadOnlyApi,
    *,
    project_id: str,
    target_host: str,
    verifier_cidr: str,
) -> None:
    host = _hostname(target_host)
    cidr = _verifier_cidr(verifier_cidr)
    witnesses = tuple(
        _collect_network_scope_witness(
            api,
            project_id=project_id,
            target_host=host,
            verifier_cidr=cidr,
        )
        for _ in range(_NETWORK_SCOPE_STABILITY_PASSES)
    )
    if len(set(witnesses)) != 1:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_SNAPSHOT_DRIFT")
    print(
        "TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=READY "
        "public_ipv4=bound ipv6=off tls=enabled "
        "firewall=drop ingress=tcp/5432 source=/32"
    )


def _runtime_inputs() -> tuple[ReadOnlyApi, str, str, str]:
    from apps.api import timeweb_postgres_tls
    from scripts import probe_v10_timeweb_postgres_control_plane as control_plane
    from scripts import provider_runtime_primitives as provider_base

    token = provider_base._required_env(TOKEN_ENV)
    bootstrap_dsn = provider_base._required_env(BOOTSTRAP_DSN_ENV)
    cidr = provider_base._required_env(VERIFIER_CIDR_ENV)
    try:
        params = timeweb_postgres_tls._connection_params(bootstrap_dsn)
    except timeweb_postgres_tls.TimewebPostgresTlsError as exc:
        _stop(exc.code)
    host = _hostname(params.get("host"))
    api = control_plane.TimewebReadOnlyApi(token)
    try:
        project_id = control_plane.verify_credential_health(api)
    except provider_base.ProvisioningStopped as exc:
        _stop(exc.code)
    return api, project_id, host, cidr


def _provider_runtime_code(exc: RuntimeError) -> str | None:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.startswith("TIMEWEB_"):
        return code
    return None


def main() -> int:
    try:
        api, project_id, host, cidr = _runtime_inputs()
        verify_network_scope(
            api,
            project_id=project_id,
            target_host=host,
            verifier_cidr=cidr,
        )
    except NetworkScopeStopped as exc:
        print(
            f"TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=STOPPED code={exc}",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as exc:
        code = _provider_runtime_code(exc)
        if code is None:
            raise
        print(
            f"TIMEWEB_PG_PRODUCTION_NETWORK_SCOPE=STOPPED code={code}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
