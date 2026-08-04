from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import ssl
import time
from typing import Any, Callable
from urllib.parse import quote, urlparse

import httpx


_QSTASH_ORIGIN = "https://qstash.upstash.io"
_MAX_RETRIES = 3


class QStashWatchtowerError(RuntimeError):
    pass


class QStashSignatureError(QStashWatchtowerError):
    pass


class QStashScheduleError(QStashWatchtowerError):
    pass


def _b64url_decode(value: str) -> bytes:
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise QStashSignatureError("invalid QStash signature encoding") from exc


def _b64url_sha256(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class QStashSignatureVerifierV1:
    """Minimal exact HS256 verifier compatible with the official QStash Receiver."""

    def __init__(
        self,
        *,
        current_signing_key: str,
        next_signing_key: str,
        clock_tolerance_seconds: int = 5,
        now_provider: Callable[[], float] = time.time,
    ) -> None:
        current = current_signing_key.strip()
        next_key = next_signing_key.strip()
        if not current or not next_key:
            raise QStashSignatureError("QStash current and next signing keys are required")
        if not 0 <= clock_tolerance_seconds <= 60:
            raise QStashSignatureError("QStash clock tolerance must be between 0 and 60 seconds")
        self._keys = (current.encode("utf-8"), next_key.encode("utf-8"))
        self._clock_tolerance = clock_tolerance_seconds
        self._now = now_provider

    def verify(self, *, signature: str, body: str, url: str) -> None:
        token = signature.strip()
        if not token:
            raise QStashSignatureError("missing Upstash-Signature")
        parts = token.split(".")
        if len(parts) != 3:
            raise QStashSignatureError("invalid QStash JWT structure")
        header_segment, payload_segment, signature_segment = parts
        try:
            header = json.loads(_b64url_decode(header_segment))
            payload = json.loads(_b64url_decode(payload_segment))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise QStashSignatureError("invalid QStash JWT payload") from exc
        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise QStashSignatureError("invalid QStash JWT object")
        if header.get("alg") != "HS256":
            raise QStashSignatureError("unsupported QStash JWT algorithm")

        signed = f"{header_segment}.{payload_segment}".encode("ascii")
        supplied = _b64url_decode(signature_segment)
        if not any(
            hmac.compare_digest(
                supplied,
                hmac.new(key, signed, hashlib.sha256).digest(),
            )
            for key in self._keys
        ):
            raise QStashSignatureError("QStash signature mismatch")

        required = {"iss", "sub", "exp", "nbf", "body"}
        if not required.issubset(payload):
            raise QStashSignatureError("QStash JWT required claims are missing")
        if payload["iss"] != "Upstash":
            raise QStashSignatureError("invalid QStash issuer")
        if payload["sub"] != url:
            raise QStashSignatureError("invalid QStash destination subject")
        try:
            expires_at = float(payload["exp"])
            not_before = float(payload["nbf"])
        except (TypeError, ValueError) as exc:
            raise QStashSignatureError("invalid QStash time claims") from exc
        now = self._now()
        if now > expires_at + self._clock_tolerance:
            raise QStashSignatureError("QStash signature expired")
        if now < not_before - self._clock_tolerance:
            raise QStashSignatureError("QStash signature is not active yet")
        if str(payload["body"]).rstrip("=") != _b64url_sha256(body):
            raise QStashSignatureError("QStash body hash mismatch")


@dataclass(frozen=True)
class QStashScheduleSpecV1:
    schedule_id: str
    cron: str
    destination_url: str
    callback_url: str
    failure_callback_url: str
    retries: int = 3
    timeout: str = "30s"
    body: str = '{"job":"portfolio_watchtower","schema_version":"1.0"}'

    def __post_init__(self) -> None:
        if not self.schedule_id.startswith("omni-cio-watchtower-"):
            raise QStashScheduleError("Watchtower schedule id has invalid namespace")
        if not self.cron.strip() or len(self.cron) > 128:
            raise QStashScheduleError("Watchtower cron is invalid")
        if not 0 <= self.retries <= _MAX_RETRIES:
            raise QStashScheduleError("Watchtower retries exceed bounded policy")
        destinations = (
            self.destination_url,
            self.callback_url,
            self.failure_callback_url,
        )
        parsed = [urlparse(value) for value in destinations]
        if any(item.scheme != "https" or not item.hostname for item in parsed):
            raise QStashScheduleError("Watchtower QStash endpoints must use HTTPS")
        destination_host = parsed[0].hostname
        if any(item.hostname != destination_host for item in parsed[1:]):
            raise QStashScheduleError("Watchtower callbacks must remain on the Gateway host")
        try:
            decoded = json.loads(self.body)
        except json.JSONDecodeError as exc:
            raise QStashScheduleError("Watchtower schedule body must be JSON") from exc
        if decoded != {"job": "portfolio_watchtower", "schema_version": "1.0"}:
            raise QStashScheduleError("Watchtower schedule body is not canonical")


@dataclass(frozen=True)
class QStashScheduleStatusV1:
    schedule_id: str
    cron: str
    destination: str
    method: str
    is_paused: bool
    retries: int | None
    callback: str | None
    failure_callback: str | None
    last_schedule_time_ms: int | None
    next_schedule_time_ms: int | None


class QStashScheduleClientV1:
    """Strict QStash v2 schedule client with no broker or execution authority."""

    def __init__(
        self,
        token: str,
        *,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        client_factory: Callable[..., httpx.Client] = httpx.Client,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        value = token.strip()
        if not value:
            raise QStashScheduleError("QStash token is required")
        self._token = value
        self._timeout = httpx.Timeout(timeout_seconds)
        self._transport = transport
        self._client_factory = client_factory
        self._ssl_context = ssl_context or ssl.create_default_context()

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        content: str | None = None,
        allow_not_found: bool = False,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "timeout": self._timeout,
            "follow_redirects": False,
            "trust_env": False,
            "verify": self._ssl_context,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        request_headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "User-Agent": "omni-cio-watchtower-qstash/1",
        }
        request_headers.update(headers or {})
        try:
            with self._client_factory(**kwargs) as client:
                response = client.request(
                    method,
                    f"{_QSTASH_ORIGIN}{path}",
                    headers=request_headers,
                    content=content,
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPError) as exc:
            raise QStashScheduleError(
                f"QStash transport failure: {type(exc).__name__}"
            ) from exc
        if allow_not_found and response.status_code == 404:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            raise QStashScheduleError(f"QStash HTTP failure: {response.status_code}")
        if not response.content:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise QStashScheduleError("QStash returned non-JSON") from exc

    @staticmethod
    def _status(payload: object) -> QStashScheduleStatusV1:
        if not isinstance(payload, dict):
            raise QStashScheduleError("QStash schedule payload is invalid")
        try:
            return QStashScheduleStatusV1(
                schedule_id=str(payload["scheduleId"]),
                cron=str(payload["cron"]),
                destination=str(payload["destination"]),
                method=str(payload["method"]),
                is_paused=bool(payload["isPaused"]),
                retries=(
                    None if payload.get("retries") is None else int(payload["retries"])
                ),
                callback=(
                    None if payload.get("callback") is None else str(payload["callback"])
                ),
                failure_callback=(
                    None
                    if payload.get("failureCallback") is None
                    else str(payload["failureCallback"])
                ),
                last_schedule_time_ms=(
                    None
                    if payload.get("lastScheduleTime") is None
                    else int(payload["lastScheduleTime"])
                ),
                next_schedule_time_ms=(
                    None
                    if payload.get("nextScheduleTime") is None
                    else int(payload["nextScheduleTime"])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise QStashScheduleError("QStash schedule payload is malformed") from exc

    def get_schedule(self, schedule_id: str) -> QStashScheduleStatusV1 | None:
        payload = self._request(
            "GET",
            f"/v2/schedules/{quote(schedule_id, safe='')}",
            allow_not_found=True,
        )
        return None if payload is None else self._status(payload)

    def list_schedules(self) -> tuple[QStashScheduleStatusV1, ...]:
        payload = self._request("GET", "/v2/schedules")
        if not isinstance(payload, list):
            raise QStashScheduleError("QStash schedule list is invalid")
        return tuple(sorted((self._status(row) for row in payload), key=lambda row: row.schedule_id))

    def ensure_schedule(self, spec: QStashScheduleSpecV1) -> QStashScheduleStatusV1:
        destination = quote(spec.destination_url, safe="")
        payload = self._request(
            "POST",
            f"/v2/schedules/{destination}",
            headers={
                "Content-Type": "application/json",
                "Upstash-Cron": spec.cron,
                "Upstash-Schedule-Id": spec.schedule_id,
                "Upstash-Method": "POST",
                "Upstash-Timeout": spec.timeout,
                "Upstash-Retries": str(spec.retries),
                "Upstash-Callback": spec.callback_url,
                "Upstash-Callback-Method": "POST",
                "Upstash-Callback-Retries": "1",
                "Upstash-Failure-Callback": spec.failure_callback_url,
                "Upstash-Failure-Callback-Method": "POST",
                "Upstash-Failure-Callback-Retries": "1",
                "Upstash-Redact-Fields": "body",
            },
            content=spec.body,
        )
        if not isinstance(payload, dict) or payload.get("scheduleId") != spec.schedule_id:
            raise QStashScheduleError("QStash did not confirm the canonical schedule id")
        status = self.get_schedule(spec.schedule_id)
        if status is None:
            raise QStashScheduleError("QStash schedule disappeared after creation")
        if (
            status.cron != spec.cron
            or status.destination != spec.destination_url
            or status.method.upper() != "POST"
            or status.is_paused
            or status.retries != spec.retries
            or status.callback != spec.callback_url
            or status.failure_callback != spec.failure_callback_url
        ):
            raise QStashScheduleError("QStash schedule does not match canonical configuration")
        return status

    def delete_schedule(self, schedule_id: str) -> None:
        self._request("DELETE", f"/v2/schedules/{quote(schedule_id, safe='')}")
