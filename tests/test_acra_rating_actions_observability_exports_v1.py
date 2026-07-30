from omni_cio.observability import (
    AcraRatingActionsObservabilityError,
    build_acra_rating_actions_cache_event,
    build_acra_rating_actions_source_event,
)
from omni_cio.observability.acra_rating_actions_events_v1 import (
    AcraRatingActionsObservabilityError as DirectError,
)
from omni_cio.observability.acra_rating_actions_events_v1 import (
    build_acra_rating_actions_cache_event as DirectCacheBuilder,
)
from omni_cio.observability.acra_rating_actions_events_v1 import (
    build_acra_rating_actions_source_event as DirectSourceBuilder,
)


def test_acra_observability_exports_are_stable() -> None:
    assert AcraRatingActionsObservabilityError is DirectError
    assert build_acra_rating_actions_cache_event is DirectCacheBuilder
    assert build_acra_rating_actions_source_event is DirectSourceBuilder
