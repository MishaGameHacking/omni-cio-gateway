from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import json
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
from omni_cio.contracts.v1.paper_ledger import (
    PaperAccountLedgerV1,
    PaperLedgerEventV1,
    PaperLedgerPositionV1,
    PaperLedgerSide,
)
from omni_cio.paper.archive_v1 import GENESIS_RECORD_DIGEST, seal_paper_ledger_record
from omni_cio.paper.recovery_v1 import (
    PaperLedgerRecoveryError,
    build_paper_ledger_recovery_manifest,
    build_paper_ledger_retention_plan,
    diagnose_paper_ledger_writer_lock,
    parse_paper_ledger_recovery_manifest_unverified,
    serialize_paper_ledger_recovery_manifest,
    verify_paper_ledger_backup_against_manifest,
    verify_paper_ledger_recovery_manifest,
)
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    write_encrypted_paper_ledger_record,
)


BASE = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
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


def _copy_archive(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    for source_file in sorted(source.glob("*.plae")):
        target = destination / source_file.name
        target.write_bytes(source_file.read_bytes())
        os.chmod(target, 0o600)


def _archives(tmp_path: Path):
    primary = tmp_path / "primary"
    backup = tmp_path / "backup"
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
        created_at=BASE + timedelta(minutes=20),
    )
    write_encrypted_paper_ledger_record(
        primary,
        second,
        key_manager=manager,
        encryption_key_id="enc-b",
        created_at=BASE + timedelta(minutes=21),
    )
    _copy_archive(primary, backup)
    return primary, backup, manager, second


def _manifest(tmp_path: Path):
    primary, backup, manager, latest = _archives(tmp_path)
    manifest = build_paper_ledger_recovery_manifest(
        primary,
        backup,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
        manifest_signing_key=MANIFEST_KEY,
        manifest_key_id="manifest-a",
        backup_reference="backup://paper-ledger-20260729",
        created_at=BASE + timedelta(minutes=30),
    )
    return primary, backup, manager, latest, manifest


def test_manifest_requires_verified_primary_and_byte_identical_backup(
    tmp_path: Path,
) -> None:
    _, _, _, latest, manifest = _manifest(tmp_path)
    serialized = serialize_paper_ledger_recovery_manifest(manifest)
    verified = verify_paper_ledger_recovery_manifest(
        serialized,
        manifest_signing_key=MANIFEST_KEY,
        expected_backup_reference="backup://paper-ledger-20260729",
    )

    assert verified == manifest
    assert manifest.latest_sequence == 2
    assert manifest.latest_record_digest == latest.record_digest
    assert manifest.latest_event_count == 2
    assert manifest.archive_file_count == 2
    assert manifest.primary_archive_verified is True
    assert manifest.backup_archive_verified is True
    assert manifest.retention_execution_allowed is False
    assert manifest.execution_ready is False
    assert manifest.trading_methods is False


def test_manifest_tampering_wrong_key_and_duplicate_json_fail_closed(tmp_path: Path) -> None:
    _, _, _, _, manifest = _manifest(tmp_path)
    serialized = serialize_paper_ledger_recovery_manifest(manifest)

    with pytest.raises(PaperLedgerRecoveryError, match="AUTHENTICATION_FAILED"):
        verify_paper_ledger_recovery_manifest(
            serialized,
            manifest_signing_key=b"z" * 32,
        )

    data = json.loads(serialized)
    data["backup_reference"] = "backup://other-copy"
    tampered = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises(PaperLedgerRecoveryError, match="MANIFEST_DIGEST_MISMATCH"):
        verify_paper_ledger_recovery_manifest(
            tampered,
            manifest_signing_key=MANIFEST_KEY,
        )

    with pytest.raises(PaperLedgerRecoveryError, match="DUPLICATE_JSON_KEY"):
        parse_paper_ledger_recovery_manifest_unverified(
            '{"format_version":"1.0","format_version":"1.0"}'
        )


def test_manifest_rejects_missing_or_modified_backup_file(tmp_path: Path) -> None:
    primary, backup, manager, _ = _archives(tmp_path)
    sorted(backup.glob("*.plae"))[-1].unlink()

    with pytest.raises(PaperLedgerRecoveryError, match="BACKUP_EVIDENCE_MISMATCH"):
        build_paper_ledger_recovery_manifest(
            primary,
            backup,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
            manifest_signing_key=MANIFEST_KEY,
            manifest_key_id="manifest-a",
            backup_reference="backup://paper-ledger-20260729",
            created_at=BASE + timedelta(minutes=30),
        )


