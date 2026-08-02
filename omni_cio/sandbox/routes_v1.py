from __future__ import annotations

from decimal import Decimal
import os
from types import SimpleNamespace
from typing import Any, Literal, NoReturn

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .client_v1 import SandboxApiFailure
from .service_v1 import (
    DEFAULT_CONFIRMATION_TTL_SECONDS,
    ProposalStoreV1,
    SANDBOX_CANCEL_CONFIRMATION,
    SANDBOX_FUND_CONFIRMATION,
    SandboxTradingServiceV1,
)


SANDBOX_TRADING_ENV = "SANDBOX_TRADING_ENABLED"
SANDBOX_TOKEN_ENV = "TINVEST_SANDBOX_TOKEN"
SANDBOX_TTL_ENV = "SANDBOX_CONFIRMATION_TTL_SECONDS"

_STORE = ProposalStoreV1()
_REGISTERED_APP_IDS: set[int] = set()


def sandbox_trading_enabled() -> bool:
    return os.environ.get(SANDBOX_TRADING_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _ttl_seconds() -> int:
    raw = os.environ.get(SANDBOX_TTL_ENV, "").strip()
    if not raw:
        return DEFAULT_CONFIRMATION_TTL_SECONDS
    try:
        return int(raw)
    except ValueError as exc:
        raise SandboxApiFailure(
            code="SANDBOX_CONFIRMATION_TTL_INVALID",
            message="SANDBOX_CONFIRMATION_TTL_SECONDS must be an integer.",
            http_status=503,
        ) from exc


def _service() -> SandboxTradingServiceV1:
    return SandboxTradingServiceV1(
        token=os.environ.get(SANDBOX_TOKEN_ENV, ""),
        gateway_secret=os.environ.get("GATEWAY_API_KEY", ""),
        confirmation_ttl_seconds=_ttl_seconds(),
        store=_STORE,
    )


def _raise_http(exc: SandboxApiFailure) -> NoReturn:
    detail: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
        "sandbox": True,
        "real_money": False,
    }
    if exc.tracking_id:
        detail["tracking_id"] = exc.tracking_id
    if exc.ambiguous_submission:
        detail["submission_state"] = "unknown_do_not_resubmit"
    raise HTTPException(status_code=exc.http_status, detail=detail) from exc


def _base_response() -> dict[str, Any]:
    return {
        "sandbox": True,
        "real_money": False,
        "sandbox_trading_methods": True,
        "real_trading_methods": False,
    }


class SandboxAccountView(BaseModel):
    masked_account: str
    name: str
    status: str


class SandboxStatusResponse(BaseModel):
    status: str
    mode: Literal["sandbox"]
    configured: bool
    enabled: bool
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool
    sandbox_host: str
    account_count: int
    accounts: list[SandboxAccountView]


class SandboxOpenAccountRequest(BaseModel):
    name: str = Field(default="Omni-CIO Sandbox", min_length=1, max_length=100)
    confirmation: str = Field(
        description="Must be exactly: ПОДТВЕРЖДАЮ СОЗДАНИЕ ПЕСОЧНИЦЫ"
    )


class SandboxOpenAccountResponse(BaseModel):
    status: str
    masked_account: str
    account_count: int
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxFundRequest(BaseModel):
    amount_rub: Decimal = Field(gt=0, le=10_000_000)
    confirmation: str = Field(
        description=f"Must be exactly: {SANDBOX_FUND_CONFIRMATION}"
    )


class SandboxFundResponse(BaseModel):
    status: str
    masked_account: str
    amount_rub: str
    broker_response_json: str
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxPortfolioResponse(BaseModel):
    status: str
    masked_account: str
    portfolio_json: str
    positions_json: str
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxTradePrepareRequest(BaseModel):
    instrument_id: str = Field(min_length=1, max_length=120)
    direction: Literal["BUY", "SELL"]
    quantity_lots: int = Field(ge=1, le=1_000_000)
    order_type: Literal["MARKET", "LIMIT"]
    limit_price: str | None = Field(
        default=None,
        pattern=r"^\d{1,18}(?:\.\d{1,9})?$",
    )
    price_type: Literal["CURRENCY", "POINT"] = "CURRENCY"
    rationale: str = Field(default="", max_length=1500)


