from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Any, Callable, Literal, NoReturn

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .client_v1 import RealTradingApiFailure
from .durable_journal_codec_v1 import JournalIntegrityError, JournalStorageError
from .durable_journal_factory_v1 import (
    DEFAULT_REAL_JOURNAL_BACKEND,
    REAL_JOURNAL_BACKEND_ENV,
    build_real_execution_journal,
)
from .journal_v1 import RealExecutionJournalV1
from .market_context_v1 import market_context_from_snapshot
from .models_v1 import RealMarketContextV1, RealTradingPolicyV1
from .service_v1 import RealTradingServiceV1, mask_account_id


REAL_TRADING_ENV = "REAL_TRADING_ENABLED"
REAL_TRADING_TOKEN_ENV = "TINVEST_TRADING_TOKEN"
REAL_MAX_ORDER_ENV = "REAL_TRADING_MAX_ORDER_RUB"
REAL_MAX_DAILY_ENV = "REAL_TRADING_MAX_DAILY_RUB"
REAL_TTL_ENV = "REAL_TRADING_CONFIRMATION_TTL_SECONDS"
REAL_MARKET_MAX_AGE_ENV = "REAL_TRADING_MARKET_MAX_AGE_SECONDS"
DEFAULT_TTL_SECONDS = 120
DEFAULT_MARKET_MAX_AGE_SECONDS = 15
PRODUCTION_JOURNAL_PATH = Path("/var/data/omni-cio-real-trading.sqlite3")

_REGISTERED_APP_IDS: set[int] = set()
ExpectedAccountIdProvider = Callable[[], str]
ReadOnlyMarketSnapshotProvider = Callable[[str], dict[str, Any]]


