from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal
import hashlib
import hmac
import json
import ssl
from typing import Any, Callable, cast
from urllib.parse import urlparse

import httpx

from .durable_journal_codec_v1 import (
    COUNTED_STATES,
    JournalIntegrityError,
    JournalStorageError,
    decode_proposal,
    encode_proposal,
)
from .journal_v1 import JournalDailyCapExceeded, JournalStateConflict, MOSCOW
from .models_v1 import ProposalState, RealTradeProposalV1


_SCHEMA_VERSION = "1"
_NAMESPACE = "omni-cio:real:v1"
_META_KEY = f"{_NAMESPACE}:meta"
_PROPOSALS_KEY = f"{_NAMESPACE}:proposals"
_MISSING = "__OMNI_CIO_MISSING__"
_MAX_CAS_ATTEMPTS = 8
_NANO_PER_RUB = Decimal("1000000000")

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

_CAS_PROPOSAL_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current ~= ARGV[2] then
  return 0
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
return 1
""".strip()

_CAS_PROPOSAL_AND_DAILY_SCRIPT = """
local current = redis.call('HGET', KEYS[1], ARGV[1])
if current ~= ARGV[2] then
  return -1
end
local daily = redis.call('GET', KEYS[2])
if ARGV[4] == '__OMNI_CIO_MISSING__' then
  if daily then
    return -2
  end
