from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import hashlib
import hmac
import json
import time
from typing import Annotated, Any

import grpc
from google.protobuf.json_format import MessageToDict
from pydantic import Field, field_validator
from t_tech.invest import GetOperationsByCursorRequest, InstrumentIdType

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    ContractModel,
    DataIssue,
    DataQuality,
    IssueSeverity,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.domain import (
    BrokerProvider,
    canonical_broker_account_id,
)
from omni_cio.contracts.v1.portfolio import (
    CashBalanceV1,
    InstrumentIdentity,
    InstrumentType,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    ValuationBasis,
)


ACCOUNT_STATUS_NAMES = {
    0: "ACCOUNT_STATUS_UNSPECIFIED",
    1: "ACCOUNT_STATUS_NEW",
    2: "ACCOUNT_STATUS_OPEN",
    3: "ACCOUNT_STATUS_CLOSED",
    4: "ACCOUNT_STATUS_ALL",
}
ACCESS_LEVEL_NAMES = {
    0: "ACCOUNT_ACCESS_LEVEL_UNSPECIFIED",
    1: "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
    2: "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
    3: "ACCOUNT_ACCESS_LEVEL_NO_ACCESS",
}
TRANSIENT_GRPC_CODES = {
    "DEADLINE_EXCEEDED",
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
}
_OPERATION_UNSTABLE_TOP_LEVEL_FIELDS = frozenset(
    {
        "cursor",
        "broker_account_id",
        "id",
        "parent_operation_id",
    }
)


class TInvestReadAdapterError(RuntimeError):
    """Base fail-closed broker read adapter error."""


class AccountBindingError(TInvestReadAdapterError):
    """Accessible broker account does not match the expected OWNER binding."""


class BrokerDataError(TInvestReadAdapterError):
    """Broker payload cannot be normalized without losing semantic safety."""


class CursorProgressError(TInvestReadAdapterError):
    """Cursor pagination failed to make deterministic forward progress."""


class RetryExhaustedError(TInvestReadAdapterError):
    """A retryable read failed after the bounded retry budget."""


class FreshnessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"


class TInvestReadPolicyV1(ContractModel):
    stale_after_seconds: Annotated[int, Field(ge=1, le=3600)] = 300
    max_operation_pages: Annotated[int, Field(ge=1, le=100)] = 20
    operation_page_limit: Annotated[int, Field(ge=1, le=1000)] = 1000
    max_attempts: Annotated[int, Field(ge=1, le=8)] = 3
    initial_backoff_seconds: Annotated[Decimal, Field(gt=0, le=Decimal("30"))] = (
        Decimal("0.5")
    )
    max_backoff_seconds: Annotated[Decimal, Field(gt=0, le=Decimal("60"))] = (
        Decimal("4")
    )
    jitter_ratio: Annotated[Decimal, Field(ge=0, le=Decimal("0.5"))] = Decimal("0.2")
    fallback_requests_per_minute: Annotated[int, Field(ge=1, le=600)] = 40
    tariff_safety_ratio: Annotated[Decimal, Field(gt=0, le=1)] = Decimal("0.8")


class BrokerAccountBindingV1(ContractModel):
    broker_account_id: Annotated[
        str,
        Field(pattern=r"^broker-account:v1:[a-f0-9]{64}$"),
    ]
    account_fingerprint_sha256: Annotated[
        str,
        Field(pattern=r"^[a-f0-9]{64}$"),
    ]
    masked_label: Annotated[str, Field(min_length=4, max_length=96)]
    account_type: Annotated[str | None, Field(max_length=64)] = None
    access_level: Annotated[str | None, Field(max_length=64)] = None

    @field_validator("masked_label")
    @classmethod
    def require_masked_label(cls, value: str) -> str:
        if "*" not in value:
            raise ValueError("broker account label must stay masked")
        return value


class FreshnessMetadataV1(ContractModel):
    retrieved_at: datetime
    evaluated_at: datetime
    age_seconds: Annotated[Decimal, Field(ge=0)]
    stale_after_seconds: Annotated[int, Field(ge=1)]
    state: FreshnessState

    @field_validator("retrieved_at", "evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("freshness timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)


