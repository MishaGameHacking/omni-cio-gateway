"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .assistant import (
    AssistantBusy,
    AssistantClient,
    AssistantNotConfigured,
    AssistantUnavailable,
    portfolio_context,
)
from .broker import (
    BrokerAccountNotAccessible,
    BrokerAssessmentBusy,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .cbr import CBRClient, CBRUnavailable
from .config import Settings, load_settings
from .db import ActiveLiveExecutionError, BrokerConnectionConflict, Database, UserRecord
from .execution_service import ExecutionServiceError, PortfolioExecutionService
from .execution_store import (
    ExecutionLedgerError,
    ExecutionLegRecord,
    ExecutionRunRecord,
    ExecutionStore,
    LiveExecutionMandateRecord,
)
from .freshness import PORTFOLIO_MAX_AGE, describe_freshness
from .instrument_facts import instrument_facts
from .market import MarketService
from .news import NewsClient, NewsUnavailable
from .observer import PortfolioRefreshBusy, PortfolioRefreshCoordinator
from .portfolio import PortfolioAnalysisError
from .portfolio_store import (
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioStore,
    SettingsVersionConflict,
)
from .proposals import (
    proposal_payload,
)
from .recovery import recovery_status
from .security import (
    OAuthFlow,
    SecurityValueError,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_oauth_flow,
    pkce_challenge,
    seal_oauth_flow,
    session_digest,
)
from .service import (
    AccountDeletionRejected,
    AuthService,
    LoginSucceeded,
    LoginUnavailable,
    RegistrationCapacityReached,
    RegistrationClosed,
)
from .strategy import strategy_catalog, validate_selection
from .strategy_service import current_account_assessment, strategy_research
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable
from .tid import TIDClient, TIDRejected, TIDUnavailable
from .vkid import VKIDClient, VKIDRejected, VKIDUnavailable
from .workspace_store import WorkspaceNotFound, WorkspaceStore

SESSION_COOKIE = "omnicio_session"
VKID_FLOW_COOKIE = "omnicio_vkid_flow"
TID_FLOW_COOKIE = "omnicio_tid_flow"
CANONICAL_ORIGIN = "https://omnicio.ru"
VKID_CALLBACK = f"{CANONICAL_ORIGIN}/api/auth/vkid/callback"
TID_CALLBACK = f"{CANONICAL_ORIGIN}/api/auth/tid/callback"
INVALID_VKID_CALLBACK = "VK ID callback payload is invalid"
_TBANK_CREDENTIAL_REJECTED_DETAIL = "stored T-Invest credential was rejected"
_UPDATED_LEGAL_CONSENT_DETAIL = "updated_legal_consent_required"
_TBANK_NOT_CONNECTED_DETAIL = "T-Invest is not connected"
_PRIVATE_NO_STORE = "private, no-store"
_PUBLIC_ID_PATTERN = r"^[0-9]{9}$"
_PROFILE_CONTEXT_HEADER = "X-Omnicio-Profile"
_PROFILE_CONTEXT_CONFLICT_DESCRIPTION = "Viewed profile is missing or differs from the session"
_PROFILE_CHANGED_EVENT = 'event: status\ndata: {"state":"profile_context_changed"}\n\n'
logger = logging.getLogger(__name__)


class StrictRequestBody(BaseModel):
    """Reject ambiguous client payloads instead of silently ignoring typos."""

    model_config = ConfigDict(extra="forbid")


class StartOAuthBody(StrictRequestBody):
    accept_privacy: bool
    accept_personal_data: bool
    accept_terms: bool
    confirm_age_18: bool
    link_current_account: bool = False


class TBankCredentialBody(StrictRequestBody):
    credential: str = Field(min_length=20, max_length=4096)
    environment: Literal["prod", "sandbox"] = "prod"
    accept_personal_terms: bool


class TBankConnectBody(TBankCredentialBody):
    account_id: str = Field(min_length=1, max_length=128)


class DeleteAccountBody(StrictRequestBody):
    confirm_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    confirm_irreversible: bool


class StrategyDraftBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    expected_version: int = Field(ge=0, le=2_147_483_647, strict=True)
    intent: Literal["select", "edit"]
    document: dict[str, Any]


class StrategyAccountBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    expected_version: int = Field(ge=1, le=2_147_483_647, strict=True)


class StrategyResearchBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    expected_version: int = Field(ge=1, le=2_147_483_647, strict=True)
    from_at: datetime
    to_at: datetime
    commission_bps: Decimal = Field(ge=0, le=1000, allow_inf_nan=False)
    slippage_bps: Decimal = Field(ge=0, le=1000, allow_inf_nan=False)
    initial_capital_rub: Decimal = Field(
        gt=0, le=1_000_000_000_000, max_digits=24, decimal_places=8, allow_inf_nan=False,
    )


class WorkspaceRefreshBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)


class WorkspaceDocumentBody(StrictRequestBody):
    document: dict[str, Any]


class WorkspaceVersionBody(StrictRequestBody):
    expected_version: int = Field(ge=0, le=2_147_483_647, strict=True)


class WorkspaceSaveBody(WorkspaceDocumentBody, WorkspaceVersionBody):
    pass


class EventsReadBody(StrictRequestBody):
    ids: list[str] = Field(min_length=1, max_length=100)
    read: bool = True


class AssistantHistoryItem(StrictRequestBody):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=16000)


class AssistantMessageBody(StrictRequestBody):
    message: str = Field(min_length=1, max_length=4000)
    context: Literal["general", "portfolio"] = "general"
    history: list[AssistantHistoryItem] = Field(default_factory=list, max_length=20)


def client_ip(request: Request) -> str:
    direct = request.client.host if request.client else ""
    candidate = direct
    if direct in {"127.0.0.1", "::1"}:
        # Nginx overwrites X-Real-IP with the TCP peer address. Do not trust the
        # first X-Forwarded-For element because a client can supply it itself.
        candidate = request.headers.get("x-real-ip", "").strip()

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin != CANONICAL_ORIGIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="origin rejected")


def service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


def settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def broker_service(request: Request) -> BrokerService:
    return cast(BrokerService, request.app.state.broker_service)


def market_service(request: Request) -> MarketService:
    return cast(MarketService, request.app.state.market_service)


def portfolio_store(request: Request) -> PortfolioStore:
    return cast(PortfolioStore, request.app.state.portfolio_store)


def workspace_store(request: Request) -> WorkspaceStore:
    return cast(WorkspaceStore, request.app.state.workspace_store)


