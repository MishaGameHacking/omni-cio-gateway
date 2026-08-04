from __future__ import annotations

import hashlib
import hmac
import json
import ssl
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from omni_cio.contracts.v1.watchtower import WatchtowerStateV1

from .journal_v1 import (
    WatchtowerJournalConflict,
    WatchtowerJournalIntegrityError,
    WatchtowerJournalStorageError,
)


_SCHEMA_VERSION = "1"
_NAMESPACE = "omni-cio:watchtower:v1"
_META_KEY = f"{_NAMESPACE}:meta"
_STATES_KEY = f"{_NAMESPACE}:states"
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


class WatchtowerUpstashRestClientV1:
    """Strict HTTPS-only Upstash Redis REST client isolated to WP13."""

    def __init__(
        self,
        rest_url: str,
        rest_token: str,
        *,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        url = rest_url.strip().rstrip("/")
        token = rest_token.strip()
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not url or not token:
            raise WatchtowerJournalStorageError("Upstash REST URL and token are required")
        if (
            parsed.scheme != "https"
            or not hostname.endswith(".upstash.io")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise WatchtowerJournalStorageError(
                "Upstash REST URL must be a bare upstash.io HTTPS endpoint"
            )
        self._url = url
        self._token = token
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client_factory = client_factory
        self._ssl_context = ssl_context or ssl.create_default_context()

    def command(self, *parts: Any) -> Any:
        if not parts:
            raise WatchtowerJournalStorageError("Redis command must not be empty")
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "follow_redirects": False,
            "trust_env": False,
            "verify": self._ssl_context,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        try:
            with self._client_factory(**kwargs) as client:
                response = client.post(
                    self._url,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "omni-cio-watchtower-journal/1",
                    },
                    json=list(parts),
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
            raise WatchtowerJournalStorageError(
                f"Watchtower Upstash transport failure: {type(exc).__name__}"
            ) from exc
        if response.status_code != 200:
            raise WatchtowerJournalStorageError(
                f"Watchtower Upstash HTTP failure: {response.status_code}"
            )
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise WatchtowerJournalStorageError(
                "Watchtower Upstash returned non-JSON"
            ) from exc
        if not isinstance(payload, dict) or "result" not in payload:
            raise WatchtowerJournalStorageError(
                "Watchtower Upstash response has no result"
            )
        if payload.get("error") is not None:
            raise WatchtowerJournalStorageError("Watchtower Upstash command failed")
        return payload["result"]


class UpstashWatchtowerJournalV1:
    """HMAC-authenticated durable WP13 state with exact Redis CAS semantics."""

    durable = True

    def __init__(
        self,
        rest_url: str,
        rest_token: str,
        *,
        journal_secret: str,
        client: WatchtowerUpstashRestClientV1 | None = None,
    ) -> None:
        secret = journal_secret.strip()
        if not secret:
            raise WatchtowerJournalStorageError("watchtower journal secret is required")
        self._key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-watchtower-journal-v1",
            hashlib.sha256,
        ).digest()
        try:
            self._client = client or WatchtowerUpstashRestClientV1(rest_url, rest_token)
        except WatchtowerJournalStorageError:
            raise
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot initialize Watchtower Upstash client: {type(exc).__name__}"
            ) from exc
        self._initialize()

    def _meta_mac(self, revision: int, state_count: int) -> str:
        message = f"meta\n{_SCHEMA_VERSION}\n{revision}\n{state_count}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _state_mac(self, watch_id: str, revision: int, payload: str) -> str:
        message = f"{watch_id}\n{revision}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _encode_meta(self, revision: int, state_count: int) -> str:
        return json.dumps(
            {
                "schema_version": _SCHEMA_VERSION,
                "revision": revision,
                "state_count": state_count,
                "mac": self._meta_mac(revision, state_count),
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
            count = int(data["state_count"])
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WatchtowerJournalIntegrityError("invalid Watchtower metadata") from exc
        if schema != _SCHEMA_VERSION or revision < 0 or count < 0:
            raise WatchtowerJournalIntegrityError("unsupported Watchtower metadata")
        if not hmac.compare_digest(mac, self._meta_mac(revision, count)):
            raise WatchtowerJournalIntegrityError("Watchtower metadata integrity failure")
        return revision, count

    def _encode_state(self, state: WatchtowerStateV1) -> str:
        payload = state.model_dump_json()
        return json.dumps(
            {
                "revision": state.revision,
                "payload_json": payload,
                "row_mac": self._state_mac(state.watch_id, state.revision, payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_state(self, watch_id: str, raw: str) -> WatchtowerStateV1:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("state envelope must be object")
            revision = int(data["revision"])
            payload = str(data["payload_json"])
            row_mac = str(data["row_mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise WatchtowerJournalIntegrityError(
                "invalid Watchtower state envelope"
            ) from exc
        expected = self._state_mac(watch_id, revision, payload)
        if revision < 0 or not hmac.compare_digest(row_mac, expected):
            raise WatchtowerJournalIntegrityError("Watchtower state integrity failure")
        try:
            state = WatchtowerStateV1.model_validate_json(payload)
        except Exception as exc:
            raise WatchtowerJournalIntegrityError(
                "invalid Watchtower state payload"
            ) from exc
        if state.watch_id != watch_id or state.revision != revision:
            raise WatchtowerJournalIntegrityError("Watchtower state identity mismatch")
        return state

    def _initialize(self) -> None:
        try:
            raw = self._client.command("GET", _META_KEY)
            if raw is None:
                candidate = self._encode_meta(0, 0)
                self._client.command("SET", _META_KEY, candidate, "NX")
                raw = self._client.command("GET", _META_KEY)
        except WatchtowerJournalIntegrityError:
            raise
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot initialize Watchtower journal: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise WatchtowerJournalStorageError("Watchtower metadata unavailable")
        self._decode_meta(raw)

    def _read_meta(self) -> tuple[str, int, int]:
        try:
            raw = self._client.command("GET", _META_KEY)
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot read Watchtower metadata: {type(exc).__name__}"
            ) from exc
        if not isinstance(raw, str):
            raise WatchtowerJournalIntegrityError("Watchtower metadata missing")
        revision, count = self._decode_meta(raw)
        return raw, revision, count

    def _raw_state(self, watch_id: str) -> str | None:
        try:
            raw = self._client.command("HGET", _STATES_KEY, watch_id)
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot read Watchtower state: {type(exc).__name__}"
            ) from exc
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise WatchtowerJournalIntegrityError("Watchtower state value is invalid")
        return raw

    def get(self, watch_id: str) -> WatchtowerStateV1 | None:
        raw = self._raw_state(watch_id)
        return None if raw is None else self._decode_state(watch_id, raw)

    def put(self, state: WatchtowerStateV1) -> WatchtowerStateV1:
        envelope = self._encode_state(state)
        for _ in range(_MAX_CAS_ATTEMPTS):
            meta_raw, meta_revision, count = self._read_meta()
            new_meta = self._encode_meta(meta_revision + 1, count + 1)
            try:
                result = self._client.command(
                    "EVAL",
                    _PUT_SCRIPT,
                    "2",
                    _META_KEY,
                    _STATES_KEY,
                    meta_raw,
                    new_meta,
                    state.watch_id,
                    envelope,
                )
            except Exception as exc:
                raise WatchtowerJournalStorageError(
                    f"cannot write Watchtower state: {type(exc).__name__}"
                ) from exc
            if result == 1:
                return state
            if result == 0:
                current = self.get(state.watch_id)
                if current == state:
                    return current
                raise WatchtowerJournalConflict(
                    "watch id already exists with different payload"
                )
            if result != -1:
                raise WatchtowerJournalStorageError("unexpected Watchtower put result")
        raise WatchtowerJournalConflict("Watchtower metadata changed concurrently")

    def compare_and_swap(
        self,
        watch_id: str,
        *,
        expected_revision: int,
        updated: WatchtowerStateV1,
    ) -> WatchtowerStateV1:
        if updated.watch_id != watch_id:
            raise WatchtowerJournalConflict("watch id mutation is forbidden")
        if updated.revision != expected_revision + 1:
            raise WatchtowerJournalConflict(
                "Watchtower revision must advance by exactly one"
            )
        expected_raw = self._raw_state(watch_id)
        if expected_raw is None:
            raise WatchtowerJournalConflict("Watchtower state is missing")
        current = self._decode_state(watch_id, expected_raw)
        if current.revision != expected_revision:
            raise WatchtowerJournalConflict(
                f"Watchtower revision conflict: {current.revision}"
            )
        new_raw = self._encode_state(updated)
        try:
            result = self._client.command(
                "EVAL",
                _CAS_SCRIPT,
                "1",
                _STATES_KEY,
                watch_id,
                expected_raw,
                new_raw,
            )
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot update Watchtower state: {type(exc).__name__}"
            ) from exc
        if result == 1:
            return updated
        if result == 0:
            raise WatchtowerJournalConflict("Watchtower state changed concurrently")
        raise WatchtowerJournalStorageError("unexpected Watchtower CAS result")

    def integrity_check(self) -> int:
        _, _, expected_count = self._read_meta()
        try:
            raw_count = self._client.command("HLEN", _STATES_KEY)
            rows = self._client.command("HGETALL", _STATES_KEY)
        except Exception as exc:
            raise WatchtowerJournalStorageError(
                f"cannot inspect Watchtower journal: {type(exc).__name__}"
            ) from exc
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as exc:
            raise WatchtowerJournalIntegrityError("Watchtower state count invalid") from exc
        if count != expected_count:
            raise WatchtowerJournalIntegrityError(
                "Watchtower state count does not match authenticated metadata"
            )
        if not isinstance(rows, list) or len(rows) != count * 2:
            raise WatchtowerJournalIntegrityError("Watchtower state rows are invalid")
        for index in range(0, len(rows), 2):
            watch_id = rows[index]
            raw = rows[index + 1]
            if not isinstance(watch_id, str) or not isinstance(raw, str):
                raise WatchtowerJournalIntegrityError("Watchtower state row type invalid")
            self._decode_state(watch_id, raw)
        return count
