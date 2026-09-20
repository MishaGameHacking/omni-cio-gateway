from __future__ import annotations

from collections.abc import Callable
from functools import partial
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import struct
import tempfile
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import OpenerDirector, Request

from scripts import probe_v10_timeweb_postgres_control_plane as read_only
from scripts import provision_v10_render_neon_preview as _provider_base
from scripts import timeweb_ipv4_custody as custody


CONFIRMATION = "ENABLE_TIMEWEB_RU_PG_PUBLIC_IPV4_200_RUB_MONTH"
CONFIRMATION_ENV = "TIMEWEB_RU_PG_PUBLIC_IPV4_CONFIRMATION"
VERIFIER_CIDR_ENV = "OMNI_V10_RU_PG_VERIFIER_CIDR"
TARGET_ZONE = "msk-1"
FIREWALL_NAME = "omni-cio-v10-ru-pg-synthetic-verifier"
FIREWALL_DESCRIPTION = "Omni-CIO V10 RU-PG-B synthetic verifier only"
FIREWALL_RESOURCE_TYPE = "dbaas"
POSTGRES_PORT = "5432"
CA_URL = "https://st.timeweb.com/cloud-static/ca.crt"
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_CA_BYTES = 128 * 1024
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,96}$", re.ASCII)
_OPERATION_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$", re.ASCII)
_HOST_RE = re.compile(
    r"^(?=.{1,253}\.?$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\.?$"
)
_RECONCILE_DELAYS_SECONDS = (1.0, 2.0, 4.0)
_RECONCILABLE_MUTATION_HTTP_STATUSES = frozenset({409, 423})
_STATE_DELAYS_SECONDS = (2.0, 3.0, 5.0, 8.0, 15.0, 20.0, 30.0)
_TRANSITIONAL_STATUSES = frozenset(
    {"starting", "rebooting", "lan_transfer", "transfer", "turning_on"}
)
Sleep = Callable[[float], None]


class AmbiguousMutation(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        operation: str | None = None,
        status: int | None = None,
    ) -> None:
        self.code = code
        self.operation = operation
        self.status = status
        details = []
        if operation is not None:
            details.append(f"operation={operation}")
        if status is not None:
            details.append(f"status={status}")
        suffix = f" {' '.join(details)}" if details else ""
        super().__init__(f"{code}{suffix}")


class TimewebMutationApi:
    def __init__(
        self,
        token: str,
        *,
        opener: OpenerDirector | Any | None = None,
    ) -> None:
        if not token:
            raise _provider_base.ProvisioningStopped("TIMEWEB_CLOUD_API_TOKEN_REQUIRED")
        self._token = token
        self._opener = opener or _provider_base._NO_REDIRECT_OPENER

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
    ) -> Request:
        if not path.startswith("/api/") or "://" in path or ".." in path:
            raise _provider_base.ProvisioningStopped("TIMEWEB_MUTATION_PATH_INVALID")
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "omni-cio-v10-ru-pg-public-ipv4-tls",
        }
        if body is not None:
            data = json.dumps(
                body,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        # Timeweb's generated SDK sends application/json for mutating POST/PATCH
        # requests even when the endpoint has no request body (for example
        # firewall resource linking). Mirror that wire contract exactly.
        if body is not None or method in {"POST", "PUT", "PATCH"}:
            headers["Content-Type"] = "application/json"
        return Request(
            f"{read_only.API_BASE}{path}",
            headers=headers,
            data=data,
            method=method,
        )

    def mutate_once(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        body: dict[str, object] | None = None,
        expected_statuses: frozenset[int],
        reconcile_statuses: frozenset[int] = frozenset(),
        timeout: float = 30.0,
    ) -> Any:
        if _OPERATION_RE.fullmatch(operation) is None:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_MUTATION_OPERATION_INVALID"
            )
        request = self._request(method, path, body)
        try:
            with self._opener.open(request, timeout=timeout) as response:
                status = int(response.status)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            status = int(exc.code)
            if status in {408, 429, 500, 502, 503, 504} or status in reconcile_statuses:
                raise AmbiguousMutation(
                    "TIMEWEB_MUTATION_AMBIGUOUS",
                    operation=operation,
                    status=status,
                ) from None
            if status in {401, 403}:
                raise _provider_base.ProvisioningStopped(
                    "TIMEWEB_API_TOKEN_INVALID_OR_INSUFFICIENT",
                    status=status,
                ) from None
            raise _provider_base.ProvisioningStopped(
                f"TIMEWEB_{operation}_REJECTED",
                status=status,
            ) from None
        except OSError:
            raise AmbiguousMutation(
                "TIMEWEB_MUTATION_AMBIGUOUS",
                operation=operation,
            ) from None

        if status not in expected_statuses:
            if (
                status in {408, 429, 500, 502, 503, 504}
                or status in reconcile_statuses
                or 200 <= status < 300
            ):
                raise AmbiguousMutation(
                    "TIMEWEB_MUTATION_AMBIGUOUS",
                    operation=operation,
                    status=status,
                )
            raise _provider_base.ProvisioningStopped(
                f"TIMEWEB_{operation}_UNEXPECTED_STATUS",
                status=status,
            )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AmbiguousMutation("TIMEWEB_MUTATION_RESPONSE_TOO_LARGE")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AmbiguousMutation("TIMEWEB_MUTATION_RESPONSE_INVALID") from None


