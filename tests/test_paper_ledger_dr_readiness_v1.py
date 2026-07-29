from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import os
from pathlib import Path

import pytest

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataQuality,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.paper import PaperOrderStatus
from omni_cio.contracts.v1.paper_dr import (
    PaperDrBlocker,
    PaperDrReadinessStatus,
    PaperDrWarning,
    PaperLedgerDrReadinessPolicyV1,
)
from omni_cio.contracts.v1.paper_ledger import (
    PaperAccountLedgerV1,
    PaperLedgerEventV1,
    PaperLedgerPositionV1,
    PaperLedgerSide,
)
from omni_cio.paper.archive_v1 import seal_paper_ledger_record
from omni_cio.paper.backup_v1 import run_paper_ledger_backup_restore_drill
from omni_cio.paper.dr_readiness_v1 import assess_paper_ledger_dr_readiness
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    write_encrypted_paper_ledger_record,
)


BASE = datetime(2026, 7, 29, 13, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
SIGNING_KEY = b"s" * 32
ENCRYPTION_KEY = b"e" * 32
MANIFEST_KEY = b"m" * 32


class _TestAeadKeyManager:
    """Test-only authenticated cipher; production uses an external AEAD/KMS."""

    def __init__(self, keys: dict[str, bytes]) -> None:
        self._keys = dict(keys)

    @staticmethod
    def _stream(key: bytes, nonce: bytes, aad: bytes, size: int) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < size:
            output.extend(
                hmac.new(
                    key,
                    nonce + aad + counter.to_bytes(4, "big"),
                    hashlib.sha256,
                ).digest()
            )
            counter += 1
        return bytes(output[:size])

    def encrypt(
        self,
        *,
        key_id: str,
        plaintext: bytes,
        associated_data: bytes,
    ) -> ExternalAeadCiphertext:
        key = self._keys[key_id]
        nonce = hashlib.sha256(key_id.encode() + plaintext + associated_data).digest()[:12]
        stream = self._stream(key, nonce, associated_data, len(plaintext))
        body = bytes(left ^ right for left, right in zip(plaintext, stream, strict=True))
        tag = hmac.new(key, associated_data + nonce + body, hashlib.sha256).digest()
        return ExternalAeadCiphertext(
            encryption_algorithm="test-aead-v1",
            nonce=nonce,
            ciphertext=body + tag,
        )

    def decrypt(
        self,
        *,
        key_id: str,
        encryption_algorithm: str,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes,
    ) -> bytes:
        if encryption_algorithm != "test-aead-v1":
            raise ValueError("unsupported test algorithm")
        key = self._keys[key_id]
        body, tag = ciphertext[:-32], ciphertext[-32:]
        expected = hmac.new(key, associated_data + nonce + body, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected):
            raise ValueError("test authentication failed")
        stream = self._stream(key, nonce, associated_data, len(body))
        return bytes(left ^ right for left, right in zip(body, stream, strict=True))


def _money(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="RUB")


def _ledger() -> PaperAccountLedgerV1:
    event = PaperLedgerEventV1(
        sequence=1,
        occurred_at=BASE,
        scenario_id="paper.buy-1",
        side=PaperLedgerSide.PURCHASE,
        status=PaperOrderStatus.FILLED,
        source_schema="paper_purchase_result",
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        lot_size=1,
        requested_lots=1,
        filled_lots=1,
        cash_before=_money("1000"),
        cash_after=_money("900"),
        position_lots_before=0,
        position_lots_after=1,
        purchase_cost=_money("100"),
        sale_net_proceeds=_money("0"),
        commission=_money("1"),
        estimated_tax=_money("0"),
    )
    metadata = ContractMetadata(
        schema_name="paper_account_ledger",
        retrieved_at=BASE,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="build_paper_account_ledger",
                retrieved_at=BASE,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )
    return PaperAccountLedgerV1(
        metadata=metadata,
        currency="RUB",
        initial_cash=_money("1000"),
        final_cash=_money("900"),
        initial_positions=(),
        final_positions=(
            PaperLedgerPositionV1(
                stable_key="uid:asset-a",
                instrument_uid="asset-a",
                lot_size=1,
                lots=1,
            ),
        ),
        events=(event,),
        scenario_ids=(event.scenario_id,),
        total_purchase_cost=_money("100"),
        total_sale_net_proceeds=_money("0"),
        total_commission=_money("1"),
        total_estimated_tax=_money("0"),
        filled_purchase_lots=1,
        filled_sale_lots=0,
        rejected_event_count=0,
    )


def _ready_storage(tmp_path: Path):
    primary = tmp_path / "primary"
    backup = tmp_path / "backup"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_KEY})
    record = seal_paper_ledger_record(
        _ledger(),
        signing_key=SIGNING_KEY,
        key_id="signing-a",
        sequence=1,
        sealed_at=BASE + timedelta(minutes=1),
    )
    write_encrypted_paper_ledger_record(
        primary,
        record,
        key_manager=manager,
        encryption_key_id="enc-a",
        created_at=BASE + timedelta(minutes=2),
    )
    run_paper_ledger_backup_restore_drill(
        primary,
        backup,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_KEY},
        manifest_signing_key=MANIFEST_KEY,
        manifest_key_id="manifest-a",
        backup_reference="backup://paper-ledger-dr-20260729",
        started_at=BASE + timedelta(minutes=3),
        completed_at=BASE + timedelta(minutes=4),
    )
    return primary, backup, manager


