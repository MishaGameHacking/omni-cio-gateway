from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.identity_v1 import ProviderDescriptorV1, default_provider_descriptors
from omni_cio.web.live_acceptance_v1 import (
    BrokerLiveAcceptanceError,
    BrokerLiveAcceptanceServiceV1,
)
from omni_cio.web.persistence_v1 import (
    BrokerConnectionRecordV1,
    PostgresBrokerConnectionRepositoryV1,
)
from omni_cio.web.provisioning_v1 import (
    BrokerProvisioningError,
    BrokerProvisioningServiceV1,
)
from omni_cio.web.session_v1 import SessionScopeV1


SESSION_COOKIE = "omni_v10_session"


class SessionRegistryLike(Protocol):
    def create(
        self,
        *,
        user_id: str,
        tenant_id: str,
        now: datetime,
    ) -> tuple[str, SessionScopeV1]: ...

    def resolve(self, token: str | None, *, now: datetime) -> SessionScopeV1 | None: ...

    def revoke(self, token: str | None, *, now: datetime) -> bool: ...

    def revoke_all_for_user(self, user_id: str, *, now: datetime) -> int: ...


@dataclass(frozen=True, slots=True)
class WebHealthV1:
    state: str = "READY"
    freshness: str = "FRESH"


@dataclass(slots=True)
class WebApiServicesV1:
    sessions: SessionRegistryLike
    broker_repository: PostgresBrokerConnectionRepositoryV1
    provisioning: BrokerProvisioningServiceV1
    live_acceptance: BrokerLiveAcceptanceServiceV1 | None = None
    providers: tuple[ProviderDescriptorV1, ...] = default_provider_descriptors()
    health_provider: Callable[[], WebHealthV1] = WebHealthV1
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    private_test_identity_enabled: bool = False
    secure_cookie: bool = False


def _now(services: WebApiServicesV1) -> datetime:
    value = services.now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise RuntimeError("WEB_API_CLOCK_NOT_UTC_AWARE")
    return value.astimezone(timezone.utc)


def _session(request: Request, services: WebApiServicesV1) -> SessionScopeV1 | None:
    return services.sessions.resolve(
        request.cookies.get(SESSION_COOKIE),
        now=_now(services),
    )


def _require_session(request: Request, services: WebApiServicesV1) -> SessionScopeV1:
    scope = _session(request, services)
    if scope is None:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return scope


def _is_loopback_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return False


def _require_live_acceptance(
    request: Request,
    services: WebApiServicesV1,
) -> BrokerLiveAcceptanceServiceV1:
    service = services.live_acceptance
    if service is None or not _is_loopback_request(request):
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return service


def _safe_connection(record: BrokerConnectionRecordV1) -> dict[str, Any]:
    return {
        "connection_id": record.connection_id,
        "provider": record.provider,
        "role": record.credential_role,
        "state": record.state,
        "last_verified_at": (
            record.last_verified_at.isoformat() if record.last_verified_at else None
        ),
        "accounts": [
            {
                "masked_label": account.masked_label,
                "access_level": "READ_ONLY",
            }
            for account in record.accounts
        ],
    }


async def _json_object(request: Request) -> dict[str, Any]:
    try:
        value = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="INVALID_REQUEST")
    return value


def _string(value: Any, *, reason: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=reason)
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise HTTPException(status_code=400, detail=reason)
    return normalized


def _integer(value: Any, *, reason: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=400, detail=reason)
    if value < minimum or value > maximum:
        raise HTTPException(status_code=400, detail=reason)
    return value


def _boolean(value: Any, *, reason: str) -> bool:
    if not isinstance(value, bool):
        raise HTTPException(status_code=400, detail=reason)
    return value


