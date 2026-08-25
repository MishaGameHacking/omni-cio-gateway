from __future__ import annotations

from omni_cio.web.identity_v1 import IdentityProviderV1
from omni_cio.web.request_limits_v1 import (
    BoundedFixedWindowLimiterV1,
    HostedRequestAbuseControlV1,
    ProviderAuthAbuseControlV1,
    RequestRatePolicyV1,
)


def test_fixed_window_limiter_bounds_attacker_controlled_key_population() -> None:
    limiter = BoundedFixedWindowLimiterV1(window_seconds=60, max_keys=2)

    assert limiter.admit("a", limit=1, now_monotonic=0.0)
    assert limiter.admit("b", limit=1, now_monotonic=0.0)
    assert not limiter.admit("c", limit=1, now_monotonic=1.0)
    assert limiter.admit("c", limit=1, now_monotonic=61.0)


def test_hosted_control_has_separate_anonymous_and_session_dimensions() -> None:
    policy = RequestRatePolicyV1(
        anonymous_requests=1,
        authenticated_session_requests=2,
        max_session_keys=8,
    )
    control = HostedRequestAbuseControlV1(policy)

    assert control.admit(session_token=None, now_monotonic=0.0)
    assert not control.admit(session_token=None, now_monotonic=1.0)
    assert control.admit(session_token="opaque-session-a", now_monotonic=1.0)
    assert control.admit(session_token="opaque-session-a", now_monotonic=2.0)
    assert not control.admit(session_token="opaque-session-a", now_monotonic=3.0)
    assert control.admit(session_token="opaque-session-b", now_monotonic=3.0)


def test_provider_start_and_callback_windows_are_bounded_independently() -> None:
    policy = RequestRatePolicyV1(provider_starts=1, provider_callbacks=2)
    control = ProviderAuthAbuseControlV1(policy)

    assert control.admit_start(IdentityProviderV1.TELEGRAM, now_monotonic=0.0)
    assert not control.admit_start(
        IdentityProviderV1.TELEGRAM,
        now_monotonic=1.0,
    )
    assert control.admit_start(IdentityProviderV1.VK_ID, now_monotonic=1.0)

    assert control.admit_callback(
        IdentityProviderV1.TELEGRAM,
        now_monotonic=0.0,
    )
    assert control.admit_callback(
        IdentityProviderV1.TELEGRAM,
        now_monotonic=1.0,
    )
    assert not control.admit_callback(
        IdentityProviderV1.TELEGRAM,
        now_monotonic=2.0,
    )


def test_provider_outbound_concurrency_fails_fast_and_recovers() -> None:
    control = ProviderAuthAbuseControlV1(
        RequestRatePolicyV1(outbound_provider_concurrency=1)
    )

    assert control.acquire_outbound()
    assert not control.acquire_outbound()
    control.release_outbound()
    assert control.acquire_outbound()
    control.release_outbound()


def test_rate_policy_rejects_unbounded_or_invalid_values() -> None:
    for kwargs in (
        {"window_seconds": 0},
        {"outbound_provider_concurrency": 257},
        {"max_session_keys": 65537},
        {"retry_after_seconds": 61},
    ):
        try:
            RequestRatePolicyV1(**kwargs)
        except ValueError as exc:
            assert str(exc) == "REQUEST_RATE_POLICY_INVALID"
        else:
            raise AssertionError("invalid request-rate policy was accepted")
