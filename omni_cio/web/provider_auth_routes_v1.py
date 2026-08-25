from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from omni_cio.web.browser_security_v1 import BrowserCookiePolicyV1
from omni_cio.web.identity_v1 import (
    IdentityProviderV1,
    ProviderAvailabilityV1,
    ProviderDescriptorV1,
    VerifiedExternalIdentityV1,
)
from omni_cio.web.product_identity_v1 import ProductIdentityError
from omni_cio.web.provider_auth_v1 import (
    ProviderAuthenticationRuntimeLike,
    ProviderAuthorizationError,
)
from omni_cio.web.request_limits_v1 import ProviderAuthAbuseControlV1
from omni_cio.web.session_v1 import SessionScopeV1


TELEGRAM_START_PATH = "/api/v10/web/auth/telegram/start"
TELEGRAM_CALLBACK_PATH = "/api/v10/web/auth/telegram/callback"
VK_ID_START_PATH = "/api/v10/web/auth/vk_id/start"
VK_ID_CALLBACK_PATH = "/api/v10/web/auth/vk_id/callback"
_PROOF_COOKIE_MAX_AGE_SECONDS = 15 * 60


class ProductAuthenticationLike(Protocol):
    def authenticate_verified_identity(
        self,
        identity: VerifiedExternalIdentityV1,
        *,
        current_session_token: str | None,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]: ...


@dataclass(slots=True)
class ProviderAuthRouteServicesV1:
    runtimes: tuple[ProviderAuthenticationRuntimeLike, ...]
    authentication: ProductAuthenticationLike | None
    cookies: BrowserCookiePolicyV1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    abuse: ProviderAuthAbuseControlV1 = field(
        default_factory=ProviderAuthAbuseControlV1
    )

    def __post_init__(self) -> None:
        providers = tuple(runtime.provider for runtime in self.runtimes)
        if len(providers) != len(set(providers)):
            raise ValueError("PROVIDER_AUTH_RUNTIME_DUPLICATE")
        if any(
            provider
            not in {IdentityProviderV1.TELEGRAM, IdentityProviderV1.VK_ID}
            for provider in providers
        ):
            raise ValueError("PROVIDER_AUTH_RUNTIME_INVALID")
        if self.runtimes and self.authentication is None:
            raise ValueError("PROVIDER_AUTH_AUTHENTICATION_REQUIRED")

    def runtime(
        self,
        provider: IdentityProviderV1,
    ) -> ProviderAuthenticationRuntimeLike | None:
        return next(
            (runtime for runtime in self.runtimes if runtime.provider == provider),
            None,
        )

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


def _delete_proof_cookie(
    response: Response,
    *,
    provider: IdentityProviderV1,
    cookies: BrowserCookiePolicyV1,
) -> None:
    response.delete_cookie(
        cookies.proof_cookie(provider),
        path="/",
        secure=cookies.secure,
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


def install_provider_auth_routes_v1(
    app: FastAPI,
    *,
    services: ProviderAuthRouteServicesV1,
) -> None:
    def start(provider: IdentityProviderV1) -> Response:
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
        issued = _utc_now(services)
        try:
            authorization = runtime.start(now=issued)
        except ProviderAuthorizationError:
            return _safe_error(
                "IDENTITY_PROVIDER_UNAVAILABLE",
                503,
                provider=provider,
                cookies=services.cookies,
            )
        max_age = min(
            _PROOF_COOKIE_MAX_AGE_SECONDS,
            max(1, int((authorization.expires_at - issued).total_seconds())),
        )
        response = RedirectResponse(
            authorization.authorization_url,
            status_code=303,
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            services.cookies.proof_cookie(provider),
            authorization.browser_proof,
            httponly=True,
            secure=services.cookies.secure,
            samesite="lax",
            path="/",
            max_age=max_age,
        )
        return response

    def callback(provider: IdentityProviderV1, request: Request) -> Response:
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
            if _bounded_query(request, "error", maximum=256, required=False):
                raise ValueError("PROVIDER_CALLBACK_REJECTED")
            state = _bounded_query(request, "state", maximum=512)
            code = _bounded_query(request, "code", maximum=2048)
            device_id = (
                _bounded_query(request, "device_id", maximum=512)
                if provider == IdentityProviderV1.VK_ID
                else None
            )
            browser_proof = request.cookies.get(
                services.cookies.proof_cookie(provider),
                "",
            )
            if not browser_proof:
                raise ValueError("PROVIDER_CALLBACK_BROWSER_PROOF_REQUIRED")
            if not services.abuse.acquire_outbound():
                return _rate_error(services)
            try:
                identity = runtime.complete(
                    state=state or "",
                    code=code or "",
                    browser_proof=browser_proof,
                    now=_utc_now(services),
                    device_id=device_id,
                )
            finally:
                services.abuse.release_outbound()
            token, _ = authentication.authenticate_verified_identity(
                identity,
                current_session_token=request.cookies.get(
                    services.cookies.session_cookie
                ),
                now=_utc_now(services),
            )
            csrf = services.cookies.csrf_token(token)
        except (ProductIdentityError, ProviderAuthorizationError, ValueError):
            return _safe_error(
                "AUTHENTICATION_REJECTED",
                400,
                provider=provider,
                cookies=services.cookies,
            )

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
            secure=services.cookies.secure,
            samesite="lax",
            path="/",
            max_age=services.cookies.session_max_age_seconds,
        )
        response.set_cookie(
            services.cookies.csrf_cookie,
            csrf,
            httponly=False,
            secure=services.cookies.secure,
            samesite="lax",
            path="/",
            max_age=services.cookies.session_max_age_seconds,
        )
        return response

    @app.post(TELEGRAM_START_PATH, include_in_schema=False)
    def telegram_start() -> Response:
        return start(IdentityProviderV1.TELEGRAM)

    @app.get(TELEGRAM_CALLBACK_PATH, include_in_schema=False)
    def telegram_callback(request: Request) -> Response:
        return callback(IdentityProviderV1.TELEGRAM, request)

    @app.post(VK_ID_START_PATH, include_in_schema=False)
    def vk_id_start() -> Response:
        return start(IdentityProviderV1.VK_ID)

    @app.get(VK_ID_CALLBACK_PATH, include_in_schema=False)
    def vk_id_callback(request: Request) -> Response:
        return callback(IdentityProviderV1.VK_ID, request)
