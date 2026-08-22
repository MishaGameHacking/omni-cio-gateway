from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


RENDER_API_BASE = "https://api.render.com/v1"
RENDER_SERVICE_NAME = "omni-cio-v10-web"
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
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
    {"deactivated", "build_failed", "update_failed", "canceled", "pre_deploy_failed"}
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


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise DiagnosticStopped(f"{name}_REQUIRED")
    _mask(value)
    return value


def _provider_id(value: object, code: str) -> str:
    if not isinstance(value, str) or _PROVIDER_ID_PATTERN.fullmatch(value) is None:
        raise DiagnosticStopped(code)
    return value


def _object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DiagnosticStopped(code)
    return value


def _list(value: object, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise DiagnosticStopped(code)
    return value


def _unwrap_rows(payload: object, key: str) -> list[dict[str, Any]]:
    rows = _list(payload, f"{key.upper()}_LIST_INVALID")
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _object(row, f"{key.upper()}_ROW_INVALID")
        nested = item.get(key)
        result.append(
            _object(nested, f"{key.upper()}_WRAPPER_INVALID")
            if nested is not None
            else item
        )
    return result


def _request(token: str, path: str) -> object:
    if not path.startswith("/") or path.startswith("//"):
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_PATH_INVALID")
    request = Request(
        f"{RENDER_API_BASE}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "omni-cio-v10-phase4-diagnostic",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=30.0) as response:  # noqa: S310 - fixed Render API base
            status = int(response.status)
            raw = response.read()
    except HTTPError as exc:
        if int(exc.code) in {401, 403}:
            raise DiagnosticStopped("RENDER_DIAGNOSTIC_AUTHORITY_FAILED") from None
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_HTTP_ERROR") from None
    except (URLError, TimeoutError, OSError):
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_NETWORK_ERROR") from None
    if status != 200:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_STATUS_INVALID")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_JSON_INVALID") from None


def _matching_service(token: str) -> dict[str, Any]:
    query = urlencode({"name": RENDER_SERVICE_NAME, "limit": 20})
    services = [
        service
        for service in _unwrap_rows(_request(token, f"/services?{query}"), "service")
        if service.get("name") == RENDER_SERVICE_NAME
    ]
    if len(services) != 1:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_SERVICE_NOT_UNIQUE")
    return services[0]


def _matching_deploy(token: str, service_id: str, expected_sha: str) -> dict[str, Any]:
    safe_service_id = quote(_provider_id(service_id, "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID"), safe="")
    query = urlencode({"limit": 100})
    deploys = _unwrap_rows(
        _request(token, f"/services/{safe_service_id}/deploys?{query}"),
        "deploy",
    )
    matches: list[dict[str, Any]] = []
    for deploy in deploys:
        commit = deploy.get("commit")
        if isinstance(commit, dict) and commit.get("id") == expected_sha:
            matches.append(deploy)
    if not matches:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_NOT_FOUND")
    matches.sort(key=lambda item: str(item.get("createdAt", "")), reverse=True)
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


def _deploy_event_reason(
    token: str,
    service_id: str,
    deploy_id: str,
    status: str,
) -> str:
    safe_service_id = quote(_provider_id(service_id, "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID"), safe="")
    query = urlencode({"type": "deploy_ended", "limit": 100})
    events = _unwrap_rows(
        _request(token, f"/services/{safe_service_id}/events?{query}"),
        "event",
    )
    matches: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "deploy_ended":
            continue
        details = event.get("details")
        if isinstance(details, dict) and details.get("deployId") == deploy_id:
            matches.append(event)
    if not matches:
        return _safe_failure_reason({}, status)
    matches.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    details = _object(matches[0].get("details"), "RENDER_DIAGNOSTIC_EVENT_DETAILS_INVALID")
    return _safe_failure_reason(details, status)


def diagnose(expected_sha: str) -> DeployDiagnostic:
    if _SHA_PATTERN.fullmatch(expected_sha) is None:
        raise DiagnosticStopped("EXPECTED_SHA_INVALID")
    token = _required_env("RENDER_API_KEY")
    service = _matching_service(token)
    service_id = _provider_id(service.get("id"), "RENDER_DIAGNOSTIC_SERVICE_ID_INVALID")
    deploy = _matching_deploy(token, service_id, expected_sha)
    deploy_id = _provider_id(deploy.get("id"), "RENDER_DIAGNOSTIC_DEPLOY_ID_INVALID")
    raw_status = deploy.get("status")
    if not isinstance(raw_status, str) or raw_status not in _DEPLOY_STATUSES:
        raise DiagnosticStopped("RENDER_DIAGNOSTIC_DEPLOY_STATUS_INVALID")
    reason = _deploy_event_reason(token, service_id, deploy_id, raw_status)
    return DeployDiagnostic(
        service_id=service_id,
        deploy_id=deploy_id,
        status=raw_status,
        reason=reason,
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        result = diagnose(args.expected_sha.strip().lower())
    except DiagnosticStopped as exc:
        print(f"RENDER_DEPLOY_DIAGNOSTIC=STOPPED code={exc.code}")
        return 1
    print(f"RENDER_DEPLOY_STATUS={result.status}")
    print(f"RENDER_DEPLOY_REASON={result.reason}")
    print(
        "RENDER_DEPLOY_TERMINAL="
        + ("YES" if result.status in _FAILURE_STATUSES or result.status == "live" else "NO")
    )
    print("RENDER_DEPLOY_DIAGNOSTIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
