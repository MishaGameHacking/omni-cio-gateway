from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

import httpx

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationStartV1,
    AuthorizationTransactionStoreLike,
    ConsumedAuthorizationTransactionV1,
    ProviderAuthorizationStartV1,
)
from omni_cio.web.telegram_oidc_v1 import (
    TelegramIdTokenVerifierLike,
    TelegramOidcConfigV1,
    TelegramOidcRuntimeV1,
)
from omni_cio.web.vk_id_oauth_v1 import VkIdOauthConfigV1, VkIdOauthRuntimeV1


class _BrowserProofBoundTransactionsV1:
    """Bind one route-owned browser proof while delegating all store authority."""

    def __init__(
        self,
        transactions: AuthorizationTransactionStoreLike,
        browser_proof: str,
    ) -> None:
        self._transactions = transactions
        self._browser_proof = browser_proof

    def begin(
        self,
        *,
        provider: IdentityProviderV1,
        redirect_uri: str,
        now: datetime,
        browser_proof: str | None = None,
    ) -> AuthorizationStartV1:
        if browser_proof is not None:
            raise ValueError("BROWSER_PROOF_ALREADY_BOUND")
        return self._transactions.begin(
            provider=provider,
            redirect_uri=redirect_uri,
            now=now,
            browser_proof=self._browser_proof,
        )

    def consume(
        self,
        *,
        provider: IdentityProviderV1,
        state: str,
        browser_proof: str,
        now: datetime,
    ) -> ConsumedAuthorizationTransactionV1:
        return self._transactions.consume(
            provider=provider,
            state=state,
            browser_proof=browser_proof,
            now=now,
        )


def _with_authorization_query(
    authorization: ProviderAuthorizationStartV1,
) -> ProviderAuthorizationStartV1:
    return ProviderAuthorizationStartV1(
        authorization_url=authorization.authorization_url,
        browser_proof=authorization.browser_proof,
        expires_at=authorization.expires_at,
        authorization_query=urlsplit(authorization.authorization_url).query,
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
        bound = _BrowserProofBoundTransactionsV1(
            self._transactions,
            browser_proof,
        )
        runtime = TelegramOidcRuntimeV1(
            config=self._config,
            transactions=bound,
            client=self._client,
            verifier=self._verifier,
        )
        return _with_authorization_query(runtime.start(now=now))


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
        bound = _BrowserProofBoundTransactionsV1(
            self._transactions,
            browser_proof,
        )
        runtime = VkIdOauthRuntimeV1(
            config=self._config,
            transactions=bound,
            client=self._client,
        )
        return _with_authorization_query(runtime.start(now=now))
