from __future__ import annotations

from base64 import b64decode, b64encode
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Iterator, Protocol
from uuid import uuid4

from pydantic import ValidationError

from omni_cio.contracts.v1.paper_archive import PaperLedgerArchiveRecordV1
from omni_cio.contracts.v1.paper_storage import PaperLedgerEncryptedEnvelopeV1
from omni_cio.paper.archive_v1 import (
    serialize_paper_ledger_record,
    verify_paper_ledger_archive_chain,
)


_MAX_ENVELOPE_BYTES = 12 * 1024 * 1024
_STORAGE_SUFFIX = ".plae"
_STORAGE_NAME_PATTERN = re.compile(r"^(?P<sequence>[0-9]{8})-(?P<digest>[0-9a-f]{64})\.plae$")
_LOCK_NAME = ".paper-ledger.lock"


class PaperLedgerStorageError(RuntimeError):
    """Encrypted paper-ledger storage failed closed."""


@dataclass(frozen=True)
class ExternalAeadCiphertext:
    encryption_algorithm: str
    nonce: bytes
    ciphertext: bytes


class ExternalPaperLedgerKeyManager(Protocol):
    """External authenticated-encryption boundary; raw keys never enter storage."""

    def encrypt(
        self,
        *,
        key_id: str,
        plaintext: bytes,
        associated_data: bytes,
    ) -> ExternalAeadCiphertext: ...

    def decrypt(
        self,
        *,
        key_id: str,
        encryption_algorithm: str,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: bytes,
    ) -> bytes: ...


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperLedgerStorageError("PAPER_STORAGE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_CANONICALIZATION_FAILED") from exc


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PaperLedgerStorageError("PAPER_STORAGE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _associated_data(
    *,
    created_at: datetime,
    sequence: int,
    record_digest: str,
    encryption_key_id: str,
) -> bytes:
    return _canonical_json_bytes(
        {
            "format_version": "1.0",
            "storage_format": "paper-ledger-encrypted-json-v1",
            "created_at": created_at.isoformat(),
            "sequence": sequence,
            "record_digest": record_digest,
            "encryption_key_id": encryption_key_id,
            "paper_only": True,
            "execution_ready": False,
            "trading_methods": False,
        }
    )


def encrypt_paper_ledger_record(
    record: PaperLedgerArchiveRecordV1,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    encryption_key_id: str,
    created_at: datetime | None = None,
) -> PaperLedgerEncryptedEnvelopeV1:
    """Encrypt one authenticated archive record through an external AEAD manager."""

    timestamp = _aware_utc(created_at)
    plaintext = serialize_paper_ledger_record(record)
    aad = _associated_data(
        created_at=timestamp,
        sequence=record.sequence,
        record_digest=record.record_digest,
        encryption_key_id=encryption_key_id,
    )
    try:
        encrypted = key_manager.encrypt(
            key_id=encryption_key_id,
            plaintext=plaintext,
            associated_data=aad,
        )
    except Exception as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_ENCRYPTION_FAILED") from exc
    if not isinstance(encrypted, ExternalAeadCiphertext):
        raise PaperLedgerStorageError("PAPER_STORAGE_ENCRYPTION_RESULT_INVALID")
    if not encrypted.encryption_algorithm or not encrypted.nonce or not encrypted.ciphertext:
        raise PaperLedgerStorageError("PAPER_STORAGE_ENCRYPTION_RESULT_INCOMPLETE")
    try:
        return PaperLedgerEncryptedEnvelopeV1(
            encryption_algorithm=encrypted.encryption_algorithm,
            encryption_key_id=encryption_key_id,
            created_at=timestamp,
            sequence=record.sequence,
            record_digest=record.record_digest,
            associated_data_digest=hashlib.sha256(aad).hexdigest(),
            nonce_b64=b64encode(encrypted.nonce).decode("ascii"),
            ciphertext_b64=b64encode(encrypted.ciphertext).decode("ascii"),
            plaintext_size=len(plaintext),
            ciphertext_size=len(encrypted.ciphertext),
        )
    except ValidationError as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_ENVELOPE_INVALID") from exc


