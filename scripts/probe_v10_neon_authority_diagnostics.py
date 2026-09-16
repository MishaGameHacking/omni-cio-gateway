from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import http.client
import os
import ssl
import sys
from typing import Any, Protocol, TextIO
from urllib.parse import quote, urlencode

from scripts import provision_v10_cloudflare_neon_runtime as _runtime
from scripts import provision_v10_render_neon_preview as _base
from scripts import provision_v10_render_neon_preview_org_scope as _org


_HTTP_GET = "GET"
_STATUS_OK = "200"
_STATUS_UNAUTHORIZED = "401"
_STATUS_FORBIDDEN = "403"
_STATUS_NOT_FOUND = "404"
_STATUS_ERROR = "ERROR"
_STATUS_UNAVAILABLE = "UNAVAILABLE"
_STATUS_SKIPPED = "SKIPPED"
_STATUS_INVALID_PAYLOAD = "INVALID_PAYLOAD"
_DENIED_STATUSES = frozenset({_STATUS_FORBIDDEN, _STATUS_NOT_FOUND})
_UNKNOWN = "UNKNOWN"
_TRUE = "TRUE"
_FALSE = "FALSE"
_CANONICAL_LOOKUP_LIMIT = 10
_AUTH_PATH = "/auth"
_CURRENT_USER_ORGANIZATIONS_PATH = "/users/me/organizations"
_QUERY_SCOPE_ORGANIZATION = "ORGANIZATION_SCOPED"
_QUERY_SCOPE_PROJECT = "PROJECT_SCOPED"
_QUERY_SCOPE_SKIPPED = "SKIPPED"
_AUTH_METHODS = frozenset(
    {
        "keycloak",
        "session_cookie",
        "api_key_user",
        "api_key_org",
        "oauth",
    }
)
_NEON_API_HOST = "console.neon.tech"
_NEON_API_PREFIX = "/api/v2"
_DIRECT_TIMEOUT_SECONDS = 20.0
_DIRECT_USER_AGENT = "omni-cio-v10-neon-authority-diagnostic/1"
_CREDENTIAL_FORMAT_MODERN = "MODERN_NAPI"
_CREDENTIAL_FORMAT_LEGACY_OR_UNKNOWN = "LEGACY_OR_UNKNOWN"
_CREDENTIAL_FORMAT_WRAPPED_OR_ASSIGNED = "WRAPPED_OR_ASSIGNED"
_RESPONSE_MEDIA_JSON = "JSON"
_RESPONSE_MEDIA_HTML = "HTML"
_RESPONSE_MEDIA_TEXT = "TEXT"
_RESPONSE_MEDIA_OTHER = "OTHER"
_RESPONSE_MEDIA_MISSING = "MISSING"
_TRANSPORT_MATCH = "MATCH"
_TRANSPORT_DIVERGENT = "DIVERGENT"
_TRANSPORT_DIRECT_UNAVAILABLE = "DIRECT_UNAVAILABLE"


class _NeonReadApi(Protocol):
    def request(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        expected: frozenset[int] = frozenset({200}),
        timeout: float = 30.0,
    ) -> Any: ...


ApiFactory = Callable[[str, str], _NeonReadApi]


@dataclass(frozen=True, slots=True)
class _ReadEvidence:
    status: str
    payload: object | None = None


@dataclass(frozen=True, slots=True)
class _DirectTransportEvidence:
    status: str
    response_media: str


DirectProbe = Callable[[str, str], _DirectTransportEvidence]


