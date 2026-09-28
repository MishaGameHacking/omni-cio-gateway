from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from typing import Any, NoReturn
from urllib.parse import urlencode

from scripts import provider_runtime_primitives as provider_base
from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as transport
from scripts import timeweb_postgres_production_network_scope as scope


CONFIRMATION_ENV = "OMNI_V10_TIMEWEB_PROD_NETWORK_CONFIRMATION"
CONFIRMATION = "BOOTSTRAP_AND_PREPARE_TIMEWEB_PRODUCTION_POSTGRES"
FIREWALL_NAME = "omni-cio-v10-production-verifier"
FIREWALL_DESCRIPTION = "Omni-CIO V10 production verifier only"
RULE_DESCRIPTION = "Omni-CIO V10 production verifier PostgreSQL"
_RECONCILE_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)
_RECONCILE_STATUSES = frozenset({409, 423})
Sleep = Callable[[float], None]


class ProductionNetworkConvergeStopped(RuntimeError):
    pass


def _stop(code: str) -> NoReturn:
    raise ProductionNetworkConvergeStopped(code)


def _required_confirmation() -> None:
    if os.environ.get(CONFIRMATION_ENV, "").strip() != CONFIRMATION:
        _stop("TIMEWEB_PG_PRODUCTION_NETWORK_CONVERGE_CONFIRMATION_REQUIRED")


def _attached_group_ids(api: scope.ReadOnlyApi, database_id: str) -> tuple[str, ...]:
    rows = scope._paged_rows(
        api,
        f"/api/v1/firewall/service/dbaas/{database_id}",
        "groups",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUPS_INVALID",
    )
    group_ids = tuple(
        scope._safe_id(
            row.get("id"),
            "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_INVALID",
        )
        for row in rows
    )
    if len(set(group_ids)) != len(group_ids):
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_SERVICE_GROUP_ID_DUPLICATE")
    return tuple(sorted(group_ids))


def _group_rows(api: scope.ReadOnlyApi) -> list[dict[str, Any]]:
    return scope._paged_rows(
        api,
        "/api/v1/firewall/groups",
        "groups",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUPS_INVALID",
    )


