"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, cast
from uuid import UUID

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from .broker import BrokerAccountNotAccessible, BrokerService
from .config import Settings, load_settings
from .db import Database, UserRecord
from .security import SecurityValueError, format_public_id
from .service import (
    AuthService,
    InvalidChallenge,
    OwnerAccessDenied,
    RateLimited,
    RegistrationClosed,
)
from .sms import SmsDeliveryError, build_sms_provider
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable

SESSION_COOKIE = "omnicio_session"
CANONICAL_ORIGIN = "https://omnicio.ru"


class RequestCodeBody(BaseModel):
    phone: str = Field(min_length=11, max_length=12)
    accept_privacy: bool
    accept_personal_data: bool
    accept_terms: bool
    confirm_age_18: bool


class VerifyCodeBody(BaseModel):
    challenge_id: UUID
    code: str = Field(min_length=6, max_length=6)


class TBankCredentialBody(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)
    environment: Literal["prod", "sandbox"] = "prod"


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = load_settings()
    database = Database(cfg.database_url)
    database.open()
    sms = build_sms_provider(
        cfg.sms_provider,
        login=cfg.sms_login,
        token=cfg.sms_token,
        sender=cfg.sms_sender,
    )
    app.state.settings = cfg
    app.state.database = database
    app.state.auth_service = AuthService(cfg, database, sms)
    app.state.broker_service = BrokerService(
        database,
        credential_key=cfg.broker_token_crypto_key,
        tbank=TBankInvestClient(),
    )
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
        "registration_enabled": False,
        "owner_login_enabled": cfg.owner_login_ready,
        "phone_format": "+79XXXXXXXXX",
        "legal_versions": {
            "privacy_policy": cfg.privacy_version,
            "personal_data_consent": cfg.consent_version,
            "terms": cfg.terms_version,
        },
    }


@app.post("/api/auth/request-code")
def request_code(body: RequestCodeBody, request: Request) -> dict[str, object]:
    require_same_origin(request)
    try:
        issued = service(request).issue_challenge(
            phone_raw=body.phone,
            client_ip=client_ip(request),
            accepted_privacy=body.accept_privacy,
            accepted_personal_data=body.accept_personal_data,
            accepted_terms=body.accept_terms,
            confirmed_age_18=body.confirm_age_18,
        )
    except SecurityValueError as exc:
        raise HTTPException(status_code=400, detail="invalid phone format") from exc
    except OwnerAccessDenied as exc:
        raise HTTPException(status_code=403, detail="owner access required") from exc
    except RateLimited as exc:
        raise HTTPException(status_code=429, detail="try again later") from exc
    except RegistrationClosed as exc:
        raise HTTPException(status_code=503, detail="registration unavailable") from exc
    except SmsDeliveryError as exc:
        raise HTTPException(status_code=503, detail="SMS delivery unavailable") from exc

    return {
        "challenge_id": str(issued.challenge_id),
        "expires_in": issued.expires_in_seconds,
    }


@app.post("/api/auth/verify")
def verify_code(
    body: VerifyCodeBody,
    request: Request,
    response: Response,
) -> dict[str, object]:
    require_same_origin(request)
    try:
        result = service(request).verify_challenge(
            challenge_id=body.challenge_id,
            code=body.code,
            client_ip=client_ip(request),
        )
    except (InvalidChallenge, OwnerAccessDenied) as exc:
        raise HTTPException(status_code=400, detail="invalid or expired code") from exc
    except RegistrationClosed as exc:
        raise HTTPException(status_code=503, detail="registration unavailable") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="account unavailable") from exc

    response.set_cookie(
        SESSION_COOKIE,
        result.session_token,
        max_age=result.expires_in_seconds,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return {
        "authenticated": True,
        "created": result.created,
        "public_id": result.public_id,
    }


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


@app.post("/api/broker/tbank/accounts")
def tbank_accounts(
    body: TBankCredentialBody,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    authenticated_user(request, session_token)
    try:
        accounts = broker_service(request).preview_accounts(
            credential=body.credential,
            environment=body.environment,
        )
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=400,
            detail="T-Invest token rejected",
        ) from exc
    except TBankUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest API unavailable",
        ) from exc

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
    try:
        connection = broker_service(request).connect(
            user_id=user.id,
            credential=body.credential,
            environment=body.environment,
            account_id=body.account_id,
        )
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=400,
            detail="T-Invest token rejected",
        ) from exc
    except BrokerAccountNotAccessible as exc:
        raise HTTPException(
            status_code=400,
            detail="T-Invest account is not accessible",
        ) from exc
    except TBankUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest API unavailable",
        ) from exc
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
