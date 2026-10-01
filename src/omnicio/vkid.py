"""VK ID OAuth 2.1 + PKCE provider adapter."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


class VKIDError(RuntimeError):
    """Base VK ID provider error."""


class VKIDRejected(VKIDError):
    """VK ID rejected the authorization response or token exchange."""


class VKIDUnavailable(VKIDError):
    """VK ID could not be reached or returned an unusable response."""


@dataclass(frozen=True, slots=True)
class VKIDIdentity:
    user_id: str


@dataclass(frozen=True, slots=True)
class VKIDClient:
    app_id: str
    redirect_uri: str
    timeout_seconds: int = 10
    base_url: str = "https://id.vk.ru"

    def authorization_url(self, *, state: str, code_challenge: str) -> str:
        if not _is_positive_numeric_id(self.app_id):
            raise VKIDRejected("VK ID app id is not configured correctly")
        query = urllib.parse.urlencode(
            {
                "client_id": self.app_id,
                "app_id": self.app_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "s256",
            }
        )
        return f"{self.base_url}/authorize?{query}"

    def exchange_code(
        self,
        *,
        code: str,
        device_id: str,
        code_verifier: str,
        expected_state: str,
    ) -> VKIDIdentity:
        if not _is_positive_numeric_id(self.app_id):
            raise VKIDRejected("VK ID app id is not configured correctly")
        query = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "client_id": self.app_id,
                "code_verifier": code_verifier,
                "state": expected_state,
                "device_id": device_id,
            }
        )
        payload = self._post(
            f"{self.base_url}/oauth2/auth?{query}",
            {"code": code},
        )
        state = str(payload.get("state") or "")
        if state != expected_state:
            raise VKIDRejected("VK ID state mismatch")

        user_id = str(payload.get("user_id") or "").strip()
        if not _is_positive_numeric_id(user_id):
            raise VKIDRejected("VK ID response has no valid user id")
        if not payload.get("access_token"):
            raise VKIDRejected("VK ID response has no access token")

        return VKIDIdentity(user_id=user_id)

    def _post(self, url: str, values: dict[str, str]) -> dict[str, object]:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(values).encode(),
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read().decode()
        except urllib.error.HTTPError as exc:
            if exc.code in {400, 401, 403, 422}:
                raise VKIDRejected(
                    f"VK ID rejected request: HTTP {exc.code}"
                ) from exc
            raise VKIDUnavailable(
                f"VK ID unavailable: HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise VKIDUnavailable(
                f"VK ID unavailable: {type(exc).__name__}"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VKIDUnavailable("VK ID returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise VKIDUnavailable("VK ID returned invalid payload")
        if payload.get("error"):
            raise VKIDRejected("VK ID returned an OAuth error")
        return payload


def _is_positive_numeric_id(value: str) -> bool:
    return value.isdigit() and int(value) > 0
