from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from threading import RLock
from typing import Protocol

from omni_cio.contracts.v1.watchtower import WatchtowerInputV1

from .engine_v1 import PortfolioWatchtowerV1
from .qstash_v1 import QStashSignatureVerifierV1


class WatchtowerRuntimeError(RuntimeError):
    pass


class WatchtowerEvidenceProviderV1(Protocol):
    def build_input(
        self,
        *,
        delivery_id: str,
        checked_at: datetime,
    ) -> WatchtowerInputV1: ...


class WatchtowerEvidenceProviderRegistryV1:
    """One process-local owner for the canonical read-only evidence provider."""

    def __init__(self) -> None:
        self._provider: WatchtowerEvidenceProviderV1 | None = None
        self._lock = RLock()

    def register(self, provider: WatchtowerEvidenceProviderV1) -> None:
        build = getattr(provider, "build_input", None)
        if not callable(build):
            raise WatchtowerRuntimeError("WATCHTOWER_PROVIDER_INVALID")
        with self._lock:
            if self._provider is not None and self._provider is not provider:
                raise WatchtowerRuntimeError("WATCHTOWER_PROVIDER_CONFLICT")
            self._provider = provider

    def get(self) -> WatchtowerEvidenceProviderV1:
        with self._lock:
            if self._provider is None:
                raise WatchtowerRuntimeError("WATCHTOWER_PROVIDER_NOT_REGISTERED")
            return self._provider


@dataclass(frozen=True)
class WatchtowerScheduledRequestV1:
    raw_body: str
    signature: str
    destination_url: str
    message_id: str
    schedule_id: str
    retried: int


class WatchtowerScheduledRunnerV1:
    """Verify QStash transport, acquire canonical evidence, then run reducer."""

    def __init__(
        self,
        *,
        verifier: QStashSignatureVerifierV1,
        watchtower: PortfolioWatchtowerV1,
        provider_registry: WatchtowerEvidenceProviderRegistryV1,
        expected_schedule_id: str,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not expected_schedule_id.startswith("omni-cio-watchtower-"):
            raise WatchtowerRuntimeError("WATCHTOWER_SCHEDULE_ID_INVALID")
        self._verifier = verifier
        self._watchtower = watchtower
        self._providers = provider_registry
        self._schedule_id = expected_schedule_id
        self._now = now_provider

    @staticmethod
    def _validate_transport(request: WatchtowerScheduledRequestV1) -> None:
        if not 8 <= len(request.message_id) <= 200:
            raise WatchtowerRuntimeError("WATCHTOWER_MESSAGE_ID_INVALID")
        if request.retried < 0 or request.retried > 3:
            raise WatchtowerRuntimeError("WATCHTOWER_RETRY_COUNT_INVALID")

    def run(self, request: WatchtowerScheduledRequestV1) -> dict[str, object]:
        self._verifier.verify(
            signature=request.signature,
            body=request.raw_body,
            url=request.destination_url,
        )
        self._validate_transport(request)
        if request.schedule_id != self._schedule_id:
            raise WatchtowerRuntimeError("WATCHTOWER_SCHEDULE_ID_MISMATCH")
        try:
            body = json.loads(request.raw_body)
        except json.JSONDecodeError as exc:
            raise WatchtowerRuntimeError("WATCHTOWER_TRIGGER_BODY_INVALID") from exc
        if body != {"job": "portfolio_watchtower", "schema_version": "1.0"}:
            raise WatchtowerRuntimeError("WATCHTOWER_TRIGGER_BODY_INVALID")

        checked_at = self._now()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise WatchtowerRuntimeError("WATCHTOWER_CLOCK_INVALID")
        checked_at = checked_at.astimezone(timezone.utc)
        source = self._providers.get().build_input(
            delivery_id=request.message_id,
            checked_at=checked_at,
        )
        value = WatchtowerInputV1.model_validate(source.model_dump(mode="python"))
        if value.delivery_id != request.message_id:
            raise WatchtowerRuntimeError("WATCHTOWER_PROVIDER_DELIVERY_ID_MISMATCH")
        evaluation = self._watchtower.evaluate(value)
        return {
            "status": "ok",
            "schema_version": "1.0",
            "watch_id": evaluation.watch_id,
            "input_sha256": evaluation.input_sha256,
            "evaluation_sha256": evaluation.evaluation_sha256,
            "state_revision": evaluation.state.revision,
            "replay": evaluation.replay,
            "material_change": evaluation.material_change,
            "should_notify": evaluation.should_notify,
            "proposed_action": evaluation.proposed_action.value,
            "alerts": [
                {
                    "alert_id": row.alert_id,
                    "fingerprint_sha256": row.fingerprint_sha256,
                    "kind": row.kind.value,
                    "severity": row.severity.value,
                    "message_code": row.message_code,
                    "requires_owner_attention": row.requires_owner_attention,
                    "action": row.action.value,
                }
                for row in evaluation.alerts
            ],
            "execution_authorized": False,
            "trading_methods": False,
        }


class WatchtowerCallbackVerifierV1:
    """Signed callback/failure-callback acknowledgment with no state mutation."""

    def __init__(self, verifier: QStashSignatureVerifierV1) -> None:
        self._verifier = verifier

    def acknowledge(
        self,
        *,
        raw_body: str,
        signature: str,
        destination_url: str,
        message_id: str,
    ) -> dict[str, object]:
        self._verifier.verify(
            signature=signature,
            body=raw_body,
            url=destination_url,
        )
        if not 8 <= len(message_id) <= 200:
            raise WatchtowerRuntimeError("WATCHTOWER_CALLBACK_MESSAGE_ID_INVALID")
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise WatchtowerRuntimeError("WATCHTOWER_CALLBACK_BODY_INVALID") from exc
        if not isinstance(payload, dict):
            raise WatchtowerRuntimeError("WATCHTOWER_CALLBACK_BODY_INVALID")
        return {
            "status": "accepted",
            "message_id_sha256": hashlib.sha256(message_id.encode()).hexdigest(),
            "callback_body_sha256": hashlib.sha256(raw_body.encode()).hexdigest(),
            "execution_authorized": False,
            "trading_methods": False,
        }