@dataclass(frozen=True, slots=True)
class NeonAuthorityDiagnostic:
    auth_status: str
    auth_method: str
    credential_orgs_status: str
    configured_org_match: str
    organization_status: str
    project_status: str
    branches_status: str
    canonical_query_scope: str
    canonical_query_status: str
    canonical_name_matches: str
    configured_id_match: str
    classification: str

    def marker(self) -> str:
        return " ".join(
            (
                "CLOUDFLARE_NEON_AUTHORITY_DIAGNOSTIC",
                f"auth_status={self.auth_status}",
                f"auth_method={self.auth_method}",
                f"credential_orgs_status={self.credential_orgs_status}",
                f"configured_org_match={self.configured_org_match}",
                f"organization_status={self.organization_status}",
                f"exact_project_status={self.project_status}",
                f"exact_branches_status={self.branches_status}",
                f"canonical_query_scope={self.canonical_query_scope}",
                f"canonical_query_status={self.canonical_query_status}",
                f"canonical_name_matches={self.canonical_name_matches}",
                f"configured_id_match={self.configured_id_match}",
                f"classification={self.classification}",
            )
        )


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise _base.ProvisioningStopped(f"{name}_REQUIRED")
    return value


def _status(exc: _base.ProvisioningStopped) -> str:
    return _STATUS_ERROR if exc.status is None else str(exc.status)


def _read(api: _NeonReadApi, path: str) -> _ReadEvidence:
    try:
        payload = api.request(_HTTP_GET, path)
    except _base.ProvisioningStopped as exc:
        return _ReadEvidence(_status(exc))
    return _ReadEvidence(_STATUS_OK, payload)


def _auth_method(payload: object) -> str:
    if not isinstance(payload, dict):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_AUTH_RESPONSE_INVALID")
    value = payload.get("auth_method")
    if not isinstance(value, str) or value not in _AUTH_METHODS:
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_AUTH_METHOD_INVALID")
    return value


def _credential_auth(api: _NeonReadApi) -> tuple[str, str]:
    evidence = _read(api, _AUTH_PATH)
    if evidence.status != _STATUS_OK:
        return evidence.status, _UNKNOWN
    try:
        method = _auth_method(evidence.payload)
    except _base.ProvisioningStopped:
        return _STATUS_INVALID_PAYLOAD, _UNKNOWN
    return evidence.status, method


def _configured_org_match(payload: object, expected_org_id: str) -> str:
    if not isinstance(payload, dict):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_ORGS_RESPONSE_INVALID")
    raw_organizations = payload.get("organizations")
    if not isinstance(raw_organizations, list):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_ORGS_INVALID")
    configured_org_present = False
    for item in raw_organizations:
        if not isinstance(item, dict):
            raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_ORG_INVALID")
        organization_id = item.get("id")
        if not isinstance(organization_id, str):
            raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_ORG_ID_INVALID")
        _org._validate_neon_org_id(organization_id)
        configured_org_present = configured_org_present or (
            organization_id == expected_org_id
        )
    return _TRUE if configured_org_present else _FALSE


def _credential_organizations(
    api: _NeonReadApi,
    expected_org_id: str,
) -> tuple[str, str]:
    evidence = _read(api, _CURRENT_USER_ORGANIZATIONS_PATH)
    if evidence.status != _STATUS_OK:
        return evidence.status, _UNKNOWN
    try:
        configured_org_match = _configured_org_match(
            evidence.payload,
            expected_org_id,
        )
    except _base.ProvisioningStopped:
        return _STATUS_INVALID_PAYLOAD, _UNKNOWN
    return evidence.status, configured_org_match


def _canonical_query_path(organization_id: str | None) -> str:
    parameters = {
        "limit": str(_CANONICAL_LOOKUP_LIMIT),
        "search": _base.NEON_PROJECT_NAME,
    }
    if organization_id is not None:
        parameters["org_id"] = organization_id
    return f"/projects?{urlencode(parameters)}"


def _canonical_project_match(
    payload: object,
    expected_project_id: str,
) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_PROJECTS_RESPONSE_INVALID")
    raw_projects = payload.get("projects")
    if not isinstance(raw_projects, list):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_PROJECTS_INVALID")
    if not all(isinstance(item, dict) for item in raw_projects):
        raise _base.ProvisioningStopped("NEON_DIAGNOSTIC_PROJECT_INVALID")
    matches = [
        item for item in raw_projects if item.get("name") == _base.NEON_PROJECT_NAME
    ]
    if not matches:
        count = "0"
    elif len(matches) == 1:
        count = "1"
    else:
        count = "MULTIPLE"
    configured_id_match = (
        _TRUE
        if any(item.get("id") == expected_project_id for item in matches)
        else _FALSE
    )
    return count, configured_id_match