def _policy(**changes: object) -> PaperLedgerDrReadinessPolicyV1:
    values: dict[str, object] = {
        "max_manifest_age_seconds": 3600,
        "max_checkpoint_age_seconds": 3600,
        "minimum_free_bytes_per_root": 0,
        "require_separate_filesystem_device": False,
        "lock_stale_after_seconds": 900,
        "maximum_temp_artifacts_per_root": 64,
    }
    values.update(changes)
    return PaperLedgerDrReadinessPolicyV1.model_validate(values)


def _assess(
    primary: Path,
    backup: Path,
    manager: _TestAeadKeyManager,
    *,
    assessed_at: datetime | None = None,
    policy: PaperLedgerDrReadinessPolicyV1 | None = None,
    manifest_keys: dict[str, bytes] | None = None,
):
    return assess_paper_ledger_dr_readiness(
        primary,
        backup,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_KEY},
        manifest_signing_keys=(
            {"manifest-a": MANIFEST_KEY} if manifest_keys is None else manifest_keys
        ),
        assessed_at=assessed_at or BASE + timedelta(minutes=5),
        policy=policy or _policy(),
    )


def test_ready_assessment_requires_verified_recent_matching_archives(tmp_path: Path) -> None:
    primary, backup, manager = _ready_storage(tmp_path)

    result = _assess(primary, backup, manager)

    assert result.status is PaperDrReadinessStatus.READY
    assert result.blockers == ()
    assert result.primary_backup_match is True
    assert result.primary_state is not None
    assert result.backup_state is not None
    assert result.manifest is not None
    assert result.primary_state.latest_record_digest == result.backup_state.latest_record_digest
    assert result.manifest.latest_record_digest == result.primary_state.latest_record_digest
    assert result.primary_lock is not None and result.primary_lock.status == "absent"
    assert result.backup_lock is not None and result.backup_lock.status == "absent"
    assert result.temp_artifact_count == 0
    assert result.no_cleanup_performed is True
    assert result.no_lock_break_performed is True
    assert result.execution_ready is False
    assert result.trading_methods is False
    if not result.separate_filesystem_device:
        assert PaperDrWarning.SAME_FILESYSTEM_DEVICE_ALLOWED in result.warnings


def test_default_policy_blocks_same_filesystem_device(tmp_path: Path) -> None:
    primary, backup, manager = _ready_storage(tmp_path)

    result = _assess(
        primary,
        backup,
        manager,
        policy=PaperLedgerDrReadinessPolicyV1(
            max_manifest_age_seconds=3600,
            max_checkpoint_age_seconds=3600,
            minimum_free_bytes_per_root=0,
        ),
    )

    if result.separate_filesystem_device:
        assert result.status is PaperDrReadinessStatus.READY
    else:
        assert result.status is PaperDrReadinessStatus.BLOCKED
        assert PaperDrBlocker.FILESYSTEM_DEVICE_NOT_INDEPENDENT in result.blockers


