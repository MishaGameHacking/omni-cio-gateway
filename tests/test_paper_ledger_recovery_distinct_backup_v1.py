from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from omni_cio.paper.recovery_v1 import (
    PaperLedgerRecoveryError,
    build_paper_ledger_recovery_manifest,
)


class _UnusedKeyManager:
    def encrypt(self, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("encrypt must not be called")

    def decrypt(self, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("decrypt must not be called")


def test_recovery_manifest_rejects_same_primary_and_backup_root(tmp_path: Path) -> None:
    root = tmp_path / "same-archive"
    root.mkdir()

    with pytest.raises(PaperLedgerRecoveryError, match="BACKUP_ROOT_NOT_DISTINCT"):
        build_paper_ledger_recovery_manifest(
            root,
            root,
            key_manager=_UnusedKeyManager(),
            signing_keys={},
            manifest_signing_key=b"m" * 32,
            manifest_key_id="manifest-a",
            backup_reference="backup://same-root",
            created_at=datetime(2026, 7, 29, 12, 45, tzinfo=timezone.utc),
        )
