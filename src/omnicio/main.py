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
from datetime import UTC, datetime
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
from .balancing_service import build_live_balancing_payload
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
from .intelligence import rating_source_references
from .market import MarketService
from .news import NewsClient, NewsUnavailable
from .portfolio import PortfolioAnalysisError
from .portfolio_store import (
    BalancingPolicyInput,
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioStore,
    ProposalStateError,
    SettingsVersionConflict,
)
from .proposals import (
    ProposalBuildError,
    build_proposal_draft,
    parse_proposal_hash,
    proposal_action_payload,
    proposal_generated_at,
    proposal_material_hash,
    proposal_payload,
)
from .recovery import recovery_status
from .security import (
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
_UPDATED_LEGAL_CONSENT_DETAIL = "updated legal consent required"
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


class StartVKIDBody(StrictRequestBody):
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


class InvestmentProfileBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    expected_version: int = Field(ge=0, le=2_147_483_647, strict=True)
    reserve_rub: Decimal = Field(ge=0, le=1_000_000_000_000, allow_inf_nan=False)
    planned_withdrawal_rub: Decimal = Field(
        ge=0,
        le=1_000_000_000_000,
        allow_inf_nan=False,
    )
    horizon_months: int = Field(ge=1, le=1200)
    max_drawdown_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    liquidity_horizon_days: int = Field(ge=0, le=36500)
    allow_below_investment_grade: bool = False


class BalancingPolicyBody(StrictRequestBody):
    expected_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    expected_version: int = Field(ge=0, le=2_147_483_647, strict=True)
    max_instrument_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_sector_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_issuer_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_group_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_share_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_bond_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_etf_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_below_grade_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_unknown_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_term_months: int = Field(ge=0, le=1200)
    turnover_budget_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    max_daily_turnover_participation_percent: Decimal = Field(
        ge=0,
        le=100,
        allow_inf_nan=False,
    )
    securities_tax_rate_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    uncertainty_haircut_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    credit_loss_haircut_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    no_trade_band_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    min_replace_benefit_rub: Decimal = Field(
        ge=0,
        le=1_000_000_000_000,
        allow_inf_nan=False,
    )


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


class PortfolioProposalBody(StrictRequestBody):
    scenario_kind: Literal["deploy_cash", "replace"]
    replaced_instrument_uid: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
    )


class PortfolioExecutionBody(StrictRequestBody):
    proposal_id: UUID
    proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mode: Literal["shadow", "sandbox", "live"]


class PortfolioLiveMandateBody(StrictRequestBody):
    account_id: str = Field(min_length=1, max_length=128)
    max_order_notional_rub: Decimal = Field(
        gt=0,
        le=1_000_000_000_000,
        decimal_places=2,
        allow_inf_nan=False,
    )
    max_daily_notional_rub: Decimal = Field(
        gt=0,
        le=1_000_000_000_000,
        decimal_places=2,
        allow_inf_nan=False,
    )
    expires_at: datetime
    confirm_public_id: str = Field(pattern=_PUBLIC_ID_PATTERN)
    confirm_live_execution: bool


class PortfolioProposalDecisionBody(StrictRequestBody):
    action: Literal["confirm", "reject", "defer"]
    proposal_version: int = Field(ge=1)
    proposal_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    reason: str | None = Field(default=None, max_length=500)
    deferred_until: datetime | None = None


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


