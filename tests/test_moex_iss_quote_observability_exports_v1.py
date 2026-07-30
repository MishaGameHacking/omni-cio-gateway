from omni_cio.observability import (
    MoexIssQuoteObservabilityError,
    build_moex_iss_quote_cache_event,
    build_moex_iss_quote_source_event,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    MoexIssQuoteObservabilityError as DirectMoexIssQuoteObservabilityError,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    build_moex_iss_quote_cache_event as direct_build_moex_iss_quote_cache_event,
)
from omni_cio.observability.moex_iss_quote_events_v1 import (
    build_moex_iss_quote_source_event as direct_build_moex_iss_quote_source_event,
)


def test_moex_observability_exports_are_stable() -> None:
    assert MoexIssQuoteObservabilityError is DirectMoexIssQuoteObservabilityError
    assert build_moex_iss_quote_cache_event is direct_build_moex_iss_quote_cache_event
    assert build_moex_iss_quote_source_event is direct_build_moex_iss_quote_source_event
