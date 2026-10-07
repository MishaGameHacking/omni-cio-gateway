"""T-ID partner Authorization Code adapter; never a T-Invest credential."""

from __future__ import annotations

import base64
import http.client
import json
from contextlib import closing
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

_HOST = "id.tbank.ru"
_MAX_RESPONSE_BYTES = 65536


class TIDRejected(RuntimeError):
    """T-ID rejected the code or did not verify a stable identity."""


class TIDUnavailable(RuntimeError):
    """T-ID could not complete a bounded, authenticated request."""


@dataclass(frozen=True, slots=True)
class TIDIdentity:
    subject: str


@dataclass(frozen=True, slots=True)
class TIDClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    pkce_enabled: bool = True
    timeout_seconds: int = 10

    def _require_configuration(self) -> None:
        if not self.client_id or not self.client_secret:
            raise TIDUnavailable("tid_not_configured")
        if self.redirect_uri != "https://omnicio.ru/api/auth/tid/callback":
            raise TIDUnavailable("tid_callback_not_registered")

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        self._require_configuration()
        values = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "state": state,
            "scope": "openid profile phone",
        }
        if self.pkce_enabled:
            values.update(code_challenge=code_challenge, code_challenge_method="S256")
        return f"https://{_HOST}/auth/authorize?{urlencode(values)}"

    def exchange_code(self, *, code: str, code_verifier: str) -> TIDIdentity:
        self._require_configuration()
        if not code or len(code) > 4096:
            raise TIDRejected("tid_code_invalid")
        basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode("ascii")
        values = {
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        if self.pkce_enabled:
            values["code_verifier"] = code_verifier
        payload = self._post("/auth/token", values, authorization=f"Basic {basic}")
        access_token = payload.get("access_token")
        if (not isinstance(access_token, str) or not access_token
                or len(access_token) > 16384
                or any(ord(char) < 33 or ord(char) > 126 for char in access_token)):
            raise TIDRejected("tid_access_token_invalid")
        # Identity authority is the authenticated userinfo response. An unverified
        # decoded JWT, callback subject, email or name is never accepted instead.
        profile = self._post(
            "/userinfo/userinfo",
            {"client_id": self.client_id, "client_secret": self.client_secret},
            authorization=f"Bearer {access_token}",
        )
        subject = profile.get("sub")
        if (not isinstance(subject, str) or not 1 <= len(subject) <= 128
                or any(ord(char) < 33 or ord(char) > 126 for char in subject)):
            raise TIDRejected("tid_subject_invalid")
        return TIDIdentity(subject=subject)

    def _post(
        self, path: str, values: dict[str, str], *, authorization: str,
    ) -> dict[str, Any]:
        try:
            with closing(http.client.HTTPSConnection(
                _HOST, timeout=self.timeout_seconds,
            )) as connection:
                connection.request(
                    "POST", path, body=urlencode(values).encode(),
                    headers={
                        "Authorization": authorization,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                )
                response = connection.getresponse()
                # HTTPSConnection does not follow redirects or forward credentials.
                if response.status in {400, 401, 403, 422}:
                    raise TIDRejected("tid_authorization_rejected")
                if response.status != 200:
                    raise TIDUnavailable("tid_provider_unavailable")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise TIDUnavailable("tid_response_too_large")
                payload = json.loads(raw)
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise TIDUnavailable("tid_provider_unavailable") from exc
        if not isinstance(payload, dict):
            raise TIDUnavailable("tid_response_invalid")
        if payload.get("error"):
            raise TIDRejected("tid_authorization_rejected")
        return payload
