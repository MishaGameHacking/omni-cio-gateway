from __future__ import annotations

import app as gateway

from omni_cio.watchtower.runtime_v1 import WatchtowerEvidenceProviderRegistryV1


INTERNAL_PATHS = {
    "/internal/watchtower/run",
    "/internal/watchtower/callback",
    "/internal/watchtower/failure-callback",
}


def test_watchtower_is_registered_on_single_gateway_but_hidden_from_openapi() -> None:
    registered = {getattr(route, "path", "") for route in gateway.app.routes}
    assert INTERNAL_PATHS <= registered

    schema_paths = set(gateway.app.openapi().get("paths", {}))
    assert INTERNAL_PATHS.isdisjoint(schema_paths)
    assert gateway.app.title == "Omni-CIO API"

    registry = gateway.app.state.watchtower_provider_registry
    assert isinstance(registry, WatchtowerEvidenceProviderRegistryV1)
    registration = gateway.app.state.watchtower_route_registration
    assert registration.include_in_schema is False
    assert registration.broker_write_called is False
    assert registration.trade_authorized is False
    assert registration.order_created is False
    assert registration.trading_methods is False