def serialize_encrypted_paper_ledger_envelope(
    envelope: PaperLedgerEncryptedEnvelopeV1,
) -> bytes:
    return _canonical_json_bytes(envelope.model_dump(mode="json"))


def parse_encrypted_paper_ledger_envelope(
    serialized: bytes | str,
) -> PaperLedgerEncryptedEnvelopeV1:
    if isinstance(serialized, str):
        raw = serialized.encode("utf-8")
    elif isinstance(serialized, bytes):
        raw = serialized
    else:
        raise PaperLedgerStorageError("PAPER_STORAGE_INPUT_TYPE_INVALID")
    if not raw or len(raw) > _MAX_ENVELOPE_BYTES:
        raise PaperLedgerStorageError("PAPER_STORAGE_SIZE_INVALID")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_UTF8_INVALID") from exc
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except PaperLedgerStorageError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise PaperLedgerStorageError("PAPER_STORAGE_ROOT_NOT_OBJECT")
    try:
        return PaperLedgerEncryptedEnvelopeV1.model_validate(value)
    except ValidationError as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_CONTRACT_INVALID") from exc


def decrypt_paper_ledger_envelope(
    envelope: PaperLedgerEncryptedEnvelopeV1,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
) -> bytes:
    aad = _associated_data(
        created_at=envelope.created_at,
        sequence=envelope.sequence,
        record_digest=envelope.record_digest,
        encryption_key_id=envelope.encryption_key_id,
    )
    if hashlib.sha256(aad).hexdigest() != envelope.associated_data_digest:
        raise PaperLedgerStorageError("PAPER_STORAGE_ASSOCIATED_DATA_MISMATCH")
    try:
        plaintext = key_manager.decrypt(
            key_id=envelope.encryption_key_id,
            encryption_algorithm=envelope.encryption_algorithm,
            nonce=b64decode(envelope.nonce_b64, validate=True),
            ciphertext=b64decode(envelope.ciphertext_b64, validate=True),
            associated_data=aad,
        )
    except Exception as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_DECRYPTION_FAILED") from exc
    if not isinstance(plaintext, bytes) or len(plaintext) != envelope.plaintext_size:
        raise PaperLedgerStorageError("PAPER_STORAGE_PLAINTEXT_SIZE_MISMATCH")
    return plaintext


def _prepare_root(root: Path) -> Path:
    if root.exists() and root.is_symlink():
        raise PaperLedgerStorageError("PAPER_STORAGE_ROOT_SYMLINK_FORBIDDEN")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise PaperLedgerStorageError("PAPER_STORAGE_ROOT_NOT_DIRECTORY")
    os.chmod(resolved, 0o700)
    return resolved


