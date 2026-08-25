from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

import httpx

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionStoreLike,
    ProviderAuthorizationStartV1,
)
from omni_cio.web.telegram_oidc_v1 import (
    TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT,
    TelegramIdTokenVerifierLike,
    TelegramOidcConfigV1,
    TelegramOidcRuntimeV1,
)
from omni_cio.web.vk_id_oauth_v1 import (
    VK_ID_AUTHORIZATION_ENDPOINT,
    VkIdOauthConfigV1,
    VkIdOauthRuntimeV1,
)


class BrowserBoundTelegramOidcRuntimeV1(TelegramOidcRuntimeV1):
    """Deployed Telegram adapter with route-owned browser-proof provenance."""

    def __init__(
        self,
        *,
        config: TelegramOidcConfigV1,
        transactions: AuthorizationTransactionStoreLike,
        client: httpx.Client | None = None,
        verifier: TelegramIdTokenVerifierLike | None = None,
    ) -> None:
        super().__init__(
            config=config,
            transactions=transactions,
            client=client,
            verifier=verifier,
        )

    def start(
        self,
        *,
        now: datetime,
        browser_proof: str | None = None,
    ) -> ProviderAuthorizationStartV1:
        if browser_proof is None:
            return super().start(now=now)
        transaction = self._transactions.begin(
            provider=IdentityProviderV1.TELEGRAM,
            redirect_uri=self._config.redirect_uri,
            now=now,
            browser_proof=browser_proof,
        )
        query = urlencode(
            {
                "client_id": self._config.client_id,
                "redirect_uri": transaction.redirect_uri,
                "response_type": "code",
                "scope": "openid",
                "state": transaction.state,
                "code_challenge": transaction.code_challenge,
                "code_challenge_method": "S256",
                "nonce": transaction.nonce,
            }
        )
        return ProviderAuthorizationStartV1(
            authorization_url=f"{TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT}?{query}",
            browser_proof=transaction.browser_proof,
            expires_at=transaction.expires_at,
            authorization_query=query,
        )


class BrowserBoundVkIdOauthRuntimeV1(VkIdOauthRuntimeV1):
    """Deployed VK ID adapter with route-owned browser-proof provenance."""

    def __init__(
        self,
        *,
        config: VkIdOauthConfigV1,
        transactions: AuthorizationTransactionStoreLike,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(config=config, transactions=transactions, client=client)

    def start(
        self,
        *,
        now: datetime,
        browser_proof: str | None = None,
    ) -> ProviderAuthorizationStartV1:
        if browser_proof is None:
            return super().start(now=now)
        transaction = self._transactions.begin(
            provider=IdentityProviderV1.VK_ID,
            redirect_uri=self._config.redirect_uri,
            now=now,
            browser_proof=browser_proof,
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
        return ProviderAuthorizationStartV1(
            authorization_url=f"{VK_ID_AUTHORIZATION_ENDPOINT}?{query}",
            browser_proof=transaction.browser_proof,
            expires_at=transaction.expires_at,
            authorization_query=query,
        )
