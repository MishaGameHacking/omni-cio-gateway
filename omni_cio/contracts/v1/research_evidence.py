from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.portfolio import InstrumentType


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class EvidenceSourceClass(StrEnum):
    BROKER = "broker"
    EXCHANGE = "exchange"
    ISSUER = "issuer"
    OFFICIAL_DISCLOSURE = "official_disclosure"
    REGULATOR = "regulator"
    RATING_AGENCY = "rating_agency"
    MEDIA_CONTEXT = "media_context"


class EvidenceUse(StrEnum):
    DECISION_GRADE = "decision_grade"
    CONTEXT_ONLY = "context_only"
    REJECTED = "rejected"


class EvidenceFactType(StrEnum):
    IDENTITY = "identity"
    FUNDAMENTAL = "fundamental"
    REPORT = "report"
    DIVIDEND = "dividend"
    COUPON = "coupon"
    CORPORATE_EVENT = "corporate_event"
    SANCTION = "sanction"
    LITIGATION = "litigation"
    AUDITOR_WARNING = "auditor_warning"
    MATERIAL_EVENT = "material_event"


class EvidenceValueType(StrEnum):
    TEXT = "text"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    MONEY = "money"


class RequirementImportance(StrEnum):
    CRITICAL = "critical"
    MATERIAL = "material"
    CONTEXT = "context"


class ContradictionSeverity(StrEnum):
    CRITICAL = "critical"
    MATERIAL = "material"
    MINOR = "minor"


class CoverageGapReason(StrEnum):
    SOURCE_UNAVAILABLE = "source_unavailable"
    NO_DECISION_GRADE_RECORD = "no_decision_grade_record"
    STALE_RECORD = "stale_record"
    INSUFFICIENT_RECORDS = "insufficient_records"
    PROBE_MISSING = "probe_missing"
    PROBE_STALE = "probe_stale"


