from datetime import datetime, timezone

import httpx
import pytest

from omni_cio.contracts.v1.ratings import CreditRatingSourceErrorCode
from omni_cio.market.expert_ra_rating_actions_v1 import (
    DEFAULT_EXPERT_RA_MAX_RESPONSE_BYTES,
    DEFAULT_EXPERT_RA_TIMEOUT_SECONDS,
    fetch_expert_ra_issuer_rating_actions,
)


NOW = datetime(2026, 7, 31, 6, 45, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        float("nan"),
        float("inf"),
        -float("inf"),
        DEFAULT_EXPERT_RA_TIMEOUT_SECONDS + 0.001,
        10**1000,
    ],
)
def test_invalid_or_expansive_timeout_makes_no_request(
    timeout_seconds: float,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
            timeout_seconds=timeout_seconds,
        )

    assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert calls == 0


@pytest.mark.parametrize(
    "max_response_bytes",
    [
        DEFAULT_EXPERT_RA_MAX_RESPONSE_BYTES + 1,
        10**1000,
    ],
)
def test_expansive_response_budget_makes_no_request(
    max_response_bytes: int,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
            max_response_bytes=max_response_bytes,
        )

    assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert calls == 0
