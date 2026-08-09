from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import hashlib
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel, CurrencyCode


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
TenantId = Annotated[str, Field(pattern=r"^tenant:v1:[a-z0-9][a-z0-9_-]{2,63}$")]
UserId = Annotated[str, Field(pattern=r"^user:v1:[a-z0-9][a-z0-9_-]{2,63}$")]
BrokerAccountId = Annotated[
    str, Field(pattern=r"^broker-account:v1:[a-f0-9]{64}$")
]
PortfolioId = Annotated[str, Field(pattern=r"^portfolio:v1:[a-f0-9]{64}$")]
PortfolioSnapshotId = Annotated[
    str, Field(pattern=r"^portfolio-snapshot:v1:[a-f0-9]{64}$")
]
PositionId = Annotated[str, Field(pattern=r"^position:v1:[a-f0-9]{64}$")]
InstrumentId = Annotated[str, Field(pattern=r"^instrument:v1:[a-f0-9]{64}$")]
PolicyId = Annotated[str, Field(pattern=r"^policy:v1:[a-f0-9]{64}$")]
EvidenceId = Annotated[str, Field(pattern=r"^evidence:v1:[a-f0-9]{64}$")]
IncidentId = Annotated[str, Field(pattern=r"^incident:v1:[a-f0-9]{64}$")]
DecisionId = Annotated[str, Field(pattern=r"^decision:v1:[a-f0-9]{64}$")]
PlanId = Annotated[str, Field(pattern=r"^plan:v1:[a-f0-9]{64}$")]
ExecutionId = Annotated[str, Field(pattern=r"^execution:v1:[a-f0-9]{64}$")]
JournalId = Annotated[str, Field(pattern=r"^journal:v1:[a-f0-9]{64}$")]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0"), allow_inf_nan=False),
]

OWNER_TENANT_ID = "tenant:v1:owner"
OWNER_USER_ID = "user:v1:owner"


class TenantMode(StrEnum):
    OWNER_PERSONAL = "owner_personal"


class UserRole(StrEnum):
    OWNER = "owner"


class BrokerProvider(StrEnum):
    T_INVEST = "t_invest"
    OTHER = "other"


class InstrumentPrimaryIdentityKind(StrEnum):
    BROKER_UID = "broker_uid"
    FIGI = "figi"
    ISIN = "isin"


class EvidenceSourceKind(StrEnum):
    BROKER = "broker"
    EXCHANGE = "exchange"
    REGULATOR = "regulator"
    ISSUER = "issuer"
    RESEARCH = "research"
    SYSTEM = "system"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"


def _utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_broker_account_id(
    provider: BrokerProvider,
    account_fingerprint_sha256: str,
) -> str:
    return f"broker-account:v1:{_digest(f'{provider.value}:{account_fingerprint_sha256}')}"


def canonical_instrument_id(
    primary_kind: InstrumentPrimaryIdentityKind,
    primary_value: str,
) -> str:
    normalized = primary_value.strip()
    if primary_kind in {
        InstrumentPrimaryIdentityKind.FIGI,
        InstrumentPrimaryIdentityKind.ISIN,
    }:
        normalized = normalized.upper()
    return f"instrument:v1:{_digest(f'{primary_kind.value}:{normalized}')}"


def canonical_position_id(
    snapshot_id: str,
    instrument_id: str,
) -> str:
    return f"position:v1:{_digest(f'{snapshot_id}:{instrument_id}')}"


class TenantV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    tenant_id: Literal["tenant:v1:owner"] = OWNER_TENANT_ID
    mode: Literal[TenantMode.OWNER_PERSONAL] = TenantMode.OWNER_PERSONAL
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="created_at")


class UserV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    user_id: Literal["user:v1:owner"] = OWNER_USER_ID
    tenant_id: Literal["tenant:v1:owner"] = OWNER_TENANT_ID
    role: Literal[UserRole.OWNER] = UserRole.OWNER
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="created_at")


