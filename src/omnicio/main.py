"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Literal, cast

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from .cbr import CBRClient, CBRUnavailable
from .broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .config import Settings, load_settings
from .db import Database, UserRecord
from .security import (
    SecurityValueError,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_vkid_flow,
    pkce_challenge,
    seal_vkid_flow,
)
from .service import AuthService, LoginUnavailable, OwnerAccessDenied
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable
from .vkid import VKIDClient, VKIDRejected, VKIDUnavailable

SESSION_COOKIE = "omnicio_session"
VKID_FLOW_COOKIE = "omnicio_vkid_flow"
CANONICAL_ORIGIN = "https://omnicio.ru"
VKID_CALLBACK = f"{CANONICAL_ORIGIN}/api/auth/vkid/callback"


class StartVKIDBody(BaseModel):
    accept_privacy: bool
    accept_personal_data: bool
    accept_terms: bool
    confirm_age_18: bool


class TBankCredentialBody(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)
    environment: Literal["prod", "sandbox"] = "prod"
    accept_personal_terms: bool


class TBankConnectBody(TBankCredentialBody):
    account_id: str = Field(min_length=1, max_length=128)


def client_ip(request: Request) -> str:
    direct = request.client.host if request.client else ""
    if direct in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return direct or "unknown"


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin != CANONICAL_ORIGIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="origin rejected")


def service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


def settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def broker_service(request: Request) -> BrokerService:
    return cast(BrokerService, request.app.state.broker_service)


def cbr_client(request: Request) -> CBRClient:
    return cast(CBRClient, request.app.state.cbr_client)


def vkid_client(request: Request) -> VKIDClient:
    return cast(VKIDClient, request.app.state.vkid_client)


def authenticated_user(
    request: Request,
    session_token: str | None,
) -> UserRecord:
    user = service(request).refresh_session(session_token or "")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user


def callback_values(request: Request) -> dict[str, str]:
    payload_raw = request.query_params.get("payload")
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError as exc:
            raise VKIDRejected("VK ID callback payload is invalid") from exc
        if not isinstance(payload, dict):
            raise VKIDRejected("VK ID callback payload is invalid")
        values: dict[str, str] = {}
        for key in ("code", "state", "device_id", "error"):
            value = payload.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise VKIDRejected("VK ID callback payload is invalid")
            values[key] = value
        return values

    return {
        key: value
        for key in ("code", "state", "device_id", "error")
        if (value := request.query_params.get(key)) is not None
    }


def validate_vkid_callback_values(values: dict[str, str], expected_state: str) -> tuple[str, str]:
    if values.get("error"):
        raise VKIDRejected("VK ID returned an authorization error")

    code = values.get("code", "")
    state_value = values.get("state", "")
    device_id = values.get("device_id", "")
    if not code or not state_value or not device_id:
        raise VKIDRejected("VK ID callback is incomplete")
    if state_value != expected_state:
        raise VKIDRejected("VK ID state mismatch")
    if len(code) > 4096 or len(device_id) > 512 or len(state_value) > 512:
        raise VKIDRejected("VK ID callback value is too long")
    return code, device_id


