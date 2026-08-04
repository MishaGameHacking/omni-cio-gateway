from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.portfolio_plan import PlanMarketObservationV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=Decimal("0"), allow_inf_nan=False),
]
Bps = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("10000"), allow_inf_nan=False),
]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]


class PlanExecutionSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class PlanExecutionSessionState(StrEnum):
    PREPARED = "prepared"
    ACTIVE = "active"
    AWAITING_BROKER_RECONCILIATION = "awaiting_broker_reconciliation"
    AWAITING_PORTFOLIO_RECONCILIATION = "awaiting_portfolio_reconciliation"
    WAITING_NEXT_STAGE_DAY = "waiting_next_stage_day"
    HALTED = "halted"
    COMPLETED = "completed"


class PlanExecutionStageState(StrEnum):
    PENDING = "pending"
    PREPARED = "prepared"
    AWAITING_BROKER_RECONCILIATION = "awaiting_broker_reconciliation"
    BROKER_TERMINAL = "broker_terminal"
    FILLED = "filled"
    HALTED = "halted"


class PlanExecutionAttemptState(StrEnum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    ACTIVE = "active"
    TERMINAL = "terminal"
    EXPIRED = "expired"
    FAILED = "failed"
    UNKNOWN = "unknown"


class PlanExecutionHaltCode(StrEnum):
    PLAN_INVALID = "plan_invalid"
    PLAN_EXPIRED = "plan_expired"
    OWNER_APPROVAL_MISMATCH = "owner_approval_mismatch"
    PLAN_MARKET_DRIFT = "plan_market_drift"
    POLICY_CHANGED = "policy_changed"
    PORTFOLIO_PROGRESS_MISMATCH = "portfolio_progress_mismatch"
    CASH_RECONCILIATION_MISMATCH = "cash_reconciliation_mismatch"
    CURRENT_RISK_NOT_READY = "current_risk_not_ready"
    CURRENT_RISK_POLICY_BREACH = "current_risk_policy_breach"
    INSTRUMENT_BINDING_MISSING = "instrument_binding_missing"
    INSTRUMENT_BINDING_MISMATCH = "instrument_binding_mismatch"
    INSTRUMENT_TYPE_NOT_SUPPORTED = "instrument_type_not_supported"
    EXECUTION_EVIDENCE_MISSING = "execution_evidence_missing"
    EXECUTION_QUOTE_STALE = "execution_quote_stale"
    EXECUTION_PRICE_STEP_MISMATCH = "execution_price_step_mismatch"
    EXECUTION_PRICE_CHANGED = "execution_price_changed"
    EXECUTION_SPREAD_TOO_WIDE = "execution_spread_too_wide"
    EXECUTION_LIQUIDITY_DROPPED = "execution_liquidity_dropped"
    PREPARE_REJECTED = "prepare_rejected"
    SUBMIT_PREFLIGHT_CHANGED = "submit_preflight_changed"
    AMBIGUOUS_SUBMISSION = "ambiguous_submission"
    BROKER_RECONCILIATION_INCOMPLETE = "broker_reconciliation_incomplete"
    BROKER_REJECTED = "broker_rejected"
    BROKER_FILL_OVERFLOW = "broker_fill_overflow"
    PORTFOLIO_RECONCILIATION_TIMEOUT = "portfolio_reconciliation_timeout"
    JOURNAL_CONFLICT = "journal_conflict"


class PlanExecutionAdvanceAction(StrEnum):
    APPROVED = "approved"
    STAGE_PREPARED = "stage_prepared"
    STAGE_SUBMITTED = "stage_submitted"
    BROKER_ACTIVE = "broker_active"
    BROKER_TERMINAL = "broker_terminal"
    PORTFOLIO_RECONCILED = "portfolio_reconciled"
    WAITING_NEXT_STAGE_DAY = "waiting_next_stage_day"
    HALTED = "halted"
    COMPLETED = "completed"
    REPLAY = "replay"


class BrokerExecutionStatus(StrEnum):
    NEW = "EXECUTION_REPORT_STATUS_NEW"
    PARTIALLY_FILLED = "EXECUTION_REPORT_STATUS_PARTIALLYFILL"
    FILLED = "EXECUTION_REPORT_STATUS_FILL"
    CANCELLED = "EXECUTION_REPORT_STATUS_CANCELLED"
    REJECTED = "EXECUTION_REPORT_STATUS_REJECTED"
    UNSPECIFIED = "EXECUTION_REPORT_STATUS_UNSPECIFIED"


class PlanExecutionSettingsV1(ContractModel):
    quote_max_age_seconds: Annotated[int, Field(ge=1, le=60)] = 15
    future_tolerance_seconds: Annotated[int, Field(ge=0, le=60)] = 5
    max_execution_price_change_bps: Bps = Decimal("25")
    cash_reconciliation_tolerance_rub: NonNegativeDecimal = Decimal("1.00")
    max_portfolio_reconciliation_age_seconds: Annotated[
        int,
        Field(ge=5, le=3600),
    ] = 300
    one_staged_slice_per_moscow_day: Literal[True] = True
    autonomous_recurring_execution: Literal[False] = False


class PlanExecutionInstrumentBindingV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str, Field(min_length=8, max_length=128)]
    ticker: Annotated[str, Field(min_length=1, max_length=64)]
    isin: Annotated[str | None, Field(min_length=8, max_length=32)] = None
    instrument_type: Literal["share", "etf", "bond"]
    lot_size: PositiveInt
    source_sha256: Sha256
    as_of: datetime

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("execution instrument binding timestamp must be aware")
        return value.astimezone(timezone.utc)


