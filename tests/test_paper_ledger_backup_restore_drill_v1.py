from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import os
from pathlib import Path

import pytest

import omni_cio.paper.backup_v1 as backup_module
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
from omni_cio.contracts.v1.paper_ledger import (
    PaperAccountLedgerV1,
    PaperLedgerEventV1,
    PaperLedgerPositionV1,
    PaperLedgerSide,
)
from omni_cio.paper.archive_v1 import GENESIS_RECORD_DIGEST, seal_paper_ledger_record
from omni_cio.paper.backup_v1 import (
    PaperLedgerBackupError,
    run_paper_ledger_backup_restore_drill,
)
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    write_encrypted_paper_ledger_record,
)


BASE = datetime(2026, 7, 29, 13, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
SIGNING_A = b"a" * 32
SIGNING_B = b"b" * 32
ENCRYPTION_A = b"c" * 32
ENCRYPTION_B = b"d" * 32
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


def _metadata(retrieved_at: datetime) -> ContractMetadata:
    return ContractMetadata(
        schema_name="paper_account_ledger",
        retrieved_at=retrieved_at,
        account=ACCOUNT,
        provenance=(
            SourceReference(
                provider="omni-cio-test",
                operation="build_paper_account_ledger",
                retrieved_at=retrieved_at,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=DataQuality.VERIFIED,
            completeness=Completeness.COMPLETE,
        ),
    )


def _event(
    *,
    sequence: int,
    cash_before: Decimal,
    cost: Decimal,
    position_before: int,
) -> PaperLedgerEventV1:
    return PaperLedgerEventV1(
        sequence=sequence,
        occurred_at=BASE + timedelta(minutes=sequence - 1),
        scenario_id=f"paper.buy-{sequence}",
        side=PaperLedgerSide.PURCHASE,
        status=PaperOrderStatus.FILLED,
        source_schema="paper_purchase_result",
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        lot_size=1,
        requested_lots=1,
        filled_lots=1,
        cash_before=Money(amount=cash_before, currency="RUB"),
        cash_after=Money(amount=cash_before - cost, currency="RUB"),
        position_lots_before=position_before,
        position_lots_after=position_before + 1,
        purchase_cost=Money(amount=cost, currency="RUB"),
        sale_net_proceeds=_money("0"),
        commission=_money("1"),
        estimated_tax=_money("0"),
    )


def _ledger(event_count: int) -> PaperAccountLedgerV1:
    first = _event(
        sequence=1,
        cash_before=Decimal("1000"),
        cost=Decimal("100"),
        position_before=0,
    )
    events = [first]
    final_cash = Decimal("900")
    total_cost = Decimal("100")
    if event_count == 2:
        events.append(
            _event(
                sequence=2,
                cash_before=final_cash,
                cost=Decimal("110"),
                position_before=1,
            )
        )
        final_cash -= Decimal("110")
        total_cost += Decimal("110")
    return PaperAccountLedgerV1(
        metadata=_metadata(BASE + timedelta(minutes=event_count - 1)),
        currency="RUB",
        initial_cash=_money("1000"),
        final_cash=Money(amount=final_cash, currency="RUB"),
        initial_positions=(),
        final_positions=(
            PaperLedgerPositionV1(
                stable_key="uid:asset-a",
                instrument_uid="asset-a",
                lot_size=1,
                lots=event_count,
            ),
        ),
        events=tuple(events),
        scenario_ids=tuple(event.scenario_id for event in events),
        total_purchase_cost=Money(amount=total_cost, currency="RUB"),
        total_sale_net_proceeds=_money("0"),
        total_commission=Money(amount=Decimal(event_count), currency="RUB"),
        total_estimated_tax=_money("0"),
        filled_purchase_lots=event_count,
        filled_sale_lots=0,
        rejected_event_count=0,
    )


def _record(
    event_count: int,
    *,
    sequence: int,
    signing_key: bytes = SIGNING_A,
    signing_key_id: str = "signing-a",
    previous: str = GENESIS_RECORD_DIGEST,
):
    return seal_paper_ledger_record(
        _ledger(event_count),
        signing_key=signing_key,
        key_id=signing_key_id,
        sequence=sequence,
        previous_record_digest=previous,
        sealed_at=BASE + timedelta(minutes=10 + sequence),
    )


def _primary(tmp_path: Path):
    primary = tmp_path / "primary"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A, "enc-b": ENCRYPTION_B})
    first = _record(1, sequence=1)
    second = _record(
        2,
        sequence=2,
        signing_key=SIGNING_B,
        signing_key_id="signing-b",
        previous=first.record_digest,
    )
    write_encrypted_paper_ledger_record(
        primary,
        first,
        key_manager=manager,
        encryption_key_id="enc-a",
        created_at=BASE + timedelta(minutes=15),
    )
    write_encrypted_paper_ledger_record(
        primary,
        second,
        key_manager=manager,
        encryption_key_id="enc-b",
        created_at=BASE + timedelta(minutes=16),
    )
    return primary, manager, second


def _run(primary: Path, backup: Path, manager: _TestAeadKeyManager):
    return run_paper_ledger_backup_restore_drill(
        primary,
        backup,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
        manifest_signing_key=MANIFEST_KEY,
        manifest_key_id="manifest-a",
        backup_reference="backup://paper-ledger-drill-20260729",
        started_at=BASE + timedelta(minutes=20),
        completed_at=BASE + timedelta(minutes=30),
    )


