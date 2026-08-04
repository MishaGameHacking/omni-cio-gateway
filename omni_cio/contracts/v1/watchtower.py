from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.credit import CreditPassportV1
from omni_cio.contracts.v1.investment_policy import PolicyReferenceV1
from omni_cio.contracts.v1.market import MarketResearchBundleV1
from omni_cio.contracts.v1.observability import ObservabilitySeverity
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskAssessmentV1


Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class WatchtowerSignalKind(StrEnum):
    RATING_DOWNGRADE = "rating_downgrade"
    RATING_WATCH = "rating_watch"
    DEFAULT_EVENT = "default_event"
    CORPORATE_EVENT = "corporate_event"
    LIQUIDITY_DETERIORATION = "liquidity_deterioration"
    CONCENTRATION_BREACH = "concentration_breach"
    POLICY_DRIFT = "policy_drift"
    DATA_QUALITY = "data_quality"


class WatchtowerActionKind(StrEnum):
    NONE = "none"
    REVIEW = "review"
    RECOMMENDATION = "recommendation"
    PROPOSE_PLAN = "propose_plan"


class WatchtowerAlertV1(ContractModel):
    alert_id: Sha256
    fingerprint_sha256: Sha256
    kind: WatchtowerSignalKind
    severity: ObservabilitySeverity
    subject_key: Annotated[str, Field(min_length=1, max_length=256)]
    effective_at: datetime
    evidence_sha256s: Annotated[tuple[Sha256, ...], Field(min_length=1)]
    message_code: Annotated[str, Field(pattern=r"^WATCHTOWER_[A-Z0-9_]{3,63}$")]
    requires_owner_attention: bool
    action: WatchtowerActionKind
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("effective_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("watchtower alert timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("evidence_sha256s", mode="before")
    @classmethod
    def normalize_evidence(cls, value: object) -> object:
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("watchtower evidence hashes must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_alert(self) -> WatchtowerAlertV1:
        if self.alert_id != watchtower_alert_id(self):
            raise ValueError("alert_id does not match canonical watchtower alert")
        if self.severity is ObservabilitySeverity.INFO and self.requires_owner_attention:
            raise ValueError("INFO watchtower alert cannot require owner attention")
        if self.action is WatchtowerActionKind.PROPOSE_PLAN and not self.requires_owner_attention:
            raise ValueError("proposed-plan action requires owner attention")
        return self


class WatchtowerInputV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    checked_at: datetime
    delivery_id: Annotated[str, Field(min_length=8, max_length=160)]
    portfolio_snapshot_sha256: Sha256
    policy_reference: PolicyReferenceV1
    risk: PortfolioRiskAssessmentV1
    credit_passports: tuple[CreditPassportV1, ...] = ()
    market_bundles: tuple[MarketResearchBundleV1, ...] = ()
    source_quality_codes: tuple[
        Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")], ...
    ] = ()
    input_sha256: Sha256
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("checked_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("watchtower checked_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("credit_passports", mode="before")
    @classmethod
    def normalize_passports(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("credit passports must be a collection")
        return tuple(sorted(value, key=lambda row: str(getattr(row, "passport_sha256", row))))

    @field_validator("market_bundles", mode="before")
    @classmethod
    def normalize_bundles(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("market bundles must be a collection")
        return tuple(sorted(value, key=lambda row: str(getattr(row, "instrument_key", row))))

    @field_validator("source_quality_codes", mode="before")
    @classmethod
    def normalize_quality_codes(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("source quality codes must be a collection")
        return tuple(sorted({str(item).strip().upper() for item in value}))

    @model_validator(mode="after")
    def validate_input(self) -> WatchtowerInputV1:
        if self.risk.portfolio_snapshot_sha256 != self.portfolio_snapshot_sha256:
            raise ValueError("watchtower risk assessment must bind exact portfolio snapshot")
        if self.risk.policy_reference != self.policy_reference:
            raise ValueError("watchtower risk assessment must bind exact owner policy")
        if any(row.policy_reference != self.policy_reference for row in self.credit_passports):
            raise ValueError("watchtower credit passports must bind exact owner policy")
        passport_ids = [row.passport_sha256 for row in self.credit_passports]
        if len(passport_ids) != len(set(passport_ids)):
            raise ValueError("watchtower credit passports must be unique")
        bundle_keys = [row.instrument_key for row in self.market_bundles]
        if len(bundle_keys) != len(set(bundle_keys)):
            raise ValueError("watchtower market bundles must have unique instrument keys")
        if self.input_sha256 != watchtower_input_sha256(self):
            raise ValueError("input_sha256 does not match canonical watchtower input")
        return self


class WatchtowerStateV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    watch_id: Annotated[str, Field(pattern=r"^watch_[a-f0-9]{16,64}$")]
    revision: Annotated[int, Field(ge=0)] = 0
    initialized_at: datetime
    updated_at: datetime
    policy_reference: PolicyReferenceV1
    last_portfolio_snapshot_sha256: Sha256
    last_risk_assessment_sha256: Sha256
    last_input_sha256: Sha256
    seen_delivery_ids: tuple[Annotated[str, Field(min_length=8, max_length=160)], ...] = ()
    seen_fingerprints: tuple[Sha256, ...] = ()
    state_sha256: Sha256
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("initialized_at", "updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("watchtower state timestamps must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("seen_delivery_ids", mode="before")
    @classmethod
    def normalize_delivery_ids(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("seen delivery IDs must be a collection")
        return tuple(sorted(set(value)))

    @field_validator("seen_fingerprints", mode="before")
    @classmethod
    def normalize_fingerprints(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("seen fingerprints must be a collection")
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def validate_state(self) -> WatchtowerStateV1:
        if self.updated_at < self.initialized_at:
            raise ValueError("watchtower updated_at cannot precede initialized_at")
        if self.state_sha256 != watchtower_state_sha256(self):
            raise ValueError("state_sha256 does not match canonical watchtower state")
        return self


class WatchtowerEvaluationV1(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    evaluated_at: datetime
    watch_id: Annotated[str, Field(pattern=r"^watch_[a-f0-9]{16,64}$")]
    input_sha256: Sha256
    replay: bool
    alerts: tuple[WatchtowerAlertV1, ...] = ()
    material_change: bool
    should_notify: bool
    proposed_action: WatchtowerActionKind
    state: WatchtowerStateV1
    evaluation_sha256: Sha256
    execution_authorized: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("evaluated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("watchtower evaluation timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("alerts", mode="before")
    @classmethod
    def normalize_alerts(cls, value: object) -> object:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
            raise ValueError("watchtower alerts must be a collection")
        return tuple(sorted(value, key=lambda row: str(getattr(row, "alert_id", row))))

    @model_validator(mode="after")
    def validate_evaluation(self) -> WatchtowerEvaluationV1:
        expected_material = bool(self.alerts)
        if self.material_change != expected_material or self.should_notify != expected_material:
            raise ValueError("material/notification flags must match emitted alerts")
        if self.replay and self.alerts:
            raise ValueError("replayed delivery cannot emit duplicate alerts")
        if not self.alerts and self.proposed_action is not WatchtowerActionKind.NONE:
            raise ValueError("no-alert evaluation cannot propose an action")
        if self.evaluation_sha256 != watchtower_evaluation_sha256(self):
            raise ValueError("evaluation_sha256 does not match canonical watchtower evaluation")
        return self


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def watchtower_alert_id(alert: WatchtowerAlertV1) -> str:
    payload = alert.model_dump(mode="json", exclude={"alert_id"})
    return _sha(payload)


def watchtower_input_sha256(value: WatchtowerInputV1) -> str:
    payload = value.model_dump(mode="json", exclude={"input_sha256"})
    return _sha(payload)


def watchtower_state_sha256(value: WatchtowerStateV1) -> str:
    payload = value.model_dump(mode="json", exclude={"state_sha256"})
    return _sha(payload)


def watchtower_evaluation_sha256(value: WatchtowerEvaluationV1) -> str:
    payload = value.model_dump(mode="json", exclude={"evaluation_sha256"})
    alerts = payload.get("alerts", [])
    if isinstance(alerts, list):
        payload["alerts"] = sorted(
            alerts,
            key=lambda row: (
                str(row.get("alert_id", "")) if isinstance(row, dict) else str(row)
            ),
        )
    return _sha(payload)
