"""Deterministic offline paper-trading simulation."""

from omni_cio.paper.archive_v1 import (
    GENESIS_RECORD_DIGEST,
    PaperLedgerArchiveError,
    parse_paper_ledger_record_unverified,
    seal_paper_ledger_record,
    serialize_paper_ledger_record,
    verify_paper_ledger_archive_chain,
    verify_paper_ledger_record,
)
from omni_cio.paper.ledger_v1 import (
    PaperAccountLedgerError,
    build_paper_account_ledger,
)
from omni_cio.paper.sell_simulator_v1 import (
    PaperSaleSimulatorError,
    simulate_paper_sale,
)
from omni_cio.paper.simulator_v1 import (
    PaperSimulatorError,
    simulate_paper_purchase,
)

__all__ = [
    "GENESIS_RECORD_DIGEST",
    "PaperAccountLedgerError",
    "PaperLedgerArchiveError",
    "PaperSaleSimulatorError",
    "PaperSimulatorError",
    "build_paper_account_ledger",
    "parse_paper_ledger_record_unverified",
    "seal_paper_ledger_record",
    "serialize_paper_ledger_record",
    "simulate_paper_purchase",
    "simulate_paper_sale",
    "verify_paper_ledger_archive_chain",
    "verify_paper_ledger_record",
]
