from __future__ import annotations

import argparse
import ipaddress
from collections.abc import Callable
from datetime import datetime
import json
import os
import re
import sys
import time
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_BASE = "https://api.timeweb.cloud"
TOKEN_ENV = "TIMEWEB_CLOUD_API_TOKEN"
CANONICAL_APP_NAME = "omni-cio-v10"
CANONICAL_REPOSITORY = "MishaGameHacking/omni-cio-gateway"
CANONICAL_REPOSITORY_NAME = "omni-cio-gateway"
CANONICAL_REPOSITORY_PATH = "/MishaGameHacking/omni-cio-gateway"
CANONICAL_BRANCH = "main"
CANONICAL_FRAMEWORK = "docker"
CANONICAL_PUBLIC_HOSTNAME = "omnicio.ru"
CANDIDATE_HOSTNAME_ENV = "OMNI_V10_CANDIDATE_HOSTNAME"
RELEASE_SHA_ENV = "OMNI_V10_RELEASE_SHA"
POSTGRES_DSN_ENV = "OMNI_V10_POSTGRES_DSN"
POSTGRES_PRIVATE_HOSTADDR_ENV = "OMNI_V10_POSTGRES_PRIVATE_HOSTADDR"
POSTGRES_PRIVATE_NETWORK_CIDR_ENV = "OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR"
POSTGRES_RUNTIME_ROLE_ENV = "OMNI_V10_POSTGRES_RUNTIME_ROLE"
TRUSTED_EDGE_TLS_ENV = "OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED"
PUBLIC_MULTI_USER_ENV = "PUBLIC_MULTI_USER_ENABLED"
TELEGRAM_LOGIN_ENV = "OMNI_V10_TELEGRAM_LOGIN_ENABLED"
VK_LOGIN_ENV = "OMNI_V10_VK_ID_LOGIN_ENABLED"
DEPLOY_CONFIRMATION = "DEPLOY_EXACT_TIMEWEB_APP_COMMIT"
RUNTIME_MODE_PREACTIVATION = "preactivation"
RUNTIME_MODE_LIVE_OPERABLE = "live-operable"
_RUNTIME_MODES = frozenset({RUNTIME_MODE_PREACTIVATION, RUNTIME_MODE_LIVE_OPERABLE})
MAX_RESPONSE_BYTES = 1024 * 1024
_PAGE_SIZE = 100
_MAX_DEPLOY_HISTORY_PAGES = 100
_GET_DELAYS = (1.0, 2.0)
_LIVEZ_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0)
_HEALTHZ_RETRY_DELAYS = (1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0)
_DEPLOY_RECONCILE_DELAYS = (0.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0)
_POLL_DELAYS = (
    0.0,
    5.0,
    10.0,
    20.0,
    30.0,
    60.0,
    60.0,
    60.0,
    60.0,
    60.0,
    60.0,
)
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
_INFLIGHT_DEPLOY_STATUS = _VALID_DEPLOY_STATUS - _TERMINAL_FAILURE - {"success"}
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,96}$", re.ASCII)
_HOST_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$",
    re.ASCII,
)
_RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
    ipaddress.IPv4Network((0x0A000000, 8)),
    ipaddress.IPv4Network((0xAC100000, 12)),
    ipaddress.IPv4Network((0xC0A80000, 16)),
)
_TIMEWEB_RESERVED_PRIVATE_HOST_OCTETS = frozenset({1, 2, 3})
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


def _digest(value: object, code: str) -> str:
    if not isinstance(value, str):
        _stop(code)
    normalized = value.strip().lower()
    if _DIGEST_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _runtime_mode(value: object) -> str:
    if not isinstance(value, str):
        _stop("TIMEWEB_APP_RELEASE_RUNTIME_MODE_INVALID")
    normalized = value.strip().lower()
    if normalized not in _RUNTIME_MODES:
        _stop("TIMEWEB_APP_RELEASE_RUNTIME_MODE_INVALID")
    return normalized


def _validate_runtime_mode_evidence(runtime_mode: str, evidence_sha256: str) -> None:
    if runtime_mode == RUNTIME_MODE_PREACTIVATION:
        if evidence_sha256.strip():
            _stop("TIMEWEB_APP_RELEASE_UNEXPECTED_P5_LIVE_EVIDENCE")
        return
    _digest(evidence_sha256, "TIMEWEB_APP_RELEASE_P5_LIVE_EVIDENCE_REQUIRED")