def _canonical_lookup_scope(
    *,
    credential_orgs_status: str,
    organization_status: str,
) -> tuple[str, str | None]:
    if organization_status == _STATUS_OK:
        return _QUERY_SCOPE_ORGANIZATION, "ORGANIZATION"
    if (
        credential_orgs_status in _DENIED_STATUSES
        and organization_status in _DENIED_STATUSES
    ):
        return _QUERY_SCOPE_PROJECT, None
    return _QUERY_SCOPE_SKIPPED, None


def _canonical_lookup(
    api: _NeonReadApi,
    organization_id: str,
    project_id: str,
    *,
    credential_orgs_status: str,
    organization_status: str,
) -> tuple[str, str, str, str]:
    query_scope, organization_mode = _canonical_lookup_scope(
        credential_orgs_status=credential_orgs_status,
        organization_status=organization_status,
    )
    if query_scope == _QUERY_SCOPE_SKIPPED:
        return query_scope, _STATUS_SKIPPED, _UNKNOWN, _UNKNOWN
    query_org_id = organization_id if organization_mode == "ORGANIZATION" else None
    evidence = _read(api, _canonical_query_path(query_org_id))
    if evidence.status != _STATUS_OK:
        return query_scope, evidence.status, _UNKNOWN, _UNKNOWN
    try:
        matches, configured_id_match = _canonical_project_match(
            evidence.payload,
            project_id,
        )
    except _base.ProvisioningStopped:
        return query_scope, _STATUS_INVALID_PAYLOAD, _UNKNOWN, _UNKNOWN
    return query_scope, evidence.status, matches, configured_id_match


def _exact_resource_denied(project_status: str, branches_status: str) -> bool:
    return project_status in _DENIED_STATUSES or branches_status in _DENIED_STATUSES


def _canonical_classification(
    *,
    canonical_query_scope: str,
    canonical_query_status: str,
    canonical_name_matches: str,
    configured_id_match: str,
    project_status: str,
    branches_status: str,
) -> str | None:
    if canonical_query_status != _STATUS_OK:
        return None
    if canonical_name_matches == "0":
        if canonical_query_scope == _QUERY_SCOPE_PROJECT:
            return "CANONICAL_PROJECT_NOT_VISIBLE_TO_CREDENTIAL"
        return "CANONICAL_PROJECT_NOT_FOUND_IN_CONFIGURED_ORG"
    if canonical_name_matches == "MULTIPLE":
        if canonical_query_scope == _QUERY_SCOPE_PROJECT:
            return "CANONICAL_PROJECT_NAME_NOT_UNIQUE_FOR_CREDENTIAL"
        return "CANONICAL_PROJECT_NAME_NOT_UNIQUE"
    if canonical_name_matches == "1" and configured_id_match == _FALSE:
        return "CONFIGURED_PROJECT_ID_DRIFT"
    if configured_id_match == _TRUE and _exact_resource_denied(
        project_status,
        branches_status,
    ):
        return "EXACT_PROJECT_AUTHORIZATION_DRIFT"
    return None


