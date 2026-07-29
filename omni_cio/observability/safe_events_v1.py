from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from logging import Logger
from uuid import uuid4

from omni_cio.contracts.v1.common import AccountReference, Completeness, DataQuality
from omni_cio.contracts.v1.observability import (
    ExternalCallTelemetryV1,
    ObservabilityEventV1,
    ObservabilityOutcome,
    ObservabilitySeverity,
    SafeCountMetricV1,
)


def new_trace_id(prefix: str) -> str:
    """Return a non-secret opaque trace identifier."""

    normalized = "".join(
        character.lower()
        for character in prefix
        if character.isascii() and (character.isalnum() or character in "_.-")
    ).strip("_.-")
    safe_prefix = normalized or "trace"
    return f"{safe_prefix}:{uuid4().hex}"


def build_safe_event(
    *,
    event_name: str,
    component: str,
    outcome: ObservabilityOutcome,
    severity: ObservabilitySeverity = ObservabilitySeverity.INFO,
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    action_id: str | None = None,
    account: AccountReference | None = None,
    duration_ms: Decimal | None = None,
    external_call: ExternalCallTelemetryV1 | None = None,
    quality: DataQuality | None = None,
    completeness: Completeness | None = None,
    error_code: str | None = None,
    exception_type: str | None = None,
    metrics: tuple[SafeCountMetricV1, ...] = (),
) -> ObservabilityEventV1:
    """Build one event from explicit allowlisted metadata only."""

    timestamp = occurred_at or datetime.now(timezone.utc)
    return ObservabilityEventV1(
        occurred_at=timestamp,
        event_name=event_name,
        severity=severity,
        component=component,
        outcome=outcome,
        correlation_id=correlation_id or new_trace_id("corr"),
        request_id=request_id,
        action_id=action_id,
        account=account,
        duration_ms=duration_ms,
        external_call=external_call,
        quality=quality,
        completeness=completeness,
        error_code=error_code,
        exception_type=exception_type,
        metrics=metrics,
        contains_sensitive_payload=False,
        trading_methods=False,
    )


def emit_safe_event(logger: Logger, event: ObservabilityEventV1) -> None:
    """Emit canonical JSON without free-form payload or exception text."""

    serialized = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    if event.severity == ObservabilitySeverity.ERROR:
        logger.error(serialized)
    elif event.severity == ObservabilitySeverity.WARNING:
        logger.warning(serialized)
    else:
        logger.info(serialized)
