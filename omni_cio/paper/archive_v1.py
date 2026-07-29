from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Any

from pydantic import ValidationError

from omni_cio.contracts.v1.paper_archive import PaperLedgerArchiveRecordV1
from omni_cio.contracts.v1.paper_ledger import PaperAccountLedgerV1


GENESIS_RECORD_DIGEST = "0" * 64
_MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
_MIN_HMAC_KEY_BYTES = 32
_HEX_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PaperLedgerArchiveError(ValueError):
    """A paper-ledger archive record or chain failed strict verification."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _validate_signing_key(signing_key: bytes) -> bytes:
    if not isinstance(signing_key, bytes) or len(signing_key) < _MIN_HMAC_KEY_BYTES:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_SIGNING_KEY_TOO_SHORT")
    return signing_key


def _validate_digest(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if _HEX_DIGEST_PATTERN.fullmatch(normalized) is None:
        raise PaperLedgerArchiveError(f"{label}_INVALID")
    return normalized


def _canonical_json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_CANONICALIZATION_FAILED") from exc
    return text.encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ledger_payload(ledger: PaperAccountLedgerV1) -> dict[str, object]:
    payload = ledger.model_dump(mode="json")
    if not isinstance(payload, dict):
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_LEDGER_NOT_MAPPING")
    return payload


def _record_core(
    *,
    sequence: int,
    sealed_at: datetime,
    key_id: str,
    account_masked_id: str,
    currency: str,
    event_count: int,
    previous_record_digest: str,
    ledger_digest: str,
    ledger: PaperAccountLedgerV1,
) -> dict[str, object]:
    return {
        "format_version": "1.0",
        "canonicalization": "json-sorted-utf8-v1",
        "digest_algorithm": "sha256",
        "authentication_algorithm": "hmac-sha256",
        "sequence": sequence,
        "sealed_at": sealed_at.isoformat(),
        "key_id": key_id,
        "account_masked_id": account_masked_id,
        "currency": currency,
        "event_count": event_count,
        "previous_record_digest": previous_record_digest,
        "ledger_digest": ledger_digest,
        "ledger": _ledger_payload(ledger),
        "authentication_required": True,
        "storage_backend_attached": False,
        "paper_only": True,
        "broker_order_created": False,
        "execution_ready": False,
        "trading_methods": False,
    }


def _core_from_record(record: PaperLedgerArchiveRecordV1) -> dict[str, object]:
    return _record_core(
        sequence=record.sequence,
        sealed_at=record.sealed_at,
        key_id=record.key_id,
        account_masked_id=record.account_masked_id,
        currency=record.currency,
        event_count=record.event_count,
        previous_record_digest=record.previous_record_digest,
        ledger_digest=record.ledger_digest,
        ledger=record.ledger,
    )


def seal_paper_ledger_record(
    ledger: PaperAccountLedgerV1,
    *,
    signing_key: bytes,
    key_id: str,
    sequence: int,
    previous_record_digest: str = GENESIS_RECORD_DIGEST,
    sealed_at: datetime | None = None,
) -> PaperLedgerArchiveRecordV1:
    """Create one authenticated, storage-agnostic paper-ledger snapshot record."""

    key = _validate_signing_key(signing_key)
    if isinstance(sequence, bool) or sequence <= 0:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_SEQUENCE_INVALID")
    normalized_previous = _validate_digest(
        previous_record_digest,
        label="PAPER_ARCHIVE_PREVIOUS_DIGEST",
    )
    timestamp = _aware_utc(sealed_at)
    ledger_bytes = _canonical_json_bytes(_ledger_payload(ledger))
    ledger_digest = _sha256(ledger_bytes)
    core = _record_core(
        sequence=sequence,
        sealed_at=timestamp,
        key_id=key_id,
        account_masked_id=ledger.metadata.account.masked_id,
        currency=ledger.currency,
        event_count=len(ledger.events),
        previous_record_digest=normalized_previous,
        ledger_digest=ledger_digest,
        ledger=ledger,
    )
    core_bytes = _canonical_json_bytes(core)
    record_digest = _sha256(core_bytes)
    authentication_tag = hmac.new(key, core_bytes, hashlib.sha256).hexdigest()
    try:
        return PaperLedgerArchiveRecordV1.model_validate(
            {
                **core,
                "record_digest": record_digest,
                "authentication_tag": authentication_tag,
            }
        )
    except ValidationError as exc:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_RECORD_INVALID") from exc


def serialize_paper_ledger_record(record: PaperLedgerArchiveRecordV1) -> bytes:
    """Serialize a record canonically without writing it to any storage backend."""

    return _canonical_json_bytes(record.model_dump(mode="json"))


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PaperLedgerArchiveError("PAPER_ARCHIVE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _decode_json(serialized: bytes | str) -> dict[str, Any]:
    if isinstance(serialized, bytes):
        raw = serialized
    elif isinstance(serialized, str):
        raw = serialized.encode("utf-8")
    else:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_INPUT_TYPE_INVALID")
    if not raw or len(raw) > _MAX_ARCHIVE_BYTES:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_SIZE_INVALID")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_UTF8_INVALID") from exc
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except PaperLedgerArchiveError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_ROOT_NOT_OBJECT")
    return value


def parse_paper_ledger_record_unverified(
    serialized: bytes | str,
) -> PaperLedgerArchiveRecordV1:
    """Parse structural data only; callers must not treat this as authenticated."""

    try:
        return PaperLedgerArchiveRecordV1.model_validate(_decode_json(serialized))
    except ValidationError as exc:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_CONTRACT_INVALID") from exc


def _verify_record(
    record: PaperLedgerArchiveRecordV1,
    *,
    signing_key: bytes,
    expected_previous_record_digest: str | None,
    expected_sequence: int | None,
    expected_key_id: str | None,
) -> PaperLedgerArchiveRecordV1:
    key = _validate_signing_key(signing_key)
    if expected_sequence is not None and record.sequence != expected_sequence:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_SEQUENCE_MISMATCH")
    if expected_key_id is not None and record.key_id != expected_key_id:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_KEY_ID_MISMATCH")
    if expected_previous_record_digest is not None:
        expected_previous = _validate_digest(
            expected_previous_record_digest,
            label="PAPER_ARCHIVE_EXPECTED_PREVIOUS_DIGEST",
        )
        if record.previous_record_digest != expected_previous:
            raise PaperLedgerArchiveError("PAPER_ARCHIVE_CHAIN_LINK_MISMATCH")

    ledger_digest = _sha256(_canonical_json_bytes(_ledger_payload(record.ledger)))
    if not hmac.compare_digest(record.ledger_digest, ledger_digest):
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_LEDGER_DIGEST_MISMATCH")

    core_bytes = _canonical_json_bytes(_core_from_record(record))
    record_digest = _sha256(core_bytes)
    if not hmac.compare_digest(record.record_digest, record_digest):
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_RECORD_DIGEST_MISMATCH")

    expected_tag = hmac.new(key, core_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(record.authentication_tag, expected_tag):
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_AUTHENTICATION_FAILED")
    return record


def verify_paper_ledger_record(
    serialized: bytes | str,
    *,
    signing_key: bytes,
    expected_previous_record_digest: str | None = None,
    expected_sequence: int | None = None,
    expected_key_id: str | None = None,
) -> PaperLedgerArchiveRecordV1:
    """Parse and authenticate one record with an externally supplied HMAC key."""

    record = parse_paper_ledger_record_unverified(serialized)
    return _verify_record(
        record,
        signing_key=signing_key,
        expected_previous_record_digest=expected_previous_record_digest,
        expected_sequence=expected_sequence,
        expected_key_id=expected_key_id,
    )


def _require_ledger_extension(
    previous: PaperAccountLedgerV1,
    current: PaperAccountLedgerV1,
) -> None:
    if previous.metadata.account != current.metadata.account:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_ACCOUNT_CHANGED")
    if previous.currency != current.currency:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_CURRENCY_CHANGED")
    if previous.initial_cash != current.initial_cash:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_INITIAL_CASH_CHANGED")
    if previous.initial_positions != current.initial_positions:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_INITIAL_POSITIONS_CHANGED")
    if current.metadata.retrieved_at < previous.metadata.retrieved_at:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_LEDGER_TIME_REGRESSED")
    previous_event_count = len(previous.events)
    if len(current.events) < previous_event_count:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_HISTORY_TRUNCATED")
    if current.events[:previous_event_count] != previous.events:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_HISTORY_REWRITTEN")
    if current.scenario_ids[:previous_event_count] != previous.scenario_ids:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_SCENARIO_HISTORY_REWRITTEN")


def verify_paper_ledger_archive_chain(
    serialized_records: Sequence[bytes | str],
    *,
    signing_keys: Mapping[str, bytes],
) -> PaperLedgerArchiveRecordV1:
    """Verify an authenticated chain and return its latest full ledger record."""

    if not serialized_records:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_CHAIN_EMPTY")
    previous_digest = GENESIS_RECORD_DIGEST
    previous_record: PaperLedgerArchiveRecordV1 | None = None

    for expected_sequence, serialized in enumerate(serialized_records, start=1):
        parsed = parse_paper_ledger_record_unverified(serialized)
        signing_key = signing_keys.get(parsed.key_id)
        if signing_key is None:
            raise PaperLedgerArchiveError("PAPER_ARCHIVE_SIGNING_KEY_UNAVAILABLE")
        record = _verify_record(
            parsed,
            signing_key=signing_key,
            expected_previous_record_digest=previous_digest,
            expected_sequence=expected_sequence,
            expected_key_id=parsed.key_id,
        )
        if previous_record is not None:
            if record.sealed_at < previous_record.sealed_at:
                raise PaperLedgerArchiveError("PAPER_ARCHIVE_SEAL_TIME_REGRESSED")
            _require_ledger_extension(previous_record.ledger, record.ledger)
        previous_digest = record.record_digest
        previous_record = record

    if previous_record is None:
        raise PaperLedgerArchiveError("PAPER_ARCHIVE_CHAIN_EMPTY")
    return previous_record
