from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from omni_cio.contracts.v1.plan_execution import PlanExecutionSessionV1
from omni_cio.real_trading.upstash_journal_v1 import UpstashRedisRestClientV1

from .journal_v1 import (
    PlanExecutionJournalConflict,
    PlanExecutionJournalIntegrityError,
    PlanExecutionJournalStorageError,
)


_SCHEMA_VERSION = "1"
_NAMESPACE = "omni-cio:plan-execution:v1"
_META_KEY = f"{_NAMESPACE}:meta"
_SESSIONS_KEY = f"{_NAMESPACE}:sessions"
_MAX_CAS_ATTEMPTS = 8

_PUT_SCRIPT = """
local meta = redis.call('GET', KEYS[1])
if meta ~= ARGV[1] then
  return -1
end
if redis.call('HEXISTS', KEYS[2], ARGV[3]) == 1 then
  return 0
end
redis.call('HSET', KEYS[2], ARGV[3], ARGV[4])
redis.call('SET', KEYS[1], ARGV[2])
return 1
""".strip()

_CAS_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current ~= ARGV[2] then
  return 0
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
return 1
""".strip()


class UpstashPlanExecutionJournalV1:
    """HMAC-authenticated durable journal for WP12 plan execution state."""

    durable = True

    def __init__(
        self,
        rest_url: str,
        rest_token: str,
        *,
        gateway_secret: str,
        client: UpstashRedisRestClientV1 | None = None,
    ) -> None:
        secret = gateway_secret.strip()
        if not secret:
            raise PlanExecutionJournalStorageError("gateway secret is required")
        self._key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-plan-execution-journal-v1",
            hashlib.sha256,
        ).digest()
        try:
            self._client = client or UpstashRedisRestClientV1(rest_url, rest_token)
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot initialize Upstash client: {type(exc).__name__}"
            ) from exc
        self._initialize()

    def _session_mac(self, execution_id: str, revision: int, payload: str) -> str:
        message = f"{execution_id}\n{revision}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _meta_mac(self, revision: int, session_count: int) -> str:
        message = (
            f"meta\n{_SCHEMA_VERSION}\n{revision}\n{session_count}"
        ).encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _encode_meta(self, revision: int, session_count: int) -> str:
        return json.dumps(
            {
                "schema_version": _SCHEMA_VERSION,
                "revision": revision,
                "session_count": session_count,
                "mac": self._meta_mac(revision, session_count),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_meta(self, raw: str) -> tuple[int, int]:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("meta must be object")
            schema = str(data["schema_version"])
            revision = int(data["revision"])
            count = int(data["session_count"])
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PlanExecutionJournalIntegrityError(
                "invalid plan execution journal metadata"
            ) from exc
        if schema != _SCHEMA_VERSION or revision < 0 or count < 0:
            raise PlanExecutionJournalIntegrityError(
                "unsupported plan execution journal metadata"
            )
        if not hmac.compare_digest(mac, self._meta_mac(revision, count)):
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal metadata integrity failure"
            )
        return revision, count

    def _encode_session(self, session: PlanExecutionSessionV1) -> str:
        payload = session.model_dump_json()
        return json.dumps(
            {
                "revision": session.revision,
                "payload_json": payload,
                "row_mac": self._session_mac(
                    session.execution_id,
                    session.revision,
                    payload,
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_session(
        self,
        execution_id: str,
        raw: str,
    ) -> PlanExecutionSessionV1:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("session envelope must be object")
            revision = int(data["revision"])
            payload = str(data["payload_json"])
            row_mac = str(data["row_mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PlanExecutionJournalIntegrityError(
                "invalid plan execution journal envelope"
            ) from exc
        expected = self._session_mac(execution_id, revision, payload)
        if revision < 0 or not hmac.compare_digest(row_mac, expected):
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal row integrity failure"
            )
        try:
            session = PlanExecutionSessionV1.model_validate_json(payload)
        except Exception as exc:
            raise PlanExecutionJournalIntegrityError(
                "invalid plan execution journal payload"
            ) from exc
        if session.execution_id != execution_id or session.revision != revision:
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal row identity mismatch"
            )
        return session

    def _initialize(self) -> None:
        try:
            raw = self._client.command("GET", _META_KEY)
            if raw is None:
                candidate = self._encode_meta(0, 0)
                self._client.command("SET", _META_KEY, candidate, "NX")
                raw = self._client.command("GET", _META_KEY)
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot initialize plan execution journal: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise PlanExecutionJournalStorageError(
                "plan execution journal metadata unavailable"
            )
        self._decode_meta(raw)

    def _read_meta(self) -> tuple[str, int, int]:
        try:
            raw = self._client.command("GET", _META_KEY)
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot read plan execution metadata: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal metadata missing"
            )
        revision, count = self._decode_meta(raw)
        return raw, revision, count

    def _raw_session(self, execution_id: str) -> str:
        try:
            raw = self._client.command("HGET", _SESSIONS_KEY, execution_id)
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot read plan execution session: {type(exc).__name__}"
            ) from exc
        if raw is None:
            raise KeyError("plan execution session not found")
        if not isinstance(raw, str):
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal value is invalid"
            )
        return raw

    def put(self, session: PlanExecutionSessionV1) -> PlanExecutionSessionV1:
        envelope = self._encode_session(session)
        for _ in range(_MAX_CAS_ATTEMPTS):
            meta_raw, meta_revision, count = self._read_meta()
            new_meta = self._encode_meta(meta_revision + 1, count + 1)
            try:
                result = self._client.command(
                    "EVAL",
                    _PUT_SCRIPT,
                    "2",
                    _META_KEY,
                    _SESSIONS_KEY,
                    meta_raw,
                    new_meta,
                    session.execution_id,
                    envelope,
                )
            except Exception as exc:
                raise PlanExecutionJournalStorageError(
                    f"cannot write plan execution session: {type(exc).__name__}"
                ) from exc
            if result == 1:
                return session
            if result == 0:
                current = self.get(session.execution_id)
                if current == session:
                    return current
                raise PlanExecutionJournalConflict(
                    "execution id already exists with different payload"
                )
            if result != -1:
                raise PlanExecutionJournalStorageError(
                    "unexpected plan execution put result"
                )
        raise PlanExecutionJournalConflict(
            "plan execution metadata changed concurrently"
        )

    def get(self, execution_id: str) -> PlanExecutionSessionV1:
        return self._decode_session(execution_id, self._raw_session(execution_id))

    def compare_and_swap(
        self,
        execution_id: str,
        *,
        expected_revision: int,
        updated: PlanExecutionSessionV1,
    ) -> PlanExecutionSessionV1:
        if updated.execution_id != execution_id:
            raise PlanExecutionJournalConflict("execution id mutation is forbidden")
        if updated.revision != expected_revision + 1:
            raise PlanExecutionJournalConflict(
                "execution revision must advance by exactly one"
            )
        expected_raw = self._raw_session(execution_id)
        current = self._decode_session(execution_id, expected_raw)
        if current.revision != expected_revision:
            raise PlanExecutionJournalConflict(
                f"execution revision conflict: {current.revision}"
            )
        new_raw = self._encode_session(updated)
        try:
            result = self._client.command(
                "EVAL",
                _CAS_SCRIPT,
                "1",
                _SESSIONS_KEY,
                execution_id,
                expected_raw,
                new_raw,
            )
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot update plan execution session: {type(exc).__name__}"
            ) from exc
        if result == 1:
            return updated
        if result != 0:
            raise PlanExecutionJournalStorageError(
                "unexpected plan execution CAS result"
            )
        raise PlanExecutionJournalConflict("plan execution session changed concurrently")

    def integrity_check(self) -> int:
        _, _, expected_count = self._read_meta()
        try:
            raw_count = self._client.command("HLEN", _SESSIONS_KEY)
            rows = self._client.command("HGETALL", _SESSIONS_KEY)
        except Exception as exc:
            raise PlanExecutionJournalStorageError(
                f"cannot inspect plan execution journal: {type(exc).__name__}"
            ) from exc
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal count is invalid"
            ) from exc
        if count != expected_count:
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal count does not match authenticated metadata"
            )
        if not isinstance(rows, list) or len(rows) != count * 2:
            raise PlanExecutionJournalIntegrityError(
                "plan execution journal hash payload is invalid"
            )
        for index in range(0, len(rows), 2):
            execution_id = rows[index]
            envelope = rows[index + 1]
            if not isinstance(execution_id, str) or not isinstance(envelope, str):
                raise PlanExecutionJournalIntegrityError(
                    "plan execution journal row is invalid"
                )
            self._decode_session(execution_id, envelope)
        return count

    @property
    def namespace(self) -> str:
        return _NAMESPACE

    def debug_metadata(self) -> dict[str, Any]:
        _, revision, count = self._read_meta()
        return {
            "schema_version": _SCHEMA_VERSION,
            "revision": revision,
            "session_count": count,
            "namespace": _NAMESPACE,
        }