def auth_redirect(path: str) -> RedirectResponse:
    response = RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(
        VKID_FLOW_COOKIE,
        path="/api/auth/vkid",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = load_settings()
    database = Database(cfg.database_url)
    database.open()
    app.state.settings = cfg
    app.state.database = database
    app.state.auth_service = AuthService(cfg, database)
    app.state.vkid_client = VKIDClient(
        app_id=cfg.vkid_app_id,
        redirect_uri=VKID_CALLBACK,
    )
    app.state.broker_service = BrokerService(
        database,
        credential_key=cfg.broker_token_crypto_key,
        tbank=TBankInvestClient(),
    )
    app.state.cbr_client = CBRClient()
    try:
        yield
    finally:
        database.close()


app = FastAPI(
    title="OmniCIO Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready(request: Request) -> dict[str, str]:
    database: Database = request.app.state.database
    if not database.healthcheck():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


@app.get("/api/auth/config")
def auth_config(request: Request) -> dict[str, object]:
    cfg = settings(request)
    return {
        "mode": "owner_only",
        "auth_provider": "vkid",
        "registration_enabled": False,
        "owner_login_enabled": cfg.vkid_ready,
        "legal_versions": {
            "privacy_policy": cfg.privacy_version,
            "personal_data_consent": cfg.consent_version,
            "terms": cfg.terms_version,
        },
    }


@app.post("/api/auth/vkid/start")
def start_vkid(
    body: StartVKIDBody,
    request: Request,
    response: Response,
) -> dict[str, str]:
    require_same_origin(request)
    cfg = settings(request)
    if not cfg.vkid_ready:
        raise HTTPException(status_code=503, detail="VK ID owner login is not configured")
    if not (body.accept_privacy and body.accept_personal_data and body.accept_terms):
        raise HTTPException(status_code=400, detail="legal acknowledgments are required")
    if not body.confirm_age_18:
        raise HTTPException(status_code=400, detail="owner must confirm age 18+")

    state_value = generate_oauth_state()
    verifier = generate_pkce_verifier()
    flow = seal_vkid_flow(
        state=state_value,
        code_verifier=verifier,
        legal_versions=service(request).legal_versions(),
        crypto_key=cfg.vkid_flow_crypto_key,
    )
    response.set_cookie(
        VKID_FLOW_COOKIE,
        flow,
        max_age=cfg.vkid_flow_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/api/auth/vkid",
    )
    return {
        "authorize_url": vkid_client(request).authorization_url(
            state=state_value,
            code_challenge=pkce_challenge(verifier),
        )
    }


@app.get("/api/auth/vkid/callback")
def vkid_callback(
    request: Request,
    flow_cookie: str | None = Cookie(default=None, alias=VKID_FLOW_COOKIE),
) -> RedirectResponse:
    cfg = settings(request)
    if not cfg.vkid_ready or not flow_cookie:
        return auth_redirect("/?auth_error=flow")

    try:
        expected_state, verifier, legal_versions = open_vkid_flow(
            flow_cookie,
            crypto_key=cfg.vkid_flow_crypto_key,
            ttl_seconds=cfg.vkid_flow_ttl_seconds,
        )
        values = callback_values(request)
        code, device_id = validate_vkid_callback_values(values, expected_state)

        owner = vkid_client(request).exchange_code(
            code=code,
            device_id=device_id,
            code_verifier=verifier,
            expected_state=expected_state,
        )
        result = service(request).complete_vkid_login(
            vk_user_id=owner.user_id,
            client_ip=client_ip(request),
            accepted_legal_versions=legal_versions,
        )
    except OwnerAccessDenied:
        return auth_redirect("/?auth_error=owner")
    except (SecurityValueError, VKIDRejected):
        return auth_redirect("/?auth_error=flow")
    except (VKIDUnavailable, LoginUnavailable):
        return auth_redirect("/?auth_error=provider")
    except PermissionError:
        return auth_redirect("/?auth_error=account")

    response = auth_redirect("/?auth=success")
    response.set_cookie(
        SESSION_COOKIE,
        result.session_token,
        max_age=result.expires_in_seconds,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return response


@app.get("/api/me")
def me(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    token = session_token or ""
    user = authenticated_user(request, token)

    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings(request).session_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {
        "public_id": format_public_id(user.public_id),
        "status": user.status,
    }


@app.get("/api/broker/tbank")
def tbank_connection_status(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    connection = broker_service(request).status(user.id)
    return {
        "connected": connection.connected,
        "environment": connection.environment,
        "account_id": connection.account_id,
        "account_name": connection.account_name,
        "verified_at": connection.verified_at,
    }


@app.get("/api/broker/tbank/portfolio")
def tbank_portfolio(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = broker_service(request).portfolio(user.id)
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
        ) from exc
    except (TBankUnavailable, BrokerConnectionError, SecurityValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest portfolio unavailable",
        ) from exc

    return {
        "account_name": snapshot.account_name,
        "environment": snapshot.environment,
        "refreshed_at": snapshot.refreshed_at,
        "portfolio": asdict(snapshot.portfolio),
        "cash": [asdict(item) for item in snapshot.positions.money],
        "blocked_cash": [asdict(item) for item in snapshot.positions.blocked_money],
        "limits_loading_in_progress": snapshot.positions.limits_loading_in_progress,
    }


@app.get("/api/broker/tbank/operations")
def tbank_operations(
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = broker_service(request).operations(
            user.id,
            limit=limit,
            cursor=cursor,
        )
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
        ) from exc
    except (TBankUnavailable, BrokerConnectionError, SecurityValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest operations unavailable",
        ) from exc

    return {
        "account_name": snapshot.account_name,
        "environment": snapshot.environment,
        "refreshed_at": snapshot.refreshed_at,
        "items": [asdict(item) for item in snapshot.operations.items],
        "has_next": snapshot.operations.has_next,
        "next_cursor": snapshot.operations.next_cursor,
    }


@app.get("/api/broker/tbank/instruments/search")
def tbank_instrument_search(
    request: Request,
    q: str = Query(min_length=1, max_length=64),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=400,
            detail="instrument search query is required",
        )
    try:
        instruments = broker_service(request).search_instruments(
            user.id,
            query=query,
            limit=20,
        )
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
        ) from exc
    except (TBankUnavailable, BrokerConnectionError, SecurityValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest instrument search unavailable",
        ) from exc

    return {
        "items": [asdict(item) for item in instruments],
    }


@app.post("/api/broker/tbank/accounts")
def tbank_accounts(
    body: TBankCredentialBody,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    authenticated_user(request, session_token)
    if not body.accept_personal_terms:
        raise HTTPException(
            status_code=400,
            detail="broker terms acknowledgment required",
        )
    try:
        accounts = broker_service(request).preview_accounts(
            credential=body.credential,
            environment=body.environment,
        )
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=400, detail="T-Invest token rejected") from exc
    except TBankUnavailable as exc:
        raise HTTPException(status_code=503, detail="T-Invest API unavailable") from exc

    return {
        "accounts": [
            {
                "id": account.id,
                "name": account.name,
                "type": account.type,
                "status": account.status,
            }
            for account in accounts
        ]
    }


@app.put("/api/broker/tbank")
def connect_tbank(
    body: TBankConnectBody,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    if not body.accept_personal_terms:
        raise HTTPException(
            status_code=400,
            detail="broker terms acknowledgment required",
        )
    try:
        connection = broker_service(request).connect(
            user_id=user.id,
            credential=body.credential,
            environment=body.environment,
            account_id=body.account_id,
            terms_version=settings(request).terms_version,
        )
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=400, detail="T-Invest token rejected") from exc
    except BrokerAccountNotAccessible as exc:
        raise HTTPException(
            status_code=400,
            detail="T-Invest account is not accessible",
        ) from exc
    except TBankUnavailable as exc:
        raise HTTPException(status_code=503, detail="T-Invest API unavailable") from exc
    except SecurityValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="broker credential storage unavailable",
        ) from exc

    return {
        "connected": connection.connected,
        "environment": connection.environment,
        "account_id": connection.account_id,
        "account_name": connection.account_name,
        "verified_at": connection.verified_at,
    }


@app.delete("/api/broker/tbank", status_code=204)
def disconnect_tbank(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    broker_service(request).disconnect(user.id)
    response.status_code = 204
    return response


@app.post("/api/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    service(request).logout(session_token or "")
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.status_code = 204
    return response
