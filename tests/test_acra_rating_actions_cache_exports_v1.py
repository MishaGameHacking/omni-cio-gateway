from omni_cio.contracts.v1 import (
    AcraIssuerRatingActionsCacheResultV1,
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
)
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsCacheResultV1 as DirectCacheResult,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode as DirectCacheErrorCode,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheStatus as DirectCacheStatus,
)
from omni_cio.market import (
    AcraIssuerRatingActionsCacheV1,
    AcraRatingActionsCacheError,
    DEFAULT_ACRA_RATING_CACHE_FRESH_SECONDS,
    DEFAULT_ACRA_RATING_CACHE_STALE_SECONDS,
)
from omni_cio.market.acra_rating_actions_cache_v1 import (
    AcraIssuerRatingActionsCacheV1 as DirectCache,
)
from omni_cio.market.acra_rating_actions_cache_v1 import (
    AcraRatingActionsCacheError as DirectCacheError,
)
from omni_cio.market.acra_rating_actions_cache_v1 import (
    DEFAULT_ACRA_RATING_CACHE_FRESH_SECONDS as DirectFreshSeconds,
)
from omni_cio.market.acra_rating_actions_cache_v1 import (
    DEFAULT_ACRA_RATING_CACHE_STALE_SECONDS as DirectStaleSeconds,
)


def test_acra_cache_contract_exports_are_stable() -> None:
    assert AcraIssuerRatingActionsCacheResultV1 is DirectCacheResult
    assert CreditRatingCacheErrorCode is DirectCacheErrorCode
    assert CreditRatingCacheStatus is DirectCacheStatus


def test_acra_cache_runtime_exports_are_stable() -> None:
    assert AcraIssuerRatingActionsCacheV1 is DirectCache
    assert AcraRatingActionsCacheError is DirectCacheError
    assert DEFAULT_ACRA_RATING_CACHE_FRESH_SECONDS == DirectFreshSeconds
    assert DEFAULT_ACRA_RATING_CACHE_STALE_SECONDS == DirectStaleSeconds