def authenticated_session_digest(session_token: str | None) -> bytes:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return session_digest(session_token)


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
        live_execution_enabled=cfg.portfolio_live_execution_enabled,
        live_max_order_rub=cfg.portfolio_live_max_order_rub,
        live_max_daily_rub=cfg.portfolio_live_max_daily_rub,
    )
    app.state.market_service = MarketService(
        broker=broker,
        cbr=CBRClient(),
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
    provider: str, body: StartVKIDBody, request: Request, response: Response,
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


@app.post("/api/auth/vkid/start")
def start_vkid(
    body: StartVKIDBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str]:
    return _start_oauth("vkid", body, request, response, session_token)


@app.post("/api/auth/tid/start")
def start_tid(
    body: StartVKIDBody, request: Request, response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str]:
    return _start_oauth("tid", body, request, response, session_token)


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
        values = callback_values(request)
        if provider == "vkid":
            code, device_id = validate_vkid_callback_values(values, flow.state)
        else:
            if any(len(request.query_params.getlist(k)) != 1 for k in ("code", "state")):
                raise TIDRejected("tid_callback_ambiguous")
            code = values.get("code", "")
            if (values.get("error") or not code or len(code) > 4096
                    or not hmac.compare_digest(
                        values.get("state", "").encode(), flow.state.encode(),
                    )):
                raise TIDRejected("tid_callback_invalid")
            device_id = ""
        linked_user = None
        if flow.link_user_id is not None:
            linked_user = authenticated_user(request, session_token)
            if (str(linked_user.id) != flow.link_user_id
                    or not hmac.compare_digest(
                        session_digest(session_token or "").hex(), flow.link_session_digest or "",
                    )):
                raise PermissionError("oauth_link_session_changed")
        database: Database = request.app.state.database
        if not database.claim_oauth_flow(
            session_digest(flow.state), provider, cfg.vkid_flow_ttl_seconds,
        ):
            raise SecurityValueError("oauth_state_already_used")
        auth = service(request)
        if provider == "vkid":
            vk_identity = vkid_client(request).exchange_code(
                code=code, device_id=device_id,
                code_verifier=flow.code_verifier, expected_state=flow.state,
            )
            result = auth.complete_vkid_login(
                vk_user_id=vk_identity.user_id, client_ip=client_ip(request),
                accepted_legal_versions=flow.legal_versions,
                link_user_id=linked_user.id if linked_user else None,
                link_session_digest=(bytes.fromhex(flow.link_session_digest)
                                     if flow.link_session_digest else None),
            )
        else:
            tid: TIDClient = request.app.state.tid_client
            tid_identity = tid.exchange_code(code=code, code_verifier=flow.code_verifier)
            result = auth.complete_tid_login(
                tid_subject=tid_identity.subject, client_ip=client_ip(request),
                accepted_legal_versions=flow.legal_versions,
                link_user_id=linked_user.id if linked_user else None,
                link_session_digest=(bytes.fromhex(flow.link_session_digest)
                                     if flow.link_session_digest else None),
            )
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


@app.get("/api/auth/vkid/callback")
def vkid_callback(
    request: Request,
    flow_cookie: str | None = Cookie(default=None, alias=VKID_FLOW_COOKIE),
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> RedirectResponse:
    return _oauth_callback("vkid", request, flow_cookie, session_token)


@app.get("/api/auth/tid/callback")
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


@app.get("/api/auth/identities")
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


@app.get("/api/assistant/status")
def assistant_status(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    authenticated_user(request, session_token)
    assistant: AssistantClient = request.app.state.assistant_client
    return assistant.status()


@app.post("/api/assistant/messages")
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


@app.get("/api/workspace")
def get_workspace(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    return workspace_store(request).dashboard(user.id)


@app.get("/api/preferences")
def get_preferences(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    return workspace_store(request).preferences(user.id)


def _workspace_editor(request: Request, session_token: str | None) -> UserRecord:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    return user


@app.put("/api/preferences")
def save_preferences(
    body: WorkspaceSaveBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        return workspace_store(request).save_preferences(
            user.id, body.document, expected_version=body.expected_version,
        )
    except SettingsVersionConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="workspace_document_invalid") from exc


@app.get("/api/goals")
def get_goals(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    return workspace_store(request).goals(user.id)


@app.post("/api/goals", status_code=201)
def create_goal(
    body: WorkspaceDocumentBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        return workspace_store(request).create_goal(user.id, body.document)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="goal_document_invalid") from exc


@app.put("/api/goals/{goal_id}")
def update_goal(
    goal_id: UUID, body: WorkspaceSaveBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        return workspace_store(request).update_goal(
            user.id, goal_id, body.document, expected_version=body.expected_version,
        )
    except SettingsVersionConflict:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="goal_document_invalid") from exc


@app.delete("/api/goals/{goal_id}")
def delete_goal(
    goal_id: UUID, body: WorkspaceVersionBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, bool]:
    user = _workspace_editor(request, session_token)
    return {"deleted": workspace_store(request).delete_goal(
        user.id, goal_id, expected_version=body.expected_version,
    )}


@app.get("/api/events")
def get_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = Query(default=False),
    category: Literal["all", "portfolio", "payments", "goals", "system"] = "all",
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = authenticated_user(request, session_token)
    return workspace_store(request).events(
        user.id, limit=limit, unread_only=unread_only, category=category,
    )


@app.post("/api/events/read")
def mark_events_read(
    body: EventsReadBody, request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, Any]:
    user = _workspace_editor(request, session_token)
    try:
        return workspace_store(request).mark_events_read(user.id, body.ids, read=body.read)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="event_ids_invalid") from exc


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


@app.get("/api/public/news")
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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


@app.put(
    "/api/profile/investment",
    responses={409: {"description": "Settings owner/version conflict or updated consent required"}},
)
def save_investment_profile(
    body: InvestmentProfileBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    profile = portfolio_store(request).save_profile(
        user.id,
        reserve_rub=body.reserve_rub,
        planned_withdrawal_rub=body.planned_withdrawal_rub,
        horizon_months=body.horizon_months,
        max_drawdown_percent=body.max_drawdown_percent,
        liquidity_horizon_days=body.liquidity_horizon_days,
        allow_below_investment_grade=body.allow_below_investment_grade,
        expected_version=body.expected_version,
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"public_id": format_public_id(user.public_id), "profile": _profile_payload(profile)}


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


@app.put(
    "/api/profile/balancing",
    responses={409: {"description": "Settings owner/version conflict or updated consent required"}},
)
def save_balancing_policy(
    body: BalancingPolicyBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = _settings_editor_user(request, session_token, body.expected_public_id)
    policy = portfolio_store(request).save_balancing_policy(
        user.id,
        BalancingPolicyInput(
            max_instrument_percent=body.max_instrument_percent,
            max_sector_percent=body.max_sector_percent,
            max_issuer_percent=body.max_issuer_percent,
            max_group_percent=body.max_group_percent,
            max_share_percent=body.max_share_percent,
            max_bond_percent=body.max_bond_percent,
            max_etf_percent=body.max_etf_percent,
            max_below_grade_percent=body.max_below_grade_percent,
            max_unknown_percent=body.max_unknown_percent,
            max_term_months=body.max_term_months,
            turnover_budget_percent=body.turnover_budget_percent,
            max_daily_turnover_participation_percent=(
                body.max_daily_turnover_participation_percent
            ),
            securities_tax_rate_percent=body.securities_tax_rate_percent,
            uncertainty_haircut_percent=body.uncertainty_haircut_percent,
            credit_loss_haircut_percent=body.credit_loss_haircut_percent,
            no_trade_band_percent=body.no_trade_band_percent,
            min_replace_benefit_rub=body.min_replace_benefit_rub,
        ),
        expected_version=body.expected_version,
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "public_id": format_public_id(user.public_id),
        "policy": _balancing_policy_payload(policy),
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
    "/api/broker/tbank/portfolio",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": "T-Invest connection requires attention"},
        503: {"description": "T-Invest portfolio is temporarily unavailable"},
    },
)
def tbank_portfolio(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = broker_service(request).portfolio(user.id)
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
            detail="T-Invest portfolio unavailable",
        ) from exc

    return {
        "account_id": snapshot.account_id,
        "account_name": snapshot.account_name,
        "environment": snapshot.environment,
        "refreshed_at": snapshot.refreshed_at,
        "portfolio": asdict(snapshot.portfolio),
        "cash": [asdict(item) for item in snapshot.positions.money],
        "blocked_cash": [asdict(item) for item in snapshot.positions.blocked_money],
        "limits_loading_in_progress": snapshot.positions.limits_loading_in_progress,
        "freshness": asdict(describe_freshness(
            snapshot.refreshed_at,
            max_age=PORTFOLIO_MAX_AGE,
            coverage="partial" if snapshot.positions.limits_loading_in_progress else "complete",
        )),
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


def _live_balancing_for_user(
    request: Request,
    user_id: UUID,
) -> dict[str, object]:
    store = portfolio_store(request)
    return build_live_balancing_payload(
        user_id=user_id,
        profile=store.current_profile(user_id),
        policy_record=store.current_balancing_policy(user_id),
        context=store.latest_balancing_context(user_id),
        broker=broker_service(request),
    )


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    "/api/portfolio/balancing",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    },
)
def portfolio_balancing(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    payload = _live_balancing_for_user(request, user.id)
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


@app.post(
    "/api/portfolio/proposals",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def create_portfolio_proposal(
    body: PortfolioProposalBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    database: Database = request.app.state.database
    if not database.has_legal_versions(user.id, service(request).legal_versions()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_UPDATED_LEGAL_CONSENT_DETAIL,
        )

    balancing = _live_balancing_for_user(request, user.id)
    try:
        draft = build_proposal_draft(
            balancing,
            scenario_kind=body.scenario_kind,
            replaced_instrument_uid=body.replaced_instrument_uid,
        )
        proposal = portfolio_store(request).create_proposal(
            user.id,
            source_snapshot_id=draft.source_snapshot_id,
            account_id=draft.account_id,
            profile_version=draft.profile_version,
            policy_version=draft.policy_version,
            scenario_kind=draft.scenario_kind,
            target_instrument_uid=draft.target_instrument_uid,
            replaced_instrument_uid=draft.replaced_instrument_uid,
            proposal_hash=draft.proposal_hash,
            session_digest=authenticated_session_digest(session_token),
            payload=draft.payload,
            expires_at=draft.expires_at,
        )
    except (ProposalBuildError, ProposalStateError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
        ) from exc

    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "proposal": proposal_payload(proposal),
        "execution_enabled": False,
    }


def _proposal_decision_action(
    action: str,
) -> Literal["confirmed", "rejected", "deferred"]:
    if action == "confirm":
        return "confirmed"
    if action == "reject":
        return "rejected"
    return "deferred"


def _proposal_scenario_kind(
    value: str,
) -> Literal["deploy_cash", "replace"]:
    if value == "deploy_cash":
        return "deploy_cash"
    if value == "replace":
        return "replace"
    raise ProposalBuildError("scenario_kind_invalid")


def _proposal_material_is_current(
    request: Request,
    user_id: UUID,
    proposal_id: UUID,
    body: PortfolioProposalDecisionBody,
    expected_hash: bytes,
) -> bool:
    if body.action != "confirm":
        return True

    store = portfolio_store(request)
    current = store.proposal(user_id, proposal_id)
    if current is None:
        raise ProposalStateError("proposal_not_found")
    if not (
        current.status == "pending"
        and current.version == body.proposal_version
        and current.proposal_hash == expected_hash
    ):
        return True

    try:
        refreshed = build_proposal_draft(
            _live_balancing_for_user(request, user_id),
            scenario_kind=_proposal_scenario_kind(current.scenario_kind),
            replaced_instrument_uid=current.replaced_instrument_uid,
            now=proposal_generated_at(current),
        )
    except ProposalBuildError as exc:
        if exc.code in {
            "balancing_not_observed",
            "live_evidence_not_received",
        }:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="proposal_revalidation_unavailable",
            ) from exc
        return False

    return (
        proposal_material_hash(current.payload)
        == proposal_material_hash(refreshed.payload)
    )


@app.post(
    "/api/portfolio/proposals/{proposal_id}/decision",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def decide_portfolio_proposal(
    proposal_id: UUID,
    body: PortfolioProposalDecisionBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    database: Database = request.app.state.database
    if not database.has_legal_versions(user.id, service(request).legal_versions()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_UPDATED_LEGAL_CONSENT_DETAIL,
        )
    try:
        expected_hash = parse_proposal_hash(body.proposal_hash)
        store = portfolio_store(request)
        material_current = _proposal_material_is_current(
            request,
            user.id,
            proposal_id,
            body,
            expected_hash,
        )
        proposal, decision = store.decide_proposal(
            user.id,
            proposal_id=proposal_id,
            expected_version=body.proposal_version,
            expected_hash=expected_hash,
            action=_proposal_decision_action(body.action),
            session_digest=authenticated_session_digest(session_token),
            user_reason=body.reason or "",
            deferred_until=body.deferred_until,
            material_current=material_current,
            now=datetime.now(UTC),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ProposalStateError as exc:
        http_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "proposal_not_found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=http_status, detail=exc.code) from exc

    result = proposal_action_payload(proposal, decision)
    if decision.action in {"expired", "revoked"}:
        response.status_code = status.HTTP_409_CONFLICT
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return result


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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    cfg = settings(request)
    mandate = execution_store(request).live_mandate(user.id)
    broker_status = broker_service(request).status(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "operator_enabled": cfg.portfolio_live_execution_enabled,
        "operator_max_order_notional_rub": cfg.portfolio_live_max_order_rub,
        "operator_max_daily_notional_rub": cfg.portfolio_live_max_daily_rub,
        "connected_environment": broker_status.environment,
        "connected_account_id": broker_status.account_id,
        "mandate": _live_mandate_payload(mandate),
        "canary_scope": "deploy_cash_buy_only",
    }


@app.put(
    "/api/portfolio/live-execution/mandate",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def save_portfolio_live_execution_mandate(
    body: PortfolioLiveMandateBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    cfg = settings(request)
    if not cfg.portfolio_live_execution_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="live_execution_disabled",
        )
    if not body.confirm_live_execution:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="live_execution_confirmation_required",
        )
    if body.confirm_public_id != format_public_id(user.public_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="profile_id_confirmation_mismatch",
        )
    if body.max_daily_notional_rub < body.max_order_notional_rub:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="live_daily_cap_below_order_cap",
        )
    if (
        body.max_order_notional_rub > cfg.portfolio_live_max_order_rub
        or body.max_daily_notional_rub > cfg.portfolio_live_max_daily_rub
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="live_operator_cap_exceeded",
        )
    broker_status = broker_service(request).status(user.id)
    if (
        not broker_status.connected
        or broker_status.environment != "prod"
        or broker_status.account_id != body.account_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="live_account_mismatch",
        )
    try:
        broker_service(request).live_account(user.id)
        mandate = execution_store(request).create_live_mandate(
            user.id,
            account_id=body.account_id,
            max_order_notional_rub=body.max_order_notional_rub,
            max_daily_notional_rub=body.max_daily_notional_rub,
            session_digest=authenticated_session_digest(session_token),
            expires_at=body.expires_at,
        )
    except ExecutionLedgerError as exc:
        raise _execution_error(exc) from exc
    except BrokerConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="live_write_access_required",
        ) from exc
    except TBankUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="live_account_revalidation_unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "operator_enabled": True,
        "mandate": _live_mandate_payload(mandate),
        "canary_scope": "deploy_cash_buy_only",
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
    cfg = settings(request)
    modes = ["shadow", "sandbox"]
    if cfg.portfolio_live_execution_enabled:
        modes.append("live")
    return {
        "executions": [_execution_run_payload(item) for item in runs],
        "live_execution_enabled": cfg.portfolio_live_execution_enabled,
        "live_mandate": _live_mandate_payload(
            execution_store(request).live_mandate(user.id)
        ),
        "modes": modes,
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
        "live_execution_enabled": settings(request).portfolio_live_execution_enabled,
    }


@app.post(
    "/api/portfolio/executions",
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def create_portfolio_execution(
    body: PortfolioExecutionBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    try:
        run, legs = execution_service(request).start(
            user.id,
            proposal_id=body.proposal_id,
            proposal_version=body.proposal_version,
            proposal_hash=parse_proposal_hash(body.proposal_hash),
            mode=body.mode,
            session_digest=authenticated_session_digest(session_token),
        )
    except (ExecutionLedgerError, ExecutionServiceError, ValueError) as exc:
        raise _execution_error(exc) from exc
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "live_execution_enabled": settings(request).portfolio_live_execution_enabled,
    }


@app.post(
    "/api/portfolio/executions/{run_id}/advance",
    responses={409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION}},
)
def advance_portfolio_execution(
    run_id: UUID,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    _require_current_legal_consent(request, user)
    try:
        run, legs = execution_service(request).advance(user.id, run_id)
    except (ExecutionLedgerError, ExecutionServiceError, ValueError) as exc:
        raise _execution_error(exc) from exc
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "live_execution_enabled": settings(request).portfolio_live_execution_enabled,
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
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "execution": _execution_run_payload(run, legs),
        "live_execution_enabled": settings(request).portfolio_live_execution_enabled,
    }


@app.get(
    "/api/portfolio/intelligence",
    responses={
        401: {"description": "Authenticated session required"},
        409: {"description": _PROFILE_CONTEXT_CONFLICT_DESCRIPTION},
    },
)
def portfolio_intelligence(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    snapshot = portfolio_store(request).latest_intelligence(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    if snapshot is None:
        return {
            "status": "pending",
            "execution_enabled": False,
            "rating_feed_status": "data_missing",
            "rating_sources": rating_source_references(),
            "risks": [],
            "payouts": [],
            "sources": [],
        }
    return {
        "status": "observed",
        "rating_sources": rating_source_references(),
        **snapshot,
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

    return {
        "connected": connection.connected,
        "environment": connection.environment,
        "account_id": connection.account_id,
        "account_name": connection.account_name,
        "verified_at": connection.verified_at,
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
