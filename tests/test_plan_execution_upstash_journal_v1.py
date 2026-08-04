from __future__ import annotations

from datetime import timedelta
import json
from threading import RLock
from typing import Any

import pytest

from omni_cio.contracts.v1.plan_execution import (
    PlanExecutionInstrumentStateV1,
    PlanExecutionSessionState,
    PlanExecutionSessionV1,
    PlanExecutionSide,
    PlanExecutionStageV1,
)
from omni_cio.plan_execution import upstash_journal_v1 as module
from omni_cio.plan_execution.journal_v1 import (
    PlanExecutionJournalConflict,
    PlanExecutionJournalIntegrityError,
)
from omni_cio.plan_execution.upstash_journal_v1 import UpstashPlanExecutionJournalV1
from tests.v9_execution_fixture import NOW, build_execution_fixture, execution_binding


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
                    meta_key, sessions_key = keys
                    expected_meta, new_meta, execution_id, envelope = args
                    if self.strings.get(meta_key) != expected_meta:
                        return -1
                    sessions = self.hashes.setdefault(sessions_key, {})
                    if execution_id in sessions:
                        return 0
                    sessions[execution_id] = envelope
                    self.strings[meta_key] = new_meta
                    return 1
                if script == module._CAS_SCRIPT:
                    sessions_key = keys[0]
                    execution_id, expected, replacement = args
                    sessions = self.hashes.setdefault(sessions_key, {})
                    if sessions.get(execution_id) != expected:
                        return 0
                    sessions[execution_id] = replacement
                    return 1
                raise AssertionError("unexpected EVAL script")
        raise AssertionError(f"unexpected command {command}")


def _session() -> PlanExecutionSessionV1:
    fixture = build_execution_fixture()
    binding = execution_binding(fixture, as_of=NOW + timedelta(minutes=1))
    stage = PlanExecutionStageV1(
        stage_id="4" * 64,
        leg_sequence=1,
        stable_key=binding.stable_key,
        side=PlanExecutionSide.BUY,
        stage_index=1,
        stage_count=1,
        planned_lots=500,
        not_before_moscow_date=NOW.date(),
    )
    return PlanExecutionSessionV1(
        execution_id="1" * 64,
        plan_sha256=fixture.plan.plan_sha256,
        initial_review_sha256="2" * 64,
        prepared_at=NOW + timedelta(minutes=1),
        last_reviewed_at=NOW + timedelta(minutes=1),
        last_review_sha256="2" * 64,
        state=PlanExecutionSessionState.PREPARED,
        instrument_states=(
            PlanExecutionInstrumentStateV1(binding=binding, stages=(stage,)),
        ),
    )


def _journal(
    store: FakeRedisRest,
    *,
    secret: str = "wp12-gateway-test-secret",  # pragma: allowlist secret
) -> UpstashPlanExecutionJournalV1:
    return UpstashPlanExecutionJournalV1(
        "https://unit-test.upstash.io",
        "unit-test-rest-value",  # pragma: allowlist secret
        gateway_secret=secret,
        client=store,  # type: ignore[arg-type]
    )


def test_put_get_restart_and_compare_and_swap_are_durable() -> None:
    store = FakeRedisRest()
    first = _journal(store)
    session = _session()
    first.put(session)
    assert first.get(session.execution_id) == session
    assert first.integrity_check() == 1

    restarted = _journal(store)
    recovered = restarted.get(session.execution_id)
    updated = PlanExecutionSessionV1.model_validate(
        recovered.model_copy(update={"revision": 1}).model_dump(mode="python")
    )
    committed = restarted.compare_and_swap(
        session.execution_id,
        expected_revision=0,
        updated=updated,
    )
    assert committed.revision == 1
    assert restarted.get(session.execution_id) == updated
    assert restarted.integrity_check() == 1


def test_stale_revision_cannot_overwrite_newer_execution_state() -> None:
    store = FakeRedisRest()
    durable = _journal(store)
    session = _session()
    durable.put(session)
    updated = PlanExecutionSessionV1.model_validate(
        session.model_copy(update={"revision": 1}).model_dump(mode="python")
    )
    durable.compare_and_swap(
        session.execution_id,
        expected_revision=0,
        updated=updated,
    )

    with pytest.raises(PlanExecutionJournalConflict):
        durable.compare_and_swap(
            session.execution_id,
            expected_revision=0,
            updated=updated,
        )


def test_wrong_secret_and_row_tamper_fail_closed() -> None:
    store = FakeRedisRest()
    durable = _journal(store, secret="first-secret")  # pragma: allowlist secret
    session = _session()
    durable.put(session)

    with pytest.raises(PlanExecutionJournalIntegrityError):
        _journal(store, secret="different-secret")  # pragma: allowlist secret

    raw = store.hashes[module._SESSIONS_KEY][session.execution_id]
    envelope = json.loads(raw)
    payload = json.loads(envelope["payload_json"])
    payload["confirmed_cash_delta_rub"] = "999999"
    envelope["payload_json"] = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    store.hashes[module._SESSIONS_KEY][session.execution_id] = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(PlanExecutionJournalIntegrityError):
        durable.integrity_check()
