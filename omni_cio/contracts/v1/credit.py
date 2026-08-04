from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.research_evidence import ResearchTargetV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class CreditEntityKind(StrEnum):
    ISSUER = "issuer"
    GUARANTOR = "guarantor"


class DebtSeniority(StrEnum):
    SENIOR_SECURED = "senior_secured"
    SENIOR_UNSECURED = "senior_unsecured"
    SUBORDINATED = "subordinated"
    STRUCTURED = "structured"
    UNKNOWN = "unknown"


class GuaranteeType(StrEnum):
    NONE = "none"
    LIMITED = "limited"
    FULL = "full"
    FULL_IRREVOCABLE_UNCONDITIONAL = "full_irrevocable_unconditional"
    UNKNOWN = "unknown"


class CreditRatingAgency(StrEnum):
    ACRA = "acra"
    EXPERT_RA = "expert_ra"
    NKR = "nkr"
    NRA = "nra"


class CreditRatingScale(StrEnum):
    ACRA_RU_NATIONAL = "acra_ru_national"
    EXPERT_RA_RU_NATIONAL = "expert_ra_ru_national"
    NKR_RU_NATIONAL = "nkr_ru_national"
    NRA_RU_NATIONAL = "nra_ru_national"


class CreditRatingSubject(StrEnum):
    ISSUE = "issue"
    ISSUER = "issuer"
    GUARANTOR = "guarantor"


class CreditRatingAction(StrEnum):
    ASSIGNED = "assigned"
    AFFIRMED = "affirmed"
    UPGRADED = "upgraded"
    DOWNGRADED = "downgraded"
    WITHDRAWN = "withdrawn"


class CreditDefaultEventType(StrEnum):
    DEFAULT = "default"
    TECHNICAL_DEFAULT = "technical_default"
    RESTRUCTURING = "restructuring"
    PAYMENT_DELAY = "payment_delay"


class CreditFloorBasis(StrEnum):
    ISSUE = "issue"
    ISSUER_PROXY = "issuer_proxy"
    ELIGIBLE_GUARANTOR = "eligible_guarantor"
    NONE = "none"


class CreditBlockerCode(StrEnum):
    DOSSIER_NOT_READY = "dossier_not_ready"
    DOSSIER_BINDING_MISMATCH = "dossier_binding_mismatch"
    SOURCE_PROVENANCE_MISSING = "source_provenance_missing"
    SOURCE_NOT_DECISION_GRADE = "source_not_decision_grade"
    ISSUER_IDENTITY_MISSING = "issuer_identity_missing"
    GUARANTOR_IDENTITY_MISSING = "guarantor_identity_missing"
    RATING_IDENTITY_CONFLICT = "rating_identity_conflict"
    RATING_CONTRADICTION = "rating_contradiction"
    POLICY_CREDIT_FLOOR_MISSING = "policy_credit_floor_missing"
    POLICY_SCALE_UNSUPPORTED = "policy_scale_unsupported"
    RATING_SCALE_INCOMPATIBLE = "rating_scale_incompatible"
    CURRENT_RATING_MISSING = "current_rating_missing"
    RATING_SYMBOL_UNRECOGNIZED = "rating_symbol_unrecognized"
    RATING_BELOW_FLOOR = "rating_below_floor"
    ACTIVE_DEFAULT_EVENT = "active_default_event"
    SENIORITY_UNKNOWN = "seniority_unknown"


class CreditReanalysisTriggerCode(StrEnum):
    DOSSIER_CHANGED = "dossier_changed"
    POLICY_CHANGED = "policy_changed"
    RATING_CHANGED = "rating_changed"
    OUTLOOK_CHANGED = "outlook_changed"
    WATCH_CHANGED = "watch_changed"
    DEFAULT_EVENT_CHANGED = "default_event_changed"
    ISSUE_TERMS_CHANGED = "issue_terms_changed"


