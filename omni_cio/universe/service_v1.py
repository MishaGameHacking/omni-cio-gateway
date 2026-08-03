from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.universe import (
    MarketUniverseSnapshotV1,
    UniverseAccountEligibilityV1,
    UniverseCatalogV1,
    UniverseFetchBatchV1,
)
from omni_cio.universe.cache_v1 import UniverseCatalogCacheV1
from omni_cio.universe.engine_v1 import build_market_universe


class UniverseBrokerAdapterV1(Protocol):
    def fetch_account_eligibility(
        self,
        *,
        account_type: AccountPolicyType,
    ) -> tuple[UniverseAccountEligibilityV1, str | None]: ...

    def fetch_catalog(
        self,
        *,
        retrieved_at: datetime | None = None,
    ) -> UniverseCatalogV1: ...


@dataclass(frozen=True)
class MarketUniverseLoadResultV1:
    snapshot: MarketUniverseSnapshotV1
    catalog_cache_hit: bool


class MarketUniverseServiceV1:
    """Refresh account eligibility every load while caching only a verified catalog."""

    def __init__(
        self,
        adapter: UniverseBrokerAdapterV1,
        *,
        cache: UniverseCatalogCacheV1 | None = None,
    ) -> None:
        self._adapter = adapter
        self._cache = cache or UniverseCatalogCacheV1()

    def load(
        self,
        *,
        account_type: AccountPolicyType,
        force_catalog_refresh: bool = False,
    ) -> MarketUniverseLoadResultV1:
        account, account_error = self._adapter.fetch_account_eligibility(
            account_type=account_type
        )
        cached = self._cache.get_or_refresh(
            self._adapter.fetch_catalog,
            force_refresh=force_catalog_refresh,
        )
        snapshot = build_market_universe(
            UniverseFetchBatchV1(
                catalog=cached.catalog,
                account=account,
                account_source_error=account_error,
            )
        )
        return MarketUniverseLoadResultV1(
            snapshot=snapshot,
            catalog_cache_hit=cached.cache_hit,
        )
