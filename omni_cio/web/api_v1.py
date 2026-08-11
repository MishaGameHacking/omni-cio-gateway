from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.web.identity_v1 import ProviderDescriptorV1, default_provider_descriptors
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

    @app.get("/api/v10/web/auth/{provider}/start")
    def provider_start(provider: str) -> Response:
        descriptor = next(
            (
                item
                for item in services.providers
                if item.provider.value == provider
            ),
            None,
        )
        if descriptor is None:
            raise HTTPException(status_code=404, detail="IDENTITY_PROVIDER_UNKNOWN")
        if not descriptor.enabled:
            raise HTTPException(status_code=503, detail="IDENTITY_PROVIDER_NOT_CONFIGURED")
        raise HTTPException(status_code=503, detail="IDENTITY_PROVIDER_RUNTIME_NOT_BOUND")

    @app.post("/api/v10/web/private-test-login")
    def private_test_login(request: Request, response: Response) -> dict[str, Any]:
        if not services.private_test_identity_enabled or not _is_loopback_request(request):
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

    return app
