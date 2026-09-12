from __future__ import annotations

from contextlib import contextmanager
import hmac
import os
from typing import Iterator

import scripts.bootstrap_v10_cloudflare_builds as builds


_INVOKE_API_TOKEN_ENV = "NEON_FUNCTION_INVOKE_API_TOKEN"
_MANAGEMENT_API_TOKEN_ENV = "NEON_FUNCTION_DEPLOY_API_KEY"
_FAILURE_PREFIX = "CLOUDFLARE_CF_D_NEON_FUNCTION_INVOKE_CREDENTIAL_"
_MIN_TOKEN_LENGTH = 16
_MAX_TOKEN_LENGTH = 4096


def _valid_secret(value: object) -> bool:
    return (
        isinstance(value, str)
        and _MIN_TOKEN_LENGTH <= len(value) <= _MAX_TOKEN_LENGTH
        and value.isascii()
        and value == value.strip()
        and not any(character.isspace() for character in value)
    )


def function_invocation_token_from_env() -> str:
    """Load the pre-provisioned branch-scoped Function invocation secret.

    The credential is created out of band with exactly ``functions:invoke`` and kept in
    GitHub Actions secret custody. Release code never lists, creates, rotates, or revokes
    Neon branch credentials. The authenticated provenance/bootstrap request itself is the
    fail-closed proof that the supplied token can invoke the exact custodied Function.
    """

    value = os.environ.get(_INVOKE_API_TOKEN_ENV, "")
    if not value:
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TOKEN_REQUIRED")
    if not _valid_secret(value):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TOKEN_INVALID")
    management = os.environ.get(_MANAGEMENT_API_TOKEN_ENV, "")
    if management and management.isascii() and hmac.compare_digest(value, management):
        raise builds.BootstrapStopped(f"{_FAILURE_PREFIX}TOKEN_ROLE_COLLISION")
    builds._mask(value)
    return value


def project_invocation_authority_from_env() -> tuple[str, str]:
    """Compatibility shim for callers predating separated invocation custody.

    Invocation authority is no longer derived from Neon management authority. Returning
    inert placeholders preserves the bounded call shape while preventing exact-source
    reuse and direct production bootstrap from loading a project-management secret.
    """

    return "", ""


@contextmanager
def function_invocation_credential(
    project_token: str,
    project_id: str,
    branch_id: str,
) -> Iterator[str]:
    """Yield the pre-provisioned invocation-only secret without provider mutation.

    The legacy arguments are deliberately ignored. Real Function source convergence
    still obtains and validates its project-scoped management authority in the deployer;
    this helper owns only the separate outer Function-ingress credential.
    """

    del project_token, project_id, branch_id
    yield function_invocation_token_from_env()
