from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "infrastructure" / "preview" / "render-neon-contract.json"
NEON_API_BASE = "https://console.neon.tech/api/v2"
RENDER_API_BASE = "https://api.render.com/v1"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DEPLOY_FAILURE_STATES = frozenset(
    {
        "build_failed",
        "canceled",
        "cancelled",
        "deactivated",
        "failed",
        "update_failed",
    }
)


class PreviewDeployError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ApiFailure(Exception):
    label: str
    status: int

    def __str__(self) -> str:
        return f"{self.label}_HTTP_{self.status}"


class JsonApi:
    def __init__(self, *, base_url: str, token: str, label: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._label = label

    def call(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
    ) -> Any:
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "omni-cio-v10-preview-deployer/1",
        }
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        target = f"{self._base_url}/{path.lstrip('/')}"
        operation = request.Request(
            target,
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with request.urlopen(operation, timeout=45) as response:
                raw = response.read()
        except error.HTTPError as exc:
            _ = exc.read()
            raise ApiFailure(self._label, int(exc.code)) from exc
        except error.URLError as exc:
            raise PreviewDeployError(f"{self._label}_NETWORK_UNAVAILABLE") from exc
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PreviewDeployError(f"{self._label}_JSON_INVALID") from exc


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PreviewDeployError(f"{name}_REQUIRED")
    print(f"::add-mask::{value}")
    return value


def _mapping(value: Any, reason: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreviewDeployError(reason)
    return value


def _sequence(value: Any, reason: str) -> list[Any]:
    if not isinstance(value, list):
        raise PreviewDeployError(reason)
    return value


def _flatten_items(payload: Any, *, key: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        values = payload.get(f"{key}s")
        if isinstance(values, list):
            payload = values
    rows = _sequence(payload, f"{key.upper()}_LIST_INVALID")
    result: list[dict[str, Any]] = []
    for item in rows:
        row = _mapping(item, f"{key.upper()}_ITEM_INVALID")
        nested = row.get(key)
        result.append(
            _mapping(nested, f"{key.upper()}_ITEM_INVALID")
            if isinstance(nested, dict)
            else row
        )
    return result


def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreviewDeployError("PREVIEW_CONTRACT_INVALID") from exc
    contract = _mapping(payload, "PREVIEW_CONTRACT_INVALID")
    authority = _mapping(contract.get("authority"), "PREVIEW_AUTHORITY_INVALID")
    render = _mapping(contract.get("render"), "PREVIEW_RENDER_INVALID")
    neon = _mapping(contract.get("neon"), "PREVIEW_NEON_INVALID")
    safety = _mapping(contract.get("preview_safety"), "PREVIEW_SAFETY_INVALID")
    if authority.get("authorized_recurring_cost") != 0:
        raise PreviewDeployError("PREVIEW_RECURRING_COST_NOT_ZERO")
    if authority.get("paid_overage_allowed") is not False:
        raise PreviewDeployError("PREVIEW_PAID_OVERAGE_FORBIDDEN")
    for field in (
        "public_multi_user_enabled",
        "registration_enabled",
        "real_trading_enabled",
        "trading_methods_enabled",
        "wp23_unlocked",
    ):
        if authority.get(field) is not False:
            raise PreviewDeployError("PREVIEW_AUTHORITY_WIDENED")
    if render.get("plan") != "free" or render.get("runtime") != "docker":
        raise PreviewDeployError("PREVIEW_RENDER_PLAN_INVALID")
    if neon.get("postgres_version") != 18:
        raise PreviewDeployError("PREVIEW_POSTGRES_VERSION_INVALID")
    if safety.get("mutation_methods_allowed") is not False:
        raise PreviewDeployError("PREVIEW_MUTATION_AUTHORITY_FORBIDDEN")
    if safety.get("real_broker_credentials_allowed") is not False:
        raise PreviewDeployError("PREVIEW_BROKER_CREDENTIALS_FORBIDDEN")
    return contract


def _int_field(value: Any, *names: str) -> int | None:
    for name in names:
        candidate = value.get(name) if isinstance(value, dict) else None
        if isinstance(candidate, int) and not isinstance(candidate, bool):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _string_field(value: Any, *names: str) -> str | None:
    for name in names:
        candidate = value.get(name) if isinstance(value, dict) else None
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _find_exact(rows: list[dict[str, Any]], *, name: str) -> dict[str, Any] | None:
    matches = [row for row in rows if _string_field(row, "name") == name]
    if len(matches) > 1:
        raise PreviewDeployError("PROVIDER_RESOURCE_NAME_AMBIGUOUS")
    return matches[0] if matches else None


def _ensure_neon_project(
    api: JsonApi,
    contract: dict[str, Any],
) -> dict[str, Any]:
    neon = _mapping(contract["neon"], "PREVIEW_NEON_INVALID")
    name = str(neon["project_name"])
    projects = _flatten_items(api.call("GET", "/projects?limit=100"), key="project")
    project = _find_exact(projects, name=name)
    if project is None:
        body = {
            "project": {
                "name": name,
                "region_id": neon["region_id"],
                "pg_version": neon["postgres_version"],
            }
        }
        try:
            created = _mapping(
                api.call("POST", "/projects", body),
                "NEON_PROJECT_CREATE_RESPONSE_INVALID",
            )
        except ApiFailure as exc:
            raise PreviewDeployError("NEON_PROJECT_CREATE_FAILED") from exc
        candidate = created.get("project", created)
        project = _mapping(candidate, "NEON_PROJECT_CREATE_RESPONSE_INVALID")

    project_id = _string_field(project, "id")
    if project_id is None:
        raise PreviewDeployError("NEON_PROJECT_ID_MISSING")
    version = _int_field(project, "pg_version", "postgres_version")
    if version != int(neon["postgres_version"]):
        raise PreviewDeployError("NEON_PROJECT_POSTGRES_VERSION_MISMATCH")
    region = _string_field(project, "region_id", "region")
    if region != str(neon["region_id"]):
        raise PreviewDeployError("NEON_PROJECT_REGION_MISMATCH")
    print(f"NEON_PROJECT_AUTH=PASS project_id={project_id}")
    return project


def _primary_neon_branch(api: JsonApi, project_id: str) -> dict[str, Any]:
    payload = api.call("GET", f"/projects/{project_id}/branches?limit=100")
    branches = _flatten_items(payload, key="branch")
    if not branches:
        raise PreviewDeployError("NEON_BRANCH_MISSING")
    primary = [row for row in branches if row.get("primary") is True]
    if len(primary) == 1:
        return primary[0]
    named = [row for row in branches if _string_field(row, "name") == "main"]
    if len(named) == 1:
        return named[0]
    if len(branches) == 1:
        return branches[0]
    raise PreviewDeployError("NEON_PRIMARY_BRANCH_AMBIGUOUS")


def _neon_connection_uri(
    api: JsonApi,
    project: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    project_id = _string_field(project, "id")
    if project_id is None:
        raise PreviewDeployError("NEON_PROJECT_ID_MISSING")
    branch = _primary_neon_branch(api, project_id)
    branch_id = _string_field(branch, "id")
    if branch_id is None:
        raise PreviewDeployError("NEON_BRANCH_ID_MISSING")

    endpoints = _flatten_items(
        api.call("GET", f"/projects/{project_id}/endpoints?limit=100"),
        key="endpoint",
    )
    endpoint = next(
        (
            row
            for row in endpoints
            if _string_field(row, "branch_id") == branch_id
            and _string_field(row, "type") in {None, "read_write"}
        ),
        None,
    )
    if endpoint is None:
        raise PreviewDeployError("NEON_READ_WRITE_ENDPOINT_MISSING")
    endpoint_id = _string_field(endpoint, "id")

    roles = _flatten_items(
        api.call("GET", f"/projects/{project_id}/branches/{branch_id}/roles"),
        key="role",
    )
    role_name = next(
        (
            name
            for row in roles
            if (name := _string_field(row, "name")) is not None
            and (name == "neondb_owner" or name.endswith("_owner"))
        ),
        None,
    )
    if role_name is None and len(roles) == 1:
        role_name = _string_field(roles[0], "name")
    if role_name is None:
        raise PreviewDeployError("NEON_RUNTIME_ROLE_MISSING")

    databases = _flatten_items(
        api.call("GET", f"/projects/{project_id}/branches/{branch_id}/databases"),
        key="database",
    )
    database_name = next(
        (
            name
            for row in databases
            if (name := _string_field(row, "name")) == "neondb"
        ),
        None,
    )
    if database_name is None and len(databases) == 1:
        database_name = _string_field(databases[0], "name")
    if database_name is None:
        raise PreviewDeployError("NEON_DATABASE_MISSING")

    base_params = {
        "branch_id": branch_id,
        "database_name": database_name,
        "role_name": role_name,
        "pooled": "true",
    }
    variants = [dict(base_params)]
    if endpoint_id is not None:
        variants.insert(0, {**base_params, "endpoint_id": endpoint_id})
    response: dict[str, Any] | None = None
    for params in variants:
        try:
            candidate = api.call(
                "GET",
                f"/projects/{project_id}/connection_uri?{parse.urlencode(params)}",
            )
        except ApiFailure as exc:
            if exc.status in {400, 404, 422}:
                continue
            raise
        response = _mapping(candidate, "NEON_CONNECTION_URI_RESPONSE_INVALID")
        break
    if response is None:
        raise PreviewDeployError("NEON_CONNECTION_URI_UNAVAILABLE")
    uri = _string_field(response, "uri", "connection_uri")
    if uri is None or not uri.startswith(("postgresql://", "postgres://")):
        raise PreviewDeployError("NEON_CONNECTION_URI_INVALID")
    parsed = parse.urlsplit(uri)
    query = parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "sslmode" for key, _ in query):
        query.append(("sslmode", "require"))
        uri = parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, parse.urlencode(query), parsed.fragment)
        )
    print("NEON_CONNECTION_CONTRACT=PASS postgres=18 pooled=true tls=true")
    return uri


def _render_owner(api: JsonApi) -> str:
    owners = _flatten_items(api.call("GET", "/owners?limit=100"), key="owner")
    configured = os.environ.get("RENDER_OWNER_ID", "").strip()
    if configured:
        matches = [row for row in owners if _string_field(row, "id") == configured]
        if len(matches) != 1:
            raise PreviewDeployError("RENDER_OWNER_ID_NOT_ACCESSIBLE")
        return configured
    if len(owners) != 1:
        raise PreviewDeployError("RENDER_OWNER_ID_REQUIRED")
    owner_id = _string_field(owners[0], "id")
    if owner_id is None:
        raise PreviewDeployError("RENDER_OWNER_ID_MISSING")
    return owner_id


def _service_from_response(payload: Any) -> dict[str, Any]:
    response = _mapping(payload, "RENDER_SERVICE_RESPONSE_INVALID")
    nested = response.get("service")
    return (
        _mapping(nested, "RENDER_SERVICE_RESPONSE_INVALID")
        if isinstance(nested, dict)
        else response
    )


def _list_render_services(api: JsonApi) -> list[dict[str, Any]]:
    return _flatten_items(api.call("GET", "/services?limit=100"), key="service")


def _create_render_service(
    api: JsonApi,
    contract: dict[str, Any],
    owner_id: str,
) -> dict[str, Any]:
    render = _mapping(contract["render"], "PREVIEW_RENDER_INVALID")
    base = {
        "type": render["service_type"],
        "name": render["service_name"],
        "ownerId": owner_id,
        "repo": render["repository"],
        "branch": render["branch"],
    }
    details = {
        "env": render["runtime"],
        "region": render["region"],
        "plan": render["plan"],
        "numInstances": 1,
        "dockerfilePath": render["dockerfile_path"],
        "dockerContext": ".",
        "healthCheckPath": render["health_check_path"],
    }
    payloads = [
        {**base, "autoDeploy": "yes", "serviceDetails": details},
        {**base, "autoDeployTrigger": "commit", "serviceDetails": details},
    ]
    for payload in payloads:
        try:
            return _service_from_response(api.call("POST", "/services", payload))
        except ApiFailure as exc:
            if exc.status in {400, 404, 409, 422}:
                services = _list_render_services(api)
                existing = _find_exact(
                    services,
                    name=str(render["service_name"]),
                )
                if existing is not None:
                    return existing
                continue
            raise
    raise PreviewDeployError("RENDER_SERVICE_CREATE_FAILED")


def _ensure_render_service(
    api: JsonApi,
    contract: dict[str, Any],
) -> dict[str, Any]:
    render = _mapping(contract["render"], "PREVIEW_RENDER_INVALID")
    services = _list_render_services(api)
    service = _find_exact(services, name=str(render["service_name"]))
    if service is None:
        service = _create_render_service(api, contract, _render_owner(api))
    service_id = _string_field(service, "id")
    if service_id is None:
        raise PreviewDeployError("RENDER_SERVICE_ID_MISSING")
    details = service.get("serviceDetails")
    if isinstance(details, dict):
        plan = _string_field(details, "plan")
        if plan is not None and plan != "free":
            raise PreviewDeployError("RENDER_EXISTING_SERVICE_NOT_FREE")
    print(f"RENDER_SERVICE_AUTH=PASS service_id={service_id}")
    return service


def _put_render_env(
    api: JsonApi,
    service_id: str,
    *,
    dsn: str,
    release_sha: str,
) -> None:
    values = [
        {"key": "OMNI_V10_HOSTED_PREVIEW", "value": "1"},
        {"key": "OMNI_V10_POSTGRES_DSN", "value": dsn},
        {"key": "OMNI_V10_IMPLEMENTATION_SHA", "value": release_sha},
        {"key": "PUBLIC_MULTI_USER_ENABLED", "value": "false"},
        {"key": "REAL_TRADING_ENABLED", "value": "false"},
        {"key": "OMNI_V10_PREVIEW_READ_ONLY", "value": "1"},
    ]
    attempts: tuple[Any, ...] = (values, {"envVars": values})
    for payload in attempts:
        try:
            api.call("PUT", f"/services/{service_id}/env-vars", payload)
            print("RENDER_ENVIRONMENT_CONTRACT=PASS")
            return
        except ApiFailure as exc:
            if exc.status in {400, 404, 422}:
                continue
            raise
    raise PreviewDeployError("RENDER_ENVIRONMENT_UPDATE_FAILED")


def _trigger_render_deploy(api: JsonApi, service_id: str) -> str:
    for payload in ({"clearCache": "do_not_clear"}, {}):
        try:
            response = _mapping(
                api.call("POST", f"/services/{service_id}/deploys", payload),
                "RENDER_DEPLOY_RESPONSE_INVALID",
            )
        except ApiFailure as exc:
            if exc.status in {400, 404, 422}:
                continue
            raise
        nested = response.get("deploy")
        deploy = nested if isinstance(nested, dict) else response
        deploy_id = _string_field(deploy, "id")
        if deploy_id is not None:
            print(f"RENDER_DEPLOY_TRIGGERED deploy_id={deploy_id}")
            return deploy_id
    raise PreviewDeployError("RENDER_DEPLOY_TRIGGER_FAILED")


def _render_deploy_view(
    api: JsonApi,
    service_id: str,
    deploy_id: str,
) -> dict[str, Any]:
    try:
        return _mapping(
            api.call("GET", f"/deploys/{deploy_id}"),
            "RENDER_DEPLOY_STATUS_INVALID",
        )
    except ApiFailure as exc:
        if exc.status not in {404, 405}:
            raise
    rows = _flatten_items(
        api.call("GET", f"/services/{service_id}/deploys?limit=20"),
        key="deploy",
    )
    matches = [row for row in rows if _string_field(row, "id") == deploy_id]
    if len(matches) != 1:
        raise PreviewDeployError("RENDER_DEPLOY_STATUS_MISSING")
    return matches[0]


def _wait_for_render_deploy(
    api: JsonApi,
    service_id: str,
    deploy_id: str,
    *,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_status = "unknown"
    while time.monotonic() < deadline:
        deploy = _render_deploy_view(api, service_id, deploy_id)
        status = (_string_field(deploy, "status") or "unknown").lower()
        if status != last_status:
            print(f"RENDER_DEPLOY_STATUS={status}")
            last_status = status
        if status == "live":
            return
        if status in _DEPLOY_FAILURE_STATES:
            raise PreviewDeployError(f"RENDER_DEPLOY_{status.upper()}")
        time.sleep(15)
    raise PreviewDeployError("RENDER_DEPLOY_TIMEOUT")


def _render_service_url(service: dict[str, Any]) -> str | None:
    details = service.get("serviceDetails")
    candidates = [
        _string_field(service, "url"),
        _string_field(details, "url") if isinstance(details, dict) else None,
    ]
    for value in candidates:
        if value is None:
            continue
        normalized = value.rstrip("/")
        if normalized.startswith("https://"):
            return normalized
    return None


def _refresh_render_service(api: JsonApi, service_id: str) -> dict[str, Any]:
    return _service_from_response(api.call("GET", f"/services/{service_id}"))


def _wait_for_health(
    url: str,
    *,
    release_sha: str,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    target = f"{url.rstrip('/')}/healthz"
    while time.monotonic() < deadline:
        probe = request.Request(
            target,
            headers={"Accept": "application/json", "User-Agent": "omni-cio-preview-probe/1"},
            method="GET",
        )
        try:
            with request.urlopen(probe, timeout=30) as response:
                raw = response.read()
            payload = _mapping(
                json.loads(raw.decode("utf-8")),
                "PREVIEW_HEALTH_INVALID",
            )
            if (
                payload.get("status") == "ok"
                and payload.get("mode") == "synthetic_read_only_preview"
                and payload.get("release") == release_sha
            ):
                print("PREVIEW_PUBLIC_HEALTH=PASS")
                return
        except (
            error.HTTPError,
            error.URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            PreviewDeployError,
        ):
            pass
        time.sleep(20)
    raise PreviewDeployError("PREVIEW_PUBLIC_HEALTH_TIMEOUT")


def _write_outputs(url: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as stream:
            stream.write(f"preview_url={url}\n")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as stream:
            stream.write("## Omni-CIO V10 synthetic preview\n\n")
            stream.write(f"- Public URL: {url}\n")
            stream.write("- Mode: synthetic, shared, read-only\n")
            stream.write("- Real broker credentials: forbidden\n")
            stream.write("- Recurring plan authorization: 0\n")


def deploy_preview(*, expected_sha: str) -> str:
    release_sha = expected_sha.strip().lower()
    if _GIT_SHA_RE.fullmatch(release_sha) is None:
        raise PreviewDeployError("EXPECTED_RELEASE_SHA_INVALID")
    contract = _load_contract()
    neon = JsonApi(
        base_url=NEON_API_BASE,
        token=_required_env("NEON_API_KEY"),
        label="NEON_API",
    )
    render = JsonApi(
        base_url=RENDER_API_BASE,
        token=_required_env("RENDER_API_KEY"),
        label="RENDER_API",
    )

    project = _ensure_neon_project(neon, contract)
    dsn = _neon_connection_uri(neon, project, contract)
    print(f"::add-mask::{dsn}")

    service = _ensure_render_service(render, contract)
    service_id = _string_field(service, "id")
    if service_id is None:
        raise PreviewDeployError("RENDER_SERVICE_ID_MISSING")
    _put_render_env(render, service_id, dsn=dsn, release_sha=release_sha)
    deploy_id = _trigger_render_deploy(render, service_id)
    timeout = int(_mapping(contract["deployment"], "PREVIEW_DEPLOYMENT_INVALID")["health_timeout_seconds"])
    _wait_for_render_deploy(
        render,
        service_id,
        deploy_id,
        timeout_seconds=timeout,
    )
    service = _refresh_render_service(render, service_id)
    url = _render_service_url(service)
    if url is None:
        raise PreviewDeployError("RENDER_SERVICE_URL_MISSING")
    _wait_for_health(url, release_sha=release_sha, timeout_seconds=timeout)
    _write_outputs(url)
    print(f"PREVIEW_DEPLOYMENT=PASS url={url}")
    return url


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-sha", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    if not args.apply:
        raise PreviewDeployError("PREVIEW_APPLY_FLAG_REQUIRED")
    deploy_preview(expected_sha=str(args.expected_sha))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreviewDeployError, ApiFailure) as exc:
        print(f"PREVIEW_DEPLOYMENT=FAIL reason={exc}", file=sys.stderr)
        raise SystemExit(1) from exc
