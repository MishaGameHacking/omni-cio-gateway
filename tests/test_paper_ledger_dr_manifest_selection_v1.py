from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import omni_cio.paper.dr_readiness_v1 as dr_module
from omni_cio.contracts.v1.paper_dr import PaperDrBlocker


BASE = datetime(2026, 7, 29, 13, 0, tzinfo=timezone.utc)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _manifest_path(root: Path, digest: str) -> Path:
    path = root / f"recovery-00000001-{digest}.plrm"
    path.write_bytes(digest.encode("ascii"))
    return path


def test_authenticated_selector_chooses_unique_latest_created_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _manifest_path(tmp_path, DIGEST_A)
    second = _manifest_path(tmp_path, DIGEST_B)

    monkeypatch.setattr(
        dr_module,
        "_read_secure_manifest",
        lambda path: path.name.encode("ascii"),
    )
    monkeypatch.setattr(
        dr_module,
        "parse_paper_ledger_recovery_manifest_unverified",
        lambda serialized: SimpleNamespace(manifest_key_id="manifest-a"),
    )

    def _verify(serialized: bytes, *, manifest_signing_key: bytes):
        assert manifest_signing_key == b"m" * 32
        name = serialized.decode("ascii")
        digest = DIGEST_A if DIGEST_A in name else DIGEST_B
        created_at = BASE if digest == DIGEST_A else BASE + timedelta(minutes=1)
        return SimpleNamespace(
            latest_sequence=1,
            manifest_digest=digest,
            created_at=created_at,
        )

    monkeypatch.setattr(dr_module, "verify_paper_ledger_recovery_manifest", _verify)

    selection, blockers = dr_module._authenticate_latest_manifest(
        (first, second),
        manifest_signing_keys={"manifest-a": b"m" * 32},
    )

    assert blockers == set()
    assert selection is not None
    assert selection[1] == second
    assert selection[0].manifest_digest == DIGEST_B


def test_authenticated_selector_blocks_equal_latest_timestamps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _manifest_path(tmp_path, DIGEST_A)
    second = _manifest_path(tmp_path, DIGEST_B)

    monkeypatch.setattr(
        dr_module,
        "_read_secure_manifest",
        lambda path: path.name.encode("ascii"),
    )
    monkeypatch.setattr(
        dr_module,
        "parse_paper_ledger_recovery_manifest_unverified",
        lambda serialized: SimpleNamespace(manifest_key_id="manifest-a"),
    )

    def _verify(serialized: bytes, *, manifest_signing_key: bytes):
        assert manifest_signing_key == b"m" * 32
        name = serialized.decode("ascii")
        digest = DIGEST_A if DIGEST_A in name else DIGEST_B
        return SimpleNamespace(
            latest_sequence=1,
            manifest_digest=digest,
            created_at=BASE,
        )

    monkeypatch.setattr(dr_module, "verify_paper_ledger_recovery_manifest", _verify)

    selection, blockers = dr_module._authenticate_latest_manifest(
        (first, second),
        manifest_signing_keys={"manifest-a": b"m" * 32},
    )

    assert selection is None
    assert PaperDrBlocker.MANIFEST_AMBIGUOUS in blockers
