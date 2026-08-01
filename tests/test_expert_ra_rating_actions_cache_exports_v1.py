from omni_cio.contracts.v1 import (
    CreditRatingCacheErrorCode,
    CreditRatingCacheStatus,
    ExpertRaIssuerRatingActionsCacheResultV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsCacheResultV1 as DirectCacheResult,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheErrorCode as DirectCacheErrorCode,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingCacheStatus as DirectCacheStatus,
)
from omni_cio.market import (
    DEFAULT_EXPERT_RA_RATING_CACHE_FRESH_SECONDS,
    DEFAULT_EXPERT_RA_RATING_CACHE_STALE_SECONDS,
    ExpertRaIssuerRatingActionsCacheV1,
    ExpertRaRatingActionsCacheError,
)
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    DEFAULT_EXPERT_RA_RATING_CACHE_FRESH_SECONDS as DirectFreshSeconds,
)
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    DEFAULT_EXPERT_RA_RATING_CACHE_STALE_SECONDS as DirectStaleSeconds,
)
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    ExpertRaIssuerRatingActionsCacheV1 as DirectCache,
)
from omni_cio.market.expert_ra_rating_actions_cache_v1 import (
    ExpertRaRatingActionsCacheError as DirectCacheError,
)


def test_expert_ra_cache_contract_exports_are_stable() -> None:
    assert ExpertRaIssuerRatingActionsCacheResultV1 is DirectCacheResult
    assert CreditRatingCacheErrorCode is DirectCacheErrorCode
    assert CreditRatingCacheStatus is DirectCacheStatus


def test_expert_ra_cache_runtime_exports_are_stable() -> None:
    assert ExpertRaIssuerRatingActionsCacheV1 is DirectCache
    assert ExpertRaRatingActionsCacheError is DirectCacheError
    assert DEFAULT_EXPERT_RA_RATING_CACHE_FRESH_SECONDS == DirectFreshSeconds
    assert DEFAULT_EXPERT_RA_RATING_CACHE_STALE_SECONDS == DirectStaleSeconds
