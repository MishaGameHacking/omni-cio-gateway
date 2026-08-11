from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import secrets
import threading
from typing import Any, Protocol

from omni_cio.adapters.tinvest_connection_v1 import TInvestConnectionReadAdapter
from omni_cio.adapters.tinvest_read_v1 import FreshnessState, TInvestSnapshotResultV1
from omni_cio.web.persistence_v1 import BrokerConnectionRecordV1


_PENDING_MARKER = "OMNI-CIO-V10-WP15-LIVE-PENDING-v1"
_PENDING_MARKER_NAME = ".omni-cio-wp15-live-pending"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BrokerLiveAcceptanceError(RuntimeError):
    """Fail-closed live acceptance error with a fixed non-sensitive reason code."""


class BrokerRepositoryLike(Protocol):
    def list_read_connections(
        self, *, tenant_id: str
    ) -> tuple[BrokerConnectionRecordV1, ...]: ...


class ReadConnectionVaultLike(Protocol):
    def load(self, secret_ref: str) -> str: ...


class SnapshotAdapterLike(Protocol):
    def read_snapshot(
        self, *, allow_partial: bool = False
    ) -> TInvestSnapshotResultV1: ...


@dataclass(frozen=True, slots=True)
class LiveAcceptanceSampleV1:
    label: str
    quantity: str
    unit_price: str
    market_value: str
    currency: str


@dataclass(frozen=True, slots=True)
class LiveAcceptanceViewV1:
    challenge_id: str
    expires_at: datetime
    masked_account: str
    access_level: str
    portfolio_total: str
    portfolio_currency: str
    sample: LiveAcceptanceSampleV1
    freshness_state: str
    retrieved_at: datetime
    evaluated_at: datetime
    age_seconds: str
    normalized_position_count: int


@dataclass(frozen=True, slots=True)
class _LiveChallengeV1:
    user_id: str
    tenant_id: str
    expires_at: datetime
    view: LiveAcceptanceViewV1