def _required_confirmation() -> None:
    if os.environ.get(CONFIRMATION_ENV, "").strip() != CONFIRMATION:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PUBLIC_IPV4_CONFIRMATION_REQUIRED"
        )


def _required_verifier_cidr() -> str:
    raw = os.environ.get(VERIFIER_CIDR_ENV, "").strip()
    try:
        network = ipaddress.ip_network(raw, strict=True)
    except ValueError:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_VERIFIER_CIDR_INVALID"
        ) from None
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or network.prefixlen != 32
        or not network.network_address.is_global
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_VERIFIER_CIDR_INVALID")
    return str(network)


def _safe_id(value: object, code: str) -> str:
    text = str(value).strip()
    if _ID_RE.fullmatch(text) is None:
        raise _provider_base.ProvisioningStopped(code)
    return text


def _numeric_id(value: object, code: str) -> int:
    if type(value) is not int and (
        not isinstance(value, str)
        or re.fullmatch(r"[1-9]\d{0,19}", value, re.ASCII) is None
    ):
        raise _provider_base.ProvisioningStopped(code)
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise _provider_base.ProvisioningStopped(code) from None
    if number <= 0:
        raise _provider_base.ProvisioningStopped(code)
    return number


def _target_cluster_id(api: read_only.TimewebReadOnlyApi) -> int:
    project_id = read_only._select_project(api.get("/api/v1/projects"))
    project_path = f"/api/v1/projects/{project_id}/resources/databases"
    rows = read_only._rows(
        api.get(project_path),
        "databases",
        "TIMEWEB_PROJECT_DATABASES_RESPONSE_INVALID",
    )
    matches = [row for row in rows if row.get("name") == read_only.TARGET_CLUSTER_NAME]
    if len(matches) != 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_TARGET_CLUSTER_NOT_UNIQUE")
    return _numeric_id(matches[0].get("id"), "TIMEWEB_TARGET_CLUSTER_ID_INVALID")


def _cluster(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
) -> dict[str, Any]:
    payload = _provider_base._json_object(
        api.get(f"/api/v1/databases/{cluster_id}"),
        "TIMEWEB_CLUSTER_RESPONSE_INVALID",
    )
    cluster = _provider_base._json_object(
        payload.get("db"),
        "TIMEWEB_CLUSTER_RESPONSE_INVALID",
    )
    if cluster.get("name") != read_only.TARGET_CLUSTER_NAME:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_ID_DRIFT")
    immutable = {
        "location": read_only.TARGET_LOCATION,
        "availability_zone": TARGET_ZONE,
        "cpu": read_only.TARGET_CPU,
        "ram": read_only.TARGET_RAM_MB,
        "is_autobackups_enabled": False,
        "is_backup_schedule_enabled": False,
    }
    for key, expected in immutable.items():
        if cluster.get(key) != expected:
            raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_SHAPE_DRIFT")
    if not isinstance(cluster.get("is_enabled_public_ipv6"), bool):
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_IPV6_STATE_INVALID")
    if _numeric_id(cluster.get("port"), "TIMEWEB_CLUSTER_PORT_INVALID") != int(
        POSTGRES_PORT
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_PORT_DRIFT")
    read_only._require_target_cluster_disk(
        cluster,
        drift_code="TIMEWEB_CLUSTER_DISK_SIZE_DRIFT",
    )
    read_only._require_target_replica_topology(
        cluster,
        expected_cluster_id=str(cluster_id),
    )
    autoscaling = cluster.get("disk_autoscaling")
    if autoscaling is not None:
        settings = _provider_base._json_object(
            autoscaling,
            "TIMEWEB_CLUSTER_DISK_AUTOSCALING_INVALID",
        )
        if settings.get("is_enabled") is not False:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_CLUSTER_DISK_AUTOSCALING_ENABLED"
            )
    return cluster


