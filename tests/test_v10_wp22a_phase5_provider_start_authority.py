from __future__ import annotations

from datetime import datetime, timezone
import secrets
from urllib.parse import parse_qs, urlsplit

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionRegistryV1,
    ProviderAuthorizationError,
    new_authorization_browser_proof_v1,
)
from omni_cio.web.provider_start_adapter_v1 import (
    BrowserBoundTelegramOidcRuntimeV1,
    BrowserBoundVkIdOauthRuntimeV1,
)
from omni_cio.web.telegram_oidc_v1 import (
    TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT,
    TelegramOidcConfigV1,
)
from omni_cio.web.vk_id_oauth_v1 import (
    VK_ID_AUTHORIZATION_ENDPOINT,
    VkIdOauthConfigV1,
)


NOW = datetime(2026, 8, 25, 21, 30, tzinfo=timezone.utc)
TELEGRAM_CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"
VK_CALLBACK = "https://omni.example/api/v10/web/auth/vk_id/callback"
TELEGRAM_CLIENT_SECRET = secrets.token_urlsafe(32)


def test_route_minted_browser_proof_binds_telegram_transaction() -> None:
    transactions = AuthorizationTransactionRegistryV1()
    runtime = BrowserBoundTelegramOidcRuntimeV1(
        config=TelegramOidcConfigV1(
            client_id="123456789",
            client_secret=TELEGRAM_CLIENT_SECRET,
            redirect_uri=TELEGRAM_CALLBACK,
        ),
        transactions=transactions,
    )
    proof = new_authorization_browser_proof_v1()

    start = runtime.start(now=NOW, browser_proof=proof)
    parsed = urlsplit(start.authorization_url)
    state = parse_qs(parsed.query)["state"][0]

    assert start.browser_proof == proof
    assert start.authorization_query == parsed.query
    assert parsed.scheme == "https"
    assert parsed.netloc == "oauth.telegram.org"
    assert parsed.path == urlsplit(TELEGRAM_OIDC_AUTHORIZATION_ENDPOINT).path
    consumed = transactions.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=state,
        browser_proof=proof,
        now=NOW,
    )
    assert consumed.redirect_uri == TELEGRAM_CALLBACK


def test_route_minted_browser_proof_binds_vk_transaction() -> None:
    transactions = AuthorizationTransactionRegistryV1()
    runtime = BrowserBoundVkIdOauthRuntimeV1(
        config=VkIdOauthConfigV1(
            client_id="123456789",
            redirect_uri=VK_CALLBACK,
        ),
        transactions=transactions,
    )
    proof = new_authorization_browser_proof_v1()

    start = runtime.start(now=NOW, browser_proof=proof)
    parsed = urlsplit(start.authorization_url)
    state = parse_qs(parsed.query, keep_blank_values=True)["state"][0]

    assert start.browser_proof == proof
    assert start.authorization_query == parsed.query
    assert parsed.scheme == "https"
    assert parsed.netloc == "id.vk.ru"
    assert parsed.path == urlsplit(VK_ID_AUTHORIZATION_ENDPOINT).path
    consumed = transactions.consume(
        provider=IdentityProviderV1.VK_ID,
        state=state,
        browser_proof=proof,
        now=NOW,
    )
    assert consumed.redirect_uri == VK_CALLBACK


def test_supplied_browser_proof_is_shape_checked_before_transaction_storage() -> None:
    transactions = AuthorizationTransactionRegistryV1()

    with pytest.raises(
        ProviderAuthorizationError,
        match="AUTH_TRANSACTION_BROWSER_PROOF_INVALID",
    ):
        transactions.begin(
            provider=IdentityProviderV1.TELEGRAM,
            redirect_uri=TELEGRAM_CALLBACK,
            now=NOW,
            browser_proof="not valid proof material",
        )
    assert transactions.pending_count(now=NOW) == 0