def _classification(
    *,
    auth_status: str,
    credential_orgs_status: str,
    configured_org_match: str,
    organization_status: str,
    project_status: str,
    branches_status: str,
    canonical_query_scope: str,
    canonical_query_status: str,
    canonical_name_matches: str,
    configured_id_match: str,
) -> str:
    if _STATUS_UNAUTHORIZED in {
        auth_status,
        credential_orgs_status,
        organization_status,
        project_status,
        branches_status,
    }:
        return "CREDENTIAL_INVALID"
    if credential_orgs_status == _STATUS_OK and configured_org_match == _FALSE:
        return "CONFIGURED_ORG_ID_DRIFT"
    canonical_classification = _canonical_classification(
        canonical_query_scope=canonical_query_scope,
        canonical_query_status=canonical_query_status,
        canonical_name_matches=canonical_name_matches,
        configured_id_match=configured_id_match,
        project_status=project_status,
        branches_status=branches_status,
    )
    if canonical_classification is not None:
        return canonical_classification
    if (
        canonical_query_scope == _QUERY_SCOPE_PROJECT
        and canonical_query_status in _DENIED_STATUSES
        and _exact_resource_denied(project_status, branches_status)
    ):
        return "CREDENTIAL_PROJECT_READ_FORBIDDEN"
    if (
        credential_orgs_status == _STATUS_OK
        and configured_org_match == _TRUE
        and organization_status in _DENIED_STATUSES
        and canonical_query_status == _STATUS_SKIPPED
        and _exact_resource_denied(project_status, branches_status)
    ):
        return "CONFIGURED_ORG_MATCH_EXACT_PROJECT_FORBIDDEN"
    if branches_status == _STATUS_OK:
        return "EXACT_PROJECT_BRANCH_READABLE"
    return "UNRESOLVED"


def diagnose_neon_authority(
    api: _NeonReadApi,
    organization_id: str,
    project_id: str,
) -> NeonAuthorityDiagnostic:
    safe_org_id = _org._validate_neon_org_id(organization_id)
    safe_project_id = _runtime._validate_neon_project_id(project_id)
    auth_status, auth_method = _credential_auth(api)
    credential_orgs_status, configured_org_match = _credential_organizations(
        api,
        safe_org_id,
    )
    organization = _read(api, f"/organizations/{safe_org_id}")
    project = _read(api, f"/projects/{safe_project_id}")
    branches = _read(api, f"/projects/{safe_project_id}/branches?limit=1")
    (
        canonical_query_scope,
        canonical_query_status,
        canonical_name_matches,
        configured_id_match,
    ) = _canonical_lookup(
        api,
        safe_org_id,
        safe_project_id,
        credential_orgs_status=credential_orgs_status,
        organization_status=organization.status,
    )
    classification = _classification(
        auth_status=auth_status,
        credential_orgs_status=credential_orgs_status,
        configured_org_match=configured_org_match,
        organization_status=organization.status,
        project_status=project.status,
        branches_status=branches.status,
        canonical_query_scope=canonical_query_scope,
        canonical_query_status=canonical_query_status,
        canonical_name_matches=canonical_name_matches,
        configured_id_match=configured_id_match,
    )
    return NeonAuthorityDiagnostic(
        auth_status=auth_status,
        auth_method=auth_method,
        credential_orgs_status=credential_orgs_status,
        configured_org_match=configured_org_match,
        organization_status=organization.status,
        project_status=project.status,
        branches_status=branches.status,
        canonical_query_scope=canonical_query_scope,
        canonical_query_status=canonical_query_status,
        canonical_name_matches=canonical_name_matches,
        configured_id_match=configured_id_match,
        classification=classification,
    )


def _credential_format(token: str) -> str:
    lowered = token.casefold()
    if (
        any(character.isspace() for character in token)
        or token[:1] in {"'", '"'}
        or token[-1:] in {"'", '"'}
        or lowered.startswith("neon_api_key=")
        or lowered.startswith("export neon_api_key=")
    ):
        return _CREDENTIAL_FORMAT_WRAPPED_OR_ASSIGNED
    if token.startswith("napi_"):
        return _CREDENTIAL_FORMAT_MODERN
    return _CREDENTIAL_FORMAT_LEGACY_OR_UNKNOWN


