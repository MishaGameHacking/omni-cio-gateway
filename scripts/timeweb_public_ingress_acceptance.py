from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, NoReturn, Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from scripts import timeweb_app_release as app_release


CANONICAL_HOSTNAME = "omnicio.ru"
CANONICAL_ORIGIN = "https://omnicio.ru"
ACCEPT_CONFIRMATION = "ACCEPT_OMNICIO_RU_TIMEWEB_PUBLIC_INGRESS"
MAX_RESPONSE_BYTES = 1024 * 1024
_PAGE_SIZE = 100
_JSON_CONTENT_TYPE = "application/json"
_HTML_CONTENT_TYPE = "text/html"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,96}$", re.ASCII)
_RETIRED_DOMAIN = "omni-cio.ru"
_RETIRED_EDGE_HEADERS = frozenset(
    {
        "cf-ray",
        "cf-cache-status",
        "x-render-origin-server",
        "x-render-routing",
    }
)
_RETIRED_EDGE_VALUES = ("cloudflare", "render")
_REQUIRED_CSP_DIRECTIVES = (
    "default-src 'self'",
    "base-uri 'none'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
)


class PublicIngressStopped(RuntimeError):
    pass


class ReadOnlyAppApiLike(Protocol):
    def list_apps(self) -> dict[str, Any]: ...

    def get_app(self, app_id: str) -> dict[str, Any]: ...

    def list_deploys(self, app_id: str) -> dict[str, Any]: ...


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


class TimewebIngressReadApi:
    """Read-only facade over the reviewed Timeweb App API transport."""

    def __init__(self, token: str) -> None:
        self._api = app_release.TimewebAppApi(token)

    def list_apps(self) -> dict[str, Any]:
        return self._api.list_apps()

    def get_app(self, app_id: str) -> dict[str, Any]:
        return self._api.get_app(app_id)

    def list_deploys(self, app_id: str) -> dict[str, Any]:
        return self._api.list_deploys(app_id)


_NO_REDIRECT_OPENER = build_opener(_RejectRedirects())


def _stop(code: str) -> NoReturn:
    raise PublicIngressStopped(code)


def _sha(value: str, code: str) -> str:
    normalized = value.strip().lower()
    if _SHA_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _sha256(value: str, code: str) -> str:
    normalized = value.strip().lower()
    if _SHA256_RE.fullmatch(normalized) is None:
        _stop(code)
    return normalized


def _safe_id(value: object) -> str:
    if isinstance(value, bool):
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_ID_INVALID")
    text = str(value).strip()
    if _ID_RE.fullmatch(text) is None:
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_ID_INVALID")
    return text


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


def _repository(row: dict[str, Any]) -> str:
    repository = _mapping(
        row.get("repository"),
        "TIMEWEB_PUBLIC_INGRESS_REPOSITORY_INVALID",
    )
    value = repository.get("full_name")
    if not isinstance(value, str):
        _stop("TIMEWEB_PUBLIC_INGRESS_REPOSITORY_INVALID")
    return value


def _normalized_headers(response: Any) -> dict[str, str]:
    try:
        return {
            str(name).casefold(): str(value).strip()
            for name, value in response.headers.items()
        }
    except AttributeError:
        _stop("TIMEWEB_PUBLIC_INGRESS_HEADERS_INVALID")


def _hsts_max_age(value: str) -> int:
    values: list[int] = []
    for item in value.split(";"):
        name, separator, raw = item.strip().partition("=")
        if name.casefold() != "max-age":
            continue
        if not separator or not raw.isascii() or not raw.isdigit():
            return -1
        values.append(int(raw))
    if len(values) != 1:
        return -1
    return values[0]


def _csp_directives(value: str) -> set[str]:
    directives: dict[str, str] = {}
    for item in value.split(";"):
        normalized = " ".join(item.strip().casefold().split())
        if not normalized:
            continue
        name = normalized.partition(" ")[0]
        if name in directives:
            _stop("TIMEWEB_PUBLIC_INGRESS_CSP_INVALID")
        directives[name] = normalized
    return set(directives.values())