def _rows(
    api: read_only.TimewebReadOnlyApi,
    path: str,
    key: str,
) -> list[dict[str, Any]]:
    return read_only._rows(
        api.get(path),
        key,
        f"TIMEWEB_{key.upper()}_RESPONSE_INVALID",
    )


def _group_id_by_name(api: read_only.TimewebReadOnlyApi) -> str | None:
    matches = [
        row
        for row in _rows(api, "/api/v1/firewall/groups", "groups")
        if row.get("name") == FIREWALL_NAME
    ]
    if len(matches) > 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_FIREWALL_GROUP_NOT_UNIQUE")
    if not matches:
        return None
    return _safe_id(matches[0].get("id"), "TIMEWEB_FIREWALL_GROUP_ID_INVALID")


def _verify_group(api: read_only.TimewebReadOnlyApi, group_id: str) -> None:
    payload = _provider_base._json_object(
        api.get(f"/api/v1/firewall/groups/{group_id}"),
        "TIMEWEB_FIREWALL_GROUP_RESPONSE_INVALID",
    )
    group = _provider_base._json_object(
        payload.get("group"),
        "TIMEWEB_FIREWALL_GROUP_RESPONSE_INVALID",
    )
    if (
        group.get("name") != FIREWALL_NAME
        or group.get("description") != FIREWALL_DESCRIPTION
        or group.get("policy") != "DROP"
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_FIREWALL_GROUP_DRIFT")


def _ensure_group(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
) -> str:
    existing = _group_id_by_name(api)
    if existing is not None:
        _verify_group(api, existing)
        return existing
    body = {"name": FIREWALL_NAME, "description": FIREWALL_DESCRIPTION}
    try:
        response = mutation.mutate_once(
            "POST",
            "/api/v1/firewall/groups?policy=DROP",
            operation="FIREWALL_GROUP_CREATE",
            body=body,
            expected_statuses=frozenset({201}),
            reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
    except AmbiguousMutation:
        response = None
    created: str | None = None
    if response is not None:
        obj = _provider_base._json_object(
            response,
            "TIMEWEB_FIREWALL_GROUP_CREATE_RESPONSE_INVALID",
        )
        group = _provider_base._json_object(
            obj.get("group"),
            "TIMEWEB_FIREWALL_GROUP_CREATE_RESPONSE_INVALID",
        )
        created = _safe_id(
            group.get("id"),
            "TIMEWEB_FIREWALL_GROUP_CREATE_RESPONSE_INVALID",
        )
    if created is None:
        for delay in _RECONCILE_DELAYS_SECONDS:
            created = _group_id_by_name(api)
            if created is not None:
                break
            time.sleep(delay)
    if created is None:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_GROUP_CREATE_RECONCILIATION_REQUIRED"
        )
    _verify_group(api, created)
    return created


def _rule_body(cidr: str) -> dict[str, object]:
    if cidr == "0.0.0.0/0":
        raise _provider_base.ProvisioningStopped("TIMEWEB_FIREWALL_WILDCARD_FORBIDDEN")
    return {
        "description": "Omni-CIO RU-PG-B verifier PostgreSQL",
        "direction": "ingress",
        "port": POSTGRES_PORT,
        "protocol": "tcp",
        "cidr": cidr,
    }


def _rules(
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
) -> list[dict[str, Any]]:
    return _rows(api, f"/api/v1/firewall/groups/{group_id}/rules", "rules")


def _ensure_rule(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
    cidr: str,
) -> None:
    expected = _rule_body(cidr)
    rules = _rules(api, group_id)
    if len(rules) > 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_FIREWALL_RULESET_WIDENED")
    if not rules:
        try:
            mutation.mutate_once(
                "POST",
                f"/api/v1/firewall/groups/{group_id}/rules",
                operation="FIREWALL_RULE_CREATE",
                body=expected,
                expected_statuses=frozenset({201}),
                reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
            )
        except AmbiguousMutation:
            pass
    else:
        rule = rules[0]
        comparable = {
            key: rule.get(key)
            for key in ("description", "direction", "port", "protocol", "cidr")
        }
        if comparable != expected:
            non_cidr = dict(comparable)
            expected_non_cidr = dict(expected)
            non_cidr.pop("cidr", None)
            expected_non_cidr.pop("cidr", None)
            if non_cidr != expected_non_cidr:
                raise _provider_base.ProvisioningStopped(
                    "TIMEWEB_FIREWALL_RULESET_WIDENED"
                )
            rule_id = _safe_id(rule.get("id"), "TIMEWEB_FIREWALL_RULE_ID_INVALID")
            try:
                mutation.mutate_once(
                    "PATCH",
                    f"/api/v1/firewall/groups/{group_id}/rules/{rule_id}",
                    operation="FIREWALL_RULE_PATCH",
                    body=expected,
                    expected_statuses=frozenset({200}),
                    reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
                )
            except AmbiguousMutation:
                pass
    verified = _rules(api, group_id)
    if len(verified) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_RULE_RECONCILIATION_FAILED"
        )
    comparable = {
        key: verified[0].get(key)
        for key in ("description", "direction", "port", "protocol", "cidr")
    }
    if comparable != expected:
        raise _provider_base.ProvisioningStopped("TIMEWEB_FIREWALL_RULE_DRIFT")