def test_fresh_backup_drill_copies_encrypted_files_and_restores_latest(
    tmp_path: Path,
) -> None:
    primary, manager, latest = _primary(tmp_path)
    backup = tmp_path / "backup"
    source_before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in primary.glob("*.plae")
    }

    drill = _run(primary, backup, manager)

    assert drill.source_latest_sequence == 2
    assert drill.source_latest_record_digest == latest.record_digest
    assert drill.source_event_count == 2
    assert drill.copied_count == 2
    assert drill.already_present_count == 0
    assert drill.source_archive_verified is True
    assert drill.backup_archive_verified is True
    assert drill.restore_drill_verified is True
    assert drill.no_source_archive_file_mutation is True
    assert drill.no_backup_deletion is True
    assert drill.archive_transaction_atomic is False
    assert drill.execution_ready is False
    assert drill.trading_methods is False

    source_after = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in primary.glob("*.plae")
    }
    backup_files = sorted(backup.glob("*.plae"))
    manifest_files = sorted(backup.glob("*.plrm"))
    assert source_after == source_before
    assert len(backup_files) == 2
    assert len(manifest_files) == 1
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in backup_files)
    assert manifest_files[0].stat().st_mode & 0o777 == 0o600
    assert backup.stat().st_mode & 0o777 == 0o700
    assert ACCOUNT.masked_id.encode() not in backup_files[0].read_bytes()


def test_repeated_drill_is_idempotent_and_does_not_rewrite_identical_files(
    tmp_path: Path,
) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    first = _run(primary, backup, manager)
    mtimes = {path.name: path.stat().st_mtime_ns for path in backup.iterdir()}

    second = _run(primary, backup, manager)

    assert first.manifest == second.manifest
    assert second.copied_count == 0
    assert second.already_present_count == 2
    assert second.manifest_storage.outcome == "already_present_identical"
    assert second.manifest_storage.atomic_write is False
    assert {path.name: path.stat().st_mtime_ns for path in backup.iterdir()} == mtimes


def test_same_primary_and_backup_root_is_rejected_before_copy(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)

    with pytest.raises(PaperLedgerBackupError, match="ROOTS_OVERLAP"):
        _run(primary, primary, manager)


def test_extra_backup_archive_file_is_rejected_without_deletion(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    backup.mkdir(mode=0o700)
    extra = backup / f"99999999-{'f' * 64}.plae"
    extra.write_bytes(b"unexpected")
    os.chmod(extra, 0o600)

    with pytest.raises(PaperLedgerBackupError, match="EXTRA_ARCHIVE_FILES"):
        _run(primary, backup, manager)

    assert extra.exists()


def test_conflicting_existing_backup_file_fails_closed(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    backup.mkdir(mode=0o700)
    source = sorted(primary.glob("*.plae"))[0]
    target = backup / source.name
    target.write_bytes(source.read_bytes() + b"tamper")
    os.chmod(target, 0o600)

    with pytest.raises(PaperLedgerBackupError, match="IMMUTABLE_FILE_CONFLICT"):
        _run(primary, backup, manager)

    assert target.read_bytes().endswith(b"tamper")


def test_active_storage_lock_blocks_drill_and_is_not_removed(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    lock = primary / ".paper-ledger.lock"
    lock.write_bytes(b"paper-ledger-writer\n")
    os.chmod(lock, 0o600)

    with pytest.raises(PaperLedgerBackupError, match="CONCURRENT_STORAGE_ACCESS"):
        _run(primary, backup, manager)

    assert lock.exists()
    assert not (backup / ".paper-ledger.lock").exists()


def test_atomic_copy_failure_leaves_no_visible_record_or_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"

    def _fail_replace(source: Path, target: Path) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(backup_module.os, "replace", _fail_replace)
    with pytest.raises(PaperLedgerBackupError, match="ATOMIC_REPLACE_FAILED"):
        _run(primary, backup, manager)

    assert list(backup.glob("*.plae")) == []
    assert list(backup.glob("*.plrm")) == []
    assert list(backup.glob("*.tmp")) == []
    assert not (primary / ".paper-ledger.lock").exists()
    assert not (backup / ".paper-ledger.lock").exists()


def test_tampered_stored_manifest_is_rejected_on_repeat(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    _run(primary, backup, manager)
    manifest = next(backup.glob("*.plrm"))
    manifest.write_bytes(manifest.read_bytes() + b"tamper")
    os.chmod(manifest, 0o600)

    with pytest.raises(PaperLedgerBackupError, match="MANIFEST_IMMUTABLE_CONFLICT"):
        _run(primary, backup, manager)


def test_unsafe_primary_permissions_and_invalid_time_fail_closed(tmp_path: Path) -> None:
    primary, manager, _ = _primary(tmp_path)
    backup = tmp_path / "backup"
    os.chmod(primary, 0o755)
    with pytest.raises(PaperLedgerBackupError, match="PRIMARY_PERMISSIONS_UNSAFE"):
        _run(primary, backup, manager)

    os.chmod(primary, 0o700)
    with pytest.raises(PaperLedgerBackupError, match="COMPLETION_PREDATES_START"):
        run_paper_ledger_backup_restore_drill(
            primary,
            backup,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
            manifest_signing_key=MANIFEST_KEY,
            manifest_key_id="manifest-a",
            backup_reference="backup://paper-ledger-drill-20260729",
            started_at=BASE + timedelta(minutes=30),
            completed_at=BASE + timedelta(minutes=20),
        )
