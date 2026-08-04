from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from omni_cio.contracts.v1.credit import CreditPassportV1
from omni_cio.contracts.v1.market import MarketResearchBundleV1
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskAssessmentV1

from .provider_v1 import CanonicalWatchtowerEvidenceProviderV1
from .runtime_v1 import WatchtowerEvidenceProviderRegistryV1, WatchtowerRuntimeError


@dataclass(frozen=True)
class WatchtowerProviderInstallationV1:
    installed: bool
    internal_only: bool = True
    startup_broker_call_performed: bool = False
    broker_write_called: bool = False
    trade_authorized: bool = False
    order_created: bool = False
    trading_methods: bool = False


def install_watchtower_canonical_provider(
    *,
    app: Any,
    risk_loader: Callable[[], PortfolioRiskAssessmentV1],
    credit_loader: Callable[[], Iterable[CreditPassportV1]] = tuple,
    market_loader: Callable[[], Iterable[MarketResearchBundleV1]] = tuple,
    quality_code_loader: Callable[[], Iterable[str]] = tuple,
) -> WatchtowerProviderInstallationV1:
    """Install lazy read-only loaders; never invoke them during installation."""
    registry = getattr(getattr(app, "state", None), "watchtower_provider_registry", None)
    if not isinstance(registry, WatchtowerEvidenceProviderRegistryV1):
        raise WatchtowerRuntimeError("WATCHTOWER_GATEWAY_REGISTRY_NOT_AVAILABLE")
    provider = CanonicalWatchtowerEvidenceProviderV1(
        risk_loader=risk_loader,
        credit_loader=credit_loader,
        market_loader=market_loader,
        quality_code_loader=quality_code_loader,
    )
    registry.register(provider)
    return WatchtowerProviderInstallationV1(installed=True)