def _resources(
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
) -> list[dict[str, Any]]:
    return _rows(api, f"/api/v1/firewall/groups/{group_id}/resources", "resources")


def _service_groups(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
) -> list[dict[str, Any]]:
    return _rows(
        api,
        f"/api/v1/firewall/service/{FIREWALL_RESOURCE_TYPE}/{cluster_id}",
        "groups",
    )


def _resource_matches(row: dict[str, Any], cluster_id: int) -> bool:
    try:
        resource_id = int(row.get("id"))
    except (TypeError, ValueError):
        return False
    return resource_id == cluster_id and row.get("type") in {"dbaas", "database"}


def _verify_resource_link(
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
    cluster_id: int,
) -> None:
    resources = _resources(api, group_id)
    if len(resources) != 1 or not _resource_matches(resources[0], cluster_id):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_RESOURCE_SCOPE_WIDENED"
        )


def _verify_exclusive_firewall(
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
    cluster_id: int,
) -> None:
    groups = _service_groups(api, cluster_id)
    if len(groups) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE"
        )
    actual = _safe_id(
        groups[0].get("id"),
        "TIMEWEB_FIREWALL_GROUP_ID_INVALID",
    )
    if actual != group_id:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_SERVICE_GROUPS_NOT_EXCLUSIVE"
        )


def _ensure_resource_link(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
    cluster_id: int,
) -> None:
    resources = _resources(api, group_id)
    if resources and not (
        len(resources) == 1 and _resource_matches(resources[0], cluster_id)
    ):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_RESOURCE_SCOPE_WIDENED"
        )
    if not resources:
        path = (
            f"/api/v1/firewall/groups/{group_id}/resources/{cluster_id}?"
            + urlencode({"resource_type": FIREWALL_RESOURCE_TYPE})
        )
        try:
            mutation.mutate_once(
                "POST",
                path,
                operation="FIREWALL_RESOURCE_LINK",
                expected_statuses=frozenset({201}),
                reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
            )
        except AmbiguousMutation:
            pass
    verified = _resources(api, group_id)
    if len(verified) != 1 or not _resource_matches(verified[0], cluster_id):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FIREWALL_RESOURCE_LINK_FAILED"
        )


def _verify_safe_narrow_rule(
    api: read_only.TimewebReadOnlyApi,
    group_id: str,
) -> None:
    rules = _rules(api, group_id)
    if len(rules) != 1:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_FIREWALL_NOT_NARROW"
        )
    rule = rules[0]
    expected = {
        "description": "Omni-CIO RU-PG-B verifier PostgreSQL",
        "direction": "ingress",
        "port": POSTGRES_PORT,
        "protocol": "tcp",
    }
    actual = {
        key: rule.get(key) for key in ("description", "direction", "port", "protocol")
    }
    if actual != expected:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_FIREWALL_NOT_NARROW"
        )
    try:
        network = ipaddress.ip_network(str(rule.get("cidr", "")), strict=True)
    except ValueError:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_FIREWALL_NOT_NARROW"
        ) from None
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or network.prefixlen != 32
        or not network.network_address.is_global
    ):
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_FIREWALL_NOT_NARROW"
        )


def _floating_ips(api: read_only.TimewebReadOnlyApi) -> list[dict[str, Any]]:
    return custody.raw_inventory(api.get("/api/v1/floating-ips"))


