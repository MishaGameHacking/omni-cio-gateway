from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import ValidationError
from t_tech.invest import Client, InstrumentStatus

from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType
from omni_cio.contracts.v1.universe import (
    UniverseAccountEligibilityV1,
    UniverseCatalogV1,
    UniverseInstrumentV1,
    UniverseSourceOperation,
)


ClientFactory = Callable[[str], AbstractContextManager[Any]]


class UniverseSourceRowError(ValueError):
    """A broker instrument row is structurally incomplete for WP3."""


def _required_attr(value: object, name: str) -> object:
    if not hasattr(value, name):
        raise UniverseSourceRowError(f"missing required broker field: {name}")
    return getattr(value, name)


def _required_bool(value: object, name: str) -> bool:
    result = _required_attr(value, name)
    if not isinstance(result, bool):
        raise UniverseSourceRowError(f"broker field {name} must be bool")
    return result


def _required_int(value: object, name: str) -> int:
    result = _required_attr(value, name)
    if isinstance(result, bool) or not isinstance(result, int):
        raise UniverseSourceRowError(f"broker field {name} must be int")
    return result


def _required_text(value: object, name: str) -> str:
    result = _required_attr(value, name)
    if not isinstance(result, str) or not result.strip():
        raise UniverseSourceRowError(f"broker field {name} must be non-empty text")
    return result.strip()


def _optional_text(value: object, name: str) -> str | None:
    result = getattr(value, name, None)
    if result is None:
        return None
    text = str(result).strip()
    return text or None


def _enum_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.name
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    text = str(value).strip()
    return text or None


def _test_codes(value: object, name: str) -> tuple[str, ...]:
    raw = getattr(value, name, ())
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)):
        raw = (raw,)
    try:
        return tuple(sorted({str(item).strip() for item in raw if str(item).strip()}))
    except TypeError as exc:
        raise UniverseSourceRowError(f"broker field {name} must be iterable") from exc


def _instrument_from_sdk(
    row: object,
    *,
    source_operation: UniverseSourceOperation,
    instrument_type: InstrumentType,
) -> UniverseInstrumentV1:
    identity = InstrumentIdentity(
        name=_required_text(row, "name"),
        instrument_type=instrument_type,
        currency=_required_text(row, "currency"),
        lot=_required_int(row, "lot"),
        ticker=_optional_text(row, "ticker"),
        isin=_optional_text(row, "isin"),
        figi=_optional_text(row, "figi"),
        uid=_required_text(row, "uid"),
        position_uid=_optional_text(row, "position_uid"),
        class_code=_optional_text(row, "class_code"),
    )
    return UniverseInstrumentV1(
        source_operation=source_operation,
        identity=identity,
        exchange=_optional_text(row, "exchange"),
        real_exchange=_enum_text(getattr(row, "real_exchange", None)),
        api_trade_available=_required_bool(row, "api_trade_available_flag"),
        buy_available=_required_bool(row, "buy_available_flag"),
        sell_available=_required_bool(row, "sell_available_flag"),
        for_iis=_required_bool(row, "for_iis_flag"),
        for_qual_investor=_required_bool(row, "for_qual_investor_flag"),
        blocked_tca=_required_bool(row, "blocked_tca_flag"),
        otc=bool(getattr(row, "otc_flag", False)),
        liquidity_sufficient=(
            bool(getattr(row, "liquidity_flag"))
            if hasattr(row, "liquidity_flag")
            else None
        ),
        required_tests=_test_codes(row, "required_tests"),
    )


def _error_code(component: str, exc: Exception) -> str:
    return f"{component}:{type(exc).__name__}"[:128]


class TInvestUniverseAdapterV1:
    """Read-only adapter for broker-wide BASE instrument catalogs and user eligibility."""

    def __init__(
        self,
        token: str,
        *,
        client_factory: ClientFactory = Client,
    ) -> None:
        cleaned = str(token or "").strip()
        if not cleaned:
            raise ValueError("T-Invest token is required")
        self._token = cleaned
        self._client_factory = client_factory

    def fetch_account_eligibility(
        self,
        *,
        account_type: AccountPolicyType,
    ) -> tuple[UniverseAccountEligibilityV1, str | None]:
        try:
            with self._client_factory(self._token) as client:
                response = client.users.get_info()
                qual_status = _required_attr(response, "qual_status")
                if not isinstance(qual_status, bool):
                    raise UniverseSourceRowError("qual_status must be bool")
                permissions = _test_codes(response, "qualified_for_work_with")
                return (
                    UniverseAccountEligibilityV1(
                        account_type=account_type,
                        qualified_investor=qual_status,
                        qualified_for_work_with=permissions,
                    ),
                    None,
                )
        except Exception as exc:  # SDK transport/protobuf boundary is normalized.
            return (
                UniverseAccountEligibilityV1(
                    account_type=account_type,
                    qualified_investor=None,
                ),
                _error_code("GetInfo", exc),
            )

    def fetch_catalog(
        self,
        *,
        retrieved_at: datetime | None = None,
    ) -> UniverseCatalogV1:
        timestamp = retrieved_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        timestamp = timestamp.astimezone(timezone.utc)

        instruments: list[UniverseInstrumentV1] = []
        completed: list[UniverseSourceOperation] = []
        source_errors: list[str] = []
        invalid_rows = 0
        operations = (
            (UniverseSourceOperation.SHARES, InstrumentType.SHARE, "shares"),
            (UniverseSourceOperation.BONDS, InstrumentType.BOND, "bonds"),
            (UniverseSourceOperation.ETFS, InstrumentType.ETF, "etfs"),
        )

        with self._client_factory(self._token) as client:
            for operation, instrument_type, method_name in operations:
                try:
                    method = getattr(client.instruments, method_name)
                    response = method(
                        instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE
                    )
                    rows = _required_attr(response, "instruments")
                    for row in rows:  # type: ignore[union-attr]
                        try:
                            instruments.append(
                                _instrument_from_sdk(
                                    row,
                                    source_operation=operation,
                                    instrument_type=instrument_type,
                                )
                            )
                        except (UniverseSourceRowError, ValidationError, ValueError):
                            invalid_rows += 1
                    completed.append(operation)
                except Exception as exc:  # One failed list makes the catalog incomplete.
                    source_errors.append(_error_code(operation.value, exc))

        return UniverseCatalogV1(
            retrieved_at=timestamp,
            completed_operations=tuple(completed),
            instruments=tuple(instruments),
            source_errors=tuple(source_errors),
            invalid_rows=invalid_rows,
        )
