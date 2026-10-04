"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .balancing_service import build_live_balancing_payload
from .broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .cbr import CBRClient
from .config import Settings, load_settings
from .db import ActiveLiveExecutionError, Database, UserRecord
from .execution_service import ExecutionServiceError, PortfolioExecutionService
from .execution_store import (
    ExecutionLedgerError,
    ExecutionLegRecord,
    ExecutionRunRecord,
    ExecutionStore,
    LiveExecutionMandateRecord,
)
from .intelligence import rating_source_references
from .market import MarketService
from .portfolio import PortfolioAnalysisError
from .portfolio_store import (
    BalancingPolicyInput,
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioStore,
    ProposalStateError,
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
from .security import (
    SecurityValueError,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_vkid_flow,
    pkce_challenge,
    seal_vkid_flow,
    session_digest,
)
from .service import (
    AccountDeletionRejected,
    AuthService,
    LoginUnavailable,
    RegistrationCapacityReached,
    RegistrationClosed,
)
from .tbank import TBankInvestClient, TBankTokenRejected, TBankUnavailable
from .vkid import VKIDClient, VKIDRejected, VKIDUnavailable

SESSION_COOKIE = "omnicio_session"
VKID_FLOW_COOKIE = "omnicio_vkid_flow"
CANONICAL_ORIGIN = "https://omnicio.ru"
VKID_CALLBACK = f"{CANONICAL_ORIGIN}/api/auth/vkid/callback"
INVALID_VKID_CALLBACK = "VK ID callback payload is invalid"
_TBANK_CREDENTIAL_REJECTED_DETAIL = "stored T-Invest credential was rejected"
_UPDATED_LEGAL_CONSENT_DETAIL = "updated legal consent required"
_TBANK_NOT_CONNECTED_DETAIL = "T-Invest is not connected"
_PRIVATE_NO_STORE = "private, no-store"


class StrictRequestBody(BaseModel):
    """Reject ambiguous client payloads instead of silently ignoring typos."""

    model_config = ConfigDict(extra="forbid")


class StartVKIDBody(StrictRequestBody):
    accept_privacy: bool
    accept_personal_data: bool
    accept_terms: bool
    confirm_age_18: bool


class TBankCredentialBody(StrictRequestBody):
    credential: str = Field(min_length=20, max_length=4096)
    environment: Literal["prod", "sandbox"] = "prod"
    accept_personal_terms: bool


class TBankConnectBody(TBankCredentialBody):
    account_id: str = Field(min_length=1, max_length=128)


class DeleteAccountBody(StrictRequestBody):
    confirm_public_id: str = Field(pattern=r"^[0-9]{9}$")
    confirm_irreversible: bool


class InvestmentProfileBody(StrictRequestBody):
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
    confirm_public_id: str = Field(pattern=r"^[0-9]{9}$")
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


def execution_store(request: Request) -> ExecutionStore:
    return cast(ExecutionStore, request.app.state.execution_store)


def execution_service(request: Request) -> PortfolioExecutionService:
    return cast(
        PortfolioExecutionService,
        request.app.state.execution_service,
    )


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
    app.state.portfolio_store = PortfolioStore(database)
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
        "registration_enabled": cfg.registration_enabled,
        "registration_max_users": cfg.registration_max_users,
        "login_enabled": cfg.vkid_ready,
        "legal_versions": {
            "privacy_policy": cfg.privacy_version,
            "personal_data_consent": cfg.consent_version,
            "terms": cfg.terms_version,
        },
    }


@app.post(
    "/api/auth/vkid/start",
    responses={
        400: {"description": "Legal or age confirmation is invalid"},
        503: {"description": "VK ID login is not configured"},
    },
)
def start_vkid(
    body: StartVKIDBody,
    request: Request,
    response: Response,
) -> dict[str, str]:
    require_same_origin(request)
    cfg = settings(request)
    if not cfg.vkid_ready:
        raise HTTPException(status_code=503, detail="VK ID login is not configured")
    if not (body.accept_privacy and body.accept_personal_data and body.accept_terms):
        raise HTTPException(status_code=400, detail="legal acknowledgments are required")
    if not body.confirm_age_18:
        raise HTTPException(status_code=400, detail="user must confirm age 18+")

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

        identity = vkid_client(request).exchange_code(
            code=code,
            device_id=device_id,
            code_verifier=verifier,
            expected_state=expected_state,
        )
        result = service(request).complete_vkid_login(
            vk_user_id=identity.user_id,
            client_ip=client_ip(request),
            accepted_legal_versions=legal_versions,
        )
    except RegistrationClosed:
        return auth_redirect("/?auth_error=registration")
    except RegistrationCapacityReached:
        return auth_redirect("/?auth_error=capacity")
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
        "role": user.role,
    }


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
    except (TBankUnavailable, BrokerConnectionError, SecurityValueError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="USD/RUB market quote unavailable",
        ) from exc
    return asdict(snapshot)


