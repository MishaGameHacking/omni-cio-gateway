from __future__ import annotations

import os
from pathlib import Path

import omni_cio.persistence.hosted_recovery_atomic_v1 as atomic


def test_hard_link_path_and_open_handle_share_validation_snapshot(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.dump"
    linked = tmp_path / "linked.dump"
    source.write_bytes(b"synthetic-recovery-archive")
    os.link(source, linked, follow_symlinks=False)

    path_metadata = linked.stat(follow_symlinks=False)
    with linked.open("rb") as handle:
        handle_metadata = os.fstat(handle.fileno())

    assert atomic._identity(path_metadata) == atomic._identity(handle_metadata)
    assert atomic._snapshot(path_metadata) == atomic._snapshot(handle_metadata)
