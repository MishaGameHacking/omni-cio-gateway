from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel


PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
KeyId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,127}$")]
ArchiveFilename = Annotated[
    str,
    Field(pattern=r"^[0-9]{8}-[0-9a-f]{64}\.plae$"),
]
BackupReference = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{2,255}$"),
]


class PaperLedgerRecoveryFileV1(ContractModel):
    sequence: PositiveInt
    filename: ArchiveFilename
    record_digest: HexDigest
    envelope_digest: HexDigest
    size_bytes: Annotated[int, Field(gt=0, le=12 * 1024 * 1024)]

    @model_validator(mode="after")
    def validate_filename_binding(self) -> PaperLedgerRecoveryFileV1:
        expected = f"{self.sequence:08d}-{self.record_digest}.plae"
        if self.filename != expected:
            raise ValueError("paper recovery filename does not match sequence and digest")
        return self


RecoveryFiles = Annotated[
    tuple[PaperLedgerRecoveryFileV1, ...],
    Field(min_length=1, max_length=4096),
]
ArchiveFilenames = Annotated[
    tuple[ArchiveFilename, ...],
    Field(max_length=4096),
]


class PaperLedgerRecoveryManifestV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    manifest_format: Literal["paper-ledger-recovery-manifest-v1"] = (
        "paper-ledger-recovery-manifest-v1"
    )
    authentication_algorithm: Literal["hmac-sha256"] = "hmac-sha256"
    created_at: datetime
    manifest_key_id: KeyId
    backup_reference: BackupReference
    files: RecoveryFiles
    archive_file_count: PositiveInt
    latest_sequence: PositiveInt
    latest_record_digest: HexDigest
    latest_event_count: PositiveInt
    files_digest: HexDigest
    manifest_digest: HexDigest
    authentication_tag: HexDigest
    primary_archive_verified: Literal[True] = True
    backup_archive_verified: Literal[True] = True
    checkpoint_verified: Literal[True] = True
    full_chain_required_for_online_recovery: Literal[True] = True
    retention_execution_allowed: Literal[False] = False
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper recovery timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_manifest_summary(self) -> PaperLedgerRecoveryManifestV1:
        if self.archive_file_count != len(self.files):
            raise ValueError("paper recovery file count does not match evidence")
        for expected, file in enumerate(self.files, start=1):
            if file.sequence != expected:
                raise ValueError("paper recovery files must form a contiguous chain")
        latest = self.files[-1]
        if self.latest_sequence != latest.sequence:
            raise ValueError("paper recovery latest sequence does not match evidence")
        if self.latest_record_digest != latest.record_digest:
            raise ValueError("paper recovery latest digest does not match evidence")
        return self


class PaperLedgerRetentionPlanV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    plan_format: Literal["paper-ledger-retention-plan-v1"] = (
        "paper-ledger-retention-plan-v1"
    )
    planned_at: datetime
    recovery_manifest_digest: HexDigest
    latest_sequence: PositiveInt
    keep_last_records: PositiveInt
    retained_files: ArchiveFilenames
    candidate_files: ArchiveFilenames
    retained_count: PositiveInt
    candidate_count: NonNegativeInt
    backup_restore_required: bool
    online_chain_preserved_after_candidates: bool
    deletion_execution_allowed: Literal[False] = False
    deletion_executed: Literal[False] = False
    explicit_operator_approval_required: Literal[True] = True
    paper_only: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("planned_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper retention timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_counts(self) -> PaperLedgerRetentionPlanV1:
        if self.retained_count != len(self.retained_files):
            raise ValueError("paper retention retained count does not match files")
        if self.candidate_count != len(self.candidate_files):
            raise ValueError("paper retention candidate count does not match files")
        if self.retained_count != self.keep_last_records:
            raise ValueError("paper retention must retain the requested record count")
        if set(self.retained_files).intersection(self.candidate_files):
            raise ValueError("paper retention file sets must not overlap")
        expected_backup = self.candidate_count > 0
        if self.backup_restore_required is not expected_backup:
            raise ValueError("paper retention backup requirement is inconsistent")
        if self.online_chain_preserved_after_candidates is not (not expected_backup):
            raise ValueError("paper retention online-chain status is inconsistent")
        return self


class PaperLedgerLockDiagnosticV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    diagnostic_format: Literal["paper-ledger-lock-diagnostic-v1"] = (
        "paper-ledger-lock-diagnostic-v1"
    )
    observed_at: datetime
    status: Literal["absent", "active", "stale_candidate", "invalid"]
    age_seconds: NonNegativeInt | None = None
    stale_after_seconds: PositiveInt
    content_valid: bool
    permissions_safe: bool
    regular_file: bool
    symlink_detected: bool
    automatic_break_allowed: Literal[False] = False
    manual_verification_required: Literal[True] = True
    paper_only: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper lock diagnostic timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_status_evidence(self) -> PaperLedgerLockDiagnosticV1:
        if self.status == "absent":
            if self.age_seconds is not None:
                raise ValueError("absent lock cannot have an age")
            if self.symlink_detected:
                raise ValueError("absent lock cannot be a symlink")
            return self
        if self.age_seconds is None:
            raise ValueError("present lock requires an age")
        if self.status in {"active", "stale_candidate"}:
            if not self.content_valid or not self.permissions_safe or not self.regular_file:
                raise ValueError("valid lock status requires valid lock evidence")
            if self.symlink_detected:
                raise ValueError("valid lock status cannot be a symlink")
        if self.status == "active" and self.age_seconds >= self.stale_after_seconds:
            raise ValueError("active lock exceeds stale threshold")
        if self.status == "stale_candidate" and self.age_seconds < self.stale_after_seconds:
            raise ValueError("stale candidate is below stale threshold")
        return self