elseif daily ~= ARGV[4] then
  return -2
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
redis.call('SET', KEYS[2], ARGV[5])
return 1
""".strip()


class UpstashRedisRestClientV1:
    """Tiny strict Upstash Redis REST client used only by the durable journal."""

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
        if not url or not token:
            raise JournalStorageError("Upstash REST URL and token are required")
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not hostname.endswith(".upstash.io")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise JournalStorageError("Upstash REST URL is invalid or not an upstash.io HTTPS endpoint")
        self._url = url
        self._token = token
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client_factory = client_factory
        self._ssl_context = ssl_context or ssl.create_default_context()

    @property
    def rest_url(self) -> str:
        return self._url

    def command(self, *parts: Any) -> Any:
        if not parts:
            raise JournalStorageError("Redis command must not be empty")
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
                        "User-Agent": "omni-cio-real-journal/1",
                    },
                    json=list(parts),
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
            raise JournalStorageError(
                f"Upstash durable journal transport failure: {type(exc).__name__}"
            ) from exc
        if response.status_code != 200:
            raise JournalStorageError(
                f"Upstash durable journal HTTP failure: {response.status_code}"
            )
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise JournalStorageError("Upstash durable journal returned non-JSON") from exc
        if not isinstance(payload, dict):
            raise JournalStorageError("Upstash durable journal response must be an object")
        if payload.get("error") is not None:
            raise JournalStorageError("Upstash durable journal command failed")
        if "result" not in payload:
            raise JournalStorageError("Upstash durable journal response has no result")
        return payload["result"]


class UpstashRealExecutionJournalV1:
    """Durable HMAC-authenticated real-order journal on Upstash Redis.

    The free Render web service can use this backend over outbound HTTPS, so no
    Render persistent disk is required. Proposal rows, journal metadata and
    daily counters are all application-HMAC authenticated. Redis Lua is used
    only for exact compare-and-swap so concurrent confirmations cannot bypass
    the daily hard limit.
    """

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
            raise JournalStorageError("gateway secret is required")
        self._key = hmac.new(
            secret.encode("utf-8"),
            b"omni-cio-real-execution-journal-v1",
            hashlib.sha256,
        ).digest()
        self._client = client or UpstashRedisRestClientV1(rest_url, rest_token)
        self._initialize()

    def _proposal_mac(self, proposal_id: str, revision: int, payload: str) -> str:
        message = f"{proposal_id}\n{revision}\n{payload}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _confirmation_evidence(self, proposal: RealTradeProposalV1) -> str:
        message = (
            f"{proposal.proposal_id}\n{proposal.order_id}\n{proposal.confirmation_phrase}"
        ).encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _meta_mac(self, revision: int, proposal_count: int) -> str:
        message = f"meta\n{_SCHEMA_VERSION}\n{revision}\n{proposal_count}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _daily_mac(self, day: date, revision: int, nano: int) -> str:
        message = f"daily\n{day.isoformat()}\n{revision}\n{nano}".encode("utf-8")
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def _encode_meta(self, revision: int, proposal_count: int) -> str:
        return json.dumps(
            {
                "schema_version": _SCHEMA_VERSION,
                "revision": revision,
                "proposal_count": proposal_count,
                "mac": self._meta_mac(revision, proposal_count),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_meta(self, raw: str) -> tuple[int, int]:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("meta must be an object")
            schema = str(data["schema_version"])
            revision = int(data["revision"])
            proposal_count = int(data["proposal_count"])
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise JournalIntegrityError("invalid Upstash journal metadata") from exc
        if schema != _SCHEMA_VERSION or revision < 0 or proposal_count < 0:
            raise JournalIntegrityError("unsupported or invalid Upstash journal metadata")
        if not hmac.compare_digest(mac, self._meta_mac(revision, proposal_count)):
            raise JournalIntegrityError("Upstash journal metadata integrity check failed")
        return revision, proposal_count

    def _encode_envelope(
        self, proposal: RealTradeProposalV1, revision: int
    ) -> str:
        payload = encode_proposal(proposal)
        return json.dumps(
            {
                "revision": revision,
                "payload_json": payload,
                "row_mac": self._proposal_mac(proposal.proposal_id, revision, payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_envelope(
        self, proposal_id: str, raw: str
    ) -> tuple[int, RealTradeProposalV1]:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("proposal envelope must be an object")
            revision = int(data["revision"])
            payload = str(data["payload_json"])
            row_mac = str(data["row_mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise JournalIntegrityError("invalid Upstash proposal envelope") from exc
        if revision < 0 or not hmac.compare_digest(
            row_mac, self._proposal_mac(proposal_id, revision, payload)
        ):
            raise JournalIntegrityError("Upstash proposal integrity check failed")
        proposal = decode_proposal(payload)
        if proposal.proposal_id != proposal_id:
            raise JournalIntegrityError("Upstash proposal id mismatch")
        return revision, proposal

    def _encode_daily(self, day: date, revision: int, nano: int) -> str:
        if revision < 0 or nano < 0:
            raise JournalIntegrityError("invalid daily journal counter")
        return json.dumps(
            {
                "day": day.isoformat(),
                "revision": revision,
                "nano": str(nano),
                "mac": self._daily_mac(day, revision, nano),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _decode_daily(self, day: date, raw: str) -> tuple[int, int]:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError("daily counter must be an object")
            stored_day = date.fromisoformat(str(data["day"]))
            revision = int(data["revision"])
            nano = int(str(data["nano"]))
            mac = str(data["mac"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise JournalIntegrityError("invalid Upstash daily counter") from exc
        if stored_day != day or revision < 0 or nano < 0:
            raise JournalIntegrityError("invalid Upstash daily counter identity")
        if not hmac.compare_digest(mac, self._daily_mac(day, revision, nano)):
            raise JournalIntegrityError("Upstash daily counter integrity check failed")
        return revision, nano

    def _initialize(self) -> None:
        raw = self._client.command("GET", _META_KEY)
        if raw is None:
            candidate = self._encode_meta(0, 0)
            self._client.command("SET", _META_KEY, candidate, "NX")
            raw = self._client.command("GET", _META_KEY)
        if not isinstance(raw, str):
            raise JournalStorageError("Upstash journal metadata is unavailable")
        self._decode_meta(raw)

    def _read_meta(self) -> tuple[str, int, int]:
        raw = self._client.command("GET", _META_KEY)
        if not isinstance(raw, str):
            raise JournalIntegrityError("Upstash journal metadata is missing")
        revision, count = self._decode_meta(raw)
        return raw, revision, count

    def _proposal_raw(self, proposal_id: str) -> str:
        raw = self._client.command("HGET", _PROPOSALS_KEY, proposal_id)
        if raw is None:
            raise KeyError("real-trading proposal not found")
        if not isinstance(raw, str):
            raise JournalIntegrityError("Upstash proposal value is invalid")
        return raw

    def _daily_key(self, day: date) -> str:
        return f"{_NAMESPACE}:daily:{day.isoformat()}"

    def _read_daily(self, day: date) -> tuple[str | None, int, int]:
        raw = self._client.command("GET", self._daily_key(day))
        if raw is None:
            return None, -1, 0
        if not isinstance(raw, str):
            raise JournalIntegrityError("Upstash daily counter value is invalid")
        revision, nano = self._decode_daily(day, raw)
        return raw, revision, nano

    def _to_nano(self, value: Decimal) -> int:
        scaled = value * _NANO_PER_RUB
        integral = scaled.to_integral_value()
        if not value.is_finite() or scaled != integral or integral < 0:
            raise JournalIntegrityError("journal money value exceeds nanoruble precision")
        return int(integral)

    def _from_nano(self, nano: int) -> Decimal:
        if nano < 0:
            raise JournalIntegrityError("negative daily counter")
        return Decimal(nano) / _NANO_PER_RUB

    def put(self, proposal: RealTradeProposalV1) -> None:
        envelope = self._encode_envelope(proposal, 0)
        for _ in range(_MAX_CAS_ATTEMPTS):
            meta_raw, meta_revision, count = self._read_meta()
            new_meta = self._encode_meta(meta_revision + 1, count + 1)
            result = self._client.command(
                "EVAL",
                _PUT_SCRIPT,
                "2",
                _META_KEY,
                _PROPOSALS_KEY,
                meta_raw,
                new_meta,
                proposal.proposal_id,
                envelope,
            )
            if result == 1:
                return
            if result == 0:
                raise RuntimeError("duplicate proposal id")
            if result != -1:
                raise JournalStorageError("unexpected Upstash put result")
        raise JournalStateConflict("journal metadata changed concurrently")

    def get(self, proposal_id: str) -> RealTradeProposalV1:
        raw = self._proposal_raw(proposal_id)
        return self._decode_envelope(proposal_id, raw)[1]

    def _counted_day(self, proposal: RealTradeProposalV1) -> date | None:
        if proposal.state not in COUNTED_STATES or proposal.submitted_at is None:
            return None
        return proposal.submitted_at.astimezone(MOSCOW).date()

    def _cas_proposal_only(
        self,
        proposal_id: str,
        expected_raw: str,
        new_raw: str,
    ) -> bool:
        result = self._client.command(
            "EVAL",
            _CAS_PROPOSAL_SCRIPT,
            "1",
            _PROPOSALS_KEY,
            proposal_id,
            expected_raw,
            new_raw,
        )
        if result not in {0, 1}:
            raise JournalStorageError("unexpected Upstash proposal CAS result")
        return result == 1

    def _cas_proposal_and_daily(
        self,
        *,
        proposal_id: str,
        expected_proposal_raw: str,
        new_proposal_raw: str,
        day: date,
        expected_daily_raw: str | None,
        new_daily_raw: str,
    ) -> int:
        result = self._client.command(
            "EVAL",
            _CAS_PROPOSAL_AND_DAILY_SCRIPT,
            "2",
            _PROPOSALS_KEY,
            self._daily_key(day),
            proposal_id,
            expected_proposal_raw,
            new_proposal_raw,
            _MISSING if expected_daily_raw is None else expected_daily_raw,
            new_daily_raw,
        )
        if result not in {-2, -1, 1}:
            raise JournalStorageError("unexpected Upstash journal CAS result")
        return int(result)

    def transition(
        self,
        proposal_id: str,
        *,
        allowed_from: frozenset[str],
        state: ProposalState,
        **changes: Any,
    ) -> RealTradeProposalV1:
        for _ in range(_MAX_CAS_ATTEMPTS):
            current_raw = self._proposal_raw(proposal_id)
            revision, current = self._decode_envelope(proposal_id, current_raw)
            if current.state not in allowed_from:
                raise JournalStateConflict(f"proposal state conflict: {current.state}")
            updated = replace(current, state=state, **changes)
            new_raw = self._encode_envelope(updated, revision + 1)
            old_day = self._counted_day(current)
            new_day = self._counted_day(updated)
            if old_day == new_day:
                if self._cas_proposal_only(proposal_id, current_raw, new_raw):
                    return updated
                continue
            if old_day is not None and new_day is not None:
                raise JournalIntegrityError("counted proposal submission day cannot change")
            day = old_day or new_day
            assert day is not None
            daily_raw, daily_revision, daily_nano = self._read_daily(day)
            amount_nano = self._to_nano(current.preview_total_rub)
            if old_day is not None:
                new_nano = daily_nano - amount_nano
                if new_nano < 0:
                    raise JournalIntegrityError("daily counter underflow")
            else:
                new_nano = daily_nano + amount_nano
            new_daily = self._encode_daily(day, daily_revision + 1, new_nano)
            result = self._cas_proposal_and_daily(
                proposal_id=proposal_id,
                expected_proposal_raw=current_raw,
                new_proposal_raw=new_raw,
                day=day,
                expected_daily_raw=daily_raw,
                new_daily_raw=new_daily,
            )
            if result == 1:
                return updated
        raise JournalStateConflict("proposal or daily counter changed concurrently")

    def submitted_notional_for_moscow_date(self, day: date) -> Decimal:
        _, _, nano = self._read_daily(day)
        return self._from_nano(nano)

    def reserve_submission(
        self,
        proposal_id: str,
        *,
        submitted_at: datetime,
        max_daily_rub: Decimal,
        confirmation_evidence_hash: str | None = None,
    ) -> RealTradeProposalV1:
        if submitted_at.tzinfo is None:
            raise ValueError("journal timestamps must be timezone-aware")
        day = submitted_at.astimezone(MOSCOW).date()
        max_nano = self._to_nano(max_daily_rub)
        for _ in range(_MAX_CAS_ATTEMPTS):
            current_raw = self._proposal_raw(proposal_id)
            revision, current = self._decode_envelope(proposal_id, current_raw)
            if current.state != "prepared":
                raise JournalStateConflict(f"proposal state conflict: {current.state}")
            daily_raw, daily_revision, daily_nano = self._read_daily(day)
            amount_nano = self._to_nano(current.preview_total_rub)
            if daily_nano + amount_nano > max_nano:
                raise JournalDailyCapExceeded("daily submission cap exceeded")
            evidence = confirmation_evidence_hash or self._confirmation_evidence(current)
            updated = replace(
                current,
                state=cast(ProposalState, "submitting"),
                submitted_at=submitted_at,
                confirmation_evidence_hash=evidence,
            )
            new_proposal_raw = self._encode_envelope(updated, revision + 1)
            new_daily_raw = self._encode_daily(
                day, daily_revision + 1, daily_nano + amount_nano
            )
            result = self._cas_proposal_and_daily(
                proposal_id=proposal_id,
                expected_proposal_raw=current_raw,
                new_proposal_raw=new_proposal_raw,
                day=day,
                expected_daily_raw=daily_raw,
                new_daily_raw=new_daily_raw,
            )
            if result == 1:
                return updated
        raise JournalStateConflict("proposal or daily counter changed concurrently")

    def integrity_check(self) -> int:
        _, _, proposal_count = self._read_meta()
        raw_len = self._client.command("HLEN", _PROPOSALS_KEY)
        try:
            hash_len = int(raw_len)
        except (TypeError, ValueError) as exc:
            raise JournalIntegrityError("Upstash proposal count is invalid") from exc
        if hash_len != proposal_count:
            raise JournalIntegrityError("Upstash proposal count integrity check failed")
        raw_rows = self._client.command("HGETALL", _PROPOSALS_KEY)
        if raw_rows is None:
            raw_rows = []
        if not isinstance(raw_rows, list) or len(raw_rows) % 2 != 0:
            raise JournalIntegrityError("Upstash proposal hash response is invalid")
        if len(raw_rows) // 2 != proposal_count:
            raise JournalIntegrityError("Upstash proposal hash length mismatch")
        expected_daily: dict[date, int] = {}
        for index in range(0, len(raw_rows), 2):
            proposal_id = raw_rows[index]
            envelope = raw_rows[index + 1]
            if not isinstance(proposal_id, str) or not isinstance(envelope, str):
                raise JournalIntegrityError("Upstash proposal hash contains invalid values")
            proposal = self._decode_envelope(proposal_id, envelope)[1]
            day = self._counted_day(proposal)
            if day is not None:
                expected_daily[day] = expected_daily.get(day, 0) + self._to_nano(
                    proposal.preview_total_rub
                )
        for day, expected_nano in expected_daily.items():
            raw, _, actual_nano = self._read_daily(day)
            if raw is None or actual_nano != expected_nano:
                raise JournalIntegrityError("Upstash daily counter integrity check failed")
        return proposal_count
