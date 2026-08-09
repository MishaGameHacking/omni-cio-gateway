from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.v10_wp10_backup_bundle import (
    BackupBundleError,
    atomic_copy_bundle,
    finalize_archive,
    load_contract,
    load_manifest,
    prune_retention,
    validate_manifest,
    verify_bundle,
)


def _staging(tmp_path: Path, payload: bytes = b"synthetic-postgres-custom-archive") -> Path:
    path = tmp_path / "staging.dump.partial"
    path.write_bytes(payload)
    return path


def test_finalize_and_verify_bundle(tmp_path: Path) -> None:
    output = tmp_path / "local"
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
        created_at=datetime(2026, 8, 9, 5, 0, tzinfo=UTC),
    )
    loaded = verify_bundle(archive, manifest)
    assert loaded["archive_name"] == archive.name
    assert loaded["archive_size_bytes"] == archive.stat().st_size
    assert len(loaded["archive_sha256"]) == 64
    assert loaded["backup_class"] == "POSTGRES_LOGICAL_RECOVERY_REHEARSAL"


def test_same_size_corruption_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "local"
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    payload = bytearray(archive.read_bytes())
    payload[0] ^= 0xFF
    archive.write_bytes(payload)
    with pytest.raises(BackupBundleError, match="ARCHIVE_SHA256_MISMATCH"):
        verify_bundle(archive, manifest)


def test_size_corruption_is_rejected_before_hash(tmp_path: Path) -> None:
    output = tmp_path / "local"
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    archive.write_bytes(archive.read_bytes() + b"tamper")
    with pytest.raises(BackupBundleError, match="ARCHIVE_SIZE_MISMATCH"):
        verify_bundle(archive, manifest)


def test_atomic_copy_rehashes_destination(tmp_path: Path) -> None:
    output = tmp_path / "local"
    target = tmp_path / "offdevice"
    target.mkdir()
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    copied_archive, copied_manifest = atomic_copy_bundle(archive, manifest, target)
    assert copied_archive.parent == target
    assert copied_manifest.parent == target
    assert verify_bundle(copied_archive, copied_manifest)["archive_sha256"] == load_manifest(
        manifest
    )["archive_sha256"]
    assert not list(target.glob("*.partial"))


def test_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    output = tmp_path / "local"
    archive, manifest_path = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archive_name"] = "../escape.dump"
    with pytest.raises(BackupBundleError, match="MANIFEST_ARCHIVE_NAME_INVALID"):
        validate_manifest(manifest, load_contract())
    assert archive.exists()


def test_manifest_rejects_unknown_field(tmp_path: Path) -> None:
    output = tmp_path / "local"
    _, manifest_path = finalize_archive(
        _staging(tmp_path),
        output,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["account_id"] = "forbidden"
    with pytest.raises(BackupBundleError, match="MANIFEST_FIELD_NOT_ALLOWED:account_id"):
        validate_manifest(manifest, load_contract())


def test_retention_keeps_newest_bounded_verified_bundles(tmp_path: Path) -> None:
    policy = copy.deepcopy(load_contract())
    policy["retention"]["maximum_successful_bundles_per_target"] = 2
    policy["retention"]["maximum_age_days"] = 30
    target = tmp_path / "target"
    target.mkdir()
    staging = _staging(tmp_path)

    created: list[Path] = []
    for day in (1, 2, 3):
        archive, _ = finalize_archive(
            staging,
            target,
            backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
            postgres_version_class="18.4",
            created_at=datetime(2026, 8, day, 5, 0, tzinfo=UTC),
            contract=policy,
        )
        created.append(archive)

    removed = prune_retention(
        target,
        now=datetime(2026, 8, 4, 5, 0, tzinfo=UTC),
        contract=policy,
    )
    assert removed == [created[0].name]
    assert not created[0].exists()
    assert created[1].exists()
    assert created[2].exists()


def test_retention_never_deletes_only_verified_bundle(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        target,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    removed = prune_retention(
        target,
        now=datetime(2026, 8, 9, tzinfo=UTC),
    )
    assert removed == []
    assert archive.exists()
    assert manifest.exists()


def test_retention_leaves_invalid_unowned_content_untouched(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    invalid = target / "wp10-20260809T050000Z-aaaaaaaaaaaa.dump.manifest.json"
    invalid.write_text("not-json", encoding="utf-8")
    unknown = target / "unowned.dump"
    unknown.write_bytes(b"unknown")
    assert prune_retention(target) == []
    assert invalid.exists()
    assert unknown.exists()