def _fsync_directory(root: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(root, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _exclusive_writer_lock(root: Path) -> Iterator[None]:
    lock_path = root / _LOCK_NAME
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except FileExistsError as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_CONCURRENT_WRITER") from exc
    try:
        os.write(fd, b"paper-ledger-writer\n")
        os.fsync(fd)
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        _fsync_directory(root)


def _storage_name(record: PaperLedgerArchiveRecordV1) -> str:
    return f"{record.sequence:08d}-{record.record_digest}{_STORAGE_SUFFIX}"


def _atomic_write(root: Path, target: Path, payload: bytes) -> None:
    temporary = root / f".{target.name}.{uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temporary, flags, 0o600)
    try:
        view = memoryview(payload)
        written = 0
        while written < len(view):
            written += os.write(fd, view[written:])
        os.fsync(fd)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(fd)
    try:
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        _fsync_directory(root)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


def write_encrypted_paper_ledger_record(
    root: Path | str,
    record: PaperLedgerArchiveRecordV1,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    encryption_key_id: str,
    created_at: datetime | None = None,
) -> Path:
    storage_root = _prepare_root(Path(root))
    envelope = encrypt_paper_ledger_record(
        record,
        key_manager=key_manager,
        encryption_key_id=encryption_key_id,
        created_at=created_at,
    )
    payload = serialize_encrypted_paper_ledger_envelope(envelope)
    target = storage_root / _storage_name(record)

    with _exclusive_writer_lock(storage_root):
        sequence_matches = tuple(storage_root.glob(f"{record.sequence:08d}-*{_STORAGE_SUFFIX}"))
        if sequence_matches and target not in sequence_matches:
            raise PaperLedgerStorageError("PAPER_STORAGE_SEQUENCE_ALREADY_EXISTS")
        if target.exists():
            if target.is_symlink():
                raise PaperLedgerStorageError("PAPER_STORAGE_TARGET_SYMLINK_FORBIDDEN")
            if _read_secure_file(target) != payload:
                raise PaperLedgerStorageError("PAPER_STORAGE_IMMUTABLE_RECORD_CONFLICT")
            return target
        _atomic_write(storage_root, target, payload)
    return target


def _read_secure_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_FILE_OPEN_FAILED") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise PaperLedgerStorageError("PAPER_STORAGE_FILE_NOT_REGULAR")
        if info.st_mode & 0o077:
            raise PaperLedgerStorageError("PAPER_STORAGE_FILE_PERMISSIONS_UNSAFE")
        if info.st_size <= 0 or info.st_size > _MAX_ENVELOPE_BYTES:
            raise PaperLedgerStorageError("PAPER_STORAGE_FILE_SIZE_INVALID")
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                raise PaperLedgerStorageError("PAPER_STORAGE_FILE_TRUNCATED")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def load_encrypted_paper_ledger_archive(
    root: Path | str,
    *,
    key_manager: ExternalPaperLedgerKeyManager,
    signing_keys: Mapping[str, bytes],
) -> PaperLedgerArchiveRecordV1:
    storage_root = _prepare_root(Path(root))
    candidates = sorted(storage_root.glob(f"*{_STORAGE_SUFFIX}"))
    if not candidates:
        raise PaperLedgerStorageError("PAPER_STORAGE_ARCHIVE_EMPTY")

    serialized_records: list[bytes] = []
    expected_sequence = 1
    for path in candidates:
        if path.is_symlink():
            raise PaperLedgerStorageError("PAPER_STORAGE_FILE_SYMLINK_FORBIDDEN")
        match = _STORAGE_NAME_PATTERN.fullmatch(path.name)
        if match is None:
            raise PaperLedgerStorageError("PAPER_STORAGE_FILENAME_INVALID")
        sequence = int(match.group("sequence"))
        if sequence != expected_sequence:
            raise PaperLedgerStorageError("PAPER_STORAGE_SEQUENCE_GAP")
        envelope = parse_encrypted_paper_ledger_envelope(_read_secure_file(path))
        if envelope.sequence != sequence:
            raise PaperLedgerStorageError("PAPER_STORAGE_FILENAME_SEQUENCE_MISMATCH")
        if envelope.record_digest != match.group("digest"):
            raise PaperLedgerStorageError("PAPER_STORAGE_FILENAME_DIGEST_MISMATCH")
        serialized_records.append(
            decrypt_paper_ledger_envelope(envelope, key_manager=key_manager)
        )
        expected_sequence += 1

    try:
        return verify_paper_ledger_archive_chain(
            serialized_records,
            signing_keys=signing_keys,
        )
    except Exception as exc:
        raise PaperLedgerStorageError("PAPER_STORAGE_ARCHIVE_VERIFICATION_FAILED") from exc


def list_encrypted_paper_ledger_files(root: Path | str) -> Sequence[Path]:
    storage_root = _prepare_root(Path(root))
    return tuple(sorted(storage_root.glob(f"*{_STORAGE_SUFFIX}")))