def _verify_floating_ip_row(row: dict[str, Any]) -> str:
    try:
        address = ipaddress.ip_address(str(row.get("ip", "")))
    except ValueError:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_FLOATING_IP_INVALID"
        ) from None
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise _provider_base.ProvisioningStopped("TIMEWEB_FLOATING_IP_INVALID")
    if (
        row.get("availability_zone") != TARGET_ZONE
        or row.get("is_ddos_guard") is not False
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_FLOATING_IP_SHAPE_DRIFT")
    return str(address)


def _bound_ip_for_cluster(
    rows: list[dict[str, Any]],
    cluster_id: int,
) -> dict[str, Any] | None:
    # Canonical binding parser rejects missing fields and numeric coercion.
    parsed = custody.inventory(rows)
    matches = [
        row
        for row in parsed
        if row.resource_type in {"database", "dbaas"}
        and row.resource_id == str(cluster_id)
    ]
    if len(matches) > 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_MULTIPLE_IPV4_BOUND")
    if not matches:
        return None
    return next(row for row in rows if row["id"] == matches[0].identifier)


def _is_unbound(row: dict[str, Any]) -> bool:
    return custody.is_unbound(row)


def _create_floating_ip(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
) -> tuple[str, str, bool]:
    before = _floating_ips(api)
    if any(_is_unbound(row) for row in before):
        raise _provider_base.ProvisioningStopped("TIMEWEB_UNMANAGED_FREE_IPV4_PRESENT")
    before_ids = {
        _safe_id(row.get("id"), "TIMEWEB_FLOATING_IP_ID_INVALID") for row in before
    }
    body = {"is_ddos_guard": False, "availability_zone": TARGET_ZONE}
    try:
        response = mutation.mutate_once(
            "POST",
            "/api/v1/floating-ips",
            operation="FLOATING_IP_CREATE",
            body=body,
            expected_statuses=frozenset({201}),
            reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
    except AmbiguousMutation:
        response = None
    if response is not None:
        obj = _provider_base._json_object(
            response,
            "TIMEWEB_FLOATING_IP_CREATE_RESPONSE_INVALID",
        )
        row = _provider_base._json_object(
            obj.get("ip"),
            "TIMEWEB_FLOATING_IP_CREATE_RESPONSE_INVALID",
        )
        return (
            _safe_id(row.get("id"), "TIMEWEB_FLOATING_IP_ID_INVALID"),
            _verify_floating_ip_row(row),
            True,
        )

    for delay in _RECONCILE_DELAYS_SECONDS:
        after = _floating_ips(api)
        new_rows = [
            row
            for row in after
            if _safe_id(row.get("id"), "TIMEWEB_FLOATING_IP_ID_INVALID")
            not in before_ids
        ]
        safe = [
            row
            for row in new_rows
            if _is_unbound(row)
            and row.get("availability_zone") == TARGET_ZONE
            and row.get("is_ddos_guard") is False
        ]
        if len(new_rows) > 1:
            break
        if len(safe) == 1:
            # Visibility is not a create receipt: another account operator could
            # have created the only delta. Preserve it; never stamp guessed custody.
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_FLOATING_IP_CREATE_RECEIPT_UNPROVEN"
            )
        time.sleep(delay)
    raise _provider_base.ProvisioningStopped(
        "TIMEWEB_FLOATING_IP_CREATE_RECONCILIATION_REQUIRED"
    )


def _issued_domain(cluster: dict[str, Any]) -> str | None:
    domains = _provider_base._json_list(
        cluster.get("domains"),
        "TIMEWEB_CLUSTER_DOMAINS_INVALID",
    )
    issued: list[str] = []
    for value in domains:
        row = _provider_base._json_object(
            value,
            "TIMEWEB_CLUSTER_DOMAINS_INVALID",
        )
        if row.get("cert_status") != "issued":
            continue
        fqdn = str(row.get("fqdn", "")).strip().rstrip(".")
        if _HOST_RE.fullmatch(fqdn) is None:
            raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_DOMAIN_INVALID")
        issued.append(fqdn)
    if len(issued) > 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_DOMAIN_NOT_UNIQUE")
    return issued[0] if issued else None


def _network_ready(cluster: dict[str, Any]) -> bool:
    return (
        cluster.get("is_enabled_public_network") is True
        and cluster.get("is_enabled_public_ipv6") is False
        and cluster.get("is_secure_connection_enabled") is True
        and cluster.get("status") == "started"
        and _issued_domain(cluster) is not None
    )


def _wait_network_ready(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    *,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _STATE_DELAYS_SECONDS,
) -> dict[str, Any]:
    for attempt in range(len(delays) + 1):
        cluster = _cluster(api, cluster_id)
        if _network_ready(cluster):
            return cluster
        status = str(cluster.get("status", ""))
        if status not in _TRANSITIONAL_STATUSES and status != "started":
            raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_UNSAFE_STATUS")
        if attempt < len(delays):
            sleeper(delays[attempt])
    raise _provider_base.ProvisioningStopped("TIMEWEB_PUBLIC_IPV4_TLS_READY_TIMEOUT")


def _patch_public_network(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    address: str,
) -> dict[str, Any]:
    body = {
        "floating_ip": address,
        "is_enabled_public_network": True,
        "is_enabled_public_ipv6": False,
        "is_secure_connection_enable": True,
    }
    try:
        mutation.mutate_once(
            "PATCH",
            f"/api/v2/databases/{cluster_id}",
            operation="DATABASE_PUBLIC_NETWORK_PATCH",
            body=body,
            expected_statuses=frozenset({200}),
            reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
    except AmbiguousMutation:
        pass
    return _wait_network_ready(api, cluster_id)


def _close_public_network(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    *,
    sleeper: Sleep = time.sleep,
) -> None:
    body = {
        "is_enabled_public_network": False,
        "is_enabled_public_ipv6": False,
    }
    try:
        mutation.mutate_once(
            "PATCH",
            f"/api/v2/databases/{cluster_id}",
            operation="DATABASE_PUBLIC_NETWORK_ROLLBACK",
            body=body,
            expected_statuses=frozenset({200}),
            reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
    except AmbiguousMutation:
        pass
    for delay in (1.0, 2.0, 4.0, 8.0, 15.0):
        cluster = _cluster(api, cluster_id)
        if (
            cluster.get("is_enabled_public_network") is False
            and cluster.get("is_enabled_public_ipv6") is False
        ):
            return
        sleeper(delay)
    raise _provider_base.ProvisioningStopped(
        "TIMEWEB_PUBLIC_NETWORK_ROLLBACK_MANUAL_RECONCILIATION_REQUIRED"
    )


def _delete_created_ipv4_if_unbound(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    floating_id: str,
) -> None:
    rows = _floating_ips(api)
    target = [
        row
        for row in rows
        if _safe_id(row.get("id"), "TIMEWEB_FLOATING_IP_ID_INVALID") == floating_id
    ]
    if not target:
        return
    if len(target) != 1:
        raise _provider_base.ProvisioningStopped("TIMEWEB_IPV4_CLEANUP_NOT_UNIQUE")
    if not _is_unbound(target[0]):
        return
    try:
        mutation.mutate_once(
            "DELETE",
            f"/api/v1/floating-ips/{floating_id}",
            operation="FLOATING_IP_CLEANUP_DELETE",
            expected_statuses=frozenset({204}),
            reconcile_statuses=frozenset({404, 409, 423}),
        )
    except AmbiguousMutation:
        pass
    for attempt in range(len(_RECONCILE_DELAYS_SECONDS) + 1):
        rows = _floating_ips(api)
        if not any(row.get("id") == floating_id for row in rows):
            return
        if attempt < len(_RECONCILE_DELAYS_SECONDS):
            time.sleep(_RECONCILE_DELAYS_SECONDS[attempt])
    raise _provider_base.ProvisioningStopped("TIMEWEB_IPV4_CLEANUP_ABSENCE_UNPROVEN")


def _fetch_ca_file(
    *,
    opener: OpenerDirector | Any | None = None,
) -> Path:
    client = opener or _provider_base._NO_REDIRECT_OPENER
    request = Request(
        CA_URL,
        headers={
            "Accept": "application/x-pem-file,text/plain",
            "User-Agent": "omni-cio-v10-ru-pg-ca-fetch",
        },
        method="GET",
    )
    try:
        with client.open(request, timeout=20.0) as response:
            status = int(response.status)
            raw = response.read(MAX_CA_BYTES + 1)
    except OSError:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CA_FETCH_FAILED") from None
    if status != 200 or len(raw) > MAX_CA_BYTES:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CA_FETCH_FAILED")
    if (
        b"-----BEGIN CERTIFICATE-----" not in raw
        or b"-----END CERTIFICATE-----" not in raw
    ):
        raise _provider_base.ProvisioningStopped("TIMEWEB_CA_INVALID")
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        prefix="omni-cio-timeweb-ca-",
        suffix=".crt",
        delete=False,
    )
    try:
        handle.write(raw)
        handle.flush()
        path = Path(handle.name)
    finally:
        handle.close()
    try:
        os.chmod(path, 0o600)
    except OSError:
        path.unlink(missing_ok=True)
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_CA_FILE_HARDENING_FAILED"
        ) from None
    return path


def _tls_client_context(ca_path: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=str(ca_path))
    return context


def _probe_postgres_tls(hostname: str, ca_path: Path) -> None:
    context = _tls_client_context(ca_path)
    raw_socket: socket.socket | None = None
    try:
        raw_socket = socket.create_connection(
            (hostname, int(POSTGRES_PORT)),
            timeout=15.0,
        )
        raw_socket.sendall(struct.pack("!II", 8, 80877103))
        if raw_socket.recv(1) != b"S":
            raise _provider_base.ProvisioningStopped("TIMEWEB_POSTGRES_TLS_REFUSED")
        with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
            raw_socket = None
            if tls_socket.getpeercert() is None:
                raise _provider_base.ProvisioningStopped(
                    "TIMEWEB_POSTGRES_TLS_CERT_MISSING"
                )
    except OSError:
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_POSTGRES_TLS_VERIFY_FULL_FAILED"
        ) from None
    finally:
        if raw_socket is not None:
            raw_socket.close()


