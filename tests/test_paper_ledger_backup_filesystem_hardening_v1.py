from __future__ import annotations

import os
from pathlib import Path

import pytest

from omni_cio.paper.backup_v1 import (
    PaperLedgerBackupError,
    _prepare_backup,
    _read_secure_file,
    _roots_overlap,
)


def test_secure_backup_reader_rejects_hardlinked_file(tmp_path: Path) -> None:
    source = tmp_path / "source.plae"
    target = tmp_path / "target.plae"
    source.write_bytes(b"encrypted-envelope")
    os.chmod(source, 0o600)
    os.link(source, target)

    with pytest.raises(PaperLedgerBackupError, match="HARDLINK_FORBIDDEN"):
        _read_secure_file(target, maximum_size=1024)


def test_backup_root_rejects_broken_symlink(tmp_path: Path) -> None:
    target = tmp_path / "missing-target"
    backup = tmp_path / "backup"
    backup.symlink_to(target, target_is_directory=True)

    with pytest.raises(PaperLedgerBackupError, match="ROOT_SYMLINK_FORBIDDEN"):
        _prepare_backup(backup)


def test_backup_root_topology_rejects_nested_or_parent_paths(tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    primary.mkdir()
    resolved_primary = primary.resolve(strict=True)

    assert _roots_overlap(resolved_primary, primary / "nested-backup") is True
    assert _roots_overlap(resolved_primary, tmp_path) is True
    assert _roots_overlap(resolved_primary, tmp_path / "sibling-backup") is False
