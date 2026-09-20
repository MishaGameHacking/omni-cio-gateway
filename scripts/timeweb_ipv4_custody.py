"""Fail-closed selection and recovery of the one RU-PG-B floating IPv4.

Provider comments are management associations in the trusted account, not signed
creation history. Only a verified current-create receipt may be stamped. An
unmarked pre-existing address is never adopted, even when it is the only match.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import re
import time


ZONE = "msk-1"
MARKER_PREFIX = "omni-cio:ru-pg-b:ipv4:v1:"
_MAX_ROWS = 1000
_ID = re.compile(r"[A-Za-z0-9-]{1,96}", re.ASCII)
_RESOURCE_TYPE = re.compile(r"[a-z][a-z0-9_-]{0,63}", re.ASCII)
_DB_TYPES = frozenset({"database", "dbaas"})
_DELAYS = (1.0, 2.0, 4.0)


class CustodyStopped(RuntimeError):
    """Contains a static code only, never a provider value."""


@dataclass(frozen=True, slots=True, repr=False)
class Address:
    identifier: str
    address: str
    zone: str
    ddos: bool
    resource_type: str | None
    resource_id: str | None
    comment: str

    @property
    def unbound(self) -> bool:
        return self.resource_type is None and self.resource_id is None


def _identifier(value: object) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_ID_INVALID")
    return value


def _address(value: object) -> str:
    if not isinstance(value, str):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_ADDRESS_INVALID")
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_ADDRESS_INVALID") from None
    if not isinstance(parsed, ipaddress.IPv4Address) or not parsed.is_global:
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_ADDRESS_INVALID")
    return str(parsed)


def _binding_identifier(kind: str, identifier: object) -> str:
    if type(identifier) is int and identifier > 0:
        return str(identifier)
    if isinstance(identifier, str) and _ID.fullmatch(identifier) is not None:
        if kind in _DB_TYPES and re.fullmatch(r"[1-9][0-9]{0,19}", identifier) is None:
            raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")
        return identifier
    raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")


def _binding(row: dict[str, object]) -> tuple[str | None, str | None]:
    if "resource_type" not in row or "resource_id" not in row:
        raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")
    kind = row["resource_type"]
    identifier = row["resource_id"]
    # bool/float zero must not masquerade as the provider's integer-zero sentinel.
    empty_id = (
        identifier is None
        or identifier == ""
        or (type(identifier) is int and identifier == 0)
    )
    if kind is None or kind == "":
        if not empty_id:
            raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")
        return None, None
    if not isinstance(kind, str) or _RESOURCE_TYPE.fullmatch(kind) is None:
        raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")
    return kind, _binding_identifier(kind, identifier)


def is_unbound(raw: object) -> bool:
    """Reject missing/malformed binding evidence before any create or cleanup."""
    if not isinstance(raw, dict):
        raise CustodyStopped("TIMEWEB_IPV4_BINDING_STATE_UNKNOWN")
    return _binding(raw) == (None, None)


def _row(raw: object) -> Address:
    if not isinstance(raw, dict):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_ROW_INVALID")
    identifier = _identifier(raw.get("id"))
    address = _address(raw.get("ip"))
    zone = raw.get("availability_zone")
    ddos = raw.get("is_ddos_guard")
    if (
        not isinstance(zone, str)
        or _ID.fullmatch(zone) is None
        or type(ddos) is not bool
    ):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_SHAPE_UNKNOWN")
    kind, resource_id = _binding(raw)
    comment = raw.get("comment")
    if comment is None:
        comment = ""
    if not isinstance(comment, str) or len(comment) > 4096:
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_COMMENT_INVALID")
    return Address(identifier, address, zone, ddos, kind, resource_id, comment)


def inventory(payload: object) -> tuple[Address, ...]:
    if not isinstance(payload, list) or len(payload) > _MAX_ROWS:
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_INVALID")
    result = tuple(_row(row) for row in payload)
    if len({row.identifier for row in result}) != len(result):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_DUPLICATE_ID")
    if len({row.address for row in result}) != len(result):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_DUPLICATE_ADDRESS")
    return result


def raw_inventory(payload: object) -> list[dict[str, object]]:
    """Reject truncation metadata; the provider endpoint otherwise returns all IPs."""
    if not isinstance(payload, dict):
        raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_INVALID")
    rows = payload.get("ips")
    inventory(rows)
    if "meta" in payload:
        meta = payload["meta"]
        if (
            not isinstance(meta, dict)
            or type(meta.get("total")) is not int
            or meta["total"] != len(rows)
        ):
            raise CustodyStopped("TIMEWEB_IPV4_INVENTORY_INCOMPLETE")
    return rows


def _target(cluster_id: int) -> str:
    if type(cluster_id) is not int or cluster_id <= 0:
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_TARGET_INVALID")
    return str(cluster_id)


def marker(cluster_id: int, row: Address) -> str:
    """Bind the association to the exact target, IP identity, address and zone."""
    payload = [
        "MishaGameHacking/omni-cio-gateway",
        "RU-PG-B",
        "omni-cio-v10-ru-pg-synthetic",
        _target(cluster_id),
        ZONE,
        row.identifier,
        row.address,
    ]
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return MARKER_PREFIX + digest


def _target_bound(row: Address, cluster_id: int) -> bool:
    return row.resource_type in _DB_TYPES and row.resource_id == _target(cluster_id)


def observation(rows: tuple[Address, ...], cluster_id: int) -> str:
    """Only fixed field names and aggregate integers cross the evidence boundary."""
    _target(cluster_id)
    free = tuple(row for row in rows if row.unbound)
    managed = sum(row.comment == marker(cluster_id, row) for row in free)
    return (
        "TIMEWEB_RU_PG_IPV4_INVENTORY=OBSERVED "
        f"total={len(rows)} unbound={len(free)} managed_unbound={managed} "
        f"unproven_unbound={len(free) - managed} "
        f"wrong_zone_unbound={sum(row.zone != ZONE for row in free)} "
        f"ddos_unbound={sum(row.ddos for row in free)} "
        f"target_bound={sum(_target_bound(row, cluster_id) for row in rows)}"
    )


def _shape(row: Address) -> None:
    if row.zone != ZONE or row.ddos:
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_SHAPE_DRIFT")


def _unique_custody(
    bound: tuple[Address, ...],
    managed: tuple[Address, ...],
    cluster_id: int,
) -> None:
    if len(bound) > 1 or len(managed) > 1:
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_NOT_UNIQUE")
    if managed and not (managed[0].unbound or _target_bound(managed[0], cluster_id)):
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_BOUND_ELSEWHERE")
    if bound and managed and managed[0] != bound[0]:
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_NOT_UNIQUE")


def select(
    rows: tuple[Address, ...],
    cluster_id: int,
    *,
    public_enabled: bool,
) -> Address | None:
    """None means create-once is eligible; it never means adopt an unknown IP."""
    _target(cluster_id)
    if type(public_enabled) is not bool:
        raise CustodyStopped("TIMEWEB_IPV4_PUBLIC_STATE_UNKNOWN")
    bound = tuple(row for row in rows if _target_bound(row, cluster_id))
    managed = tuple(row for row in rows if row.comment == marker(cluster_id, row))
    _unique_custody(bound, managed, cluster_id)
    if bound:
        _shape(bound[0])
        return bound[0]
    if public_enabled:
        raise CustodyStopped("TIMEWEB_PUBLIC_NETWORK_WITHOUT_MANAGED_IPV4")
    free = tuple(row for row in rows if row.unbound)
    if len(free) > 1:
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_NOT_UNIQUE")
    if not free:
        return None
    _shape(free[0])
    if free[0].comment != marker(cluster_id, free[0]):
        raise CustodyStopped("TIMEWEB_IPV4_ORPHAN_PROVENANCE_REQUIRED")
    return free[0]


def disposition(
    rows: tuple[Address, ...],
    cluster_id: int,
    *,
    public_enabled: bool,
) -> str:
    """A successful observation can report BLOCKED, never network/SQL PASS."""
    try:
        selected = select(rows, cluster_id, public_enabled=public_enabled)
    except CustodyStopped as exc:
        return f"TIMEWEB_RU_PG_IPV4_RECOVERY=BLOCKED code={exc}"
    if selected is None:
        action = "CREATE_ONCE"
    elif selected.unbound:
        action = "RECOVER_MANAGED"
    else:
        action = "REUSE_BOUND"
    return f"TIMEWEB_RU_PG_IPV4_RECOVERY=ELIGIBLE action={action}"


ReadRows = Callable[[], object]
CreateOnce = Callable[[], tuple[str, str, bool]]
StampOnce = Callable[[str, str], None]
DeleteOnce = Callable[[str], None]


def _same_identity(actual: Address, expected: Address) -> bool:
    return (
        actual.identifier == expected.identifier
        and actual.address == expected.address
        and actual.zone == expected.zone
        and actual.ddos == expected.ddos
    )


def _created_receipt(
    before: tuple[Address, ...],
    after: tuple[Address, ...],
    receipt: tuple[str, str, bool],
) -> Address:
    identifier, address, created = receipt
    _identifier(identifier)
    _address(address)
    if created is not True:
        raise CustodyStopped("TIMEWEB_IPV4_CREATE_RECEIPT_INVALID")
    old_ids = {row.identifier for row in before}
    new_rows = tuple(row for row in after if row.identifier not in old_ids)
    if len(new_rows) != 1:
        raise CustodyStopped("TIMEWEB_IPV4_CREATE_RECEIPT_NOT_UNIQUE")
    row = new_rows[0]
    if row.identifier != identifier or row.address != address or not row.unbound:
        raise CustodyStopped("TIMEWEB_IPV4_CREATE_RECEIPT_DRIFT")
    _shape(row)
    if row.comment:
        raise CustodyStopped("TIMEWEB_IPV4_CREATE_COMMENT_NOT_EMPTY")
    return row


def _wait_created_receipt(
    read_rows: ReadRows,
    before: tuple[Address, ...],
    receipt: tuple[str, str, bool],
    *,
    sleeper: Callable[[float], None],
) -> Address:
    # A successful response may precede list visibility. Only GET is retried;
    # any visible conflicting delta is rejected instead of choosing a candidate.
    old_ids = {row.identifier for row in before}
    for attempt in range(len(_DELAYS) + 1):
        after = inventory(read_rows())
        if any(row.identifier not in old_ids for row in after):
            return _created_receipt(before, after, receipt)
        if attempt < len(_DELAYS):
            sleeper(_DELAYS[attempt])
    raise CustodyStopped("TIMEWEB_IPV4_CREATE_RECEIPT_NOT_VISIBLE")


def _current_created(rows: tuple[Address, ...], created: Address) -> Address:
    current = tuple(row for row in rows if row.identifier == created.identifier)
    if (
        len(current) != 1
        or not _same_identity(current[0], created)
        or not current[0].unbound
    ):
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_STAMP_DRIFT")
    return current[0]


def _stamped_receipt(
    read_rows: ReadRows,
    cluster_id: int,
    created: Address,
    *,
    sleeper: Callable[[float], None],
) -> Address:
    for attempt in range(len(_DELAYS) + 1):
        rows = inventory(read_rows())
        current = _current_created(rows, created)
        if current.comment == marker(cluster_id, current):
            selected = select(rows, cluster_id, public_enabled=False)
            if selected != current:
                raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_STAMP_DRIFT")
            return current
        if current.comment:
            raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_STAMP_DRIFT")
        if attempt < len(_DELAYS):
            sleeper(_DELAYS[attempt])
    raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_STAMP_UNPROVEN")


def _cleanup_created(
    read_rows: ReadRows,
    delete_once: DeleteOnce,
    cluster_id: int,
    created: Address,
) -> None:
    current = tuple(
        row for row in inventory(read_rows()) if row.identifier == created.identifier
    )
    if not current:
        return
    if (
        len(current) != 1
        or not _same_identity(current[0], created)
        or not current[0].unbound
        or current[0].comment not in {"", marker(cluster_id, current[0])}
    ):
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_CLEANUP_UNPROVEN")
    delete_once(created.identifier)
    if any(row.identifier == created.identifier for row in inventory(read_rows())):
        raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_CLEANUP_UNPROVEN")


def resolve(
    read_rows: ReadRows,
    create_once: CreateOnce,
    stamp_once: StampOnce,
    delete_once: DeleteOnce,
    cluster_id: int,
    *,
    public_enabled: bool,
    emit: Callable[[str], None],
    sleeper: Callable[[float], None] = time.sleep,
) -> tuple[str, str, bool]:
    before = inventory(read_rows())
    emit(observation(before, cluster_id))
    selected = select(before, cluster_id, public_enabled=public_enabled)
    if selected is not None:
        # A second GET must agree. No purchase, stamping, deletion or stealing
        # authority is inherited from recovering a previously managed address.
        fresh = select(
            inventory(read_rows()), cluster_id, public_enabled=public_enabled
        )
        if fresh != selected:
            raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_RECOVERY_DRIFT")
        return selected.identifier, selected.address, False
    receipt = create_once()
    created = _wait_created_receipt(read_rows, before, receipt, sleeper=sleeper)
    try:
        stamp_once(created.identifier, marker(cluster_id, created))
        verified = _stamped_receipt(read_rows, cluster_id, created, sleeper=sleeper)
    except Exception:
        try:
            _cleanup_created(read_rows, delete_once, cluster_id, created)
        except Exception:
            raise CustodyStopped("TIMEWEB_IPV4_CUSTODY_CLEANUP_UNPROVEN") from None
        raise
    return verified.identifier, verified.address, True