def _safe_id(value: object, code: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        _stop(code)
    if isinstance(value, int) and value <= 0:
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
        if type(total) is not int or total < 0 or total != len(rows):
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


def _deploy_page(
    payload: dict[str, Any],
    existing_count: int,
) -> tuple[list[dict[str, Any]], int]:
    raw = payload.get("deploys")
    if not isinstance(raw, list):
        _stop(_DEPLOYS_INVALID)
    page_rows = [_mapping(item, _DEPLOYS_INVALID) for item in raw]
    total = _mapping(payload.get("meta"), _DEPLOYS_INVALID).get("total")
    if (
        type(total) is not int
        or total < 0
        or len(page_rows) > _PAGE_SIZE
        or existing_count + len(page_rows) > total
    ):
        _stop(_DEPLOYS_INVALID)
    return page_rows, total


def _require_stable_total(expected_total: int | None, total: int) -> int:
    if expected_total is not None and total != expected_total:
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_CHANGED")
    return total if expected_total is None else expected_total


def _validate_deploy_history_ids(rows: list[dict[str, Any]]) -> None:
    identifiers = [
        _safe_id(
            row.get("id"),
            "TIMEWEB_APP_RELEASE_DEPLOY_ID_INVALID",
        )
        for row in rows
    ]
    if len(set(identifiers)) != len(identifiers):
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_DUPLICATE_ID")


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
        rows: list[dict[str, Any]] = []
        expected_total: int | None = None
        for page in range(_MAX_DEPLOY_HISTORY_PAGES):
            offset = page * _PAGE_SIZE
            payload = self._get(
                f"/api/v1/apps/{safe}/deploys?limit={_PAGE_SIZE}&offset={offset}"
            )
            page_rows, total = _deploy_page(payload, len(rows))
            expected_total = _require_stable_total(expected_total, total)
            rows.extend(page_rows)
            if len(rows) == total:
                _validate_deploy_history_ids(rows)
                return {"deploys": rows, "meta": {"total": total}}
            if not page_rows or len(page_rows) < _PAGE_SIZE:
                _stop("TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_TRUNCATED")
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_HISTORY_TOO_LARGE")

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
                status = int(response.status)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            status = int(exc.code)
            if status in _TRANSIENT or status in {409, 423}:
                raise AmbiguousDeploy from None
            if status in {401, 403}:
                _stop("TIMEWEB_APP_RELEASE_AUTH_REJECTED", status=status)
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_REJECTED", status=status)
        except OSError:
            raise AmbiguousDeploy from None

        if status != 201:
            if 200 <= status < 300:
                raise AmbiguousDeploy from None
            _stop("TIMEWEB_APP_RELEASE_DEPLOY_REJECTED", status=status)
        try:
            return _decode(
                status,
                raw,
                201,
                "TIMEWEB_APP_RELEASE_DEPLOY",
            )
        except ReleaseStopped as exc:
            if exc.code in {
                "TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_TOO_LARGE",
                "TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_INVALID",
            }:
                raise AmbiguousDeploy from None
            raise


def _canonical_repository_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError:
        return False
    path = parsed.path.rstrip("/")
    if path.casefold().endswith(".git"):
        path = path[:-4]
    return (
        parsed.scheme.casefold() == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.hostname == "github.com"
        and port in {None, 443}
        and parsed.query == ""
        and parsed.fragment == ""
        and path.casefold() == CANONICAL_REPOSITORY_PATH.casefold()
    )


def _repository(app: dict[str, Any]) -> str:
    repository = _mapping(
        app.get("repository"), "TIMEWEB_APP_RELEASE_REPOSITORY_INVALID"
    )
    full_name = repository.get("full_name")
    name = repository.get("name")
    if (
        not isinstance(full_name, str)
        or not full_name.strip()
        or not isinstance(name, str)
        or not name.strip()
        or not _canonical_repository_url(repository.get("url"))
    ):
        _stop("TIMEWEB_APP_RELEASE_REPOSITORY_INVALID")
    return CANONICAL_REPOSITORY


def is_canonical_repository(app: dict[str, Any]) -> bool:
    try:
        return _repository(app) == CANONICAL_REPOSITORY
    except ReleaseStopped:
        return False


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


def _completed_deploy_time(row: dict[str, Any]) -> datetime:
    value = row.get("ended_at")
    if not isinstance(value, str) or not value.strip():
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_ENDED_AT_INVALID")
    try:
        observed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_ENDED_AT_INVALID")
    if observed.tzinfo is None or observed.utcoffset() is None:
        _stop("TIMEWEB_APP_RELEASE_DEPLOY_ENDED_AT_INVALID")
    return observed


def _last_known_good(rows: list[dict[str, Any]], expected: str) -> str | None:
    candidates: list[tuple[datetime, str]] = []
    for row in rows:
        _id, commit, status = _deploy(row)
        if status == "success" and commit != expected:
            candidates.append((_completed_deploy_time(row), commit))
    if not candidates:
        return None
    latest_time = max(observed for observed, _commit in candidates)
    latest_commits = {
        commit for observed, commit in candidates if observed == latest_time
    }
    if len(latest_commits) != 1:
        _stop("TIMEWEB_APP_RELEASE_LKG_HISTORY_AMBIGUOUS")
    return next(iter(latest_commits))


def _inflight_exact_deploy_id(
    rows: list[dict[str, Any]],
    expected: str,
) -> str | None:
    candidates = [
        deploy_id
        for row in rows
        for deploy_id, commit, status in (_deploy(row),)
        if commit == expected and status in _INFLIGHT_DEPLOY_STATUS
    ]
    if len(candidates) > 1:
        _stop("TIMEWEB_APP_RELEASE_MULTIPLE_INFLIGHT_EXACT_SHA")
    return candidates[0] if candidates else None


def _matching_app_row(api: ApiLike) -> dict[str, Any]:
    matches = [
        row
        for row in _rows(api.list_apps(), "apps", "TIMEWEB_APP_RELEASE_APPS_INVALID")
        if row.get("name") == CANONICAL_APP_NAME
        and is_canonical_repository(row)
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


def _expected_runtime_env(expected: str, runtime_mode: str) -> dict[str, str]:
    activation = "true" if runtime_mode == RUNTIME_MODE_LIVE_OPERABLE else "false"
    return {
        "OMNI_V10_HOSTED_RUNTIME": "1",
        "OMNI_V10_PUBLIC_HOSTNAME": CANONICAL_PUBLIC_HOSTNAME,
        RELEASE_SHA_ENV: expected,
        POSTGRES_RUNTIME_ROLE_ENV: "omni_cio_hosted_api",
        TRUSTED_EDGE_TLS_ENV: "true",
        PUBLIC_MULTI_USER_ENV: activation,
        TELEGRAM_LOGIN_ENV: activation,
    }


def validate_private_route_env(envs: dict[str, Any]) -> None:
    raw_hostaddr = envs.get(POSTGRES_PRIVATE_HOSTADDR_ENV)
    raw_cidr = envs.get(POSTGRES_PRIVATE_NETWORK_CIDR_ENV)
    if (
        not isinstance(raw_hostaddr, str)
        or not raw_hostaddr.strip()
        or not isinstance(raw_cidr, str)
        or not raw_cidr.strip()
    ):
        _stop("TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_REQUIRED")
    try:
        network = ipaddress.ip_network(raw_cidr.strip(), strict=True)
        address = ipaddress.ip_address(raw_hostaddr.strip())
    except ValueError:
        _stop("TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_INVALID")
    if (
        not isinstance(network, ipaddress.IPv4Network)
        or not any(network.subnet_of(parent) for parent in _RFC1918_NETWORKS)
        or not isinstance(address, ipaddress.IPv4Address)
        or address not in network
        or address in {network.network_address, network.broadcast_address}
        or (int(address) & 0xFF) in _TIMEWEB_RESERVED_PRIVATE_HOST_OCTETS
    ):
        _stop("TIMEWEB_APP_RELEASE_PRIVATE_ROUTE_INVALID")


def _validate_runtime_env(app: dict[str, Any], expected: str, runtime_mode: str) -> str:
    envs = _mapping(app.get("envs"), "TIMEWEB_APP_RELEASE_ENV_INVALID")
    for name, value in _expected_runtime_env(expected, runtime_mode).items():
        if envs.get(name) != value:
            _stop(f"TIMEWEB_APP_RELEASE_ENV_DRIFT:{name}")
    if str(envs.get(VK_LOGIN_ENV, "")).lower() not in {"", "0", "false"}:
        _stop("TIMEWEB_APP_RELEASE_VK_ACTIVATION_FORBIDDEN")

    dsn = envs.get(POSTGRES_DSN_ENV)
    if not isinstance(dsn, str) or not dsn.strip():
        _stop("TIMEWEB_APP_RELEASE_POSTGRES_DSN_REQUIRED")
    _mask(dsn)

    validate_private_route_env(envs)

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


def _validate_candidate_domains(
    app: dict[str, Any], candidate: str, runtime_mode: str
) -> None:
    domains = _domain_names(app)
    if candidate not in domains:
        _stop("TIMEWEB_APP_RELEASE_CANDIDATE_DOMAIN_MISSING")
    has_canonical = CANONICAL_PUBLIC_HOSTNAME in domains
    if runtime_mode == RUNTIME_MODE_PREACTIVATION and has_canonical:
        _stop("TIMEWEB_APP_RELEASE_PREMATURE_CANONICAL_DOMAIN")
    if runtime_mode == RUNTIME_MODE_LIVE_OPERABLE and not has_canonical:
        _stop("TIMEWEB_APP_RELEASE_CANONICAL_DOMAIN_REQUIRED")


def _candidate_app(
    api: ApiLike, expected: str, runtime_mode: str
) -> tuple[dict[str, Any], str, str]:
    match = _matching_app_row(api)
    app_id = _safe_id(match.get("id"), _APP_ID_INVALID)
    app = _mapping(api.get_app(app_id).get("app"), "TIMEWEB_APP_RELEASE_APP_INVALID")
    _validate_app_shape(app, app_id)
    candidate = _validate_runtime_env(app, expected, runtime_mode)
    _validate_candidate_domains(app, candidate, runtime_mode)
    return app, app_id, candidate


def _livez_attempt(
    active: Any,
    request: Request,
) -> tuple[dict[str, Any] | None, str | None, int | None]:
    try:
        with active.open(request, timeout=30.0) as response:
            status = int(response.status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = int(exc.code)
        if status in _TRANSIENT:
            return None, "http", status
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_HTTP_ERROR", status=status)
    except OSError:
        return None, "transport", None
    if status in _TRANSIENT:
        return None, "http", status
    if status != 200:
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_HTTP_ERROR", status=status)
    return _decode(status, raw, 200, "TIMEWEB_APP_RELEASE_LIVEZ"), None, None


def _stop_livez_retry(failure: str | None, status: int | None) -> NoReturn:
    if failure == "http" and status is not None:
        _stop("TIMEWEB_APP_RELEASE_LIVEZ_HTTP_ERROR", status=status)
    _stop("TIMEWEB_APP_RELEASE_LIVEZ_TRANSPORT_FAILED")


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
    for attempt in range(len(_LIVEZ_RETRY_DELAYS) + 1):
        payload, failure, status = _livez_attempt(active, request)
        if payload is None:
            if attempt >= len(_LIVEZ_RETRY_DELAYS):
                _stop_livez_retry(failure, status)
            time.sleep(_LIVEZ_RETRY_DELAYS[attempt])
            continue
        if payload.get("status") != "ok":
            _stop("TIMEWEB_APP_RELEASE_LIVEZ_NOT_OK")
        observed = _sha(
            payload.get("release_sha"),
            "TIMEWEB_APP_RELEASE_LIVEZ_SHA_INVALID",
        )
        if observed == expected:
            return
        if attempt >= len(_LIVEZ_RETRY_DELAYS):
            _stop("TIMEWEB_APP_RELEASE_LIVEZ_SHA_DRIFT")
        time.sleep(_LIVEZ_RETRY_DELAYS[attempt])
    raise AssertionError("bounded liveness verification exhausted")


def _healthz_unavailable_payload(raw: bytes) -> dict[str, Any] | None:
    if not raw or len(raw) > MAX_RESPONSE_BYTES:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    if value.get("status") != "unavailable":
        return None
    if not isinstance(value.get("release_sha"), str):
        return None
    if not isinstance(value.get("synthetic_preview"), bool):
        return None
    return value


def _healthz_attempt(
    active: Any,
    request: Request,
) -> tuple[dict[str, Any] | None, str | None, int | None]:
    try:
        with active.open(request, timeout=30.0) as response:
            status = int(response.status)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        status = int(exc.code)
        if status == 503:
            try:
                raw = exc.read(MAX_RESPONSE_BYTES + 1)
            except OSError:
                raw = b""
            payload = _healthz_unavailable_payload(raw)
            if payload is not None:
                return payload, None, status
        if status in _TRANSIENT:
            return None, "http", status
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_HTTP_ERROR", status=status)
    except OSError:
        return None, "transport", None
    if status == 503:
        payload = _healthz_unavailable_payload(raw)
        if payload is not None:
            return payload, None, status
    if status in _TRANSIENT:
        return None, "http", status
    if status != 200:
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_HTTP_ERROR", status=status)
    return _decode(status, raw, 200, "TIMEWEB_APP_RELEASE_HEALTHZ"), None, None


def _stop_healthz_retry(failure: str | None, status: int | None) -> NoReturn:
    if failure == "http" and status is not None:
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_HTTP_ERROR", status=status)
    _stop("TIMEWEB_APP_RELEASE_HEALTHZ_TRANSPORT_FAILED")


def _healthz_state(payload: dict[str, Any], expected: str) -> tuple[bool, bool]:
    if payload.get("synthetic_preview") is not False:
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_SYNTHETIC_PREVIEW_FORBIDDEN")
    observed = _sha(
        payload.get("release_sha"),
        "TIMEWEB_APP_RELEASE_HEALTHZ_SHA_INVALID",
    )
    database_ready = (
        payload.get("status") == "ok" and payload.get("database") == "READY"
    )
    return database_ready, observed == expected


def _stop_healthz_terminal(*, database_ready: bool, release_matches: bool) -> NoReturn:
    if not release_matches:
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_SHA_DRIFT")
    if not database_ready:
        _stop("TIMEWEB_APP_RELEASE_HEALTHZ_DATABASE_NOT_READY")
    raise AssertionError("unreachable healthz terminal state")


def _verify_healthz(hostname: str, expected: str, *, opener: Any | None = None) -> None:
    request = Request(
        f"https://{hostname}/healthz",
        headers={
            "Accept": _JSON_CONTENT_TYPE,
            "User-Agent": "omni-cio-v10-timeweb-healthz",
        },
        method="GET",
    )
    active = opener or _NO_REDIRECT_OPENER
    last_attempt = len(_HEALTHZ_RETRY_DELAYS)
    for attempt in range(last_attempt + 1):
        payload, failure, status = _healthz_attempt(active, request)
        if payload is None:
            if attempt == last_attempt:
                _stop_healthz_retry(failure, status)
            time.sleep(_HEALTHZ_RETRY_DELAYS[attempt])
            continue
        database_ready, release_matches = _healthz_state(payload, expected)
        if database_ready and release_matches:
            return
        if attempt == last_attempt:
            _stop_healthz_terminal(
                database_ready=database_ready,
                release_matches=release_matches,
            )
        time.sleep(_HEALTHZ_RETRY_DELAYS[attempt])
    raise AssertionError("bounded database readiness verification exhausted")


def _reconcile(api: ApiLike, app_id: str, before: frozenset[str], expected: str) -> str:
    for delay in _DEPLOY_RECONCILE_DELAYS:
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
    api: ApiLike,
    expected: str,
    *,
    runtime_mode: str = RUNTIME_MODE_PREACTIVATION,
    livez_opener: Any | None = None,
) -> str | None:
    app, app_id, hostname = _candidate_app(api, expected, runtime_mode)
    if (
        app.get("status") != "active"
        or _sha(app.get(_COMMIT_SHA_KEY), "TIMEWEB_APP_RELEASE_ACTIVE_SHA_INVALID")
        != expected
    ):
        _stop("TIMEWEB_APP_RELEASE_NOT_ACTIVE_EXACT_SHA")
    _verify_livez(hostname, expected, opener=livez_opener)
    _verify_healthz(hostname, expected, opener=livez_opener)
    return _last_known_good(_deploys(api, app_id), expected)


def _verify_completed_deploy(
    api: ApiLike,
    app_id: str,
    deploy_id: str,
    hostname: str,
    expected: str,
    runtime_mode: str,
) -> None:
    _wait(api, app_id, deploy_id, expected)
    refreshed, refreshed_id, refreshed_hostname = _candidate_app(
        api, expected, runtime_mode
    )
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


def _perform_exact_deploy(
    api: ApiLike,
    app_id: str,
    hostname: str,
    expected: str,
    runtime_mode: str,
    before_rows: list[dict[str, Any]],
) -> None:
    before = frozenset(_deploy(row)[0] for row in before_rows)
    try:
        response = api.deploy_once(app_id, expected)
    except AmbiguousDeploy:
        deploy_id = _reconcile(api, app_id, before, expected)
    else:
        try:
            row = _mapping(
                response.get("deploy"),
                "TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_INVALID",
            )
            deploy_id, commit, _status = _deploy(row)
            if commit != expected or deploy_id in before:
                _stop("TIMEWEB_APP_RELEASE_DEPLOY_RESPONSE_DRIFT")
        except ReleaseStopped:
            deploy_id = _reconcile(api, app_id, before, expected)

    _verify_completed_deploy(
        api,
        app_id,
        deploy_id,
        hostname,
        expected,
        runtime_mode,
    )


def deploy(
    api: ApiLike,
    expected: str,
    confirmation: str,
    *,
    runtime_mode: str = RUNTIME_MODE_PREACTIVATION,
    livez_opener: Any | None = None,
) -> str | None:
    if confirmation != DEPLOY_CONFIRMATION:
        _stop("TIMEWEB_APP_RELEASE_CONFIRMATION_REQUIRED")

    app, app_id, hostname = _candidate_app(api, expected, runtime_mode)
    before_rows = _deploys(api, app_id)
    last_known_good = _last_known_good(before_rows, expected)
    inflight = _inflight_exact_deploy_id(before_rows, expected)
    already_active = (
        app.get("status") == "active" and app.get(_COMMIT_SHA_KEY) == expected
    )
    if not already_active:
        if inflight is not None:
            _verify_completed_deploy(
                api,
                app_id,
                inflight,
                hostname,
                expected,
                runtime_mode,
            )
        else:
            _perform_exact_deploy(
                api, app_id, hostname, expected, runtime_mode, before_rows
            )

    _verify_livez(hostname, expected, opener=livez_opener)
    _verify_healthz(hostname, expected, opener=livez_opener)
    return last_known_good


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    token: str,
    confirmation: str = "",
    runtime_mode: str = RUNTIME_MODE_PREACTIVATION,
    p5_live_evidence_sha256: str = "",
    api: ApiLike | None = None,
    livez_opener: Any | None = None,
) -> str | None:
    expected = _sha(expected_sha, "TIMEWEB_APP_RELEASE_EXPECTED_SHA_INVALID")
    if expected != _sha(observed_main_sha, "TIMEWEB_APP_RELEASE_MAIN_SHA_INVALID"):
        _stop("TIMEWEB_APP_RELEASE_MAIN_SHA_DRIFT")
    mode = _runtime_mode(runtime_mode)
    _validate_runtime_mode_evidence(mode, p5_live_evidence_sha256)
    client = api or TimewebAppApi(token)
    if operation == "observe":
        return observe(
            client,
            expected,
            runtime_mode=mode,
            livez_opener=livez_opener,
        )
    if operation == "deploy":
        return deploy(
            client,
            expected,
            confirmation,
            runtime_mode=mode,
            livez_opener=livez_opener,
        )
    _stop("TIMEWEB_APP_RELEASE_OPERATION_INVALID")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("observe", "deploy"), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    parser.add_argument(
        "--runtime-mode",
        choices=(RUNTIME_MODE_PREACTIVATION, RUNTIME_MODE_LIVE_OPERABLE),
        default=RUNTIME_MODE_PREACTIVATION,
    )
    parser.add_argument("--p5-live-evidence-sha256", default="")
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
            runtime_mode=args.runtime_mode,
            p5_live_evidence_sha256=args.p5_live_evidence_sha256,
        )
    except ReleaseStopped as exc:
        print(exc.code, file=sys.stderr)
        return 1
    marker = (
        "TIMEWEB_APP_EXACT_SHA_CANDIDATE=PASS "
        f"release_sha={args.expected_sha} runtime_mode={args.runtime_mode}"
    )
    if last_known_good is not None:
        marker += f" last_known_good_sha={last_known_good}"
    print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
