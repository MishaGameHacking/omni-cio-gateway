from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
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


AUDIT_DIGEST_TABLES: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
    ("tenants", ("tenant_id",), "record_sha256"),
    ("users", ("user_id",), "record_sha256"),
    ("broker_accounts", ("broker_account_id",), "record_sha256"),
    ("portfolios", ("portfolio_id",), "record_sha256"),
    ("instruments", ("instrument_id",), "record_sha256"),
    ("policies", ("policy_id",), "record_sha256"),
    ("portfolio_snapshots", ("snapshot_id",), "record_sha256"),
    ("positions", ("position_id",), "record_sha256"),
    ("evidence", ("evidence_id",), "record_sha256"),
    ("incidents", ("incident_id",), "identity_sha256"),
    ("incident_revisions", ("incident_id", "revision"), "record_sha256"),
    (
        "incident_evidence",
        ("incident_id", "incident_revision", "evidence_id"),
        None,
    ),
    ("decisions", ("decision_id",), "record_sha256"),
    ("decision_evidence", ("decision_id", "evidence_id"), None),
    ("plans", ("plan_id",), "record_sha256"),
    ("executions", ("execution_id",), "record_sha256"),
    ("journal", ("journal_id",), "record_sha256"),
    ("content_blobs", ("tenant_id", "payload_sha256"), None),
    ("jobs", ("job_id",), "payload_sha256"),
)


class PersistenceConflictError(RuntimeError):
    """Same canonical identity was replayed with conflicting immutable content."""


