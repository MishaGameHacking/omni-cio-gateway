from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
import sys
from typing import Any
from urllib.parse import urlencode

from scripts import provision_v10_render_neon_preview as provisioner


_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PAGE_LIMIT = 100
_DEPLOY_QUERY_SKEW = timedelta(seconds=1)
_DEPLOY_STATUSES = frozenset(
    {
        "created",
        "queued",
        "build_in_progress",
        "update_in_progress",
        "live",
        "deactivated",
        "build_failed",
        "update_failed",
        "canceled",
        "pre_deploy_in_progress",
        "pre_deploy_failed",
    }
)
_FAILURE_STATUSES = frozenset(
    {
        "deactivated",
        "build_failed",
        "update_failed",
        "canceled",
        "pre_deploy_failed",
    }
)


class DiagnosticStopped(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DeployDiagnostic:
    service_id: str
    deploy_id: str
    status: str
    reason: str


def _api_from_environment() -> provisioner.JsonApi:
    return provisioner.JsonApi(
        provisioner.RENDER_API_BASE,
        provisioner._required_env("RENDER_API_KEY"),
        label="RENDER",
    )


def _utc_timestamp(value: object, code: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticStopped(code)
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise DiagnosticStopped(code) from None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DiagnosticStopped(code)
    return parsed.astimezone(timezone.utc)


def _render_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_rows(payload: Any, key: str, code: str) -> list[dict[str, Any]]:
    rows = provisioner._unwrap_rows(payload, key)
    if len(rows) >= _PAGE_LIMIT:
        raise DiagnosticStopped(code)
    return rows


def _matching_service(api: provisioner.JsonApi) -> dict[str, Any]:
    owner_id = provisioner._render_owner(api)
    services = [
        service
        for service in provisioner._render_services(api, owner_id)
        if service.get("name") == provisioner.RENDER_SERVICE_NAME
    ]
    if len(services) != 1:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_SERVICE_NOT_UNIQUE")
    service = services[0]
    provisioner._validate_existing_render_service(service)
    return service


def _matching_deploy(
    api: provisioner.JsonApi,
    service_id: str,
    expected_sha: str,
    not_before: datetime,
) -> dict[str, Any]:
    safe_service_id = provisioner._provider_segment(
        service_id,
        "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID",
    )
    query = urlencode(
        {
            "createdAfter": _render_timestamp(not_before - _DEPLOY_QUERY_SKEW),
            "limit": _PAGE_LIMIT,
        }
    )
    deploys = _bounded_rows(
        api.request("GET", f"/services/{safe_service_id}/deploys?{query}"),
        "deploy",
        "RENDER_DIAGNOSTIC_DEPLOY_WINDOW_TRUNCATED",
    )
    matches: list[tuple[datetime, dict[str, Any]]] = []
    for deploy in deploys:
        commit = deploy.get("commit")
        if not isinstance(commit, dict) or commit.get("id") != expected_sha:
            continue
        created_at = _utc_timestamp(
            deploy.get("createdAt"),
            "RENDER_DIAGNOSTIC_DEPLOY_CREATED_AT_INVALID",
        )
        if created_at >= not_before:
            matches.append((created_at, deploy))
    if not matches:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND")
    if len(matches) != 1:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_NOT_UNIQUE")
    return matches[0][1]


def _service_events(
    api: provisioner.JsonApi,
    service_id: str,
    event_type: str,
    *,
    not_before: datetime | None = None,
) -> list[dict[str, Any]]:
    safe_service_id = provisioner._provider_segment(
        service_id,
        "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID",
    )
    query_values: dict[str, object] = {"type": event_type, "limit": _PAGE_LIMIT}
    if not_before is not None:
        query_values["startTime"] = _render_timestamp(not_before)
    query = urlencode(query_values)
    return _bounded_rows(
        api.request("GET", f"/services/{safe_service_id}/events?{query}"),
        "event",
        "RENDER_DIAGNOSTIC_EVENT_WINDOW_TRUNCATED",
    )


def _event_id(summary: dict[str, Any], event_type: str) -> str:
    if summary.get("type") != event_type:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_EVENT_TYPE_DRIFT")
    return provisioner._provider_id(
        summary.get("id"),
        "RENDER_DIAGNOSTIC_EVENT_ID_INVALID",
    )


def _retrieve_event(
    api: provisioner.JsonApi,
    event_id: str,
    event_type: str,
) -> dict[str, Any]:
    safe_event_id = provisioner._provider_segment(
        event_id,
        "RENDER_DIAGNOSTIC_EVENT_ID_INVALID",
    )
    payload = provisioner._json_object(
        api.request("GET", f"/events/{safe_event_id}"),
        "RENDER_DIAGNOSTIC_EVENT_RESPONSE_INVALID",
    )
    nested = payload.get("event")
    event = (
        provisioner._json_object(
            nested,
            "RENDER_DIAGNOSTIC_EVENT_RESPONSE_INVALID",
        )
        if nested is not None
        else payload
    )
    actual_id = provisioner._provider_id(
        event.get("id"),
        "RENDER_DIAGNOSTIC_EVENT_ID_INVALID",
    )
    if actual_id != event_id or event.get("type") != event_type:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_EVENT_IDENTITY_DRIFT")
    return event


def _matching_event_details(
    api: provisioner.JsonApi,
    service_id: str,
    event_type: str,
    detail_key: str,
    detail_id: str,
    not_before: datetime,
) -> dict[str, Any] | None:
    matches: list[dict[str, Any]] = []
    for summary in _service_events(
        api,
        service_id,
        event_type,
        not_before=not_before,
    ):
        event_id = _event_id(summary, event_type)
        timestamp = _utc_timestamp(
            summary.get("timestamp"),
            "RENDER_DIAGNOSTIC_EVENT_TIMESTAMP_INVALID",
        )
        if timestamp < not_before:
            continue
        event = _retrieve_event(api, event_id, event_type)
        details = provisioner._json_object(
            event.get("details"),
            "RENDER_DIAGNOSTIC_EVENT_DETAILS_INVALID",
        )
        if details.get(detail_key) == detail_id:
            matches.append(details)
    if not matches:
        return None
    if len(matches) != 1:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_EVENT_NOT_UNIQUE")
    return matches[0]


def _safe_failure_reason(details: dict[str, Any], status: str) -> str:
    reason = details.get("reason")
    if isinstance(reason, dict):
        failure = reason.get("failure")
        if isinstance(failure, dict):
            non_zero = failure.get("nonZeroExit")
            if isinstance(non_zero, int) and not isinstance(non_zero, bool):
                return "NON_ZERO_EXIT"
            if failure.get("earlyExit") is True:
                return "EARLY_EXIT"
            if isinstance(failure.get("oomKilled"), dict):
                return "OOM_KILLED"
            if isinstance(failure.get("timedOutSeconds"), int):
                return "TIMED_OUT"
            if "unhealthy" in failure:
                return "UNHEALTHY"
            if failure.get("evicted") is True:
                return "EVICTED"
        if isinstance(reason.get("buildFailed"), dict):
            return "BUILD_FAILED"
    return {
        "build_failed": "BUILD_FAILED",
        "update_failed": "UPDATE_FAILED",
        "pre_deploy_failed": "PRE_DEPLOY_FAILED",
        "canceled": "CANCELED",
        "deactivated": "DEACTIVATED",
    }.get(status, "NO_SAFE_REASON")


def _build_failure_id(details: dict[str, Any]) -> str | None:
    reason = details.get("reason")
    if not isinstance(reason, dict):
        return None
    build_failed = reason.get("buildFailed")
    if not isinstance(build_failed, dict) or "id" not in build_failed:
        return None
    return provisioner._provider_id(
        build_failed.get("id"),
        "RENDER_DIAGNOSTIC_BUILD_ID_INVALID",
    )


def _attempt_pipeline_reason(
    api: provisioner.JsonApi,
    service_id: str,
    not_before: datetime,
) -> str | None:
    matches: list[str] = []
    for summary in _service_events(
        api,
        service_id,
        "pipeline_minutes_exhausted",
        not_before=not_before,
    ):
        _event_id(summary, "pipeline_minutes_exhausted")
        timestamp = _utc_timestamp(
            summary.get("timestamp"),
            "RENDER_DIAGNOSTIC_PIPELINE_EVENT_TIMESTAMP_INVALID",
        )
        if timestamp >= not_before:
            matches.append("PIPELINE_MINUTES_EXHAUSTED")
    if not matches:
        return None
    if len(matches) != 1:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_PIPELINE_EVENT_NOT_UNIQUE")
    return matches[0]


def _build_event_reason(
    api: provisioner.JsonApi,
    service_id: str,
    build_id: str,
    status: str,
    not_before: datetime,
) -> str:
    details = _matching_event_details(
        api,
        service_id,
        "build_ended",
        "buildId",
        build_id,
        not_before,
    )
    if details is None:
        return "BUILD_FAILED"
    return _safe_failure_reason(details, status)


def _deploy_event_reason(
    api: provisioner.JsonApi,
    service_id: str,
    deploy_id: str,
    status: str,
    not_before: datetime,
) -> str:
    details = _matching_event_details(
        api,
        service_id,
        "deploy_ended",
        "deployId",
        deploy_id,
        not_before,
    )
    if details is None:
        return _safe_failure_reason({}, status)
    reason = _safe_failure_reason(details, status)
    if reason != "BUILD_FAILED":
        return reason
    build_id = _build_failure_id(details)
    if build_id is None:
        return reason
    return _build_event_reason(
        api,
        service_id,
        build_id,
        status,
        not_before,
    )


def diagnose(
    expected_sha: str,
    not_before: str,
    *,
    api: provisioner.JsonApi | None = None,
) -> DeployDiagnostic:
    if _SHA_PATTERN.fullmatch(expected_sha) is None:
        raise DiagnosticStopped("EXPECTED_SHA_INVALID")
    lower_bound = _utc_timestamp(
        not_before,
        "RENDER_DIAGNOSTIC_NOT_BEFORE_INVALID",
    )
    client = _api_from_environment() if api is None else api
    service = _matching_service(client)
    service_id = provisioner._provider_id(
        service.get("id"),
        "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID",
    )
    deploy = _matching_deploy(client, service_id, expected_sha, lower_bound)
    deploy_id = provisioner._provider_id(
        deploy.get("id"),
        "RENDER_DIAGNOSTIC_DEPLOY_ID_INVALID",
    )
    raw_status = deploy.get("status")
    if not isinstance(raw_status, str) or raw_status not in _DEPLOY_STATUSES:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_STATUS_INVALID")
    reason = _attempt_pipeline_reason(client, service_id, lower_bound)
    if reason is None:
        if raw_status not in _FAILURE_STATUSES:
            raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_NOT_FAILED")
        reason = _deploy_event_reason(
            client,
            service_id,
            deploy_id,
            raw_status,
            lower_bound,
        )
    return DeployDiagnostic(
        service_id=service_id,
        deploy_id=deploy_id,
        status=raw_status,
        reason=reason,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--not-before", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        result = diagnose(
            args.expected_sha.strip().lower(),
            args.not_before.strip(),
        )
    except (DiagnosticStopped, provisioner.ProvisioningStopped) as exc:
        print(f"RENDER_DEPLOY_DIAGNOSTIC=STOPPED code={exc.code}")
        return 1
    print(f"RENDER_DEPLOY_STATUS={result.status}")
    print(f"RENDER_DEPLOY_REASON={result.reason}")
    terminal = "YES" if result.status in _FAILURE_STATUSES else "NO"
    print(f"RENDER_DEPLOY_TERMINAL={terminal}")
    print("RENDER_DEPLOY_DIAGNOSTIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
