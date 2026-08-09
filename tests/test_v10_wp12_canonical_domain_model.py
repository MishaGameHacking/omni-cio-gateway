from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError
import pytest

from omni_cio.contracts.v1.domain import (
    OWNER_TENANT_ID,
    OWNER_USER_ID,
    BrokerAccountV1,
    BrokerProvider,
    CanonicalDomainCatalogV1,
    DecisionRecordV1,
    EvidenceRecordV1,
    EvidenceSourceKind,
    ExecutionRecordV1,
    IncidentRecordV1,
    IncidentStatus,
    InstrumentPrimaryIdentityKind,
    InstrumentV1,
    JournalRecordV1,
    PlanRecordV1,
    PolicyRecordV1,
    PortfolioSnapshotRecordV1,
    PortfolioV1,
    PositionRecordV1,
    TenantV1,
    UserV1,
    canonical_broker_account_id,
    canonical_instrument_id,
    canonical_position_id,
    require_owner_scope,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc)


def _id(prefix: str, character: str) -> str:
    return f"{prefix}:v1:{character * 64}"


def _valid_catalog() -> CanonicalDomainCatalogV1:
    fingerprint = "1" * 64
    account_id = canonical_broker_account_id(BrokerProvider.T_INVEST, fingerprint)
    portfolio_id = _id("portfolio", "2")
    policy_id = _id("policy", "3")
    snapshot_id = _id("portfolio-snapshot", "4")
    instrument_id = canonical_instrument_id(
        InstrumentPrimaryIdentityKind.BROKER_UID,
        "broker-uid-001",
    )
    evidence_id = _id("evidence", "5")
    incident_id = _id("incident", "6")
    decision_id = _id("decision", "7")
    plan_id = _id("plan", "8")
    execution_id = _id("execution", "9")
    journal_id = _id("journal", "a")

    return CanonicalDomainCatalogV1(
        generated_at=NOW,
        tenants=(TenantV1(created_at=NOW),),
        users=(UserV1(created_at=NOW),),
        broker_accounts=(
            BrokerAccountV1(
                broker_account_id=account_id,
                tenant_id=OWNER_TENANT_ID,
                provider=BrokerProvider.T_INVEST,
                account_fingerprint_sha256=fingerprint,
                masked_label="****1234",
                created_at=NOW,
            ),
        ),
        portfolios=(
            PortfolioV1(
                portfolio_id=portfolio_id,
                tenant_id=OWNER_TENANT_ID,
                broker_account_id=account_id,
                base_currency="RUB",
                created_at=NOW,
                label="OWNER portfolio",
            ),
        ),
        instruments=(
            InstrumentV1(
                instrument_id=instrument_id,
                primary_identity_kind=InstrumentPrimaryIdentityKind.BROKER_UID,
                broker_uid="broker-uid-001",
                figi="BBG000000001",
                class_code="TQBR",
                ticker="SYNTH",
                name="Synthetic Instrument",
            ),
        ),
        policies=(
            PolicyRecordV1(
                policy_id=policy_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                source_policy_id="ips_owner_core",
                source_policy_sha256="b" * 64,
                effective_at=NOW,
            ),
        ),
        snapshots=(
            PortfolioSnapshotRecordV1(
                snapshot_id=snapshot_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                broker_account_id=account_id,
                source_payload_sha256="c" * 64,
                broker_server_at=NOW - timedelta(seconds=1),
                local_received_at=NOW,
            ),
        ),
        positions=(
            PositionRecordV1(
                position_id=canonical_position_id(snapshot_id, instrument_id),
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                instrument_id=instrument_id,
                quantity=Decimal("10"),
                blocked_quantity=Decimal("0"),
            ),
        ),
        evidence=(
            EvidenceRecordV1(
                evidence_id=evidence_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                instrument_id=instrument_id,
                source_kind=EvidenceSourceKind.EXCHANGE,
                payload_sha256="d" * 64,
                published_at=NOW - timedelta(minutes=5),
                retrieved_at=NOW - timedelta(seconds=2),
                broker_server_at=None,
                local_received_at=NOW,
            ),
        ),
        incidents=(
            IncidentRecordV1(
                incident_id=incident_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                status=IncidentStatus.OPEN,
                evidence_ids=(evidence_id,),
                opened_at=NOW,
            ),
        ),
        decisions=(
            DecisionRecordV1(
                decision_id=decision_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                evidence_ids=(evidence_id,),
                payload_sha256="e" * 64,
                decided_at=NOW,
            ),
        ),
        plans=(
            PlanRecordV1(
                plan_id=plan_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                decision_id=decision_id,
                payload_sha256="f" * 64,
                created_at=NOW,
            ),
        ),
        executions=(
            ExecutionRecordV1(
                execution_id=execution_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                snapshot_id=snapshot_id,
                plan_id=plan_id,
                payload_sha256="0" * 64,
                recorded_at=NOW,
            ),
        ),
        journal=(
            JournalRecordV1(
                journal_id=journal_id,
                tenant_id=OWNER_TENANT_ID,
                portfolio_id=portfolio_id,
                policy_id=policy_id,
                decision_id=decision_id,
                plan_id=plan_id,
                execution_id=execution_id,
                incident_id=incident_id,
                payload_sha256="1" * 64,
                recorded_at=NOW,
            ),
        ),
    )


