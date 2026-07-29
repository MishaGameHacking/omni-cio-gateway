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
from omni_cio.paper.recovery_v1 import (
    PaperLedgerRecoveryError,
    build_paper_ledger_recovery_manifest,
    build_paper_ledger_retention_plan,
    diagnose_paper_ledger_writer_lock,
    parse_paper_ledger_recovery_manifest_unverified,
    serialize_paper_ledger_recovery_manifest,
    verify_paper_ledger_backup_against_manifest,
    verify_paper_ledger_recovery_manifest,
)
from omni_cio.paper.sell_simulator_v1 import (
    PaperSaleSimulatorError,
    simulate_paper_sale,
)
from omni_cio.paper.simulator_v1 import (
    PaperSimulatorError,
    simulate_paper_purchase,
)
from omni_cio.paper.storage_v1 import (
    ExternalAeadCiphertext,
    ExternalPaperLedgerKeyManager,
    PaperLedgerStorageError,
    decrypt_paper_ledger_envelope,
    encrypt_paper_ledger_record,
    list_encrypted_paper_ledger_files,
    load_encrypted_paper_ledger_archive,
    parse_encrypted_paper_ledger_envelope,
    serialize_encrypted_paper_ledger_envelope,
    write_encrypted_paper_ledger_record,
)

__all__ = [
    "GENESIS_RECORD_DIGEST",
    "ExternalAeadCiphertext",
    "ExternalPaperLedgerKeyManager",
    "PaperAccountLedgerError",
    "PaperLedgerArchiveError",
    "PaperLedgerRecoveryError",
    "PaperLedgerStorageError",
    "PaperSaleSimulatorError",
    "PaperSimulatorError",
    "build_paper_account_ledger",
    "build_paper_ledger_recovery_manifest",
    "build_paper_ledger_retention_plan",
    "decrypt_paper_ledger_envelope",
    "diagnose_paper_ledger_writer_lock",
    "encrypt_paper_ledger_record",
    "list_encrypted_paper_ledger_files",
    "load_encrypted_paper_ledger_archive",
    "parse_encrypted_paper_ledger_envelope",
    "parse_paper_ledger_recovery_manifest_unverified",
    "parse_paper_ledger_record_unverified",
    "seal_paper_ledger_record",
    "serialize_encrypted_paper_ledger_envelope",
    "serialize_paper_ledger_recovery_manifest",
    "serialize_paper_ledger_record",
    "simulate_paper_purchase",
    "simulate_paper_sale",
    "verify_paper_ledger_archive_chain",
    "verify_paper_ledger_backup_against_manifest",
    "verify_paper_ledger_recovery_manifest",
    "verify_paper_ledger_record",
    "write_encrypted_paper_ledger_record",
]