class ThrottleMetadataV1(ContractModel):
    source: Annotated[str, Field(pattern=r"^(broker_tariff|fallback)$")]
    effective_requests_per_minute: Annotated[Decimal, Field(gt=0)]
    minimum_interval_seconds: Annotated[Decimal, Field(ge=0)]


class NormalizedOperationV1(ContractModel):
    fingerprint_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    occurred_at: datetime | None = None
    operation_type: Annotated[str, Field(min_length=1, max_length=96)]
    state: Annotated[str, Field(min_length=1, max_length=96)]
    instrument_uid: Annotated[str | None, Field(max_length=128)] = None
    position_uid: Annotated[str | None, Field(max_length=128)] = None
    figi: Annotated[str | None, Field(max_length=32)] = None
    payment: Money | None = None
    price: Money | None = None
    commission: Money | None = None
    quantity: Decimal | None = None
    quantity_done: Decimal | None = None

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class TInvestSnapshotResultV1(ContractModel):
    account: BrokerAccountBindingV1
    snapshot: PortfolioSnapshotV1
    freshness: FreshnessMetadataV1
    throttle: ThrottleMetadataV1
    portfolio_total: Money | None = None
    broker_position_count: Annotated[int, Field(ge=0)]
    normalized_position_count: Annotated[int, Field(ge=0)]
    unresolved_position_count: Annotated[int, Field(ge=0)]


class TInvestOperationsResultV1(ContractModel):
    account: BrokerAccountBindingV1
    retrieved_at: datetime
    throttle: ThrottleMetadataV1
    operations: tuple[NormalizedOperationV1, ...]
    pages_loaded: Annotated[int, Field(ge=1)]
    duplicates_removed: Annotated[int, Field(ge=0)]
    truncated: bool
    next_cursor: Annotated[str | None, Field(max_length=2048)] = None

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str) and enum_name:
        return enum_name
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    return str(value)


def _message_to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        safe = _json_safe(value)
        if isinstance(safe, dict):
            return safe
    if hasattr(value, "DESCRIPTOR"):
        result = MessageToDict(
            value,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )
        safe = _json_safe(result)
        if isinstance(safe, dict):
            return safe
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        safe = _json_safe(to_dict())
        if isinstance(safe, dict):
            return safe
    if is_dataclass(value) and not isinstance(value, type):
        safe = _json_safe(asdict(value))
        if isinstance(safe, dict):
            return safe
    raise BrokerDataError("BROKER_RESPONSE_SHAPE_UNSUPPORTED")


def _enum_name(value: Any, mapping: dict[int, str]) -> str:
    if value is None:
        return "UNKNOWN"
    enum_name = getattr(value, "name", None)
    if isinstance(enum_name, str) and enum_name:
        return enum_name
    raw = getattr(value, "value", value)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return mapping.get(raw, str(raw))
    text = str(raw).strip()
    if text.isdigit():
        return mapping.get(int(text), text)
    return text.rsplit(".", 1)[-1] or "UNKNOWN"


def _aware_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            result = datetime.fromisoformat(text)
        except ValueError as exc:
            raise BrokerDataError("BROKER_TIMESTAMP_INVALID") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise BrokerDataError("BROKER_TIMESTAMP_NAIVE")
    return result.astimezone(timezone.utc)


