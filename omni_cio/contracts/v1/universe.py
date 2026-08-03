from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, QualityMetadata
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType


class UniverseSourceOperation(StrEnum):
    SHARES = "Shares"
    BONDS = "Bonds"
    ETFS = "Etfs"


REQUIRED_UNIVERSE_OPERATIONS: tuple[UniverseSourceOperation, ...] = (
    UniverseSourceOperation.SHARES,
    UniverseSourceOperation.BONDS,
    UniverseSourceOperation.ETFS,
)


def _normalize_operation_collection(value: object) -> tuple[UniverseSourceOperation, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError("completed_operations must be a collection")
    parsed = {UniverseSourceOperation(item) for item in value}
    return tuple(operation for operation in REQUIRED_UNIVERSE_OPERATIONS if operation in parsed)


class UniverseExclusionCode(StrEnum):
    API_NOT_AVAILABLE = "api_not_available"
    BUY_NOT_AVAILABLE = "buy_not_available"
    IIS_NOT_ALLOWED = "iis_not_allowed"
    QUALIFICATION_REQUIRED = "qualification_required"
    REQUIRED_TESTS_MISSING = "required_tests_missing"
    BLOCKED_TCA = "blocked_tca"


class UniverseAliasKind(StrEnum):
    UID = "uid"
    UID_PAYLOAD = "uid_payload"
    POSITION_UID = "position_uid"
    FIGI = "figi"
    ISIN = "isin"
    TICKER_CLASS_CODE = "ticker_class_code"


class UniverseAccountEligibilityV1(ContractModel):
    account_type: AccountPolicyType = AccountPolicyType.UNKNOWN
    qualified_investor: bool | None = None
    qualified_for_work_with: tuple[
        Annotated[str, Field(min_length=1, max_length=64)], ...
    ] = ()

    @field_validator("qualified_for_work_with", mode="before")
    @classmethod
    def normalize_test_permissions(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        if isinstance(value, bytes) or not isinstance(value, Iterable):
            raise ValueError("qualified_for_work_with must be a collection")
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


class UniverseInstrumentV1(ContractModel):
    source_operation: UniverseSourceOperation
    identity: InstrumentIdentity
    exchange: Annotated[str | None, Field(max_length=64)] = None
    real_exchange: Annotated[str | None, Field(max_length=64)] = None
    api_trade_available: bool
    buy_available: bool
    sell_available: bool
    for_iis: bool
    for_qual_investor: bool
    blocked_tca: bool
    otc: bool = False
    liquidity_sufficient: bool | None = None
    required_tests: tuple[
        Annotated[str, Field(min_length=1, max_length=64)], ...
    ] = ()

    @field_validator("required_tests", mode="before")
    @classmethod
    def normalize_required_tests(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, str):
            value = (value,)
        if isinstance(value, bytes) or not isinstance(value, Iterable):
            raise ValueError("required_tests must be a collection")
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))

    @model_validator(mode="after")
    def require_broker_identity(self) -> UniverseInstrumentV1:
        expected_types = {
            UniverseSourceOperation.SHARES: InstrumentType.SHARE,
            UniverseSourceOperation.BONDS: InstrumentType.BOND,
            UniverseSourceOperation.ETFS: InstrumentType.ETF,
        }
        if self.identity.instrument_type is not expected_types[self.source_operation]:
            raise ValueError("source operation and instrument type must agree")
        if not self.identity.uid:
            raise ValueError("broker universe row requires instrument UID")
        has_ticker = bool(self.identity.ticker)
        has_class_code = bool(self.identity.class_code)
        if has_ticker != has_class_code:
            raise ValueError("ticker and class_code must be present together")
        return self


class UniverseCatalogV1(ContractModel):
    retrieved_at: datetime
    completed_operations: tuple[UniverseSourceOperation, ...]
    instruments: tuple[UniverseInstrumentV1, ...] = ()
    source_errors: tuple[
        Annotated[str, Field(min_length=1, max_length=128)], ...
    ] = ()
    invalid_rows: Annotated[int, Field(ge=0)] = 0

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("completed_operations", mode="before")
    @classmethod
    def normalize_completed_operations(cls, value: object) -> object:
        return _normalize_operation_collection(value)

    @field_validator("source_errors", mode="before")
    @classmethod
    def normalize_source_errors(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("source_errors must be a collection")
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


class UniverseFetchBatchV1(ContractModel):
    catalog: UniverseCatalogV1
    account: UniverseAccountEligibilityV1
    account_source_error: Annotated[str | None, Field(max_length=128)] = None


class UniverseExcludedInstrumentV1(ContractModel):
    instrument: UniverseInstrumentV1
    reasons: Annotated[tuple[UniverseExclusionCode, ...], Field(min_length=1)]

    @field_validator("reasons", mode="before")
    @classmethod
    def normalize_reasons(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("reasons must be a collection")
        return tuple(sorted(set(value), key=str))


class UniverseIdentityConflictV1(ContractModel):
    alias_kind: UniverseAliasKind
    alias_value: Annotated[str, Field(min_length=1, max_length=256)]
    instrument_uids: Annotated[tuple[str, ...], Field(min_length=1)]
    record_count: Annotated[int, Field(ge=2)]

    @field_validator("instrument_uids", mode="before")
    @classmethod
    def normalize_uids(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("instrument_uids must be a collection")
        return tuple(sorted({str(item) for item in value}))


class UniverseSourceCountV1(ContractModel):
    operation: UniverseSourceOperation
    received: Annotated[int, Field(ge=0)]
    unique: Annotated[int, Field(ge=0)]
    accepted: Annotated[int, Field(ge=0)]
    excluded: Annotated[int, Field(ge=0)]
    duplicates_removed: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def validate_counts(self) -> UniverseSourceCountV1:
        if self.unique + self.duplicates_removed != self.received:
            raise ValueError("unique + duplicates_removed must equal received")
        if self.accepted + self.excluded != self.unique:
            raise ValueError("accepted + excluded must equal unique")
        return self


class MarketUniverseSnapshotV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    retrieved_at: datetime
    source_status: Literal["INSTRUMENT_STATUS_BASE"] = "INSTRUMENT_STATUS_BASE"
    account: UniverseAccountEligibilityV1
    completed_operations: tuple[UniverseSourceOperation, ...]
    instruments: tuple[UniverseInstrumentV1, ...] = ()
    excluded: tuple[UniverseExcludedInstrumentV1, ...] = ()
    conflicts: tuple[UniverseIdentityConflictV1, ...] = ()
    duplicate_rows_removed: Annotated[int, Field(ge=0)] = 0
    source_counts: tuple[UniverseSourceCountV1, ...] = ()
    content_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    quality: QualityMetadata
    decision_ready: bool

    @field_validator("retrieved_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("completed_operations", mode="before")
    @classmethod
    def normalize_completed_operations(cls, value: object) -> object:
        return _normalize_operation_collection(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> MarketUniverseSnapshotV1:
        if len(self.source_counts) != len({row.operation for row in self.source_counts}):
            raise ValueError("source_counts must contain at most one row per operation")
        return self