class CreditEntityIdentityV1(ContractModel):
    entity_id: Annotated[str, Field(pattern=r"^credit_[a-z0-9][a-z0-9:_-]{2,95}$")]
    kind: CreditEntityKind
    name: Annotated[str, Field(min_length=1, max_length=256)]
    registration_id: Annotated[str | None, Field(max_length=128)] = None
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("entity source hashes must be a collection")
        return tuple(sorted(set(value)))


class CreditGuaranteeV1(ContractModel):
    guarantor_entity_id: Annotated[str, Field(min_length=4, max_length=96)]
    guarantee_type: GuaranteeType
    credit_substitution_eligible: bool = False
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("guarantee source hashes must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_substitution(self) -> CreditGuaranteeV1:
        if self.credit_substitution_eligible and self.guarantee_type is not GuaranteeType.FULL_IRREVOCABLE_UNCONDITIONAL:
            raise ValueError(
                "credit substitution requires full irrevocable unconditional guarantee"
            )
        return self


class DebtIssueTermsV1(ContractModel):
    instrument_uid: Annotated[str, Field(min_length=1, max_length=128)]
    issuer_entity_id: Annotated[str, Field(min_length=4, max_length=96)]
    seniority: DebtSeniority
    maturity_date: date | None = None
    offer_date: date | None = None
    amortizing: bool | None = None
    secured: bool | None = None
    guarantees: tuple[CreditGuaranteeV1, ...] = ()
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("issue term source hashes must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_dates(self) -> DebtIssueTermsV1:
        if self.offer_date is not None and self.maturity_date is not None:
            if self.offer_date > self.maturity_date:
                raise ValueError("offer date cannot follow maturity date")
        guarantor_ids = [row.guarantor_entity_id for row in self.guarantees]
        if len(guarantor_ids) != len(set(guarantor_ids)):
            raise ValueError("issue guarantees must have unique guarantor ids")
        return self


class CreditRatingObservationV1(ContractModel):
    observation_id: Annotated[str, Field(pattern=r"^rating_[a-z0-9][a-z0-9_-]{2,95}$")]
    subject: CreditRatingSubject
    subject_id: Annotated[str, Field(min_length=1, max_length=128)]
    agency: CreditRatingAgency
    scale: CreditRatingScale
    rating: Annotated[str, Field(min_length=1, max_length=32)]
    outlook: Annotated[str | None, Field(max_length=64)] = None
    watch: Annotated[str | None, Field(max_length=64)] = None
    action: CreditRatingAction
    effective_at: datetime
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("effective_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rating effective_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("rating", mode="before")
    @classmethod
    def normalize_rating(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("rating source hashes must be a collection")
        return tuple(sorted(set(value)))


class CreditDefaultEventV1(ContractModel):
    event_id: Annotated[str, Field(pattern=r"^credit_event_[a-z0-9][a-z0-9_-]{2,95}$")]
    event_type: CreditDefaultEventType
    subject_id: Annotated[str, Field(min_length=1, max_length=128)]
    occurred_at: datetime
    resolved_at: datetime | None = None
    source_record_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]

    @field_validator("occurred_at", "resolved_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("credit event timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("source_record_sha256s", mode="before")
    @classmethod
    def normalize_sources(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("credit event source hashes must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_resolution(self) -> CreditDefaultEventV1:
        if self.resolved_at is not None and self.resolved_at < self.occurred_at:
            raise ValueError("credit event resolution cannot predate occurrence")
        return self

    @property
    def active(self) -> bool:
        return self.resolved_at is None


class CreditEvidenceInputV1(ContractModel):
    dossier_sha256: Sha256
    target: ResearchTargetV1
    issuer: CreditEntityIdentityV1
    guarantors: tuple[CreditEntityIdentityV1, ...] = ()
    issue_terms: DebtIssueTermsV1
    ratings: tuple[CreditRatingObservationV1, ...] = ()
    default_events: tuple[CreditDefaultEventV1, ...] = ()

    @model_validator(mode="after")
    def validate_identity_graph(self) -> CreditEvidenceInputV1:
        if self.issuer.kind is not CreditEntityKind.ISSUER:
            raise ValueError("issuer identity must have ISSUER kind")
        if self.issue_terms.instrument_uid != self.target.instrument_uid:
            raise ValueError("issue terms must bind research target instrument UID")
        if self.issue_terms.issuer_entity_id != self.issuer.entity_id:
            raise ValueError("issue issuer id must match issuer identity")
        guarantor_ids = {row.entity_id for row in self.guarantors}
        if any(row.kind is not CreditEntityKind.GUARANTOR for row in self.guarantors):
            raise ValueError("guarantor identities must have GUARANTOR kind")
        if len(guarantor_ids) != len(self.guarantors):
            raise ValueError("guarantor identities must be unique")
        if any(row.guarantor_entity_id not in guarantor_ids for row in self.issue_terms.guarantees):
            raise ValueError("issue guarantee references missing guarantor identity")
        return self


class CreditFloorAssessmentV1(ContractModel):
    policy_scale: CreditRatingScale | None
    policy_floor: Annotated[str | None, Field(max_length=32)]
    basis: CreditFloorBasis
    selected_observation_id: Annotated[str | None, Field(max_length=96)] = None
    selected_rating: Annotated[str | None, Field(max_length=32)] = None
    selected_subject_id: Annotated[str | None, Field(max_length=128)] = None
    meets_floor: bool
    blockers: tuple[CreditBlockerCode, ...] = ()

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("credit blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_assessment(self) -> CreditFloorAssessmentV1:
        selected = self.selected_observation_id is not None
        if selected != (self.selected_rating is not None and self.selected_subject_id is not None):
            raise ValueError("selected credit observation fields must be supplied together")
        if self.meets_floor and self.blockers:
            raise ValueError("credit floor cannot pass with blockers")
        if self.meets_floor and not selected:
            raise ValueError("credit floor pass requires selected observation")
        return self


class CreditReanalysisTriggerV1(ContractModel):
    required: bool
    codes: tuple[CreditReanalysisTriggerCode, ...] = ()

    @field_validator("codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("reanalysis codes must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_required(self) -> CreditReanalysisTriggerV1:
        if self.required != bool(self.codes):
            raise ValueError("reanalysis required must match trigger codes")
        return self


class CreditPassportV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    assessed_at: datetime
    dossier_sha256: Sha256
    target: ResearchTargetV1
    policy_reference: PolicyReferenceV1
    issuer: CreditEntityIdentityV1
    guarantors: tuple[CreditEntityIdentityV1, ...] = ()
    issue_terms: DebtIssueTermsV1
    ratings: tuple[CreditRatingObservationV1, ...] = ()
    default_events: tuple[CreditDefaultEventV1, ...] = ()
    floor_assessment: CreditFloorAssessmentV1
    reanalysis: CreditReanalysisTriggerV1
    blockers: tuple[CreditBlockerCode, ...] = ()
    passport_sha256: Sha256
    decision_ready: bool
    strong_recommendation_allowed: bool
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("credit passport assessed_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("blockers", mode="before")
    @classmethod
    def normalize_blockers(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("passport blockers must be a collection")
        return tuple(sorted(set(value), key=str))

    @model_validator(mode="after")
    def validate_passport(self) -> CreditPassportV1:
        if self.decision_ready != (not self.blockers):
            raise ValueError("credit decision readiness must match blockers")
        active_adverse = any(row.active for row in self.default_events)
        expected_strong = self.decision_ready and self.floor_assessment.meets_floor and not active_adverse
        if self.strong_recommendation_allowed != expected_strong:
            raise ValueError("strong recommendation state does not reconcile")
        if self.passport_sha256 != credit_passport_sha256(self):
            raise ValueError("passport_sha256 does not match canonical credit payload")
        return self


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def credit_passport_sha256(passport: CreditPassportV1) -> str:
    payload = passport.model_dump(mode="json", exclude={"passport_sha256"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
