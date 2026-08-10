from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from omni_cio.contracts.v1.domain import (
    OWNER_TENANT_ID,
    BrokerAccountV1,
    CanonicalDomainCatalogV1,
    DecisionRecordV1,
    EvidenceRecordV1,
    ExecutionRecordV1,
    IncidentRecordV1,
    InstrumentV1,
    JournalRecordV1,
    PlanRecordV1,
    PolicyRecordV1,
    PortfolioSnapshotRecordV1,
    PortfolioV1,
    PositionRecordV1,
    TenantV1,
    UserV1,
)
from omni_cio.persistence.migration import ConnectionLike, SCHEMA_NAME


class PersistenceReadError(RuntimeError):
    """Raised when durable canonical state cannot be reconstructed safely."""


def _rows(connection: ConnectionLike, query: str) -> list[Sequence[Any]]:
    return connection.execute(query).fetchall()


def _latest_incident_revision(
    connection: ConnectionLike,
    incident_id: str,
) -> tuple[int, str]:
    row = connection.execute(
        f"SELECT revision, status FROM {SCHEMA_NAME}.incident_revisions "
        "WHERE incident_id = %s ORDER BY revision DESC LIMIT 1",
        (incident_id,),
    ).fetchone()
    if row is None:
        raise PersistenceReadError("incident has no durable revision")
    return int(row[0]), str(row[1])


