from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Literal, TypeAlias, TypeVar

from omni_cio.contracts.v1.decision_journal import (
    DecisionEvaluationRecordV1,
    DecisionJournalRecordV1,
    DecisionOutcomeRecordV1,
)
from omni_cio.watchtower.upstash_journal_v1 import WatchtowerUpstashRestClientV1

from .journal_v1 import (
    DecisionJournalConflict,
    DecisionJournalIntegrityError,
    DecisionJournalStorageError,
)


_SCHEMA_VERSION = "1"
_NAMESPACE = "omni-cio:decision-journal:v1"
_META_KEY = f"{_NAMESPACE}:meta"
_DECISIONS_KEY = f"{_NAMESPACE}:decisions"
_OUTCOMES_KEY = f"{_NAMESPACE}:outcomes"
_EVALUATIONS_KEY = f"{_NAMESPACE}:evaluations"
_MAX_CAS_ATTEMPTS = 8

_APPEND_SCRIPT = """
local meta = redis.call('GET', KEYS[1])
if meta ~= ARGV[1] then
  return -1
end
local current = redis.call('HGET', KEYS[2], ARGV[3])
if current then
  if current == ARGV[4] then
    return 0
  end
  return -2
end
redis.call('HSET', KEYS[2], ARGV[3], ARGV[4])
redis.call('SET', KEYS[1], ARGV[2])
return 1
""".strip()

_Record = TypeVar(
    "_Record",
    DecisionJournalRecordV1,
    DecisionOutcomeRecordV1,
    DecisionEvaluationRecordV1,
)
_RecordValue: TypeAlias = (
    DecisionJournalRecordV1 | DecisionOutcomeRecordV1 | DecisionEvaluationRecordV1
)
_RecordKind = Literal["decision", "outcome", "evaluation"]


