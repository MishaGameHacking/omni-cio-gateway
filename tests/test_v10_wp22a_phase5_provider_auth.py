from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.provider_auth_v1 import (
    AuthorizationTransactionPolicyV1,
    AuthorizationTransactionRegistryV1,
    ProviderAuthorizationError,
)

NOW = datetime(2026, 8, 24, 0, 0, tzinfo=timezone.utc)
CALLBACK = "https://omni.example/api/v10/web/auth/telegram/callback"


def test_transaction_generates_pkce_without_exposing_verifier() -> None:
    registry = AuthorizationTransactionRegistryV1()
    transaction = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    assert 43 <= len(transaction.state) <= 128
    assert not hasattr(transaction, "code_verifier")
    assert len(transaction.code_challenge) == 43
    assert "=" not in transaction.code_challenge

    consumed = registry.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=transaction.state,
        now=NOW,
    )
    assert 43 <= len(consumed.code_verifier) <= 128
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(consumed.code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    assert transaction.code_challenge == expected


def test_transaction_is_one_time_and_wrong_provider_cannot_consume_it() -> None:
    registry = AuthorizationTransactionRegistryV1()
    transaction = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    with pytest.raises(
        ProviderAuthorizationError, match="AUTH_TRANSACTION_PROVIDER_MISMATCH"
    ):
        registry.consume(
            provider=IdentityProviderV1.VK_ID,
            state=transaction.state,
            now=NOW,
        )
    assert registry.pending_count(now=NOW) == 1

    consumed = registry.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=transaction.state,
        now=NOW,
    )
    assert 43 <= len(consumed.code_verifier) <= 128
    assert consumed.nonce == transaction.nonce
    assert consumed.redirect_uri == CALLBACK

    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        registry.consume(
            provider=IdentityProviderV1.TELEGRAM,
            state=transaction.state,
            now=NOW,
        )


def test_expired_state_is_destroyed_and_rejected() -> None:
    registry = AuthorizationTransactionRegistryV1(
        AuthorizationTransactionPolicyV1(lifetime=timedelta(seconds=30))
    )
    transaction = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        registry.consume(
            provider=IdentityProviderV1.TELEGRAM,
            state=transaction.state,
            now=NOW + timedelta(seconds=30),
        )
    assert registry.pending_count(now=NOW + timedelta(seconds=30)) == 0


def test_capacity_is_bounded_but_expired_entries_do_not_self_dos() -> None:
    registry = AuthorizationTransactionRegistryV1(
        AuthorizationTransactionPolicyV1(
            lifetime=timedelta(seconds=10),
            max_pending=1,
        )
    )
    registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )
    with pytest.raises(
        ProviderAuthorizationError, match="AUTH_TRANSACTION_CAPACITY_EXCEEDED"
    ):
        registry.begin(
            provider=IdentityProviderV1.TELEGRAM,
            redirect_uri=CALLBACK,
            now=NOW,
        )

    replacement = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW + timedelta(seconds=10),
    )
    assert replacement.state


def test_lazy_expiry_keeps_later_transaction_until_its_deadline() -> None:
    registry = AuthorizationTransactionRegistryV1(
        AuthorizationTransactionPolicyV1(lifetime=timedelta(seconds=10))
    )
    first = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )
    second = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW + timedelta(seconds=1),
    )

    assert registry.pending_count(now=NOW + timedelta(seconds=10)) == 1
    consumed = registry.consume(
        provider=IdentityProviderV1.TELEGRAM,
        state=second.state,
        now=NOW + timedelta(seconds=10),
    )
    assert consumed.expires_at == NOW + timedelta(seconds=11)
    with pytest.raises(ProviderAuthorizationError, match="AUTH_TRANSACTION_NOT_FOUND"):
        registry.consume(
            provider=IdentityProviderV1.TELEGRAM,
            state=first.state,
            now=NOW + timedelta(seconds=10),
        )


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "http://omni.example/callback",
        "https://user:pass@omni.example/callback",
        "https://omni.example:8443/callback",
        "https://omni.example/callback?next=/portfolio",
        "https://omni.example/callback#fragment",
        "not-a-url",
    ],
)
def test_redirect_uri_is_fail_closed(redirect_uri: str) -> None:
    registry = AuthorizationTransactionRegistryV1()
    with pytest.raises(ValueError, match="AUTH_REDIRECT_URI_INVALID"):
        registry.begin(
            provider=IdentityProviderV1.TELEGRAM,
            redirect_uri=redirect_uri,
            now=NOW,
        )


def test_only_one_parallel_callback_can_consume_state() -> None:
    registry = AuthorizationTransactionRegistryV1()
    transaction = registry.begin(
        provider=IdentityProviderV1.TELEGRAM,
        redirect_uri=CALLBACK,
        now=NOW,
    )

    def consume(_: int) -> str:
        try:
            registry.consume(
                provider=IdentityProviderV1.TELEGRAM,
                state=transaction.state,
                now=NOW,
            )
            return "accepted"
        except ProviderAuthorizationError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(consume, range(16)))

    assert results.count("accepted") == 1
    assert results.count("AUTH_TRANSACTION_NOT_FOUND") == 15


def test_policy_bounds_and_utc_clock_are_enforced() -> None:
    with pytest.raises(ValueError, match="AUTH_TRANSACTION_LIFETIME_INVALID"):
        AuthorizationTransactionPolicyV1(lifetime=timedelta(0))
    with pytest.raises(ValueError, match="AUTH_TRANSACTION_CAPACITY_INVALID"):
        AuthorizationTransactionPolicyV1(max_pending=0)
    with pytest.raises(ValueError, match="AUTH_TRANSACTION_CAPACITY_INVALID"):
        AuthorizationTransactionPolicyV1(max_pending=4097)

    registry = AuthorizationTransactionRegistryV1()
    with pytest.raises(ValueError, match="AUTH_TRANSACTION_CLOCK_NOT_UTC_AWARE"):
        registry.begin(
            provider=IdentityProviderV1.TELEGRAM,
            redirect_uri=CALLBACK,
            now=datetime(2026, 8, 24),
        )


def test_non_base64url_state_is_rejected_without_lookup() -> None:
    registry = AuthorizationTransactionRegistryV1()
    with pytest.raises(
        ProviderAuthorizationError, match="AUTH_TRANSACTION_STATE_INVALID"
    ):
        registry.consume(
            provider=IdentityProviderV1.TELEGRAM,
            state="☃" * 40,
            now=NOW,
        )