class PendingLiveAcceptanceEvidenceWriterV1:
    """Write only sanitized pending evidence into a pre-provisioned local boundary."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def write(self, payload: dict[str, Any]) -> None:
        parent = self._path.parent
        marker = parent / _PENDING_MARKER_NAME
        if not parent.is_dir() or not marker.is_file():
            raise BrokerLiveAcceptanceError("WP15_LIVE_PENDING_BOUNDARY_NOT_READY")
        try:
            if marker.read_text(encoding="ascii").strip() != _PENDING_MARKER:
                raise BrokerLiveAcceptanceError("WP15_LIVE_PENDING_BOUNDARY_NOT_READY")
        except OSError as exc:
            raise BrokerLiveAcceptanceError(
                "WP15_LIVE_PENDING_BOUNDARY_NOT_READY"
            ) from exc

        data = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        temporary = parent / f".{self._path.name}.{secrets.token_hex(12)}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
        except OSError as exc:
            raise BrokerLiveAcceptanceError("WP15_LIVE_EVIDENCE_WRITE_FAILED") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BrokerLiveAcceptanceError("WP15_LIVE_CLOCK_INVALID")
    return value.astimezone(timezone.utc)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _default_adapter_factory(
    client_factory: Callable[[], Any],
    expected_account_fingerprint_sha256: str,
) -> SnapshotAdapterLike:
    return TInvestConnectionReadAdapter(
        client_factory=client_factory,
        expected_account_fingerprint_sha256=expected_account_fingerprint_sha256,
    )


class BrokerLiveAcceptanceServiceV1:
    """Acceptance-only local bridge from a verified Web connection to one live snapshot.

    Private values stay inside the short-lived in-memory challenge and loopback browser
    response. Confirmation writes only a bounded sanitized evidence record. This service
    does not provide a portfolio product API and must not be used by WP18 UI code.
    """

    def __init__(
        self,
        *,
        repository: BrokerRepositoryLike,
        vault: ReadConnectionVaultLike,
        client_factory_builder: Callable[[str], Callable[[], Any]],
        evidence_writer: PendingLiveAcceptanceEvidenceWriterV1,
        implementation_sha: str,
        adapter_factory: Callable[
            [Callable[[], Any], str], SnapshotAdapterLike
        ] = _default_adapter_factory,
        ttl: timedelta = timedelta(minutes=10),
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        candidate_sha = implementation_sha.strip().lower()
        if _GIT_SHA_RE.fullmatch(candidate_sha) is None:
            raise ValueError("implementation_sha must be an exact 40-character Git SHA")
        if ttl <= timedelta(0) or ttl > timedelta(minutes=30):
            raise ValueError("live acceptance challenge TTL is out of bounds")
        self._repository = repository
        self._vault = vault
        self._client_factory_builder = client_factory_builder
        self._evidence_writer = evidence_writer
        self._implementation_sha = candidate_sha
        self._adapter_factory = adapter_factory
        self._ttl = ttl
        self._now = now
        self._lock = threading.Lock()
        self._challenges: dict[str, _LiveChallengeV1] = {}

    def _current(self) -> datetime:
        return _aware_utc(self._now())

    def _purge_expired(self, current: datetime) -> None:
        expired = [
            challenge_id
            for challenge_id, challenge in self._challenges.items()
            if current >= challenge.expires_at
        ]
        for challenge_id in expired:
            self._challenges.pop(challenge_id, None)

    def _connection(
        self,
        *,
        tenant_id: str,
        connection_id: str,
    ) -> BrokerConnectionRecordV1:
        matches = [
            item
            for item in self._repository.list_read_connections(tenant_id=tenant_id)
            if item.connection_id == connection_id
        ]
        if len(matches) != 1:
            raise BrokerLiveAcceptanceError("WP15_LIVE_CONNECTION_NOT_FOUND")
        record = matches[0]
        if (
            record.state != "ACTIVE"
            or record.provider != "t_invest"
            or record.credential_role != "read"
        ):
            raise BrokerLiveAcceptanceError("WP15_LIVE_CONNECTION_NOT_ACTIVE_READ")
        if not record.accounts:
            raise BrokerLiveAcceptanceError("WP15_LIVE_ACCOUNT_BINDING_MISSING")
        return record

    @staticmethod
    def _sample(result: TInvestSnapshotResultV1) -> LiveAcceptanceSampleV1:
        candidates = [
            position
            for position in result.snapshot.positions
            if position.quantity_units > 0
            and position.valuation is not None
            and position.valuation.unit_price is not None
        ]
        if not candidates:
            raise BrokerLiveAcceptanceError("WP15_LIVE_SAMPLE_POSITION_REQUIRED")
        candidates.sort(
            key=lambda item: (
                item.instrument.ticker or "",
                item.instrument.name,
                item.instrument.stable_key(),
            )
        )
        position = candidates[0]
        valuation = position.valuation
        if valuation is None or valuation.unit_price is None:
            raise BrokerLiveAcceptanceError("WP15_LIVE_SAMPLE_POSITION_REQUIRED")
        market_value = position.quantity_units * valuation.unit_price
        label = position.instrument.ticker or position.instrument.name
        return LiveAcceptanceSampleV1(
            label=label,
            quantity=_decimal_text(position.quantity_units),
            unit_price=_decimal_text(valuation.unit_price),
            market_value=_decimal_text(market_value),
            currency=valuation.currency,
        )

    def start(
        self,
        *,
        user_id: str,
        tenant_id: str,
        connection_id: str,
        account_index: int,
    ) -> LiveAcceptanceViewV1:
        if account_index < 0 or account_index > 255:
            raise BrokerLiveAcceptanceError("WP15_LIVE_ACCOUNT_SELECTION_INVALID")
        record = self._connection(tenant_id=tenant_id, connection_id=connection_id)
        if account_index >= len(record.accounts):
            raise BrokerLiveAcceptanceError("WP15_LIVE_ACCOUNT_SELECTION_INVALID")
        selected = record.accounts[account_index]
        if selected.access_level != "ACCOUNT_ACCESS_LEVEL_READ_ONLY":
            raise BrokerLiveAcceptanceError("WP15_LIVE_AUTHORITY_NOT_READ_ONLY")

        token = ""
        try:
            token = self._vault.load(record.secret_ref)
            if not token:
                raise BrokerLiveAcceptanceError("WP15_LIVE_READ_CREDENTIAL_UNAVAILABLE")
            adapter = self._adapter_factory(
                self._client_factory_builder(token),
                selected.account_fingerprint_sha256,
            )
            result = adapter.read_snapshot(allow_partial=False)
        except BrokerLiveAcceptanceError:
            raise
        except Exception as exc:
            raise BrokerLiveAcceptanceError("WP15_LIVE_BROKER_READ_FAILED") from exc
        finally:
            token = ""

        if (
            result.account.account_fingerprint_sha256
            != selected.account_fingerprint_sha256
        ):
            raise BrokerLiveAcceptanceError("WP15_LIVE_ACCOUNT_BINDING_MISMATCH")
        if result.account.masked_label != selected.masked_label:
            raise BrokerLiveAcceptanceError("WP15_LIVE_MASKED_ACCOUNT_MISMATCH")
        if result.account.access_level != "ACCOUNT_ACCESS_LEVEL_READ_ONLY":
            raise BrokerLiveAcceptanceError("WP15_LIVE_AUTHORITY_NOT_READ_ONLY")
        if result.freshness.state != FreshnessState.FRESH:
            raise BrokerLiveAcceptanceError("WP15_LIVE_DATA_STALE")
        if result.unresolved_position_count != 0:
            raise BrokerLiveAcceptanceError("WP15_LIVE_PORTFOLIO_INCOMPLETE")
        if result.portfolio_total is None:
            raise BrokerLiveAcceptanceError("WP15_LIVE_PORTFOLIO_TOTAL_MISSING")

        current = self._current()
        challenge_id = f"wp15-live:v1:{secrets.token_urlsafe(24)}"
        expires_at = current + self._ttl
        view = LiveAcceptanceViewV1(
            challenge_id=challenge_id,
            expires_at=expires_at,
            masked_account=selected.masked_label,
            access_level="READ_ONLY",
            portfolio_total=_decimal_text(result.portfolio_total.amount),
            portfolio_currency=result.portfolio_total.currency,
            sample=self._sample(result),
            freshness_state="FRESH",
            retrieved_at=_aware_utc(result.freshness.retrieved_at),
            evaluated_at=_aware_utc(result.freshness.evaluated_at),
            age_seconds=_decimal_text(result.freshness.age_seconds),
            normalized_position_count=result.normalized_position_count,
        )
        with self._lock:
            self._purge_expired(current)
            self._challenges[challenge_id] = _LiveChallengeV1(
                user_id=user_id,
                tenant_id=tenant_id,
                expires_at=expires_at,
                view=view,
            )
        return view

    def confirm(
        self,
        *,
        user_id: str,
        tenant_id: str,
        challenge_id: str,
        intended_account_confirmed: bool,
        portfolio_summary_parity: bool,
        sample_position_quantity_value_parity: bool,
        freshness_confirmed: bool,
    ) -> dict[str, Any]:
        current = self._current()
        with self._lock:
            self._purge_expired(current)
            challenge = self._challenges.get(challenge_id)
            if challenge is None:
                raise BrokerLiveAcceptanceError("WP15_LIVE_CHALLENGE_INVALID")
            if challenge.user_id != user_id or challenge.tenant_id != tenant_id:
                raise BrokerLiveAcceptanceError("WP15_LIVE_CHALLENGE_SCOPE_MISMATCH")

        if not all(
            (
                intended_account_confirmed,
                portfolio_summary_parity,
                sample_position_quantity_value_parity,
                freshness_confirmed,
            )
        ):
            raise BrokerLiveAcceptanceError("WP15_LIVE_OWNER_PARITY_NOT_CONFIRMED")
        if challenge.view.freshness_state != "FRESH":
            raise BrokerLiveAcceptanceError("WP15_LIVE_DATA_STALE")

        payload: dict[str, Any] = {
            "schema_version": "1",
            "work_package": "WP15",
            "evidence_type": "LIVE_WEB_READ_ACCEPTANCE_PENDING",
            "implementation_sha": self._implementation_sha,
            "observed_at": challenge.view.retrieved_at.isoformat(),
            "confirmed_at": current.isoformat(),
            "broker_authority": "READ_ONLY",
            "intended_masked_account_confirmed": True,
            "portfolio_summary_parity": True,
            "sample_position_quantity_value_parity": True,
            "freshness_state": "FRESH",
            "freshness_confirmed": True,
            "sample_position_present": True,
            "normalized_position_count": challenge.view.normalized_position_count,
            "real_broker_read_observation": True,
            "real_read_credential_used_locally": True,
            "secret_value_recorded": False,
            "full_account_id_recorded": False,
            "account_fingerprint_recorded": False,
            "private_portfolio_values_recorded": False,
            "broker_write_authority_added": False,
            "trading_methods": False,
            "gateway_entrypoint": "app:app",
            "ready_for_owner_finalization": True,
        }
        self._evidence_writer.write(payload)
        with self._lock:
            self._challenges.pop(challenge_id, None)
        return payload

    def cancel(self, *, user_id: str, tenant_id: str, challenge_id: str) -> bool:
        current = self._current()
        with self._lock:
            self._purge_expired(current)
            challenge = self._challenges.get(challenge_id)
            if challenge is None:
                return False
            if challenge.user_id != user_id or challenge.tenant_id != tenant_id:
                raise BrokerLiveAcceptanceError("WP15_LIVE_CHALLENGE_SCOPE_MISMATCH")
            self._challenges.pop(challenge_id, None)
            return True