def portfolio_refresh(request: Request) -> PortfolioRefreshCoordinator:
    return cast(PortfolioRefreshCoordinator, request.app.state.portfolio_refresh)


def execution_store(request: Request) -> ExecutionStore:
    return cast(ExecutionStore, request.app.state.execution_store)


def execution_service(request: Request) -> PortfolioExecutionService:
    return cast(
        PortfolioExecutionService,
        request.app.state.execution_service,
    )


def vkid_client(request: Request) -> VKIDClient:
    return cast(VKIDClient, request.app.state.vkid_client)


def _require_profile_context(user: UserRecord, expected_public_id: str | None) -> None:
    # A precondition on the viewed profile, never a tenant selector or credential.
    if expected_public_id is None:
        raise HTTPException(status_code=409, detail="profile_context_required")
    if expected_public_id != format_public_id(user.public_id):
        raise HTTPException(status_code=409, detail="profile_context_changed")


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
    expected = request.headers.get(_PROFILE_CONTEXT_HEADER)
    if expected is not None or request.method not in {"GET", "HEAD", "OPTIONS"}:
        _require_profile_context(user, expected)
    return user


def callback_values(request: Request) -> dict[str, str]:
    payload_raw = request.query_params.get("payload")
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError as exc:
            raise VKIDRejected(INVALID_VKID_CALLBACK) from exc
        if not isinstance(payload, dict):
            raise VKIDRejected(INVALID_VKID_CALLBACK)
        values: dict[str, str] = {}
        for key in ("code", "state", "device_id", "error"):
            value = payload.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                raise VKIDRejected(INVALID_VKID_CALLBACK)
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


def auth_redirect(path: str, provider: str = "vkid") -> RedirectResponse:
    response = RedirectResponse(path, status_code=status.HTTP_303_SEE_OTHER)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.delete_cookie(
        VKID_FLOW_COOKIE if provider == "vkid" else TID_FLOW_COOKIE,
        path=f"/api/auth/{provider}", secure=True, httponly=True, samesite="lax",
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
    app.state.portfolio_store = PortfolioStore(database)
    app.state.workspace_store = WorkspaceStore(database)
    app.state.assistant_client = AssistantClient(
        base_url=cfg.assistant_base_url, model=cfg.assistant_model,
        api_key=cfg.assistant_api_key,
    )
    app.state.news_client = NewsClient()
    app.state.tid_client = TIDClient(
        client_id=cfg.tid_client_id, client_secret=cfg.tid_client_secret,
        redirect_uri=TID_CALLBACK, pkce_enabled=cfg.tid_pkce_enabled,
    )
    execution_ledger = ExecutionStore(database)
    app.state.execution_store = execution_ledger
    app.state.vkid_client = VKIDClient(
        app_id=cfg.vkid_app_id,
        redirect_uri=VKID_CALLBACK,
    )
    broker = BrokerService(
        database,
        credential_key=cfg.broker_token_crypto_key,
        tbank=TBankInvestClient(),
    )
    app.state.broker_service = broker
    app.state.execution_service = PortfolioExecutionService(
        store=execution_ledger,
        broker=broker,
    )
    app.state.market_service = MarketService(
        broker=broker,
        cbr=CBRClient(),
    )
    refresh = PortfolioRefreshCoordinator(
        app.state.portfolio_store, broker,
        legal_versions=app.state.auth_service.legal_versions(),
    )
    app.state.portfolio_refresh = refresh
    try:
        refresh.start()
        yield
    finally:
        try:
            refresh.close()
        finally:
            database.close()


app = FastAPI(
    title="OmniCIO Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.exception_handler(SettingsVersionConflict)
async def settings_conflict_response(
    request: Request, exc: SettingsVersionConflict,
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "settings_version_conflict"})


@app.exception_handler(WorkspaceNotFound)
async def workspace_not_found_response(
    request: Request, exc: WorkspaceNotFound,
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "workspace_item_not_found"})


