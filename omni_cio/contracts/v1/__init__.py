"""Omni-CIO data contracts, schema version 1.0."""

from omni_cio.contracts.v1.common import (
    AccountReference,
    Completeness,
    ContractMetadata,
    DataIssue,
    DataQuality,
    IssueSeverity,
    Money,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.portfolio import (
    CashBalanceV1,
    CurrencyTotalsV1,
    InstrumentIdentity,
    InstrumentType,
    PortfolioPositionV1,
    PortfolioSnapshotV1,
    PositionValuation,
    ValuationBasis,
)

SCHEMA_VERSION = "1.0"

__all__ = [
    "SCHEMA_VERSION",
    "AccountReference",
    "CashBalanceV1",
    "Completeness",
    "ContractMetadata",
    "CurrencyTotalsV1",
    "DataIssue",
    "DataQuality",
    "InstrumentIdentity",
    "InstrumentType",
    "IssueSeverity",
    "Money",
    "PortfolioPositionV1",
    "PortfolioSnapshotV1",
    "PositionValuation",
    "QualityMetadata",
    "SourceReference",
    "ValuationBasis",
]