class UpstashDecisionJournalV1:
    """HMAC-authenticated append-only WP14 journal over the existing REST transport."""

    durable = True

    def __init__(
        self,
        rest_url: str,
        rest_token: str,
        *,
        journal_secret: str,
        client: WatchtowerUpstashRestClientV1 | Any | None = None,
    ) -> None:
        secret = journal_secret.strip()
        if not secret:
            raise DecisionJournalStorageError("decision journal secret is required")
        self._key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-decision-journal-v1",
            hashlib.sha256,
        ).digest()
        try:
            self._client = client or WatchtowerUpstashRestClientV1(rest_url, rest_token)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot initialize decision journal client: {type(exc).__name__}"
            ) from exc
        self._initialize()

    def _meta_mac(
        self,
        revision: int,
        decision_count: int,
        outcome_count: int,
        evaluation_count: int,
    ) -> str:
        message = (
            f"meta\n{_SCHEMA_VERSION}\n{revision}\n{decision_count}\n"
            f"{outcome_count}\n{evaluation_count}"
        ).encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _encode_meta(
        self,
        revision: int,
        decision_count: int,
        outcome_count: int,
        evaluation_count: int,
    ) -> str:
        return json.dumps(
            {
                "schema_version": _SCHEMA_VERSION,
                "revision": revision,
                "decision_count": decision_count,
                "outcome_count": outcome_count,
                "evaluation_count": evaluation_count,
                "mac": self._meta_mac(
                    revision,
                    decision_count,
                    outcome_count,
                    evaluation_count,
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_meta(self, raw: str) -> tuple[int, int, int, int]:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("metadata must be object")
            schema = str(data["schema_version"])
            revision = int(data["revision"])
            decisions = int(data["decision_count"])
            outcomes = int(data["outcome_count"])
            evaluations = int(data["evaluation_count"])
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DecisionJournalIntegrityError("invalid decision journal metadata") from exc
        counts = (revision, decisions, outcomes, evaluations)
        if schema != _SCHEMA_VERSION or any(value < 0 for value in counts):
            raise DecisionJournalIntegrityError("unsupported decision journal metadata")
        expected = self._meta_mac(revision, decisions, outcomes, evaluations)
        if not hmac.compare_digest(mac, expected):
            raise DecisionJournalIntegrityError("decision journal metadata integrity failure")
        return counts

    def _row_mac(self, kind: _RecordKind, record_id: str, payload: str) -> str:
        message = f"{kind}\n{record_id}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _encode_row(self, kind: _RecordKind, record_id: str, record: _Record) -> str:
        payload = record.model_dump_json()
        return json.dumps(
            {
                "kind": kind,
                "record_id": record_id,
                "payload_json": payload,
                "row_mac": self._row_mac(kind, record_id, payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_row(
        self,
        kind: _RecordKind,
        record_id: str,
        raw: str,
    ) -> DecisionJournalRecordV1 | DecisionOutcomeRecordV1 | DecisionEvaluationRecordV1:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("row envelope must be object")
            stored_kind = str(data["kind"])
            stored_id = str(data["record_id"])
            payload = str(data["payload_json"])
            row_mac = str(data["row_mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DecisionJournalIntegrityError("invalid decision journal row") from exc
        if stored_kind != kind or stored_id != record_id:
            raise DecisionJournalIntegrityError("decision journal row identity mismatch")
        expected = self._row_mac(kind, record_id, payload)
        if not hmac.compare_digest(row_mac, expected):
            raise DecisionJournalIntegrityError("decision journal row integrity failure")
        try:
            if kind == "decision":
                record = DecisionJournalRecordV1.model_validate_json(payload)
                if record.decision_id != record_id:
                    raise DecisionJournalIntegrityError("decision identity mismatch")
                return record
            if kind == "outcome":
                record = DecisionOutcomeRecordV1.model_validate_json(payload)
                if record.outcome_id != record_id:
                    raise DecisionJournalIntegrityError("outcome identity mismatch")
                return record
            record = DecisionEvaluationRecordV1.model_validate_json(payload)
            if record.evaluation_id != record_id:
                raise DecisionJournalIntegrityError("evaluation identity mismatch")
            return record
        except DecisionJournalIntegrityError:
            raise
        except Exception as exc:
            raise DecisionJournalIntegrityError("invalid decision journal payload") from exc

    def _initialize(self) -> None:
        try:
            raw = self._client.command("GET", _META_KEY)
            if raw is None:
                candidate = self._encode_meta(0, 0, 0, 0)
                self._client.command("SET", _META_KEY, candidate, "NX")
                raw = self._client.command("GET", _META_KEY)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot initialize decision journal: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise DecisionJournalStorageError("decision journal metadata unavailable")
        self._decode_meta(raw)

    def _read_meta(self) -> tuple[str, int, int, int, int]:
        try:
            raw = self._client.command("GET", _META_KEY)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot read decision journal metadata: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise DecisionJournalIntegrityError("decision journal metadata missing")
        revision, decisions, outcomes, evaluations = self._decode_meta(raw)
        return raw, revision, decisions, outcomes, evaluations

    def _raw(self, key: str, record_id: str) -> str | None:
        try:
            raw = self._client.command("HGET", key, record_id)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot read decision journal row: {type(exc).__name__}"
            ) from exc
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise DecisionJournalIntegrityError("decision journal row value is invalid")
        return raw

    def _append(
        self,
        *,
        kind: _RecordKind,
        key: str,
        record_id: str,
        record: _Record,
    ) -> _Record:
        envelope = self._encode_row(kind, record_id, record)
        for _ in range(_MAX_CAS_ATTEMPTS):
            meta_raw, revision, decisions, outcomes, evaluations = self._read_meta()
            new_counts = {
                "decision": (decisions + 1, outcomes, evaluations),
                "outcome": (decisions, outcomes + 1, evaluations),
                "evaluation": (decisions, outcomes, evaluations + 1),
            }[kind]
            new_meta = self._encode_meta(revision + 1, *new_counts)
            try:
                result = self._client.command(
                    "EVAL",
                    _APPEND_SCRIPT,
                    "2",
                    _META_KEY,
                    key,
                    meta_raw,
                    new_meta,
                    record_id,
                    envelope,
                )
            except Exception as exc:
                raise DecisionJournalStorageError(
                    f"cannot append decision journal row: {type(exc).__name__}"
                ) from exc
            if result == 1:
                return record
            if result == 0:
                current_raw = self._raw(key, record_id)
                if current_raw is None:
                    raise DecisionJournalConflict("journal row disappeared during replay")
                current = self._decode_row(kind, record_id, current_raw)
                if current == record:
                    return record
                raise DecisionJournalConflict("journal identity already has different payload")
            if result == -2:
                raise DecisionJournalConflict("journal identity already has different payload")
            if result != -1:
                raise DecisionJournalStorageError("unexpected decision journal append result")
        raise DecisionJournalConflict("decision journal metadata changed concurrently")

    def put_decision(self, record: DecisionJournalRecordV1) -> DecisionJournalRecordV1:
        return self._append(
            kind="decision",
            key=_DECISIONS_KEY,
            record_id=record.decision_id,
            record=record,
        )

    def get_decision(self, decision_id: str) -> DecisionJournalRecordV1:
        raw = self._raw(_DECISIONS_KEY, decision_id)
        if raw is None:
            raise KeyError("decision journal record not found")
        record = self._decode_row("decision", decision_id, raw)
        assert isinstance(record, DecisionJournalRecordV1)
        return record

    def put_outcome(self, record: DecisionOutcomeRecordV1) -> DecisionOutcomeRecordV1:
        try:
            self.get_decision(record.decision_id)
        except KeyError as exc:
            raise DecisionJournalConflict(
                "outcome cannot precede its immutable decision record"
            ) from exc
        return self._append(
            kind="outcome",
            key=_OUTCOMES_KEY,
            record_id=record.outcome_id,
            record=record,
        )

    def get_outcome(self, outcome_id: str) -> DecisionOutcomeRecordV1:
        raw = self._raw(_OUTCOMES_KEY, outcome_id)
        if raw is None:
            raise KeyError("decision outcome record not found")
        record = self._decode_row("outcome", outcome_id, raw)
        assert isinstance(record, DecisionOutcomeRecordV1)
        return record

    def _outcome_hash_bound(self, decision_id: str, outcome_sha256: str) -> bool:
        try:
            rows = self._client.command("HGETALL", _OUTCOMES_KEY)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot inspect outcome bindings: {type(exc).__name__}"
            ) from exc
        if not isinstance(rows, list) or len(rows) % 2:
            raise DecisionJournalIntegrityError("outcome rows are invalid")
        for index in range(0, len(rows), 2):
            outcome_id = rows[index]
            raw = rows[index + 1]
            if not isinstance(outcome_id, str) or not isinstance(raw, str):
                raise DecisionJournalIntegrityError("outcome row type invalid")
            row = self._decode_row("outcome", outcome_id, raw)
            assert isinstance(row, DecisionOutcomeRecordV1)
            if row.decision_id == decision_id and row.outcome_sha256 == outcome_sha256:
                return True
        return False

    def put_evaluation(
        self,
        record: DecisionEvaluationRecordV1,
    ) -> DecisionEvaluationRecordV1:
        try:
            decision = self.get_decision(record.decision_id)
        except KeyError as exc:
            raise DecisionJournalConflict("evaluation decision binding is unavailable") from exc
        if decision.record_sha256 != record.decision_record_sha256:
            raise DecisionJournalConflict("evaluation decision binding is unavailable")
        if not self._outcome_hash_bound(record.decision_id, record.outcome_record_sha256):
            raise DecisionJournalConflict("evaluation outcome binding is unavailable")
        return self._append(
            kind="evaluation",
            key=_EVALUATIONS_KEY,
            record_id=record.evaluation_id,
            record=record,
        )

    def get_evaluation(self, evaluation_id: str) -> DecisionEvaluationRecordV1:
        raw = self._raw(_EVALUATIONS_KEY, evaluation_id)
        if raw is None:
            raise KeyError("decision evaluation record not found")
        record = self._decode_row("evaluation", evaluation_id, raw)
        assert isinstance(record, DecisionEvaluationRecordV1)
        return record

    def _all_rows(self, key: str) -> list[Any]:
        try:
            rows = self._client.command("HGETALL", key)
        except Exception as exc:
            raise DecisionJournalStorageError(
                f"cannot inspect decision journal rows: {type(exc).__name__}"
            ) from exc
        if not isinstance(rows, list) or len(rows) % 2:
            raise DecisionJournalIntegrityError("decision journal rows are invalid")
        return rows

    def integrity_check(self) -> tuple[int, int, int]:
        _, _, expected_decisions, expected_outcomes, expected_evaluations = self._read_meta()
        keys: tuple[tuple[str, _RecordKind, int], ...] = (
            (_DECISIONS_KEY, "decision", expected_decisions),
            (_OUTCOMES_KEY, "outcome", expected_outcomes),
            (_EVALUATIONS_KEY, "evaluation", expected_evaluations),
        )
        decoded: dict[_RecordKind, list[_RecordValue]] = {
            "decision": [],
            "outcome": [],
            "evaluation": [],
        }
        for key, kind, expected_count in keys:
            try:
                raw_count = self._client.command("HLEN", key)
            except Exception as exc:
                raise DecisionJournalStorageError(
                    f"cannot count decision journal rows: {type(exc).__name__}"
                ) from exc
            try:
                count = int(raw_count)
            except (TypeError, ValueError) as exc:
                raise DecisionJournalIntegrityError("decision journal count invalid") from exc
            if count != expected_count:
                raise DecisionJournalIntegrityError(
                    "decision journal count does not match authenticated metadata"
                )
            rows = self._all_rows(key)
            if len(rows) != count * 2:
                raise DecisionJournalIntegrityError("decision journal row count invalid")
            for index in range(0, len(rows), 2):
                record_id = rows[index]
                raw = rows[index + 1]
                if not isinstance(record_id, str) or not isinstance(raw, str):
                    raise DecisionJournalIntegrityError("decision journal row type invalid")
                decoded[kind].append(self._decode_row(kind, record_id, raw))

        decisions = {
            row.decision_id: row
            for row in decoded["decision"]
            if isinstance(row, DecisionJournalRecordV1)
        }
        outcomes = [
            row for row in decoded["outcome"] if isinstance(row, DecisionOutcomeRecordV1)
        ]
        for row in outcomes:
            if row.decision_id not in decisions:
                raise DecisionJournalIntegrityError("orphan outcome record")
        decision_hashes = {
            row.record_sha256: row.decision_id for row in decisions.values()
        }
        outcome_hashes = {row.outcome_sha256: row.decision_id for row in outcomes}
        for row in decoded["evaluation"]:
            if not isinstance(row, DecisionEvaluationRecordV1):
                continue
            if decision_hashes.get(row.decision_record_sha256) != row.decision_id:
                raise DecisionJournalIntegrityError("evaluation decision binding mismatch")
            if outcome_hashes.get(row.outcome_record_sha256) != row.decision_id:
                raise DecisionJournalIntegrityError("evaluation outcome binding mismatch")
        return expected_decisions, expected_outcomes, expected_evaluations
