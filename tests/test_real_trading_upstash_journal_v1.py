from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from threading import Barrier, RLock, Thread
from typing import Any

import httpx
import pytest

from omni_cio.real_trading.durable_journal_codec_v1 import (
    JournalIntegrityError,
    JournalStorageError,
)
from omni_cio.real_trading.journal_v1 import JournalDailyCapExceeded
from omni_cio.real_trading.models_v1 import RealTradeProposalV1
from omni_cio.real_trading import upstash_journal_v1 as module
from omni_cio.real_trading.upstash_journal_v1 import (
    UpstashRealExecutionJournalV1,
    UpstashRedisRestClientV1,
)


BASE_TIME = datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc)


class FakeRedisRest:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.lock = RLock()

    def command(self, *parts: Any) -> Any:
        command = str(parts[0]).upper()
        with self.lock:
            if command == "GET":
                return self.strings.get(str(parts[1]))
            if command == "SET":
                key = str(parts[1])
                value = str(parts[2])
                if len(parts) >= 4 and str(parts[3]).upper() == "NX":
                    if key in self.strings:
                        return None
                self.strings[key] = value
                return "OK"
            if command == "HGET":
                return self.hashes.get(str(parts[1]), {}).get(str(parts[2]))
            if command == "HLEN":
                return len(self.hashes.get(str(parts[1]), {}))
            if command == "HGETALL":
                result: list[str] = []
                for key, value in self.hashes.get(str(parts[1]), {}).items():
                    result.extend([key, value])
                return result
            if command == "EVAL":
                script = str(parts[1])
                numkeys = int(str(parts[2]))
                keys = [str(value) for value in parts[3 : 3 + numkeys]]
                args = [str(value) for value in parts[3 + numkeys :]]
                if script == module._PUT_SCRIPT:
                    meta_key, proposals_key = keys
                    expected_meta, new_meta, proposal_id, envelope = args
                    if self.strings.get(meta_key) != expected_meta:
                        return -1
                    proposals = self.hashes.setdefault(proposals_key, {})
                    if proposal_id in proposals:
                        return 0
                    proposals[proposal_id] = envelope
                    self.strings[meta_key] = new_meta
                    return 1
                if script == module._CAS_PROPOSAL_SCRIPT:
                    proposals_key = keys[0]
                    proposal_id, expected, replacement = args
                    proposals = self.hashes.setdefault(proposals_key, {})
                    if proposals.get(proposal_id) != expected:
                        return 0
                    proposals[proposal_id] = replacement
                    return 1
                if script == module._CAS_PROPOSAL_AND_DAILY_SCRIPT:
                    proposals_key, daily_key = keys
                    proposal_id, expected, replacement, expected_daily, new_daily = args
                    proposals = self.hashes.setdefault(proposals_key, {})
                    if proposals.get(proposal_id) != expected:
                        return -1
                    daily = self.strings.get(daily_key)
                    if expected_daily == module._MISSING:
                        if daily is not None:
                            return -2
                    elif daily != expected_daily:
                        return -2
                    proposals[proposal_id] = replacement
                    self.strings[daily_key] = new_daily
                    return 1
                raise AssertionError("unexpected EVAL script")
        raise AssertionError(f"unexpected command {command}")


def proposal(
    proposal_id: str,
    order_id: str,
    *,
    amount: str = "1000",
) -> RealTradeProposalV1:
    return RealTradeProposalV1(
        proposal_id=proposal_id,
        order_id=order_id,
        account_id="real-account-1234",
        instrument_uid="instrument-uid",
        ticker="SBER",
        isin="RU0009029540",
        direction="BUY",
        quantity_lots=1,
        limit_price=Decimal("270"),
        rationale="free durable journal test",
        preview_total_rub=Decimal(amount),
        preview_commission_rub=Decimal("1"),
        available_lots=10,
        market_retrieved_at=BASE_TIME - timedelta(seconds=1),
        created_at=BASE_TIME,
        expires_at=BASE_TIME + timedelta(seconds=120),
        confirmation_code="ABCDEF1234",
    )


def journal(
    store: FakeRedisRest,
    *,
    secret: str = "gateway-test-secret",
) -> UpstashRealExecutionJournalV1:
    return UpstashRealExecutionJournalV1(
        "https://unit-test.upstash.io",
        "unit-test-rest-value",  # pragma: allowlist secret
        gateway_secret=secret,
        client=store,  # type: ignore[arg-type]
    )


def test_rest_client_enforces_https_upstash_host() -> None:
    with pytest.raises(JournalStorageError):
        UpstashRedisRestClientV1(
            "http://example.com",
            "unit-test-rest-value",  # pragma: allowlist secret
        )
    with pytest.raises(JournalStorageError):
        UpstashRedisRestClientV1(
            "https://example.com",
            "unit-test-rest-value",  # pragma: allowlist secret
        )


