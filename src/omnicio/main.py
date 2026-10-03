"""FastAPI HTTP boundary for OmniCIO."""

from __future__ import annotations

import asyncio
import ipaddress
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from decimal import Decimal
from typing import Literal, cast

from fastapi import Cookie, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from .broker import (
    BrokerAccountNotAccessible,
    BrokerConnectionError,
    BrokerNotConnected,
    BrokerService,
)
from .cbr import CBRClient
from .config import Settings, load_settings
from .db import Database, UserRecord
from .intelligence import rating_source_references
from .market import MarketService
from .portfolio import PortfolioAnalysisError
from .portfolio_store import (
    BalancingPolicyRecord,
    InvestmentProfileRecord,
    PortfolioStore,
)
from .security import (
    SecurityValueError,
    format_public_id,
    generate_oauth_state,
    generate_pkce_verifier,
    open_vkid_flow,
    pkce_challenge,
    seal_vkid_flow,
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


class DeleteAccountBody(BaseModel):
    confirm_public_id: str = Field(pattern=r"^[0-9]{9}$")
    confirm_irreversible: bool


class InvestmentProfileBody(BaseModel):
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


class BalancingPolicyBody(BaseModel):
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
    no_trade_band_percent: Decimal = Field(ge=0, le=100, allow_inf_nan=False)
    min_replace_benefit_rub: Decimal = Field(
        ge=0,
        le=1_000_000_000_000,
        allow_inf_nan=False,
    )


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


@app.post("/api/auth/vkid/start")
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


@app.get("/api/market/usd-rub")
def usd_rub_market_snapshot(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    try:
        snapshot = market_service(request).usd_rub(user.id)
    except BrokerNotConnected as exc:
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
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
    response.headers["Cache-Control"] = "private, no-store"
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
            detail="updated legal consent required",
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
    response.headers["Cache-Control"] = "private, no-store"
    return {"profile": _profile_payload(profile)}


@app.get("/api/profile/balancing")
def balancing_policy(
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, object]:
    user = authenticated_user(request, session_token)
    policy = portfolio_store(request).current_balancing_policy(user.id)
    response.headers["Cache-Control"] = "private, no-store"
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
            detail="updated legal consent required",
        )
    policy = portfolio_store(request).save_balancing_policy(
        user.id,
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
        no_trade_band_percent=body.no_trade_band_percent,
        min_replace_benefit_rub=body.min_replace_benefit_rub,
    )
    response.headers["Cache-Control"] = "private, no-store"
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
        raise HTTPException(status_code=409, detail="T-Invest is not connected") from exc
    except TBankTokenRejected as exc:
        raise HTTPException(
            status_code=409,
            detail="stored T-Invest credential was rejected",
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

    response.headers["Cache-Control"] = "private, no-store"
    return asdict(snapshot)


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
    response.headers["Cache-Control"] = "private, no-store"
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


@app.post("/api/account/delete", status_code=204)
def delete_account(
    body: DeleteAccountBody,
    request: Request,
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> Response:
    require_same_origin(request)
    user = authenticated_user(request, session_token)
    if not body.confirm_irreversible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="irreversible deletion confirmation is required",
        )

    try:
        deleted = service(request).delete_account(user, body.confirm_public_id)
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
