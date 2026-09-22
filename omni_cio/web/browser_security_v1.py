from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import re

from omni_cio.web.identity_v1 import IdentityProviderV1


BROWSER_SESSION_COOKIE = "__Host-omni_v10_session"
BROWSER_CSRF_COOKIE = "__Host-omni_v10_csrf"
BROWSER_CSRF_HEADER = "X-Omni-CSRF"
_COOKIE_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}$")
_SESSION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,512}$")
_CSRF_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PROOF_COOKIES = {
    IdentityProviderV1.TELEGRAM: "__Host-omni_v10_oauth_telegram",
    IdentityProviderV1.VK_ID: "__Host-omni_v10_oauth_vk_id",
}


@dataclass(frozen=True, slots=True)
class BrowserCookiePolicyV1:
    """Production BFF cookie and session-bound CSRF policy."""

    csrf_binding_key: bytes = field(repr=False)
    session_cookie: str = BROWSER_SESSION_COOKIE
    csrf_cookie: str = BROWSER_CSRF_COOKIE
    secure: bool = True
    session_max_age_seconds: int = 24 * 60 * 60
    allowed_providers: tuple[IdentityProviderV1, ...] = (
        IdentityProviderV1.TELEGRAM,
        IdentityProviderV1.VK_ID,
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.csrf_binding_key, bytes)
            or len(self.csrf_binding_key) < 32
        ):
            raise ValueError("BROWSER_CSRF_BINDING_KEY_INVALID")
        if len(self.allowed_providers) != len(set(self.allowed_providers)):
            raise ValueError("BROWSER_PROVIDER_DUPLICATE")
        if any(
            provider not in _PROOF_COOKIES for provider in self.allowed_providers
        ):
            raise ValueError("BROWSER_PROVIDER_INVALID")
        proof_cookie_names = tuple(
            _PROOF_COOKIES[provider] for provider in self.allowed_providers
        )
        for name in (self.session_cookie, self.csrf_cookie, *proof_cookie_names):
            if _COOKIE_NAME_PATTERN.fullmatch(name) is None:
                raise ValueError("BROWSER_COOKIE_NAME_INVALID")
            if name.startswith("__Host-") and not self.secure:
                raise ValueError("BROWSER_HOST_COOKIE_REQUIRES_SECURE")
        if not 60 <= self.session_max_age_seconds <= 24 * 60 * 60:
            raise ValueError("BROWSER_SESSION_MAX_AGE_INVALID")

    def proof_cookie(self, provider: IdentityProviderV1) -> str:
        if provider not in self.allowed_providers:
            raise ValueError("BROWSER_PROVIDER_INVALID")
        try:
            return _PROOF_COOKIES[provider]
        except KeyError:
            raise ValueError("BROWSER_PROVIDER_INVALID") from None

    def csrf_token(self, session_token: str) -> str:
        if (
            not isinstance(session_token, str)
            or _SESSION_TOKEN_PATTERN.fullmatch(session_token) is None
        ):
            raise ValueError("BROWSER_SESSION_TOKEN_INVALID")
        digest = hmac.new(
            self.csrf_binding_key,
            b"omni-cio-v10-csrf\x00" + session_token.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def csrf_matches(self, *, session_token: str, csrf_token: str) -> bool:
        if (
            not isinstance(csrf_token, str)
            or _CSRF_TOKEN_PATTERN.fullmatch(csrf_token) is None
        ):
            return False
        try:
            expected = self.csrf_token(session_token)
        except ValueError:
            return False
        return hmac.compare_digest(expected, csrf_token)
