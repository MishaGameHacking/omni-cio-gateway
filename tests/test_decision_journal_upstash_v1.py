from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from threading import RLock
from typing import Any

import pytest

from omni_cio.contracts.v1.investment_policy import (
    InvestmentObjective,
    PolicyReferenceV1,
)
from omni_cio.decision_journal import (
    DecisionJournalConflict,
    DecisionJournalIntegrityError,
    UpstashDecisionJournalV1,
    evaluate_decision,
    finalize_decision_record,
    finalize_outcome_record,
)
from omni_cio.decision_journal import upstash_journal_v1 as module
from omni_cio.contracts.v1.decision_journal import DecisionJournalAction


NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
POLICY = PolicyReferenceV1(
    policy_id="ips_owner_v9",
    version="1",
    fingerprint_sha256="1" * 64,
)


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
                if script != module._APPEND_SCRIPT:
                    raise AssertionError("unexpected EVAL script")
                meta_key, rows_key = keys
                expected_meta, new_meta, record_id, envelope = args
                if self.strings.get(meta_key) != expected_meta:
                    return -1
                rows = self.hashes.setdefault(rows_key, {})
                current = rows.get(record_id)
                if current is not None:
                    return 0 if current == envelope else -2
                rows[record_id] = envelope
                self.strings[meta_key] = new_meta
                return 1
        raise AssertionError(f"unexpected command {command}")


def _decision():
    return finalize_decision_record(
        {
            "recorded_at": NOW,
            "horizon_days": 30,
            "policy_reference": POLICY,
            "policy_objective": InvestmentObjective.PRESERVE_PURCHASING_POWER,
            "portfolio_snapshot_sha256": "2" * 64,
            "decision_set_sha256": "3" * 64,
            "evidence_sha256s": ("4" * 64,),
            "risk_assessment_sha256": "5" * 64,
            "selected_action": DecisionJournalAction.HOLD,
            "starting_value_base": Decimal("1000000"),
            "research_items_expected": 1,
            "research_items_available": 1,
            "data_complete_at_decision": True,
        }
    )


def _outcome(decision_id: str):
    return finalize_outcome_record(
        {
            "decision_id": decision_id,
            "observed_at": NOW + timedelta(days=30),
            "horizon_days": 30,
            "ending_value_base": Decimal("1010000"),
            "net_external_flow_base": Decimal("0"),
            "research_items_observed": 1,
            "research_items_covered": 1,
            "data_completeness_ratio": Decimal("1"),
            "source_sha256s": ("6" * 64,),
        }
    )


def _journal(
    store: FakeRedisRest,
    *,
    secret: str = "wp14-decision-journal-test-secret",  # pragma: allowlist secret
) -> UpstashDecisionJournalV1:
    return UpstashDecisionJournalV1(
        "https://unit-test.upstash.io",
        "unit-test-rest-value",  # pragma: allowlist secret
        journal_secret=secret,
        client=store,
    )


def test_append_restart_and_replay_are_durable_and_idempotent() -> None:
    store = FakeRedisRest()
    journal = _journal(store)
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    evaluation = evaluate_decision(decision, outcome, evaluated_at=outcome.observed_at)

    journal.put_decision(decision)
    journal.put_outcome(outcome)
    journal.put_evaluation(evaluation)
    assert journal.integrity_check() == (1, 1, 1)

    restarted = _journal(store)
    assert restarted.get_decision(decision.decision_id) == decision
    assert restarted.get_outcome(outcome.outcome_id) == outcome
    assert restarted.get_evaluation(evaluation.evaluation_id) == evaluation
    assert restarted.put_decision(decision) == decision
    assert restarted.put_outcome(outcome) == outcome
    assert restarted.put_evaluation(evaluation) == evaluation
    assert restarted.integrity_check() == (1, 1, 1)


def test_append_only_identity_cannot_be_overwritten() -> None:
    store = FakeRedisRest()
    journal = _journal(store)
    decision = _decision()
    journal.put_decision(decision)

    raw = store.hashes[module._DECISIONS_KEY][decision.decision_id]
    envelope = json.loads(raw)
    envelope["payload_json"] = envelope["payload_json"].replace("1000000", "999999")
    tampered = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    store.hashes[module._DECISIONS_KEY][decision.decision_id] = tampered

    with pytest.raises(DecisionJournalIntegrityError):
        journal.get_decision(decision.decision_id)


def test_wrong_secret_and_metadata_tamper_fail_closed() -> None:
    store = FakeRedisRest()
    journal = _journal(store, secret="first-journal-secret")  # pragma: allowlist secret
    journal.put_decision(_decision())

    with pytest.raises(DecisionJournalIntegrityError):
        _journal(store, secret="other-journal-secret")  # pragma: allowlist secret

    raw = store.strings[module._META_KEY]
    metadata = json.loads(raw)
    metadata["decision_count"] = 99
    store.strings[module._META_KEY] = json.dumps(
        metadata,
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(DecisionJournalIntegrityError):
        journal.integrity_check()


def test_outcome_and_evaluation_require_existing_hash_bound_sources() -> None:
    store = FakeRedisRest()
    journal = _journal(store)
    decision = _decision()
    outcome = _outcome(decision.decision_id)
    evaluation = evaluate_decision(decision, outcome, evaluated_at=outcome.observed_at)

    with pytest.raises(DecisionJournalConflict, match="cannot precede"):
        journal.put_outcome(outcome)

    journal.put_decision(decision)
    with pytest.raises(DecisionJournalConflict, match="outcome binding"):
        journal.put_evaluation(evaluation)

    journal.put_outcome(outcome)
    journal.put_evaluation(evaluation)
    assert journal.integrity_check() == (1, 1, 1)
