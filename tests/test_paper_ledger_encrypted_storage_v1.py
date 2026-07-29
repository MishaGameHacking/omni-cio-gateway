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
from omni_cio.paper.archive_v1 import (
    GENESIS_RECORD_DIGEST,
    seal_paper_ledger_record,
)
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    PaperLedgerStorageError,
    load_encrypted_paper_ledger_archive,
    parse_encrypted_paper_ledger_envelope,
    write_encrypted_paper_ledger_record,
)


BASE = datetime(2026, 7, 29, 11, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
SIGNING_A = b"a" * 32
SIGNING_B = b"b" * 32
ENCRYPTION_A = b"c" * 32
ENCRYPTION_B = b"d" * 32


class _TestAeadKeyManager:
    """Test-only authenticated cipher; production supplies an external AEAD KMS."""

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


def test_atomic_encrypted_round_trip_hides_plaintext_and_sets_permissions(
    tmp_path: Path,
) -> None:
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})
    record = _record(1, sequence=1)

    stored = write_encrypted_paper_ledger_record(
        tmp_path / "paper",
        record,
        key_manager=manager,
        encryption_key_id="enc-a",
        created_at=BASE + timedelta(minutes=20),
    )
    raw = stored.read_bytes()
    envelope = parse_encrypted_paper_ledger_envelope(raw)
    restored = load_encrypted_paper_ledger_archive(
        tmp_path / "paper",
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_A},
    )

    assert restored == record
    assert b"paper_account_ledger" not in raw
    assert ACCOUNT.masked_id.encode() not in raw
    assert stored.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "paper").stat().st_mode & 0o777 == 0o700
    assert envelope.storage_backend_attached is True
    assert envelope.external_key_management is True
    assert envelope.execution_ready is False
    assert envelope.trading_methods is False


def test_two_record_chain_supports_signing_and_encryption_key_rotation(
    tmp_path: Path,
) -> None:
    manager = _TestAeadKeyManager(
        {"enc-a": ENCRYPTION_A, "enc-b": ENCRYPTION_B}
    )
    first = _record(1, sequence=1)
    second = _record(
        2,
        sequence=2,
        signing_key=SIGNING_B,
        signing_key_id="signing-b",
        previous=first.record_digest,
    )
    root = tmp_path / "paper"
    write_encrypted_paper_ledger_record(
        root,
        first,
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    write_encrypted_paper_ledger_record(
        root,
        second,
        key_manager=manager,
        encryption_key_id="enc-b",
    )

    restored = load_encrypted_paper_ledger_archive(
        root,
        key_manager=manager,
        signing_keys={"signing-a": SIGNING_A, "signing-b": SIGNING_B},
    )

    assert restored == second
    assert len(restored.ledger.events) == 2


def test_ciphertext_tampering_and_wrong_external_key_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "paper"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})
    stored = write_encrypted_paper_ledger_record(
        root,
        _record(1, sequence=1),
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    data = json.loads(stored.read_text())
    ciphertext = data["ciphertext_b64"]
    data["ciphertext_b64"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
    stored.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
    os.chmod(stored, 0o600)

    with pytest.raises(PaperLedgerStorageError, match="DECRYPTION_FAILED"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A},
        )

    stored.unlink()
    write_encrypted_paper_ledger_record(
        root,
        _record(1, sequence=1),
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    wrong = _TestAeadKeyManager({"enc-a": ENCRYPTION_B})
    with pytest.raises(PaperLedgerStorageError, match="DECRYPTION_FAILED"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=wrong,
            signing_keys={"signing-a": SIGNING_A},
        )


def test_concurrent_writer_lock_blocks_mutation(tmp_path: Path) -> None:
    root = tmp_path / "paper"
    root.mkdir(mode=0o700)
    lock = root / ".paper-ledger.lock"
    lock.write_text("held")
    os.chmod(lock, 0o600)

    with pytest.raises(PaperLedgerStorageError, match="CONCURRENT_WRITER"):
        write_encrypted_paper_ledger_record(
            root,
            _record(1, sequence=1),
            key_manager=_TestAeadKeyManager({"enc-a": ENCRYPTION_A}),
            encryption_key_id="enc-a",
        )

    assert tuple(root.glob("*.plae")) == ()


def test_atomic_replace_failure_leaves_no_partial_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "paper"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})

    def _fail_replace(source: object, destination: object) -> None:
        del source, destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr(os, "replace", _fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        write_encrypted_paper_ledger_record(
            root,
            _record(1, sequence=1),
            key_manager=manager,
            encryption_key_id="enc-a",
        )

    assert tuple(root.glob("*.plae")) == ()
    assert tuple(root.glob("*.tmp")) == ()
    assert not (root / ".paper-ledger.lock").exists()


def test_sequence_conflict_and_gap_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "paper"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})
    first = _record(1, sequence=1)
    write_encrypted_paper_ledger_record(
        root,
        first,
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    conflicting = _record(
        1,
        sequence=1,
        signing_key=SIGNING_B,
        signing_key_id="signing-b",
    )
    with pytest.raises(PaperLedgerStorageError, match="SEQUENCE_ALREADY_EXISTS"):
        write_encrypted_paper_ledger_record(
            root,
            conflicting,
            key_manager=manager,
            encryption_key_id="enc-a",
        )

    only_file = next(root.glob("*.plae"))
    gap_name = "00000002-" + "f" * 64 + ".plae"
    only_file.rename(root / gap_name)
    with pytest.raises(PaperLedgerStorageError, match="SEQUENCE_GAP"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A},
        )


def test_root_and_record_symlinks_are_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(real, target_is_directory=True)
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})

    with pytest.raises(PaperLedgerStorageError, match="ROOT_SYMLINK_FORBIDDEN"):
        write_encrypted_paper_ledger_record(
            root_link,
            _record(1, sequence=1),
            key_manager=manager,
            encryption_key_id="enc-a",
        )

    root = tmp_path / "paper"
    stored = write_encrypted_paper_ledger_record(
        root,
        _record(1, sequence=1),
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    content = stored.read_bytes()
    stored.unlink()
    target = tmp_path / "outside.plae"
    target.write_bytes(content)
    os.chmod(target, 0o600)
    stored.symlink_to(target)

    with pytest.raises(PaperLedgerStorageError, match="FILE_SYMLINK_FORBIDDEN"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A},
        )


def test_unsafe_permissions_and_envelope_metadata_tampering_are_rejected(
    tmp_path: Path,
) -> None:
    root = tmp_path / "paper"
    manager = _TestAeadKeyManager({"enc-a": ENCRYPTION_A})
    stored = write_encrypted_paper_ledger_record(
        root,
        _record(1, sequence=1),
        key_manager=manager,
        encryption_key_id="enc-a",
    )
    os.chmod(stored, 0o644)
    with pytest.raises(PaperLedgerStorageError, match="PERMISSIONS_UNSAFE"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A},
        )

    os.chmod(stored, 0o600)
    data = json.loads(stored.read_text())
    data["record_digest"] = "f" * 64
    stored.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
    os.chmod(stored, 0o600)
    with pytest.raises(PaperLedgerStorageError, match="FILENAME_DIGEST_MISMATCH"):
        load_encrypted_paper_ledger_archive(
            root,
            key_manager=manager,
            signing_keys={"signing-a": SIGNING_A},
        )