def test_wp12_owner_scoped_canonical_graph_validates() -> None:
    catalog = _valid_catalog()

    assert catalog.tenants[0].tenant_id == OWNER_TENANT_ID
    assert catalog.users[0].user_id == OWNER_USER_ID
    assert catalog.positions[0].instrument_id == catalog.instruments[0].instrument_id
    assert catalog.decisions[0].policy_id == catalog.policies[0].policy_id
    assert catalog.plans[0].decision_id == catalog.decisions[0].decision_id
    assert catalog.executions[0].plan_id == catalog.plans[0].plan_id


def test_wp12_required_models_emit_strict_json_schema() -> None:
    models = (
        TenantV1,
        UserV1,
        BrokerAccountV1,
        PortfolioV1,
        PortfolioSnapshotRecordV1,
        PositionRecordV1,
        InstrumentV1,
        PolicyRecordV1,
        EvidenceRecordV1,
        IncidentRecordV1,
        DecisionRecordV1,
        PlanRecordV1,
        ExecutionRecordV1,
        JournalRecordV1,
        CanonicalDomainCatalogV1,
    )

    for model in models:
        schema = model.model_json_schema()
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False


def test_wp12_public_tenant_creation_fails_closed() -> None:
    with pytest.raises(ValidationError):
        TenantV1(
            tenant_id="tenant:v1:public",
            created_at=NOW,
        )


def test_wp12_cross_tenant_access_fails_closed() -> None:
    catalog = _valid_catalog()

    with pytest.raises(PermissionError, match="cross-tenant"):
        require_owner_scope(
            catalog,
            actor_user_id=OWNER_USER_ID,
            tenant_id="tenant:v1:foreign",
        )

    with pytest.raises(PermissionError, match="only OWNER"):
        require_owner_scope(
            catalog,
            actor_user_id="user:v1:foreign",
            tenant_id=OWNER_TENANT_ID,
        )


def test_wp12_unmasked_account_identifier_is_rejected() -> None:
    fingerprint = "2" * 64
    account_id = canonical_broker_account_id(BrokerProvider.T_INVEST, fingerprint)

    with pytest.raises(ValidationError, match="masked"):
        BrokerAccountV1(
            broker_account_id=account_id,
            tenant_id=OWNER_TENANT_ID,
            provider=BrokerProvider.T_INVEST,
            account_fingerprint_sha256=fingerprint,
            masked_label="123456789012",
            created_at=NOW,
        )


def test_wp12_ticker_or_name_cannot_be_instrument_identity() -> None:
    bogus_id = _id("instrument", "3")

    with pytest.raises(ValidationError, match="broker UID, FIGI or ISIN"):
        InstrumentV1(
            instrument_id=bogus_id,
            primary_identity_kind=InstrumentPrimaryIdentityKind.BROKER_UID,
            class_code="TQBR",
            ticker="SBER",
            name="Similar-looking name",
        )


def test_wp12_display_labels_do_not_change_strong_instrument_identity() -> None:
    instrument_id = canonical_instrument_id(
        InstrumentPrimaryIdentityKind.BROKER_UID,
        "stable-broker-uid",
    )

    first = InstrumentV1(
        instrument_id=instrument_id,
        primary_identity_kind=InstrumentPrimaryIdentityKind.BROKER_UID,
        broker_uid="stable-broker-uid",
        class_code="TQBR",
        ticker="OLD",
        name="Old display label",
    )
    second = InstrumentV1(
        instrument_id=instrument_id,
        primary_identity_kind=InstrumentPrimaryIdentityKind.BROKER_UID,
        broker_uid="stable-broker-uid",
        class_code="TQBR",
        ticker="NEW",
        name="New display label",
    )

    assert first.instrument_id == second.instrument_id