class PlanExecutionQuoteV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    instrument_uid: Annotated[str, Field(min_length=8, max_length=128)]
    as_of: datetime
    source_sha256: Sha256
    currency: Literal["RUB"] = "RUB"
    lot_size: PositiveInt
    min_price_increment: PositiveDecimal
    best_bid: PositiveDecimal
    best_ask: PositiveDecimal
    spread_bps: Bps
    average_daily_turnover_base: PositiveDecimal
    top_of_book_depth_base: PositiveDecimal

    @field_validator("as_of")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("execution quote timestamp must be aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_book(self) -> PlanExecutionQuoteV1:
        if self.best_ask < self.best_bid:
            raise ValueError("execution quote ask cannot be below bid")
        midpoint = (self.best_ask + self.best_bid) / Decimal("2")
        computed = (self.best_ask - self.best_bid) / midpoint * Decimal("10000")
        if abs(computed - self.spread_bps) > Decimal("0.05"):
            raise ValueError("execution quote spread does not match bid/ask")
        return self

    def limit_price(self, side: PlanExecutionSide) -> Decimal:
        return self.best_ask if side is PlanExecutionSide.BUY else self.best_bid


class PlanExecutionLegEvidenceV1(ContractModel):
    observation: PlanMarketObservationV1
    quote: PlanExecutionQuoteV1

    @model_validator(mode="after")
    def bind_observation_to_quote(self) -> PlanExecutionLegEvidenceV1:
        observation = self.observation
        quote = self.quote
        if observation.stable_key != quote.stable_key:
            raise ValueError("plan execution evidence stable keys must match")
        if observation.observed_at != quote.as_of:
            raise ValueError("plan execution observation and quote times must match")
        if observation.spread_bps != quote.spread_bps:
            raise ValueError("plan execution observation and quote spread must match")
        if (
            observation.average_daily_turnover_base
            != quote.average_daily_turnover_base
            or observation.top_of_book_depth_base
            != quote.top_of_book_depth_base
        ):
            raise ValueError("plan execution observation liquidity must match quote")
        return self


class PlanExecutionPositionV1(ContractModel):
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    lots: NonNegativeInt


class PlanExecutionCurrentStateV1(ContractModel):
    observed_at: datetime
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    base_currency: Literal["RUB"] = "RUB"
    cash_base: NonNegativeDecimal
    positions: tuple[PlanExecutionPositionV1, ...]
    risk_assessment_sha256: Sha256
    risk_decision_ready: bool
    risk_policy_compliant: bool
    risk_blocker_codes: tuple[Annotated[str, Field(min_length=1, max_length=128)], ...] = ()
    strategy_selection_sha256: Sha256
    optimizer_sha256: Sha256
    target_risk_assessment_sha256: Sha256
    source_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("observed_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("execution current-state timestamp must be aware")
        return value.astimezone(timezone.utc)

    @field_validator("positions", mode="before")
    @classmethod
    def normalize_positions(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("execution positions must be a collection")
        return tuple(sorted(value, key=lambda row: _key(row, "stable_key")))

    @field_validator("risk_blocker_codes", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("risk blocker codes must be a collection")
        return tuple(sorted(set(value)))

    @field_validator("source_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("execution state sources must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("execution state sources cannot be empty")
        return result

    @model_validator(mode="after")
    def unique_positions(self) -> PlanExecutionCurrentStateV1:
        keys = [row.stable_key for row in self.positions]
        if len(keys) != len(set(keys)):
            raise ValueError("execution current positions must have unique keys")
        return self


class PlanExecutionBrokerSnapshotV1(ContractModel):
    proposal_id: Annotated[str, Field(min_length=8, max_length=128)]
    order_request_id: Annotated[str, Field(min_length=8, max_length=128)]
    status: BrokerExecutionStatus
    lots_requested: PositiveInt
    lots_executed: NonNegativeInt
    total_order_amount_rub: NonNegativeDecimal
    executed_commission_rub: NonNegativeDecimal
    executed_order_price_rub: NonNegativeDecimal | None = None
    response_sha256: Sha256

    @model_validator(mode="after")
    def validate_lots(self) -> PlanExecutionBrokerSnapshotV1:
        if self.lots_executed > self.lots_requested:
            raise ValueError("broker executed lots cannot exceed requested lots")
        if self.status is BrokerExecutionStatus.FILLED and (
            self.lots_executed != self.lots_requested
        ):
            raise ValueError("filled broker status requires every requested lot")
        return self

    @property
    def terminal(self) -> bool:
        return self.status in {
            BrokerExecutionStatus.FILLED,
            BrokerExecutionStatus.CANCELLED,
            BrokerExecutionStatus.REJECTED,
        }


class PlanExecutionAttemptV1(ContractModel):
    attempt_index: PositiveInt
    quantity_lots: PositiveInt
    state: PlanExecutionAttemptState
    proposal_id: Annotated[str | None, Field(min_length=8, max_length=128)] = None
    order_request_id: Annotated[str | None, Field(min_length=8, max_length=128)] = None
    limit_price: PositiveDecimal | None = None
    prepared_at: datetime | None = None
    submitted_at: datetime | None = None
    reconciled_at: datetime | None = None
    broker_status: BrokerExecutionStatus | None = None
    lots_executed: NonNegativeInt = 0
    total_order_amount_rub: NonNegativeDecimal = Decimal("0")
    executed_commission_rub: NonNegativeDecimal = Decimal("0")
    broker_response_sha256: Sha256 | None = None
    idempotent_replay: bool = False
    failure_code: Annotated[str | None, Field(min_length=1, max_length=128)] = None

    @field_validator("prepared_at", "submitted_at", "reconciled_at")
    @classmethod
    def normalize_optional_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan execution attempt timestamp must be aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_attempt(self) -> PlanExecutionAttemptV1:
        prepared_states = {
            PlanExecutionAttemptState.PREPARED,
            PlanExecutionAttemptState.SUBMITTED,
            PlanExecutionAttemptState.ACTIVE,
            PlanExecutionAttemptState.TERMINAL,
            PlanExecutionAttemptState.EXPIRED,
            PlanExecutionAttemptState.FAILED,
            PlanExecutionAttemptState.UNKNOWN,
        }
        if self.state in prepared_states and (
            self.proposal_id is None
            or self.order_request_id is None
            or self.limit_price is None
            or self.prepared_at is None
        ):
            raise ValueError("prepared execution attempt requires proposal identity and price")
        if self.lots_executed > self.quantity_lots:
            raise ValueError("execution attempt cannot execute more than requested")
        if self.state is PlanExecutionAttemptState.TERMINAL:
            if self.broker_status is None or self.reconciled_at is None:
                raise ValueError("terminal attempt requires broker reconciliation")
        return self


class PlanExecutionStageV1(ContractModel):
    stage_id: Sha256
    leg_sequence: PositiveInt
    stable_key: Annotated[str, Field(min_length=3, max_length=256)]
    side: PlanExecutionSide
    stage_index: PositiveInt
    stage_count: PositiveInt
    planned_lots: PositiveInt
    broker_terminal_lots: NonNegativeInt = 0
    portfolio_reconciled_lots: NonNegativeInt = 0
    state: PlanExecutionStageState = PlanExecutionStageState.PENDING
    attempts: tuple[PlanExecutionAttemptV1, ...] = ()
    not_before_moscow_date: date
    last_submission_moscow_date: date | None = None

    @field_validator("attempts", mode="before")
    @classmethod
    def normalize_attempts(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("execution attempts must be a collection")
        return tuple(sorted(value, key=lambda row: int(_key(row, "attempt_index"))))

    @model_validator(mode="after")
    def validate_stage(self) -> PlanExecutionStageV1:
        if self.stage_index > self.stage_count:
            raise ValueError("stage index cannot exceed stage count")
        if self.broker_terminal_lots > self.planned_lots:
            raise ValueError("broker terminal lots cannot exceed stage lots")
        if self.portfolio_reconciled_lots > self.broker_terminal_lots:
            raise ValueError("portfolio-reconciled lots cannot exceed broker-terminal lots")
        indices = [row.attempt_index for row in self.attempts]
        if indices != list(range(1, len(indices) + 1)):
            raise ValueError("execution attempt indices must be contiguous")
        terminal_lots = sum(
            row.lots_executed
            for row in self.attempts
            if row.state is PlanExecutionAttemptState.TERMINAL
        )
        if self.broker_terminal_lots != terminal_lots:
            raise ValueError("stage broker-terminal lots must reconcile to attempts")
        if self.state is PlanExecutionStageState.FILLED and (
            self.portfolio_reconciled_lots != self.planned_lots
        ):
            raise ValueError("filled stage requires all lots portfolio-reconciled")
        return self

    @property
    def remaining_lots(self) -> int:
        return self.planned_lots - self.broker_terminal_lots


class PlanExecutionInstrumentStateV1(ContractModel):
    binding: PlanExecutionInstrumentBindingV1
    stages: Annotated[tuple[PlanExecutionStageV1, ...], Field(min_length=1)]


class PlanExecutionSessionV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    execution_id: Sha256
    plan_sha256: Sha256
    initial_review_sha256: Sha256
    prepared_at: datetime
    last_reviewed_at: datetime
    last_review_sha256: Sha256
    state: PlanExecutionSessionState
    instrument_states: Annotated[
        tuple[PlanExecutionInstrumentStateV1, ...],
        Field(min_length=1),
    ]
    owner_approved: bool = False
    owner_approved_at: datetime | None = None
    owner_approval_evidence_sha256: Sha256 | None = None
    confirmed_cash_delta_rub: Decimal = Decimal("0")
    estimated_tax_allowance_rub: NonNegativeDecimal = Decimal("0")
    halt_code: PlanExecutionHaltCode | None = None
    halt_message: Annotated[str | None, Field(min_length=1, max_length=512)] = None
    revision: NonNegativeInt = 0
    real_money: Literal[True] = True
    autonomous_execution: Literal[False] = False
    margin_allowed: Literal[False] = False
    short_allowed: Literal[False] = False
    withdrawal_allowed: Literal[False] = False
    transfer_allowed: Literal[False] = False

    @field_validator("prepared_at", "last_reviewed_at", "owner_approved_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("plan execution session timestamp must be aware")
        return value.astimezone(timezone.utc)

    @field_validator("instrument_states", mode="before")
    @classmethod
    def normalize_instruments(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("execution instrument states must be a collection")
        return tuple(sorted(value, key=lambda row: _binding_key(row)))

    @model_validator(mode="after")
    def validate_session(self) -> PlanExecutionSessionV1:
        keys = [row.binding.stable_key for row in self.instrument_states]
        if len(keys) != len(set(keys)):
            raise ValueError("execution session instrument keys must be unique")
        if self.last_reviewed_at < self.prepared_at:
            raise ValueError("last execution review cannot precede preparation")
        if self.owner_approved != (self.owner_approved_at is not None):
            raise ValueError("owner approval timestamp must match approval state")
        if self.owner_approved != (self.owner_approval_evidence_sha256 is not None):
            raise ValueError("owner approval evidence must match approval state")
        if self.state is PlanExecutionSessionState.HALTED:
            if self.halt_code is None or self.halt_message is None:
                raise ValueError("halted execution session requires halt reason")
        elif self.halt_code is not None or self.halt_message is not None:
            raise ValueError("non-halted execution session cannot carry halt reason")
        if self.state is PlanExecutionSessionState.COMPLETED:
            if any(
                stage.state is not PlanExecutionStageState.FILLED
                for item in self.instrument_states
                for stage in item.stages
            ):
                raise ValueError("completed execution requires every stage filled")
        return self


class PlanExecutionAdvanceResultV1(ContractModel):
    action: PlanExecutionAdvanceAction
    session: PlanExecutionSessionV1
    stage_id: Sha256 | None = None
    proposal_id: Annotated[str | None, Field(min_length=8, max_length=128)] = None
    message: Annotated[str, Field(min_length=1, max_length=512)]
    broker_snapshot: PlanExecutionBrokerSnapshotV1 | None = None
    execution_authorized: bool
    trading_methods: Literal[True] = True

    @model_validator(mode="after")
    def validate_authority(self) -> PlanExecutionAdvanceResultV1:
        expected = self.session.owner_approved and self.session.state not in {
            PlanExecutionSessionState.HALTED,
            PlanExecutionSessionState.COMPLETED,
        }
        if self.execution_authorized != expected:
            raise ValueError("execution result authority must match approved active session")
        return self


def _key(row: object, attribute: str) -> str:
    if isinstance(row, dict):
        value = row.get(attribute)
    else:
        value = getattr(row, attribute, None)
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def _binding_key(row: object) -> str:
    if isinstance(row, dict):
        binding = row.get("binding")
    else:
        binding = getattr(row, "binding", None)
    return _key(binding, "stable_key")
