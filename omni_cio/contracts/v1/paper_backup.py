from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from omni_cio.contracts.v1.common import ContractModel
from omni_cio.contracts.v1.paper_recovery import PaperLedgerRecoveryManifestV1


PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ArchiveFilename = Annotated[
    str,
    Field(pattern=r"^[0-9]{8}-[0-9a-f]{64}\.plae$"),
]
ManifestFilename = Annotated[
    str,
    Field(pattern=r"^recovery-[0-9]{8}-[0-9a-f]{64}\.plrm$"),
]
BackupReference = Annotated[
    str,
    Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{2,255}$"),
]


class PaperLedgerBackupFileResultV1(ContractModel):
    sequence: PositiveInt
    filename: ArchiveFilename
    record_digest: HexDigest
    envelope_digest: HexDigest
    size_bytes: Annotated[int, Field(gt=0, le=12 * 1024 * 1024)]
    outcome: Literal["copied", "already_present_identical"]
    atomic_write: bool
    immutable_target: Literal[True] = True
    encrypted_payload_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_file_binding(self) -> PaperLedgerBackupFileResultV1:
        expected = f"{self.sequence:08d}-{self.record_digest}.plae"
        if self.filename != expected:
            raise ValueError("paper backup filename does not match sequence and digest")
        if self.outcome == "copied" and self.atomic_write is not True:
            raise ValueError("copied paper backup file requires atomic write")
        if self.outcome == "already_present_identical" and self.atomic_write is not False:
            raise ValueError("existing identical paper backup file was not rewritten")
        return self


BackupFileResults = Annotated[
    tuple[PaperLedgerBackupFileResultV1, ...],
    Field(min_length=1, max_length=4096),
]


class PaperLedgerManifestStorageReceiptV1(ContractModel):
    stored_at: datetime
    filename: ManifestFilename
    manifest_digest: HexDigest
    latest_sequence: PositiveInt
    size_bytes: Annotated[int, Field(gt=0, le=4 * 1024 * 1024)]
    outcome: Literal["stored", "already_present_identical"]
    atomic_write: bool
    immutable_target: Literal[True] = True
    authenticated_manifest: Literal[True] = True
    permissions_mode: Literal["0600"] = "0600"
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("stored_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper backup receipt timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_manifest_filename(self) -> PaperLedgerManifestStorageReceiptV1:
        expected = (
            f"recovery-{self.latest_sequence:08d}-{self.manifest_digest}.plrm"
        )
        if self.filename != expected:
            raise ValueError("paper backup manifest filename does not match checkpoint")
        if self.outcome == "stored" and self.atomic_write is not True:
            raise ValueError("stored recovery manifest requires atomic write")
        if self.outcome == "already_present_identical" and self.atomic_write is not False:
            raise ValueError("existing recovery manifest was not rewritten")
        return self


class PaperLedgerBackupRestoreDrillV1(ContractModel):
    format_version: Literal["1.0"] = "1.0"
    drill_format: Literal["paper-ledger-backup-restore-drill-v1"] = (
        "paper-ledger-backup-restore-drill-v1"
    )
    started_at: datetime
    completed_at: datetime
    backup_reference: BackupReference
    source_latest_sequence: PositiveInt
    source_latest_record_digest: HexDigest
    source_event_count: PositiveInt
    files: BackupFileResults
    source_file_count: PositiveInt
    copied_count: NonNegativeInt
    already_present_count: NonNegativeInt
    manifest: PaperLedgerRecoveryManifestV1
    manifest_storage: PaperLedgerManifestStorageReceiptV1
    source_archive_verified: Literal[True] = True
    backup_archive_verified: Literal[True] = True
    restore_drill_verified: Literal[True] = True
    distinct_roots_verified: Literal[True] = True
    byte_identical_replication: Literal[True] = True
    encrypted_payload_only: Literal[True] = True
    no_source_mutation: Literal[True] = True
    no_backup_deletion: Literal[True] = True
    archive_transaction_atomic: Literal[False] = False
    record_atomic_writes: Literal[True] = True
    paper_only: Literal[True] = True
    broker_order_created: Literal[False] = False
    execution_ready: Literal[False] = False
    trading_methods: Literal[False] = False

    @field_validator("started_at", "completed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("paper backup drill timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_drill_summary(self) -> PaperLedgerBackupRestoreDrillV1:
        if self.completed_at < self.started_at:
            raise ValueError("paper backup drill completion predates start")
        if self.source_file_count != len(self.files):
            raise ValueError("paper backup source count does not match file results")
        if self.copied_count != sum(file.outcome == "copied" for file in self.files):
            raise ValueError("paper backup copied count does not match file results")
        if self.already_present_count != sum(
            file.outcome == "already_present_identical" for file in self.files
        ):
            raise ValueError("paper backup existing count does not match file results")
        if self.copied_count + self.already_present_count != self.source_file_count:
            raise ValueError("paper backup outcome counts do not cover source files")
        for expected, file in enumerate(self.files, start=1):
            if file.sequence != expected:
                raise ValueError("paper backup files must be contiguous")
        if self.source_latest_sequence != self.files[-1].sequence:
            raise ValueError("paper backup latest sequence does not match files")
        if self.source_latest_record_digest != self.files[-1].record_digest:
            raise ValueError("paper backup latest digest does not match files")
        if self.manifest.latest_sequence != self.source_latest_sequence:
            raise ValueError("paper backup manifest sequence does not match source")
        if self.manifest.latest_record_digest != self.source_latest_record_digest:
            raise ValueError("paper backup manifest digest does not match source")
        if self.manifest.latest_event_count != self.source_event_count:
            raise ValueError("paper backup manifest event count does not match source")
        if self.manifest.backup_reference != self.backup_reference:
            raise ValueError("paper backup reference does not match manifest")
        if self.manifest_storage.manifest_digest != self.manifest.manifest_digest:
            raise ValueError("paper backup stored manifest digest does not match manifest")
        return self
