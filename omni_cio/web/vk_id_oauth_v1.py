from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from omni_cio.web.identity_v1 import IdentityProviderV1, VerifiedExternalIdentityV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionRegistryV1,
    ConsumedAuthorizationTransactionV1,
    ProviderAuthorizationError,
)

VK_ID_ORIGIN = "https://id.vk.ru"
VK_ID_AUTHORIZATION_ENDPOINT = f"{VK_ID_ORIGIN}/authorize"
VK_ID_TOKEN_ENDPOINT = f"{VK_ID_ORIGIN}/oauth2/auth"

_MAX_PROVIDER_RESPONSE_BYTES = 32_768
_MAX_ACCESS_TOKEN_CHARS = 8_192
_MAX_USER_ID = (1 << 63) - 1
_CODE_PATTERN = re.compile(r"^[\x21-\x7e]{1,2048}$")
_DEVICE_ID_PATTERN = re.compile(r"^[\x21-\x7e]{1,512}$")


class VkIdOauthError(ProviderAuthorizationError):
    """Fail-closed VK ID OAuth 2.1 transport or validation error."""


@dataclass(frozen=True, slots=True)
class VkIdOauthConfigV1:
    client_id: str
    redirect_uri: str
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if (
            not isinstance(self.client_id, str)
            or not self.client_id.isascii()
            or not self.client_id.isdigit()
            or not 1 <= len(self.client_id) <= 32
        ):
            raise ValueError("VK_ID_CLIENT_ID_INVALID")
        _validate_redirect_uri(self.redirect_uri)
        if not 0.5 <= self.timeout_seconds <= 15.0:
            raise ValueError("VK_ID_TIMEOUT_INVALID")


def _validate_redirect_uri(value: str) -> None:
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("VK_ID_REDIRECT_URI_INVALID")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("VK_ID_REDIRECT_URI_INVALID") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("VK_ID_REDIRECT_URI_INVALID")


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").partition(";")[0].strip().lower()


def _unique_json_object(payload: bytes) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
        value = json.loads(decoded, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, ValueError):
        raise VkIdOauthError("VK_ID_PROVIDER_JSON_INVALID") from None
    if not isinstance(value, dict):
        raise VkIdOauthError("VK_ID_PROVIDER_JSON_INVALID")
    return value


def _bounded_json_response(
    client: httpx.Client,
    *,
    url: str,
    timeout_seconds: float,
    data: dict[str, str],
) -> dict[str, Any]:
    try:
        with client.stream(
            "POST",
            url,
            data=data,
            timeout=timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        ) as response:
            if (
                response.status_code != 200
                or _content_type(response) != "application/json"
            ):
                raise VkIdOauthError("VK_ID_PROVIDER_RESPONSE_INVALID")
            declared = response.headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > _MAX_PROVIDER_RESPONSE_BYTES:
                        raise VkIdOauthError("VK_ID_PROVIDER_RESPONSE_TOO_LARGE")
                except ValueError:
                    pass
            payload = bytearray()
            for chunk in response.iter_bytes():
                if len(payload) + len(chunk) > _MAX_PROVIDER_RESPONSE_BYTES:
                    raise VkIdOauthError("VK_ID_PROVIDER_RESPONSE_TOO_LARGE")
                payload.extend(chunk)
    except VkIdOauthError:
        raise
    except httpx.HTTPError:
        raise VkIdOauthError("VK_ID_NETWORK_ERROR") from None
    return _unique_json_object(bytes(payload))


def _valid_access_token(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= _MAX_ACCESS_TOKEN_CHARS
        and value.isascii()
        and all(0x21 <= ord(char) <= 0x7E for char in value)
    )


class VkIdOauthRuntimeV1:
    """Dormant VK ID OAuth 2.1 Authorization Code + PKCE adapter."""

    def __init__(
        self,
        *,
        config: VkIdOauthConfigV1,
        transactions: AuthorizationTransactionRegistryV1,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._transactions = transactions
        self._client = client

    @property
    def provider(self) -> IdentityProviderV1:
        return IdentityProviderV1.VK_ID

    def start(self, *, now: datetime) -> str:
        transaction = self._transactions.begin(
            provider=self.provider,
            redirect_uri=self._config.redirect_uri,
            now=now,
        )
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "app_id": self._config.client_id,
                "redirect_uri": transaction.redirect_uri,
                "response_type": "code",
                "state": transaction.state,
                "code_challenge": transaction.code_challenge,
                "code_challenge_method": "s256",
                "prompt": "",
            }
        )
        return f"{VK_ID_AUTHORIZATION_ENDPOINT}?{query}"

    def complete(
        self,
        *,
        state: str,
        code: str,
        now: datetime,
        device_id: str | None = None,
    ) -> VerifiedExternalIdentityV1:
        if not isinstance(code, str) or _CODE_PATTERN.fullmatch(code) is None:
            raise VkIdOauthError("VK_ID_CODE_INVALID")
        if device_id is None or _DEVICE_ID_PATTERN.fullmatch(device_id) is None:
            raise VkIdOauthError("VK_ID_DEVICE_ID_INVALID")
        transaction = self._transactions.consume(
            provider=self.provider,
            state=state,
            now=now,
        )
        if self._client is not None:
            return self._complete_with_client(
                transaction=transaction,
                expected_state=state,
                code=code,
                device_id=device_id,
                client=self._client,
            )
        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds,
                verify=True,
                follow_redirects=False,
            ) as client:
                return self._complete_with_client(
                    transaction=transaction,
                    expected_state=state,
                    code=code,
                    device_id=device_id,
                    client=client,
                )
        except VkIdOauthError:
            raise
        except httpx.HTTPError:
            raise VkIdOauthError("VK_ID_NETWORK_ERROR") from None

    def _complete_with_client(
        self,
        *,
        transaction: ConsumedAuthorizationTransactionV1,
        expected_state: str,
        code: str,
        device_id: str,
        client: httpx.Client,
    ) -> VerifiedExternalIdentityV1:
        query = urlencode(
            {
                "grant_type": "authorization_code",
                "redirect_uri": transaction.redirect_uri,
                "client_id": self._config.client_id,
                "code_verifier": transaction.code_verifier,
                "state": expected_state,
                "device_id": device_id,
            }
        )
        payload = _bounded_json_response(
            client,
            url=f"{VK_ID_TOKEN_ENDPOINT}?{query}",
            timeout_seconds=self._config.timeout_seconds,
            data={"code": code},
        )
        if "error" in payload:
            payload.clear()
            raise VkIdOauthError("VK_ID_PROVIDER_RESPONSE_INVALID")

        response_state = payload.get("state")
        user_id = payload.get("user_id")
        access_token = payload.get("access_token")
        valid_state = (
            isinstance(response_state, str) and response_state == expected_state
        )
        valid_user_id = (
            isinstance(user_id, int)
            and not isinstance(user_id, bool)
            and 1 <= user_id <= _MAX_USER_ID
        )
        valid_access_token = _valid_access_token(access_token)
        subject = str(user_id) if valid_user_id else ""
        payload.clear()

        if not valid_state:
            raise VkIdOauthError("VK_ID_STATE_MISMATCH")
        if not valid_access_token or not valid_user_id:
            raise VkIdOauthError("VK_ID_TOKEN_RESPONSE_INVALID")
        return VerifiedExternalIdentityV1(
            provider=IdentityProviderV1.VK_ID,
            subject=subject,
        )
