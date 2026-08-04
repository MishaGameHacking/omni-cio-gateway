from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone

from omni_cio.contracts.v1.credit import CreditPassportV1
from omni_cio.contracts.v1.market import MarketResearchBundleV1
from omni_cio.contracts.v1.portfolio_risk import PortfolioRiskAssessmentV1
from omni_cio.contracts.v1.watchtower import (
    WatchtowerInputV1,
    watchtower_input_sha256,
)


class WatchtowerProviderError(RuntimeError):
    pass


class CanonicalWatchtowerEvidenceProviderV1:
    """Compose already-canonical WP6/WP8/market objects without recalculating them."""

    def __init__(
        self,
        *,
        risk_loader: Callable[[], PortfolioRiskAssessmentV1],
        credit_loader: Callable[[], Iterable[CreditPassportV1]] = tuple,
        market_loader: Callable[[], Iterable[MarketResearchBundleV1]] = tuple,
        quality_code_loader: Callable[[], Iterable[str]] = tuple,
    ) -> None:
        for name, loader in (
            ("risk", risk_loader),
            ("credit", credit_loader),
            ("market", market_loader),
            ("quality", quality_code_loader),
        ):
            if not callable(loader):
                raise WatchtowerProviderError(f"WATCHTOWER_{name.upper()}_LOADER_INVALID")
        self._risk_loader = risk_loader
        self._credit_loader = credit_loader
        self._market_loader = market_loader
        self._quality_loader = quality_code_loader

    def build_input(
        self,
        *,
        delivery_id: str,
        checked_at: datetime,
    ) -> WatchtowerInputV1:
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise WatchtowerProviderError("WATCHTOWER_PROVIDER_TIMESTAMP_INVALID")
        checked_at = checked_at.astimezone(timezone.utc)
        try:
            risk = PortfolioRiskAssessmentV1.model_validate(
                self._risk_loader().model_dump(mode="python")
            )
            credits = tuple(
                CreditPassportV1.model_validate(row.model_dump(mode="python"))
                for row in self._credit_loader()
            )
            markets = tuple(
                MarketResearchBundleV1.model_validate(row.model_dump(mode="python"))
                for row in self._market_loader()
            )
            quality_codes = tuple(str(row).strip().upper() for row in self._quality_loader())
        except Exception as exc:
            raise WatchtowerProviderError("WATCHTOWER_CANONICAL_EVIDENCE_UNAVAILABLE") from exc

        values = {
            "schema_version": "1.0",
            "checked_at": checked_at,
            "delivery_id": delivery_id,
            "portfolio_snapshot_sha256": risk.portfolio_snapshot_sha256,
            "policy_reference": risk.policy_reference,
            "risk": risk,
            "credit_passports": credits,
            "market_bundles": markets,
            "source_quality_codes": quality_codes,
            "input_sha256": "0" * 64,
            "execution_authorized": False,
            "trading_methods": False,
        }
        provisional = WatchtowerInputV1.model_construct(**values)
        values["input_sha256"] = watchtower_input_sha256(provisional)
        try:
            return WatchtowerInputV1.model_validate(values)
        except Exception as exc:
            raise WatchtowerProviderError("WATCHTOWER_CANONICAL_EVIDENCE_INVALID") from exc
