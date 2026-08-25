from __future__ import annotations

from datetime import datetime, timedelta
from threading import Condition, RLock

import httpx

from omni_cio.web.telegram_oidc_v1 import (
    TELEGRAM_OIDC_JWKS_ENDPOINT,
    TelegramIdTokenVerifierV1,
    TelegramOidcConfigV1,
    TelegramOidcError,
    _MAX_JWKS_RESPONSE_BYTES,
    _RsaPublicKeyV1,
    _bounded_json_response,
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
        payload = _bounded_json_response(
            client,
            method="GET",
            url=TELEGRAM_OIDC_JWKS_ENDPOINT,
            timeout_seconds=self._config.timeout_seconds,
            max_response_bytes=_MAX_JWKS_RESPONSE_BYTES,
        )
        return _parse_jwks(payload)

    def _key_for(
        self,
        kid: str,
        *,
        now: datetime,
        client: httpx.Client,
    ) -> _RsaPublicKeyV1:
        waited = False
        while True:
            with self._refresh_condition:
                cache_fresh = (
                    self._keys_expires_at is not None
                    and now < self._keys_expires_at
                )
                if cache_fresh:
                    key = self._keys.get(kid)
                    if key is not None:
                        return key
                    if (
                        self._unknown_kid_refresh_after is not None
                        and now < self._unknown_kid_refresh_after
                    ):
                        raise TelegramOidcError(
                            "TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN"
                        )

                if (
                    self._refresh_failed_until is not None
                    and now < self._refresh_failed_until
                ):
                    raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_BACKOFF")

                if not self._refreshing:
                    self._refreshing = True
                    break

                if waited:
                    raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_TIMEOUT")
                notified = self._refresh_condition.wait(
                    timeout=self._config.timeout_seconds
                )
                waited = True
                if not notified:
                    raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_TIMEOUT")

        try:
            refreshed = self._fetch_keys(client)
        except TelegramOidcError:
            with self._refresh_condition:
                self._refreshing = False
                self._refresh_failed_until = now + _JWKS_REFRESH_FAILURE_COOLDOWN
                self._refresh_condition.notify_all()
            raise
        except Exception:
            with self._refresh_condition:
                self._refreshing = False
                self._refresh_failed_until = now + _JWKS_REFRESH_FAILURE_COOLDOWN
                self._refresh_condition.notify_all()
            raise TelegramOidcError("TELEGRAM_OIDC_JWKS_REFRESH_FAILED") from None

        with self._refresh_condition:
            self._keys = refreshed
            self._keys_expires_at = now + self._config.jwks_cache_lifetime
            self._refresh_failed_until = None
            self._refreshing = False
            key = self._keys.get(kid)
            if key is None:
                self._unknown_kid_refresh_after = (
                    now + _JWKS_UNKNOWN_KID_REFRESH_COOLDOWN
                )
            else:
                self._unknown_kid_refresh_after = None
            self._refresh_condition.notify_all()

        if key is None:
            raise TelegramOidcError("TELEGRAM_OIDC_SIGNING_KEY_UNKNOWN")
        return key
