from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from omni_cio.adapters.tinvest_connection_v1 import TInvestInstrumentClassificationV1
from omni_cio.adapters.tinvest_market_v1 import TInvestMarketResultV1
from omni_cio.adapters.tinvest_read_v1 import TInvestSnapshotResultV1
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType, PortfolioPositionV1
from omni_cio.web.api_v1 import SESSION_COOKIE, SessionRegistryLike
from omni_cio.web.persistence_v1 import (
    BrokerConnectionRecordV1,
    PostgresBrokerConnectionRepositoryV1,
)
from omni_cio.web.session_v1 import SessionScopeV1


class ReadVaultLike(Protocol):
    def load(self, *, secret_ref: str) -> str: ...


class DashboardAdapterLike(Protocol):
    def read_snapshot(
        self,
        *,
        allow_partial: bool = False,
        evaluated_at: datetime | None = None,
    ) -> TInvestSnapshotResultV1: ...

    def read_last_prices(
        self,
        instruments: tuple[InstrumentIdentity, ...],
        *,
        allow_partial: bool = False,
    ) -> TInvestMarketResultV1: ...

    def read_instrument_classifications(
        self,
        instruments: tuple[InstrumentIdentity, ...],
        *,
        allow_partial: bool = False,
    ) -> tuple[TInvestInstrumentClassificationV1, ...]: ...


DashboardAdapterBuilder = Callable[[str, str], DashboardAdapterLike]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WP18 timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _money(
    amount: Decimal,
    currency: str,
    *,
    source: str,
    as_of: datetime,
) -> dict[str, str]:
    return {
        "amount": _decimal(amount),
        "currency": currency,
        "source": source,
        "as_of": _utc(as_of).isoformat(),
    }


def _instrument_type(position: PortfolioPositionV1) -> str:
    value = position.instrument.instrument_type
    return value.value if hasattr(value, "value") else str(value)


def _market_value_allowed(position: PortfolioPositionV1) -> bool:
    return position.instrument.instrument_type in (
        InstrumentType.SHARE,
        InstrumentType.ETF,
    )


def _market_by_uid(result: TInvestMarketResultV1 | None) -> dict[str, Any]:
    if result is None:
        return {}
    return {row.instrument_uid: row for row in result.prices}


def _classification_by_uid(
    rows: tuple[TInvestInstrumentClassificationV1, ...],
) -> dict[str, TInvestInstrumentClassificationV1]:
    return {row.instrument_uid: row for row in rows}


def _safe_issue(issue: Any) -> dict[str, str]:
    return {
        "code": str(issue.code),
        "severity": str(
            issue.severity.value if hasattr(issue.severity, "value") else issue.severity
        ),
        "message": str(issue.message),
    }