@app.middleware("http")
async def private_request_boundary(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Give every API result a server-owned trace and prevent private caching."""
    request_id = uuid4().hex
    request.state.request_id = request_id
    error_type = ""
    try:
        response = await call_next(request)
    except Exception as exc:
        # Exception text/tracebacks may contain provider credentials or SQL data.
        # Record only a safe class and a generated reference; never request input.
        error_type = type(exc).__name__
        response = JSONResponse(
            status_code=500,
            content={
                "detail": "Сервис не смог завершить запрос. Проверьте состояние перед повтором.",
                "request_id": request_id,
            },
        )
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    if response.status_code >= 400:
        route = getattr(request.scope.get("route"), "path", "unmatched")
        logger.warning(
            "request_failed request_id=%s route=%s status=%s error_type=%s",
            request_id, route, response.status_code, error_type,
        )
    return response


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", responses={503: {"description": "Database unavailable"}})
def ready(request: Request) -> dict[str, str]:
    database: Database = request.app.state.database
    if not database.healthcheck():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}


@app.get("/api/auth/config")
def auth_config(request: Request) -> dict[str, object]:
    cfg = settings(request)
    return {
        "mode": cfg.access_mode,
        "auth_provider": "vkid",
        "auth_providers": ["tid", "vkid"],
        "registration_enabled": cfg.registration_enabled,
        "registration_max_users": cfg.registration_max_users,
        "login_enabled": cfg.login_ready,
        "vkid_enabled": cfg.vkid_ready,
        "tid_enabled": cfg.tid_ready,
        "tid_configured": bool(cfg.tid_client_id and cfg.tid_client_secret),
        "legal_versions": service(request).legal_versions(),
    }


def _start_oauth(
    provider: str, body: StartOAuthBody, request: Request, response: Response,
    session_token: str | None,
) -> dict[str, str]:
    require_same_origin(request)
    cfg = settings(request)
    ready = cfg.vkid_ready if provider == "vkid" else cfg.tid_ready
    if not ready:
        raise HTTPException(status_code=503, detail=f"{provider}_not_configured")
    if not (body.accept_privacy and body.accept_personal_data and body.accept_terms):
        raise HTTPException(status_code=400, detail="legal acknowledgments are required")
    if not body.confirm_age_18:
        raise HTTPException(status_code=400, detail="user must confirm age 18+")
    user = authenticated_user(request, session_token) if body.link_current_account else None
    state_value, verifier = generate_oauth_state(), generate_pkce_verifier()
    flow = seal_oauth_flow(
        state=state_value, code_verifier=verifier,
        legal_versions=service(request).legal_versions(),
        crypto_key=cfg.vkid_flow_crypto_key, provider=provider,
        link_user_id=str(user.id) if user else None,
        link_session_digest=session_digest(session_token or "").hex() if user else None,
    )
    response.set_cookie(
        VKID_FLOW_COOKIE if provider == "vkid" else TID_FLOW_COOKIE,
        flow, max_age=cfg.vkid_flow_ttl_seconds, httponly=True, secure=True,
        samesite="lax", path=f"/api/auth/{provider}",
    )
    client = (vkid_client(request) if provider == "vkid" else
              cast(TIDClient, request.app.state.tid_client))
    return {"authorize_url": client.authorization_url(
        state=state_value, code_challenge=pkce_challenge(verifier),
    )}


@app.post("/api/auth/vkid/start", responses={
    400: {"description": "Required legal acknowledgments are missing"},
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    503: {"description": "VK ID login is not configured"},
})
def start_vkid(
    body: StartOAuthBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str]:
    return _start_oauth("vkid", body, request, response, session_token)


@app.post("/api/auth/tid/start", responses={
    400: {"description": "Required legal acknowledgments are missing"},
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    503: {"description": "T-ID login is not configured"},
})
def start_tid(
    body: StartOAuthBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str]:
    return _start_oauth("tid", body, request, response, session_token)


def _oauth_callback_values(
    provider: str, request: Request, flow: OAuthFlow,
) -> tuple[str, str]:
    values = callback_values(request)
    if provider == "vkid":
        return validate_vkid_callback_values(values, flow.state)
    if any(len(request.query_params.getlist(k)) != 1 for k in ("code", "state")):
        raise TIDRejected("tid_callback_ambiguous")
    code = values.get("code", "")
    if (values.get("error") or not code or len(code) > 4096
            or not hmac.compare_digest(
                values.get("state", "").encode(), flow.state.encode(),
            )):
        raise TIDRejected("tid_callback_invalid")
    return code, ""


def _oauth_link_user(
    request: Request, flow: OAuthFlow, session_token: str | None,
) -> UserRecord | None:
    if flow.link_user_id is None:
        return None
    linked_user = authenticated_user(request, session_token)
    if (str(linked_user.id) != flow.link_user_id
            or not hmac.compare_digest(
                session_digest(session_token or "").hex(), flow.link_session_digest or "",
            )):
        raise PermissionError("oauth_link_session_changed")
    return linked_user


def _exchange_oauth_identity(
    provider: str, request: Request, flow: OAuthFlow, code: str, device_id: str,
    linked_user: UserRecord | None,
) -> LoginSucceeded:
    auth = service(request)
    link_user_id = linked_user.id if linked_user else None
    link_digest = bytes.fromhex(flow.link_session_digest) if flow.link_session_digest else None
    if provider == "vkid":
        identity = vkid_client(request).exchange_code(
            code=code, device_id=device_id,
            code_verifier=flow.code_verifier, expected_state=flow.state,
        )
        return auth.complete_vkid_login(
            vk_user_id=identity.user_id, client_ip=client_ip(request),
            accepted_legal_versions=flow.legal_versions,
            link_user_id=link_user_id, link_session_digest=link_digest,
        )
    tid: TIDClient = request.app.state.tid_client
    tid_identity = tid.exchange_code(code=code, code_verifier=flow.code_verifier)
    return auth.complete_tid_login(
        tid_subject=tid_identity.subject, client_ip=client_ip(request),
        accepted_legal_versions=flow.legal_versions,
        link_user_id=link_user_id, link_session_digest=link_digest,
    )


def _oauth_callback(
    provider: str, request: Request, flow_cookie: str | None, session_token: str | None,
) -> RedirectResponse:
    cfg = settings(request)
    provider_ready = cfg.vkid_ready if provider == "vkid" else cfg.tid_ready
    if not provider_ready or not flow_cookie or len(flow_cookie) > 8192:
        return auth_redirect("/?auth_error=flow", provider)
    try:
        flow = open_oauth_flow(
            flow_cookie, crypto_key=cfg.vkid_flow_crypto_key,
            ttl_seconds=cfg.vkid_flow_ttl_seconds, provider=provider,
        )
        code, device_id = _oauth_callback_values(provider, request, flow)
        linked_user = _oauth_link_user(request, flow, session_token)
        database: Database = request.app.state.database
        if not database.claim_oauth_flow(
            session_digest(flow.state), provider, cfg.vkid_flow_ttl_seconds,
        ):
            raise SecurityValueError("oauth_state_already_used")
        result = _exchange_oauth_identity(provider, request, flow, code, device_id, linked_user)
    except RegistrationClosed:
        return auth_redirect("/?auth_error=registration", provider)
    except RegistrationCapacityReached:
        return auth_redirect("/?auth_error=capacity", provider)
    except (SecurityValueError, VKIDRejected, TIDRejected):
        return auth_redirect("/?auth_error=flow", provider)
    except (VKIDUnavailable, TIDUnavailable, LoginUnavailable):
        return auth_redirect("/?auth_error=provider", provider)
    except (PermissionError, HTTPException):
        return auth_redirect("/?auth_error=account", provider)
    response = auth_redirect("/?auth=success", provider)
    response.set_cookie(
        SESSION_COOKIE, result.session_token, max_age=result.expires_in_seconds,
        httponly=True, secure=True, samesite="lax", path="/",
    )
    return response


@app.get("/api/auth/vkid/callback", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def vkid_callback(
    request: Request,
    flow_cookie: str | None = Cookie(default=None, alias=VKID_FLOW_COOKIE),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> RedirectResponse:
    return _oauth_callback("vkid", request, flow_cookie, session_token)


@app.get("/api/auth/tid/callback", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def tid_callback(
    request: Request,
    flow_cookie: str | None = Cookie(default=None, alias=TID_FLOW_COOKIE),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> RedirectResponse:
    return _oauth_callback("tid", request, flow_cookie, session_token)


@app.get(
    "/api/me",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
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
        samesite="lax",
        path="/",
    )
    return {
        "public_id": format_public_id(user.public_id),
        "status": user.status,
        "role": user.role,
    }


@app.get("/api/auth/identities", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def auth_identities(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    database: Database = request.app.state.database
    cfg = settings(request)
    return {
        "providers": database.identity_providers(user.id),
        "available_providers": {"tid": cfg.tid_ready, "vkid": cfg.vkid_ready},
    }


@app.get("/api/assistant/status", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def assistant_status(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    authenticated_user(request, session_token)
    assistant: AssistantClient = request.app.state.assistant_client
    return assistant.status()


@app.post("/api/assistant/messages", responses={
    409: {"description": "Profile or portfolio context changed during the request"},
    422: {"description": "Assistant message or history is invalid"},
    429: {"description": "The bounded assistant worker is busy"},
    502: {"description": "The configured model did not return a valid response"},
    503: {"description": "The assistant has not been configured"},
})
def assistant_message(
    body: AssistantMessageBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    assistant: AssistantClient = request.app.state.assistant_client
    snapshot = workspace_store(request).dashboard(user.id) if body.context == "portfolio" else None
    evidence = portfolio_context(snapshot) if snapshot is not None else None
    try:
        result = assistant.chat(
            message=body.message,
            history=[item.model_dump() for item in body.history], context=evidence,
        )
    except AssistantNotConfigured as exc:
        raise HTTPException(status_code=503, detail="assistant_not_configured") from exc
    except AssistantBusy as exc:
        raise HTTPException(
            status_code=429, detail="assistant_busy", headers={"Retry-After": "10"},
        ) from exc
    except AssistantUnavailable as exc:
        raise HTTPException(status_code=502, detail="assistant_unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="assistant_message_invalid") from exc
    current = authenticated_user(request, session_token)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    if snapshot is not None:
        latest = broker_service(request).status(user.id)
        previous = snapshot["connection"]
        if (latest.connected != previous["connected"]
                or latest.account_id != previous.get("account_id")
                or latest.environment != previous.get("environment")):
            raise HTTPException(status_code=409, detail="assistant_context_changed")
    return result


@app.get("/api/workspace", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    422: {"description": "Portfolio history period is invalid"},
})
def get_workspace(
    request: Request,
    history_period: Literal["1d", "1w", "1m", "3m", "1y", "all"] = Query(default="all"),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    payload = workspace_store(request).dashboard(user.id, history_period=history_period)
    return _workspace_result(request, session_token, user, payload)


@app.get(
    "/api/workspace/refresh",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def get_workspace_refresh(
    request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    payload = portfolio_refresh(request).status(user.id)
    if authenticated_user(request, session_token).id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {**payload, "public_id": format_public_id(user.public_id)}


@app.post(
    "/api/workspace/refresh",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        429: {"description": "Refresh admission slots are temporarily occupied"},
    },
)
def request_workspace_refresh(
    body: WorkspaceRefreshBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    try:
        payload = portfolio_refresh(request).request(user.id)
    except PortfolioRefreshBusy as exc:
        raise HTTPException(
            status_code=429, detail="portfolio_refresh_busy", headers={"Retry-After": "2"},
        ) from exc
    current = _settings_editor_user(request, session_token, body.expected_public_id)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {**payload, "public_id": format_public_id(user.public_id)}


@app.get("/api/preferences", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def get_preferences(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    payload = workspace_store(request).preferences(user.id)
    return _workspace_result(request, session_token, user, payload)


def _workspace_editor(request: Request, session_token: str | None) -> UserRecord:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    return user


def _workspace_result(
    request: Request, session_token: str | None, user: UserRecord,
    payload: dict[str, Any], *, write: bool = False,
) -> dict[str, Any]:
    # A write may already have committed. Revalidate before disclosing its
    # result; an expired session must sign in and read back the actual version.
    current = (
        _workspace_editor(request, session_token)
        if write else authenticated_user(request, session_token)
    )
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    return payload


@app.put("/api/preferences", responses={
    409: {"description": "Preferences version or current legal consent changed"},
    422: {"description": "Preferences document is invalid"},
})
def save_preferences(
    body: WorkspaceSaveBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        payload = workspace_store(request).save_preferences(
            user.id, body.document, expected_version=body.expected_version,
        )
    except SettingsVersionConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="workspace_document_invalid") from exc
    return _workspace_result(request, session_token, user, payload, write=True)


@app.get("/api/goals", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def get_goals(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    payload = workspace_store(request).goals(user.id)
    return _workspace_result(request, session_token, user, payload)


@app.post("/api/goals", status_code=201, responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    422: {"description": "Goal document or allocation is invalid"},
})
def create_goal(
    body: WorkspaceDocumentBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        payload = workspace_store(request).create_goal(user.id, body.document)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="goal_document_invalid") from exc
    return _workspace_result(request, session_token, user, payload, write=True)


@app.put("/api/goals/{goal_id}", responses={
    404: {"description": "Goal does not exist in the current profile"},
    409: {"description": "Goal version or current legal consent changed"},
    422: {"description": "Goal document or allocation is invalid"},
})
def update_goal(
    goal_id: UUID, body: WorkspaceSaveBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        payload = workspace_store(request).update_goal(
            user.id, goal_id, body.document, expected_version=body.expected_version,
        )
    except SettingsVersionConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="goal_document_invalid") from exc
    return _workspace_result(request, session_token, user, payload, write=True)


@app.delete("/api/goals/{goal_id}", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def delete_goal(
    goal_id: UUID, body: WorkspaceVersionBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, bool]:
    user = _workspace_editor(request, session_token)
    payload = {"deleted": workspace_store(request).delete_goal(
        user.id, goal_id, expected_version=body.expected_version,
    )}
    return _workspace_result(request, session_token, user, payload, write=True)


@app.get("/api/events", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
})
def get_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
    category: Literal["all", "portfolio", "payments", "goals", "system"] = "all",
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    payload = workspace_store(request).events(
        user.id, limit=limit, unread_only=unread_only, category=category,
    )
    return _workspace_result(request, session_token, user, payload)


@app.post("/api/events/read", responses={
    409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    422: {"description": "Event identifiers are invalid"},
})
def mark_events_read(
    body: EventsReadBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        payload = workspace_store(request).mark_events_read(user.id, body.ids, read=body.read)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="event_ids_invalid") from exc
    return _workspace_result(request, session_token, user, payload, write=True)


@app.get(
    "/api/me/activity",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def account_activity(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    database = cast(Database, request.app.state.database)
    return {"events": database.recent_activity(user.id, limit=limit)}


@app.get(
    "/api/system/recovery",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def system_recovery(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    authenticated_user(request, session_token)
    return recovery_status()


@app.get("/api/public/news", responses={
    503: {"description": "Public news sources are temporarily unavailable"},
})
def public_news(request: Request) -> dict[str, Any]:
    client: NewsClient = request.app.state.news_client
    try:
        return client.headlines()
    except NewsUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="news_source_unavailable", headers={"Retry-After": "60"},
        ) from exc


@app.get(
    "/api/public/market-reference",
    responses={503: {"description": "Public reference refresh is busy"}},
)
def public_market_reference(
    request: Request,
    response: Response,
    currency: Literal["USD", "EUR", "CNY"] = Query(default="USD"),
    period: Literal["1m", "3m", "1y"] = Query(default="1m"),
) -> dict[str, object]:
    # Deliberately no session/broker access. Browser caching cannot turn a failed
    # refresh into an apparently new quote; the source adapter owns bounded cache.
    response.headers["Cache-Control"] = "no-store"
    try:
        return market_service(request).public_reference(currency, period)
    except CBRUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="public_reference_busy", headers={"Retry-After": "30"},
        ) from exc


@app.get(
    "/api/market/cbr-indicators",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        401: {"description": "Authenticated session required"},
        503: {"description": "Bank of Russia indicators are temporarily unavailable"},
    },
)
def cbr_market_indicators(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    authenticated_user(request, session_token)
    try:
        snapshot = market_service(request).cbr_indicators()
    except CBRUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Bank of Russia indicators unavailable",
        ) from exc
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return asdict(snapshot)


@app.get(
    "/api/market/usd-rub",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": "T-Invest connection requires attention"},
        503: {"description": "USD/RUB market data is temporarily unavailable"},
    },
)
def usd_rub_market_snapshot(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = market_service(request).usd_rub(user.id)
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail=_TBANK_CREDENTIAL_REJECTED_DETAIL,
        ) from exc
    except (TBankUnavailable, BrokerConnectionError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="USD/RUB market quote unavailable",
        ) from exc
    return asdict(snapshot)


async def _stream_session_current(
    request: Request, session_token: str | None, user_id: UUID,
) -> bool:
    user = await asyncio.to_thread(service(request).refresh_session, session_token or "")
    return user is not None and user.id == user_id


async def _usd_rub_market_events(
    request: Request,
    market: MarketService,
    user_id: UUID,
    session_token: str | None,
) -> AsyncIterator[str]:
    retry_delay = 5
    yield "retry: 5000\n\n"
    while not await request.is_disconnected():
        if not await _stream_session_current(request, session_token, user_id):
            yield _PROFILE_CHANGED_EVENT
            break

        payload: dict[str, object]
        try:
            snapshot = await asyncio.to_thread(market.usd_rub, user_id)
        except BrokerNotConnected:
            payload = {"state": "disconnected"}
            event = "status"
            delay = 15
            retry_delay = 5
        except TBankTokenRejected:
            payload = {"state": "reconnect"}
            event = "status"
            delay = 30
            retry_delay = 5
        except (TBankUnavailable, BrokerConnectionError, ValueError):
            payload = {"state": "unavailable"}
            event = "status"
            delay = retry_delay
            retry_delay = min(retry_delay * 2, 30)
        else:
            payload = asdict(snapshot)
            event = "quote"
            delay = 5
            retry_delay = 5

        if not await _stream_session_current(request, session_token, user_id):
            yield _PROFILE_CHANGED_EVENT
            break
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        yield f"event: {event}\ndata: {data}\n\n"
        await asyncio.sleep(delay)


@app.get(
    "/api/market/usd-rub/stream",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
async def usd_rub_market_stream(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    user = authenticated_user(request, session_token)
    _require_profile_context(user, request.query_params.get("profile_context"))
    market = market_service(request)
    return StreamingResponse(
        _usd_rub_market_events(request, market, user.id, session_token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@app.get(
    "/api/market/instruments/{instrument_uid}",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": "T-Invest connection requires attention"},
        422: {"description": "Instrument or period is invalid"},
        503: {"description": "Instrument market data is temporarily unavailable"},
    },
)
def instrument_market_snapshot(
    instrument_uid: str,
    request: Request,
    response: Response,
    period: Literal["1d", "1w", "1m", "3m", "1y", "all"] = Query(default="1m"),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = market_service(request).instrument_snapshot(
            user.id,
            instrument_uid,
            period=period,
        )
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
        ) from exc
    except SecurityValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="instrument market data unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except (TBankUnavailable, BrokerConnectionError) as exc:
        raise HTTPException(
            status_code=503,
            detail="instrument market data unavailable",
        ) from exc
    current = authenticated_user(request, session_token)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return asdict(snapshot)


@app.get(
    "/api/market/instruments/{instrument_uid}/facts",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": "Profile or T-Invest connection requires attention"},
        422: {"description": "Instrument UID is invalid"},
        503: {"description": "Instrument facts are temporarily unavailable"},
    },
)
def get_instrument_facts(
    instrument_uid: str, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    try:
        payload = instrument_facts(
            user_id=user.id, instrument_uid=instrument_uid, broker=broker_service(request),
        )
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_CREDENTIAL_REJECTED_DETAIL) from exc
    except SecurityValueError as exc:
        raise HTTPException(status_code=503, detail="instrument_facts_unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="instrument_uid_invalid") from exc
    except (TBankUnavailable, BrokerConnectionError) as exc:
        raise HTTPException(status_code=503, detail="instrument_facts_unavailable") from exc
    current = authenticated_user(request, session_token)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return payload


def _terminal_instrument_market_stream_state(error: Exception) -> str | None:
    state: str | None = None
    if isinstance(error, BrokerNotConnected):
        state = "disconnected"
    elif isinstance(error, TBankTokenRejected):
        state = "reconnect"
    elif isinstance(error, SecurityValueError):
        state = "offline"
    elif isinstance(error, ValueError):
        state = "invalid"
    return state


def _instrument_market_failure_event(
    error: Exception,
    *,
    consecutive_failures: int,
    retry_delay: int,
) -> tuple[dict[str, object], int, int, int, bool]:
    terminal_state = _terminal_instrument_market_stream_state(error)
    if terminal_state is not None:
        return {"state": terminal_state}, 0, 3, 0, True

    failures = consecutive_failures + 1
    if failures >= 6:
        return {"state": "offline"}, 0, retry_delay, failures, True
    return (
        {"state": "unavailable"},
        retry_delay,
        min(retry_delay * 2, 30),
        failures,
        False,
    )


async def _next_instrument_market_event(
    market: MarketService,
    user_id: UUID,
    instrument_uid: str,
    *,
    consecutive_failures: int,
    retry_delay: int,
) -> tuple[str, dict[str, object], int, int, int, bool]:
    try:
        state = await asyncio.to_thread(
            market.instrument_live_state,
            user_id,
            instrument_uid,
        )
    except (
        TBankTokenRejected,
        ValueError,
        TBankUnavailable,
        BrokerConnectionError,
    ) as error:
        payload, delay, next_retry_delay, failures, stop = (
            _instrument_market_failure_event(
                error,
                consecutive_failures=consecutive_failures,
                retry_delay=retry_delay,
            )
        )
        return "status", payload, delay, next_retry_delay, failures, stop
    return "market", asdict(state), 5, 3, 0, False


async def _instrument_market_events(
    request: Request,
    market: MarketService,
    user_id: UUID,
    instrument_uid: str,
    session_token: str | None,
) -> AsyncIterator[str]:
    retry_delay = 3
    consecutive_failures = 0
    yield "retry: 5000\n\n"
    while not await request.is_disconnected():
        if not await _stream_session_current(request, session_token, user_id):
            yield _PROFILE_CHANGED_EVENT
            break
        (
            event,
            payload,
            delay,
            retry_delay,
            consecutive_failures,
            stop_after_event,
        ) = await _next_instrument_market_event(
            market,
            user_id,
            instrument_uid,
            consecutive_failures=consecutive_failures,
            retry_delay=retry_delay,
        )
        if not await _stream_session_current(request, session_token, user_id):
            yield _PROFILE_CHANGED_EVENT
            break
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        yield f"event: {event}\ndata: {data}\n\n"
        if stop_after_event:
            break
        await asyncio.sleep(delay)


@app.get(
    "/api/market/instruments/{instrument_uid}/stream",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    },
)
async def instrument_market_stream(
    instrument_uid: str,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    user = authenticated_user(request, session_token)
    _require_profile_context(user, request.query_params.get("profile_context"))
    market = market_service(request)
    return StreamingResponse(
        _instrument_market_events(request, market, user.id, instrument_uid, session_token),
        media_type="text/event-stream",
        headers={
            "Cache-Control": _PRIVATE_NO_STORE,
            "X-Accel-Buffering": "no",
        },
    )


def _profile_payload(profile: InvestmentProfileRecord) -> dict[str, object]:
    return {
        "version": profile.version,
        "reserve_rub": str(profile.reserve_rub),
        "planned_withdrawal_rub": str(profile.planned_withdrawal_rub),
        "horizon_months": profile.horizon_months,
        "max_drawdown_percent": str(profile.max_drawdown_percent),
        "liquidity_horizon_days": profile.liquidity_horizon_days,
        "allow_below_investment_grade": profile.allow_below_investment_grade,
        "created_at": profile.created_at,
    }


def _balancing_policy_payload(
    policy: BalancingPolicyRecord,
) -> dict[str, object]:
    return {
        "version": policy.version,
        "max_instrument_percent": str(policy.max_instrument_percent),
        "max_sector_percent": str(policy.max_sector_percent),
        "max_issuer_percent": str(policy.max_issuer_percent),
        "max_group_percent": str(policy.max_group_percent),
        "max_share_percent": str(policy.max_share_percent),
        "max_bond_percent": str(policy.max_bond_percent),
        "max_etf_percent": str(policy.max_etf_percent),
        "max_below_grade_percent": str(policy.max_below_grade_percent),
        "max_unknown_percent": str(policy.max_unknown_percent),
        "max_term_months": policy.max_term_months,
        "turnover_budget_percent": str(policy.turnover_budget_percent),
        "max_daily_turnover_participation_percent": str(
            policy.max_daily_turnover_participation_percent
        ),
        "securities_tax_rate_percent": str(policy.securities_tax_rate_percent),
        "uncertainty_haircut_percent": str(policy.uncertainty_haircut_percent),
        "credit_loss_haircut_percent": str(policy.credit_loss_haircut_percent),
        "no_trade_band_percent": str(policy.no_trade_band_percent),
        "min_replace_benefit_rub": str(policy.min_replace_benefit_rub),
        "created_at": policy.created_at,
        "system_constraints": {
            "allowed_asset_classes": ["share", "bond", "etf"],
            "allowed_currencies": ["RUB"],
            "new_buy_risk_states": ["normal"],
        },
    }


@app.get(
    "/api/profile/investment",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def investment_profile(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    profile = portfolio_store(request).current_profile(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "public_id": format_public_id(user.public_id),
        "profile": _profile_payload(profile) if profile is not None else None,
    }


def _settings_editor_user(
    request: Request,
    session_token: str | None,
    expected_public_id: str,
) -> UserRecord:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    database: Database = request.app.state.database
    if not database.has_legal_versions(user.id, service(request).legal_versions()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_UPDATED_LEGAL_CONSENT_DETAIL,
        )
    # This is a stale-page precondition; only the session chooses the tenant.
    if expected_public_id != format_public_id(user.public_id):
        raise HTTPException(status_code=409, detail="settings_owner_conflict")
    return user


@app.get("/api/strategy/catalog")
def get_strategy_catalog(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return strategy_catalog()


@app.get(
    "/api/profile/strategy",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def get_strategy_draft(
    request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"public_id": format_public_id(user.public_id),
            "selection": portfolio_store(request).current_strategy_draft(user.id)}


@app.put(
    "/api/profile/strategy",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        422: {"description": "Invalid strategy document or preset selection"},
    },
)
def save_strategy_draft(
    body: StrategyDraftBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    try:
        document = validate_selection(body.document, intent=body.intent)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    saved = portfolio_store(request).save_strategy_draft(
        user.id, document, expected_version=body.expected_version,
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"public_id": format_public_id(user.public_id), "selection": saved,
            "applied_to_confirmed_policy": False, "broker_execution_enabled": False}


@app.post(
    "/api/profile/strategy/account-assessment",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        429: {"description": "An account assessment is already running or cooling down"},
        503: {"description": "Account evidence is unavailable or not coherent"},
    },
)
def strategy_account_assessment(
    body: StrategyAccountBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    try:
        payload = current_account_assessment(
            user_id=user.id, expected_version=body.expected_version,
            store=portfolio_store(request), broker=broker_service(request),
        )
    except SettingsVersionConflict:
        raise
    except BrokerAssessmentBusy as exc:
        raise HTTPException(
            status_code=429, detail="strategy_assessment_busy", headers={"Retry-After": "10"},
        ) from exc
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_CREDENTIAL_REJECTED_DETAIL) from exc
    except (BrokerConnectionError, TBankUnavailable, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail="strategy_account_evidence_unavailable",
        ) from exc
    # Revocation or logout during upstream I/O must prevent release of the response.
    current = _settings_editor_user(request, session_token, body.expected_public_id)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="strategy_account_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {**payload, "public_id": format_public_id(user.public_id)}


@app.post(
    "/api/profile/strategy/research",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        422: {"description": "Invalid research period or explicit cost assumptions"},
        429: {"description": "Research is already running or cooling down"},
        503: {"description": "Broker evidence unavailable"},
    },
)
def research_strategy(
    body: StrategyResearchBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    try:
        payload = strategy_research(
            user_id=user.id, expected_version=body.expected_version,
            store=portfolio_store(request), broker=broker_service(request),
            from_at=body.from_at, to_at=body.to_at,
            commission_bps=body.commission_bps, slippage_bps=body.slippage_bps,
            initial_capital_rub=body.initial_capital_rub,
        )
    except BrokerAssessmentBusy as exc:
        raise HTTPException(status_code=429, detail="strategy_assessment_busy") from exc
    except SettingsVersionConflict:
        raise
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_CREDENTIAL_REJECTED_DETAIL) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="research_parameters_invalid") from exc
    except (BrokerConnectionError, TBankUnavailable) as exc:
        raise HTTPException(status_code=503, detail="strategy_research_unavailable") from exc
    current = _settings_editor_user(request, session_token, body.expected_public_id)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="strategy_account_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {**payload, "public_id": format_public_id(user.public_id)}


@app.get(
    "/api/profile/balancing",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def balancing_policy(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    policy = portfolio_store(request).current_balancing_policy(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "public_id": format_public_id(user.public_id),
        "policy": _balancing_policy_payload(policy) if policy is not None else None,
    }


@app.get(
    "/api/broker/tbank",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
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


@app.get(
    "/api/broker/tbank/analysis",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": "Broker connection or credential must be checked"},
        503: {"description": "Broker analysis is temporarily unavailable"},
    },
)
def tbank_analysis(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = broker_service(request).analysis(user.id)
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail=_TBANK_CREDENTIAL_REJECTED_DETAIL,
        ) from exc
    except (
        TBankUnavailable,
        BrokerConnectionError,
        PortfolioAnalysisError,
        SecurityValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest analysis unavailable",
        ) from exc

    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        **asdict(snapshot),
        "freshness": asdict(describe_freshness(
            snapshot.refreshed_at,
            max_age=PORTFOLIO_MAX_AGE,
            coverage="complete" if snapshot.analysis.status == "observed" else "partial",
        )),
    }


@app.get(
    "/api/portfolio/visualization",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    },
)
def portfolio_visualization(
    request: Request,
    response: Response,
    history_limit: int = Query(default=90, ge=2, le=365),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    payload = portfolio_store(request).portfolio_visualization(
        user.id,
        history_limit=history_limit,
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return payload


@app.get(
    "/api/portfolio/instruments/{instrument_uid}/visualization",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        401: {"description": "Authenticated session required"},
        404: {"description": "Instrument is not present in the current account history"},
    },
)
def portfolio_instrument_visualization(
    instrument_uid: str,
    request: Request,
    response: Response,
    history_limit: int = Query(default=90, ge=2, le=365),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        payload = portfolio_store(request).instrument_visualization(
            user.id,
            instrument_uid,
            history_limit=history_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="instrument visualization unavailable",
        )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return payload


@app.get(
    "/api/portfolio/proposals",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def portfolio_proposals(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    proposals = portfolio_store(request).proposals(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "proposals": [proposal_payload(item) for item in proposals],
        "execution_enabled": False,
    }


def _execution_run_payload(
    run: ExecutionRunRecord,
    legs: tuple[ExecutionLegRecord, ...] = (),
) -> dict[str, object]:
    return {
        "id": str(run.id),
        "proposal_id": str(run.proposal_id),
        "proposal_version": run.proposal_version,
        "proposal_hash": run.proposal_hash.hex(),
        "account_id": run.account_id,
        "mode": run.mode,
        "provider_environment": run.provider_environment,
        "live_mandate_id": (
            str(run.live_mandate_id)
            if run.live_mandate_id is not None
            else None
        ),
        "status": run.status,
        "error_code": run.error_code,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "finished_at": run.finished_at,
        "live_execution": run.mode == "live",
        "legs": [
            {
                "id": str(leg.id),
                "leg_index": leg.leg_index,
                "action": leg.action,
                "instrument_uid": leg.instrument_uid,
                "lots_requested": leg.lots_requested,
                "lots_executed": leg.lots_executed,
                "limit_price": str(leg.limit_price),
                "limit_price_type": leg.limit_price_type,
                "max_spend_rub": (
                    str(leg.max_spend_rub)
                    if leg.max_spend_rub is not None
                    else None
                ),
                "min_proceeds_rub": (
                    str(leg.min_proceeds_rub)
                    if leg.min_proceeds_rub is not None
                    else None
                ),
                "request_id": str(leg.request_id),
                "provider_order_id": leg.provider_order_id,
                "provider_status": leg.provider_status,
                "status": leg.status,
                "executed_amount_rub": str(leg.executed_amount_rub),
                "executed_commission_rub": str(
                    leg.executed_commission_rub
                ),
                "submitted_at": leg.submitted_at,
                "last_checked_at": leg.last_checked_at,
                "terminal_at": leg.terminal_at,
            }
            for leg in legs
        ],
    }


def _live_mandate_payload(
    mandate: LiveExecutionMandateRecord | None,
) -> dict[str, object] | None:
    if mandate is None:
        return None
    return {
        "id": str(mandate.id),
        "account_id": mandate.account_id,
        "max_order_notional_rub": str(mandate.max_order_notional_rub),
        "max_daily_notional_rub": str(mandate.max_daily_notional_rub),
        "created_at": mandate.created_at,
        "expires_at": mandate.expires_at,
        "revoked_at": mandate.revoked_at,
    }


def _require_current_legal_consent(request: Request, user: UserRecord) -> None:
    database: Database = request.app.state.database
    if not database.has_legal_versions(
        user.id,
        service(request).legal_versions(),
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_UPDATED_LEGAL_CONSENT_DETAIL,
        )


def _execution_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ExecutionLedgerError, ExecutionServiceError)):
        code = exc.code
    else:
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    if code in {"proposal_not_found", "execution_not_found"}:
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=code,
        )
    if code in {
        "sandbox_connection_changed",
        "sandbox_reconcile_unavailable",
        "live_connection_changed",
        "live_reconcile_unavailable",
    }:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=code,
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=code,
    )


@app.get(
    "/api/portfolio/live-execution/mandate",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def portfolio_live_execution_mandate(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    mandate = execution_store(request).live_mandate(user.id)
    broker_status = broker_service(request).status(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "new_orders_enabled": False,
        "recovery_only": True,
        "connected_environment": broker_status.environment,
        "connected_account_id": broker_status.account_id,
        "mandate": _live_mandate_payload(mandate),
    }


@app.delete(
    "/api/portfolio/live-execution/mandate",
    status_code=204,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def revoke_portfolio_live_execution_mandate(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    execution_store(request).revoke_live_mandate(user.id)
    response.status_code = 204
    return response


@app.get(
    "/api/portfolio/executions",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def portfolio_executions(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    runs = execution_store(request).executions(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "executions": [_execution_run_payload(item) for item in runs],
        "new_orders_enabled": False,
        "recovery_only": True,
        "has_active_live_execution": execution_store(request).has_active_live_execution(user.id),
        "live_mandate": _live_mandate_payload(
            execution_store(request).live_mandate(user.id)
        ),
    }


@app.get(
    "/api/portfolio/executions/{run_id}",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def portfolio_execution(
    run_id: UUID,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    snapshot = execution_store(request).execution(user.id, run_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="execution_not_found",
        )
    run, legs, events = snapshot
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "events": [
            {
                "id": event.id,
                "leg_id": str(event.leg_id) if event.leg_id else None,
                "event_type": event.event_type,
                "details": event.details,
                "created_at": event.created_at,
            }
            for event in events
        ],
        "new_orders_enabled": False,
        "recovery_only": True,
    }


@app.post(
    "/api/portfolio/executions/{run_id}/reconcile",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def reconcile_portfolio_execution(
    run_id: UUID,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    try:
        run, legs = execution_service(request).reconcile(user.id, run_id)
    except (ExecutionLedgerError, ExecutionServiceError, ValueError) as exc:
        raise _execution_error(exc) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_CREDENTIAL_REJECTED_DETAIL) from exc
    if authenticated_user(request, session_token).id != user.id:
        raise HTTPException(status_code=409, detail="execution_account_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "new_orders_enabled": False,
        "recovery_only": True,
    }


@app.post(
    "/api/portfolio/executions/{run_id}/cancel",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def cancel_portfolio_execution(
    run_id: UUID,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    try:
        run, legs = execution_service(request).cancel(user.id, run_id)
    except (ExecutionLedgerError, ExecutionServiceError, ValueError) as exc:
        raise _execution_error(exc) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(status_code=409, detail=_TBANK_CREDENTIAL_REJECTED_DETAIL) from exc
    if authenticated_user(request, session_token).id != user.id:
        raise HTTPException(status_code=409, detail="execution_account_context_changed")
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "new_orders_enabled": False,
        "recovery_only": True,
    }


@app.get(
    "/api/broker/tbank/instruments/search",
    responses={
        400: {"description": "Instrument search query is invalid"},
        401: {"description": "Authenticated session required"},
        409: {"description": "T-Invest connection requires attention"},
        503: {"description": "T-Invest instrument search is temporarily unavailable"},
    },
)
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
        raise HTTPException(status_code=409, detail=_TBANK_NOT_CONNECTED_DETAIL) from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail=_TBANK_CREDENTIAL_REJECTED_DETAIL,
        ) from exc
    except (TBankUnavailable, BrokerConnectionError, SecurityValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="T-Invest instrument search unavailable",
        ) from exc

    return {
        "items": [asdict(item) for item in instruments],
    }


@app.post(
    "/api/broker/tbank/accounts",
    responses={
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
        400: {"description": "Broker credential or terms acknowledgment is invalid"},
        401: {"description": "Authenticated session required"},
        503: {"description": "T-Invest API is temporarily unavailable"},
    },
)
def tbank_accounts(
    body: TBankCredentialBody,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _workspace_editor(request, session_token)
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

    payload = {
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
    return _workspace_result(request, session_token, user, payload, write=True)


@app.put(
    "/api/broker/tbank",
    responses={
        400: {"description": "Broker credential, account, or terms are invalid"},
        401: {"description": "Authenticated session required"},
        409: {"description": "Disconnect the previous account or reconcile active execution"},
        503: {"description": "Broker connection storage or T-Invest API is unavailable"},
    },
)
def connect_tbank(
    body: TBankConnectBody,
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _workspace_editor(request, session_token)
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
    except BrokerConnectionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActiveLiveExecutionError as exc:
        raise HTTPException(
            status_code=409, detail="active_live_execution_must_be_reconciled",
        ) from exc
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

    current = authenticated_user(request, session_token)
    if current.id != user.id:
        raise HTTPException(status_code=409, detail="profile_context_changed")
    _require_current_legal_consent(request, current)
    try:
        refresh = portfolio_refresh(request).request(user.id)
    except PortfolioRefreshBusy:
        # The connection was persisted successfully; admission saturation only
        # postpones its initial read-only observation.
        refresh = {"status": "busy", "retry_after_seconds": 2}

    return {
        "connected": connection.connected,
        "environment": connection.environment,
        "account_id": connection.account_id,
        "account_name": connection.account_name,
        "verified_at": connection.verified_at,
        "refresh": refresh,
    }


@app.delete(
    "/api/broker/tbank",
    status_code=204,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def disconnect_tbank(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    ledger = execution_store(request)
    if ledger.has_active_live_execution(user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_live_execution_must_be_reconciled",
        )
    ledger.revoke_live_mandate(user.id)
    try:
        broker_service(request).disconnect(user.id)
    except ActiveLiveExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_live_execution_must_be_reconciled",
        ) from exc
    response.status_code = 204
    return response


@app.post(
    "/api/account/delete",
    status_code=204,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def delete_account(
    body: DeleteAccountBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    if execution_store(request).has_active_live_execution(user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_live_execution_must_be_reconciled",
        )
    if not body.confirm_irreversible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="irreversible deletion confirmation is required",
        )

    try:
        deleted = service(request).delete_account(user, body.confirm_public_id)
    except ActiveLiveExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_live_execution_must_be_reconciled",
        ) from exc
    except AccountDeletionRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="profile ID confirmation does not match",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account is not active",
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="account could not be deleted",
        )

    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.status_code = 204
    return response


@app.post(
    "/api/auth/logout",
    status_code=204,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def logout(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    auth = service(request)
    user = auth.refresh_session(session_token or "")
    if user is not None:
        _require_profile_context(user, request.headers.get(_PROFILE_CONTEXT_HEADER))
    auth.logout(session_token or "")
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.status_code = 204
    return response