def _verify_bound_ipv4(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    expected_address: str,
) -> None:
    row = _bound_ip_for_cluster(_floating_ips(api), cluster_id)
    if row is None or _verify_floating_ip_row(row) != expected_address:
        raise _provider_base.ProvisioningStopped("TIMEWEB_FLOATING_IP_BINDING_DRIFT")


def _prepare_preexisting_exposure(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    initial: dict[str, Any],
) -> bool:
    if initial.get("is_enabled_public_ipv6") is True:
        _close_public_network(mutation, api, cluster_id)
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_PUBLIC_IPV6_UNSAFE"
        )

    public_network_enabled = initial.get("is_enabled_public_network") is True
    if not public_network_enabled:
        return False

    try:
        existing_group = _group_id_by_name(api)
        if existing_group is None:
            raise _provider_base.ProvisioningStopped(
                "TIMEWEB_PREEXISTING_PUBLIC_NETWORK_UNSAFE"
            )
        _verify_group(api, existing_group)
        _verify_safe_narrow_rule(api, existing_group)
        _verify_resource_link(api, existing_group, cluster_id)
        _verify_exclusive_firewall(api, existing_group, cluster_id)
    except _provider_base.ProvisioningStopped:
        _close_public_network(mutation, api, cluster_id)
        raise _provider_base.ProvisioningStopped(
            "TIMEWEB_PREEXISTING_PUBLIC_NETWORK_UNSAFE"
        ) from None
    return True