def test_backup_restore_verification_returns_authenticated_latest_record(
    tmp_path: Path,
) -> None:
    _, backup, manager, latest, manifest = _manifest(tmp_path)
    restored = verify_paper_ledger_backup_against_manifest(
        backup,
        serialize_paper_ledger_recovery_manifest(manifest),
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
        manifest_signing_key=MANIFEST_KEY,
        expected_backup_reference="backup://paper-ledger-20260729",
    )

    assert restored == latest
    assert restored.execution_ready is False
    assert restored.trading_methods is False


def test_retention_plan_identifies_candidates_but_never_deletes(tmp_path: Path) -> None:
    _, _, _, _, manifest = _manifest(tmp_path)
    plan = build_paper_ledger_retention_plan(
        serialize_paper_ledger_recovery_manifest(manifest),
        manifest_signing_key=MANIFEST_KEY,
        keep_last_records=1,
        planned_at=BASE + timedelta(minutes=31),
    )

    assert plan.candidate_count == 1
    assert plan.retained_count == 1
    assert plan.candidate_files == (manifest.files[0].filename,)
    assert plan.retained_files == (manifest.files[1].filename,)
    assert plan.backup_restore_required is True
    assert plan.online_chain_preserved_after_candidates is False
    assert plan.deletion_execution_allowed is False
    assert plan.deletion_executed is False


def test_retention_plan_can_keep_complete_online_chain(tmp_path: Path) -> None:
    _, _, _, _, manifest = _manifest(tmp_path)
    plan = build_paper_ledger_retention_plan(
        serialize_paper_ledger_recovery_manifest(manifest),
        manifest_signing_key=MANIFEST_KEY,
        keep_last_records=2,
    )

    assert plan.candidate_files == ()
    assert plan.backup_restore_required is False
    assert plan.online_chain_preserved_after_candidates is True


@pytest.mark.parametrize("keep_count", [0, -1, True, 3])
def test_retention_plan_rejects_invalid_keep_counts(
    tmp_path: Path,
    keep_count: int,
) -> None:
    _, _, _, _, manifest = _manifest(tmp_path)
    with pytest.raises(PaperLedgerRecoveryError, match="KEEP_COUNT"):
        build_paper_ledger_retention_plan(
            serialize_paper_ledger_recovery_manifest(manifest),
            manifest_signing_key=MANIFEST_KEY,
            keep_last_records=keep_count,
        )


def test_manifest_rejects_unsafe_archive_permissions(tmp_path: Path) -> None:
    primary, backup, manager, _ = _archives(tmp_path)
    os.chmod(sorted(backup.glob("*.plae"))[0], 0o644)

    with pytest.raises(PaperLedgerRecoveryError, match="PERMISSIONS_UNSAFE"):
        build_paper_ledger_recovery_manifest(
            primary,
            backup,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
            manifest_signing_key=MANIFEST_KEY,
            manifest_key_id="manifest-a",
            backup_reference="backup://paper-ledger-20260729",
            created_at=BASE + timedelta(minutes=30),
        )


def test_lock_diagnostic_reports_absent_active_and_stale_without_breaking(
    tmp_path: Path,
) -> None:
    root = tmp_path / "paper"
    root.mkdir()
    absent = diagnose_paper_ledger_writer_lock(
        root,
        observed_at=BASE,
        stale_after_seconds=900,
    )
    assert absent.status == "absent"
    assert absent.automatic_break_allowed is False

    lock = root / ".paper-ledger.lock"
    lock.write_bytes(b"paper-ledger-writer\n")
    os.chmod(lock, 0o600)
    os.utime(lock, (BASE.timestamp() - 100, BASE.timestamp() - 100))
    active = diagnose_paper_ledger_writer_lock(
        root,
        observed_at=BASE,
        stale_after_seconds=900,
    )
    assert active.status == "active"
    assert lock.exists()

    os.utime(lock, (BASE.timestamp() - 1000, BASE.timestamp() - 1000))
    stale = diagnose_paper_ledger_writer_lock(
        root,
        observed_at=BASE,
        stale_after_seconds=900,
    )
    assert stale.status == "stale_candidate"
    assert stale.manual_verification_required is True
    assert stale.automatic_break_allowed is False
    assert lock.exists()


def test_lock_diagnostic_marks_malformed_or_unsafe_lock_invalid(tmp_path: Path) -> None:
    root = tmp_path / "paper"
    root.mkdir()
    lock = root / ".paper-ledger.lock"
    lock.write_bytes(b"unexpected\n")
    os.chmod(lock, 0o644)
    os.utime(lock, (BASE.timestamp() - 1000, BASE.timestamp() - 1000))

    diagnostic = diagnose_paper_ledger_writer_lock(
        root,
        observed_at=BASE,
        stale_after_seconds=900,
    )

    assert diagnostic.status == "invalid"
    assert diagnostic.content_valid is False
    assert diagnostic.permissions_safe is False
    assert diagnostic.automatic_break_allowed is False
    assert lock.exists()
