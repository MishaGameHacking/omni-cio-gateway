from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

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
from omni_cio.paper import (
    GENESIS_RECORD_DIGEST,
    PaperLedgerArchiveError,
    parse_paper_ledger_record_unverified,
    seal_paper_ledger_record,
    serialize_paper_ledger_record,
    verify_paper_ledger_archive_chain,
    verify_paper_ledger_record,
)


BASE = datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc)
ACCOUNT = AccountReference(masked_id="***3118", account_type="ИИС")
KEY_A = b"a" * 32
KEY_B = b"b" * 32


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


def _purchase_event(
    *,
    sequence: int,
    occurred_at: datetime,
    scenario_id: str,
    cash_before: Decimal,
    purchase_cost: Decimal,
    position_before: int,
) -> PaperLedgerEventV1:
    return PaperLedgerEventV1(
        sequence=sequence,
        occurred_at=occurred_at,
        scenario_id=scenario_id,
        side=PaperLedgerSide.PURCHASE,
        status=PaperOrderStatus.FILLED,
        source_schema="paper_purchase_result",
        stable_key="uid:asset-a",
        instrument_uid="asset-a",
        lot_size=1,
        requested_lots=1,
        filled_lots=1,
        cash_before=Money(amount=cash_before, currency="RUB"),
        cash_after=Money(amount=cash_before - purchase_cost, currency="RUB"),
        position_lots_before=position_before,
        position_lots_after=position_before + 1,
        purchase_cost=Money(amount=purchase_cost, currency="RUB"),
        sale_net_proceeds=_money("0"),
        commission=_money("1"),
        estimated_tax=_money("0"),
    )


