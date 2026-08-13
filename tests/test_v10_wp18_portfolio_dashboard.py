from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.web.portfolio_dashboard_v1 import (
    PortfolioDashboardServiceV1,
    install_portfolio_dashboard_routes,
)


NOW = datetime(2026, 8, 13, 8, 30, tzinfo=timezone.utc)


class FakeRepository:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.seen_tenants: list[str] = []

    def list_read_connections(self, *, tenant_id: str) -> list[Any]:
        self.seen_tenants.append(tenant_id)
        return self.rows


class FakeVault:
    def __init__(self, token: str = "super-private-token") -> None:
        self.token = token
        self.loaded_refs: list[str] = []

    def load(self, *, secret_ref: str) -> str:
        self.loaded_refs.append(secret_ref)
        return self.token


class FakeAdapter:
    def __init__(
        self,
        snapshot: Any,
        market: Any = None,
        *,
        market_error: bool = False,
        classification_error: bool = False,
        classification_state: str = "VERIFIED",
    ) -> None:
        self.snapshot = snapshot
        self.market = market
        self.market_error = market_error
        self.classification_error = classification_error
        self.classification_state = classification_state

    def read_snapshot(
        self,
        *,
        allow_partial: bool = False,
        evaluated_at: datetime | None = None,
    ) -> Any:
        assert allow_partial is True
        assert evaluated_at == NOW
        return self.snapshot

    def read_last_prices(
        self,
        instruments: tuple[Any, ...],
        *,
        allow_partial: bool = False,
    ) -> Any:
        assert allow_partial is True
        assert instruments
        if self.market_error:
            raise RuntimeError("provider unavailable")
        return self.market

    def read_instrument_classifications(
        self,
        instruments: tuple[Any, ...],
        *,
        allow_partial: bool = False,
    ) -> tuple[Any, ...]:
        assert allow_partial is True
        assert instruments
        if self.classification_error:
            raise RuntimeError("classification unavailable")
        return tuple(
            SimpleNamespace(
                instrument_uid=instrument.uid,
                issuer=(
                    "Example Issuer" if self.classification_state == "VERIFIED" else None
                ),
                sector=(
                    "Technology" if self.classification_state == "VERIFIED" else None
                ),
                source="T-Invest GetAssets → GetAssetBy.brand",
                retrieved_at=NOW,
                state=self.classification_state,
            )
            for instrument in instruments
            if instrument.uid
        )


def _state(value: str) -> Any:
    return SimpleNamespace(value=value)


def _connection(*, fingerprint: str = "f" * 64) -> Any:
    return SimpleNamespace(
        connection_id="conn-public-id",
        tenant_id="tenant-owner",
        provider="t_invest",
        credential_role="read",
        state="ACTIVE",
        secret_ref="private-secret-ref",
        created_at=NOW,
        last_verified_at=NOW,
        accounts=(
            SimpleNamespace(
                masked_label="***1234",
                account_fingerprint_sha256=fingerprint,
            ),
        ),
    )


def _position(*, kind: InstrumentType = InstrumentType.SHARE) -> Any:
    instrument = SimpleNamespace(
        name="Example Asset",
        ticker="EXMP",
        instrument_type=kind,
        currency="RUB",
        class_code="TQBR",
        isin="RU0000000001",
        figi="BBG000000001",
        uid="instrument-uid-1",
        position_uid="position-uid-1",
    )
    valuation = SimpleNamespace(
        unit_price=Decimal("10.00"),
        currency="RUB",
        as_of=NOW,
    )
    return SimpleNamespace(
        instrument=instrument,
        quantity_units=Decimal("3"),
        blocked_units=Decimal("0"),
        valuation=valuation,
    )


