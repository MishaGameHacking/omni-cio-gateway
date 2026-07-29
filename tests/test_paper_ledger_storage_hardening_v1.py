from __future__ import annotations

import os
from typing import cast

import pytest

from omni_cio.contracts.v1.paper_archive import PaperLedgerArchiveRecordV1
from omni_cio.paper import storage_v1
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    PaperLedgerStorageError,
    encrypt_paper_ledger_record,
)


class _NeverCalledKeyManager:
    def encrypt(
        self,
        *,
        key_id: str,
        plaintext: bytes,
        associated_data: bytes,
    ) -> ExternalAeadCiphertext:
        del key_id, plaintext, associated_data
        raise AssertionError("invalid key ID must be rejected before KMS access")

    def decrypt(
        self,
        *,
        key_id: str,
        encryption_algorithm: str,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes,
    ) -> bytes:
        del key_id, encryption_algorithm, nonce, ciphertext, associated_data
        raise AssertionError("decrypt is not used")


def test_invalid_external_key_id_is_rejected_before_key_manager_access() -> None:
    invalid_record = cast(PaperLedgerArchiveRecordV1, object())
    with pytest.raises(PaperLedgerStorageError, match="KEY_ID_INVALID"):
        encrypt_paper_ledger_record(
            invalid_record,
            key_manager=_NeverCalledKeyManager(),
            encryption_key_id="INVALID KEY ID",
        )


def test_zero_progress_low_level_write_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "write", lambda fd, payload: 0)
    with pytest.raises(PaperLedgerStorageError, match="WRITE_STALLED"):
        storage_v1._write_all(1, b"payload")
