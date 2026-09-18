from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import quote

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import (
    IdentityProviderV1,
    ProviderAvailabilityV1,
    ProviderDescriptorV1,
    VerifiedExternalIdentityV1,
)
from omni_cio.web.product_identity_v1 import (
    ProductAccountScopeV1,
    ProductIdentityError,
)
from omni_cio.web.provider_auth_v1 import (
    ProviderAuthenticationRuntimeLike,
    ProviderAuthorizationError,
    ProviderAuthorizationStartV1,
    new_authorization_browser_proof_v1,
)
from omni_cio.web.request_limits_v1 import ProviderAuthAbuseControlV1
from omni_cio.web.session_v1 import SessionScopeV1, new_session_token_v1
from omni_cio.web.telegram_oidc_v1 import TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT
from omni_cio.web.vk_id_oauth_v1 import VK_ID_AUTHORIZATION_ENDPOINT


TELEGRAM_START_PATH = "/api/v10/web/auth/telegram/start"
TELEGRAM_CALLBACK_PATH = "/api/v10/web/auth/telegram/callback"
VK_ID_START_PATH = "/api/v10/web/auth/vk_id/start"
VK_ID_CALLBACK_PATH = "/api/v10/web/auth/vk_id/callback"
_PROOF_COOKIE_MAX_AGE_SECONDS = 15 * 60
_ALLOWED_DISABLED_REASONS = frozenset(
    {
        "PUBLIC_MULTI_USER_DISABLED",
        "PROVIDER_ACTIVATION_DISABLED",
    }
)


class ProductAuthenticationLike(Protocol):
    def resolve_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        now: datetime,
    ) -> ProductAccountScopeV1: ...

    def revoke_session(self, token: str | None, *, now: datetime) -> bool: ...

    def bind_session(
        self,
        token: str,
        account_scope: ProductAccountScopeV1,
        *,
        now: datetime,
    ) -> SessionScopeV1: ...


@dataclass(slots=True)
class ProviderAuthRouteServicesV1:
    runtimes: tuple[ProviderAuthenticationRuntimeLike, ...]
    authentication: ProductAuthenticationLike | None
    cookies: BrowserCookiePolicyV1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    disabled_reasons: Mapping[IdentityProviderV1, str] = field(default_factory=dict)
    registration_enabled: bool = False
    abuse: ProviderAuthAbuseControlV1 = field(
        default_factory=ProviderAuthAbuseControlV1
    )

    def __post_init__(self) -> None:
        providers = tuple(runtime.provider for runtime in self.runtimes)
        if len(providers) != len(set(providers)):
            raise ValueError("PROVIDER_AUTH_RUNTIME_DUPLICATE")
        if any(
            provider not in {IdentityProviderV1.TELEGRAM, IdentityProviderV1.VK_ID}
            for provider in providers
        ):
            raise ValueError("PROVIDER_AUTH_RUNTIME_INVALID")
        if self.runtimes and self.authentication is None:
            raise ValueError("PROVIDER_AUTH_AUTHENTICATION_REQUIRED")
        if self.registration_enabled and self.authentication is None:
            raise ValueError("PROVIDER_AUTH_REGISTRATION_REQUIRES_AUTHENTICATION")
        blocked = set(self.disabled_reasons)
        if blocked - set(IdentityProviderV1):
            raise ValueError("PROVIDER_AUTH_DISABLED_PROVIDER_INVALID")
        if blocked & set(providers):
            raise ValueError("PROVIDER_AUTH_ENABLED_PROVIDER_CANNOT_BE_DISABLED")
        if any(
            reason not in _ALLOWED_DISABLED_REASONS
            for reason in self.disabled_reasons.values()
        ):
            raise ValueError("PROVIDER_AUTH_DISABLED_REASON_INVALID")

    def runtime(
        self,
        provider: IdentityProviderV1,
    ) -> ProviderAuthenticationRuntimeLike | None:
        return next(
            (runtime for runtime in self.runtimes if runtime.provider == provider),
            None,
        )

    def disabled_reason(self, provider: IdentityProviderV1) -> str | None:
        if self.runtime(provider) is not None:
            return None
        return self.disabled_reasons.get(provider, "NOT_CONFIGURED")

    def descriptors(self) -> tuple[ProviderDescriptorV1, ...]:
        configured = {runtime.provider for runtime in self.runtimes}
        return tuple(
            ProviderDescriptorV1(
                provider=provider,
                availability=(
                    ProviderAvailabilityV1.CONFIGURED
                    if provider in configured
                    else ProviderAvailabilityV1.NOT_CONFIGURED
                ),
            )
            for provider in (IdentityProviderV1.TELEGRAM, IdentityProviderV1.VK_ID)
        )