def test_stale_manifest_and_checkpoint_block_readiness(tmp_path: Path) -> None:
    primary, backup, manager = _ready_storage(tmp_path)

    result = _assess(
        primary,
        backup,
        manager,
        assessed_at=BASE + timedelta(hours=2),
        policy=_policy(
            max_manifest_age_seconds=60,
            max_checkpoint_age_seconds=60,
        ),
    )

    assert result.status is PaperDrReadinessStatus.BLOCKED
    assert PaperDrBlocker.MANIFEST_STALE in result.blockers
    assert PaperDrBlocker.CHECKPOINT_STALE in result.blockers


def test_lock_temp_artifact_and_capacity_shortfall_are_reported_without_cleanup(
    tmp_path: Path,
) -> None:
    primary, backup, manager = _ready_storage(tmp_path)
    lock = primary / ".paper-ledger.lock"
    lock.write_bytes(b"paper-ledger-writer\n")
    os.chmod(lock, 0o600)
    temporary = backup / ".orphan-record.tmp"
    temporary.write_bytes(b"partial")
    os.chmod(temporary, 0o600)

    result = _assess(
        primary,
        backup,
        manager,
        policy=_policy(minimum_free_bytes_per_root=10**18),
    )

    assert result.status is PaperDrReadinessStatus.BLOCKED
    assert PaperDrBlocker.PRIMARY_LOCK_PRESENT in result.blockers
    assert PaperDrBlocker.TEMP_ARTIFACT_PRESENT in result.blockers
    assert PaperDrBlocker.CAPACITY_INSUFFICIENT in result.blockers
    assert result.temp_artifact_count == 1
    assert result.temp_artifacts[0].cleanup_performed is False
    assert lock.exists()
    assert temporary.exists()


def test_missing_manifest_and_missing_manifest_key_fail_closed(tmp_path: Path) -> None:
    primary, backup, manager = _ready_storage(tmp_path)
    manifest = next(backup.glob("*.plrm"))
    manifest.unlink()

    missing = _assess(primary, backup, manager)
    assert missing.status is PaperDrReadinessStatus.BLOCKED
    assert PaperDrBlocker.MANIFEST_MISSING in missing.blockers
    assert PaperDrBlocker.BACKUP_ARCHIVE_VERIFICATION_FAILED in missing.blockers

    run_paper_ledger_backup_restore_drill(
        primary,
        backup,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_KEY},
        manifest_signing_key=MANIFEST_KEY,
        manifest_key_id="manifest-a",
        backup_reference="backup://paper-ledger-dr-20260729",
        started_at=BASE + timedelta(minutes=3),
        completed_at=BASE + timedelta(minutes=4),
    )
    unavailable = _assess(primary, backup, manager, manifest_keys={})
    assert unavailable.status is PaperDrReadinessStatus.BLOCKED
    assert PaperDrBlocker.MANIFEST_KEY_UNAVAILABLE in unavailable.blockers


def test_tampered_manifest_is_blocked_without_repair(tmp_path: Path) -> None:
    primary, backup, manager = _ready_storage(tmp_path)
    manifest = next(backup.glob("*.plrm"))
    original = manifest.read_bytes()
    manifest.write_bytes(original[:-1] + (b"0" if original[-1:] != b"0" else b"1"))
    os.chmod(manifest, 0o600)

    result = _assess(primary, backup, manager)

    assert result.status is PaperDrReadinessStatus.BLOCKED
    assert (
        PaperDrBlocker.MANIFEST_AUTHENTICATION_FAILED in result.blockers
        or PaperDrBlocker.MANIFEST_FILE_INVALID in result.blockers
    )
    assert manifest.read_bytes() != original


def test_invalid_root_returns_blocked_assessment_without_invented_capacity(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    backup.mkdir(mode=0o700)
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_KEY})

    result = assess_paper_ledger_dr_readiness(
        tmp_path / "missing-primary",
        backup,
        key_manager=manager,
        signing_keys={},
        manifest_signing_keys={},
        assessed_at=BASE,
        policy=_policy(),
    )

    assert result.status is PaperDrReadinessStatus.BLOCKED
    assert PaperDrBlocker.PRIMARY_ROOT_INVALID in result.blockers
    assert result.capacities == ()
    assert result.primary_state is None
    assert result.no_cleanup_performed is True
