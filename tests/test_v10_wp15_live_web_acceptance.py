from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

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
from omni_cio.contracts.v1.portfolio import (
    InstrumentIdentity,
    InstrumentType,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    ValuationBasis,
)
from omni_cio.web.live_acceptance_v1 import (
    BrokerLiveAcceptanceError,
    BrokerLiveAcceptanceServiceV1,
    PendingLiveAcceptanceEvidenceWriterV1,
)
from omni_cio.web.persistence_v1 import BrokerConnectionRecordV1


NOW = datetime(2026, 8, 11, 15, 0, tzinfo=timezone.utc)
FINGERPRINT = "a" * 64
BROKER_ACCOUNT_ID = "broker-account:v1:" + ("b" * 64)
IMPLEMENTATION_SHA = "c" * 40


class FakeRepository:
    def __init__(self, records: tuple[BrokerConnectionRecordV1, ...]) -> None:
        self.records = records

    def list_read_connections(
        self, *, tenant_id: str
    ) -> tuple[BrokerConnectionRecordV1, ...]:
        return tuple(record for record in self.records if record.tenant_id == tenant_id)


class FakeVault:
    def __init__(self, value: str = "real-local-test-token") -> None:
        self.value = value
        self.loads: list[str] = []

    def load(self, *, secret_ref: str) -> str:
        self.loads.append(secret_ref)
        return self.value


class FakeAdapter:
    def __init__(self, result: TInvestSnapshotResultV1) -> None:
        self.result = result
        self.allow_partial_values: list[bool] = []

    def read_snapshot(self, *, allow_partial: bool = False) -> TInvestSnapshotResultV1:
        self.allow_partial_values.append(allow_partial)
        return self.result


def _binding(*, access_level: str = "ACCOUNT_ACCESS_LEVEL_READ_ONLY") -> BrokerAccountBindingV1:
    return BrokerAccountBindingV1(
        broker_account_id=BROKER_ACCOUNT_ID,
        account_fingerprint_sha256=FINGERPRINT,
        masked_label="***3118",
        account_type="BROKER_ACCOUNT_TYPE_TINKOFF",
        access_level=access_level,
    )


def _record(*, tenant_id: str = "tenant:owner:v1") -> BrokerConnectionRecordV1:
    return BrokerConnectionRecordV1(
        connection_id="broker-connection:v1:" + ("d" * 64),
        tenant_id=tenant_id,
        provider="t_invest",
        credential_role="read",
        state="ACTIVE",
        secret_ref="read-connection:v1:" + ("e" * 64),
        created_at=NOW - timedelta(days=1),
        last_verified_at=NOW - timedelta(minutes=1),
        accounts=(_binding(),),
    )


def _snapshot_result(
    *,
    freshness: FreshnessState = FreshnessState.FRESH,
    account: BrokerAccountBindingV1 | None = None,
    unresolved: int = 0,
    include_position: bool = True,
) -> TInvestSnapshotResultV1:
    binding = account or _binding()
    provenance = (
        SourceReference(
            provider="T-Invest",
            operation="GetPortfolio",
            retrieved_at=NOW,
            source_id=binding.masked_label,
        ),
    )
    positions = ()
    if include_position:
        positions = (
            PortfolioPositionV1(
                instrument=InstrumentIdentity(
                    name="Сбербанк",
                    ticker="SBER",
                    instrument_type=InstrumentType.SHARE,
                    currency="RUB",
                    lot=10,
                    uid="uid-sensitive-position",
                ),
                quantity_units=Decimal("10"),
                valuation=PositionValuation(
                    basis=ValuationBasis.BROKER_REPORTED,
                    currency="RUB",
                    as_of=NOW,
                    unit_price=Decimal("100"),
                ),
            ),
        )
    return TInvestSnapshotResultV1(
        account=binding,
        snapshot=PortfolioSnapshotV1(
            metadata=ContractMetadata(
                schema_name="portfolio_snapshot",
                retrieved_at=NOW,
                account=AccountReference(masked_id=binding.masked_label),
                provenance=provenance,
                quality=QualityMetadata(
                    quality=DataQuality.VERIFIED,
                    completeness=Completeness.COMPLETE,
                ),
            ),
            positions=positions,
        ),
        freshness=FreshnessMetadataV1(
            retrieved_at=NOW,
            evaluated_at=NOW,
            age_seconds=Decimal("0"),
            stale_after_seconds=300,
            state=freshness,
        ),
        throttle=ThrottleMetadataV1(
            source="fallback",
            effective_requests_per_minute=Decimal("40"),
            minimum_interval_seconds=Decimal("1.5"),
        ),
        portfolio_total=Money(amount=Decimal("1200"), currency="RUB"),
        broker_position_count=len(positions),
        normalized_position_count=len(positions),
        unresolved_position_count=unresolved,
    )


