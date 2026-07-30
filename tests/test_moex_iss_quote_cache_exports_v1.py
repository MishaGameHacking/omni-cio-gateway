from __future__ import annotations

from omni_cio.contracts.v1 import (
    MoexIssTqbrQuoteCacheResultV1,
    MoexQuoteCacheErrorCode,
    MoexQuoteCacheStatus,
)
from omni_cio.market import MoexIssQuoteCacheError, MoexIssTqbrQuoteCacheV1


def test_moex_quote_cache_contracts_are_versioned_exports() -> None:
    assert MoexQuoteCacheStatus.FRESH.value == "fresh"
    assert (
        MoexQuoteCacheErrorCode.STALE_NOT_ALLOWED.value
        == "MOEX_QUOTE_CACHE_STALE_NOT_ALLOWED"
    )
    assert (
        MoexIssTqbrQuoteCacheResultV1.__name__
        == "MoexIssTqbrQuoteCacheResultV1"
    )


def test_moex_quote_cache_runtime_is_market_export() -> None:
    assert MoexIssQuoteCacheError.__name__ == "MoexIssQuoteCacheError"
    assert MoexIssTqbrQuoteCacheV1.__name__ == "MoexIssTqbrQuoteCacheV1"