class PortfolioDashboardServiceV1:
    """WP18 read-only product service over accepted WP15/WP17 boundaries.

    The service is tenant-scoped, never returns provider account IDs, fingerprints,
    secret references or credentials, and never silently converts incomplete data to
    zero. Market-value calculations are intentionally limited to instrument classes
    whose last-price quotation can be interpreted without extra conversion metadata.
    """

    def __init__(
        self,
        *,
        repository: PostgresBrokerConnectionRepositoryV1,
        vault: ReadVaultLike,
        adapter_builder: DashboardAdapterBuilder,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._vault = vault
        self._adapter_builder = adapter_builder
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _read_account(
        self,
        *,
        connection: BrokerConnectionRecordV1,
        account_index: int,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        account = connection.accounts[account_index]
        token = self._vault.load(secret_ref=connection.secret_ref)
        try:
            adapter = self._adapter_builder(
                token,
                account.account_fingerprint_sha256,
            )
            snapshot_result = adapter.read_snapshot(
                allow_partial=True,
                evaluated_at=evaluated_at,
            )
            positions = snapshot_result.snapshot.positions
            instruments = tuple(position.instrument for position in positions)
            market_result: TInvestMarketResultV1 | None = None
            market_error = False
            classification_rows: tuple[TInvestInstrumentClassificationV1, ...] = ()
            classification_error = False
            if positions:
                try:
                    market_result = adapter.read_last_prices(
                        instruments,
                        allow_partial=True,
                    )
                except Exception:
                    market_error = True
                try:
                    classification_rows = adapter.read_instrument_classifications(
                        instruments,
                        allow_partial=True,
                    )
                except Exception:
                    classification_error = True
        finally:
            token = ""

        prices = _market_by_uid(market_result)
        classifications = _classification_by_uid(classification_rows)
        broker_totals: dict[str, Decimal] = {}
        position_rows: list[dict[str, Any]] = []
        pending_weights: list[tuple[int, str, Decimal]] = []

        for position in positions:
            valuation = position.valuation
            valuation_as_of: datetime | None = None
            broker_value: dict[str, str] | None = None
            broker_value_amount: Decimal | None = None
            if valuation is not None and valuation.unit_price is not None:
                if valuation.as_of is None:
                    raise ValueError("POSITION_VALUATION_AS_OF_REQUIRED")
                valuation_as_of = valuation.as_of
                broker_value_amount = valuation.unit_price * position.quantity_units
                broker_value = _money(
                    broker_value_amount,
                    valuation.currency,
                    source="T-Invest GetPortfolio: current_price × quantity",
                    as_of=valuation_as_of,
                )
                broker_totals[valuation.currency] = (
                    broker_totals.get(valuation.currency, Decimal("0"))
                    + broker_value_amount
                )

            uid = position.instrument.uid or ""
            market = prices.get(uid)
            classification = classifications.get(uid)
            current_market_value: dict[str, str] | None = None
            market_conversion_state = "NO_LAST_PRICE"
            if market is not None:
                if _market_value_allowed(position):
                    current_market_value = _money(
                        market.price * position.quantity_units,
                        position.instrument.currency,
                        source="T-Invest GetLastPrices: last_price × quantity",
                        as_of=market.price_time,
                    )
                    market_conversion_state = "DIRECT_SHARE_OR_ETF"
                else:
                    market_conversion_state = "ASSET_SPECIFIC_CONVERSION_REQUIRED"

            classification_state = (
                classification.state if classification is not None else "UNAVAILABLE"
            )
            classification_source = (
                classification.source
                if classification is not None
                else "T-Invest asset metadata unavailable"
            )
            classification_as_of = (
                classification.retrieved_at.isoformat()
                if classification is not None
                else snapshot_result.snapshot.metadata.retrieved_at.isoformat()
            )
            row: dict[str, Any] = {
                "instrument": {
                    "name": position.instrument.name,
                    "ticker": position.instrument.ticker,
                    "type": _instrument_type(position),
                    "currency": position.instrument.currency,
                    "class_code": position.instrument.class_code,
                    "isin": position.instrument.isin,
                    "figi": position.instrument.figi,
                    "uid": position.instrument.uid,
                    "position_uid": position.instrument.position_uid,
                    "issuer": (
                        classification.issuer if classification is not None else None
                    ),
                    "sector": (
                        classification.sector if classification is not None else None
                    ),
                    "classification_state": classification_state,
                    "classification_source": classification_source,
                    "classification_as_of": classification_as_of,
                },
                "quantity_units": _decimal(position.quantity_units),
                "blocked_units": _decimal(position.blocked_units),
                "broker_unit_price": (
                    _money(
                        valuation.unit_price,
                        valuation.currency,
                        source="T-Invest GetPortfolio current_price",
                        as_of=valuation_as_of,
                    )
                    if valuation is not None
                    and valuation.unit_price is not None
                    and valuation_as_of is not None
                    else None
                ),
                "broker_value": broker_value,
                "current_market_last_price": (
                    {
                        "amount": _decimal(market.price),
                        "currency": position.instrument.currency,
                        "source": "T-Invest GetLastPrices",
                        "as_of": _utc(market.price_time).isoformat(),
                        "freshness": market.freshness.value,
                        "age_seconds": _decimal(market.age_seconds),
                    }
                    if market is not None
                    else None
                ),
                "current_market_value": current_market_value,
                "market_conversion_state": market_conversion_state,
                "weight_within_position_currency_pct": None,
            }
            position_rows.append(row)
            if broker_value_amount is not None and valuation is not None:
                pending_weights.append(
                    (len(position_rows) - 1, valuation.currency, broker_value_amount)
                )

        for index, currency, value in pending_weights:
            denominator = broker_totals.get(currency, Decimal("0"))
            if denominator > 0:
                position_rows[index]["weight_within_position_currency_pct"] = _decimal(
                    (value / denominator) * Decimal("100")
                )

        position_rows.sort(
            key=lambda row: (
                row["broker_value"] is not None,
                Decimal(row["broker_value"]["amount"])
                if row["broker_value"]
                else Decimal("0"),
                row["instrument"]["name"],
            ),
            reverse=True,
        )

        concentration: list[dict[str, str]] = []
        for currency, total in sorted(broker_totals.items()):
            values = sorted(
                (
                    Decimal(row["broker_value"]["amount"])
                    for row in position_rows
                    if row["broker_value"] is not None
                    and row["broker_value"]["currency"] == currency
                ),
                reverse=True,
            )
            if total <= 0 or not values:
                continue
            concentration.append(
                {
                    "currency": currency,
                    "normalized_position_value": _decimal(total),
                    "top_1_weight_pct": _decimal(
                        values[0] / total * Decimal("100")
                    ),
                    "top_5_weight_pct": _decimal(
                        sum(values[:5], Decimal("0")) / total * Decimal("100")
                    ),
                    "basis": "normalized broker current_price × quantity; same-currency positions only",
                }
            )

        quality = snapshot_result.snapshot.metadata.quality
        warnings = [_safe_issue(issue) for issue in quality.issues]
        if snapshot_result.unresolved_position_count:
            warnings.append(
                {
                    "code": "UNRESOLVED_BROKER_POSITIONS",
                    "severity": "error",
                    "message": f"{snapshot_result.unresolved_position_count} broker positions are not represented as normalized rows.",
                }
            )
        if snapshot_result.freshness.state.value == "stale":
            warnings.append(
                {
                    "code": "BROKER_SNAPSHOT_STALE",
                    "severity": "warning",
                    "message": "Broker snapshot age exceeded the accepted freshness threshold.",
                }
            )
        if market_error:
            warnings.append(
                {
                    "code": "CURRENT_MARKET_DATA_UNAVAILABLE",
                    "severity": "warning",
                    "message": "Current-market quotes are unavailable; broker-reported data remains visible.",
                }
            )
        elif market_result is not None:
            if market_result.missing_instrument_count:
                warnings.append(
                    {
                        "code": "CURRENT_MARKET_QUOTES_PARTIAL",
                        "severity": "warning",
                        "message": f"{market_result.missing_instrument_count} normalized instruments have no returned last price.",
                    }
                )
            if market_result.stale_instrument_count:
                warnings.append(
                    {
                        "code": "CURRENT_MARKET_QUOTES_STALE",
                        "severity": "warning",
                        "message": f"{market_result.stale_instrument_count} returned last prices are stale.",
                    }
                )
        if classification_error:
            warnings.append(
                {
                    "code": "INSTRUMENT_CLASSIFICATION_UNAVAILABLE",
                    "severity": "warning",
                    "message": "Issuer/sector metadata could not be read; no inferred classification was emitted.",
                }
            )
        elif any(row.state != "VERIFIED" for row in classification_rows):
            warnings.append(
                {
                    "code": "INSTRUMENT_CLASSIFICATION_PARTIAL",
                    "severity": "warning",
                    "message": "Some positions have no verified issuer/sector metadata; unavailable values remain explicit.",
                }
            )

        portfolio_total = snapshot_result.portfolio_total
        return {
            "masked_account": account.masked_label,
            "access": "READ_ONLY",
            "connection_state": connection.state,
            "retrieved_at": snapshot_result.snapshot.metadata.retrieved_at.isoformat(),
            "freshness": {
                "state": snapshot_result.freshness.state.value,
                "age_seconds": _decimal(snapshot_result.freshness.age_seconds),
                "evaluated_at": snapshot_result.freshness.evaluated_at.isoformat(),
            },
            "completeness": quality.completeness.value,
            "broker_position_count": snapshot_result.broker_position_count,
            "normalized_position_count": snapshot_result.normalized_position_count,
            "unresolved_position_count": snapshot_result.unresolved_position_count,
            "portfolio_total": (
                _money(
                    portfolio_total.amount,
                    portfolio_total.currency,
                    source="T-Invest GetPortfolio total_amount_portfolio",
                    as_of=snapshot_result.snapshot.metadata.retrieved_at,
                )
                if portfolio_total is not None
                else None
            ),
            "cash": [
                {
                    "currency": cash.reported.currency,
                    "reported": _decimal(cash.reported.amount),
                    "available": (
                        _decimal(cash.available.amount)
                        if cash.available is not None
                        else None
                    ),
                    "blocked": (
                        _decimal(cash.blocked.amount)
                        if cash.blocked is not None
                        else None
                    ),
                    "source": "T-Invest GetPositions",
                    "as_of": cash.as_of.isoformat(),
                }
                for cash in snapshot_result.snapshot.cash_balances
            ],
            "positions": position_rows,
            "concentration": concentration,
            "warnings": warnings,
            "current_market": {
                "state": (
                    "UNAVAILABLE"
                    if market_error
                    else "EMPTY"
                    if not positions
                    else "PARTIAL"
                    if market_result is not None
                    and market_result.missing_instrument_count > 0
                    else "AVAILABLE"
                ),
                "retrieved_at": (
                    market_result.retrieved_at.isoformat()
                    if market_result is not None
                    else None
                ),
                "missing_instrument_count": (
                    market_result.missing_instrument_count
                    if market_result is not None
                    else len(positions)
                    if market_error
                    else 0
                ),
                "stale_instrument_count": (
                    market_result.stale_instrument_count
                    if market_result is not None
                    else 0
                ),
            },
        }

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        evaluated_at = _utc(self._clock())
        connections = self._repository.list_read_connections(tenant_id=tenant_id)
        accounts: list[dict[str, Any]] = []
        connection_views: list[dict[str, Any]] = []
        warnings: list[dict[str, str]] = []

        for connection in connections:
            connection_views.append(
                {
                    "connection_id": connection.connection_id,
                    "provider": connection.provider,
                    "role": connection.credential_role,
                    "state": connection.state,
                    "last_verified_at": (
                        connection.last_verified_at.isoformat()
                        if connection.last_verified_at is not None
                        else None
                    ),
                    "account_count": len(connection.accounts),
                }
            )
            if connection.state != "ACTIVE" or connection.credential_role != "read":
                continue
            for account_index in range(len(connection.accounts)):
                try:
                    accounts.append(
                        self._read_account(
                            connection=connection,
                            account_index=account_index,
                            evaluated_at=evaluated_at,
                        )
                    )
                except Exception:
                    warnings.append(
                        {
                            "code": "BROKER_ACCOUNT_READ_UNAVAILABLE",
                            "severity": "error",
                            "message": f"Current-on-demand read failed for masked account {connection.accounts[account_index].masked_label}; no zero-value substitute was emitted.",
                        }
                    )

        return {
            "schema_version": "1.0.0",
            "generated_at": evaluated_at.isoformat(),
            "state": (
                "EMPTY"
                if not connections
                else "UNAVAILABLE"
                if not accounts
                else "PARTIAL"
                if warnings or any(account["warnings"] for account in accounts)
                else "READY"
            ),
            "connections": connection_views,
            "accounts": accounts,
            "warnings": warnings,
            "calculation_policy": {
                "decimal_transport": "strings_only",
                "cross_currency_aggregation": "forbidden_without_explicit_conversion",
                "broker_position_value": "current_price × quantity_units",
                "current_market_value": "direct only for shares/ETFs; other asset classes require instrument-specific conversion metadata",
                "weights": "same-currency normalized positions only",
            },
        }


def _require_dashboard_session(
    request: Request,
    *,
    sessions: SessionRegistryLike,
    now: Callable[[], datetime],
) -> SessionScopeV1:
    current = _utc(now())
    scope = sessions.resolve(request.cookies.get(SESSION_COOKIE), now=current)
    if scope is None:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")
    return scope


def install_portfolio_dashboard_routes(
    app: FastAPI,
    *,
    sessions: SessionRegistryLike,
    service: PortfolioDashboardServiceV1,
    now: Callable[[], datetime] | None = None,
) -> None:
    clock = now or (lambda: datetime.now(timezone.utc))

    @app.get("/api/v10/web/portfolio-dashboard")
    def portfolio_dashboard(request: Request) -> JSONResponse:
        scope = _require_dashboard_session(request, sessions=sessions, now=clock)
        payload = service.read(tenant_id=scope.tenant_id)
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})
