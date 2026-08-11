from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from omni_cio.adapters.tinvest_read_v1 import (
    BrokerAccountBindingV1,
    FreshnessMetadataV1,
    FreshnessState,
    ThrottleMetadataV1,
    TInvestSnapshotResultV1,
)
from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.domain import OWNER_TENANT_ID, OWNER_USER_ID
from omni_cio.contracts.v1.portfolio import (
    InstrumentIdentity,
    InstrumentType,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    ValuationBasis,
)
from omni_cio.web.api_v1 import SESSION_COOKIE, WebApiServicesV1, create_web_api
from omni_cio.web.live_acceptance_v1 import (
    BrokerLiveAcceptanceServiceV1,
    PendingLiveAcceptanceEvidenceWriterV1,
)
from omni_cio.web.persistence_v1 import BrokerConnectionRecordV1
from omni_cio.web.session_v1 import SessionRegistryV1


NOW = datetime(2026, 8, 11, 15, 30, tzinfo=timezone.utc)
FINGERPRINT = "a" * 64
CONNECTION_ID = "broker-connection:v1:" + ("b" * 64)
SECRET_REF = "read-connection:v1:" + ("c" * 64)
IMPLEMENTATION_SHA = "d" * 40


class FakeRepository:
    def __init__(self, record: BrokerConnectionRecordV1) -> None:
        self.record = record

    def list_read_connections(
        self, *, tenant_id: str
    ) -> tuple[BrokerConnectionRecordV1, ...]:
        return (self.record,) if tenant_id == self.record.tenant_id else ()


class FakeVault:
    def load(self, *, secret_ref: str) -> str:
        assert secret_ref == SECRET_REF
        return "synthetic-local-read-token"


class FakeAdapter:
    def __init__(self, result: TInvestSnapshotResultV1) -> None:
        self.result = result

    def read_snapshot(self, *, allow_partial: bool = False) -> TInvestSnapshotResultV1:
        assert allow_partial is False
        return self.result


def _binding() -> BrokerAccountBindingV1:
    return BrokerAccountBindingV1(
        broker_account_id="broker-account:v1:" + ("e" * 64),
        account_fingerprint_sha256=FINGERPRINT,
        masked_label="***2048",
        access_level="ACCOUNT_ACCESS_LEVEL_READ_ONLY",
    )


def _record() -> BrokerConnectionRecordV1:
    return BrokerConnectionRecordV1(
        connection_id=CONNECTION_ID,
        tenant_id=OWNER_TENANT_ID,
        provider="t_invest",
        credential_role="read",
        state="ACTIVE",
        secret_ref=SECRET_REF,
        created_at=NOW - timedelta(days=1),
        last_verified_at=NOW - timedelta(minutes=1),
        accounts=(_binding(),),
    )


def _snapshot() -> TInvestSnapshotResultV1:
    binding = _binding()
    position = PortfolioPositionV1(
        instrument=InstrumentIdentity(
            name="Synthetic Share",
            ticker="SYN",
            instrument_type=InstrumentType.SHARE,
            currency="RUB",
            lot=1,
            uid="synthetic-instrument-uid",
        ),
        quantity_units=Decimal("3"),
        valuation=PositionValuation(
            basis=ValuationBasis.BROKER_REPORTED,
            currency="RUB",
            as_of=NOW,
            unit_price=Decimal("50"),
        ),
    )
    return TInvestSnapshotResultV1(
        account=binding,
        snapshot=PortfolioSnapshotV1(
            metadata=ContractMetadata(
                schema_name="portfolio_snapshot",
                retrieved_at=NOW,
                account=AccountReference(masked_id=binding.masked_label),
                provenance=(
                    SourceReference(
                        provider="T-Invest",
                        operation="GetPortfolio",
                        retrieved_at=NOW,
                        source_id=binding.masked_label,
                    ),
                ),
                quality=QualityMetadata(
                    quality=DataQuality.VERIFIED,
                    completeness=Completeness.COMPLETE,
                ),
            ),
            positions=(position,),
        ),
        freshness=FreshnessMetadataV1(
            retrieved_at=NOW,
            evaluated_at=NOW,
            age_seconds=Decimal("0"),
            stale_after_seconds=300,
            state=FreshnessState.FRESH,
        ),
        throttle=ThrottleMetadataV1(
            source="fallback",
            effective_requests_per_minute=Decimal("40"),
            minimum_interval_seconds=Decimal("1.5"),
        ),
        portfolio_total=Money(amount=Decimal("150"), currency="RUB"),
        broker_position_count=1,
        normalized_position_count=1,
        unresolved_position_count=0,
    )