def create_web_api(services: WebApiServicesV1) -> FastAPI:
    app = FastAPI(
        title="Omni-CIO V10 local Web API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/api/v10/web/session")
    def session_view(request: Request) -> dict[str, Any]:
        scope = _session(request, services)
        if scope is None:
            return {"authenticated": False}
        return {
            "authenticated": True,
            "user_label": "OWNER",
            "tenant_label": "Personal",
            "expires_at": scope.expires_at.isoformat(),
        }

    @app.get("/api/v10/web/auth/providers")
    def provider_view() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for descriptor in services.providers:
            row: dict[str, Any] = {
                "provider": descriptor.provider.value,
                "enabled": descriptor.enabled,
            }
            if not descriptor.enabled:
                row["reason"] = "NOT_CONFIGURED"
            elif descriptor.availability.value == "private_acceptance":
                row["reason"] = "PRIVATE_ACCEPTANCE_ONLY"
            result.append(row)
        return result

    @app.get("/api/v10/web/private-test-login/status")
    def private_test_login_status(request: Request) -> dict[str, bool]:
        return {
            "enabled": services.private_test_identity_enabled
            and _is_loopback_request(request)
        }

    @app.get("/api/v10/web/auth/{provider}/start")
    def provider_start(provider: str) -> Response:
        descriptor = next(
            (item for item in services.providers if item.provider.value == provider),
            None,
        )
        if descriptor is None:
            raise HTTPException(status_code=404, detail="IDENTITY_PROVIDER_UNKNOWN")
        if not descriptor.enabled:
            raise HTTPException(
                status_code=503, detail="IDENTITY_PROVIDER_NOT_CONFIGURED"
            )
        raise HTTPException(
            status_code=503, detail="IDENTITY_PROVIDER_RUNTIME_NOT_BOUND"
        )

    @app.post("/api/v10/web/private-test-login")
    def private_test_login(request: Request, response: Response) -> dict[str, Any]:
        if not services.private_test_identity_enabled or not _is_loopback_request(
            request
        ):
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        token, scope = services.sessions.create(
            user_id=OWNER_USER_ID,
            tenant_id=OWNER_TENANT_ID,
            now=_now(services),
        )
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            secure=services.secure_cookie,
            samesite="strict",
            path="/",
            max_age=max(1, int((scope.expires_at - _now(services)).total_seconds())),
        )
        return {"ok": True}

    @app.post("/api/v10/web/session/logout")
    def logout(request: Request, response: Response) -> dict[str, Any]:
        token = request.cookies.get(SESSION_COOKIE)
        services.sessions.revoke(token, now=_now(services))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @app.post("/api/v10/web/session/revoke-all")
    def revoke_all(request: Request, response: Response) -> dict[str, Any]:
        scope = _require_session(request, services)
        services.sessions.revoke_all_for_user(scope.user_id, now=_now(services))
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"ok": True}

    @app.get("/api/v10/web/health")
    def health(request: Request) -> dict[str, Any]:
        _require_session(request, services)
        value = services.health_provider()
        return {
            "state": value.state,
            "freshness": value.freshness,
            "checked_at": _now(services).isoformat(),
        }

    @app.get("/api/v10/web/broker-connections")
    def broker_connections(request: Request) -> list[dict[str, Any]]:
        scope = _require_session(request, services)
        return [
            _safe_connection(item)
            for item in services.broker_repository.list_read_connections(
                tenant_id=scope.tenant_id
            )
        ]

    @app.post("/api/v10/web/broker-connections/preview")
    async def broker_preview(request: Request) -> JSONResponse:
        scope = _require_session(request, services)
        body = await _json_object(request)
        token = _string(
            body.get("token"),
            reason="BROKER_READ_TOKEN_INVALID",
            maximum=16384,
        )
        try:
            preview = services.provisioning.preview(
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                token=token,
                now=_now(services),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="BROKER_READ_VALIDATION_FAILED",
            ) from exc
        finally:
            token = ""
        return JSONResponse(
            {
                "challenge_id": preview.challenge_id,
                "expires_at": preview.expires_at.isoformat(),
                "accounts": [
                    {
                        "selection_id": item.selection_id,
                        "masked_label": item.masked_label,
                        "access_level": item.access_level,
                    }
                    for item in preview.accounts
                ],
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/v10/web/broker-connections/commit")
    async def broker_commit(request: Request) -> dict[str, Any]:
        scope = _require_session(request, services)
        body = await _json_object(request)
        challenge_id = _string(
            body.get("challenge_id"),
            reason="BROKER_PROVISIONING_CHALLENGE_INVALID",
            maximum=256,
        )
        selected = body.get("selected_accounts")
        if not isinstance(selected, list) or not all(
            isinstance(item, str) for item in selected
        ):
            raise HTTPException(
                status_code=400,
                detail="BROKER_ACCOUNT_SELECTION_INVALID",
            )
        try:
            record = services.provisioning.commit_new(
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                challenge_id=challenge_id,
                selected_accounts=tuple(selected),
                now=_now(services),
            )
        except BrokerProvisioningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _safe_connection(record)

    @app.post("/api/v10/web/broker-connections/{connection_id}/replace")
    async def broker_replace(connection_id: str, request: Request) -> dict[str, Any]:
        scope = _require_session(request, services)
        body = await _json_object(request)
        challenge_id = _string(
            body.get("challenge_id"),
            reason="BROKER_PROVISIONING_CHALLENGE_INVALID",
            maximum=256,
        )
        selected = body.get("selected_accounts")
        if not isinstance(selected, list) or not all(
            isinstance(item, str) for item in selected
        ):
            raise HTTPException(
                status_code=400,
                detail="BROKER_ACCOUNT_SELECTION_INVALID",
            )
        try:
            services.provisioning.replace_read_credential(
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                connection_id=connection_id,
                challenge_id=challenge_id,
                selected_accounts=tuple(selected),
                now=_now(services),
            )
        except BrokerProvisioningError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @app.delete("/api/v10/web/broker-connections/{connection_id}")
    def broker_revoke(connection_id: str, request: Request) -> dict[str, Any]:
        scope = _require_session(request, services)
        revoked = services.provisioning.revoke_read_connection(
            tenant_id=scope.tenant_id,
            connection_id=connection_id,
            now=_now(services),
        )
        if not revoked:
            raise HTTPException(status_code=404, detail="BROKER_CONNECTION_NOT_FOUND")
        return {"ok": True}

    @app.get("/api/v10/web/wp15-live-acceptance/status")
    def wp15_live_status(request: Request) -> dict[str, bool]:
        _require_session(request, services)
        return {
            "enabled": services.live_acceptance is not None
            and _is_loopback_request(request)
        }

    @app.post("/api/v10/web/wp15-live-acceptance/start")
    async def wp15_live_start(request: Request) -> JSONResponse:
        scope = _require_session(request, services)
        service = _require_live_acceptance(request, services)
        body = await _json_object(request)
        connection_id = _string(
            body.get("connection_id"),
            reason="WP15_LIVE_CONNECTION_INVALID",
            maximum=256,
        )
        account_index = _integer(
            body.get("account_index"),
            reason="WP15_LIVE_ACCOUNT_SELECTION_INVALID",
            minimum=0,
            maximum=255,
        )
        try:
            view = await asyncio.to_thread(
                service.start,
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                connection_id=connection_id,
                account_index=account_index,
            )
        except BrokerLiveAcceptanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="WP15_LIVE_ACCEPTANCE_UNAVAILABLE",
            ) from exc
        return JSONResponse(
            {
                "challenge_id": view.challenge_id,
                "expires_at": view.expires_at.isoformat(),
                "masked_account": view.masked_account,
                "access_level": view.access_level,
                "portfolio_total": view.portfolio_total,
                "portfolio_currency": view.portfolio_currency,
                "sample": {
                    "label": view.sample.label,
                    "quantity": view.sample.quantity,
                    "unit_price": view.sample.unit_price,
                    "market_value": view.sample.market_value,
                    "currency": view.sample.currency,
                },
                "freshness_state": view.freshness_state,
                "retrieved_at": view.retrieved_at.isoformat(),
                "evaluated_at": view.evaluated_at.isoformat(),
                "age_seconds": view.age_seconds,
                "normalized_position_count": view.normalized_position_count,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/v10/web/wp15-live-acceptance/confirm")
    async def wp15_live_confirm(request: Request) -> JSONResponse:
        scope = _require_session(request, services)
        service = _require_live_acceptance(request, services)
        body = await _json_object(request)
        challenge_id = _string(
            body.get("challenge_id"),
            reason="WP15_LIVE_CHALLENGE_INVALID",
            maximum=256,
        )
        try:
            service.confirm(
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                challenge_id=challenge_id,
                intended_account_confirmed=_boolean(
                    body.get("intended_account_confirmed"),
                    reason="WP15_LIVE_CONFIRMATION_INVALID",
                ),
                portfolio_summary_parity=_boolean(
                    body.get("portfolio_summary_parity"),
                    reason="WP15_LIVE_CONFIRMATION_INVALID",
                ),
                sample_position_quantity_value_parity=_boolean(
                    body.get("sample_position_quantity_value_parity"),
                    reason="WP15_LIVE_CONFIRMATION_INVALID",
                ),
                freshness_confirmed=_boolean(
                    body.get("freshness_confirmed"),
                    reason="WP15_LIVE_CONFIRMATION_INVALID",
                ),
            )
        except BrokerLiveAcceptanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(
            {"accepted": True, "pending_owner_finalization": True},
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/v10/web/wp15-live-acceptance/cancel")
    async def wp15_live_cancel(request: Request) -> dict[str, bool]:
        scope = _require_session(request, services)
        service = _require_live_acceptance(request, services)
        body = await _json_object(request)
        challenge_id = _string(
            body.get("challenge_id"),
            reason="WP15_LIVE_CHALLENGE_INVALID",
            maximum=256,
        )
        try:
            cancelled = service.cancel(
                user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                challenge_id=challenge_id,
            )
        except BrokerLiveAcceptanceError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"cancelled": cancelled}

    return app
