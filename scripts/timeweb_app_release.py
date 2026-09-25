from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
import re
import sys
import time
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_BASE = "https://api.timeweb.cloud"
TOKEN_ENV = "TIMEWEB_CLOUD_API_TOKEN"
CANONICAL_APP_NAME = "omni-cio-v10"
CANONICAL_REPOSITORY = "MishaGameHacking/omni-cio-gateway"
CANONICAL_BRANCH = "main"
CANONICAL_FRAMEWORK = "docker"
CANONICAL_PUBLIC_HOSTNAME = "omnicio.ru"
CANDIDATE_HOSTNAME_ENV = "OMNI_V10_CANDIDATE_HOSTNAME"
RELEASE_SHA_ENV = "OMNI_V10_RELEASE_SHA"
POSTGRES_DSN_ENV = "OMNI_V10_POSTGRES_DSN"
POSTGRES_RUNTIME_ROLE_ENV = "OMNI_V10_POSTGRES_RUNTIME_ROLE"
TRUSTED_EDGE_TLS_ENV = "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED"
PUBLIC_MULTI_USER_ENV = "PUBLIC_MULTI_USER_ENABLED"
TELEGRAM_LOGIN_ENV = "OMNI_V10_TELEGRAM_LOGIN_ENABLED"
VK_LOGIN_ENV = "OMNI_V10_VK_ID_LOGIN_ENABLED"
DEPLOY_CONFIRMATION = "DEPLOY_EXACT_TIMEWEB_APP_COMMIT"
MAX_RESPONSE_BYTES = 1024 * 1024
_PAGE_SIZE = 100
_GET_DELAYS = (1.0, 2.0)
_POLL_DELAYS = (0.0, 5.0, 10.0, 20.0, 30.0, 60.0, 60.0)
_TRANSIENT = frozenset({408, 429, 500, 502, 503, 504})
_TERMINAL_FAILURE = frozenset({"failure", "access_error", "stopped"})
_VALID_DEPLOY_STATUS = frozenset(
    {
        "created",
        "started",
        "preparing_environment",
        "cloning_code",
        "installing_dependencies",
        "building_code",
        "checking_ssl_certs",
        "cleaning_up",
        "running_container",
        "stopping",
        "stopped",
        "failure",
        "success",
        "access_error",
    }
)
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,96}$", re.ASCII)
_HOST_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.ASCII,
)
_RETIRED_ENV_MARKERS = ("CLOUDFLARE", "NEON", "RENDER", "CLOUDRU")
_APP_ID_INVALID = "TIMEWEB_APP_RELEASE_APP_ID_INVALID"
_DEPLOYS_INVALID = "TIMEWEB_APP_RELEASE_DEPLOYS_INVALID"
_COMMIT_SHA_KEY = "commit_sha"
_JSON_CONTENT_TYPE = "application/json"
Sleep = Callable[[float], None]


class ReleaseStopped(RuntimeError):
    def __init__(self, code: str, *, status: int | None = None) -> None:
        self.code = code
        suffix = "" if status is None else f" status={status}"
        super().__init__(f"{code}{suffix}")


class AmbiguousDeploy(RuntimeError):
    pass


class ApiLike(Protocol):
    sleeper: Sleep

    def list_apps(self) -> dict[str, Any]: ...
    def get_app(self, app_id: str) -> dict[str, Any]: ...
    def list_deploys(self, app_id: str) -> dict[str, Any]: ...
    def deploy_once(self, app_id: str, sha: str) -> dict[str, Any]: ...


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


def _stop(code: str, *, status: int | None = None) -> NoReturn:
    raise ReleaseStopped(code, status=status)


def _mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}")


def _sha(value: object, code: str) -> str:
    if not isinstance(value, str):
        _stop(code)
    normalized = value.strip().lower()
    if _SHA_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _safe_id(value: object, code: str) -> str:
    if isinstance(value, bool):
        _stop(code)
    text = str(value).strip()
    if _ID_RE.fullmatch(text) is None:
        _stop(code)
    return text


def _host(value: object, code: str) -> str:
    if not isinstance(value, str):
        _stop(code)
    normalized = value.strip().lower().rstrip(".")
    if len(normalized) > 253 or _HOST_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _stop(code)
    return value