def _writer(tmp_path: Path) -> PendingLiveAcceptanceEvidenceWriterV1:
    root = tmp_path / "pending"
    root.mkdir(parents=True)
    (root / ".omni-cio-wp15-live-pending").write_text(
        "OMNI-CIO-V10-WP15-LIVE-PENDING-v1",
        encoding="ascii",
    )
    return PendingLiveAcceptanceEvidenceWriterV1(root / "owner-confirmation.json")


def _service(
    tmp_path: Path,
    *,
    result: TInvestSnapshotResultV1 | None = None,
    records: tuple[BrokerConnectionRecordV1, ...] | None = None,
) -> tuple[BrokerLiveAcceptanceServiceV1, FakeVault, FakeAdapter]:
    adapter = FakeAdapter(result or _snapshot_result())
    vault = FakeVault()
    service = BrokerLiveAcceptanceServiceV1(
        repository=FakeRepository(records or (_record(),)),
        vault=vault,
        client_factory_builder=lambda token: lambda: token,
        evidence_writer=_writer(tmp_path),
        implementation_sha=IMPLEMENTATION_SHA,
        adapter_factory=lambda client_factory, fingerprint: adapter,
        now=lambda: NOW,
    )
    return service, vault, adapter


def test_live_acceptance_keeps_private_values_out_of_durable_evidence(
    tmp_path: Path,
) -> None:
    service, vault, adapter = _service(tmp_path)
    record = _record()

    view = service.start(
        user_id="user:owner:v1",
        tenant_id=record.tenant_id,
        connection_id=record.connection_id,
        account_index=0,
    )

    assert view.masked_account == "***3118"
    assert view.access_level == "READ_ONLY"
    assert view.portfolio_total == "1200"
    assert view.sample.label == "SBER"
    assert view.sample.quantity == "10"
    assert view.sample.unit_price == "100"
    assert view.sample.market_value == "1000"
    assert view.freshness_state == "FRESH"
    assert vault.loads == [record.secret_ref]
    assert adapter.allow_partial_values == [False]

    evidence = service.confirm(
        user_id="user:owner:v1",
        tenant_id=record.tenant_id,
        challenge_id=view.challenge_id,
        intended_account_confirmed=True,
        portfolio_summary_parity=True,
        sample_position_quantity_value_parity=True,
        freshness_confirmed=True,
    )

    assert evidence["implementation_sha"] == IMPLEMENTATION_SHA
    assert evidence["broker_authority"] == "READ_ONLY"
    assert evidence["portfolio_summary_parity"] is True
    assert evidence["sample_position_quantity_value_parity"] is True
    assert evidence["private_portfolio_values_recorded"] is False
    assert evidence["secret_value_recorded"] is False

    persisted = __import__("json").loads(
        (tmp_path / "pending" / "owner-confirmation.json").read_text(encoding="utf-8")
    )
    forbidden_keys = {
        "token",
        "secret",
        "account_id",
        "account_fingerprint",
        "portfolio_total",
        "sample",
        "quantity",
        "unit_price",
        "market_value",
        "position",
    }
    assert forbidden_keys.isdisjoint(persisted)
    assert persisted == evidence