def test_rest_client_sends_bearer_and_body_command() -> None:
    observed: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers.get("Authorization")
        observed["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"result": "PONG"})

    client = UpstashRedisRestClientV1(
        "https://unit-test.upstash.io",
        "unit-test-rest-value",  # pragma: allowlist secret
        transport=httpx.MockTransport(handler),
    )
    assert client.command("PING") == "PONG"
    assert observed == {
        "url": "https://unit-test.upstash.io/",
        "authorization": "Bearer unit-test-rest-value",  # pragma: allowlist secret
        "body": ["PING"],
    }


def test_put_get_and_restart_recovery() -> None:
    store = FakeRedisRest()
    first = journal(store)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    first.put(item)
    assert first.get(item.proposal_id) == item
    assert first.integrity_check() == 1

    restarted = journal(store)
    assert restarted.get(item.proposal_id) == item
    assert restarted.integrity_check() == 1


def test_wrong_gateway_secret_fails_closed() -> None:
    store = FakeRedisRest()
    first = journal(store, secret="first-secret")
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    first.put(item)
    with pytest.raises(JournalIntegrityError):
        journal(store, secret="different-secret")


def test_proposal_tampering_is_detected() -> None:
    store = FakeRedisRest()
    durable = journal(store)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    durable.put(item)
    raw = store.hashes[module._PROPOSALS_KEY][item.proposal_id]
    store.hashes[module._PROPOSALS_KEY][item.proposal_id] = raw.replace(
        '"quantity_lots":1', '"quantity_lots":9'
    )
    with pytest.raises(JournalIntegrityError):
        durable.integrity_check()


def test_metadata_deletion_or_count_tamper_is_detected() -> None:
    store = FakeRedisRest()
    durable = journal(store)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    durable.put(item)
    store.hashes[module._PROPOSALS_KEY].pop(item.proposal_id)
    with pytest.raises(JournalIntegrityError):
        durable.integrity_check()


def test_atomic_daily_cap_under_concurrent_confirmations() -> None:
    store = FakeRedisRest()
    durable = journal(store)
    first = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    second = proposal(
        "22222222-2222-4222-8222-222222222222",
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )
    durable.put(first)
    durable.put(second)

    barrier = Barrier(2)
    successes: list[str] = []
    blocked: list[str] = []

    def reserve(item: RealTradeProposalV1) -> None:
        barrier.wait()
        try:
            durable.reserve_submission(
                item.proposal_id,
                submitted_at=BASE_TIME + timedelta(seconds=10),
                max_daily_rub=Decimal("1500"),
            )
            successes.append(item.proposal_id)
        except JournalDailyCapExceeded:
            blocked.append(item.proposal_id)

    workers = [Thread(target=reserve, args=(first,)), Thread(target=reserve, args=(second,))]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert len(successes) == 1
    assert len(blocked) == 1
    day = (BASE_TIME + timedelta(seconds=10)).astimezone(module.MOSCOW).date()
    assert durable.submitted_notional_for_moscow_date(day) == Decimal("1000")
    assert durable.integrity_check() == 2


def test_definitive_failure_releases_daily_budget() -> None:
    store = FakeRedisRest()
    durable = journal(store)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    durable.put(item)
    submitted_at = BASE_TIME + timedelta(seconds=10)
    reserved = durable.reserve_submission(
        item.proposal_id,
        submitted_at=submitted_at,
        max_daily_rub=Decimal("2000"),
    )
    assert reserved.state == "submitting"
    day = submitted_at.astimezone(module.MOSCOW).date()
    assert durable.submitted_notional_for_moscow_date(day) == Decimal("1000")

    failed = durable.transition(
        item.proposal_id,
        allowed_from=frozenset({"submitting"}),
        state="failed",
        failure_code="BROKER_REJECTED",
        failure_message="definitive rejection",
    )
    assert failed.state == "failed"
    assert durable.submitted_notional_for_moscow_date(day) == Decimal("0")
    assert durable.integrity_check() == 1


def test_daily_counter_tampering_is_detected() -> None:
    store = FakeRedisRest()
    durable = journal(store)
    item = proposal(
        "11111111-1111-4111-8111-111111111111",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    durable.put(item)
    submitted_at = BASE_TIME + timedelta(seconds=10)
    durable.reserve_submission(
        item.proposal_id,
        submitted_at=submitted_at,
        max_daily_rub=Decimal("2000"),
    )
    day = submitted_at.astimezone(module.MOSCOW).date()
    key = durable._daily_key(day)
    raw = store.strings[key]
    store.strings[key] = raw.replace('"nano":"1000000000000"', '"nano":"1"')
    with pytest.raises(JournalIntegrityError):
        durable.integrity_check()