def _decimal(value: Any, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise BrokerDataError(f"{field_name}_INVALID_DECIMAL")
    if isinstance(value, dict):
        try:
            units = Decimal(str(value.get("units", "0") or "0"))
            nano = Decimal(str(value.get("nano", "0") or "0"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise BrokerDataError(f"{field_name}_INVALID_QUOTATION") from exc
        if nano < Decimal("-999999999") or nano > Decimal("999999999"):
            raise BrokerDataError(f"{field_name}_INVALID_NANO")
        return units + nano / Decimal("1000000000")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerDataError(f"{field_name}_INVALID_DECIMAL") from exc


def _optional_decimal(value: Any, *, field_name: str) -> Decimal | None:
    if value in (None, ""):
        return None
    return _decimal(value, field_name=field_name)


def _money(value: Any, *, field_name: str) -> Money | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        value = _message_to_dict(value)
    currency = str(value.get("currency", "") or "").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise BrokerDataError(f"{field_name}_CURRENCY_INVALID")
    amount = _decimal(value, field_name=field_name)
    return Money(amount=amount, currency=currency)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _account_fingerprint(raw_account_id: str) -> str:
    return _sha256(raw_account_id.encode("utf-8"))


def _mask_account(raw_account_id: str) -> str:
    suffix = raw_account_id[-4:] if raw_account_id else ""
    return f"***{suffix}" if suffix else "****"


def _accounts(response: Any) -> list[Any]:
    direct = _field(response, "accounts")
    if direct is not None:
        return list(direct)
    data = _message_to_dict(response)
    raw = data.get("accounts", [])
    if not isinstance(raw, list):
        raise BrokerDataError("BROKER_ACCOUNTS_SHAPE_INVALID")
    return raw


def _binding_for_account(account: Any) -> tuple[str, BrokerAccountBindingV1]:
    raw_account_id = str(_field(account, "id", "") or "").strip()
    if not raw_account_id:
        raise AccountBindingError("ACCOUNT_ID_MISSING")
    fingerprint = _account_fingerprint(raw_account_id)
    return raw_account_id, BrokerAccountBindingV1(
        broker_account_id=canonical_broker_account_id(
            BrokerProvider.T_INVEST,
            fingerprint,
        ),
        account_fingerprint_sha256=fingerprint,
        masked_label=_mask_account(raw_account_id),
        account_type=_enum_name(_field(account, "type"), {}),
        access_level=_enum_name(
            _field(account, "access_level"),
            ACCESS_LEVEL_NAMES,
        ),
    )


def _single_open_account(response: Any) -> tuple[str, BrokerAccountBindingV1]:
    accessible = _accounts(response)
    open_accounts = [
        account
        for account in accessible
        if _enum_name(_field(account, "status"), ACCOUNT_STATUS_NAMES)
        == "ACCOUNT_STATUS_OPEN"
        and _enum_name(_field(account, "access_level"), ACCESS_LEVEL_NAMES)
        != "ACCOUNT_ACCESS_LEVEL_NO_ACCESS"
    ]
    if not open_accounts:
        raise AccountBindingError("NO_ACCESSIBLE_OPEN_ACCOUNT")
    if len(open_accounts) != 1:
        raise AccountBindingError("MULTIPLE_ACCESSIBLE_OPEN_ACCOUNTS")
    return _binding_for_account(open_accounts[0])


def discover_owner_account_binding(
    client_factory: Callable[[], Any],
) -> BrokerAccountBindingV1:
    """OWNER-local discovery only; does not persist or authorize an account."""
    with client_factory() as client:
        response = client.users.get_accounts()
        _, binding = _single_open_account(response)
        return binding


def evaluate_freshness(
    retrieved_at: datetime,
    *,
    evaluated_at: datetime,
    stale_after_seconds: int,
) -> FreshnessMetadataV1:
    retrieved = _aware_utc(retrieved_at)
    evaluated = _aware_utc(evaluated_at)
    if retrieved is None or evaluated is None:
        raise BrokerDataError("FRESHNESS_TIMESTAMP_MISSING")
    age = max(Decimal("0"), Decimal(str((evaluated - retrieved).total_seconds())))
    state = (
        FreshnessState.STALE
        if age > Decimal(stale_after_seconds)
        else FreshnessState.FRESH
    )
    return FreshnessMetadataV1(
        retrieved_at=retrieved,
        evaluated_at=evaluated,
        age_seconds=age,
        stale_after_seconds=stale_after_seconds,
        state=state,
    )


def _grpc_code_name(exc: BaseException) -> str:
    code_method = getattr(exc, "code", None)
    if not callable(code_method):
        return ""
    try:
        code = code_method()
    except Exception:
        return ""
    name = getattr(code, "name", None)
    if isinstance(name, str):
        return name
    return str(code).rsplit(".", 1)[-1]


def _instrument_type(value: Any) -> InstrumentType:
    text = _enum_name(value, {}).lower()
    mapping = (
        ("share", InstrumentType.SHARE),
        ("bond", InstrumentType.BOND),
        ("etf", InstrumentType.ETF),
        ("currency", InstrumentType.CURRENCY),
        ("future", InstrumentType.FUTURE),
        ("option", InstrumentType.OPTION),
        ("sp", InstrumentType.STRUCTURED_PRODUCT),
        ("structured", InstrumentType.STRUCTURED_PRODUCT),
    )
    for marker, result in mapping:
        if marker in text:
            return result
    return InstrumentType.OTHER


def _instrument_payload(response: Any) -> dict[str, Any]:
    data = _message_to_dict(response)
    instrument = data.get("instrument")
    if not isinstance(instrument, dict):
        raise BrokerDataError("INSTRUMENT_RESPONSE_MISSING")
    return instrument


def _strong_reference(position: dict[str, Any]) -> list[tuple[str, str]]:
    references: list[tuple[str, str]] = []
    for field_name in ("instrument_uid", "position_uid", "figi"):
        value = str(position.get(field_name, "") or "").strip()
        if value:
            references.append((field_name, value))
    return references


def _instrument_lookup_plan(
    position: dict[str, Any],
) -> list[tuple[Any, str, str]]:
    plan: list[tuple[Any, str, str]] = []
    uid = str(position.get("instrument_uid", "") or "").strip()
    if uid:
        plan.append((InstrumentIdType.INSTRUMENT_ID_TYPE_UID, uid, "instrument_uid"))
    position_uid = str(position.get("position_uid", "") or "").strip()
    if position_uid:
        plan.append(
            (
                InstrumentIdType.INSTRUMENT_ID_TYPE_POSITION_UID,
                position_uid,
                "position_uid",
            )
        )
    figi = str(position.get("figi", "") or "").strip()
    if figi:
        plan.append((InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, figi, "figi"))
    return plan


def _validate_identity(
    position: dict[str, Any],
    instrument: dict[str, Any],
) -> None:
    matches = 0
    for field_name, expected in _strong_reference(position):
        metadata_field = "uid" if field_name == "instrument_uid" else field_name
        actual = str(instrument.get(metadata_field, "") or "").strip()
        if not actual:
            continue
        if actual != expected:
            raise BrokerDataError("INSTRUMENT_IDENTITY_CONFLICT")
        matches += 1
    if not matches:
        raise BrokerDataError("INSTRUMENT_IDENTITY_UNVERIFIED")


def _instrument_identity(
    position: dict[str, Any],
    instrument: dict[str, Any],
) -> InstrumentIdentity:
    _validate_identity(position, instrument)
    currency = str(
        instrument.get("currency")
        or _field(position.get("current_price"), "currency", "")
        or ""
    ).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise BrokerDataError("INSTRUMENT_CURRENCY_INVALID")
    try:
        lot = int(instrument.get("lot") or 0)
    except (TypeError, ValueError) as exc:
        raise BrokerDataError("INSTRUMENT_LOT_INVALID") from exc
    if lot <= 0:
        raise BrokerDataError("INSTRUMENT_LOT_INVALID")
    name = str(instrument.get("name", "") or "").strip()
    if not name:
        raise BrokerDataError("INSTRUMENT_NAME_MISSING")
    return InstrumentIdentity(
        name=name,
        instrument_type=_instrument_type(
            instrument.get("instrument_type")
            or instrument.get("instrument_kind")
            or position.get("instrument_type")
        ),
        currency=currency,
        lot=lot,
        ticker=str(instrument.get("ticker") or "").strip() or None,
        isin=str(instrument.get("isin") or "").strip().upper() or None,
        figi=str(instrument.get("figi") or "").strip().upper() or None,
        uid=str(instrument.get("uid") or "").strip() or None,
        position_uid=str(instrument.get("position_uid") or "").strip() or None,
        class_code=str(instrument.get("class_code") or "").strip().upper() or None,
    )


def _portfolio_positions(response: Any) -> list[dict[str, Any]]:
    data = _message_to_dict(response)
    raw = data.get("positions", [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise BrokerDataError("PORTFOLIO_POSITIONS_SHAPE_INVALID")
    return list(raw)


def _virtual_positions(response: Any) -> list[dict[str, Any]]:
    data = _message_to_dict(response)
    raw = data.get("virtual_positions", [])
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise BrokerDataError("PORTFOLIO_VIRTUAL_POSITIONS_SHAPE_INVALID")
    return list(raw)


def _position_balances(response: Any) -> dict[str, Any]:
    return _message_to_dict(response)


def _cash_balances(
    positions_data: dict[str, Any],
    *,
    retrieved_at: datetime,
) -> tuple[CashBalanceV1, ...]:
    totals: dict[str, Decimal] = {}
    blocked_totals: dict[str, Decimal] = {}
    for row in positions_data.get("money", []) or []:
        money = _money(row, field_name="CASH_MONEY")
        if money is not None:
            totals[money.currency] = (
                totals.get(money.currency, Decimal("0")) + money.amount
            )
    for row in positions_data.get("blocked", []) or []:
        money = _money(row, field_name="CASH_BLOCKED")
        if money is not None:
            blocked_totals[money.currency] = (
                blocked_totals.get(money.currency, Decimal("0")) + money.amount
            )
    result: list[CashBalanceV1] = []
    for currency in sorted(set(totals) | set(blocked_totals)):
        reported = totals.get(currency, Decimal("0"))
        blocked = blocked_totals.get(currency, Decimal("0"))
        result.append(
            CashBalanceV1(
                reported=Money(amount=reported, currency=currency),
                available=Money(amount=reported - blocked, currency=currency),
                blocked=Money(amount=blocked, currency=currency),
                as_of=retrieved_at,
            )
        )
    return tuple(result)


def _portfolio_total(response: Any) -> Money | None:
    data = _message_to_dict(response)
    return _money(data.get("total_amount_portfolio"), field_name="PORTFOLIO_TOTAL")


def _operation_fingerprint(operation: dict[str, Any]) -> str:
    payload = {
        str(key): value
        for key, value in operation.items()
        if str(key) not in _OPERATION_UNSTABLE_TOP_LEVEL_FIELDS
    }
    return _sha256(_canonical_json(payload))


def _normalized_operation(operation: dict[str, Any]) -> NormalizedOperationV1:
    return NormalizedOperationV1(
        fingerprint_sha256=_operation_fingerprint(operation),
        occurred_at=_aware_utc(operation.get("date")),
        operation_type=_enum_name(operation.get("type"), {}),
        state=_enum_name(operation.get("state"), {}),
        instrument_uid=str(operation.get("instrument_uid") or "").strip() or None,
        position_uid=str(operation.get("position_uid") or "").strip() or None,
        figi=str(operation.get("figi") or "").strip().upper() or None,
        payment=_money(operation.get("payment"), field_name="OPERATION_PAYMENT"),
        price=_money(operation.get("price"), field_name="OPERATION_PRICE"),
        commission=_money(
            operation.get("commission"),
            field_name="OPERATION_COMMISSION",
        ),
        quantity=_optional_decimal(
            operation.get("quantity"),
            field_name="OPERATION_QUANTITY",
        ),
        quantity_done=_optional_decimal(
            operation.get("quantity_done"),
            field_name="OPERATION_QUANTITY_DONE",
        ),
    )


class TInvestReadAdapter:
    """Narrow production READ adapter. It intentionally exposes no SDK client."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any],
        expected_account_fingerprint_sha256: str,
        policy: TInvestReadPolicyV1 | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        random_unit: Callable[[], float] | None = None,
    ) -> None:
        if len(expected_account_fingerprint_sha256) != 64:
            raise ValueError("expected account fingerprint must be SHA-256")
        try:
            int(expected_account_fingerprint_sha256, 16)
        except ValueError as exc:
            raise ValueError("expected account fingerprint must be SHA-256") from exc
        self._client_factory = client_factory
        self._expected_account_fingerprint = expected_account_fingerprint_sha256
        self._policy = policy or TInvestReadPolicyV1()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._random_unit = random_unit or __import__("random").random
        self._minimum_interval = Decimal("60") / Decimal(
            self._policy.fallback_requests_per_minute
        )
        self._throttle_source = "fallback"
        self._last_call_at: float | None = None
        self._instrument_cache: dict[str, dict[str, Any]] = {}

    def _pace(self) -> None:
        if self._last_call_at is None:
            self._last_call_at = self._monotonic()
            return
        now = self._monotonic()
        elapsed = Decimal(str(max(0.0, now - self._last_call_at)))
        wait = self._minimum_interval - elapsed
        if wait > 0:
            self._sleeper(float(wait))
        self._last_call_at = self._monotonic()

    def _backoff(self, attempt: int) -> None:
        base = min(
            self._policy.max_backoff_seconds,
            self._policy.initial_backoff_seconds * (Decimal(2) ** (attempt - 1)),
        )
        jitter_unit = Decimal(str(max(0.0, min(1.0, self._random_unit()))))
        jitter = base * self._policy.jitter_ratio * jitter_unit
        self._sleeper(float(base + jitter))

    def _call_read(self, operation: str, call: Callable[[], Any]) -> Any:
        last_code = ""
        for attempt in range(1, self._policy.max_attempts + 1):
            self._pace()
            try:
                return call()
            except grpc.RpcError as exc:
                code = _grpc_code_name(exc)
                last_code = code or "UNKNOWN"
                if code not in TRANSIENT_GRPC_CODES:
                    raise TInvestReadAdapterError(
                        f"{operation}_PERMANENT_BROKER_ERROR:{last_code}"
                    ) from exc
                if attempt >= self._policy.max_attempts:
                    break
                self._backoff(attempt)
        raise RetryExhaustedError(f"{operation}_RETRY_EXHAUSTED:{last_code}")

    def _configure_throttle(self, client: Any) -> ThrottleMetadataV1:
        limits: list[int] = []
        try:
            response = client.users.get_user_tariff()
            data = _message_to_dict(response)
            unary_limits = data.get("unary_limits", [])
            if isinstance(unary_limits, list):
                for row in unary_limits:
                    if not isinstance(row, dict):
                        continue
                    try:
                        value = int(row.get("limit_per_minute") or 0)
                    except (TypeError, ValueError):
                        continue
                    if value > 0:
                        limits.append(value)
        except Exception:
            limits = []
        if limits:
            broker_limit = Decimal(min(limits))
            effective = max(
                Decimal("1"),
                broker_limit * self._policy.tariff_safety_ratio,
            )
            self._minimum_interval = Decimal("60") / effective
            self._throttle_source = "broker_tariff"
        else:
            effective = Decimal(self._policy.fallback_requests_per_minute)
            self._minimum_interval = Decimal("60") / effective
            self._throttle_source = "fallback"
        return ThrottleMetadataV1(
            source=self._throttle_source,
            effective_requests_per_minute=effective,
            minimum_interval_seconds=self._minimum_interval,
        )

    def _bind_account(
        self,
        client: Any,
    ) -> tuple[str, BrokerAccountBindingV1]:
        response = self._call_read("GET_ACCOUNTS", client.users.get_accounts)
        raw_account_id, binding = _single_open_account(response)
        if not hmac.compare_digest(
            binding.account_fingerprint_sha256,
            self._expected_account_fingerprint,
        ):
            raise AccountBindingError("OWNER_ACCOUNT_FINGERPRINT_MISMATCH")
        return raw_account_id, binding

    def _lookup_instrument(
        self,
        client: Any,
        position: dict[str, Any],
    ) -> dict[str, Any]:
        cache_key = next(
            (f"{kind}:{value}" for kind, value in _strong_reference(position)),
            "",
        )
        if cache_key and cache_key in self._instrument_cache:
            return dict(self._instrument_cache[cache_key])

        plan = _instrument_lookup_plan(position)
        if not plan:
            raise BrokerDataError("POSITION_STRONG_IDENTITY_MISSING")
        last_error: BaseException | None = None
        for id_type, identifier, field_name in plan:
            try:
                lookup_id_type = id_type
                lookup_identifier = identifier
                response = self._call_read(
                    "GET_INSTRUMENT_BY",
                    lambda: client.instruments.get_instrument_by(
                        id_type=lookup_id_type,
                        id=lookup_identifier,
                    ),
                )
                instrument = _instrument_payload(response)
                _validate_identity(position, instrument)
                for kind, value in _strong_reference(position):
                    self._instrument_cache[f"{kind}:{value}"] = dict(instrument)
                return instrument
            except TInvestReadAdapterError as exc:
                last_error = exc
                if "NOT_FOUND" not in str(exc) and "INVALID_ARGUMENT" not in str(exc):
                    break
            except BrokerDataError as exc:
                last_error = exc
                if field_name == plan[-1][2]:
                    break
        raise BrokerDataError("POSITION_INSTRUMENT_UNRESOLVED") from last_error

    def read_snapshot(
        self,
        *,
        allow_partial: bool = False,
        evaluated_at: datetime | None = None,
    ) -> TInvestSnapshotResultV1:
        with self._client_factory() as client:
            throttle = self._configure_throttle(client)
            raw_account_id, binding = self._bind_account(client)
            portfolio_response = self._call_read(
                "GET_PORTFOLIO",
                lambda: client.operations.get_portfolio(account_id=raw_account_id),
            )
            positions_response = self._call_read(
                "GET_POSITIONS",
                lambda: client.operations.get_positions(account_id=raw_account_id),
            )
            retrieved_at = self._clock().astimezone(timezone.utc)
            raw_positions = _portfolio_positions(portfolio_response)
            virtual_positions = _virtual_positions(portfolio_response)
            positions_data = _position_balances(positions_response)

            issues: list[DataIssue] = []
            limits_loading = positions_data.get("limits_loading_in_progress", False)
            if not isinstance(limits_loading, bool):
                raise BrokerDataError("POSITIONS_LIMITS_LOADING_FLAG_INVALID")
            if limits_loading:
                if not allow_partial:
                    raise BrokerDataError("POSITIONS_LIMITS_LOADING_IN_PROGRESS")
                issues.append(
                    DataIssue(
                        code="BROKER_LIMITS_LOADING_IN_PROGRESS",
                        severity=IssueSeverity.ERROR,
                        message="Broker position limits are still loading.",
                        component="tinvest_read_v1",
                    )
                )
            if virtual_positions:
                if not allow_partial:
                    raise BrokerDataError("PORTFOLIO_VIRTUAL_POSITIONS_UNSUPPORTED")
                issues.append(
                    DataIssue(
                        code="BROKER_VIRTUAL_POSITIONS_UNRESOLVED",
                        severity=IssueSeverity.ERROR,
                        message="Broker virtual positions are not silently omitted.",
                        component="tinvest_read_v1",
                    )
                )

            normalized: list[PortfolioPositionV1] = []
            for item in raw_positions:
                try:
                    instrument_payload = self._lookup_instrument(client, item)
                    identity = _instrument_identity(item, instrument_payload)
                    quantity = _decimal(
                        item.get("quantity"),
                        field_name="POSITION_QUANTITY",
                    )
                    blocked_lots = _optional_decimal(
                        item.get("blocked_lots"),
                        field_name="POSITION_BLOCKED_LOTS",
                    ) or Decimal("0")
                    depositary_blocked = item.get("blocked", False)
                    if not isinstance(depositary_blocked, bool):
                        raise BrokerDataError("POSITION_BLOCKED_FLAG_INVALID")
                    blocked = quantity if depositary_blocked else blocked_lots
                    if quantity < 0 or blocked < 0:
                        raise BrokerDataError("POSITION_NEGATIVE_QUANTITY")
                    current_price = _money(
                        item.get("current_price"),
                        field_name="POSITION_CURRENT_PRICE",
                    )
                    valuation = None
                    if current_price is not None:
                        valuation = PositionValuation(
                            basis=ValuationBasis.BROKER_REPORTED,
                            currency=current_price.currency,
                            as_of=retrieved_at,
                            unit_price=current_price.amount,
                        )
                    normalized.append(
                        PortfolioPositionV1(
                            instrument=identity,
                            quantity_units=quantity,
                            blocked_units=blocked,
                            valuation=valuation,
                        )
                    )
                except (BrokerDataError, ValueError) as exc:
                    if not allow_partial:
                        raise BrokerDataError(
                            "PORTFOLIO_NORMALIZATION_INCOMPLETE"
                        ) from exc
                    issues.append(
                        DataIssue(
                            code="BROKER_POSITION_UNRESOLVED",
                            severity=IssueSeverity.ERROR,
                            message="A broker position could not be safely normalized.",
                            component="tinvest_read_v1",
                        )
                    )

            unresolved = len(raw_positions) - len(normalized) + len(virtual_positions)
            complete = unresolved == 0 and not issues
            quality = QualityMetadata(
                quality=DataQuality.VERIFIED if complete else DataQuality.DEGRADED,
                completeness=(
                    Completeness.COMPLETE if complete else Completeness.PARTIAL
                ),
                issues=tuple(issues),
            )
            provenance = (
                SourceReference(
                    provider="T-Invest",
                    operation="GetAccounts",
                    retrieved_at=retrieved_at,
                    source_id=binding.masked_label,
                ),
                SourceReference(
                    provider="T-Invest",
                    operation="GetPortfolio",
                    retrieved_at=retrieved_at,
                    source_id=binding.masked_label,
                ),
                SourceReference(
                    provider="T-Invest",
                    operation="GetPositions",
                    retrieved_at=retrieved_at,
                    source_id=binding.masked_label,
                ),
            )
            snapshot = PortfolioSnapshotV1(
                metadata=ContractMetadata(
                    schema_name="portfolio_snapshot",
                    retrieved_at=retrieved_at,
                    account=AccountReference(
                        masked_id=binding.masked_label,
                        account_type=binding.account_type,
                    ),
                    provenance=provenance,
                    quality=quality,
                ),
                positions=tuple(normalized),
                cash_balances=_cash_balances(
                    positions_data,
                    retrieved_at=retrieved_at,
                ),
                totals_by_currency=(),
            )
            freshness = evaluate_freshness(
                retrieved_at,
                evaluated_at=evaluated_at or self._clock(),
                stale_after_seconds=self._policy.stale_after_seconds,
            )
            return TInvestSnapshotResultV1(
                account=binding,
                snapshot=snapshot,
                freshness=freshness,
                throttle=throttle,
                portfolio_total=_portfolio_total(portfolio_response),
                broker_position_count=len(raw_positions) + len(virtual_positions),
                normalized_position_count=len(normalized),
                unresolved_position_count=unresolved,
            )

    def read_operations(
        self,
        *,
        start_cursor: str = "",
    ) -> TInvestOperationsResultV1:
        if len(start_cursor) > 2048:
            raise CursorProgressError("OPERATIONS_START_CURSOR_TOO_LONG")
        with self._client_factory() as client:
            throttle = self._configure_throttle(client)
            raw_account_id, binding = self._bind_account(client)
            cursor = start_cursor
            pages_loaded = 0
            all_items: list[dict[str, Any]] = []
            has_more = False
            while pages_loaded < self._policy.max_operation_pages:
                request = GetOperationsByCursorRequest(
                    account_id=raw_account_id,
                    cursor=cursor,
                    limit=self._policy.operation_page_limit,
                    without_commissions=False,
                    without_trades=False,
                    without_overnights=True,
                )
                operation_request = request
                response = self._call_read(
                    "GET_OPERATIONS_BY_CURSOR",
                    lambda: client.operations.get_operations_by_cursor(
                        operation_request
                    ),
                )
                data = _message_to_dict(response)
                raw_items = data.get("items", [])
                if not isinstance(raw_items, list) or any(
                    not isinstance(item, dict) for item in raw_items
                ):
                    raise BrokerDataError("OPERATIONS_ITEMS_SHAPE_INVALID")
                all_items.extend(raw_items)
                pages_loaded += 1
                has_next = bool(data.get("has_next"))
                next_cursor = str(data.get("next_cursor", "") or "")
                if not has_next:
                    has_more = False
                    break
                has_more = True
                if not next_cursor or next_cursor == cursor:
                    raise CursorProgressError("OPERATIONS_CURSOR_DID_NOT_ADVANCE")
                if len(next_cursor) > 2048:
                    raise CursorProgressError("OPERATIONS_CURSOR_TOO_LONG")
                cursor = next_cursor

            seen: set[str] = set()
            operations: list[NormalizedOperationV1] = []
            duplicates = 0
            for item in all_items:
                fingerprint = _operation_fingerprint(item)
                if fingerprint in seen:
                    duplicates += 1
                    continue
                seen.add(fingerprint)
                operations.append(_normalized_operation(item))
            operations.sort(
                key=lambda row: (
                    row.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
                    row.fingerprint_sha256,
                ),
                reverse=True,
            )
            return TInvestOperationsResultV1(
                account=binding,
                retrieved_at=self._clock(),
                throttle=throttle,
                operations=tuple(operations),
                pages_loaded=pages_loaded,
                duplicates_removed=duplicates,
                truncated=has_more,
                next_cursor=cursor if has_more else None,
            )