def _response_media_family(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        return _RESPONSE_MEDIA_MISSING
    media_type = value.split(";", 1)[0].strip().casefold()
    if media_type == "application/json" or media_type.endswith("+json"):
        return _RESPONSE_MEDIA_JSON
    if media_type == "text/html":
        return _RESPONSE_MEDIA_HTML
    if media_type == "text/plain":
        return _RESPONSE_MEDIA_TEXT
    return _RESPONSE_MEDIA_OTHER


def _direct_tls_context() -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_default_certs(ssl.Purpose.SERVER_AUTH)
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise OSError("direct Neon diagnostic TLS verification unavailable")
    return context


def _direct_exact_project_probe(
    token: str,
    project_id: str,
) -> _DirectTransportEvidence:
    safe_project_id = _runtime._validate_neon_project_id(project_id)
    path = f"{_NEON_API_PREFIX}/projects/{quote(safe_project_id, safe='')}"
    connection: http.client.HTTPSConnection | None = None
    try:
        connection = http.client.HTTPSConnection(
            _NEON_API_HOST,
            443,
            timeout=_DIRECT_TIMEOUT_SECONDS,
            context=_direct_tls_context(),
        )
        connection.request(
            _HTTP_GET,
            path,
            body=None,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": _DIRECT_USER_AGENT,
            },
        )
        response = connection.getresponse()
        return _DirectTransportEvidence(
            status=str(int(response.status)),
            response_media=_response_media_family(response.getheader("Content-Type")),
        )
    except (OSError, http.client.HTTPException):
        return _DirectTransportEvidence(
            status=_STATUS_UNAVAILABLE,
            response_media=_RESPONSE_MEDIA_MISSING,
        )
    finally:
        if connection is not None:
            connection.close()


def _transport_relation(primary_status: str, direct_status: str) -> str:
    if direct_status == _STATUS_UNAVAILABLE:
        return _TRANSPORT_DIRECT_UNAVAILABLE
    if direct_status == primary_status:
        return _TRANSPORT_MATCH
    return _TRANSPORT_DIVERGENT


def _credential_transport_marker(
    token: str,
    project_id: str,
    primary_project_status: str,
    *,
    direct_probe: DirectProbe,
) -> str:
    evidence = direct_probe(token, project_id)
    return " ".join(
        (
            "CLOUDFLARE_NEON_CREDENTIAL_DIAGNOSTIC",
            f"credential_format={_credential_format(token)}",
            f"primary_exact_project_status={primary_project_status}",
            f"direct_exact_project_status={evidence.status}",
            f"direct_response_media={evidence.response_media}",
            "transport_equivalence="
            f"{_transport_relation(primary_project_status, evidence.status)}",
        )
    )


def _default_api_factory(token: str, organization_id: str) -> _NeonReadApi:
    return _org.OrgScopedNeonApi(token, organization_id)


def _blocked_report(exc: _base.ProvisioningStopped) -> str:
    fields = [
        "CLOUDFLARE_NEON_AUTHORITY_DIAGNOSTIC=BLOCKED",
        f"code={exc.code}",
    ]
    if exc.status is not None:
        fields.append(f"status={exc.status}")
    return " ".join(fields)


def probe_neon_authority_diagnostics(
    environ: Mapping[str, str] | None = None,
    *,
    api_factory: ApiFactory = _default_api_factory,
    output: TextIO | None = None,
    enable_direct_transport_probe: bool = False,
    direct_probe: DirectProbe = _direct_exact_project_probe,
) -> int:
    environment = os.environ if environ is None else environ
    destination = sys.stdout if output is None else output
    try:
        token = _required(environment, "NEON_API_KEY")
        _base._mask(token)
        organization_id = _org._validate_neon_org_id(
            _required(environment, "NEON_ORG_ID")
        )
        project_id = _runtime._validate_neon_project_id(
            _required(environment, "NEON_PROJECT_ID")
        )
        diagnostic = diagnose_neon_authority(
            api_factory(token, organization_id),
            organization_id,
            project_id,
        )
    except _base.ProvisioningStopped as exc:
        print(_blocked_report(exc), file=destination)
        return 78
    print(diagnostic.marker(), file=destination)
    if enable_direct_transport_probe:
        print(
            _credential_transport_marker(
                token,
                project_id,
                diagnostic.project_status,
                direct_probe=direct_probe,
            ),
            file=destination,
        )
    return 0


def main() -> int:
    return probe_neon_authority_diagnostics(enable_direct_transport_probe=True)


if __name__ == "__main__":
    raise SystemExit(main())
