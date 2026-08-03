from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic

from omni_cio.contracts.v1.universe import (
    REQUIRED_UNIVERSE_OPERATIONS,
    UniverseCatalogV1,
)


Clock = Callable[[], float]
CatalogLoader = Callable[[], UniverseCatalogV1]


@dataclass(frozen=True)
class UniverseCatalogCacheResultV1:
    catalog: UniverseCatalogV1
    cache_hit: bool


class UniverseCatalogCacheV1:
    """Process-local TTL cache for the expensive full BASE instrument catalog."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 6 * 60 * 60,
        clock: Clock = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._lock = RLock()
        self._entry: tuple[float, UniverseCatalogV1] | None = None

    @staticmethod
    def _cacheable(catalog: UniverseCatalogV1) -> bool:
        return (
            not catalog.source_errors
            and catalog.invalid_rows == 0
            and set(catalog.completed_operations) == set(REQUIRED_UNIVERSE_OPERATIONS)
        )

    def clear(self) -> None:
        with self._lock:
            self._entry = None

    def get_or_refresh(
        self,
        loader: CatalogLoader,
        *,
        force_refresh: bool = False,
    ) -> UniverseCatalogCacheResultV1:
        with self._lock:
            now = self._clock()
            if not force_refresh and self._entry is not None:
                expires_at, catalog = self._entry
                if now < expires_at:
                    return UniverseCatalogCacheResultV1(
                        catalog=catalog,
                        cache_hit=True,
                    )

            catalog = loader()
            if self._cacheable(catalog):
                self._entry = (now + self._ttl_seconds, catalog)
            else:
                self._entry = None
            return UniverseCatalogCacheResultV1(
                catalog=catalog,
                cache_hit=False,
            )