def _require_security_headers(headers: dict[str, str], *, api_path: bool) -> None:
    for name in _RETIRED_EDGE_HEADERS:
        if name in headers:
            _stop("TIMEWEB_PUBLIC_INGRESS_RETIRED_EDGE_HEADER")
    for name in ("server", "via"):
        value = headers.get(name, "").casefold()
        if any(marker in value for marker in _RETIRED_EDGE_VALUES):
            _stop("TIMEWEB_PUBLIC_INGRESS_RETIRED_EDGE_HEADER")

    if _hsts_max_age(headers.get("strict-transport-security", "")) < 31_536_000:
        _stop("TIMEWEB_PUBLIC_INGRESS_HSTS_INVALID")
    csp = _csp_directives(headers.get("content-security-policy", ""))
    if not set(_REQUIRED_CSP_DIRECTIVES) <= csp:
        _stop("TIMEWEB_PUBLIC_INGRESS_CSP_INVALID")
    expected = {
        "cross-origin-opener-policy": "same-origin",
        "x-content-type-options": "nosniff",
        "referrer-policy": "same-origin",
    }
    if any(
        headers.get(name, "").casefold() != value
        for name, value in expected.items()
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_SECURITY_HEADER_INVALID")

    vary = {
        item.strip().casefold()
        for item in headers.get("vary", "").split(",")
        if item.strip()
    }
    if not {"origin", "sec-fetch-site"} <= vary:
        _stop("TIMEWEB_PUBLIC_INGRESS_VARY_INVALID")
    cache_control = headers.get("cache-control", "").casefold()
    required_cache = "no-store" if api_path else "no-cache"
    if required_cache not in cache_control:
        _stop("TIMEWEB_PUBLIC_INGRESS_CACHE_POLICY_INVALID")


def _read_public(
    path: str,
    *,
    opener: Any | None = None,
) -> tuple[dict[str, str], bytes]:
    if path not in {"/", "/livez", "/healthz"}:
        _stop("TIMEWEB_PUBLIC_INGRESS_PROBE_PATH_INVALID")
    request = Request(
        CANONICAL_ORIGIN + path,
        headers={
            "Accept": _JSON_CONTENT_TYPE if path != "/" else _HTML_CONTENT_TYPE,
            "User-Agent": "omni-cio-v10-timeweb-public-ingress",
        },
        method="GET",
    )
    active = opener or _NO_REDIRECT_OPENER
    try:
        with active.open(request, timeout=30.0) as response:
            status = int(response.status)
            headers = _normalized_headers(response)
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        _stop(f"TIMEWEB_PUBLIC_INGRESS_HTTP_ERROR:{int(exc.code)}")
    except OSError:
        _stop("TIMEWEB_PUBLIC_INGRESS_TRANSPORT_FAILED")
    if status != 200:
        _stop(f"TIMEWEB_PUBLIC_INGRESS_HTTP_STATUS:{status}")
    if len(raw) > MAX_RESPONSE_BYTES:
        _stop("TIMEWEB_PUBLIC_INGRESS_RESPONSE_TOO_LARGE")
    _require_security_headers(headers, api_path=path != "/")
    return headers, raw


def _json_payload(raw: bytes, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _stop(code)
    return _mapping(payload, code)


def _probe_public_runtime(expected_sha: str, *, opener: Any | None = None) -> None:
    live_headers, live_raw = _read_public("/livez", opener=opener)
    if not live_headers.get("content-type", "").casefold().startswith(
        _JSON_CONTENT_TYPE
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_LIVEZ_CONTENT_TYPE_INVALID")
    live = _json_payload(live_raw, "TIMEWEB_PUBLIC_INGRESS_LIVEZ_INVALID")
    if live.get("status") != "ok":
        _stop("TIMEWEB_PUBLIC_INGRESS_LIVEZ_INVALID")
    if (
        _sha(
            str(live.get("release_sha", "")),
            "TIMEWEB_PUBLIC_INGRESS_SHA_INVALID",
        )
        != expected_sha
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_RELEASE_SHA_DRIFT")

    health_headers, health_raw = _read_public("/healthz", opener=opener)
    if not health_headers.get("content-type", "").casefold().startswith(
        _JSON_CONTENT_TYPE
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_HEALTHZ_CONTENT_TYPE_INVALID")
    health = _json_payload(health_raw, "TIMEWEB_PUBLIC_INGRESS_HEALTHZ_INVALID")
    if (
        health.get("status") != "ok"
        or health.get("database") != "READY"
        or health.get("synthetic_preview") is not False
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_HEALTHZ_INVALID")
    if (
        _sha(
            str(health.get("release_sha", "")),
            "TIMEWEB_PUBLIC_INGRESS_SHA_INVALID",
        )
        != expected_sha
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_RELEASE_SHA_DRIFT")

    root_headers, root_raw = _read_public("/", opener=opener)
    if not root_headers.get("content-type", "").casefold().startswith(
        _HTML_CONTENT_TYPE
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_ROOT_CONTENT_TYPE_INVALID")
    lowered = root_raw[:65_536].lower()
    if b"<html" not in lowered and b"<!doctype html" not in lowered:
        _stop("TIMEWEB_PUBLIC_INGRESS_ROOT_INVALID")


def _canonical_app(api: ReadOnlyAppApiLike) -> tuple[str, dict[str, Any]]:
    matches = [
        row
        for row in _rows(
            api.list_apps(),
            "apps",
            "TIMEWEB_PUBLIC_INGRESS_APPS_INVALID",
        )
        if row.get("name") == app_release.CANONICAL_APP_NAME
        and _repository(row) == app_release.CANONICAL_REPOSITORY
    ]
    if len(matches) != 1:
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_NOT_UNIQUE")
    app_id = _safe_id(matches[0].get("id"))
    payload = _mapping(
        api.get_app(app_id).get("app"),
        "TIMEWEB_PUBLIC_INGRESS_APP_INVALID",
    )
    if _safe_id(payload.get("id")) != app_id:
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_ID_DRIFT")
    expected_shape = {
        "name": app_release.CANONICAL_APP_NAME,
        "type": "backend",
        "framework": app_release.CANONICAL_FRAMEWORK,
        "branch_name": app_release.CANONICAL_BRANCH,
    }
    if any(payload.get(key) != value for key, value in expected_shape.items()):
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_SHAPE_DRIFT")
    if _repository(payload) != app_release.CANONICAL_REPOSITORY:
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_SHAPE_DRIFT")
    if payload.get("is_auto_deploy") is not False:
        _stop("TIMEWEB_PUBLIC_INGRESS_AUTODEPLOY_FORBIDDEN")
    if payload.get("status") != "active":
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_NOT_ACTIVE")
    return app_id, payload


def _validate_domains(app: dict[str, Any]) -> None:
    rows = app.get("domains")
    if not isinstance(rows, list):
        _stop("TIMEWEB_PUBLIC_INGRESS_DOMAINS_INVALID")
    names: set[str] = set()
    for row in rows:
        value = _mapping(row, "TIMEWEB_PUBLIC_INGRESS_DOMAINS_INVALID").get("fqdn")
        if not isinstance(value, str):
            _stop("TIMEWEB_PUBLIC_INGRESS_DOMAINS_INVALID")
        names.add(value.strip().lower().rstrip("."))
    if CANONICAL_HOSTNAME not in names:
        _stop("TIMEWEB_PUBLIC_INGRESS_CANONICAL_DOMAIN_MISSING")
    if _RETIRED_DOMAIN in names:
        _stop("TIMEWEB_PUBLIC_INGRESS_RETIRED_DOMAIN_ATTACHED")


def _validate_runtime_env(app: dict[str, Any], expected_sha: str) -> None:
    envs = _mapping(app.get("envs"), "TIMEWEB_PUBLIC_INGRESS_ENV_INVALID")
    expected = {
        "OMNI_V10_HOSTED_RUNTIME": "1",
        "OMNI_V10_PUBLIC_HOSTNAME": CANONICAL_HOSTNAME,
        app_release.RELEASE_SHA_ENV: expected_sha,
        app_release.POSTGRES_RUNTIME_ROLE_ENV: "omni_cio_hosted_api",
        app_release.TRUSTED_EDGE_TLS_ENV: "true",
        app_release.PUBLIC_MULTI_USER_ENV: "false",
        app_release.TELEGRAM_LOGIN_ENV: "false",
    }
    if any(str(envs.get(name, "")) != value for name, value in expected.items()):
        _stop("TIMEWEB_PUBLIC_INGRESS_ENV_DRIFT")
    if str(envs.get(app_release.VK_LOGIN_ENV, "")).strip().lower() not in {
        "",
        "0",
        "false",
    }:
        _stop("TIMEWEB_PUBLIC_INGRESS_VK_ACTIVATION_FORBIDDEN")
    dsn = envs.get(app_release.POSTGRES_DSN_ENV)
    if not isinstance(dsn, str) or not dsn.strip():
        _stop("TIMEWEB_PUBLIC_INGRESS_POSTGRES_DSN_REQUIRED")
    retired = ("CLOUDFLARE", "NEON", "RENDER", "CLOUDRU")
    if any(any(marker in str(name).upper() for marker in retired) for name in envs):
        _stop("TIMEWEB_PUBLIC_INGRESS_RETIRED_PROVIDER_ENV_PRESENT")


def _validate_release_history(
    api: ReadOnlyAppApiLike,
    app_id: str,
    expected_sha: str,
    rollback_sha: str,
) -> None:
    successful: set[str] = set()
    for row in _rows(
        api.list_deploys(app_id),
        "deploys",
        "TIMEWEB_PUBLIC_INGRESS_DEPLOYS_INVALID",
    ):
        status = row.get("status")
        commit = row.get("commit_sha")
        if status != "success" or not isinstance(commit, str):
            continue
        successful.add(_sha(commit, "TIMEWEB_PUBLIC_INGRESS_DEPLOY_SHA_INVALID"))
    if expected_sha not in successful:
        _stop("TIMEWEB_PUBLIC_INGRESS_CURRENT_RELEASE_NOT_PROVEN")
    if rollback_sha not in successful:
        _stop("TIMEWEB_PUBLIC_INGRESS_ROLLBACK_RELEASE_NOT_PROVEN")


def _validate_provider_state(
    api: ReadOnlyAppApiLike,
    expected_sha: str,
    rollback_sha: str,
) -> None:
    app_id, app = _canonical_app(api)
    if (
        _sha(
            str(app.get("commit_sha", "")),
            "TIMEWEB_PUBLIC_INGRESS_APP_SHA_INVALID",
        )
        != expected_sha
    ):
        _stop("TIMEWEB_PUBLIC_INGRESS_APP_SHA_DRIFT")
    _validate_domains(app)
    _validate_runtime_env(app, expected_sha)
    _validate_release_history(api, app_id, expected_sha, rollback_sha)


def run(
    *,
    operation: str,
    expected_sha: str,
    observed_main_sha: str,
    confirmation: str = "",
    p3_recovery_evidence_sha256: str = "",
    russian_no_vpn_evidence_sha256: str = "",
    rollback_release_sha: str = "",
    rollback_evidence_sha256: str = "",
    token: str | None = None,
    api: ReadOnlyAppApiLike | None = None,
    opener: Any | None = None,
) -> None:
    expected = _sha(expected_sha, "TIMEWEB_PUBLIC_INGRESS_SHA_INVALID")
    observed = _sha(observed_main_sha, "TIMEWEB_PUBLIC_INGRESS_MAIN_SHA_INVALID")
    if expected != observed:
        _stop("TIMEWEB_PUBLIC_INGRESS_MAIN_SHA_DRIFT")

    evidence_values = (
        p3_recovery_evidence_sha256,
        russian_no_vpn_evidence_sha256,
        rollback_release_sha,
        rollback_evidence_sha256,
    )
    if operation == "observe":
        if confirmation or any(evidence_values):
            _stop("TIMEWEB_PUBLIC_INGRESS_UNEXPECTED_ACCEPTANCE_EVIDENCE")
        _probe_public_runtime(expected, opener=opener)
        print(
            "TIMEWEB_PUBLIC_INGRESS=OBSERVED "
            f"sha={expected} origin={CANONICAL_ORIGIN} public_users=false"
        )
        return

    if operation != "accept":
        _stop("TIMEWEB_PUBLIC_INGRESS_OPERATION_INVALID")
    if confirmation != ACCEPT_CONFIRMATION:
        _stop("TIMEWEB_PUBLIC_INGRESS_CONFIRMATION_REQUIRED")

    p3_digest = _sha256(
        p3_recovery_evidence_sha256,
        "TIMEWEB_PUBLIC_INGRESS_P3_RECOVERY_EVIDENCE_INVALID",
    )
    russia_digest = _sha256(
        russian_no_vpn_evidence_sha256,
        "TIMEWEB_PUBLIC_INGRESS_RUSSIA_EVIDENCE_INVALID",
    )
    rollback_digest = _sha256(
        rollback_evidence_sha256,
        "TIMEWEB_PUBLIC_INGRESS_ROLLBACK_EVIDENCE_INVALID",
    )
    rollback = _sha(
        rollback_release_sha,
        "TIMEWEB_PUBLIC_INGRESS_ROLLBACK_SHA_INVALID",
    )
    if rollback == expected:
        _stop("TIMEWEB_PUBLIC_INGRESS_ROLLBACK_SHA_COLLISION")

    _probe_public_runtime(expected, opener=opener)
    active_api = api
    if active_api is None:
        active_token = (token or os.environ.get(app_release.TOKEN_ENV, "")).strip()
        if not active_token:
            _stop("TIMEWEB_CLOUD_API_TOKEN_REQUIRED")
        active_api = TimewebIngressReadApi(active_token)
    _validate_provider_state(active_api, expected, rollback)

    print(
        "TIMEWEB_PUBLIC_INGRESS=ACCEPTED "
        f"sha={expected} origin={CANONICAL_ORIGIN} "
        f"p3_recovery_evidence_sha256={p3_digest} "
        f"russian_no_vpn_evidence_sha256={russia_digest} "
        f"rollback_release_sha={rollback} "
        f"rollback_evidence_sha256={rollback_digest} public_users=false"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("observe", "accept"), required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--observed-main-sha", required=True)
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--p3-recovery-evidence-sha256", default="")
    parser.add_argument("--russian-no-vpn-evidence-sha256", default="")
    parser.add_argument("--rollback-release-sha", default="")
    parser.add_argument("--rollback-evidence-sha256", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        run(
            operation=args.operation,
            expected_sha=args.expected_sha,
            observed_main_sha=args.observed_main_sha,
            confirmation=args.confirmation,
            p3_recovery_evidence_sha256=args.p3_recovery_evidence_sha256,
            russian_no_vpn_evidence_sha256=args.russian_no_vpn_evidence_sha256,
            rollback_release_sha=args.rollback_release_sha,
            rollback_evidence_sha256=args.rollback_evidence_sha256,
        )
    except PublicIngressStopped as exc:
        print(f"TIMEWEB_PUBLIC_INGRESS=STOPPED code={exc}", file=sys.stderr)
        return 1
    except app_release.ReleaseStopped as exc:
        print(f"TIMEWEB_PUBLIC_INGRESS=STOPPED code={exc.code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
