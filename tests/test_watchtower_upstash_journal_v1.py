from __future__ import annotations

from datetime import timedelta
import json
from threading import RLock
from typing import Any

import pytest

from omni_cio.contracts.v1.watchtower import (
    WatchtowerInputV1,
    watchtower_input_sha256,
)
from omni_cio.watchtower import InMemoryWatchtowerJournalV1, PortfolioWatchtowerV1
from omni_cio.watchtower import upstash_journal_v1 as module
from omni_cio.watchtower.journal_v1 import (
    WatchtowerJournalConflict,
    WatchtowerJournalIntegrityError,
    WatchtowerJournalStorageError,
)
from omni_cio.watchtower.upstash_journal_v1 import UpstashWatchtowerJournalV1
from tests.v9_execution_fixture import NOW, build_execution_fixture


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
                    meta_key, states_key = keys
                    expected_meta, new_meta, watch_id, envelope = args
                    if self.strings.get(meta_key) != expected_meta:
                        return -1
                    states = self.hashes.setdefault(states_key, {})
                    if watch_id in states:
                        return 0
                    states[watch_id] = envelope
                    self.strings[meta_key] = new_meta
                    return 1
                if script == module._CAS_SCRIPT:
                    states_key = keys[0]
                    watch_id, expected, replacement = args
                    states = self.hashes.setdefault(states_key, {})
                    if states.get(watch_id) != expected:
                        return 0
                    states[watch_id] = replacement
                    return 1
                raise AssertionError("unexpected EVAL script")
        raise AssertionError(f"unexpected command {command}")


def _state():
    fixture = build_execution_fixture()
    values = {
        "schema_version": "1.0",
        "checked_at": NOW + timedelta(minutes=1),
        "delivery_id": "durable-delivery-0001",
        "portfolio_snapshot_sha256": fixture.risk.portfolio_snapshot_sha256,
        "policy_reference": fixture.risk.policy_reference,
        "risk": fixture.risk,
        "credit_passports": (),
        "market_bundles": (),
        "source_quality_codes": (),
        "input_sha256": "0" * 64,
        "execution_authorized": False,
        "trading_methods": False,
    }
    provisional = WatchtowerInputV1.model_construct(**values)
    values["input_sha256"] = watchtower_input_sha256(provisional)
    value = WatchtowerInputV1.model_validate(values)
    service = PortfolioWatchtowerV1(
        journal=InMemoryWatchtowerJournalV1(),
        require_durable_journal=False,
    )
    return service.evaluate(value).state


def _journal(
    store: FakeRedisRest,
    *,
    secret: str = "wp13-watchtower-test-secret",  # pragma: allowlist secret
) -> UpstashWatchtowerJournalV1:
    return UpstashWatchtowerJournalV1(
        "https://unit-test.upstash.io",
        "unit-test-rest-value",  # pragma: allowlist secret
        journal_secret=secret,
        client=store,  # type: ignore[arg-type]
    )


def test_put_get_restart_and_compare_and_swap_are_durable() -> None:
    store = FakeRedisRest()
    first = _journal(store)
    state = _state()
    first.put(state)
    assert first.get(state.watch_id) == state
    assert first.integrity_check() == 1

    restarted = _journal(store)
    recovered = restarted.get(state.watch_id)
    assert recovered is not None
    updated = recovered.model_copy(
        update={
            "revision": 1,
            "updated_at": recovered.updated_at + timedelta(minutes=1),
            "state_sha256": "0" * 64,
        }
    )
    from omni_cio.contracts.v1.watchtower import watchtower_state_sha256

    updated = updated.model_copy(update={"state_sha256": watchtower_state_sha256(updated)})
    updated = type(recovered).model_validate(updated.model_dump(mode="python"))
    committed = restarted.compare_and_swap(
        state.watch_id,
        expected_revision=0,
        updated=updated,
    )
    assert committed.revision == 1
    assert restarted.integrity_check() == 1


def test_stale_writer_cannot_overwrite_newer_state() -> None:
    store = FakeRedisRest()
    durable = _journal(store)
    state = _state()
    durable.put(state)

    recovered = durable.get(state.watch_id)
    assert recovered is not None
    from omni_cio.contracts.v1.watchtower import watchtower_state_sha256

    updated = recovered.model_copy(
        update={"revision": 1, "state_sha256": "0" * 64}
    )
    updated = updated.model_copy(update={"state_sha256": watchtower_state_sha256(updated)})
    updated = type(recovered).model_validate(updated.model_dump(mode="python"))
    durable.compare_and_swap(state.watch_id, expected_revision=0, updated=updated)

    with pytest.raises(WatchtowerJournalConflict):
        durable.compare_and_swap(state.watch_id, expected_revision=0, updated=updated)


def test_wrong_secret_and_row_tamper_fail_closed() -> None:
    store = FakeRedisRest()
    durable = _journal(store, secret="first-watch-secret")  # pragma: allowlist secret
    state = _state()
    durable.put(state)

    with pytest.raises(WatchtowerJournalIntegrityError):
        _journal(store, secret="other-watch-secret")  # pragma: allowlist secret

    raw = store.hashes[module._STATES_KEY][state.watch_id]
    envelope = json.loads(raw)
    payload = json.loads(envelope["payload_json"])
    payload["last_input_sha256"] = "f" * 64
    envelope["payload_json"] = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    store.hashes[module._STATES_KEY][state.watch_id] = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(WatchtowerJournalIntegrityError):
        durable.integrity_check()


def test_upstash_endpoint_is_fail_closed() -> None:
    with pytest.raises(WatchtowerJournalStorageError):
        UpstashWatchtowerJournalV1(
            "http://unit-test.upstash.io",
            "rest-value",  # pragma: allowlist secret
            journal_secret="secret",  # pragma: allowlist secret
        )
    with pytest.raises(WatchtowerJournalStorageError):
        UpstashWatchtowerJournalV1(
            "https://example.com",
            "rest-value",  # pragma: allowlist secret
            journal_secret="secret",  # pragma: allowlist secret
        )