def test_wp12_instrument_alias_collision_is_rejected() -> None:
    catalog = _valid_catalog()
    existing = catalog.instruments[0]
    conflicting_id = canonical_instrument_id(
        InstrumentPrimaryIdentityKind.FIGI,
        "BBG000000099",
    )
    conflicting = InstrumentV1(
        instrument_id=conflicting_id,
        primary_identity_kind=InstrumentPrimaryIdentityKind.FIGI,
        broker_uid=existing.broker_uid,
        figi="BBG000000099",
        class_code="TQBR",
        ticker="DIFF",
        name="Different canonical instrument",
    )

    with pytest.raises(ValidationError, match="alias collision"):
        catalog.model_copy(update={"instruments": (existing, conflicting)}).model_validate(
            {
                **catalog.model_dump(mode="python"),
                "instruments": (existing, conflicting),
            }
        )


def test_wp12_duplicate_position_identity_is_rejected() -> None:
    catalog = _valid_catalog()
    position = catalog.positions[0]

    with pytest.raises(ValidationError, match="duplicate position identity"):
        CanonicalDomainCatalogV1.model_validate(
            {
                **catalog.model_dump(mode="python"),
                "positions": (position, position),
            }
        )


def test_wp12_missing_instrument_reference_is_rejected() -> None:
    catalog = _valid_catalog()
    snapshot = catalog.snapshots[0]
    missing_instrument_id = _id("instrument", "4")
    position = PositionRecordV1(
        position_id=canonical_position_id(snapshot.snapshot_id, missing_instrument_id),
        tenant_id=OWNER_TENANT_ID,
        portfolio_id=snapshot.portfolio_id,
        policy_id=snapshot.policy_id,
        snapshot_id=snapshot.snapshot_id,
        instrument_id=missing_instrument_id,
        quantity=Decimal("1"),
    )

    with pytest.raises(ValidationError, match="unknown instrument"):
        CanonicalDomainCatalogV1.model_validate(
            {
                **catalog.model_dump(mode="python"),
                "positions": (position,),
            }
        )


def test_wp12_cross_portfolio_policy_relationship_is_rejected() -> None:
    catalog = _valid_catalog()
    account_id = catalog.broker_accounts[0].broker_account_id
    second_portfolio_id = _id("portfolio", "b")
    second_portfolio = PortfolioV1(
        portfolio_id=second_portfolio_id,
        tenant_id=OWNER_TENANT_ID,
        broker_account_id=account_id,
        base_currency="RUB",
        created_at=NOW,
        label="Second synthetic portfolio",
    )
    evidence = catalog.evidence[0].model_copy(
        update={"portfolio_id": second_portfolio_id}
    )

    with pytest.raises(ValidationError, match="policy crosses portfolio scope"):
        CanonicalDomainCatalogV1.model_validate(
            {
                **catalog.model_dump(mode="python"),
                "portfolios": (*catalog.portfolios, second_portfolio),
                "evidence": (evidence,),
            }
        )


def test_wp12_persisted_timestamps_require_timezone_and_normalize_to_utc() -> None:
    catalog = _valid_catalog()
    plus_three = timezone(timedelta(hours=3))
    local_time = datetime(2026, 8, 9, 15, 0, tzinfo=plus_three)
    portfolio = catalog.portfolios[0].model_copy(update={"created_at": local_time})
    normalized = PortfolioV1.model_validate(portfolio.model_dump(mode="python"))

    assert normalized.created_at == NOW
    assert normalized.created_at.utcoffset() == timedelta(0)

    with pytest.raises(ValidationError, match="timezone-aware"):
        PortfolioV1(
            portfolio_id=catalog.portfolios[0].portfolio_id,
            tenant_id=OWNER_TENANT_ID,
            broker_account_id=catalog.broker_accounts[0].broker_account_id,
            base_currency="RUB",
            created_at=datetime(2026, 8, 9, 12, 0),
        )


def test_wp12_evidence_keeps_distinct_temporal_semantics() -> None:
    record = _valid_catalog().evidence[0]

    assert record.published_at is not None
    assert record.published_at < record.retrieved_at < record.local_received_at
    assert record.broker_server_at is None


def test_wp12_domain_contract_does_not_import_persistence_or_execution_authority() -> None:
    source = (ROOT / "omni_cio/contracts/v1/domain.py").read_text(encoding="utf-8")

    for forbidden in (
        "psycopg",
        "sqlalchemy",
        "omni_cio.real_trading",
        "omni_cio.plan_execution",
        "TINVEST_TRADING_TOKEN",
    ):
        assert forbidden not in source