class BrokerAccountV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    broker_account_id: BrokerAccountId
    tenant_id: TenantId
    provider: BrokerProvider
    account_fingerprint_sha256: Sha256
    masked_label: Annotated[str, Field(min_length=4, max_length=96)]
    created_at: datetime

    @field_validator("masked_label")
    @classmethod
    def require_masked_label(cls, value: str) -> str:
        mask_characters = {"*", "•", "…", "x", "X"}
        if not any(character in value for character in mask_characters):
            raise ValueError("broker account label must be masked")
        return value

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="created_at")

    @model_validator(mode="after")
    def validate_identity(self) -> BrokerAccountV1:
        expected = canonical_broker_account_id(
            self.provider,
            self.account_fingerprint_sha256,
        )
        if self.broker_account_id != expected:
            raise ValueError("broker_account_id does not match canonical fingerprint identity")
        return self


class PortfolioV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    portfolio_id: PortfolioId
    tenant_id: TenantId
    broker_account_id: BrokerAccountId
    base_currency: CurrencyCode
    created_at: datetime
    label: Annotated[str | None, Field(max_length=96)] = None

    @field_validator("base_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="created_at")


class InstrumentV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    instrument_id: InstrumentId
    primary_identity_kind: InstrumentPrimaryIdentityKind
    broker_uid: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    figi: Annotated[str | None, Field(min_length=1, max_length=32)] = None
    isin: Annotated[
        str | None,
        Field(pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$"),
    ] = None
    class_code: Annotated[str | None, Field(min_length=1, max_length=32)] = None
    ticker: Annotated[str | None, Field(min_length=1, max_length=32)] = None
    name: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("figi", "isin", "class_code", "ticker", mode="before")
    @classmethod
    def normalize_uppercase_aliases(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("broker_uid", mode="before")
    @classmethod
    def normalize_broker_uid(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_identity(self) -> InstrumentV1:
        if not any((self.broker_uid, self.figi, self.isin)):
            raise ValueError("instrument requires broker UID, FIGI or ISIN")
        if bool(self.ticker) != bool(self.class_code):
            raise ValueError("ticker and class_code must be present together")

        primary_values = {
            InstrumentPrimaryIdentityKind.BROKER_UID: self.broker_uid,
            InstrumentPrimaryIdentityKind.FIGI: self.figi,
            InstrumentPrimaryIdentityKind.ISIN: self.isin,
        }
        primary_value = primary_values[self.primary_identity_kind]
        if primary_value is None:
            raise ValueError("selected primary instrument identity is missing")
        expected = canonical_instrument_id(self.primary_identity_kind, primary_value)
        if self.instrument_id != expected:
            raise ValueError("instrument_id does not match canonical primary identity")
        return self

    def alias_keys(self) -> tuple[str, ...]:
        aliases: list[str] = []
        if self.broker_uid:
            aliases.append(f"broker_uid:{self.broker_uid}")
        if self.figi:
            aliases.append(f"figi:{self.figi}")
        if self.isin:
            aliases.append(f"isin:{self.isin}")
        if self.ticker and self.class_code:
            aliases.append(f"ticker_class:{self.ticker}:{self.class_code}")
        return tuple(aliases)


class PolicyRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    policy_id: PolicyId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    source_policy_id: Annotated[str, Field(min_length=3, max_length=96)]
    source_policy_sha256: Sha256
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def normalize_effective_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="effective_at")


class PortfolioSnapshotRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    snapshot_id: PortfolioSnapshotId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    broker_account_id: BrokerAccountId
    source_payload_sha256: Sha256
    broker_server_at: datetime | None = None
    local_received_at: datetime

    @field_validator("broker_server_at")
    @classmethod
    def normalize_broker_server_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _utc(value, field_name="broker_server_at")

    @field_validator("local_received_at")
    @classmethod
    def normalize_local_received_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="local_received_at")


class PositionRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    position_id: PositionId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    snapshot_id: PortfolioSnapshotId
    instrument_id: InstrumentId
    quantity: NonNegativeDecimal
    blocked_quantity: NonNegativeDecimal = Decimal("0")

    @model_validator(mode="after")
    def validate_position(self) -> PositionRecordV1:
        expected = canonical_position_id(self.snapshot_id, self.instrument_id)
        if self.position_id != expected:
            raise ValueError("position_id does not match snapshot/instrument identity")
        if self.blocked_quantity > self.quantity:
            raise ValueError("blocked_quantity cannot exceed quantity")
        return self


class EvidenceRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    evidence_id: EvidenceId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    instrument_id: InstrumentId | None = None
    source_kind: EvidenceSourceKind
    payload_sha256: Sha256
    published_at: datetime | None = None
    retrieved_at: datetime
    broker_server_at: datetime | None = None
    local_received_at: datetime

    @field_validator("published_at")
    @classmethod
    def normalize_published_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _utc(value, field_name="published_at")

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieved_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="retrieved_at")

    @field_validator("broker_server_at")
    @classmethod
    def normalize_broker_server_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _utc(value, field_name="broker_server_at")

    @field_validator("local_received_at")
    @classmethod
    def normalize_local_received_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="local_received_at")


class IncidentRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    incident_id: IncidentId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    status: IncidentStatus
    evidence_ids: tuple[EvidenceId, ...] = ()
    opened_at: datetime

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_evidence_ids(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)):
            raise ValueError("evidence_ids must be a collection")
        return tuple(sorted(set(value)))

    @field_validator("opened_at")
    @classmethod
    def normalize_opened_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="opened_at")


class DecisionRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    decision_id: DecisionId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    snapshot_id: PortfolioSnapshotId
    evidence_ids: tuple[EvidenceId, ...]
    payload_sha256: Sha256
    decided_at: datetime

    @field_validator("evidence_ids", mode="before")
    @classmethod
    def normalize_evidence_ids(cls, value: object) -> object:
        if isinstance(value, (str, bytes)):
            raise ValueError("evidence_ids must be a collection")
        result = tuple(sorted(set(value)))
        if not result:
            raise ValueError("decision requires evidence identity")
        return result

    @field_validator("decided_at")
    @classmethod
    def normalize_decided_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="decided_at")


class PlanRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    plan_id: PlanId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    snapshot_id: PortfolioSnapshotId
    decision_id: DecisionId
    payload_sha256: Sha256
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="created_at")


class ExecutionRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    execution_id: ExecutionId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    snapshot_id: PortfolioSnapshotId
    plan_id: PlanId
    payload_sha256: Sha256
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def normalize_recorded_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="recorded_at")


class JournalRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    identity_version: Literal[1] = 1
    journal_id: JournalId
    tenant_id: TenantId
    portfolio_id: PortfolioId
    policy_id: PolicyId
    decision_id: DecisionId | None = None
    plan_id: PlanId | None = None
    execution_id: ExecutionId | None = None
    incident_id: IncidentId | None = None
    payload_sha256: Sha256
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def normalize_recorded_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="recorded_at")

    @model_validator(mode="after")
    def require_subject(self) -> JournalRecordV1:
        if not any(
            (
                self.decision_id,
                self.plan_id,
                self.execution_id,
                self.incident_id,
            )
        ):
            raise ValueError("journal record requires an explicit subject identity")
        return self