@app.get("/api/market/usd-rub/stream")
async def usd_rub_market_stream(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> StreamingResponse:
    user = authenticated_user(request, session_token)
    market = market_service(request)

    async def events() -> AsyncIterator[str]:
        retry_delay = 5
        yield "retry: 5000\n\n"
        while True:
            if await request.is_disconnected():
                break

            payload: dict[str, object]
            try:
                snapshot = await asyncio.to_thread(market.usd_rub, user.id)
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
            except (TBankUnavailable, BrokerConnectionError, SecurityValueError, ValueError):
                payload = {"state": "unavailable"}
                event = "status"
                delay = retry_delay
                retry_delay = min(retry_delay * 2, 30)
            else:
                payload = asdict(snapshot)
                event = "quote"
                delay = 5
                retry_delay = 5

            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            yield f"event: {event}\ndata: {data}\n\n"
            await asyncio.sleep(delay)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
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


@app.get("/api/profile/investment")
def investment_profile(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    profile = portfolio_store(request).current_profile(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"profile": _profile_payload(profile) if profile is not None else None}


@app.put("/api/profile/investment")
def save_investment_profile(
    body: InvestmentProfileBody,
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
    profile = portfolio_store(request).save_profile(
        user.id,
        reserve_rub=body.reserve_rub,
        planned_withdrawal_rub=body.planned_withdrawal_rub,
        horizon_months=body.horizon_months,
        max_drawdown_percent=body.max_drawdown_percent,
        liquidity_horizon_days=body.liquidity_horizon_days,
        allow_below_investment_grade=body.allow_below_investment_grade,
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"profile": _profile_payload(profile)}


@app.get("/api/profile/balancing")
def balancing_policy(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    policy = portfolio_store(request).current_balancing_policy(user.id)
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {
        "policy": _balancing_policy_payload(policy) if policy is not None else None
    }


@app.put("/api/profile/balancing")
def save_balancing_policy(
    body: BalancingPolicyBody,
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
    )
    response.headers["Cache-Control"] = _PRIVATE_NO_STORE
    return {"policy": _balancing_policy_payload(policy)}


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
        "account_name": snapshot.account_name,
        "environment": snapshot.environment,
        "refreshed_at": snapshot.refreshed_at,
        "portfolio": asdict(snapshot.portfolio),
        "cash": [asdict(item) for item in snapshot.positions.money],
        "blocked_cash": [asdict(item) for item in snapshot.positions.blocked_money],
        "limits_loading_in_progress": snapshot.positions.limits_loading_in_progress,
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
    return asdict(snapshot)


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
    responses={401: {"description": "Authenticated session required"}},
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
    responses={401: {"description": "Authenticated session required"}},
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


@app.get("/api/portfolio/proposals")
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


@app.post("/api/portfolio/proposals", status_code=status.HTTP_201_CREATED)
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


@app.post("/api/portfolio/proposals/{proposal_id}/decision")
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


@app.get("/api/portfolio/live-execution/mandate")
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


@app.put("/api/portfolio/live-execution/mandate")
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


@app.delete("/api/portfolio/live-execution/mandate", status_code=204)
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


@app.get("/api/portfolio/executions")
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


@app.get("/api/portfolio/executions/{run_id}")
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


@app.post("/api/portfolio/executions", status_code=status.HTTP_201_CREATED)
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


@app.post("/api/portfolio/executions/{run_id}/advance")
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


@app.post("/api/portfolio/executions/{run_id}/cancel")
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
    responses={401: {"description": "Authenticated session required"}},
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


@app.post("/api/account/delete", status_code=204)
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
