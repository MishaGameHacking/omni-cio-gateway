"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from .config import Settings, load_settings
from .db import Database
from .security import SecurityValueError, format_public_id
from .service import AuthService, InvalidChallenge, RateLimited, RegistrationClosed
from .sms import SmsDeliveryError, build_sms_provider

SESSION_COOKIE = "omnicio_session"
CANONICAL_ORIGIN = "https://omnicio.ru"


class RequestCodeBody(BaseModel):
    phone: str = Field(min_length=12, max_length=12)
    accept_privacy: bool
    accept_personal_data: bool
    accept_terms: bool
    confirm_age_18: bool


class VerifyCodeBody(BaseModel):
    challenge_id: UUID
    code: str = Field(min_length=6, max_length=6)


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = load_settings()
    database = Database(cfg.database_url)
    database.open()
    sms = build_sms_provider(
        cfg.sms_provider,
        token=cfg.sms_token,
        sender=cfg.sms_sender,
    )
    app.state.settings = cfg
    app.state.database = database
    app.state.auth_service = AuthService(cfg, database, sms)
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
        "registration_enabled": cfg.registration_ready,
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
    except InvalidChallenge as exc:
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
    user = service(request).refresh_session(token)
    if user is None:
        raise HTTPException(status_code=401, detail="authentication required")

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