class CanonicalDomainCatalogV1(ContractModel):
    """In-memory relationship validator for WP12 canonical identities.

    This model is deliberately not a persistence repository. WP13 owns durable
    storage and migrations. WP12 only proves explicit identity, scope, temporal
    and collision semantics before persistence exists.
    """

    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    tenants: tuple[TenantV1, ...]
    users: tuple[UserV1, ...]
    broker_accounts: tuple[BrokerAccountV1, ...] = ()
    portfolios: tuple[PortfolioV1, ...] = ()
    instruments: tuple[InstrumentV1, ...] = ()
    policies: tuple[PolicyRecordV1, ...] = ()
    snapshots: tuple[PortfolioSnapshotRecordV1, ...] = ()
    positions: tuple[PositionRecordV1, ...] = ()
    evidence: tuple[EvidenceRecordV1, ...] = ()
    incidents: tuple[IncidentRecordV1, ...] = ()
    decisions: tuple[DecisionRecordV1, ...] = ()
    plans: tuple[PlanRecordV1, ...] = ()
    executions: tuple[ExecutionRecordV1, ...] = ()
    journal: tuple[JournalRecordV1, ...] = ()

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _utc(value, field_name="generated_at")

    @model_validator(mode="after")
    def validate_catalog(self) -> CanonicalDomainCatalogV1:
        if len(self.tenants) != 1 or self.tenants[0].tenant_id != OWNER_TENANT_ID:
            raise ValueError("Personal V10 admits exactly one OWNER tenant")
        if len(self.users) != 1 or self.users[0].user_id != OWNER_USER_ID:
            raise ValueError("Personal V10 admits exactly one OWNER user")
        if self.users[0].tenant_id != OWNER_TENANT_ID:
            raise ValueError("OWNER user must belong to OWNER tenant")

        accounts = self._unique_index(
            self.broker_accounts, "broker_account_id", "broker account"
        )
        portfolios = self._unique_index(self.portfolios, "portfolio_id", "portfolio")
        instruments = self._unique_index(
            self.instruments, "instrument_id", "instrument"
        )
        policies = self._unique_index(self.policies, "policy_id", "policy")
        snapshots = self._unique_index(self.snapshots, "snapshot_id", "snapshot")
        positions = self._unique_index(self.positions, "position_id", "position")
        evidence = self._unique_index(self.evidence, "evidence_id", "evidence")
        incidents = self._unique_index(self.incidents, "incident_id", "incident")
        decisions = self._unique_index(self.decisions, "decision_id", "decision")
        plans = self._unique_index(self.plans, "plan_id", "plan")
        executions = self._unique_index(self.executions, "execution_id", "execution")
        self._unique_index(self.journal, "journal_id", "journal")

        for record in self.broker_accounts:
            self._require_owner_tenant(record.tenant_id, "broker account")

        for record in self.portfolios:
            self._require_owner_tenant(record.tenant_id, "portfolio")
            account = accounts.get(record.broker_account_id)
            if account is None:
                raise ValueError("portfolio references unknown broker account")
            if account.tenant_id != record.tenant_id:
                raise ValueError("portfolio broker account crosses tenant scope")

        for record in self.policies:
            self._require_owner_tenant(record.tenant_id, "policy")
            portfolio = portfolios.get(record.portfolio_id)
            if portfolio is None:
                raise ValueError("policy references unknown portfolio")
            if portfolio.tenant_id != record.tenant_id:
                raise ValueError("policy crosses tenant scope")

        for record in self.snapshots:
            portfolio = self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "snapshot",
            )
            account = accounts.get(record.broker_account_id)
            if account is None:
                raise ValueError("snapshot references unknown broker account")
            if account.tenant_id != record.tenant_id:
                raise ValueError("snapshot broker account crosses tenant scope")
            if portfolio.broker_account_id != record.broker_account_id:
                raise ValueError("snapshot broker account does not match portfolio")

        alias_owners: dict[str, str] = {}
        for instrument in self.instruments:
            for alias in instrument.alias_keys():
                owner = alias_owners.get(alias)
                if owner is not None and owner != instrument.instrument_id:
                    raise ValueError("instrument identity alias collision detected")
                alias_owners[alias] = instrument.instrument_id

        position_pairs: set[tuple[str, str]] = set()
        for record in self.positions:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "position",
            )
            snapshot = snapshots.get(record.snapshot_id)
            if snapshot is None:
                raise ValueError("position references unknown snapshot")
            if (
                snapshot.tenant_id != record.tenant_id
                or snapshot.portfolio_id != record.portfolio_id
                or snapshot.policy_id != record.policy_id
            ):
                raise ValueError("position crosses snapshot scope")
            if record.instrument_id not in instruments:
                raise ValueError("position references unknown instrument")
            pair = (record.snapshot_id, record.instrument_id)
            if pair in position_pairs:
                raise ValueError("duplicate instrument position within snapshot")
            position_pairs.add(pair)

        for record in self.evidence:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "evidence",
            )
            if record.instrument_id is not None and record.instrument_id not in instruments:
                raise ValueError("evidence references unknown instrument")

        for record in self.incidents:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "incident",
            )
            for evidence_id in record.evidence_ids:
                item = evidence.get(evidence_id)
                if item is None:
                    raise ValueError("incident references unknown evidence")
                self._require_matching_scope(record, item, "incident evidence")

        for record in self.decisions:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "decision",
            )
            snapshot = snapshots.get(record.snapshot_id)
            if snapshot is None:
                raise ValueError("decision references unknown snapshot")
            self._require_matching_scope(record, snapshot, "decision snapshot")
            for evidence_id in record.evidence_ids:
                item = evidence.get(evidence_id)
                if item is None:
                    raise ValueError("decision references unknown evidence")
                self._require_matching_scope(record, item, "decision evidence")

        for record in self.plans:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "plan",
            )
            decision = decisions.get(record.decision_id)
            snapshot = snapshots.get(record.snapshot_id)
            if decision is None:
                raise ValueError("plan references unknown decision")
            if snapshot is None:
                raise ValueError("plan references unknown snapshot")
            self._require_matching_scope(record, decision, "plan decision")
            self._require_matching_scope(record, snapshot, "plan snapshot")
            if decision.snapshot_id != record.snapshot_id:
                raise ValueError("plan snapshot must match decision snapshot")

        for record in self.executions:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "execution",
            )
            plan = plans.get(record.plan_id)
            if plan is None:
                raise ValueError("execution references unknown plan")
            self._require_matching_scope(record, plan, "execution plan")
            if plan.snapshot_id != record.snapshot_id:
                raise ValueError("execution snapshot must match plan snapshot")

        for record in self.journal:
            self._require_scope(
                record.tenant_id,
                record.portfolio_id,
                record.policy_id,
                portfolios,
                policies,
                "journal",
            )
            for reference, index, label in (
                (record.decision_id, decisions, "decision"),
                (record.plan_id, plans, "plan"),
                (record.execution_id, executions, "execution"),
                (record.incident_id, incidents, "incident"),
            ):
                if reference is None:
                    continue
                item = index.get(reference)
                if item is None:
                    raise ValueError(f"journal references unknown {label}")
                self._require_matching_scope(record, item, f"journal {label}")

        return self

    @staticmethod
    def _unique_index(
        records: tuple[ContractModel, ...],
        field_name: str,
        label: str,
    ) -> dict[str, ContractModel]:
        result: dict[str, ContractModel] = {}
        for record in records:
            value = getattr(record, field_name)
            if value in result:
                raise ValueError(f"duplicate {label} identity")
            result[value] = record
        return result

    @staticmethod
    def _require_owner_tenant(tenant_id: str, label: str) -> None:
        if tenant_id != OWNER_TENANT_ID:
            raise ValueError(f"{label} is outside OWNER tenant")

    @classmethod
    def _require_scope(
        cls,
        tenant_id: str,
        portfolio_id: str,
        policy_id: str,
        portfolios: dict[str, ContractModel],
        policies: dict[str, ContractModel],
        label: str,
    ) -> ContractModel:
        cls._require_owner_tenant(tenant_id, label)
        portfolio = portfolios.get(portfolio_id)
        if portfolio is None:
            raise ValueError(f"{label} references unknown portfolio")
        policy = policies.get(policy_id)
        if policy is None:
            raise ValueError(f"{label} references unknown policy")
        if getattr(portfolio, "tenant_id") != tenant_id:
            raise ValueError(f"{label} portfolio crosses tenant scope")
        if getattr(policy, "tenant_id") != tenant_id:
            raise ValueError(f"{label} policy crosses tenant scope")
        if getattr(policy, "portfolio_id") != portfolio_id:
            raise ValueError(f"{label} policy crosses portfolio scope")
        return portfolio

    @staticmethod
    def _require_matching_scope(
        left: ContractModel,
        right: ContractModel,
        label: str,
    ) -> None:
        for field_name in ("tenant_id", "portfolio_id", "policy_id"):
            if getattr(left, field_name) != getattr(right, field_name):
                raise ValueError(f"{label} crosses {field_name} scope")


