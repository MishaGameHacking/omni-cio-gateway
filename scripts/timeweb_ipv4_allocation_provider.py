"""Canonical Timeweb adapter for the bounded existing-IPv4 allocation protocol.

The adapter exposes exactly two capabilities to the protocol:

* a complete, fail-closed read snapshot of the one authorized synthetic cluster
  and the complete floating-IPv4 inventory;
* one metadata-only PATCH of the selected floating IP's ``comment`` field.

It cannot create/delete/bind an IP, mutate firewall/network state, or infer
historical creation provenance. Provider response bodies and identifiers never
belong in public diagnostics.
"""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any, NoReturn, Protocol

from scripts import provider_runtime_primitives as _provider_base
from scripts import timeweb_ipv4_allocation as allocation
from scripts import timeweb_ipv4_custody as custody


TARGET_PROJECT_NAME = "Общий проект"
TARGET_LOCATION = "ru-3"
TARGET_ZONE = allocation.ZONE
TARGET_CPU = 1
TARGET_RAM_MB = 2048
TARGET_DISK_KB = 20 * 1024 * 1024
POSTGRES_PORT = 5432
MAX_ROWS = 1000
_ID = re.compile(r"[A-Za-z0-9-]{1,96}", re.ASCII)
_NUMERIC_ID = re.compile(r"[1-9]\d{0,19}", re.ASCII)
_MARKER = re.compile(
    re.escape(allocation.MARKER_PREFIX) + r"[0-9a-f]{64}",
    re.ASCII,
)


class ProviderStopped(allocation.AllocationStopped):
    """Static public code only; never attach provider payloads or identifiers."""


class ReadApi(Protocol):
    def get(self, path: str, *, timeout: float = 30.0) -> Any: ...


class MutationApi(Protocol):
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
    ) -> Any: ...


Emitter = Callable[[str], None]


