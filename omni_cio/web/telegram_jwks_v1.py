from __future__ import annotations

from datetime import datetime, timedelta
from threading import Condition, RLock

import httpx

from omni_cio.web.telegram_oidc_v1 import (
    TelegramIdTokenVerifierV1,
    TelegramOidcConfigV1,
    TelegramOidcError,
    _RsaPublicKeyV1,
    _bounded_jwks_response,
    _parse_jwks,
)


_JWKS_REFRESH_FAILURE_COOLDOWN = timedelta(seconds=5)
_JWKS_UNKNOWN_KID_REFRESH_COOLDOWN = timedelta(seconds=10)


class TelegramJwksSingleFlightVerifierV1(TelegramIdTokenVerifierV1):
    """Telegram ID-token verifier with bounded single-flight JWKS refresh.

    Provider network I/O is always performed outside the shared refresh lock.
    One caller refreshes while concurrent callers wait for at most the configured
    provider timeout. Failed refreshes and unknown-kid rotation probes are
    cooldown-bounded so an outage or attacker-controlled random ``kid`` values
    cannot amplify into an unbounded provider request storm.
    """

    def __init__(self, config: TelegramOidcConfigV1) -> None:
        super().__init__(config)
        self._config = config
        self._refresh_lock = RLock()
        self._refresh_condition = Condition(self._refresh_lock)
        self._refreshing = False
        self._refresh_failed_until: datetime | None = None
        self._unknown_kid_refresh_after: datetime | None = None

    def _fetch_keys(self, client: httpx.Client) -> dict[str, _RsaPublicKeyV1]:
        payload = _bounded_jwks_response(
            client,
            timeout_seconds=self._config.timeout_seconds,
        )
        return _parse_jwks(payload)

    def _fresh_cached_key(
        self,
        kid: str,
        *,
        now: datetime,
    ) -> _RsaPublicKeyV1 | None:
        if self._keys_expires_at is None or now >= self._keys_expires_at:
            return None
        key = self._keys.get(kid)
        if key is not None:
            return key
        if (
            self._unknown_kid_refresh_after is not None
            and now < self._unknown_kid_refresh_after
        ):
            raise TelegramOidcError("TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN")
        return None

    def _claim_refresh_or_wait(
        self,
        kid: str,
        *,
        now: datetime,
        already_waited: bool,
    ) -> tuple[_RsaPublicKeyV1 | None, bool, bool]:
        with self._refresh_condition:
            key = self._fresh_cached_key(kid, now=now)
            if key is not None:
                return key, already_waited, False
            if (
                self._refresh_failed_until is not None
                and now < self._refresh_failed_until
            ):
                raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_BACKOFF")
            if not self._refreshing:
                self._refreshing = True
                return None, already_waited, True
            if already_waited:
                raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_TIMEOUT")
            notified = self._refresh_condition.wait(
                timeout=self._config.timeout_seconds
            )
        if not notified:
            raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_TIMEOUT")
        return None, True, False

    def _mark_refresh_failure(self, *, now: datetime) -> None:
        with self._refresh_condition:
            self._refreshing = False
            self._refresh_failed_until = now + _JWKS_REFRESH_FAILURE_COOLDOWN
            self._refresh_condition.notify_all()

    def _refresh_keys(
        self,
        client: httpx.Client,
        *,
        now: datetime,
    ) -> dict[str, _RsaPublicKeyV1]:
        try:
            return self._fetch_keys(client)
        except TelegramOidcError:
            self._mark_refresh_failure(now=now)
            raise
        except Exception:
            self._mark_refresh_failure(now=now)
            raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_FAILED") from None

    def _publish_refreshed_keys(
        self,
        kid: str,
        refreshed: dict[str, _RsaPublicKeyV1],
        *,
        now: datetime,
    ) -> _RsaPublicKeyV1:
        with self._refresh_condition:
            self._keys = refreshed
            self._keys_expires_at = now + self._config.jwks_cache_lifetime
            self._refresh_failed_until = None
            self._refreshing = False
            key = self._keys.get(kid)
            self._unknown_kid_refresh_after = (
                None if key is not None else now + _JWKS_UNKNOWN_KID_REFRESH_COOLDOWN
            )
            self._refresh_condition.notify_all()
        if key is None:
            raise TelegramOidcError("TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN")
        return key

    def _key_for(
        self,
        kid: str,
        *,
        now: datetime,
        client: httpx.Client,
    ) -> _RsaPublicKeyV1:
        waited = False
        while True:
            key, waited, refresh_claimed = self._claim_refresh_or_wait(
                kid,
                now=now,
                already_waited=waited,
            )
            if key is not None:
                return key
            if refresh_claimed:
                break

        refreshed = self._refresh_keys(client, now=now)
        return self._publish_refreshed_keys(kid, refreshed, now=now)