def _converge_firewall(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    cidr: str,
) -> str:
    group_id = _ensure_group(mutation, api)
    _ensure_rule(mutation, api, group_id, cidr)
    _ensure_resource_link(mutation, api, group_id, cluster_id)
    _verify_group(api, group_id)
    _verify_exclusive_firewall(api, group_id, cluster_id)
    return group_id


def _stamp_created_ipv4(
    mutation: TimewebMutationApi,
    floating_id: str,
    management_marker: str,
) -> None:
    # The caller has just verified the current-create receipt and exact GET delta.
    # This is metadata only; never send ptr or change another resource's comment.
    try:
        mutation.mutate_once(
            "PATCH",
            f"/api/v1/floating-ips/{floating_id}",
            operation="FLOATING_IP_CUSTODY_STAMP",
            body={"comment": management_marker},
            expected_statuses=frozenset({200}),
            reconcile_statuses=_RECONCILABLE_MUTATION_HTTP_STATUSES,
        )
    except AmbiguousMutation:
        # The caller proves the exact stored association by bounded GETs.
        return


def _preflight_ipv4_custody(
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    initial: dict[str, Any],
) -> None:
    rows = custody.inventory(_floating_ips(api))
    _provider_base._emit(custody.observation(rows, cluster_id))
    custody.select(
        rows,
        cluster_id,
        public_enabled=initial.get("is_enabled_public_network"),
    )