def _snapshot(
    *,
    position: Any | None = None,
    partial: bool = False,
    optional_cash_unknown: bool = False,
) -> Any:
    positions = () if position is None else (position,)
    quality = SimpleNamespace(
        completeness=_state("partial" if partial else "complete"),
        issues=(
            SimpleNamespace(
                code="BROKER_POSITION_UNRESOLVED",
                severity=_state("error"),
                message="One position is unresolved.",
            ),
        )
        if partial
        else (),
    )
    snapshot = SimpleNamespace(
        metadata=SimpleNamespace(retrieved_at=NOW, quality=quality),
        positions=positions,
        cash_balances=(
            SimpleNamespace(
                reported=SimpleNamespace(amount=Decimal("125.50"), currency="RUB"),
                available=(
                    None
                    if optional_cash_unknown
                    else SimpleNamespace(amount=Decimal("120.50"), currency="RUB")
                ),
                blocked=(
                    None
                    if optional_cash_unknown
                    else SimpleNamespace(amount=Decimal("5.00"), currency="RUB")
                ),
                as_of=NOW,
            ),
        ),
    )
    return SimpleNamespace(
        snapshot=snapshot,
        freshness=SimpleNamespace(
            state=_state("fresh"),
            age_seconds=Decimal("0"),
            evaluated_at=NOW,
        ),
        portfolio_total=SimpleNamespace(
            amount=Decimal("1000.25"),
            currency="RUB",
        ),
        broker_position_count=2 if partial else len(positions),
        normalized_position_count=len(positions),
        unresolved_position_count=1 if partial else 0,
    )


def _market(*, stale: bool = False) -> Any:
    return SimpleNamespace(
        retrieved_at=NOW,
        prices=(
            SimpleNamespace(
                instrument_uid="instrument-uid-1",
                price=Decimal("10.50"),
                price_time=NOW - timedelta(seconds=1),
                age_seconds=Decimal("1"),
                freshness=_state("stale" if stale else "fresh"),
            ),
        ),
        missing_instrument_count=0,
        stale_instrument_count=1 if stale else 0,
    )


def _service(
    *,
    snapshot: Any,
    market: Any = None,
    market_error: bool = False,
    classification_error: bool = False,
    classification_state: str = "VERIFIED",
) -> tuple[PortfolioDashboardServiceV1, FakeRepository, FakeVault]:
    repository = FakeRepository([_connection()])
    vault = FakeVault()
    adapter = FakeAdapter(
        snapshot,
        market,
        market_error=market_error,
        classification_error=classification_error,
        classification_state=classification_state,
    )
    service = PortfolioDashboardServiceV1(
        repository=repository,  # type: ignore[arg-type]
        vault=vault,
        adapter_builder=lambda token, fingerprint: adapter,
        clock=lambda: NOW,
    )
    return service, repository, vault


def test_empty_dashboard_does_not_read_secret() -> None:
    repository = FakeRepository([])
    vault = FakeVault()
    service = PortfolioDashboardServiceV1(
        repository=repository,  # type: ignore[arg-type]
        vault=vault,
        adapter_builder=lambda token, fingerprint: (_ for _ in ()).throw(
            AssertionError()
        ),
        clock=lambda: NOW,
    )

    result = service.read(tenant_id="tenant-owner")

    assert result["state"] == "EMPTY"
    assert result["accounts"] == []
    assert vault.loaded_refs == []
    assert repository.seen_tenants == ["tenant-owner"]


def test_share_dashboard_preserves_decimal_sources_and_current_market_value() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(position=_position()),
        market=_market(),
    )

    result = service.read(tenant_id="tenant-owner")

    account = result["accounts"][0]
    position = account["positions"][0]
    assert result["state"] == "READY"
    assert account["portfolio_total"]["amount"] == "1000.25"
    assert account["cash"][0]["reported"] == "125.50"
    assert position["broker_value"]["amount"] == "30.00"
    assert (
        position["broker_value"]["source"]
        == "T-Invest GetPortfolio: current_price × quantity"
    )
    assert position["current_market_value"]["amount"] == "31.50"
    assert position["market_conversion_state"] == "DIRECT_SHARE_OR_ETF"
    assert Decimal(position["weight_within_position_currency_pct"]) == Decimal("100")
    assert account["concentration"][0]["top_1_weight_pct"] == "100"
    assert position["instrument"]["issuer"] == "Example Issuer"
    assert position["instrument"]["sector"] == "Technology"
    assert position["instrument"]["classification_state"] == "VERIFIED"
    assert position["instrument"]["uid"] == "instrument-uid-1"


def test_bond_market_quote_is_not_naively_converted_to_currency_value() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(position=_position(kind=InstrumentType.BOND)),
        market=_market(),
    )

    result = service.read(tenant_id="tenant-owner")
    position = result["accounts"][0]["positions"][0]

    assert position["current_market_last_price"]["amount"] == "10.50"
    assert position["current_market_value"] is None
    assert (
        position["market_conversion_state"]
        == "ASSET_SPECIFIC_CONVERSION_REQUIRED"
    )


