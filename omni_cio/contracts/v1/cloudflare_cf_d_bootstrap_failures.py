from __future__ import annotations

import json
from types import MappingProxyType
from typing import Final


NEON_FUNCTION_FAILURE_PREFIX: Final = "CLOUDFLARE_CF_D_NEON_FUNCTION_"
NEON_BOOTSTRAP_REJECTED: Final = "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_REJECTED"
GENERIC_STAGING_BOOTSTRAP_FAILURE: Final = "CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED"
STAGING_BOOTSTRAP_UNAVAILABLE: Final = "CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_UNAVAILABLE"
STAGING_BOOTSTRAP_REDIRECT_REJECTED: Final = (
    "CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_REDIRECT_REJECTED"
)

NEON_FUNCTION_FAILURE_STATUS_BY_CODE: Final = MappingProxyType(
    {
        "METHOD_NOT_ALLOWED": 405,
        "OIDC_REQUIRED": 401,
        "REQUEST_TOO_LARGE": 400,
        "REQUEST_INVALID": 400,
        "EXPECTED_SHA_INVALID": 400,
        "OIDC_SEGMENT_INVALID": 403,
        "OIDC_TIME_CLAIMS_INVALID": 403,
        "OIDC_EXPIRED": 403,
        "OIDC_NOT_YET_VALID": 403,
        "OIDC_ISSUED_AT_INVALID": 403,
        "OIDC_ISSUER_INVALID": 403,
        "OIDC_AUDIENCE_INVALID": 403,
        "OIDC_REPOSITORY_INVALID": 403,
        "OIDC_OWNER_INVALID": 403,
        "OIDC_REPOSITORY_VISIBILITY_INVALID": 403,
        "OIDC_REF_INVALID": 403,
        "OIDC_WORKFLOW_INVALID": 403,
        "OIDC_WORKFLOW_REF_INVALID": 403,
        "OIDC_WORKFLOW_SHA_INVALID": 403,
        "OIDC_SOURCE_SHA_INVALID": 403,
        "OIDC_EVENT_INVALID": 403,
        "OIDC_RUNNER_INVALID": 403,
        "OIDC_RUN_ID_INVALID": 403,
        "OIDC_RUN_ATTEMPT_INVALID": 403,
        "OIDC_JTI_INVALID": 403,
        "OIDC_JWKS_UNAVAILABLE": 403,
        "OIDC_JWKS_INVALID": 403,
        "OIDC_SIGNING_KEY_INVALID": 403,
        "OIDC_TOKEN_INVALID": 403,
        "OIDC_HEADER_INVALID": 403,
        "OIDC_CLAIMS_INVALID": 403,
        "OIDC_SIGNATURE_INVALID": 403,
        "DATABASE_URL_REQUIRED": 502,
        "DATABASE_URL_INVALID": 502,
        "DATABASE_REGION_INVALID": 502,
        "DATABASE_OWNER_CREDENTIAL_INVALID": 502,
        "DATABASE_QUERY_FAILED": 502,
        "DATABASE_QUERY_RESPONSE_INVALID": 502,
        "DATABASE_TRANSACTION_FAILED": 502,
        "DATABASE_TRANSACTION_RESPONSE_INVALID": 502,
        "NEON_POSTGRES18_REQUIRED": 502,
        "RUNTIME_PROBE_INVALID": 502,
        "RUNTIME_PROBE_FAILED": 502,
        "BOOTSTRAP_FAILED": 502,
    }
)
NEON_FUNCTION_FAILURE_CODES: Final = frozenset(NEON_FUNCTION_FAILURE_STATUS_BY_CODE)

WORKER_FAILURE_STATUS_BY_CODE: Final = MappingProxyType(
    {
        "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED": 403,
        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_UNAVAILABLE": 502,
    }
)
WORKER_FAILURE_CODES: Final = frozenset(WORKER_FAILURE_STATUS_BY_CODE)

STAGING_ROUTE_FAILURE_STATUS_BY_CODE: Final = MappingProxyType(
    {
        "CLOUDFLARE_CF_D_EXPECTED_SHA_INVALID": 403,
        "CLOUDFLARE_CF_D_OIDC_REQUIRED": 401,
        "CLOUDFLARE_CF_D_STAGING_PROVIDER_CONTEXT_UNAVAILABLE": 502,
        "CLOUDFLARE_CF_D_EGRESS_TLS_UNAVAILABLE": 502,
        "CLOUDFLARE_CF_D_EGRESS_REQUEST_REJECTED": 502,
        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_UNAVAILABLE": 502,
        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_TOO_LARGE": 502,
        "CLOUDFLARE_CF_D_NEON_BOOTSTRAP_RESPONSE_INVALID": 502,
        NEON_BOOTSTRAP_REJECTED: 502,
        **{
            f"{NEON_FUNCTION_FAILURE_PREFIX}{code}": 502
            for code in NEON_FUNCTION_FAILURE_CODES
        },
    }
)
STAGING_BOOTSTRAP_FAILURE_CODES: Final = frozenset(
    {
        *STAGING_ROUTE_FAILURE_STATUS_BY_CODE,
        GENERIC_STAGING_BOOTSTRAP_FAILURE,
        STAGING_BOOTSTRAP_UNAVAILABLE,
        STAGING_BOOTSTRAP_REDIRECT_REJECTED,
    }
)


def _json_object(content: bytes) -> dict[str, object] | None:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def classify_neon_bootstrap_provider_failure(status_code: int, content: bytes) -> str:
    payload = _json_object(content)
    if payload is None:
        return NEON_BOOTSTRAP_REJECTED

    detail = payload.get("detail")
    if isinstance(detail, str) and WORKER_FAILURE_STATUS_BY_CODE.get(detail) == status_code:
        return detail

    provider_status = payload.get("status")
    provider_code = payload.get("code")
    if (
        provider_status == "BLOCKED"
        and isinstance(provider_code, str)
        and NEON_FUNCTION_FAILURE_STATUS_BY_CODE.get(provider_code) == status_code
    ):
        return f"{NEON_FUNCTION_FAILURE_PREFIX}{provider_code}"
    return NEON_BOOTSTRAP_REJECTED


def classify_staging_bootstrap_failure(status_code: int, content: bytes) -> str:
    payload = _json_object(content)
    if payload is None:
        return GENERIC_STAGING_BOOTSTRAP_FAILURE
    detail = payload.get("detail")
    if (
        isinstance(detail, str)
        and STAGING_ROUTE_FAILURE_STATUS_BY_CODE.get(detail) == status_code
    ):
        return detail
    return GENERIC_STAGING_BOOTSTRAP_FAILURE