def _incident_evidence_ids(
    connection: ConnectionLike,
    incident_id: str,
    revision: int,
) -> tuple[str, ...]:
    rows = connection.execute(
        f"SELECT evidence_id FROM {SCHEMA_NAME}.incident_evidence "
        "WHERE incident_id = %s AND incident_revision = %s ORDER BY evidence_id",
        (incident_id, revision),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def _decision_evidence_ids(
    connection: ConnectionLike,
    decision_id: str,
) -> tuple[str, ...]:
    rows = connection.execute(
        f"SELECT evidence_id FROM {SCHEMA_NAME}.decision_evidence "
        "WHERE decision_id = %s ORDER BY evidence_id",
        (decision_id,),
    ).fetchall()
    return tuple(str(row[0]) for row in rows)


def load_catalog(connection: ConnectionLike) -> CanonicalDomainCatalogV1:
    """Reconstruct the current canonical OWNER graph from PostgreSQL.

    The returned WP12 contract re-validates every identity and cross-scope
    relationship. No volatile fallback is used when durable state is missing.
    """

    revision = connection.execute(
        f"SELECT generated_at FROM {SCHEMA_NAME}.state_revisions "
        "WHERE tenant_id = %s ORDER BY revision DESC LIMIT 1",
        (OWNER_TENANT_ID,),
    ).fetchone()
    if revision is None:
        raise PersistenceReadError("no canonical state revision is available")

    tenants = tuple(
        TenantV1(
            tenant_id=row[0],
            schema_version=row[1],
            identity_version=row[2],
            mode=row[3],
            created_at=row[4],
        )
        for row in _rows(
            connection,
            f"SELECT tenant_id, schema_version, identity_version, mode, created_at "
            f"FROM {SCHEMA_NAME}.tenants ORDER BY tenant_id",
        )
    )
    users = tuple(
        UserV1(
            user_id=row[0],
            tenant_id=row[1],
            schema_version=row[2],
            identity_version=row[3],
            role=row[4],
            created_at=row[5],
        )
        for row in _rows(
            connection,
            f"SELECT user_id, tenant_id, schema_version, identity_version, role, "
            f"created_at FROM {SCHEMA_NAME}.users ORDER BY user_id",
        )
    )
    broker_accounts = tuple(
        BrokerAccountV1(
            broker_account_id=row[0],
            tenant_id=row[1],
            schema_version=row[2],
            identity_version=row[3],
            provider=row[4],
            account_fingerprint_sha256=row[5],
            masked_label=row[6],
            created_at=row[7],
        )
        for row in _rows(
            connection,
            f"SELECT broker_account_id, tenant_id, schema_version, identity_version, "
            f"provider, account_fingerprint_sha256, masked_label, created_at "
            f"FROM {SCHEMA_NAME}.broker_accounts ORDER BY broker_account_id",
        )
    )
    portfolios = tuple(
        PortfolioV1(
            portfolio_id=row[0],
            tenant_id=row[1],
            broker_account_id=row[2],
            schema_version=row[3],
            identity_version=row[4],
            base_currency=row[5],
            created_at=row[6],
            label=row[7],
        )
        for row in _rows(
            connection,
            f"SELECT portfolio_id, tenant_id, broker_account_id, schema_version, "
            f"identity_version, base_currency, created_at, label "
            f"FROM {SCHEMA_NAME}.portfolios ORDER BY portfolio_id",
        )
    )
    instruments = tuple(
        InstrumentV1(
            instrument_id=row[0],
            schema_version=row[1],
            identity_version=row[2],
            primary_identity_kind=row[3],
            broker_uid=row[4],
            figi=row[5],
            isin=row[6],
            class_code=row[7],
            ticker=row[8],
            name=row[9],
        )
        for row in _rows(
            connection,
            f"SELECT instrument_id, schema_version, identity_version, "
            f"primary_identity_kind, broker_uid, figi, isin, class_code, ticker, name "
            f"FROM {SCHEMA_NAME}.instruments ORDER BY instrument_id",
        )
    )
    policies = tuple(
        PolicyRecordV1(
            policy_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            schema_version=row[3],
            identity_version=row[4],
            source_policy_id=row[5],
            source_policy_sha256=row[6],
            effective_at=row[7],
        )
        for row in _rows(
            connection,
            f"SELECT policy_id, tenant_id, portfolio_id, schema_version, "
            f"identity_version, source_policy_id, source_policy_sha256, effective_at "
            f"FROM {SCHEMA_NAME}.policies ORDER BY policy_id",
        )
    )
    snapshots = tuple(
        PortfolioSnapshotRecordV1(
            snapshot_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            broker_account_id=row[4],
            schema_version=row[5],
            identity_version=row[6],
            source_payload_sha256=row[7],
            broker_server_at=row[8],
            local_received_at=row[9],
        )
        for row in _rows(
            connection,
            f"SELECT snapshot_id, tenant_id, portfolio_id, policy_id, broker_account_id, "
            f"schema_version, identity_version, source_payload_sha256, broker_server_at, "
            f"local_received_at FROM {SCHEMA_NAME}.portfolio_snapshots ORDER BY snapshot_id",
        )
    )
    positions = tuple(
        PositionRecordV1(
            position_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            snapshot_id=row[4],
            instrument_id=row[5],
            schema_version=row[6],
            identity_version=row[7],
            quantity=row[8],
            blocked_quantity=row[9],
        )
        for row in _rows(
            connection,
            f"SELECT position_id, tenant_id, portfolio_id, policy_id, snapshot_id, "
            f"instrument_id, schema_version, identity_version, quantity, blocked_quantity "
            f"FROM {SCHEMA_NAME}.positions ORDER BY position_id",
        )
    )
    evidence = tuple(
        EvidenceRecordV1(
            evidence_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            instrument_id=row[4],
            schema_version=row[5],
            identity_version=row[6],
            source_kind=row[7],
            payload_sha256=row[8],
            published_at=row[9],
            retrieved_at=row[10],
            broker_server_at=row[11],
            local_received_at=row[12],
        )
        for row in _rows(
            connection,
            f"SELECT evidence_id, tenant_id, portfolio_id, policy_id, instrument_id, "
            f"schema_version, identity_version, source_kind, payload_sha256, published_at, "
            f"retrieved_at, broker_server_at, local_received_at "
            f"FROM {SCHEMA_NAME}.evidence ORDER BY evidence_id",
        )
    )

    incident_records: list[IncidentRecordV1] = []
    for row in _rows(
        connection,
        f"SELECT incident_id, tenant_id, portfolio_id, policy_id, schema_version, "
        f"identity_version, opened_at FROM {SCHEMA_NAME}.incidents ORDER BY incident_id",
    ):
        revision_number, status = _latest_incident_revision(connection, str(row[0]))
        incident_records.append(
            IncidentRecordV1(
                incident_id=row[0],
                tenant_id=row[1],
                portfolio_id=row[2],
                policy_id=row[3],
                schema_version=row[4],
                identity_version=row[5],
                status=status,
                evidence_ids=_incident_evidence_ids(
                    connection,
                    str(row[0]),
                    revision_number,
                ),
                opened_at=row[6],
            )
        )

    decision_records: list[DecisionRecordV1] = []
    for row in _rows(
        connection,
        f"SELECT decision_id, tenant_id, portfolio_id, policy_id, snapshot_id, "
        f"schema_version, identity_version, payload_sha256, decided_at "
        f"FROM {SCHEMA_NAME}.decisions ORDER BY decision_id",
    ):
        decision_records.append(
            DecisionRecordV1(
                decision_id=row[0],
                tenant_id=row[1],
                portfolio_id=row[2],
                policy_id=row[3],
                snapshot_id=row[4],
                schema_version=row[5],
                identity_version=row[6],
                evidence_ids=_decision_evidence_ids(connection, str(row[0])),
                payload_sha256=row[7],
                decided_at=row[8],
            )
        )

    plans = tuple(
        PlanRecordV1(
            plan_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            snapshot_id=row[4],
            decision_id=row[5],
            schema_version=row[6],
            identity_version=row[7],
            payload_sha256=row[8],
            created_at=row[9],
        )
        for row in _rows(
            connection,
            f"SELECT plan_id, tenant_id, portfolio_id, policy_id, snapshot_id, decision_id, "
            f"schema_version, identity_version, payload_sha256, created_at "
            f"FROM {SCHEMA_NAME}.plans ORDER BY plan_id",
        )
    )
    executions = tuple(
        ExecutionRecordV1(
            execution_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            snapshot_id=row[4],
            plan_id=row[5],
            schema_version=row[6],
            identity_version=row[7],
            payload_sha256=row[8],
            recorded_at=row[9],
        )
        for row in _rows(
            connection,
            f"SELECT execution_id, tenant_id, portfolio_id, policy_id, snapshot_id, plan_id, "
            f"schema_version, identity_version, payload_sha256, recorded_at "
            f"FROM {SCHEMA_NAME}.executions ORDER BY execution_id",
        )
    )
    journal = tuple(
        JournalRecordV1(
            journal_id=row[0],
            tenant_id=row[1],
            portfolio_id=row[2],
            policy_id=row[3],
            decision_id=row[4],
            plan_id=row[5],
            execution_id=row[6],
            incident_id=row[7],
            schema_version=row[8],
            identity_version=row[9],
            payload_sha256=row[10],
            recorded_at=row[11],
        )
        for row in _rows(
            connection,
            f"SELECT journal_id, tenant_id, portfolio_id, policy_id, decision_id, plan_id, "
            f"execution_id, incident_id, schema_version, identity_version, payload_sha256, "
            f"recorded_at FROM {SCHEMA_NAME}.journal ORDER BY journal_id",
        )
    )

    return CanonicalDomainCatalogV1(
        generated_at=revision[0],
        tenants=tenants,
        users=users,
        broker_accounts=broker_accounts,
        portfolios=portfolios,
        instruments=instruments,
        policies=policies,
        snapshots=snapshots,
        positions=positions,
        evidence=evidence,
        incidents=tuple(incident_records),
        decisions=tuple(decision_records),
        plans=plans,
        executions=executions,
        journal=journal,
    )