def test_partial_snapshot_is_visible_and_never_replaced_with_zero() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(position=_position(), partial=True),
        market=_market(),
    )

    result = service.read(tenant_id="tenant-owner")

    assert result["state"] == "PARTIAL"
    account = result["accounts"][0]
    assert account["completeness"] == "partial"
    assert account["broker_position_count"] == 2
    assert account["normalized_position_count"] == 1
    assert account["unresolved_position_count"] == 1
    assert any(
        row["code"] == "UNRESOLVED_BROKER_POSITIONS"
        for row in account["warnings"]
    )


def test_optional_cash_components_remain_unknown_instead_of_zero() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(optional_cash_unknown=True),
    )

    result = service.read(tenant_id="tenant-owner")
    cash = result["accounts"][0]["cash"][0]

    assert cash["reported"] == "125.50"
    assert cash["available"] is None
    assert cash["blocked"] is None


def test_classification_failure_is_visible_and_never_inferred() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(position=_position()),
        market=_market(),
        classification_error=True,
    )

    result = service.read(tenant_id="tenant-owner")
    account = result["accounts"][0]
    instrument = account["positions"][0]["instrument"]

    assert result["state"] == "PARTIAL"
    assert instrument["issuer"] is None
    assert instrument["sector"] is None
    assert instrument["classification_state"] == "UNAVAILABLE"
    assert any(
        row["code"] == "INSTRUMENT_CLASSIFICATION_UNAVAILABLE"
        for row in account["warnings"]
    )


def test_dashboard_payload_never_exposes_token_secret_ref_or_fingerprint() -> None:
    service, _, vault = _service(
        snapshot=_snapshot(position=_position()),
        market=_market(),
    )

    result = service.read(tenant_id="tenant-owner")
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert vault.loaded_refs == ["private-secret-ref"]
    assert "super-private-token" not in encoded
    assert "private-secret-ref" not in encoded
    assert (
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        not in encoded
    )
    assert "***1234" in encoded


def test_market_failure_keeps_broker_data_visible_with_explicit_warning() -> None:
    service, _, _ = _service(
        snapshot=_snapshot(position=_position()),
        market_error=True,
    )

    result = service.read(tenant_id="tenant-owner")
    account = result["accounts"][0]

    assert result["state"] == "PARTIAL"
    assert account["portfolio_total"]["amount"] == "1000.25"
    assert account["current_market"]["state"] == "UNAVAILABLE"
    assert any(
        row["code"] == "CURRENT_MARKET_DATA_UNAVAILABLE"
        for row in account["warnings"]
    )


class FakeSessions:
    def __init__(self, scope: Any | None) -> None:
        self.scope = scope

    def resolve(self, token: str | None, *, now: datetime) -> Any | None:
        del token, now
        return self.scope


class CapturingService:
    def __init__(self) -> None:
        self.tenant_ids: list[str] = []

    def read(self, *, tenant_id: str) -> dict[str, Any]:
        self.tenant_ids.append(tenant_id)
        return {
            "schema_version": "1.0.0",
            "generated_at": NOW.isoformat(),
            "state": "EMPTY",
            "connections": [],
            "accounts": [],
            "warnings": [],
            "calculation_policy": {},
        }


def test_api_requires_session_and_derives_tenant_server_side() -> None:
    app = FastAPI()
    service = CapturingService()
    sessions = FakeSessions(
        SimpleNamespace(user_id="user-owner", tenant_id="tenant-from-session")
    )
    install_portfolio_dashboard_routes(
        app,
        sessions=sessions,  # type: ignore[arg-type]
        service=service,  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    response = TestClient(app).get("/api/v10/web/portfolio-dashboard")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert service.tenant_ids == ["tenant-from-session"]

    unauthenticated = FastAPI()
    install_portfolio_dashboard_routes(
        unauthenticated,
        sessions=FakeSessions(None),  # type: ignore[arg-type]
        service=CapturingService(),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    denied = TestClient(unauthenticated).get("/api/v10/web/portfolio-dashboard")
    assert denied.status_code == 401
