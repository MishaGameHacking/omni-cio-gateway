from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import hashlib
import re
from threading import BoundedSemaphore, RLock
import time

from omni_cio.web.identity_v1 import IdentityProviderV1


_SESSION_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,512}$")


@dataclass(frozen=True, slots=True)
class RequestRatePolicyV1:
    window_seconds: int = 60
    global_api_requests: int = 5000
    health_requests: int = 120
    anonymous_requests: int = 300
    authenticated_session_requests: int = 600
    provider_starts: int = 60
    provider_callbacks: int = 120
    outbound_provider_concurrency: int = 8
    max_session_keys: int = 4096
    retry_after_seconds: int = 1

    def __post_init__(self) -> None:
        values = (
            self.window_seconds,
            self.global_api_requests,
            self.health_requests,
            self.anonymous_requests,
            self.authenticated_session_requests,
            self.provider_starts,
            self.provider_callbacks,
            self.outbound_provider_concurrency,
            self.max_session_keys,
            self.retry_after_seconds,
        )
        if any(value <= 0 for value in values):
            raise ValueError("REQUEST_RATE_POLICY_INVALID")
        if self.window_seconds > 3600 or self.retry_after_seconds > self.window_seconds:
            raise ValueError("REQUEST_RATE_POLICY_INVALID")
        if self.outbound_provider_concurrency > 256 or self.max_session_keys > 65536:
            raise ValueError("REQUEST_RATE_POLICY_INVALID")


class BoundedFixedWindowLimiterV1:
    """Thread-safe fixed-window limiter with bounded attacker-controlled keys."""

    def __init__(self, *, window_seconds: int, max_keys: int) -> None:
        if window_seconds <= 0 or max_keys <= 0:
            raise ValueError("REQUEST_RATE_LIMIT_INVALID")
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = RLock()

    def admit(
        self,
        key: str,
        *,
        limit: int,
        now_monotonic: float | None = None,
    ) -> bool:
        if not key or limit <= 0:
            raise ValueError("REQUEST_RATE_LIMIT_INVALID")
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        cutoff = now - float(self._window_seconds)
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= self._max_keys:
                    self._purge_all(cutoff)
                if len(self._events) >= self._max_keys:
                    return False
                events = deque()
                self._events[key] = events
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def _purge_all(self, cutoff: float) -> None:
        for key, events in tuple(self._events.items()):
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                self._events.pop(key, None)


class HostedRequestAbuseControlV1:
    def __init__(self, policy: RequestRatePolicyV1 | None = None) -> None:
        self.policy = policy or RequestRatePolicyV1()
        self._limiter = BoundedFixedWindowLimiterV1(
            window_seconds=self.policy.window_seconds,
            max_keys=self.policy.max_session_keys + 3,
        )

    def admit_health(self, *, now_monotonic: float | None = None) -> bool:
        return self._limiter.admit(
            "health",
            limit=self.policy.health_requests,
            now_monotonic=now_monotonic,
        )

    def admit(
        self,
        *,
        session_token: str | None,
        now_monotonic: float | None = None,
    ) -> bool:
        if not self._limiter.admit(
            "global-api",
            limit=self.policy.global_api_requests,
            now_monotonic=now_monotonic,
        ):
            return False

        if session_token and _SESSION_TOKEN_RE.fullmatch(session_token):
            digest = hashlib.sha256(session_token.encode("ascii")).hexdigest()
            key = "session:" + digest
            limit = self.policy.authenticated_session_requests
        else:
            key = "anonymous"
            limit = self.policy.anonymous_requests
        return self._limiter.admit(
            key,
            limit=limit,
            now_monotonic=now_monotonic,
        )


class ProviderAuthAbuseControlV1:
    def __init__(self, policy: RequestRatePolicyV1 | None = None) -> None:
        self.policy = policy or RequestRatePolicyV1()
        self._limiter = BoundedFixedWindowLimiterV1(
            window_seconds=self.policy.window_seconds,
            max_keys=8,
        )
        self._outbound = BoundedSemaphore(self.policy.outbound_provider_concurrency)

    def admit_start(
        self,
        provider: IdentityProviderV1,
        *,
        now_monotonic: float | None = None,
    ) -> bool:
        return self._limiter.admit(
            "start:" + provider.value,
            limit=self.policy.provider_starts,
            now_monotonic=now_monotonic,
        )

    def admit_callback(
        self,
        provider: IdentityProviderV1,
        *,
        now_monotonic: float | None = None,
    ) -> bool:
        return self._limiter.admit(
            "callback:" + provider.value,
            limit=self.policy.provider_callbacks,
            now_monotonic=now_monotonic,
        )

    def acquire_outbound(self) -> bool:
        return self._outbound.acquire(blocking=False)

    def release_outbound(self) -> None:
        self._outbound.release()
