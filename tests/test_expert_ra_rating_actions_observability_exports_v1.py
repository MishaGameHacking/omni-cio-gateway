from omni_cio.observability import (
    ExpertRaRatingActionsObservabilityError,
    build_expert_ra_rating_actions_cache_event,
    build_expert_ra_rating_actions_source_event,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    ExpertRaRatingActionsObservabilityError as DirectError,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_cache_event as DirectCacheBuilder,
)
from omni_cio.observability.expert_ra_rating_actions_events_v1 import (
    build_expert_ra_rating_actions_source_event as DirectSourceBuilder,
)


def test_expert_ra_observability_exports_are_stable() -> None:
    assert ExpertRaRatingActionsObservabilityError is DirectError
    assert build_expert_ra_rating_actions_cache_event is DirectCacheBuilder
    assert build_expert_ra_rating_actions_source_event is DirectSourceBuilder