def _named_group_id(api: scope.ReadOnlyApi) -> str | None:
    matches = [row for row in _group_rows(api) if row.get("name") == FIREWALL_NAME]
    if len(matches) > 1:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_GROUP_NOT_UNIQUE")
    if not matches:
        return None
    return scope._safe_id(
        matches[0].get("id"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_INVALID",
    )


def _require_group_shape(api: scope.ReadOnlyApi, group_id: str) -> None:
    payload = scope._mapping(
        api.get(f"/api/v1/firewall/groups/{group_id}"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_INVALID",
    )
    group = scope._mapping(
        payload.get("group"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_INVALID",
    )
    observed_id = scope._safe_id(
        group.get("id"),
        "TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_INVALID",
    )
    if observed_id != group_id:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_ID_DRIFT")
    if group.get("name") != FIREWALL_NAME:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_GROUP_NAME_DRIFT")
    if group.get("policy") != "DROP":
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_DEFAULT_DROP_REQUIRED")
    if group.get("description") != FIREWALL_DESCRIPTION:
        _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_GROUP_DESCRIPTION_DRIFT")


def _rule_body(verifier_cidr: str) -> dict[str, object]:
    return {
        "description": RULE_DESCRIPTION,
        "direction": "ingress",
        "port": scope.POSTGRES_PORT,
        "protocol": "tcp",
        "cidr": scope._verifier_cidr(verifier_cidr),
    }


def _rule_rows(api: scope.ReadOnlyApi, group_id: str) -> list[dict[str, Any]]:
    return scope._paged_rows(
        api,
        f"/api/v1/firewall/groups/{group_id}/rules",
        "rules",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RULES_INVALID",
    )


def _rule_matches(rule: dict[str, Any], expected: dict[str, object]) -> bool:
    return {
        key: rule.get(key)
        for key in ("description", "direction", "port", "protocol", "cidr")
    } == expected


def _resource_rows(api: scope.ReadOnlyApi, group_id: str) -> list[dict[str, Any]]:
    return scope._paged_rows(
        api,
        f"/api/v1/firewall/groups/{group_id}/resources",
        "resources",
        "TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCES_INVALID",
    )


def _resource_matches(row: dict[str, Any], database_id: str) -> bool:
    try:
        resource_id = scope._safe_id(
            row.get("id"),
            "TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_ID_INVALID",
        )
    except scope.NetworkScopeStopped:
        return False
    return (
        resource_id == database_id
        and row.get("type") in scope._FIREWALL_RESOURCE_TYPES
    )


def _wait_for_named_group(
    api: scope.ReadOnlyApi,
    *,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> str:
    for attempt in range(len(delays) + 1):
        group_id = _named_group_id(api)
        if group_id is not None:
            _require_group_shape(api, group_id)
            return group_id
        if attempt < len(delays):
            sleeper(delays[attempt])
    _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_GROUP_CREATE_RECONCILIATION_REQUIRED")


def _ensure_group(
    mutation: transport.TimewebMutationApi,
    api: scope.ReadOnlyApi,
    *,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> str:
    existing = _named_group_id(api)
    if existing is not None:
        _require_group_shape(api, existing)
        return existing
    try:
        mutation.mutate_once(
            "POST",
            "/api/v1/firewall/groups?policy=DROP",
            operation="PRODUCTION_FIREWALL_GROUP_CREATE",
            body={"name": FIREWALL_NAME, "description": FIREWALL_DESCRIPTION},
            expected_statuses=frozenset({201}),
            reconcile_statuses=_RECONCILE_STATUSES,
        )
    except transport.AmbiguousMutation:
        pass
    return _wait_for_named_group(api, sleeper=sleeper, delays=delays)


def _ensure_rule(
    mutation: transport.TimewebMutationApi,
    api: scope.ReadOnlyApi,
    group_id: str,
    verifier_cidr: str,
    *,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> None:
    expected = _rule_body(verifier_cidr)
    rules = _rule_rows(api, group_id)
    if rules:
        if len(rules) != 1 or not _rule_matches(rules[0], expected):
            _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_RULE_DRIFT")
        return
    try:
        mutation.mutate_once(
            "POST",
            f"/api/v1/firewall/groups/{group_id}/rules",
            operation="PRODUCTION_FIREWALL_RULE_CREATE",
            body=expected,
            expected_statuses=frozenset({201}),
            reconcile_statuses=_RECONCILE_STATUSES,
        )
    except transport.AmbiguousMutation:
        pass
    for attempt in range(len(delays) + 1):
        rules = _rule_rows(api, group_id)
        if len(rules) == 1 and _rule_matches(rules[0], expected):
            return
        if rules:
            _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_BOOTSTRAP_RULE_DRIFT")
        if attempt < len(delays):
            sleeper(delays[attempt])
    _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RULE_RECONCILIATION_FAILED")


def _ensure_resource(
    mutation: transport.TimewebMutationApi,
    api: scope.ReadOnlyApi,
    group_id: str,
    database_id: str,
    *,
    sleeper: Sleep,
    delays: tuple[float, ...],
) -> None:
    resources = _resource_rows(api, group_id)
    if resources:
        if len(resources) != 1 or not _resource_matches(resources[0], database_id):
            _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED")
        return
    path = f"/api/v1/firewall/groups/{group_id}/resources/{database_id}?" + urlencode(
        {"resource_type": "dbaas"}
    )
    try:
        mutation.mutate_once(
            "POST",
            path,
            operation="PRODUCTION_FIREWALL_RESOURCE_LINK",
            expected_statuses=frozenset({201}),
            reconcile_statuses=_RECONCILE_STATUSES,
        )
    except transport.AmbiguousMutation:
        pass
    for attempt in range(len(delays) + 1):
        resources = _resource_rows(api, group_id)
        if len(resources) == 1 and _resource_matches(resources[0], database_id):
            return
        if resources:
            _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_SCOPE_WIDENED")
        if attempt < len(delays):
            sleeper(delays[attempt])
    _stop("TIMEWEB_PG_PRODUCTION_FIREWALL_RESOURCE_LINK_FAILED")


def converge_missing_firewall(
    mutation: transport.TimewebMutationApi,
    api: scope.ReadOnlyApi,
    *,
    database_id: str,
    verifier_cidr: str,
    sleeper: Sleep = time.sleep,
    delays: tuple[float, ...] = _RECONCILE_DELAYS_SECONDS,
) -> None:
    attached = _attached_group_ids(api, database_id)
    if attached:
        return
    group_id = _ensure_group(mutation, api, sleeper=sleeper, delays=delays)
    _ensure_rule(
        mutation,
        api,
        group_id,
        verifier_cidr,
        sleeper=sleeper,
        delays=delays,
    )
    _ensure_resource(
        mutation,
        api,
        group_id,
        database_id,
        sleeper=sleeper,
        delays=delays,
    )


def _provider_runtime_code(exc: RuntimeError) -> str | None:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.startswith("TIMEWEB_"):
        return code
    text = str(exc)
    if text.startswith("TIMEWEB_"):
        return text.split()[0]
    return None


def main() -> int:
    try:
        _required_confirmation()
        api, project_id, host, cidr = scope._runtime_inputs()
        database_id, cluster = scope._select_target_cluster(api, project_id, host)
        availability_zone = scope._require_target_network(cluster, host)
        scope._require_bound_public_ipv4(api, database_id, availability_zone)
        token = provider_base._required_env(scope.TOKEN_ENV)
        mutation = transport.TimewebMutationApi(token)
        converge_missing_firewall(
            mutation,
            api,
            database_id=database_id,
            verifier_cidr=scope._verifier_cidr(cidr),
        )
        scope.verify_network_scope(
            api,
            project_id=project_id,
            target_host=host,
            verifier_cidr=cidr,
        )
    except (ProductionNetworkConvergeStopped, scope.NetworkScopeStopped) as exc:
        print(
            f"TIMEWEB_PG_PRODUCTION_NETWORK_CONVERGE=STOPPED code={exc}",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as exc:
        code = _provider_runtime_code(exc)
        if code is None:
            raise
        print(
            f"TIMEWEB_PG_PRODUCTION_NETWORK_CONVERGE=STOPPED code={code}",
            file=sys.stderr,
        )
        return 1
    print(
        "TIMEWEB_PG_PRODUCTION_NETWORK_CONVERGE=READY "
        "firewall=drop ingress=tcp/5432 source=/32"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
