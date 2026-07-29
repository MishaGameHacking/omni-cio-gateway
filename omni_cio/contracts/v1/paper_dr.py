from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.paper_recovery import PaperLedgerLockDiagnosticV1


PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ManifestFilename = Annotated[
    str,
    Field(pattern=r"^recovery-[0-9]{8}-[0-9a-f]{64}\.plrm$"),
]
BackupReference = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{2,255}$"),
]


class PaperDrReadinessStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class PaperDrBlocker(StrEnum):
    PRIMARY_ROOT_INVALID = "primary_root_invalid"
    BACKUP_ROOT_INVALID = "backup_root_invalid"
    ROOTS_NOT_INDEPENDENT = "roots_not_independent"
    PRIMARY_LOCK_PRESENT = "primary_lock_present"
    BACKUP_LOCK_PRESENT = "backup_lock_present"
    TEMP_ARTIFACT_PRESENT = "temp_artifact_present"
    MANIFEST_MISSING = "manifest_missing"
    MANIFEST_AMBIGUOUS = "manifest_ambiguous"
    MANIFEST_FILE_INVALID = "manifest_file_invalid"
    MANIFEST_KEY_UNAVAILABLE = "manifest_key_unavailable"
    MANIFEST_AUTHENTICATION_FAILED = "manifest_authentication_failed"
    MANIFEST_FILENAME_MISMATCH = "manifest_filename_mismatch"
    MANIFEST_TIME_IN_FUTURE = "manifest_time_in_future"
    MANIFEST_STALE = "manifest_stale"
    PRIMARY_ARCHIVE_VERIFICATION_FAILED = "primary_archive_verification_failed"
    BACKUP_ARCHIVE_VERIFICATION_FAILED = "backup_archive_verification_failed"
    SOURCE_BACKUP_MISMATCH = "source_backup_mismatch"
    CHECKPOINT_TIME_IN_FUTURE = "checkpoint_time_in_future"
    CHECKPOINT_STALE = "checkpoint_stale"
    CAPACITY_INSUFFICIENT = "capacity_insufficient"
    FILESYSTEM_DEVICE_NOT_INDEPENDENT = "filesystem_device_not_independent"


class PaperDrWarning(StrEnum):
    SAME_FILESYSTEM_DEVICE_ALLOWED = "same_filesystem_device_allowed"
    OLD_MANIFESTS_PRESENT = "old_manifests_present"


class PaperLedgerDrReadinessPolicyV1(ContractModel):
    max_manifest_age_seconds: PositiveInt = 7 * 24 * 60 * 60
    max_checkpoint_age_seconds: PositiveInt = 7 * 24 * 60 * 60
    minimum_free_bytes_per_root: NonNegativeInt = 512 * 1024 * 1024
    require_separate_filesystem_device: bool = True
    maximum_temp_artifacts_per_root: Annotated[int, Field(gt=0, le=256)] = 64