def _stop(code: str) -> NoReturn:
    raise ProviderStopped(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _stop(code)
    return value


def _rows(payload: object, key: str, code: str) -> list[dict[str, Any]]:
    body = _mapping(payload, code)
    raw = body.get(key)
    if not isinstance(raw, list) or len(raw) > MAX_ROWS:
        _stop(code)
    rows = [_mapping(item, code) for item in raw]
    if "meta" in body:
        meta = _mapping(body["meta"], code)
        if type(meta.get("total")) is not int or meta["total"] != len(rows):
            _stop(code)
    return rows


def _provider_id(value: object, code: str) -> str:
    if type(value) is int and value > 0:
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        _stop(code)
    if _ID.fullmatch(text) is None:
        _stop(code)
    return text


def _numeric_id(value: object, code: str) -> int:
    text = _provider_id(value, code)
    if _NUMERIC_ID.fullmatch(text) is None:
        _stop(code)
    return int(text)


def _exact_positive_int(value: object, code: str) -> int:
    if type(value) is not int or value <= 0:
        _stop(code)
    return value


def _select_project(payload: object) -> tuple[str, str]:
    rows = _rows(payload, "projects", "TIMEWEB_ALLOCATION_PROJECTS_INVALID")
    matches = [row for row in rows if row.get("name") == TARGET_PROJECT_NAME]
    if len(matches) != 1:
        _stop("TIMEWEB_ALLOCATION_PROJECT_NOT_UNIQUE")
    row = matches[0]
    return (
        _provider_id(row.get("id"), "TIMEWEB_ALLOCATION_PROJECT_ID_INVALID"),
        _provider_id(row.get("account_id"), "TIMEWEB_ALLOCATION_ACCOUNT_SCOPE_INVALID"),
    )


def _select_cluster(payload: object) -> int:
    rows = _rows(payload, "databases", "TIMEWEB_ALLOCATION_DATABASES_INVALID")
    matches = [row for row in rows if row.get("name") == allocation.TARGET_NAME]
    if len(matches) != 1:
        _stop("TIMEWEB_ALLOCATION_TARGET_NOT_UNIQUE")
    return _numeric_id(matches[0].get("id"), "TIMEWEB_ALLOCATION_TARGET_ID_INVALID")


def _cluster_identity(
    row: dict[str, Any],
    expected_id: int,
    expected_project_id: str,
) -> None:
    if (
        _numeric_id(row.get("id"), "TIMEWEB_ALLOCATION_TARGET_ID_INVALID")
        != expected_id
        or row.get("name") != allocation.TARGET_NAME
        or row.get("location") != TARGET_LOCATION
        or row.get("availability_zone") != TARGET_ZONE
        or _exact_positive_int(row.get("cpu"), "TIMEWEB_ALLOCATION_CLUSTER_CPU_INVALID")
        != TARGET_CPU
        or _exact_positive_int(row.get("ram"), "TIMEWEB_ALLOCATION_CLUSTER_RAM_INVALID")
        != TARGET_RAM_MB
        or row.get("status") != "started"
        or row.get("is_autobackups_enabled") is not False
        or row.get("is_backup_schedule_enabled") is not False
    ):
        _stop("TIMEWEB_ALLOCATION_CLUSTER_SHAPE_DRIFT")
    project_id = _provider_id(
        row.get("project_id"), "TIMEWEB_ALLOCATION_CLUSTER_PROJECT_ID_INVALID"
    )
    if project_id != expected_project_id:
        _stop("TIMEWEB_ALLOCATION_CLUSTER_PROJECT_DRIFT")


def _cluster_storage(row: dict[str, Any], expected_id: int) -> None:
    if (
        _numeric_id(row.get("port"), "TIMEWEB_ALLOCATION_CLUSTER_PORT_INVALID")
        != POSTGRES_PORT
    ):
        _stop("TIMEWEB_ALLOCATION_CLUSTER_SHAPE_DRIFT")
    disk = _mapping(row.get("disk"), "TIMEWEB_ALLOCATION_CLUSTER_DISK_INVALID")
    size = disk.get("size")
    if (
        isinstance(size, bool)
        or not isinstance(size, (int, float))
        or int(size) != size
    ):
        _stop("TIMEWEB_ALLOCATION_CLUSTER_DISK_INVALID")
    if int(size) != TARGET_DISK_KB:
        _stop("TIMEWEB_ALLOCATION_CLUSTER_SHAPE_DRIFT")
    autoscaling = row.get("disk_autoscaling")
    if autoscaling is not None:
        settings = _mapping(autoscaling, "TIMEWEB_ALLOCATION_CLUSTER_SHAPE_DRIFT")
        if settings.get("is_enabled") is not False:
            _stop("TIMEWEB_ALLOCATION_CLUSTER_SHAPE_DRIFT")
    replicas = row.get("replica_list")
    if not isinstance(replicas, list) or len(replicas) != 1:
        _stop("TIMEWEB_ALLOCATION_CLUSTER_REPLICA_DRIFT")
    replica = _mapping(replicas[0], "TIMEWEB_ALLOCATION_CLUSTER_REPLICA_DRIFT")
    if (
        _numeric_id(replica.get("db_id"), "TIMEWEB_ALLOCATION_CLUSTER_REPLICA_DRIFT")
        != expected_id
    ):
        _stop("TIMEWEB_ALLOCATION_CLUSTER_REPLICA_DRIFT")


def _cluster(
    payload: object,
    expected_id: int,
    expected_project_id: str,
) -> tuple[bool, bool]:
    body = _mapping(payload, "TIMEWEB_ALLOCATION_CLUSTER_INVALID")
    row = _mapping(body.get("db"), "TIMEWEB_ALLOCATION_CLUSTER_INVALID")
    _cluster_identity(row, expected_id, expected_project_id)
    _cluster_storage(row, expected_id)
    public = row.get("is_enabled_public_network")
    ipv6 = row.get("is_enabled_public_ipv6")
    if type(public) is not bool or type(ipv6) is not bool:
        _stop("TIMEWEB_ALLOCATION_CLUSTER_NETWORK_STATE_INVALID")
    return public, ipv6

def _raw_inventory(payload: object) -> list[dict[str, object]]:
    try:
        rows = custody.raw_inventory(payload)
    except custody.CustodyStopped:
        raise ProviderStopped("TIMEWEB_ALLOCATION_IPV4_INVENTORY_INVALID") from None
    if len(rows) != 1:
        _stop("TIMEWEB_ALLOCATION_IPV4_INVENTORY_NOT_UNIQUE")
    return rows


def _address(row: dict[str, object]) -> custody.Address:
    try:
        parsed = custody.inventory([row])
    except custody.CustodyStopped:
        raise ProviderStopped("TIMEWEB_ALLOCATION_IPV4_ROW_INVALID") from None
    if len(parsed) != 1:
        _stop("TIMEWEB_ALLOCATION_IPV4_ROW_INVALID")
    return parsed[0]


def _detail(payload: object) -> dict[str, object]:
    body = _mapping(payload, "TIMEWEB_ALLOCATION_IPV4_DETAIL_INVALID")
    row = body.get("ip")
    if not isinstance(row, dict):
        _stop("TIMEWEB_ALLOCATION_IPV4_DETAIL_INVALID")
    return row


def _ptr(row: dict[str, object]) -> str:
    value = row.get("ptr")
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 253:
        _stop("TIMEWEB_ALLOCATION_IPV4_PTR_INVALID")
    return value


def _same_provider_row(left: dict[str, object], right: dict[str, object]) -> bool:
    return _address(left) == _address(right) and _ptr(left) == _ptr(right)


class TimewebAllocationProvider:
    """Read-complete adapter plus one comment-only metadata writer."""

    def __init__(
        self,
        read_api: ReadApi,
        mutation_api: MutationApi | None = None,
    ) -> None:
        self._read_api = read_api
        self._mutation_api = mutation_api

    def transport_snapshot(self) -> allocation.TransportSnapshot:
        try:
            project_id, account_scope = _select_project(
                self._read_api.get("/api/v1/projects")
            )
            cluster_id = _select_cluster(
                self._read_api.get(f"/api/v1/projects/{project_id}/resources/databases")
            )
            public_enabled, ipv6_enabled = _cluster(
                self._read_api.get(f"/api/v1/databases/{cluster_id}"),
                cluster_id,
                project_id,
            )
            list_row = _raw_inventory(self._read_api.get("/api/v1/floating-ips"))[0]
            parsed = _address(list_row)
            detail_row = _detail(
                self._read_api.get(f"/api/v1/floating-ips/{parsed.identifier}")
            )
            if not _same_provider_row(list_row, detail_row):
                _stop("TIMEWEB_ALLOCATION_IPV4_LIST_DETAIL_DRIFT")
            if _ptr(detail_row) != "":
                _stop("TIMEWEB_ALLOCATION_IPV4_PTR_PRESENT")
            snapshot = allocation.TransportSnapshot(
                account_scope=account_scope,
                project_id=project_id,
                cluster_id=cluster_id,
                floating_id=parsed.identifier,
                ip_address=parsed.ip_address,
                comment=parsed.comment,
                inventory_count=1,
                target_name=allocation.TARGET_NAME,
                zone=parsed.zone,
                ddos_enabled=parsed.ddos,
                resource_type=parsed.resource_type,
                resource_id=parsed.resource_id,
                public_enabled=public_enabled,
                ipv6_enabled=ipv6_enabled,
            )
            allocation._transport_snapshot(snapshot)
            return snapshot
        except ProviderStopped:
            raise
        except allocation.AllocationStopped:
            raise ProviderStopped(
                "TIMEWEB_ALLOCATION_TRANSPORT_SNAPSHOT_INVALID"
            ) from None
        except Exception:
            raise ProviderStopped("TIMEWEB_ALLOCATION_PROVIDER_READ_FAILED") from None

    def snapshot(self) -> allocation.Snapshot:
        current = self.transport_snapshot()
        try:
            snapshot = allocation.Snapshot(
                account_scope=current.account_scope,
                project_id=current.project_id,
                cluster_id=current.cluster_id,
                floating_id=current.floating_id,
                ip_address=current.ip_address,
                comment=current.comment,
                inventory_count=current.inventory_count,
                target_name=current.target_name,
                zone=current.zone,
                ddos_enabled=current.ddos_enabled,
                resource_type=current.resource_type,
                resource_id=current.resource_id,
                public_enabled=current.public_enabled,
                ipv6_enabled=current.ipv6_enabled,
            )
            allocation._snapshot(snapshot)
            return snapshot
        except allocation.AllocationStopped:
            raise ProviderStopped("TIMEWEB_ALLOCATION_SNAPSHOT_INVALID") from None

    def write_comment_once(self, floating_id: str, marker: str) -> None:
        """Perform exactly one PATCH after a fresh complete empty-comment snapshot."""
        mutation_api = self._mutation_api
        if mutation_api is None:
            _stop("TIMEWEB_ALLOCATION_PROVIDER_WRITE_UNAVAILABLE")
        if not isinstance(floating_id, str) or _ID.fullmatch(floating_id) is None:
            _stop("TIMEWEB_ALLOCATION_IPV4_ID_INVALID")
        if not isinstance(marker, str) or _MARKER.fullmatch(marker) is None:
            _stop("TIMEWEB_ALLOCATION_MARKER_INVALID")
        current = self.snapshot()
        if current.floating_id != floating_id or current.comment != "":
            _stop("TIMEWEB_ALLOCATION_PREWRITE_RESOURCE_DRIFT")
        if marker != allocation.expected_marker(current):
            _stop("TIMEWEB_ALLOCATION_MARKER_INVALID")
        try:
            mutation_api.mutate_once(
                "PATCH",
                f"/api/v1/floating-ips/{floating_id}",
                operation="FLOATING_IP_ALLOCATION_COMMENT_PATCH",
                body={"comment": marker},
                expected_statuses=frozenset({200}),
                reconcile_statuses=frozenset({409, 423}),
            )
        except Exception:
            # The protocol owns ambiguity handling: it never retries this write and
            # proves the result with GET-only reconciliation.
            raise ProviderStopped(
                "TIMEWEB_ALLOCATION_PROVIDER_WRITE_AMBIGUOUS"
            ) from None


def live_provider(token: str, *, allow_write: bool) -> TimewebAllocationProvider:
    """Build only from the accepted Timeweb HTTP transports already in the repo."""
    if not isinstance(token, str) or not token:
        _stop("TIMEWEB_ALLOCATION_PROVIDER_TOKEN_REQUIRED")
    try:
        from scripts import probe_v10_timeweb_postgres_control_plane as read_only
        from scripts import provision_v10_timeweb_postgres_public_ipv4_tls as network

        reader = read_only.TimewebReadOnlyApi(token)
        if allow_write:
            read_only.verify_credential_health(reader)
        writer: MutationApi | None = (
            network.TimewebMutationApi(token) if allow_write else None
        )
        return TimewebAllocationProvider(reader, writer)
    except ProviderStopped:
        raise
    except _provider_base.ProvisioningStopped as exc:
        raise ProviderStopped(exc.code) from None
    except Exception:
        raise ProviderStopped("TIMEWEB_ALLOCATION_PROVIDER_INIT_FAILED") from None