def _live_service(
    tmp_path: Path, repository: FakeRepository
) -> BrokerLiveAcceptanceServiceV1:
    pending = tmp_path / "pending"
    pending.mkdir()
    (pending / ".omni-cio-wp15-live-pending").write_text(
        "OMNI-CIO-V10-WP15-LIVE-PENDING-v1",
        encoding="ascii",
    )
    adapter = FakeAdapter(_snapshot())
    return BrokerLiveAcceptanceServiceV1(
        repository=repository,
        vault=FakeVault(),
        client_factory_builder=lambda token: lambda: token,
        evidence_writer=PendingLiveAcceptanceEvidenceWriterV1(
            pending / "owner-confirmation.json"
        ),
        implementation_sha=IMPLEMENTATION_SHA,
        adapter_factory=lambda client_factory, fingerprint: adapter,
        now=lambda: NOW,
    )


def _app(tmp_path: Path) -> tuple[Any, SessionRegistryV1]:
    repository = FakeRepository(_record())
    sessions = SessionRegistryV1()
    app = create_web_api(
        WebApiServicesV1(
            sessions=sessions,
            broker_repository=repository,  # type: ignore[arg-type]
            provisioning=object(),  # type: ignore[arg-type]
            live_acceptance=_live_service(tmp_path, repository),
            now=lambda: NOW,
            private_test_identity_enabled=True,
        )
    )
    return app, sessions


def test_live_web_api_is_authenticated_loopback_only_and_no_store(
    tmp_path: Path,
) -> None:
    app, sessions = _app(tmp_path)
    client = TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 50000),
    )

    unauthenticated = client.post(
        "/api/v10/web/wp15-live-acceptance/start",
        json={"connection_id": CONNECTION_ID, "account_index": 0},
    )
    assert unauthenticated.status_code == 401

    assert client.post("/api/v10/web/private-test-login").status_code == 200
    status = client.get("/api/v10/web/wp15-live-acceptance/status")
    assert status.status_code == 200
    assert status.json() == {"enabled": True}

    started = client.post(
        "/api/v10/web/wp15-live-acceptance/start",
        json={"connection_id": CONNECTION_ID, "account_index": 0},
    )
    assert started.status_code == 200
    assert started.headers["cache-control"] == "no-store"
    body = started.json()
    assert body["masked_account"] == "***2048"
    assert body["access_level"] == "READ_ONLY"
    assert body["freshness_state"] == "FRESH"
    assert FINGERPRINT not in started.text
    assert SECRET_REF not in started.text
    assert "synthetic-local-read-token" not in started.text

    confirmed = client.post(
        "/api/v10/web/wp15-live-acceptance/confirm",
        json={
            "challenge_id": body["challenge_id"],
            "intended_account_confirmed": True,
            "portfolio_summary_parity": True,
            "sample_position_quantity_value_parity": True,
            "freshness_confirmed": True,
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.headers["cache-control"] == "no-store"
    assert confirmed.json() == {
        "accepted": True,
        "pending_owner_finalization": True,
    }

    pending_text = (tmp_path / "pending" / "owner-confirmation.json").read_text(
        encoding="utf-8"
    )
    for marker in (
        "synthetic-local-read-token",
        SECRET_REF,
        FINGERPRINT,
        '"portfolio_total"',
        '"quantity"',
        '"unit_price"',
        '"market_value"',
        '"masked_account"',
    ):
        assert marker not in pending_text

    remote_token, _ = sessions.create(
        user_id=OWNER_USER_ID,
        tenant_id=OWNER_TENANT_ID,
        now=NOW,
    )
    remote = TestClient(
        app,
        base_url="http://198.51.100.7",
        client=("198.51.100.7", 50001),
    )
    remote.cookies.set(SESSION_COOKIE, remote_token)
    remote_status = remote.get("/api/v10/web/wp15-live-acceptance/status")
    assert remote_status.status_code == 200
    assert remote_status.json() == {"enabled": False}
    remote_start = remote.post(
        "/api/v10/web/wp15-live-acceptance/start",
        json={"connection_id": CONNECTION_ID, "account_index": 0},
    )
    assert remote_start.status_code == 404