def real_trading_enabled() -> bool:
    return os.environ.get(REAL_TRADING_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _positive_decimal_env(name: str) -> Decimal:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise RealTradingApiFailure(
            code="REAL_TRADING_LIMIT_NOT_CONFIGURED",
            message=f"{name} is required before real trading can be published.",
            http_status=503,
        )
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise RealTradingApiFailure(
            code="REAL_TRADING_LIMIT_INVALID",
            message=f"{name} must be a positive finite decimal.",
            http_status=503,
        ) from exc
    if not value.is_finite() or value <= 0:
        raise RealTradingApiFailure(
            code="REAL_TRADING_LIMIT_INVALID",
            message=f"{name} must be a positive finite decimal.",
            http_status=503,
        )
    return value


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RealTradingApiFailure(
            code="REAL_TRADING_POLICY_INVALID",
            message=f"{name} must be an integer.",
            http_status=503,
        ) from exc
    if not minimum <= value <= maximum:
        raise RealTradingApiFailure(
            code="REAL_TRADING_POLICY_INVALID",
            message=f"{name} must be between {minimum} and {maximum}.",
            http_status=503,
        )
    return value


def _policy() -> RealTradingPolicyV1:
    policy = RealTradingPolicyV1(
        max_order_rub=_positive_decimal_env(REAL_MAX_ORDER_ENV),
        max_daily_rub=_positive_decimal_env(REAL_MAX_DAILY_ENV),
        confirmation_ttl_seconds=_bounded_int_env(REAL_TTL_ENV, 120, 30, 600),
        market_max_age_seconds=_bounded_int_env(
            REAL_MARKET_MAX_AGE_ENV, 15, 1, 60
        ),
    )
    try:
        policy.validate()
    except ValueError as exc:
        raise RealTradingApiFailure(
            code="REAL_TRADING_POLICY_INVALID",
            message=str(exc),
            http_status=503,
        ) from exc
    return policy


def _journal_backend_name() -> str:
    return (
        os.environ.get(REAL_JOURNAL_BACKEND_ENV, DEFAULT_REAL_JOURNAL_BACKEND)
        .strip()
        .lower()
        or DEFAULT_REAL_JOURNAL_BACKEND
    )


@dataclass(frozen=True, slots=True)
class StaticRuntimeV1:
    token: str
    gateway_secret: str
    policy: RealTradingPolicyV1
    journal_backend: str
    journal: RealExecutionJournalV1


def _static_runtime(journal_path: Path) -> StaticRuntimeV1:
    token = os.environ.get(REAL_TRADING_TOKEN_ENV, "").strip()
    if not token:
        raise RealTradingApiFailure(
            code="REAL_TRADING_TOKEN_NOT_CONFIGURED",
            message="Dedicated TINVEST_TRADING_TOKEN is not configured.",
            http_status=503,
        )
    gateway_secret = os.environ.get("GATEWAY_API_KEY", "").strip()
    if not gateway_secret:
        raise RealTradingApiFailure(
            code="GATEWAY_SECRET_NOT_CONFIGURED",
            message="Gateway secret is required for confirmation binding.",
            http_status=503,
        )
    try:
        backend, journal = build_real_execution_journal(
            gateway_secret=gateway_secret,
            sqlite_path=journal_path,
        )
    except (JournalIntegrityError, JournalStorageError) as exc:
        raise RealTradingApiFailure(
            code="REAL_DURABLE_JOURNAL_UNAVAILABLE",
            message="Durable real execution journal is unavailable or invalid.",
            http_status=503,
        ) from exc
    return StaticRuntimeV1(
        token=token,
        gateway_secret=gateway_secret,
        policy=_policy(),
        journal_backend=backend,
        journal=journal,
    )


def _raise_http(exc: RealTradingApiFailure) -> NoReturn:
    detail: dict[str, Any] = {
        "code": exc.code,
        "message": exc.message,
        "sandbox": False,
        "real_money": True,
    }
    if exc.tracking_id:
        detail["tracking_id"] = exc.tracking_id
    if exc.ambiguous_submission:
        detail["submission_state"] = "unknown_do_not_resubmit"
    raise HTTPException(status_code=exc.http_status, detail=detail) from exc


def _execution_status(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("executionReportStatus") or payload.get(
        "execution_report_status"
    )
    return None if value is None else str(value)


class RealTradingStatusResponse(BaseModel):
    status: str
    enabled: bool
    configured: bool
    mutation_routes_registered: bool
    execution_ready: bool
    masked_account: str | None = None
    max_order_rub: str | None = None
    max_daily_rub: str | None = None
    confirmation_ttl_seconds: int | None = None
    market_max_age_seconds: int | None = None
    durable_journal: bool
    journal_backend: str | None = None
    journal_integrity: str
    proposal_rows: int | None = None
    real_money: bool
    real_trading_methods: bool
    sandbox: bool
    error_code: str | None = None
    warning: str | None = None


class RealTradePrepareRequest(BaseModel):
    instrument_uid: str = Field(min_length=1, max_length=120)
    direction: Literal["BUY", "SELL"]
    quantity_lots: int = Field(ge=1, le=1_000_000)
    limit_price: str = Field(pattern=r"^\d{1,18}(?:\.\d{1,9})?$")
    rationale: str = Field(min_length=1, max_length=1500)


class RealTradePrepareResponse(BaseModel):
    status: Literal["confirmation_required"]
    proposal_id: str
    order_id: str
    masked_account: str
    instrument_uid: str
    ticker: str
    isin: str | None
    direction: str
    quantity_lots: int
    order_type: Literal["LIMIT"]
    price_type: Literal["CURRENCY"]
    time_in_force: Literal["DAY"]
    limit_price: str
    preview_total_rub: str
    preview_commission_rub: str
    available_lots: int
    market_retrieved_at: str
    created_at: str
    expires_at: str
    confirmation_phrase: str
    execution_ready: bool
    requires_user_confirmation: bool
    real_money: bool
    real_trading_methods: bool
    sandbox: bool
    warning: str


class RealTradeExecuteRequest(BaseModel):
    proposal_id: str = Field(min_length=36, max_length=36)
    confirmation_phrase: str = Field(min_length=1, max_length=120)


class RealTradeExecuteResponse(BaseModel):
    status: str
    proposal_id: str
    order_id: str
    masked_account: str
    instrument_uid: str
    ticker: str
    direction: str
    quantity_lots: int
    limit_price: str
    proposal_state: str
    broker_execution_report_status: str | None
    broker_fill_confirmed: bool
    broker_response_json: str
    idempotent_replay: bool
    real_money: bool
    real_trading_methods: bool
    sandbox: bool
    warning: str


class RealOrderStateResponse(BaseModel):
    status: str
    proposal_id: str
    order_id: str
    masked_account: str
    proposal_state: str
    broker_execution_report_status: str | None
    broker_fill_confirmed: bool
    broker_response_json: str
    real_money: bool
    real_trading_methods: bool
    sandbox: bool


def register_real_trading_gateway(
    *,
    app: FastAPI,
    base: Any,
    app_version: str,
    expected_account_id_provider: ExpectedAccountIdProvider,
    market_snapshot_provider: ReadOnlyMarketSnapshotProvider,
    journal_path: Path = PRODUCTION_JOURNAL_PATH,
) -> bool:
    del app_version
    app_id = id(app)
    if app_id in _REGISTERED_APP_IDS:
        return True
    _REGISTERED_APP_IDS.add(app_id)

    runtime: StaticRuntimeV1 | None = None
    static_error: RealTradingApiFailure | None = None
    try:
        runtime = _static_runtime(journal_path)
    except RealTradingApiFailure as exc:
        static_error = exc

    dependency = Depends(base.require_gateway_key)

    def _service() -> RealTradingServiceV1:
        if runtime is None:
            assert static_error is not None
            raise static_error
        try:
            expected_account_id = expected_account_id_provider().strip()
        except Exception as exc:
            raise RealTradingApiFailure(
                code="REAL_READ_ONLY_ACCOUNT_BINDING_UNAVAILABLE",
                message="Read-only account binding could not be resolved.",
                http_status=503,
            ) from exc
        if not expected_account_id:
            raise RealTradingApiFailure(
                code="REAL_EXPECTED_ACCOUNT_REQUIRED",
                message="Read-only account binding is empty.",
                http_status=503,
            )

        def _market(instrument_uid: str) -> RealMarketContextV1:
            try:
                payload = market_snapshot_provider(instrument_uid)
            except Exception as exc:
                raise RealTradingApiFailure(
                    code="REAL_READ_ONLY_MARKET_UNAVAILABLE",
                    message="Trusted read-only market snapshot is unavailable.",
                    http_status=503,
                ) from exc
            return market_context_from_snapshot(payload, instrument_uid=instrument_uid)

        return RealTradingServiceV1(
            token=runtime.token,
            gateway_secret=runtime.gateway_secret,
            expected_account_id=expected_account_id,
            policy=runtime.policy,
            journal=runtime.journal,
            market_context_provider=_market,
        )

    @app.get(
        "/real-trading/status",
        operation_id="getRealTradingStatus",
        summary="Verify real-money trading readiness without submitting an order",
        response_model=RealTradingStatusResponse,
        dependencies=[dependency],
    )
    def real_trading_status() -> RealTradingStatusResponse:
        if runtime is None:
            assert static_error is not None
            return RealTradingStatusResponse(
                status="not_ready",
                enabled=True,
                configured=bool(os.environ.get(REAL_TRADING_TOKEN_ENV, "").strip()),
                mutation_routes_registered=False,
                execution_ready=False,
                durable_journal=False,
                journal_backend=_journal_backend_name(),
                journal_integrity="unavailable",
                real_money=True,
                real_trading_methods=False,
                sandbox=False,
                error_code=static_error.code,
                warning="No real-money mutation route is published in this state.",
            )
        try:
            service = _service()
            account_id, _ = service.resolve_bound_account()
            rows = runtime.journal.integrity_check()
        except RealTradingApiFailure as exc:
            return RealTradingStatusResponse(
                status="not_ready",
                enabled=True,
                configured=True,
                mutation_routes_registered=True,
                execution_ready=False,
                max_order_rub=format(runtime.policy.max_order_rub, "f"),
                max_daily_rub=format(runtime.policy.max_daily_rub, "f"),
                confirmation_ttl_seconds=runtime.policy.confirmation_ttl_seconds,
                market_max_age_seconds=runtime.policy.market_max_age_seconds,
                durable_journal=True,
                journal_backend=runtime.journal_backend,
                journal_integrity="ok",
                real_money=True,
                real_trading_methods=True,
                sandbox=False,
                error_code=exc.code,
                warning="No real order was submitted.",
            )
        return RealTradingStatusResponse(
            status="ready",
            enabled=True,
            configured=True,
            mutation_routes_registered=True,
            execution_ready=True,
            masked_account=mask_account_id(account_id),
            max_order_rub=format(runtime.policy.max_order_rub, "f"),
            max_daily_rub=format(runtime.policy.max_daily_rub, "f"),
            confirmation_ttl_seconds=runtime.policy.confirmation_ttl_seconds,
            market_max_age_seconds=runtime.policy.market_max_age_seconds,
            durable_journal=True,
            journal_backend=runtime.journal_backend,
            journal_integrity="ok",
            proposal_rows=rows,
            real_money=True,
            real_trading_methods=True,
            sandbox=False,
            warning=(
                "Readiness is not authorization: each order still requires a fresh "
                "proposal and exact short-lived owner confirmation."
            ),
        )

    # Fail closed: flag=true is not enough. Mutations are omitted from OpenAPI
    # unless token, hard limits and durable journal initialize successfully.
    if runtime is None:
        return False

    @app.post(
        "/real-trading/trade/prepare",
        operation_id="prepareRealTrade",
        summary="Prepare a real-money LIMIT order without submitting it",
        response_model=RealTradePrepareResponse,
        dependencies=[dependency],
    )
    def real_prepare_trade(request: RealTradePrepareRequest) -> RealTradePrepareResponse:
        try:
            proposal = _service().prepare_trade(
                instrument_uid=request.instrument_uid,
                direction=request.direction,
                quantity_lots=request.quantity_lots,
                limit_price=request.limit_price,
                rationale=request.rationale,
            )
        except RealTradingApiFailure as exc:
            _raise_http(exc)
        return RealTradePrepareResponse(
            status="confirmation_required",
            proposal_id=proposal.proposal_id,
            order_id=proposal.order_id,
            masked_account=mask_account_id(proposal.account_id),
            instrument_uid=proposal.instrument_uid,
            ticker=proposal.ticker,
            isin=proposal.isin,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            order_type="LIMIT",
            price_type="CURRENCY",
            time_in_force="DAY",
            limit_price=format(proposal.limit_price, "f"),
            preview_total_rub=format(proposal.preview_total_rub, "f"),
            preview_commission_rub=format(proposal.preview_commission_rub, "f"),
            available_lots=proposal.available_lots,
            market_retrieved_at=proposal.market_retrieved_at.isoformat(),
            created_at=proposal.created_at.isoformat(),
            expires_at=proposal.expires_at.isoformat(),
            confirmation_phrase=proposal.confirmation_phrase,
            execution_ready=False,
            requires_user_confirmation=True,
            real_money=True,
            real_trading_methods=True,
            sandbox=False,
            warning="Nothing has been submitted yet.",
        )

    @app.post(
        "/real-trading/trade/execute",
        operation_id="executeRealTrade",
        summary="Submit exactly one confirmed real-money LIMIT order",
        response_model=RealTradeExecuteResponse,
        dependencies=[dependency],
        openapi_extra={"x-openai-isConsequential": True},
    )
    def real_execute_trade(request: RealTradeExecuteRequest) -> RealTradeExecuteResponse:
        try:
            proposal, replay = _service().execute_trade(
                request.proposal_id, request.confirmation_phrase
            )
        except RealTradingApiFailure as exc:
            _raise_http(exc)
        broker_status = _execution_status(proposal.broker_response_json)
        return RealTradeExecuteResponse(
            status="already_submitted" if replay else "submitted",
            proposal_id=proposal.proposal_id,
            order_id=proposal.order_id,
            masked_account=mask_account_id(proposal.account_id),
            instrument_uid=proposal.instrument_uid,
            ticker=proposal.ticker,
            direction=proposal.direction,
            quantity_lots=proposal.quantity_lots,
            limit_price=format(proposal.limit_price, "f"),
            proposal_state=proposal.state,
            broker_execution_report_status=broker_status,
            broker_fill_confirmed=broker_status == "EXECUTION_REPORT_STATUS_FILL",
            broker_response_json=proposal.broker_response_json or "{}",
            idempotent_replay=replay,
            real_money=True,
            real_trading_methods=True,
            sandbox=False,
            warning=(
                "submitted means the broker accepted the request path; a fill is "
                "reported only when the broker explicitly returns FILL."
            ),
        )

    @app.get(
        "/real-trading/order/state",
        operation_id="getRealOrderState",
        summary="Reconcile a real-money proposal by its original request id",
        response_model=RealOrderStateResponse,
        dependencies=[dependency],
    )
    def real_order_state(
        proposal_id: str = Query(..., min_length=36, max_length=36),
    ) -> RealOrderStateResponse:
        try:
            proposal = _service().reconcile_proposal(proposal_id)
        except RealTradingApiFailure as exc:
            _raise_http(exc)
        broker_status = _execution_status(proposal.broker_response_json)
        return RealOrderStateResponse(
            status="reconciled",
            proposal_id=proposal.proposal_id,
            order_id=proposal.order_id,
            masked_account=mask_account_id(proposal.account_id),
            proposal_state=proposal.state,
            broker_execution_report_status=broker_status,
            broker_fill_confirmed=broker_status == "EXECUTION_REPORT_STATUS_FILL",
            broker_response_json=proposal.broker_response_json or "{}",
            real_money=True,
            real_trading_methods=True,
            sandbox=False,
        )

    if hasattr(base, "CAPABILITIES") and "real_trading_v1" not in base.CAPABILITIES:
        base.CAPABILITIES.append("real_trading_v1")
    return True


def maybe_register_real_trading_gateway(
    *,
    app: FastAPI,
    base: Any,
    app_version: str,
    expected_account_id_provider: ExpectedAccountIdProvider,
    market_snapshot_provider: ReadOnlyMarketSnapshotProvider,
    journal_path: Path = PRODUCTION_JOURNAL_PATH,
) -> bool:
    if not real_trading_enabled():
        return False
    return register_real_trading_gateway(
        app=app,
        base=base,
        app_version=app_version,
        expected_account_id_provider=expected_account_id_provider,
        market_snapshot_provider=market_snapshot_provider,
        journal_path=journal_path,
    )