class ResearchSourceV1(ContractModel):
    provider: Annotated[str, Field(min_length=1, max_length=128)]
    source_class: EvidenceSourceClass
    authority: SourceAuthority
    source_id: Annotated[str, Field(min_length=1, max_length=256)]
    source_location: Annotated[str | None, Field(max_length=1024)] = None
    retrieved_at: datetime

    @field_validator("retrieved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("source retrieved_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class ResearchTargetV1(ContractModel):
    funnel_sha256: Sha256
    candidate_id: Annotated[str, Field(min_length=5, max_length=256)]
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    instrument_type: InstrumentType
    asset_uid: Annotated[str | None, Field(max_length=128)] = None
    asset_uid_source: ResearchSourceV1 | None = None

    @model_validator(mode="after")
    def validate_candidate_identity(self) -> ResearchTargetV1:
        if self.candidate_id != f"uid:{self.instrument_uid}":
            raise ValueError("research target candidate_id must bind exact instrument UID")
        if (self.asset_uid is None) != (self.asset_uid_source is None):
            raise ValueError("asset UID and asset UID provenance must be supplied together")
        if self.asset_uid_source is not None:
            if self.asset_uid_source.source_class is not EvidenceSourceClass.BROKER:
                raise ValueError("T-Invest asset UID provenance must be broker source")
            if self.asset_uid_source.authority not in {
                SourceAuthority.PRIMARY,
                SourceAuthority.OFFICIAL,
                SourceAuthority.REGULATED,
            }:
                raise ValueError("asset UID provenance must be trusted")
        return self


class EvidenceValueV1(ContractModel):
    value_type: EvidenceValueType
    canonical_value: Annotated[str, Field(min_length=1, max_length=4096)]
    currency: Annotated[str | None, Field(pattern=r"^[A-Z]{3}$")] = None

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_currency(self) -> EvidenceValueV1:
        if self.value_type is EvidenceValueType.MONEY and self.currency is None:
            raise ValueError("money evidence requires currency")
        if self.value_type is not EvidenceValueType.MONEY and self.currency is not None:
            raise ValueError("only money evidence may carry currency")
        return self


class EvidenceRecordV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    record_sha256: Sha256
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    fact_type: EvidenceFactType
    fact_key: Annotated[
        str,
        Field(pattern=r"^[a-z][a-z0-9_.:@/-]{2,191}$"),
    ]
    value: EvidenceValueV1
    source: ResearchSourceV1
    use: EvidenceUse
    source_record_id: Annotated[str | None, Field(max_length=256)] = None
    published_at: datetime | None = None
    effective_at: datetime | None = None
    material: bool = True

    @field_validator("published_at", "effective_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_record(self) -> EvidenceRecordV1:
        trusted = {
            SourceAuthority.PRIMARY,
            SourceAuthority.OFFICIAL,
            SourceAuthority.REGULATED,
        }
        if self.use is EvidenceUse.DECISION_GRADE:
            if self.source.authority not in trusted:
                raise ValueError("decision-grade evidence requires trusted authority")
            if self.source.source_class is EvidenceSourceClass.MEDIA_CONTEXT:
                raise ValueError("media context cannot be decision-grade by itself")
        if (
            self.source.source_class is EvidenceSourceClass.MEDIA_CONTEXT
            and self.use is not EvidenceUse.CONTEXT_ONLY
        ):
            raise ValueError("media evidence must remain context-only")
        if self.record_sha256 != evidence_record_sha256(self):
            raise ValueError("record_sha256 does not match canonical evidence payload")
        return self


class EvidenceCoverageProbeV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    fact_type: EvidenceFactType
    source_class: EvidenceSourceClass
    checked_at: datetime
    success: bool
    record_count: Annotated[int, Field(ge=0)] = 0
    source_error: Annotated[str | None, Field(max_length=256)] = None

    @field_validator("checked_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("probe checked_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_probe(self) -> EvidenceCoverageProbeV1:
        if self.success and self.source_error is not None:
            raise ValueError("successful probe cannot carry source_error")
        if not self.success and self.record_count != 0:
            raise ValueError("failed probe cannot report records")
        return self


class EvidenceRequirementV1(ContractModel):
    requirement_id: Annotated[
        str,
        Field(pattern=r"^req_[a-z0-9][a-z0-9_-]{2,63}$"),
    ]
    fact_type: EvidenceFactType
    fact_key_prefix: Annotated[str | None, Field(max_length=128)] = None
    source_classes: Annotated[tuple[EvidenceSourceClass, ...], Field(min_length=1)]
    minimum_decision_grade_records: Annotated[int, Field(ge=0, le=10)] = 1
    max_age_seconds: Annotated[int, Field(ge=60, le=31_536_000)]
    importance: RequirementImportance = RequirementImportance.MATERIAL
    allow_empty_after_successful_probe: bool = False

    @field_validator("source_classes", mode="before")
    @classmethod
    def normalize_source_classes(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("source_classes must be a collection")
        return tuple(sorted(set(value), key=str))

    @field_validator("fact_key_prefix", mode="before")
    @classmethod
    def normalize_fact_key_prefix(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("fact_key_prefix must be text")
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("fact_key_prefix cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_requirement(self) -> EvidenceRequirementV1:
        if self.allow_empty_after_successful_probe and self.minimum_decision_grade_records != 0:
            raise ValueError("allow-empty requirement must set minimum records to zero")
        return self


class EvidenceCoverageGapV1(ContractModel):
    requirement_id: Annotated[str, Field(min_length=1, max_length=64)]
    fact_type: EvidenceFactType
    importance: RequirementImportance
    reason: CoverageGapReason


class EvidenceContradictionV1(ContractModel):
    fact_key: Annotated[str, Field(min_length=3, max_length=192)]
    comparison_period: Annotated[str | None, Field(max_length=64)] = None
    severity: ContradictionSeverity
    record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=2)]
    distinct_values: Annotated[tuple[str, ...], Field(min_length=2)]
    unresolved: bool = True

    @field_validator("record_sha256s", "distinct_values", mode="before")
    @classmethod
    def normalize_values(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("contradiction values must be a collection")
        return tuple(sorted(set(value)))


class ResearchSourceLoadV1(ContractModel):
    target: ResearchTargetV1
    loaded_at: datetime
    source_fetched_at: datetime
    expires_at: datetime
    next_refresh_at: datetime
    cache_hit: bool
    source_calls: Annotated[int, Field(ge=0, le=32)]
    cacheable: bool
    records: tuple[EvidenceRecordV1, ...] = ()
    probes: tuple[EvidenceCoverageProbeV1, ...] = ()
    raw_content_stored: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator(
        "loaded_at",
        "source_fetched_at",
        "expires_at",
        "next_refresh_at",
    )
    @classmethod
    def normalize_load_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("research load timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_load(self) -> ResearchSourceLoadV1:
        if self.expires_at < self.source_fetched_at:
            raise ValueError("research cache expiry cannot predate source fetch")
        if self.next_refresh_at < self.source_fetched_at:
            raise ValueError("research next refresh cannot predate source fetch")
        if self.cache_hit and self.source_calls != 0:
            raise ValueError("cache hit cannot perform source calls")
        if self.cache_hit and not self.cacheable:
            raise ValueError("cache hit must come from cacheable evidence")
        if any(row.instrument_uid != self.target.instrument_uid for row in self.records):
            raise ValueError("research load record UID mismatch")
        if any(probe.instrument_uid != self.target.instrument_uid for probe in self.probes):
            raise ValueError("research load probe UID mismatch")
        return self


class ResearchDossierV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    target: ResearchTargetV1
    assessed_at: datetime
    requirements: tuple[EvidenceRequirementV1, ...] = ()
    probes: tuple[EvidenceCoverageProbeV1, ...] = ()
    records: tuple[EvidenceRecordV1, ...] = ()
    contradictions: tuple[EvidenceContradictionV1, ...] = ()
    coverage_gaps: tuple[EvidenceCoverageGapV1, ...] = ()
    duplicate_records_removed: Annotated[int, Field(ge=0)] = 0
    dossier_sha256: Sha256
    decision_ready: bool
    strong_recommendation_allowed: bool
    raw_content_stored: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dossier assessed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_dossier(self) -> ResearchDossierV1:
        if any(row.instrument_uid != self.target.instrument_uid for row in self.records):
            raise ValueError("dossier evidence instrument UID mismatch")
        if any(probe.instrument_uid != self.target.instrument_uid for probe in self.probes):
            raise ValueError("dossier probe instrument UID mismatch")
        required_ids = {item.requirement_id for item in self.requirements}
        if len(required_ids) != len(self.requirements):
            raise ValueError("research requirements must have unique ids")
        if any(gap.requirement_id not in required_ids for gap in self.coverage_gaps):
            raise ValueError("coverage gap references unknown requirement")
        expected_ready = not any(
            gap.importance in {RequirementImportance.CRITICAL, RequirementImportance.MATERIAL}
            for gap in self.coverage_gaps
        )
        if self.decision_ready != expected_ready:
            raise ValueError("decision_ready does not reconcile to material coverage gaps")
        critical_conflict = any(
            row.severity is ContradictionSeverity.CRITICAL and row.unresolved
            for row in self.contradictions
        )
        expected_strong = self.decision_ready and not critical_conflict
        if self.strong_recommendation_allowed != expected_strong:
            raise ValueError(
                "strong_recommendation_allowed does not reconcile to dossier state"
            )
        if self.dossier_sha256 != research_dossier_sha256(self):
            raise ValueError("dossier_sha256 does not match canonical dossier payload")
        return self


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def evidence_record_sha256(record: EvidenceRecordV1) -> str:
    payload = record.model_dump(mode="json", exclude={"record_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def make_evidence_record(**values: object) -> EvidenceRecordV1:
    provisional = dict(values)
    provisional.setdefault("schema_version", "1.0")
    provisional.setdefault("material", True)
    provisional["record_sha256"] = "0" * 64
    candidate = EvidenceRecordV1.model_construct(**provisional)
    provisional["record_sha256"] = evidence_record_sha256(candidate)
    return EvidenceRecordV1.model_validate(provisional)


def research_dossier_sha256(dossier: ResearchDossierV1) -> str:
    payload = dossier.model_dump(mode="json", exclude={"dossier_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