class ContentHashMismatchError(ValueError):
    """Provided content does not match its claimed SHA-256 identity."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("persisted timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def model_record_sha256(model: Any) -> str:
    payload = model.model_dump(mode="json")
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def catalog_sha256(catalog: CanonicalDomainCatalogV1) -> str:
    return hashlib.sha256(
        _canonical_json(catalog.model_dump(mode="json"))
    ).hexdigest()


def _insert_immutable(
    connection: ConnectionLike,
    *,
    table: str,
    key_columns: tuple[str, ...],
    key_values: tuple[Any, ...],
    values: dict[str, Any],
    record_sha256: str,
    hash_column: str = "record_sha256",
) -> None:
    columns = (*values.keys(), hash_column)
    params = (*values.values(), record_sha256)
    placeholders = ", ".join("%s" for _ in columns)
    column_sql = ", ".join(columns)
    key_sql = ", ".join(key_columns)
    cursor = connection.execute(
        f"INSERT INTO {SCHEMA_NAME}.{table} ({column_sql}) "
        f"VALUES ({placeholders}) ON CONFLICT ({key_sql}) DO NOTHING "
        f"RETURNING {hash_column}",
        params,
    )
    if cursor.fetchone() is not None:
        return

    predicate = " AND ".join(f"{column} = %s" for column in key_columns)
    existing = connection.execute(
        f"SELECT {hash_column} FROM {SCHEMA_NAME}.{table} WHERE {predicate}",
        key_values,
    ).fetchone()
    if existing is None:
        raise PersistenceConflictError(
            f"{table} insert conflicted with a secondary uniqueness constraint"
        )
    if str(existing[0]) != record_sha256:
        raise PersistenceConflictError(
            f"{table} canonical identity replay conflicts with immutable content"
        )


def _persist_tenant(connection: ConnectionLike, record: TenantV1) -> None:
    _insert_immutable(
        connection,
        table="tenants",
        key_columns=("tenant_id",),
        key_values=(record.tenant_id,),
        values={
            "tenant_id": record.tenant_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "mode": record.mode.value,
            "created_at": _utc(record.created_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_user(connection: ConnectionLike, record: UserV1) -> None:
    _insert_immutable(
        connection,
        table="users",
        key_columns=("user_id",),
        key_values=(record.user_id,),
        values={
            "user_id": record.user_id,
            "tenant_id": record.tenant_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "role": record.role.value,
            "created_at": _utc(record.created_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_broker_account(connection: ConnectionLike, record: BrokerAccountV1) -> None:
    _insert_immutable(
        connection,
        table="broker_accounts",
        key_columns=("broker_account_id",),
        key_values=(record.broker_account_id,),
        values={
            "broker_account_id": record.broker_account_id,
            "tenant_id": record.tenant_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "provider": record.provider.value,
            "account_fingerprint_sha256": record.account_fingerprint_sha256,
            "masked_label": record.masked_label,
            "created_at": _utc(record.created_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_portfolio(connection: ConnectionLike, record: PortfolioV1) -> None:
    _insert_immutable(
        connection,
        table="portfolios",
        key_columns=("portfolio_id",),
        key_values=(record.portfolio_id,),
        values={
            "portfolio_id": record.portfolio_id,
            "tenant_id": record.tenant_id,
            "broker_account_id": record.broker_account_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "base_currency": record.base_currency,
            "created_at": _utc(record.created_at),
            "label": record.label,
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_instrument(connection: ConnectionLike, record: InstrumentV1) -> None:
    _insert_immutable(
        connection,
        table="instruments",
        key_columns=("instrument_id",),
        key_values=(record.instrument_id,),
        values={
            "instrument_id": record.instrument_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "primary_identity_kind": record.primary_identity_kind.value,
            "broker_uid": record.broker_uid,
            "figi": record.figi,
            "isin": record.isin,
            "class_code": record.class_code,
            "ticker": record.ticker,
            "name": record.name,
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_policy(connection: ConnectionLike, record: PolicyRecordV1) -> None:
    _insert_immutable(
        connection,
        table="policies",
        key_columns=("policy_id",),
        key_values=(record.policy_id,),
        values={
            "policy_id": record.policy_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "source_policy_id": record.source_policy_id,
            "source_policy_sha256": record.source_policy_sha256,
            "effective_at": _utc(record.effective_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_snapshot(
    connection: ConnectionLike,
    record: PortfolioSnapshotRecordV1,
) -> None:
    _insert_immutable(
        connection,
        table="portfolio_snapshots",
        key_columns=("snapshot_id",),
        key_values=(record.snapshot_id,),
        values={
            "snapshot_id": record.snapshot_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "broker_account_id": record.broker_account_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "source_payload_sha256": record.source_payload_sha256,
            "broker_server_at": (
                _utc(record.broker_server_at)
                if record.broker_server_at is not None
                else None
            ),
            "local_received_at": _utc(record.local_received_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_position(connection: ConnectionLike, record: PositionRecordV1) -> None:
    _insert_immutable(
        connection,
        table="positions",
        key_columns=("position_id",),
        key_values=(record.position_id,),
        values={
            "position_id": record.position_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "snapshot_id": record.snapshot_id,
            "instrument_id": record.instrument_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "quantity": record.quantity,
            "blocked_quantity": record.blocked_quantity,
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_evidence(connection: ConnectionLike, record: EvidenceRecordV1) -> None:
    _insert_immutable(
        connection,
        table="evidence",
        key_columns=("evidence_id",),
        key_values=(record.evidence_id,),
        values={
            "evidence_id": record.evidence_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "instrument_id": record.instrument_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "source_kind": record.source_kind.value,
            "payload_sha256": record.payload_sha256,
            "published_at": _utc(record.published_at) if record.published_at else None,
            "retrieved_at": _utc(record.retrieved_at),
            "broker_server_at": (
                _utc(record.broker_server_at) if record.broker_server_at else None
            ),
            "local_received_at": _utc(record.local_received_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _incident_identity_sha256(record: IncidentRecordV1) -> str:
    payload = {
        "schema_version": record.schema_version,
        "identity_version": record.identity_version,
        "incident_id": record.incident_id,
        "tenant_id": record.tenant_id,
        "portfolio_id": record.portfolio_id,
        "policy_id": record.policy_id,
        "opened_at": _utc(record.opened_at).isoformat(),
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _persist_incident(connection: ConnectionLike, record: IncidentRecordV1) -> None:
    identity_hash = _incident_identity_sha256(record)
    _insert_immutable(
        connection,
        table="incidents",
        key_columns=("incident_id",),
        key_values=(record.incident_id,),
        values={
            "incident_id": record.incident_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "opened_at": _utc(record.opened_at),
        },
        record_sha256=identity_hash,
        hash_column="identity_sha256",
    )

    revision_hash = model_record_sha256(record)
    existing = connection.execute(
        f"SELECT revision FROM {SCHEMA_NAME}.incident_revisions "
        "WHERE incident_id = %s AND record_sha256 = %s",
        (record.incident_id, revision_hash),
    ).fetchone()
    if existing is not None:
        revision = int(existing[0])
    else:
        connection.execute(
            f"SELECT incident_id FROM {SCHEMA_NAME}.incidents "
            "WHERE incident_id = %s FOR UPDATE",
            (record.incident_id,),
        )
        row = connection.execute(
            f"SELECT COALESCE(MAX(revision), 0) + 1 FROM {SCHEMA_NAME}.incident_revisions "
            "WHERE incident_id = %s",
            (record.incident_id,),
        ).fetchone()
        if row is None:
            raise PersistenceConflictError("cannot allocate incident revision")
        revision = int(row[0])
        connection.execute(
            f"INSERT INTO {SCHEMA_NAME}.incident_revisions "
            "(incident_id, revision, status, revised_at, record_sha256) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                record.incident_id,
                revision,
                record.status.value,
                _utc(record.opened_at),
                revision_hash,
            ),
        )

    for evidence_id in record.evidence_ids:
        connection.execute(
            f"INSERT INTO {SCHEMA_NAME}.incident_evidence "
            "(incident_id, incident_revision, evidence_id, tenant_id, portfolio_id, policy_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                record.incident_id,
                revision,
                evidence_id,
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
            ),
        )


def _persist_decision(connection: ConnectionLike, record: DecisionRecordV1) -> None:
    _insert_immutable(
        connection,
        table="decisions",
        key_columns=("decision_id",),
        key_values=(record.decision_id,),
        values={
            "decision_id": record.decision_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "snapshot_id": record.snapshot_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "payload_sha256": record.payload_sha256,
            "decided_at": _utc(record.decided_at),
        },
        record_sha256=model_record_sha256(record),
    )
    for evidence_id in record.evidence_ids:
        connection.execute(
            f"INSERT INTO {SCHEMA_NAME}.decision_evidence "
            "(decision_id, evidence_id, tenant_id, portfolio_id, policy_id) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (
                record.decision_id,
                evidence_id,
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
            ),
        )


def _persist_plan(connection: ConnectionLike, record: PlanRecordV1) -> None:
    _insert_immutable(
        connection,
        table="plans",
        key_columns=("plan_id",),
        key_values=(record.plan_id,),
        values={
            "plan_id": record.plan_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "snapshot_id": record.snapshot_id,
            "decision_id": record.decision_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "payload_sha256": record.payload_sha256,
            "created_at": _utc(record.created_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_execution(connection: ConnectionLike, record: ExecutionRecordV1) -> None:
    _insert_immutable(
        connection,
        table="executions",
        key_columns=("execution_id",),
        key_values=(record.execution_id,),
        values={
            "execution_id": record.execution_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "snapshot_id": record.snapshot_id,
            "plan_id": record.plan_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "payload_sha256": record.payload_sha256,
            "recorded_at": _utc(record.recorded_at),
        },
        record_sha256=model_record_sha256(record),
    )


def _persist_journal(connection: ConnectionLike, record: JournalRecordV1) -> None:
    _insert_immutable(
        connection,
        table="journal",
        key_columns=("journal_id",),
        key_values=(record.journal_id,),
        values={
            "journal_id": record.journal_id,
            "tenant_id": record.tenant_id,
            "portfolio_id": record.portfolio_id,
            "policy_id": record.policy_id,
            "decision_id": record.decision_id,
            "plan_id": record.plan_id,
            "execution_id": record.execution_id,
            "incident_id": record.incident_id,
            "schema_version": record.schema_version,
            "identity_version": record.identity_version,
            "payload_sha256": record.payload_sha256,
            "recorded_at": _utc(record.recorded_at),
        },
        record_sha256=model_record_sha256(record),
    )


class PostgresDomainRepository:
    def __init__(self, connection: ConnectionLike) -> None:
        self._connection = connection

    def persist_catalog(self, catalog: CanonicalDomainCatalogV1) -> int:
        if catalog.tenants[0].tenant_id != OWNER_TENANT_ID:
            raise PermissionError("WP13 persistence admits only the OWNER tenant")

        digest = catalog_sha256(catalog)
        with self._connection.transaction():
            for record in catalog.tenants:
                _persist_tenant(self._connection, record)
            for record in catalog.users:
                _persist_user(self._connection, record)
            for record in catalog.broker_accounts:
                _persist_broker_account(self._connection, record)
            for record in catalog.portfolios:
                _persist_portfolio(self._connection, record)
            for record in catalog.instruments:
                _persist_instrument(self._connection, record)
            for record in catalog.policies:
                _persist_policy(self._connection, record)
            for record in catalog.snapshots:
                _persist_snapshot(self._connection, record)
            for record in catalog.positions:
                _persist_position(self._connection, record)
            for record in catalog.evidence:
                _persist_evidence(self._connection, record)
            for record in catalog.incidents:
                _persist_incident(self._connection, record)
            for record in catalog.decisions:
                _persist_decision(self._connection, record)
            for record in catalog.plans:
                _persist_plan(self._connection, record)
            for record in catalog.executions:
                _persist_execution(self._connection, record)
            for record in catalog.journal:
                _persist_journal(self._connection, record)

            self._connection.execute(
                f"INSERT INTO {SCHEMA_NAME}.state_revisions "
                "(tenant_id, catalog_sha256, generated_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (tenant_id, catalog_sha256) DO NOTHING",
                (OWNER_TENANT_ID, digest, _utc(catalog.generated_at)),
            )
            row = self._connection.execute(
                f"SELECT revision FROM {SCHEMA_NAME}.state_revisions "
                "WHERE tenant_id = %s AND catalog_sha256 = %s",
                (OWNER_TENANT_ID, digest),
            ).fetchone()
            if row is None:
                raise PersistenceConflictError("state revision was not persisted")
            return int(row[0])

    def put_content_blob(
        self,
        payload: bytes,
        *,
        media_type: str,
        schema_ref: str | None = None,
        expected_sha256: str | None = None,
        created_at: datetime | None = None,
    ) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ContentHashMismatchError("payload SHA-256 does not match expected identity")
        timestamp = _utc(created_at or datetime.now(timezone.utc))
        with self._connection.transaction():
            cursor = self._connection.execute(
                f"INSERT INTO {SCHEMA_NAME}.content_blobs "
                "(tenant_id, payload_sha256, media_type, schema_ref, payload, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING "
                "RETURNING payload_sha256",
                (
                    OWNER_TENANT_ID,
                    digest,
                    media_type,
                    schema_ref,
                    payload,
                    timestamp,
                ),
            )
            if cursor.fetchone() is None:
                row = self._connection.execute(
                    f"SELECT media_type, schema_ref, payload FROM {SCHEMA_NAME}.content_blobs "
                    "WHERE tenant_id = %s AND payload_sha256 = %s",
                    (OWNER_TENANT_ID, digest),
                ).fetchone()
                if row is None or bytes(row[2]) != payload:
                    raise PersistenceConflictError("content hash identity conflict")
        return digest

    def prune_research_cache(self, *, expired_before: datetime) -> int:
        with self._connection.transaction():
            cursor = self._connection.execute(
                f"DELETE FROM {SCHEMA_NAME}.research_cache WHERE expires_at <= %s",
                (_utc(expired_before),),
            )
            return cursor.rowcount

    def prune_system_health(self, *, observed_before: datetime) -> int:
        with self._connection.transaction():
            cursor = self._connection.execute(
                f"DELETE FROM {SCHEMA_NAME}.system_health WHERE observed_at < %s",
                (_utc(observed_before),),
            )
            return cursor.rowcount

    def state_digest(self) -> str:
        digest = hashlib.sha256()
        for table, key_columns, hash_column in AUDIT_DIGEST_TABLES:
            selected = [*key_columns]
            if hash_column is not None and hash_column not in selected:
                selected.append(hash_column)
            rows = self._connection.execute(
                f"SELECT {', '.join(selected)} FROM {SCHEMA_NAME}.{table} "
                f"ORDER BY {', '.join(key_columns)}"
            ).fetchall()
            for row in rows:
                encoded = _canonical_json(
                    [table, *(_digest_value(value) for value in row)]
                )
                digest.update(encoded)
                digest.update(b"\n")
        return digest.hexdigest()


def _digest_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return value


def count_rows(connection: ConnectionLike, tables: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for table in tables:
        row = connection.execute(f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{table}").fetchone()
        if row is None:
            raise RuntimeError(f"row count unavailable for {table}")
        result[table] = int(row[0])
    return result
