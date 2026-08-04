from __future__ import annotations

from fastapi import FastAPI

from omni_cio.watchtower.installation_v1 import install_watchtower_canonical_provider
from omni_cio.watchtower.routes_v1 import register_watchtower_routes
from omni_cio.watchtower.runtime_v1 import WatchtowerEvidenceProviderRegistryV1
from tests.v9_execution_fixture import build_execution_fixture


def test_canonical_provider_installation_performs_no_source_or_broker_call() -> None:
    app = FastAPI()
    registry = WatchtowerEvidenceProviderRegistryV1()
    register_watchtower_routes(
        app,
        provider_registry=registry,
        environment={"WATCHTOWER_ENABLED": "false"},
    )
    app.state.watchtower_provider_registry = registry
    calls = 0

    def risk_loader():
        nonlocal calls
        calls += 1
        return build_execution_fixture().risk

    installed = install_watchtower_canonical_provider(
        app=app,
        risk_loader=risk_loader,
    )
    assert installed.installed is True
    assert installed.internal_only is True
    assert installed.startup_broker_call_performed is False
    assert installed.broker_write_called is False
    assert installed.trade_authorized is False
    assert installed.order_created is False
    assert installed.trading_methods is False
    assert calls == 0

    built = registry.get().build_input(
        delivery_id="installation-delivery-0001",
        checked_at=build_execution_fixture().risk.assessed_at,
    )
    assert built.risk == build_execution_fixture().risk
    assert calls == 1
