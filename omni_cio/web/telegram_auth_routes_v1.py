from __future__ import annotations

from datetime import timezone
from urllib.parse import quote

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.product_identity_v1 import ProductIdentityError
from omni_cio.web.provider_auth_v1 import (
    ProviderAuthenticationRuntimeLike,
    ProviderAuthorizationError,
    ProviderAuthorizationStartV1,
    new_authorization_browser_proof_v1,
)
from omni_cio.web.session_v1 import new_session_token_v1
from omni_cio.web.telegram_auth_services_v1 import (
    TelegramAuthRouteServicesV1,
    TelegramProductAuthenticationLike,
)
from omni_cio.web.telegram_oidc_v1 import TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT


TELEGRAM_START_PATH = "/api/v10/web/auth/telegram/start"
TELEGRAM_CALLBACK_PATH = "/api/v10/web/auth/telegram/callback"
_PROOF_COOKIE_MAX_AGE_SECONDS = 15 * 60


def _utc_now(services: TelegramAuthRouteServicesV1):
    value = services.now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("TELEGRAM_AUTH_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _bounded_query(
    request: Request,
    name: str,
    *,
    maximum: int,
    required: bool = True,
) -> str | None:
    values = request.query_params.getlist(name)
    if not values:
        if required:
            raise ValueError("TELEGRAM_CALLBACK_INVALID")
        return None
    if len(values) != 1:
        raise ValueError("TELEGRAM_CALLBACK_INVALID")
    value = values[0]
    if not value or len(value) > maximum or not value.isascii():
        raise ValueError("TELEGRAM_CALLBACK_INVALID")
    return value


def _fixed_authorization_url(
    authorization: ProviderAuthorizationStartV1,
) -> str:
    query = quote(
        str(authorization.authorization_query or ""),
        safe="=&%+._~-",
    )
    return f"{TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT}?{query}"


def _delete_proof_cookie(
    response: Response,
    *,
    services: TelegramAuthRouteServicesV1,
) -> None:
    response.delete_cookie(
        services.cookies.proof_cookie(IdentityProviderV1.TELEGRAM),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _safe_error(
    detail: str,
    status_code: int,
    *,
    services: TelegramAuthRouteServicesV1,
) -> Response:
    response = JSONResponse(
        {"detail": detail},
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )
    _delete_proof_cookie(response, services=services)
    return response


def _rate_error(services: TelegramAuthRouteServicesV1) -> Response:
    return JSONResponse(
        {"detail": "RATE_LIMITED"},
        status_code=429,
        headers={
            "Cache-Control": "no-store",
            "Retry-After": str(services.abuse.policy.retry_after_seconds),
        },
    )


def _start_telegram_auth(services: TelegramAuthRouteServicesV1) -> Response:
    provider = IdentityProviderV1.TELEGRAM
    if not services.abuse.admit_start(provider):
        return _rate_error(services)
    runtime = services.runtime()
    if runtime is None:
        return _safe_error(
            "IDENTITY_PROVIDER_NOT_CONFIGURED",
            503,
            services=services,
        )

    browser_proof = new_authorization_browser_proof_v1()
    try:
        authorization = runtime.start(
            now=_utc_now(services),
            browser_proof=browser_proof,
        )
        authorization_url = _fixed_authorization_url(authorization)
    except (ProviderAuthorizationError, TypeError, ValueError):
        return _safe_error(
            "IDENTITY_PROVIDER_UNAVAILABLE",
            503,
            services=services,
        )

    response = RedirectResponse(
        authorization_url,
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        services.cookies.proof_cookie(provider),
        browser_proof,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=_PROOF_COOKIE_MAX_AGE_SECONDS,
    )
    return response


def _callback_values(
    request: Request,
    services: TelegramAuthRouteServicesV1,
) -> tuple[str, str, str]:
    if _bounded_query(request, "error", maximum=256, required=False):
        raise ValueError("TELEGRAM_CALLBACK_REJECTED")
    state = _bounded_query(request, "state", maximum=512) or ""
    code = _bounded_query(request, "code", maximum=2048) or ""
    browser_proof = request.cookies.get(
        services.cookies.proof_cookie(IdentityProviderV1.TELEGRAM),
        "",
    )
    if not browser_proof:
        raise ValueError("TELEGRAM_CALLBACK_BROWSER_PROOF_REQUIRED")
    return state, code, browser_proof


def _complete_identity(
    request: Request,
    services: TelegramAuthRouteServicesV1,
    runtime: ProviderAuthenticationRuntimeLike,
) -> VerifiedExternalIdentityV1 | Response:
    state, code, browser_proof = _callback_values(request, services)
    if not services.abuse.acquire_outbound():
        return _rate_error(services)
    try:
        identity = runtime.complete(
            state=state,
            code=code,
            browser_proof=browser_proof,
            now=_utc_now(services),
            device_id=None,
        )
    finally:
        services.abuse.release_outbound()
    if identity.provider != IdentityProviderV1.TELEGRAM:
        raise ProviderAuthorizationError("TELEGRAM_AUTH_PROVIDER_MISMATCH")
    return identity


def _establish_authenticated_session(
    request: Request,
    services: TelegramAuthRouteServicesV1,
    authentication: TelegramProductAuthenticationLike,
    identity: VerifiedExternalIdentityV1,
) -> Response:
    authenticated_at = _utc_now(services)
    account_scope = authentication.resolve_verified_identity(
        identity,
        now=authenticated_at,
    )
    authentication.revoke_session(
        request.cookies.get(services.cookies.session_cookie),
        now=authenticated_at,
    )

    token = new_session_token_v1()
    authentication.bind_session(
        token,
        account_scope,
        now=authenticated_at,
    )
    csrf = services.cookies.csrf_token(token)

    response = RedirectResponse(
        "/",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    _delete_proof_cookie(response, services=services)
    response.set_cookie(
        services.cookies.session_cookie,
        token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=services.cookies.session_max_age_seconds,
    )
    response.set_cookie(
        services.cookies.csrf_cookie,
        csrf,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=services.cookies.session_max_age_seconds,
    )
    return response


def _complete_telegram_callback(
    request: Request,
    services: TelegramAuthRouteServicesV1,
) -> Response:
    provider = IdentityProviderV1.TELEGRAM
    if not services.abuse.admit_callback(provider):
        return _rate_error(services)
    runtime = services.runtime()
    authentication = services.authentication
    if runtime is None or authentication is None:
        return _safe_error(
            "IDENTITY_PROVIDER_NOT_CONFIGURED",
            503,
            services=services,
        )

    try:
        identity = _complete_identity(request, services, runtime)
        if isinstance(identity, Response):
            return identity
        return _establish_authenticated_session(
            request,
            services,
            authentication,
            identity,
        )
    except (ProductIdentityError, ProviderAuthorizationError, ValueError):
        return _safe_error(
            "AUTHENTICATION_REJECTED",
            400,
            services=services,
        )


def install_telegram_auth_routes_v1(
    app: FastAPI,
    *,
    services: TelegramAuthRouteServicesV1,
) -> None:
    """Install only the current Telegram human-login surface."""

    @app.post(TELEGRAM_START_PATH, include_in_schema=False)
    def telegram_start() -> Response:
        return _start_telegram_auth(services)

    @app.get(TELEGRAM_CALLBACK_PATH, include_in_schema=False)
    def telegram_callback(request: Request) -> Response:
        return _complete_telegram_callback(request, services)