def _resolve_transport_ipv4(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    *,
    preexisting_public_network: bool,
) -> tuple[str, str, bool]:
    return custody.resolve(
        partial(_floating_ips, api),
        partial(_create_floating_ip, mutation, api),
        partial(_stamp_created_ipv4, mutation),
        partial(_delete_created_ipv4_if_unbound, mutation, api),
        cluster_id,
        public_enabled=preexisting_public_network,
        emit=_provider_base._emit,
    )


def _verify_tls_transport(cluster: dict[str, Any]) -> None:
    hostname = _issued_domain(cluster)
    if hostname is None:
        raise _provider_base.ProvisioningStopped("TIMEWEB_CLUSTER_DOMAIN_NOT_READY")
    ca_path = _fetch_ca_file()
    try:
        _probe_postgres_tls(hostname, ca_path)
    finally:
        ca_path.unlink(missing_ok=True)


def _rollback_failed_transport(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    *,
    public_exposure_possible: bool,
    created_this_run: bool,
    floating_id: str,
) -> None:
    if public_exposure_possible:
        _close_public_network(mutation, api, cluster_id)
    if created_this_run and floating_id:
        _delete_created_ipv4_if_unbound(mutation, api, floating_id)


def _configure_transport(
    mutation: TimewebMutationApi,
    api: read_only.TimewebReadOnlyApi,
    cluster_id: int,
    initial: dict[str, Any],
    cidr: str,
    *,
    preexisting_public_network: bool,
) -> None:
    floating_id = ""
    created_this_run = False
    public_exposure_possible = preexisting_public_network
    try:
        _preflight_ipv4_custody(api, cluster_id, initial)
        group_id = _converge_firewall(mutation, api, cluster_id, cidr)
        floating_id, address, created_this_run = _resolve_transport_ipv4(
            mutation,
            api,
            cluster_id,
            preexisting_public_network=preexisting_public_network,
        )
        if _network_ready(initial):
            cluster = initial
        else:
            public_exposure_possible = True
            cluster = _patch_public_network(
                mutation,
                api,
                cluster_id,
                address,
            )

        _verify_group(api, group_id)
        _ensure_rule(mutation, api, group_id, cidr)
        _ensure_resource_link(mutation, api, group_id, cluster_id)
        _verify_exclusive_firewall(api, group_id, cluster_id)
        _verify_bound_ipv4(api, cluster_id, address)
        _verify_tls_transport(cluster)
    except Exception:
        _rollback_failed_transport(
            mutation,
            api,
            cluster_id,
            public_exposure_possible=public_exposure_possible,
            created_this_run=created_this_run,
            floating_id=floating_id,
        )
        raise


def _provision_transport() -> None:
    _required_confirmation()
    cidr = _required_verifier_cidr()
    token = _provider_base._required_env(read_only.TOKEN_ENV)
    api = read_only.TimewebReadOnlyApi(token)
    mutation = TimewebMutationApi(token)

    cluster_id = _target_cluster_id(api)
    initial = _cluster(api, cluster_id)
    preexisting_public_network = _prepare_preexisting_exposure(
        mutation,
        api,
        cluster_id,
        initial,
    )
    _configure_transport(
        mutation,
        api,
        cluster_id,
        initial,
        cidr,
        preexisting_public_network=preexisting_public_network,
    )

    _provider_base._emit(
        "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=READY "
        "firewall=DROP ingress=tcp/5432 source=/32 ipv4=verified "
        "ipv6=off ddos=off tls=verify-full"
    )


def provision() -> None:
    try:
        _provision_transport()
    except custody.CustodyStopped as exc:
        raise _provider_base.ProvisioningStopped(str(exc)) from None


def _stopped_marker(exc: _provider_base.ProvisioningStopped) -> str:
    marker = f"TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED code={exc.code}"
    if exc.status is not None:
        marker += f" http_status={exc.status}"
    return marker


def main() -> int:
    try:
        provision()
    except _provider_base.ProvisioningStopped as exc:
        _provider_base._emit(_stopped_marker(exc))
        return 1
    except AmbiguousMutation as exc:
        marker = (
            "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED "
            "code=TIMEWEB_MUTATION_MANUAL_RECONCILIATION_REQUIRED"
        )
        if exc.operation is not None:
            marker += f" operation={exc.operation}"
        if exc.status is not None:
            marker += f" http_status={exc.status}"
        _provider_base._emit(marker)
        return 1
    except Exception:
        _provider_base._emit(
            "TIMEWEB_RU_PG_PUBLIC_IPV4_TLS=STOPPED "
            "code=TIMEWEB_PUBLIC_IPV4_UNEXPECTED_FAILURE"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