class PaperLedgerDrArchiveStateV1(ContractModel):
    root_role: Literal["primary", "backup"]
    latest_sequence: PositiveInt
    latest_record_digest: HexDigest
    latest_event_count: PositiveInt
    checkpoint_at: datetime
    checkpoint_age_seconds: NonNegativeInt
    archive_verified: Literal[True] = True
    paper_only: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("checkpoint_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper DR checkpoint timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class PaperLedgerDrManifestEvidenceV1(ContractModel):
    filename: ManifestFilename
    manifest_digest: HexDigest
    manifest_key_id: Annotated[
        str,
        Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{2,127}$"),
    ]
    backup_reference: BackupReference
    created_at: datetime
    age_seconds: NonNegativeInt
    latest_sequence: PositiveInt
    latest_record_digest: HexDigest
    latest_event_count: PositiveInt
    authenticated: Literal[True] = True
    checkpoint_verified: Literal[True] = True
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("created_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper DR manifest timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_filename_binding(self) -> PaperLedgerDrManifestEvidenceV1:
        expected = (
            f"recovery-{self.latest_sequence:08d}-{self.manifest_digest}.plrm"
        )
        if self.filename != expected:
            raise ValueError("paper DR manifest filename does not match evidence")
        return self


class PaperLedgerDrTempArtifactV1(ContractModel):
    root_role: Literal["primary", "backup"]
    filename: Annotated[str, Field(min_length=1, max_length=255)]
    size_bytes: NonNegativeInt
    modified_at: datetime
    age_seconds: NonNegativeInt
    regular_file: bool
    symlink_detected: bool
    permissions_safe: bool
    cleanup_performed: Literal[False] = False

    @field_validator("modified_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper DR temp timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class PaperLedgerDrFilesystemCapacityV1(ContractModel):
    root_role: Literal["primary", "backup"]
    device_id: NonNegativeInt
    total_bytes: PositiveInt
    free_bytes: NonNegativeInt
    minimum_free_bytes: NonNegativeInt
    sufficient: bool

    @model_validator(mode="after")
    def validate_capacity(self) -> PaperLedgerDrFilesystemCapacityV1:
        if self.free_bytes > self.total_bytes:
            raise ValueError("paper DR free bytes exceed total bytes")
        if self.sufficient is not (self.free_bytes >= self.minimum_free_bytes):
            raise ValueError("paper DR capacity status is inconsistent")
        return self


TempArtifacts = Annotated[
    tuple[PaperLedgerDrTempArtifactV1, ...],
    Field(max_length=512),
]
Capacities = Annotated[
    tuple[PaperLedgerDrFilesystemCapacityV1, ...],
    Field(min_length=2, max_length=2),
]
Blockers = Annotated[tuple[PaperDrBlocker, ...], Field(max_length=32)]
Warnings = Annotated[tuple[PaperDrWarning, ...], Field(max_length=16)]


class PaperLedgerDrReadinessV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    assessment_format: Literal["paper-ledger-dr-readiness-v1"] = (
        "paper-ledger-dr-readiness-v1"
    )
    assessed_at: datetime
    status: PaperDrReadinessStatus
    policy: PaperLedgerDrReadinessPolicyV1
    primary_state: PaperLedgerDrArchiveStateV1 | None = None
    backup_state: PaperLedgerDrArchiveStateV1 | None = None
    manifest: PaperLedgerDrManifestEvidenceV1 | None = None
    primary_lock: PaperLedgerLockDiagnosticV1 | None = None
    backup_lock: PaperLedgerLockDiagnosticV1 | None = None
    temp_artifacts: TempArtifacts = ()
    temp_artifact_count: NonNegativeInt = 0
    capacities: Capacities
    blockers: Blockers = ()
    warnings: Warnings = ()
    primary_backup_match: bool
    separate_filesystem_device: bool
    no_cleanup_performed: Literal[True] = True
    no_lock_break_performed: Literal[True] = True
    no_retention_executed: Literal[True] = True
    read_only_assessment: Literal[True] = True
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("assessed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper DR assessment timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_readiness(self) -> PaperLedgerDrReadinessV1:
        if self.temp_artifact_count != len(self.temp_artifacts):
            raise ValueError("paper DR temp artifact count does not match evidence")
        blocker_set = set(self.blockers)
        warning_set = set(self.warnings)
        if len(blocker_set) != len(self.blockers):
            raise ValueError("paper DR blockers must be unique")
        if len(warning_set) != len(self.warnings):
            raise ValueError("paper DR warnings must be unique")
        capacity_sufficient = all(capacity.sufficient for capacity in self.capacities)
        evidence_complete = (
            self.primary_state is not None
            and self.backup_state is not None
            and self.manifest is not None
            and self.primary_lock is not None
            and self.backup_lock is not None
        )
        expected_ready = (
            not self.blockers
            and evidence_complete
            and self.primary_backup_match
            and capacity_sufficient
            and not self.temp_artifacts
            and self.primary_lock.status == "absent"
            and self.backup_lock.status == "absent"
        )
        if (self.status is PaperDrReadinessStatus.READY) is not expected_ready:
            raise ValueError("paper DR readiness status is inconsistent")
        if self.status is PaperDrReadinessStatus.READY:
            if self.policy.require_separate_filesystem_device:
                if not self.separate_filesystem_device:
                    raise ValueError("paper DR ready state requires separate devices")
            elif not self.separate_filesystem_device:
                if PaperDrWarning.SAME_FILESYSTEM_DEVICE_ALLOWED not in warning_set:
                    raise ValueError("paper DR same-device readiness requires warning")
        return self