class SandboxTradePrepareResponse(BaseModel):
    status: Literal["confirmation_required"]
    proposal_id: str
    order_id: str
    masked_account: str
    instrument_id: str
    direction: str
    quantity_lots: int
    order_type: str
    limit_price: str | None
    price_type: str
    rationale: str
    created_at: str
    expires_at: str
    confirmation_phrase: str
    preflight_json: str
    execution_ready: bool
    requires_user_confirmation: bool
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxTradeExecuteRequest(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    confirmation_phrase: str = Field(min_length=1, max_length=100)


class SandboxTradeExecuteResponse(BaseModel):
    status: str
    proposal_id: str
    order_id: str
    masked_account: str
    instrument_id: str
    direction: str
    quantity_lots: int
    order_type: str
    broker_response_json: str
    idempotent_replay: bool
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxOrderStatusResponse(BaseModel):
    status: str
    masked_account: str
    order_id: str
    broker_response_json: str
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


class SandboxCancelRequest(BaseModel):
    order_id: str = Field(min_length=36, max_length=36)
    confirmation: str = Field(
        description=f"Must be exactly: {SANDBOX_CANCEL_CONFIRMATION}"
    )


class SandboxCancelResponse(BaseModel):
    status: str
    masked_account: str
    order_id: str
    broker_response_json: str
    sandbox: bool
    real_money: bool
    sandbox_trading_methods: bool
    real_trading_methods: bool


def register_sandbox_trading_gateway(
    *,
    app: FastAPI,
    base: Any,
    app_version: str,
) -> None:
    del app_version
    app_id = id(app)
    if app_id in _REGISTERED_APP_IDS:
        return
    _REGISTERED_APP_IDS.add(app_id)

    dependency = Depends(base.require_gateway_key)

    @app.get(
        "/sandbox/status",
        operation_id="getSandboxTradingStatus",
        summary="Verify isolated T-Invest Sandbox connectivity and account state",
        response_model=SandboxStatusResponse,
        dependencies=[dependency],
    )
    def sandbox_status() -> SandboxStatusResponse:
        try:
            payload = _service().status()
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxStatusResponse(
            **payload,
            configured=bool(os.environ.get(SANDBOX_TOKEN_ENV, "").strip()),
            enabled=True,
            **_base_response(),
        )

    @app.post(
        "/sandbox/account/open",
        operation_id="openSandboxAccount",
        summary="Open exactly one virtual T-Invest Sandbox account",
        response_model=SandboxOpenAccountResponse,
        dependencies=[dependency],
        openapi_extra={"x-openai-isConsequential": True},
    )
    def sandbox_open_account(
        request: SandboxOpenAccountRequest,
    ) -> SandboxOpenAccountResponse:
        if request.confirmation.strip() != "ПОДТВЕРЖДАЮ СОЗДАНИЕ ПЕСОЧНИЦЫ":
            raise HTTPException(
                status_code=403,
                detail={"code": "SANDBOX_ACCOUNT_CONFIRMATION_REQUIRED"},
            )
        try:
            payload = _service().open_account(request.name)
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxOpenAccountResponse(**payload, **_base_response())

    @app.post(
        "/sandbox/account/fund",
        operation_id="fundSandboxAccount",
        summary="Add virtual RUB to the single Sandbox account",
        response_model=SandboxFundResponse,
        dependencies=[dependency],
        openapi_extra={"x-openai-isConsequential": True},
    )
    def sandbox_fund_account(request: SandboxFundRequest) -> SandboxFundResponse:
        if request.confirmation.strip() != SANDBOX_FUND_CONFIRMATION:
            raise HTTPException(
                status_code=403,
                detail={"code": "SANDBOX_FUND_CONFIRMATION_REQUIRED"},
            )
        try:
            payload = _service().fund_account(request.amount_rub)
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxFundResponse(**payload, **_base_response())

    @app.get(
        "/sandbox/portfolio",
        operation_id="getSandboxPortfolio",
        summary="Get the virtual Sandbox portfolio and positions",
        response_model=SandboxPortfolioResponse,
        dependencies=[dependency],
    )
    def sandbox_portfolio() -> SandboxPortfolioResponse:
        try:
            payload = _service().portfolio()
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxPortfolioResponse(**payload, **_base_response())

    @app.post(
        "/sandbox/trade/prepare",
        operation_id="prepareSandboxTrade",
        summary=(
            "Prepare a time-limited virtual trade and return the exact phrase "
            "the user must confirm before submission"
        ),
        response_model=SandboxTradePrepareResponse,
        dependencies=[dependency],
    )
    def sandbox_prepare_trade(
        request: SandboxTradePrepareRequest,
    ) -> SandboxTradePrepareResponse:
        try:
            proposal = _service().prepare_trade(
                instrument_id=request.instrument_id,
                direction=request.direction,
                quantity_lots=request.quantity_lots,
                order_type=request.order_type,
                limit_price=request.limit_price,
                price_type=request.price_type,
                rationale=request.rationale,
            )
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxTradePrepareResponse(
            status="confirmation_required",
            proposal_id=proposal.proposal_id,
            order_id=proposal.order_id,
            masked_account=f"***{proposal.account_id[-4:]}",
            instrument_id=proposal.instrument_id,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            order_type=proposal.order_type,
            limit_price=proposal.limit_price,
            price_type=proposal.price_type,
            rationale=proposal.rationale,
            created_at=proposal.created_at.isoformat(),
            expires_at=proposal.expires_at.isoformat(),
            confirmation_phrase=proposal.confirmation_phrase,
            preflight_json=proposal.broker_response_json or "{}",
            execution_ready=False,
            requires_user_confirmation=True,
            **_base_response(),
        )

    @app.post(
        "/sandbox/trade/execute",
        operation_id="executeSandboxTrade",
        summary="Submit only the exact unexpired virtual trade that the user confirmed",
        response_model=SandboxTradeExecuteResponse,
        dependencies=[dependency],
        openapi_extra={"x-openai-isConsequential": True},
    )
    def sandbox_execute_trade(
        request: SandboxTradeExecuteRequest,
    ) -> SandboxTradeExecuteResponse:
        try:
            proposal, replay = _service().execute_trade(
                request.proposal_id,
                request.confirmation_phrase,
            )
        except SandboxApiFailure as exc:
            _raise_http(exc)
        return SandboxTradeExecuteResponse(
            status="submitted" if not replay else "already_submitted",
            proposal_id=proposal.proposal_id,
            order_id=proposal.order_id,
            masked_account=f"***{proposal.account_id[-4:]}",
            instrument_id=proposal.instrument_id,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            order_type=proposal.order_type,
            broker_response_json=proposal.broker_response_json or "{}",
            idempotent_replay=replay,
            **_base_response(),
        )

    @app.get(
        "/sandbox/order/status",
        operation_id="getSandboxOrderState",
        summary="Read the state of a virtual order by its idempotency request id",
        response_model=SandboxOrderStatusResponse,
        dependencies=[dependency],
    )
    def sandbox_order_state(
        order_id: str = Query(..., min_length=36, max_length=36),
    ) -> SandboxOrderStatusResponse:
        try:
            payload = _service().order_state(order_id)
        except SandboxApiFailure as exc:
            _raise_http(exc)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "SANDBOX_ORDER_ID_INVALID"},
            ) from exc
        return SandboxOrderStatusResponse(**payload, **_base_response())

    @app.post(
        "/sandbox/order/cancel",
        operation_id="cancelSandboxOrder",
        summary="Cancel one virtual Sandbox order after explicit user confirmation",
        response_model=SandboxCancelResponse,
        dependencies=[dependency],
        openapi_extra={"x-openai-isConsequential": True},
    )
    def sandbox_cancel_order(request: SandboxCancelRequest) -> SandboxCancelResponse:
        if request.confirmation.strip() != SANDBOX_CANCEL_CONFIRMATION:
            raise HTTPException(
                status_code=403,
                detail={"code": "SANDBOX_CANCEL_CONFIRMATION_REQUIRED"},
            )
        try:
            payload = _service().cancel_order(request.order_id)
        except SandboxApiFailure as exc:
            _raise_http(exc)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "SANDBOX_ORDER_ID_INVALID"},
            ) from exc
        return SandboxCancelResponse(**payload, **_base_response())

    if hasattr(base, "CAPABILITIES") and "sandbox_trading_v1" not in base.CAPABILITIES:
        base.CAPABILITIES.append("sandbox_trading_v1")


def maybe_register_sandbox_trading_gateway(
    *,
    app: FastAPI,
    base: Any,
    app_version: str,
) -> bool:
    if not sandbox_trading_enabled():
        return False
    register_sandbox_trading_gateway(app=app, base=base, app_version=app_version)
    return True


# Small helper used by focused tests without importing the production gateway.
def test_base() -> Any:
    return SimpleNamespace(require_gateway_key=lambda: None, CAPABILITIES=[])