def _rows(payload: dict[str, Any], key: str, code: str) -> list[dict[str, Any]]:
    raw = payload.get(key)
    if not isinstance(raw, list):
        _stop(code)
    rows = [_mapping(item, code) for item in raw]
    meta = payload.get("meta")
    if meta is not None:
        total = _mapping(meta, code).get("total")
        if type(total) is not int or total != len(rows) or total > _PAGE_SIZE:
            _stop(code)
    return rows


def _decode(status: int, raw: bytes, expected: int, code: str) -> dict[str, Any]:
    if status != expected:
        _stop(code, status=status)
    if len(raw) > MAX_RESPONSE_BYTES:
        _stop(f"{code}_RESPONSE_TOO_LARGE")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _stop(f"{code}_RESPONSE_INVALID")
    return _mapping(value, f"{code}_RESPONSE_INVALID")


class TimewebAppApi:
    def __init__(
        self, token: str, *, opener: Any | None = None, sleeper: Sleep = time.sleep
    ) -> None:
        if not token:
            _stop("TIMEWEB_CLOUD_API_TOKEN_REQUIRED")
        _mask(token)
        self._token = token
        self._opener = opener or _NO_REDIRECT_OPENER
        self.sleeper = sleeper

    def _request(
        self, method: str, path: str, body: dict[str, object] | None = None
    ) -> Request:
        if not path.startswith("/api/v1/") or ".." in path or "://" in path:
            _stop("TIMEWEB_APP_RELEASE_API_PATH_INVALID")
        headers = {
            "Accept": _JSON_CONTENT_TYPE,
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "omni-cio-v10-timeweb-exact-sha-release",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = _JSON_CONTENT_TYPE
            data = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
        return Request(API_BASE + path, headers=headers, data=data, method=method)

    def _get(self, path: str) -> dict[str, Any]:
        request = self._request("GET", path)
        attempts = len(_GET_DELAYS) + 1
        for attempt in range(attempts):
            try:
                with self._opener.open(request, timeout=30.0) as response:
                    return _decode(
                        int(response.status),
                        response.read(MAX_RESPONSE_BYTES + 1),
                        200,
                        "TIMEWEB_APP_RELEASE_READ",
                    )
            except HTTPError as exc:
                status = int(exc.code)
                if status in _TRANSIENT and attempt + 1 < attempts:
                    self.sleeper(_GET_DELAYS[attempt])
                    continue
                if status in {401, 403}:
                    _stop("TIMEWEB_APP_RELEASE_AUTH_REJECTED", status=status)
                _stop("TIMEWEB_APP_RELEASE_READ_REJECTED", status=status)
            except OSError:
                if attempt + 1 >= attempts:
                    _stop("TIMEWEB_APP_RELEASE_READ_TRANSPORT_FAILED")
                self.sleeper(_GET_DELAYS[attempt])
        raise AssertionError("bounded retry exhausted")

    def list_apps(self) -> dict[str, Any]:
        return self._get("/api/v1/apps")

    def get_app(self, app_id: str) -> dict[str, Any]:
        safe = _safe_id(app_id, _APP_ID_INVALID)
        return self._get(f"/api/v1/apps/{safe}")

    def list_deploys(self, app_id: str) -> dict[str, Any]:
        safe = _safe_id(app_id, _APP_ID_INVALID)
        return self._get(f"/api/v1/apps/{safe}/deploys?limit={_PAGE_SIZE}&offset=0")

    def deploy_once(self, app_id: str, sha: str) -> dict[str, Any]:
        safe = _safe_id(app_id, _APP_ID_INVALID)
        expected = _sha(sha, "TIMEWEB_APP_RELEASE_SHA_INVALID")
        request = self._request(
            "POST",
            f"/api/v1/apps/{safe}/deploy",
            {_COMMIT_SHA_KEY: expected},
        )
        try:
            with self._opener.open(request, timeout=30.0) as response:
                return _decode(
                    int(response.status),
                    response.read(MAX_RESPONSE_BYTES + 1),
                    201,
                    "TIMEWEB_APP_RELEASE_DEPLOY",
                )
        except HTTPError as exc:
            status = int(exc.code)
            if status in _TRANSIENT or status in {409, 423}:
                raise AmbiguousDeploy from None
            if status in {401, 403}:
                _stop("TIMEWEB_APP_RELEASE_AUTH_REJECTED", status=status)
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_REJECTED", status=status)
        except OSError:
            raise AmbiguousDeploy from None


def _repository(app: dict[str, Any]) -> str:
    repository = _mapping(
        app.get("repository"), "TIMEWEB_APP_RELEASE_REPOSITORY_INVALID"
    )
    full_name = repository.get("full_name")
    if not isinstance(full_name, str):
        _stop("TIMEWEB_APP_RELEASE_REPOSITORY_INVALID")
    return full_name


def _deploy(row: dict[str, Any]) -> tuple[str, str, str]:
    deploy_id = _safe_id(row.get("id"), "TIMEWEB_APP_RELEASE_DEPLOY_ID_INVALID")
    commit = _sha(row.get(_COMMIT_SHA_KEY), "TIMEWEB_APP_RELEASE_DEPLOY_SHA_INVALID")
    status = row.get("status")
    if not isinstance(status, str) or status not in _VALID_DEPLOY_STATUS:
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_STATUS_INVALID")
    return deploy_id, commit, status


def _deploys(api: ApiLike, app_id: str) -> list[dict[str, Any]]:
    rows = _rows(api.list_deploys(app_id), "deploys", _DEPLOYS_INVALID)
    for row in rows:
        _deploy(row)
    return rows


def _last_known_good(rows: list[dict[str, Any]], expected: str) -> str | None:
    for row in rows:
        _id, commit, status = _deploy(row)
        if status == "success" and commit != expected:
            return commit
    return None


def _matching_app_row(api: ApiLike) -> dict[str, Any]:
    matches = [
        row
        for row in _rows(api.list_apps(), "apps", "TIMEWEB_APP_RELEASE_APPS_INVALID")
        if row.get("name") == CANONICAL_APP_NAME
        and _repository(row) == CANONICAL_REPOSITORY
    ]
    if len(matches) != 1:
        _stop("TIMEWEB_APP_RELEASE_TARGET_NOT_UNIQUE")
    return matches[0]


def _validate_app_shape(app: dict[str, Any], app_id: str) -> None:
    if _safe_id(app.get("id"), _APP_ID_INVALID) != app_id:
        _stop("TIMEWEB_APP_RELEASE_APP_ID_DRIFT")
    expected_shape = (
        app.get("type") == "backend"
        and app.get("framework") == CANONICAL_FRAMEWORK
        and app.get("branch_name") == CANONICAL_BRANCH
        and _repository(app) == CANONICAL_REPOSITORY
    )
    if not expected_shape:
        _stop("TIMEWEB_APP_RELEASE_APP_SHAPE_DRIFT")
    if app.get("is_auto_deploy") is not False:
        _stop("TIMEWEB_APP_RELEASE_AUTODEPLOY_FORBIDDEN")


def _expected_runtime_env(expected: str) -> dict[str, str]:
    return {
        "OMNI_V10_HOSTED_RUNTIME": "1",
        "OMNI_V10_PUBLIC_HOSTNAME": CANONICAL_PUBLIC_HOSTNAME,
        RELEASE_SHA_ENV: expected,
        POSTGRES_RUNTIME_ROLE_ENV: "omni_cio_hosted_api",
        TRUSTED_EDGE_TLS_ENV: "true",
        PUBLIC_MULTI_USER_ENV: "false",
        TELEGRAM_LOGIN_ENV: "false",
    }


def _validate_runtime_env(app: dict[str, Any], expected: str) -> str:
    envs = _mapping(app.get("envs"), "TIMEWEB_APP_RELEASE_ENV_INVALID")
    for name, value in _expected_runtime_env(expected).items():
        if envs.get(name) != value:
            _stop(f"TIMEWEB_APP_RELEASE_ENV_DRIFT:{name}")
    if str(envs.get(VK_LOGIN_ENV, "")).lower() not in {"", "0", "false"}:
        _stop("TIMEWEB_APP_RELEASE_VK_ACTIVATION_FORBIDDEN")

    dsn = envs.get(POSTGRES_DSN_ENV)
    if not isinstance(dsn, str) or not dsn.strip():
        _stop("TIMEWEB_APP_RELEASE_POSTGRES_DSN_REQUIRED")
    _mask(dsn)

    retired_names = [
        str(name)
        for name in envs
        if any(marker in str(name).upper() for marker in _RETIRED_ENV_MARKERS)
    ]
    if retired_names:
        _stop("TIMEWEB_APP_RELEASE_RETIRED_PROVIDER_ENV_PRESENT")

    return _host(
        envs.get(CANDIDATE_HOSTNAME_ENV),
        "TIMEWEB_APP_RELEASE_CANDIDATE_HOST_INVALID",
    )


def _domain_names(app: dict[str, Any]) -> set[str]:
    raw_domains = app.get("domains")
    if not isinstance(raw_domains, list):
        _stop("TIMEWEB_APP_RELEASE_DOMAINS_INVALID")
    return {
        _host(
            _mapping(row, "TIMEWEB_APP_RELEASE_DOMAINS_INVALID").get("fqdn"),
            "TIMEWEB_APP_RELEASE_DOMAINS_INVALID",
        )
        for row in raw_domains
    }


def _validate_candidate_domains(app: dict[str, Any], candidate: str) -> None:
    domains = _domain_names(app)
    if candidate not in domains:
        _stop("TIMEWEB_APP_RELEASE_CANDIDATE_DOMAIN_MISSING")
    if CANONICAL_PUBLIC_HOSTNAME in domains:
        _stop("TIMEWEB_APP_RELEASE_PREMATURE_CANONICAL_DOMAIN")


def _candidate_app(api: ApiLike, expected: str) -> tuple[dict[str, Any], str, str]:
    match = _matching_app_row(api)
    app_id = _safe_id(match.get("id"), _APP_ID_INVALID)
    app = _mapping(api.get_app(app_id).get("app"), "TIMEWEB_APP_RELEASE_APP_INVALID")
    _validate_app_shape(app, app_id)
    candidate = _validate_runtime_env(app, expected)
    _validate_candidate_domains(app, candidate)
    return app, app_id, candidate


def _verify_livez(hostname: str, expected: str, *, opener: Any | None = None) -> None:
    request = Request(
        f"https://{hostname}/livez",
        headers={
            "Accept": _JSON_CONTENT_TYPE,
            "User-Agent": "omni-cio-v10-timeweb-livez",
        },
        method="GET",
    )
    active = opener or _NO_REDIRECT_OPENER
    try:
        with active.open(request, timeout=30.0) as response:
            payload = _decode(
                int(response.status),
                response.read(MAX_RESPONSE_BYTES + 1),
                200,
                "TIMEWEB_APP_RELEASE_LIVEZ",
            )
    except HTTPError as exc:
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_HTTP_ERROR", status=int(exc.code))
    except OSError:
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_TRANSPORT_FAILED")
    if payload.get("status") != "ok":
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_NOT_OK")
    if (
        _sha(payload.get("release_sha"), "TIMEWEB_APP_RELEASE_LIVEZ_SHA_INVALID")
        != expected
    ):
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_SHA_DRIFT")


def _reconcile(api: ApiLike, app_id: str, before: frozenset[str], expected: str) -> str:
    for delay in (0.0, 2.0, 5.0, 10.0):
        if delay:
            api.sleeper(delay)
        candidates = []
        for row in _deploys(api, app_id):
            deploy_id, commit, _status = _deploy(row)
            if deploy_id not in before and commit == expected:
                candidates.append(deploy_id)
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            _stop("TIMEWEB_APP_RELEASE_AMBIGUOUS_DUPLICATE_DEPLOY")
    _stop("TIMEWEB_APP_RELEASE_AMBIGUOUS_UNRESOLVED")


def _deploy_status_for_id(
    api: ApiLike,
    app_id: str,
    deploy_id: str,
    expected: str,
) -> str | None:
    matched: str | None = None
    for row in _deploys(api, app_id):
        current_id, commit, status = _deploy(row)
        if current_id != deploy_id:
            continue
        if matched is not None:
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_ID_NOT_UNIQUE")
        if commit != expected:
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_SHA_DRIFT")
        matched = status
    return matched


def _wait(api: ApiLike, app_id: str, deploy_id: str, expected: str) -> None:
    for delay in _POLL_DELAYS:
        if delay:
            api.sleeper(delay)
        status = _deploy_status_for_id(api, app_id, deploy_id, expected)
        if status == "success":
            return
        if status in _TERMINAL_FAILURE:
            _stop(f"TIMEWEB_APP_RELEASE_DEPLOY_TERMINAL_{status.upper()}")
    _stop("TIMEWEB_APP_RELEASE_DEPLOY_TIMEOUT")


def observe(
    api: ApiLike, expected: str, *, livez_opener: Any | None = None
) -> str | None:
    app, app_id, hostname = _candidate_app(api, expected)
    if (
        app.get("status") != "active"
        or _sha(app.get(_COMMIT_SHA_KEY), "TIMEWEB_APP_RELEASE_ACTIVE_SHA_INVALID")
        != expected
    ):
        _stop("TIMEWEB_APP_RELEASE_NOT_ACTIVE_EXACT_SHA")
    _verify_livez(hostname, expected, opener=livez_opener)
    return _last_known_good(_deploys(api, app_id), expected)


def _perform_exact_deploy(
    api: ApiLike,
    app_id: str,
    hostname: str,
    expected: str,
    before_rows: list[dict[str, Any]],
) -> None:
    before = frozenset(_deploy(row)[0] for row in before_rows)
    try:
        response = api.deploy_once(app_id, expected)
    except AmbiguousDeploy:
        deploy_id = _reconcile(api, app_id, before, expected)
    else:
        row = _mapping(
            response.get("deploy"), "TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_INVALID"
        )
        deploy_id, commit, _status = _deploy(row)
        if commit != expected or deploy_id in before:
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_DRIFT")

    _wait(api, app_id, deploy_id, expected)
    refreshed, refreshed_id, refreshed_hostname = _candidate_app(api, expected)
    if refreshed_id != app_id or refreshed_hostname != hostname:
        _stop("TIMEWEB_APP_RELEASE_APP_POSTDEPLOY_DRIFT")
    if (
        refreshed.get("status") != "active"
        or _sha(
            refreshed.get(_COMMIT_SHA_KEY), "TIMEWEB_APP_RELEASE_ACTIVE_SHA_INVALID"
        )
        != expected
    ):
        _stop("TIMEWEB_APP_RELEASE_POSTDEPLOY_NOT_ACTIVE")


def deploy(
    api: ApiLike,
    expected: str,
    confirmation: str,
    *,
    livez_opener: Any | None = None,
) -> str | None:
    if confirmation != DEPLOY_CONFIRMATION:
        _stop("TIMEWEB_APP_RELEASE_CONFIRMATION_REQUIRED")

    app, app_id, hostname = _candidate_app(api, expected)
    before_rows = _deploys(api, app_id)
    last_known_good = _last_known_good(before_rows, expected)
    already_active = (
        app.get("status") == "active" and app.get(_COMMIT_SHA_KEY) == expected
    )
    if not already_active:
        _perform_exact_deploy(api, app_id, hostname, expected, before_rows)

    _verify_livez(hostname, expected, opener=livez_opener)
    return last_known_good


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    token: str,
    confirmation: str = "",
    api: ApiLike | None = None,
    livez_opener: Any | None = None,
) -> str | None:
    expected = _sha(expected_sha, "TIMEWEB_APP_RELEASE_EXPECTED_SHA_INVALID")
    if expected != _sha(observed_main_sha, "TIMEWEB_APP_RELEASE_MAIN_SHA_INVALID"):
        _stop("TIMEWEB_APP_RELEASE_MAIN_SHA_DRIFT")
    client = api or TimewebAppApi(token)
    if operation == "observe":
        return observe(client, expected, livez_opener=livez_opener)
    if operation == "deploy":
        return deploy(
            client,
            expected,
            confirmation,
            livez_opener=livez_opener,
        )
    _stop("TIMEWEB_APP_RELEASE_OPERATION_INVALID")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("observe", "deploy"), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args()
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print("TIMEWEB_CLOUD_API_TOKEN_REQUIRED", file=sys.stderr)
        return 1
    try:
        last_known_good = run(
            operation=args.operation,
            expected_sha=args.expected_sha,
            observed_main_sha=args.observed_main_sha,
            token=token,
            confirmation=args.confirmation,
        )
    except ReleaseStopped as exc:
        print(exc.code, file=sys.stderr)
        return 1
    marker = f"TIMEWEB_APP_EXACT_SHA_CANDIDATE=PASS release_sha={args.expected_sha}"
    if last_known_good is not None:
        marker += f" last_known_good_sha={last_known_good}"
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