def _ledger(
    event_count: int,
    *,
    first_purchase_cost: Decimal = Decimal("100"),
) -> PaperAccountLedgerV1:
    if event_count not in {1, 2}:
        raise ValueError("test ledger supports one or two events")

    first = _purchase_event(
        sequence=1,
        occurred_at=BASE,
        scenario_id="paper.buy-1",
        cash_before=Decimal("1000"),
        purchase_cost=first_purchase_cost,
        position_before=0,
    )
    events = [first]
    total_cost = first_purchase_cost
    final_cash = Decimal("1000") - first_purchase_cost

    if event_count == 2:
        second = _purchase_event(
            sequence=2,
            occurred_at=BASE + timedelta(minutes=1),
            scenario_id="paper.buy-2",
            cash_before=final_cash,
            purchase_cost=Decimal("110"),
            position_before=1,
        )
        events.append(second)
        total_cost += Decimal("110")
        final_cash -= Decimal("110")

    retrieved_at = BASE + timedelta(minutes=event_count - 1)
    return PaperAccountLedgerV1(
        metadata=_metadata(retrieved_at),
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


def _seal(
    ledger: PaperAccountLedgerV1,
    *,
    key: bytes = KEY_A,
    key_id: str = "paper-key-a",
    sequence: int = 1,
    previous: str = GENESIS_RECORD_DIGEST,
    sealed_at: datetime | None = None,
):
    return seal_paper_ledger_record(
        ledger,
        signing_key=key,
        key_id=key_id,
        sequence=sequence,
        previous_record_digest=previous,
        sealed_at=sealed_at or BASE + timedelta(minutes=5 + sequence),
    )


def _serialized(record) -> bytes:
    return serialize_paper_ledger_record(record)


def test_record_round_trip_authenticates_and_restores_ledger() -> None:
    ledger = _ledger(1)
    record = _seal(ledger)
    restored = verify_paper_ledger_record(
        _serialized(record),
        signing_key=KEY_A,
        expected_previous_record_digest=GENESIS_RECORD_DIGEST,
        expected_sequence=1,
        expected_key_id="paper-key-a",
    )

    assert restored == record
    assert restored.ledger == ledger
    assert restored.authentication_required is True
    assert restored.storage_backend_attached is False
    assert restored.execution_ready is False
    assert restored.trading_methods is False


def test_sealing_is_deterministic_for_same_inputs() -> None:
    ledger = _ledger(1)
    first = _seal(ledger)
    second = _seal(ledger)

    assert first == second
    assert _serialized(first) == _serialized(second)


def test_wrong_key_and_modified_authentication_tag_are_rejected() -> None:
    record = _seal(_ledger(1))
    serialized = _serialized(record)

    with pytest.raises(PaperLedgerArchiveError, match="AUTHENTICATION_FAILED"):
        verify_paper_ledger_record(serialized, signing_key=KEY_B)

    data = json.loads(serialized)
    data["authentication_tag"] = "f" * 64
    tampered = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises(PaperLedgerArchiveError, match="AUTHENTICATION_FAILED"):
        verify_paper_ledger_record(tampered, signing_key=KEY_A)


def test_semantic_ledger_tampering_is_detected_before_hmac() -> None:
    record = _seal(_ledger(1))
    data = json.loads(_serialized(record))
    data["ledger"]["metadata"]["quality"]["warnings"] = ["tampered"]
    tampered = json.dumps(data, sort_keys=True, separators=(",", ":"))

    with pytest.raises(PaperLedgerArchiveError, match="LEDGER_DIGEST_MISMATCH"):
        verify_paper_ledger_record(tampered, signing_key=KEY_A)


def test_record_digest_tampering_is_detected() -> None:
    record = _seal(_ledger(1))
    data = json.loads(_serialized(record))
    data["record_digest"] = "f" * 64
    tampered = json.dumps(data, sort_keys=True, separators=(",", ":"))

    with pytest.raises(PaperLedgerArchiveError, match="RECORD_DIGEST_MISMATCH"):
        verify_paper_ledger_record(tampered, signing_key=KEY_A)


def test_duplicate_json_keys_and_invalid_utf8_are_rejected() -> None:
    with pytest.raises(PaperLedgerArchiveError, match="DUPLICATE_JSON_KEY"):
        parse_paper_ledger_record_unverified('{"sequence":1,"sequence":1}')

    with pytest.raises(PaperLedgerArchiveError, match="UTF8_INVALID"):
        parse_paper_ledger_record_unverified(b"\xff\xfe")


def test_unverified_parser_does_not_bypass_authentication() -> None:
    record = _seal(_ledger(1))
    parsed = parse_paper_ledger_record_unverified(_serialized(record))

    assert parsed.authentication_required is True
    with pytest.raises(PaperLedgerArchiveError, match="AUTHENTICATION_FAILED"):
        verify_paper_ledger_record(_serialized(parsed), signing_key=KEY_B)


def test_chain_verifies_full_history_and_supports_key_rotation() -> None:
    first = _seal(_ledger(1))
    second = _seal(
        _ledger(2),
        key=KEY_B,
        key_id="paper-key-b",
        sequence=2,
        previous=first.record_digest,
    )

    latest = verify_paper_ledger_archive_chain(
        (_serialized(first), _serialized(second)),
        signing_keys={"paper-key-a": KEY_A, "paper-key-b": KEY_B},
    )

    assert latest == second
    assert len(latest.ledger.events) == 2
    assert latest.ledger.final_cash.amount == Decimal("790")


def test_chain_rejects_missing_key_and_broken_link() -> None:
    first = _seal(_ledger(1))
    second = _seal(_ledger(2), sequence=2, previous=first.record_digest)

    with pytest.raises(PaperLedgerArchiveError, match="SIGNING_KEY_UNAVAILABLE"):
        verify_paper_ledger_archive_chain(
            (_serialized(first),),
            signing_keys={},
        )

    broken = _seal(_ledger(2), sequence=2, previous=GENESIS_RECORD_DIGEST)
    with pytest.raises(PaperLedgerArchiveError, match="CHAIN_LINK_MISMATCH"):
        verify_paper_ledger_archive_chain(
            (_serialized(first), _serialized(broken)),
            signing_keys={"paper-key-a": KEY_A},
        )


def test_chain_rejects_rewritten_or_truncated_history() -> None:
    first = _seal(_ledger(1))
    rewritten = _seal(
        _ledger(2, first_purchase_cost=Decimal("101")),
        sequence=2,
        previous=first.record_digest,
    )
    with pytest.raises(PaperLedgerArchiveError, match="HISTORY_REWRITTEN"):
        verify_paper_ledger_archive_chain(
            (_serialized(first), _serialized(rewritten)),
            signing_keys={"paper-key-a": KEY_A},
        )

    full = _seal(_ledger(2))
    truncated = _seal(
        _ledger(1),
        sequence=2,
        previous=full.record_digest,
        sealed_at=BASE + timedelta(minutes=8),
    )
    with pytest.raises(PaperLedgerArchiveError, match="HISTORY_TRUNCATED"):
        verify_paper_ledger_archive_chain(
            (_serialized(full), _serialized(truncated)),
            signing_keys={"paper-key-a": KEY_A},
        )


def test_chain_rejects_sequence_and_seal_time_regressions() -> None:
    first = _seal(_ledger(1))
    second = _seal(
        _ledger(2),
        sequence=3,
        previous=first.record_digest,
    )
    with pytest.raises(PaperLedgerArchiveError, match="SEQUENCE_MISMATCH"):
        verify_paper_ledger_archive_chain(
            (_serialized(first), _serialized(second)),
            signing_keys={"paper-key-a": KEY_A},
        )

    regressed = _seal(
        _ledger(2),
        sequence=2,
        previous=first.record_digest,
        sealed_at=BASE + timedelta(minutes=5),
    )
    with pytest.raises(PaperLedgerArchiveError, match="SEAL_TIME_REGRESSED"):
        verify_paper_ledger_archive_chain(
            (_serialized(first), _serialized(regressed)),
            signing_keys={"paper-key-a": KEY_A},
        )


def test_weak_key_empty_chain_and_execution_flag_tampering_are_rejected() -> None:
    with pytest.raises(PaperLedgerArchiveError, match="SIGNING_KEY_TOO_SHORT"):
        _seal(_ledger(1), key=b"short")

    with pytest.raises(PaperLedgerArchiveError, match="CHAIN_EMPTY"):
        verify_paper_ledger_archive_chain((), signing_keys={})

    record = _seal(_ledger(1))
    data = json.loads(_serialized(record))
    data["execution_ready"] = True
    tampered = json.dumps(data, sort_keys=True, separators=(",", ":"))
    with pytest.raises(PaperLedgerArchiveError, match="CONTRACT_INVALID"):
        verify_paper_ledger_record(tampered, signing_key=KEY_A)
