"""Bounded existing-IPv4 allocation protocol; no live provider entry point.

The closed journal and approval verifier are mandatory trusted adapters, not
user-supplied payloads. A durable claim must complete before the sole metadata
write. Re-entering a claimed plan is GET-only, even after a lost write response.
This module neither grants OWNER authority nor certifies transport/SQL readiness.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import ipaddress
import json
import re
import secrets
from typing import Protocol

from scripts import timeweb_ipv4_custody as custody


REPOSITORY = "MishaGameHacking/omni-cio-gateway"
ENVIRONMENT = "timeweb-synthetic"
TARGET_NAME = "omni-cio-v10-ru-pg-synthetic"
ZONE = "msk-1"
PLAN_TTL_SECONDS = 3600
MARKER_PREFIX = custody.MARKER_PREFIX
ALLOCATE_CONFIRMATION = "ALLOCATE_EXISTING_TIMEWEB_IPV4_NO_CREATE_NO_DELETE"
_SHA = re.compile(r"[a-f0-9]{40}", re.ASCII)
_HANDLE = re.compile(r"[a-f0-9]{32}", re.ASCII)
_PROVIDER_ID = re.compile(r"[A-Za-z0-9-]{1,96}", re.ASCII)
_DELAYS = (1.0, 2.0, 4.0)


class AllocationStopped(RuntimeError):
    """Only a fixed public code may be passed; never attach provider payloads."""


class Phase(Enum):
    PLANNED = "PLANNED"
    ATTEMPTED = "ATTEMPTED"
    ALLOCATED = "ALLOCATED"


class CommentState(Enum):
    EMPTY = "EMPTY"
    MATCHING = "MATCHING"
    OTHER_TARGET = "OTHER_TARGET"
    FOREIGN = "FOREIGN"


class Outcome(Enum):
    ALLOCATED_VERIFIED = "ALLOCATED_VERIFIED"
    RECEIPT_RECONCILED = "RECEIPT_RECONCILED"
    RECEIPT_REVERIFIED = "RECEIPT_REVERIFIED"


@dataclass(frozen=True, slots=True, repr=False)
class Context:
    source_sha: str
    current_main_sha: str
    repository: str = REPOSITORY
    environment: str = ENVIRONMENT
    ref: str = "refs/heads/main"


@dataclass(frozen=True, slots=True, repr=False)
class TransportSnapshot:
    """Current provider state used only to prove allocation before transport."""

    account_scope: str
    project_id: str
    cluster_id: int
    floating_id: str
    ip_address: str
    comment: str
    inventory_count: int = 1
    target_name: str = TARGET_NAME
    zone: str = ZONE
    ddos_enabled: bool = False
    resource_type: str | None = None
    resource_id: str | None = None
    public_enabled: bool = False
    ipv6_enabled: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class Snapshot:
    """Exact private values returned by the canonical read-only provider adapter.

    The adapter must validate full canonical DB shape before producing this value.
    Provider account scope is an opaque identifier retained ONLY in closed custody.
    No row may be selected from an incomplete or filtered account inventory.
    """

    account_scope: str
    project_id: str
    cluster_id: int
    floating_id: str
    ip_address: str
    comment: str
    inventory_count: int = 1
    target_name: str = TARGET_NAME
    zone: str = ZONE
    ddos_enabled: bool = False
    resource_type: str | None = None
    resource_id: str | None = None
    public_enabled: bool = False
    ipv6_enabled: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class Plan:
    identifier: str
    context: Context
    snapshot: Snapshot
    issued_at: int
    expires_at: int
    digest: str


@dataclass(frozen=True, slots=True, repr=False)
class Entry:
    plan: Plan
    phase: Phase
    approval_reference: str | None = None


@dataclass(frozen=True, slots=True, repr=False)
class OwnerApproval:
    """Authentic evidence resolved by the verifier, never a browser/chat payload."""

    reference: str
    plan_id: str
    plan_digest: str
    source_sha: str
    approved_at: int
    expires_at: int
    purpose: str = ALLOCATE_CONFIRMATION
    revoked: bool = False


class ClosedJournal(Protocol):
    """Authenticated, durable, private and serializable storage, not CI artifacts.

    create: no overwrite; deny another active plan for the same target OR IP.
    claim: atomically PLANNED -> ATTEMPTED, pin the approval reference, then fsync
    or equivalent durable acknowledgement BEFORE returning True. A racing caller
    returns False. Exceptions are ambiguous; callers MUST NOT mutate the provider.
    complete: only ATTEMPTED -> ALLOCATED for the exact plan/claim after GET proof.
    Never release an ATTEMPTED claim merely because its plan's TTL has expired.
    """

    def create(self, plan: Plan) -> None: ...

    def read(self, identifier: str) -> Entry: ...

    def claim(self, identifier: str, digest: str, approval_reference: str) -> bool: ...

    def complete(self, identifier: str, digest: str) -> None: ...


class ApprovalVerifier(Protocol):
    """Resolve authentic OWNER evidence from its trusted source and reject errors.

    Must bind exact plan identifier/digest/source/target, purpose, expiry and
    revocation. A bool, a chat development request, cost approval, PR merge,
    unsigned JSON or a user-supplied actor string is NOT approval evidence.
    """

    def verify(self, reference: str, plan: Plan, now: int) -> OwnerApproval: ...


ReadSnapshot = Callable[[], Snapshot]
ReadTransportSnapshot = Callable[[], TransportSnapshot]
WriteCommentOnce = Callable[[str, str], None]
Clock = Callable[[], int]
ReadContext = Callable[[], Context]
Sleep = Callable[[float], None]


def _context(context: Context) -> None:
    if (
        not isinstance(context, Context)
        or context.repository != REPOSITORY
        or context.environment != ENVIRONMENT
        or context.ref != "refs/heads/main"
        or not isinstance(context.source_sha, str)
        or _SHA.fullmatch(context.source_sha) is None
        or context.current_main_sha != context.source_sha
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_SOURCE_AUTHORITY_INVALID")


def _current_source(read_context: ReadContext, expected: Context) -> None:
    try:
        current = read_context()
    except Exception:
        raise AllocationStopped(
            "TIMEWEB_ALLOCATION_MAIN_OBSERVATION_UNAVAILABLE"
        ) from None
    _context(current)
    if current != expected:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_SOURCE_DRIFT")


def _instant(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise AllocationStopped("TIMEWEB_ALLOCATION_CLOCK_INVALID")
    return value


def _snapshot_common(snapshot: Snapshot | TransportSnapshot) -> None:
    for identifier in (
        snapshot.account_scope,
        snapshot.project_id,
        snapshot.floating_id,
    ):
        if (
            not isinstance(identifier, str)
            or _PROVIDER_ID.fullmatch(identifier) is None
        ):
            raise AllocationStopped("TIMEWEB_ALLOCATION_SCOPE_INVALID")
    if type(snapshot.cluster_id) is not int or snapshot.cluster_id <= 0:
        raise AllocationStopped("TIMEWEB_ALLOCATION_TARGET_INVALID")
    if (
        type(snapshot.inventory_count) is not int
        or snapshot.inventory_count != 1
        or snapshot.target_name != TARGET_NAME
        or snapshot.zone != ZONE
        or snapshot.ddos_enabled is not False
        or type(snapshot.public_enabled) is not bool
        or type(snapshot.ipv6_enabled) is not bool
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_SHAPE_OR_BINDING_DRIFT")
    if not isinstance(snapshot.ip_address, str):
        raise AllocationStopped("TIMEWEB_ALLOCATION_IP_INVALID")
    try:
        address = ipaddress.ip_address(snapshot.ip_address)
    except ValueError:
        raise AllocationStopped("TIMEWEB_ALLOCATION_IP_INVALID") from None
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or not address.is_global
        or str(address) != snapshot.ip_address
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_IP_INVALID")
    if not isinstance(snapshot.comment, str) or len(snapshot.comment) > 4096:
        raise AllocationStopped("TIMEWEB_ALLOCATION_COMMENT_INVALID")


def _snapshot(snapshot: Snapshot) -> None:
    if not isinstance(snapshot, Snapshot):
        raise AllocationStopped("TIMEWEB_ALLOCATION_SNAPSHOT_INVALID")
    _snapshot_common(snapshot)
    if (
        snapshot.resource_type is not None
        or snapshot.resource_id is not None
        or snapshot.public_enabled is not False
        or snapshot.ipv6_enabled is not False
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_SHAPE_OR_BINDING_DRIFT")


def _transport_snapshot(snapshot: TransportSnapshot) -> None:
    if not isinstance(snapshot, TransportSnapshot):
        raise AllocationStopped("TIMEWEB_ALLOCATION_TRANSPORT_SNAPSHOT_INVALID")
    _snapshot_common(snapshot)
    unbound = snapshot.resource_type is None and snapshot.resource_id is None
    target_bound = (
        snapshot.resource_type in {"database", "dbaas"}
        and snapshot.resource_id == str(snapshot.cluster_id)
    )
    if not (unbound or target_bound):
        raise AllocationStopped("TIMEWEB_ALLOCATION_TRANSPORT_RESOURCE_DRIFT")


def expected_marker(snapshot: Snapshot) -> str:
    """Preserve the accepted custody-v1 preimage; do not invent creation history."""
    _snapshot(snapshot)
    row = custody.Address(
        snapshot.floating_id,
        snapshot.ip_address,
        snapshot.zone,
        snapshot.ddos_enabled,
        snapshot.resource_type,
        snapshot.resource_id,
        snapshot.comment,
    )
    return custody.marker(snapshot.cluster_id, row)


def comment_state(snapshot: Snapshot) -> CommentState:
    _snapshot(snapshot)
    if snapshot.comment == "":
        return CommentState.EMPTY
    if snapshot.comment == expected_marker(snapshot):
        return CommentState.MATCHING
    if snapshot.comment.startswith(MARKER_PREFIX):
        return CommentState.OTHER_TARGET
    return CommentState.FOREIGN


def _private_digest(
    identifier: str,
    context: Context,
    snapshot: Snapshot,
    issued_at: int,
    expires_at: int,
) -> str:
    # This checksum is not authentication and MUST remain inside closed custody.
    payload = [
        "omni-cio.ru-pg-b.existing-ipv4-allocation.v1",
        identifier,
        context.repository,
        context.environment,
        context.ref,
        context.source_sha,
        snapshot.account_scope,
        snapshot.project_id,
        snapshot.cluster_id,
        snapshot.target_name,
        snapshot.floating_id,
        snapshot.ip_address,
        snapshot.zone,
        snapshot.ddos_enabled,
        snapshot.resource_type,
        snapshot.resource_id,
        snapshot.public_enabled,
        snapshot.ipv6_enabled,
        snapshot.inventory_count,
        snapshot.comment,
        issued_at,
        expires_at,
    ]
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _plan(plan: Plan, context: Context) -> None:
    _context(context)
    if not isinstance(plan, Plan):
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_INVALID")
    _context(plan.context)
    if plan.context != context:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_SOURCE_DRIFT")
    _snapshot(plan.snapshot)
    if (
        not isinstance(plan.identifier, str)
        or _HANDLE.fullmatch(plan.identifier) is None
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_ID_INVALID")
    issued_at = _instant(plan.issued_at)
    expires_at = _instant(plan.expires_at)
    if expires_at - issued_at != PLAN_TTL_SECONDS or plan.snapshot.comment != "":
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_INVALID")
    expected = _private_digest(
        plan.identifier, plan.context, plan.snapshot, issued_at, expires_at
    )
    if plan.digest != expected:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_INTEGRITY_INVALID")


def _fresh(plan: Plan, now: int) -> None:
    now = _instant(now)
    if not plan.issued_at <= now < plan.expires_at:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_EXPIRED_OR_FUTURE")


def _read_transport(
    read_snapshot: ReadTransportSnapshot,
) -> TransportSnapshot:
    try:
        snapshot = read_snapshot()
        _transport_snapshot(snapshot)
        return snapshot
    except AllocationStopped:
        raise
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_OBSERVATION_UNAVAILABLE") from None


def _read(read_snapshot: ReadSnapshot) -> Snapshot:
    try:
        snapshot = read_snapshot()
        _snapshot(snapshot)
        return snapshot
    except AllocationStopped:
        raise
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_OBSERVATION_UNAVAILABLE") from None


def _journal_read(journal: ClosedJournal, identifier: str, context: Context) -> Entry:
    if not isinstance(identifier, str) or _HANDLE.fullmatch(identifier) is None:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_ID_INVALID")
    try:
        entry = journal.read(identifier)
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_UNAVAILABLE") from None
    if not isinstance(entry, Entry) or not isinstance(entry.phase, Phase):
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_INVALID")
    _plan(entry.plan, context)
    if entry.plan.identifier != identifier:
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_ID_DRIFT")
    if entry.phase is not Phase.PLANNED and not entry.approval_reference:
        raise AllocationStopped("TIMEWEB_ALLOCATION_CLAIM_UNPROVEN")
    return entry


def prepare(
    read_snapshot: ReadSnapshot,
    journal: ClosedJournal,
    context: Context,
    *,
    clock: Clock,
    read_context: ReadContext,
) -> str:
    """Store an exact private plan and return only a random, non-authorizing handle."""
    _context(context)
    _current_source(read_context, context)
    first = _read(read_snapshot)
    if comment_state(first) is not CommentState.EMPTY:
        raise AllocationStopped("TIMEWEB_ALLOCATION_EXISTING_ASSOCIATION_FORBIDDEN")
    if _read(read_snapshot) != first:
        raise AllocationStopped("TIMEWEB_ALLOCATION_OBSERVATION_DRIFT")
    issued_at = _instant(clock())
    expires_at = issued_at + PLAN_TTL_SECONDS
    identifier = secrets.token_hex(16)
    plan = Plan(
        identifier,
        context,
        first,
        issued_at,
        expires_at,
        _private_digest(identifier, context, first, issued_at, expires_at),
    )
    _plan(plan, context)
    _current_source(read_context, context)
    try:
        journal.create(plan)
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_SAVE_UNPROVEN") from None
    stored = _journal_read(journal, identifier, context)
    if stored.plan != plan or stored.phase is not Phase.PLANNED:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_SAVE_UNPROVEN")
    return identifier


def _matches(snapshot: Snapshot, planned: Snapshot, comment: str) -> bool:
    # Compare all private fields, not only compatible shape or floating-id.
    return snapshot == replace(planned, comment=comment)


def _verify_approval(
    verifier: ApprovalVerifier, reference: str, plan: Plan, clock: Clock
) -> None:
    if not isinstance(reference, str) or not 1 <= len(reference) <= 256:
        raise AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_REQUIRED")
    if any(ord(char) < 33 or ord(char) > 126 for char in reference):
        raise AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_REQUIRED")
    now = _instant(clock())
    _fresh(plan, now)
    try:
        approval = verifier.verify(reference, plan, now)
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_UNPROVEN") from None
    if (
        not isinstance(approval, OwnerApproval)
        or approval.reference != reference
        or approval.plan_id != plan.identifier
        or approval.plan_digest != plan.digest
        or approval.source_sha != plan.context.source_sha
        or approval.purpose != ALLOCATE_CONFIRMATION
        or approval.revoked is not False
        or type(approval.approved_at) is not int
        or type(approval.expires_at) is not int
        or not plan.issued_at <= approval.approved_at <= now
        or not now < approval.expires_at <= plan.expires_at
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_APPROVAL_UNPROVEN")


def _finish(journal: ClosedJournal, entry: Entry) -> None:
    if entry.phase is Phase.ATTEMPTED:
        try:
            journal.complete(entry.plan.identifier, entry.plan.digest)
        except Exception:
            raise AllocationStopped(
                "TIMEWEB_ALLOCATION_RECEIPT_SAVE_UNPROVEN"
            ) from None
    stored = _journal_read(journal, entry.plan.identifier, entry.plan.context)
    if (
        stored.plan != entry.plan
        or stored.approval_reference != entry.approval_reference
        or stored.phase is not Phase.ALLOCATED
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_RECEIPT_SAVE_UNPROVEN")


def _observe_result(
    read_snapshot: ReadSnapshot,
    journal: ClosedJournal,
    entry: Entry,
    *,
    sleeper: Sleep,
) -> None:
    planned = entry.plan.snapshot
    expected = expected_marker(planned)
    for attempt in range(len(_DELAYS) + 1):
        current = _read(read_snapshot)
        if _matches(current, planned, expected):
            if _read(read_snapshot) != current:
                raise AllocationStopped("TIMEWEB_ALLOCATION_RECEIPT_DRIFT")
            _finish(journal, entry)
            return
        if not _matches(current, planned, ""):
            raise AllocationStopped("TIMEWEB_ALLOCATION_RECEIPT_DRIFT")
        if attempt < len(_DELAYS):
            sleeper(_DELAYS[attempt])
    raise AllocationStopped("TIMEWEB_ALLOCATION_OUTCOME_UNKNOWN_RECONCILE_ONLY")


def reconcile(
    identifier: str,
    read_snapshot: ReadSnapshot,
    journal: ClosedJournal,
    context: Context,
    *,
    sleeper: Sleep,
) -> Outcome:
    """GET-only after any durable attempt, including expired or lost-response plans.

    Expiry blocks writes, not investigation. There is deliberately no writer
    argument. This may verify metadata but never proves network or SQL readiness.
    """
    entry = _journal_read(journal, identifier, context)
    if entry.phase is Phase.PLANNED:
        raise AllocationStopped("TIMEWEB_ALLOCATION_NOT_ATTEMPTED")
    _observe_result(read_snapshot, journal, entry, sleeper=sleeper)
    if entry.phase is Phase.ALLOCATED:
        return Outcome.RECEIPT_REVERIFIED
    return Outcome.RECEIPT_RECONCILED


def apply(
    identifier: str,
    approval_reference: str,
    confirmation: str,
    read_snapshot: ReadSnapshot,
    write_comment_once: WriteCommentOnce,
    journal: ClosedJournal,
    verifier: ApprovalVerifier,
    context: Context,
    *,
    clock: Clock,
    sleeper: Sleep,
    read_context: ReadContext,
) -> Outcome:
    """Authorize, persist the attempt, write comment once, then prove it by GET.

    A repeated apply cannot retry a mutation: callers must use reconcile.
    Neither an unknown response nor an expired plan releases the durable claim.
    """
    if confirmation != ALLOCATE_CONFIRMATION:
        raise AllocationStopped("TIMEWEB_ALLOCATION_CONFIRMATION_REQUIRED")
    entry = _journal_read(journal, identifier, context)
    if entry.phase is not Phase.PLANNED:
        raise AllocationStopped("TIMEWEB_ALLOCATION_ALREADY_ATTEMPTED_RECONCILE_ONLY")
    plan = entry.plan
    _verify_approval(verifier, approval_reference, plan, clock)
    if _read(read_snapshot) != plan.snapshot or _read(read_snapshot) != plan.snapshot:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_RESOURCE_DRIFT")
    # Approval may have expired/revoked while the provider GETs were running.
    _verify_approval(verifier, approval_reference, plan, clock)
    _current_source(read_context, context)
    try:
        claimed = journal.claim(identifier, plan.digest, approval_reference)
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_CLAIM_UNPROVEN") from None
    if claimed is not True:
        raise AllocationStopped("TIMEWEB_ALLOCATION_CLAIM_CONFLICT")
    claimed_entry = _journal_read(journal, identifier, context)
    if (
        claimed_entry.plan != plan
        or claimed_entry.phase is not Phase.ATTEMPTED
        or claimed_entry.approval_reference != approval_reference
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_CLAIM_UNPROVEN")
    if _read(read_snapshot) != plan.snapshot:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_RESOURCE_DRIFT")
    _verify_approval(verifier, approval_reference, plan, clock)
    _current_source(read_context, context)
    try:
        write_comment_once(plan.snapshot.floating_id, expected_marker(plan.snapshot))
    except Exception:
        # A rejection/lost response cannot authorize retry. GET decides the outcome.
        # Raw exception data and provider values never enter public diagnostics.
        pass
    _observe_result(read_snapshot, journal, claimed_entry, sleeper=sleeper)
    return Outcome.ALLOCATED_VERIFIED


def _transport_matches(
    current: TransportSnapshot,
    planned: Snapshot,
    expected_comment: str,
) -> bool:
    return (
        current.account_scope == planned.account_scope
        and current.project_id == planned.project_id
        and current.cluster_id == planned.cluster_id
        and current.floating_id == planned.floating_id
        and current.ip_address == planned.ip_address
        and current.comment == expected_comment
        and current.inventory_count == planned.inventory_count
        and current.target_name == planned.target_name
        and current.zone == planned.zone
        and current.ddos_enabled == planned.ddos_enabled
    )


def verify_transport_prerequisite(
    identifier: str,
    read_snapshot: ReadTransportSnapshot,
    journal: ClosedJournal,
) -> Outcome:
    """Bind a durable ALLOCATED receipt to the current exact managed resource."""
    if not isinstance(identifier, str) or _HANDLE.fullmatch(identifier) is None:
        raise AllocationStopped("TIMEWEB_ALLOCATION_PLAN_ID_INVALID")
    try:
        entry = journal.read(identifier)
    except Exception:
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_UNAVAILABLE") from None
    if not isinstance(entry, Entry) or not isinstance(entry.phase, Phase):
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_INVALID")
    _plan(entry.plan, entry.plan.context)
    if entry.plan.identifier != identifier:
        raise AllocationStopped("TIMEWEB_ALLOCATION_JOURNAL_ID_DRIFT")
    if (
        entry.phase is not Phase.ALLOCATED
        or not isinstance(entry.approval_reference, str)
        or not entry.approval_reference
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_TRANSPORT_RECEIPT_REQUIRED")

    expected = expected_marker(entry.plan.snapshot)
    current = _read_transport(read_snapshot)
    if not _transport_matches(current, entry.plan.snapshot, expected):
        raise AllocationStopped("TIMEWEB_ALLOCATION_TRANSPORT_RESOURCE_DRIFT")
    if _read_transport(read_snapshot) != current:
        raise AllocationStopped("TIMEWEB_ALLOCATION_TRANSPORT_RESOURCE_DRIFT")
    return Outcome.RECEIPT_REVERIFIED


def safe_summary(identifier: str, state: str) -> str:
    """No plan digest, raw snapshot, approval payload, provider IDs or addresses."""
    states = {
        "OWNER_APPROVAL_REQUIRED",
        "RECONCILIATION_REQUIRED",
        "ALLOCATION_VERIFIED_TRANSPORT_NOT_VERIFIED",
    }
    if (
        not isinstance(identifier, str)
        or _HANDLE.fullmatch(identifier) is None
        or not isinstance(state, str)
        or state not in states
    ):
        raise AllocationStopped("TIMEWEB_ALLOCATION_SUMMARY_INVALID")
    return f"TIMEWEB_IPV4_ALLOCATION_PLAN={identifier} state={state}"