def _utc_now(services: ProviderAuthRouteServicesV1) -> datetime:
    value = services.now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("PROVIDER_AUTH_CLOCK_NOT_UTC_AWARE")
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
            raise ValueError("PROVIDER_CALLBACK_INVALID")
        return None
    if len(values) != 1:
        raise ValueError("PROVIDER_CALLBACK_INVALID")
    value = values[0]
    if not value or len(value) > maximum or not value.isascii():
        raise ValueError("PROVIDER_CALLBACK_INVALID")
    return value


def _fixed_authorization_url(
    provider: IdentityProviderV1,
    authorization: ProviderAuthorizationStartV1,
) -> str:
    if provider == IdentityProviderV1.TELEGRAM:
        endpoint = TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT
    elif provider == IdentityProviderV1.VK_ID:
        endpoint = VK_ID_AUTHORIZATION_ENDPOINT
    else:
        raise ProviderAuthorizationError("PROVIDER_AUTHORIZATION_ENDPOINT_INVALID")
    query = quote(
        str(authorization.authorization_query or ""),
        safe="=&%+._~-",
    )
    return f"{endpoint}?{query}"


def _delete_proof_cookie(
    response: Response,
    *,
    provider: IdentityProviderV1,
    cookies: BrowserCookiePolicyV1,
) -> None:
    response.delete_cookie(
        cookies.proof_cookie(provider),
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _safe_error(
    detail: str,
    status_code: int,
    *,
    provider: IdentityProviderV1,
    cookies: BrowserCookiePolicyV1,
) -> Response:
    response = JSONResponse(
        {"detail": detail},
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )
    _delete_proof_cookie(response, provider=provider, cookies=cookies)
    return response


def _rate_error(services: ProviderAuthRouteServicesV1) -> Response:
    return JSONResponse(
        {"detail": "RATE_LIMITED"},
        status_code=429,
        headers={
            "Cache-Control": "no-store",
            "Retry-After": str(services.abuse.policy.retry_after_seconds),
        },
    )


def _start_provider_auth(
    provider: IdentityProviderV1,
    services: ProviderAuthRouteServicesV1,
) -> Response:
    if not services.abuse.admit_start(provider):
        return _rate_error(services)
    runtime = services.runtime(provider)
    if runtime is None:
        return _safe_error(
            "IDENTITY_PROVIDER_NOT_CONFIGURED",
            503,
            provider=provider,
            cookies=services.cookies,
        )

    browser_proof = new_authorization_browser_proof_v1()
    try:
        authorization = runtime.start(
            now=_utc_now(services),
            browser_proof=browser_proof,
        )
        authorization_url = _fixed_authorization_url(provider, authorization)
    except (ProviderAuthorizationError, TypeError, ValueError):
        return _safe_error(
            "IDENTITY_PROVIDER_UNAVAILABLE",
            503,
            provider=provider,
            cookies=services.cookies,
        )

    response = RedirectResponse(
        authorization_url,
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )
    # The credential is minted locally and the provider runtime cannot replace it.
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


def _provider_callback_values(
    provider: IdentityProviderV1,
    request: Request,
    cookies: BrowserCookiePolicyV1,
) -> tuple[str, str, str | None, str]:
    if _bounded_query(request, "error", maximum=256, required=False):
        raise ValueError("PROVIDER_CALLBACK_REJECTED")
    state = _bounded_query(request, "state", maximum=512) or ""
    code = _bounded_query(request, "code", maximum=2048) or ""
    device_id = (
        _bounded_query(request, "device_id", maximum=512)
        if provider == IdentityProviderV1.VK_ID
        else None
    )
    browser_proof = request.cookies.get(cookies.proof_cookie(provider), "")
    if not browser_proof:
        raise ValueError("PROVIDER_CALLBACK_BROWSER_PROOF_REQUIRED")
    return state, code, device_id, browser_proof


def _complete_provider_identity(
    provider: IdentityProviderV1,
    request: Request,
    services: ProviderAuthRouteServicesV1,
    runtime: ProviderAuthenticationRuntimeLike,
) -> VerifiedExternalIdentityV1 | Response:
    state, code, device_id, browser_proof = _provider_callback_values(
        provider,
        request,
        services.cookies,
    )
    if not services.abuse.acquire_outbound():
        return _rate_error(services)
    try:
        return runtime.complete(
            state=state,
            code=code,
            browser_proof=browser_proof,
            now=_utc_now(services),
            device_id=device_id,
        )
    finally:
        services.abuse.release_outbound()


def _establish_authenticated_session(
    provider: IdentityProviderV1,
    request: Request,
    services: ProviderAuthRouteServicesV1,
    authentication: ProductAuthenticationLike,
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

    # Session and CSRF material are derived locally only after provider verification.
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
    _delete_proof_cookie(response, provider=provider, cookies=services.cookies)
    response.set_cookie(
        services.cookies.session_cookie,
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=services.cookies.session_max_age_seconds,
    )
    # The browser receives the verified CSRF value through the authenticated
    # session bootstrap response; the cookie itself remains script-inaccessible.
    response.set_cookie(
        services.cookies.csrf_cookie,
        csrf,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        max_age=services.cookies.session_max_age_seconds,
    )
    return response


def _complete_provider_callback(
    provider: IdentityProviderV1,
    request: Request,
    services: ProviderAuthRouteServicesV1,
) -> Response:
    if not services.abuse.admit_callback(provider):
        return _rate_error(services)
    runtime = services.runtime(provider)
    authentication = services.authentication
    if runtime is None or authentication is None:
        return _safe_error(
            "IDENTITY_PROVIDER_NOT_CONFIGURED",
            503,
            provider=provider,
            cookies=services.cookies,
        )

    try:
        identity = _complete_provider_identity(provider, request, services, runtime)
        if isinstance(identity, Response):
            return identity
        return _establish_authenticated_session(
            provider,
            request,
            services,
            authentication,
            identity,
        )
    except (ProductIdentityError, ProviderAuthorizationError, ValueError):
        return _safe_error(
            "AUTHENTICATION_REJECTED",
            400,
            provider=provider,
            cookies=services.cookies,
        )


def install_provider_auth_routes_v1(
    app: FastAPI,
    *,
    services: ProviderAuthRouteServicesV1,
) -> None:
    @app.post(TELEGRAM_START_PATH, include_in_schema=False)
    def telegram_start() -> Response:
        return _start_provider_auth(IdentityProviderV1.TELEGRAM, services)

    @app.get(TELEGRAM_CALLBACK_PATH, include_in_schema=False)
    def telegram_callback(request: Request) -> Response:
        return _complete_provider_callback(
            IdentityProviderV1.TELEGRAM,
            request,
            services,
        )

    @app.post(VK_ID_START_PATH, include_in_schema=False)
    def vk_id_start() -> Response:
        return _start_provider_auth(IdentityProviderV1.VK_ID, services)

    @app.get(VK_ID_CALLBACK_PATH, include_in_schema=False)
    def vk_id_callback(request: Request) -> Response:
        return _complete_provider_callback(
            IdentityProviderV1.VK_ID,
            request,
            services,
        )