def test_live_acceptance_rejects_non_read_binding(tmp_path: Path) -> None:
    record = _record()
    broad = BrokerConnectionRecordV1(
        connection_id=record.connection_id,
        tenant_id=record.tenant_id,
        provider=record.provider,
        credential_role=record.credential_role,
        state=record.state,
        secret_ref=record.secret_ref,
        created_at=record.created_at,
        last_verified_at=record.last_verified_at,
        accounts=(_binding(access_level="ACCOUNT_ACCESS_LEVEL_FULL_ACCESS"),),
    )
    service, _, _ = _service(tmp_path, records=(broad,))

    with pytest.raises(BrokerLiveAcceptanceError, match="AUTHORITY_NOT_READ_ONLY"):
        service.start(
            user_id="user:owner:v1",
            tenant_id=broad.tenant_id,
            connection_id=broad.connection_id,
            account_index=0,
        )


def test_live_acceptance_rejects_stale_or_incomplete_snapshot(tmp_path: Path) -> None:
    record = _record()
    stale_service, _, _ = _service(
        tmp_path / "stale",
        result=_snapshot_result(freshness=FreshnessState.STALE),
    )
    with pytest.raises(BrokerLiveAcceptanceError, match="DATA_STALE"):
        stale_service.start(
            user_id="user:owner:v1",
            tenant_id=record.tenant_id,
            connection_id=record.connection_id,
            account_index=0,
        )

    incomplete_service, _, _ = _service(
        tmp_path / "incomplete",
        result=_snapshot_result(unresolved=1),
    )
    with pytest.raises(BrokerLiveAcceptanceError, match="PORTFOLIO_INCOMPLETE"):
        incomplete_service.start(
            user_id="user:owner:v1",
            tenant_id=record.tenant_id,
            connection_id=record.connection_id,
            account_index=0,
        )


def test_live_acceptance_requires_sample_position_and_owner_parity(tmp_path: Path) -> None:
    record = _record()
    empty_service, _, _ = _service(
        tmp_path / "empty",
        result=_snapshot_result(include_position=False),
    )
    with pytest.raises(BrokerLiveAcceptanceError, match="SAMPLE_POSITION_REQUIRED"):
        empty_service.start(
            user_id="user:owner:v1",
            tenant_id=record.tenant_id,
            connection_id=record.connection_id,
            account_index=0,
        )

    service, _, _ = _service(tmp_path / "parity")
    view = service.start(
        user_id="user:owner:v1",
        tenant_id=record.tenant_id,
        connection_id=record.connection_id,
        account_index=0,
    )
    with pytest.raises(BrokerLiveAcceptanceError, match="OWNER_PARITY_NOT_CONFIRMED"):
        service.confirm(
            user_id="user:owner:v1",
            tenant_id=record.tenant_id,
            challenge_id=view.challenge_id,
            intended_account_confirmed=True,
            portfolio_summary_parity=False,
            sample_position_quantity_value_parity=True,
            freshness_confirmed=True,
        )


def test_live_acceptance_challenge_is_tenant_and_user_scoped(tmp_path: Path) -> None:
    record = _record()
    service, _, _ = _service(tmp_path)
    view = service.start(
        user_id="user:owner:v1",
        tenant_id=record.tenant_id,
        connection_id=record.connection_id,
        account_index=0,
    )

    with pytest.raises(BrokerLiveAcceptanceError, match="CHALLENGE_SCOPE_MISMATCH"):
        service.confirm(
            user_id="user:other:v1",
            tenant_id=record.tenant_id,
            challenge_id=view.challenge_id,
            intended_account_confirmed=True,
            portfolio_summary_parity=True,
            sample_position_quantity_value_parity=True,
            freshness_confirmed=True,
        )


def test_pending_evidence_writer_refuses_unmarked_directory(tmp_path: Path) -> None:
    root = tmp_path / "unmarked"
    root.mkdir()
    writer = PendingLiveAcceptanceEvidenceWriterV1(root / "evidence.json")

    with pytest.raises(BrokerLiveAcceptanceError, match="PENDING_BOUNDARY_NOT_READY"):
        writer.write({"ready": True})