def require_owner_scope(
    catalog: CanonicalDomainCatalogV1,
    *,
    actor_user_id: str,
    tenant_id: str,
    portfolio_id: str | None = None,
    policy_id: str | None = None,
) -> None:
    """Fail closed when a caller attempts to cross Personal V10 scope."""

    if actor_user_id != OWNER_USER_ID:
        raise PermissionError("only OWNER user is admitted in Personal V10")
    if not any(user.user_id == actor_user_id for user in catalog.users):
        raise PermissionError("OWNER user is not present in canonical domain catalog")
    if tenant_id != OWNER_TENANT_ID:
        raise PermissionError("cross-tenant access is denied")

    portfolio: PortfolioV1 | None = None
    if portfolio_id is not None:
        portfolio = next(
            (item for item in catalog.portfolios if item.portfolio_id == portfolio_id),
            None,
        )
        if portfolio is None or portfolio.tenant_id != tenant_id:
            raise PermissionError("portfolio is outside authorized tenant scope")

    if policy_id is not None:
        policy = next(
            (item for item in catalog.policies if item.policy_id == policy_id),
            None,
        )
        if policy is None or policy.tenant_id != tenant_id:
            raise PermissionError("policy is outside authorized tenant scope")
        if portfolio is not None and policy.portfolio_id != portfolio.portfolio_id:
            raise PermissionError("policy is outside authorized portfolio scope")
