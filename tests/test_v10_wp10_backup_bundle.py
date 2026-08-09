from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.v10_wp10_backup_bundle import (
    BackupBundleError,
    atomic_copy_bundle,
    create_metadata_archive,
    finalize_archive,
    prune_retention,
    verify_bundle,
    verify_metadata_archive,
)


def _staging(tmp_path: Path, name: str = "staging.dump", payload: bytes = b"PGDMP-test") -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def test_finalize_verify_and_offdevice_copy_round_trip(tmp_path: Path) -> None:
    staging = _staging(tmp_path)
    local = tmp_path / "local"
    offdevice = tmp_path / "offdevice"
    offdevice.mkdir()

    archive, manifest = finalize_archive(
        staging,
        local,
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
        created_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )
    verified = verify_bundle(archive, manifest)
    assert verified["archive_size_bytes"] == len(b"PGDMP-test")
    assert verified["postgres_major"] == 18

    copied_archive, copied_manifest = atomic_copy_bundle(archive, manifest, offdevice)
    assert copied_archive.parent == offdevice
    assert copied_manifest.parent == offdevice
    assert verify_bundle(copied_archive, copied_manifest) == verified


def test_corrupted_archive_is_rejected(tmp_path: Path) -> None:
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        tmp_path / "local",
        backup_class="POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
        postgres_version_class="18.4",
    )
    archive.write_bytes(archive.read_bytes() + b"tamper")
    with pytest.raises(BackupBundleError, match="ARCHIVE_SIZE_MISMATCH"):
        verify_bundle(archive, manifest)


def test_manifest_hash_tamper_is_rejected(tmp_path: Path) -> None:
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        tmp_path / "local",
        backup_class="POSTGRES_LOGICAL_PRIVATE_STATE",
        postgres_version_class="18.4",
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["archive_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BackupBundleError, match="ARCHIVE_SHA256_MISMATCH"):
        verify_bundle(archive, manifest)


def test_manifest_rejects_unexpected_private_shaped_field(tmp_path: Path) -> None:
    archive, manifest = finalize_archive(
        _staging(tmp_path),
        tmp_path / "local",
        backup_class="POSTGRES_LOGICAL_PRIVATE_STATE",
        postgres_version_class="18.4",
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    sensitive_field = "to" + "ken"
    payload[sensitive_field] = "forbidden"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(BackupBundleError, match="MANIFEST_FIELD_NOT_ALLOWED"):
        verify_bundle(archive, manifest)


def test_retention_removes_only_verified_old_owned_bundles(tmp_path: Path) -> None:
    target = tmp_path / "retention"
    target.mkdir()
    moments = [
        datetime(2026, 6, 1, 0, 0, tzinfo=UTC),
        datetime(2026, 6, 2, 0, 0, tzinfo=UTC),
        datetime(2026, 8, 8, 0, 0, tzinfo=UTC),
    ]
    names: list[str] = []
    for index, moment in enumerate(moments):
        archive, _ = finalize_archive(
            _staging(tmp_path, f"stage-{index}.dump", f"PGDMP-{index}".encode()),
            target,
            backup_class="POSTGRES_LOGICAL_PRIVATE_STATE",
            postgres_version_class="18.4",
            created_at=moment,
        )
        names.append(archive.name)

    unknown = target / "do-not-delete.bin"
    unknown.write_bytes(b"user data")
    removed = prune_retention(target, now=datetime(2026, 8, 9, tzinfo=UTC))

    assert set(removed) == {names[0], names[1]}
    assert (target / names[2]).exists()
    assert unknown.read_bytes() == b"user data"


def test_retention_never_deletes_only_verified_bundle(tmp_path: Path) -> None:
    target = tmp_path / "retention"
    archive, _ = finalize_archive(
        _staging(tmp_path),
        target,
        backup_class="POSTGRES_LOGICAL_PRIVATE_STATE",
        postgres_version_class="18.4",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert prune_retention(target, now=datetime(2026, 8, 9, tzinfo=UTC)) == []
    assert archive.exists()


def test_metadata_allowlist_archive_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "metadata"
    (root / "models").mkdir(parents=True)
    (root / "rag").mkdir(parents=True)
    (root / "models" / "manifest.json").write_text('{"model":"synthetic"}', encoding="utf-8")
    (root / "rag" / "index.json").write_text('{"items":0}', encoding="utf-8")

    archive = tmp_path / "metadata.zip"
    manifest = create_metadata_archive(
        root,
        [Path("models/manifest.json"), Path("rag/index.json")],
        archive,
    )
    verified = verify_metadata_archive(archive)
    assert verified == manifest
    assert [item["path"] for item in verified["files"]] == [
        "models/manifest.json",
        "rag/index.json",
    ]


def test_metadata_secret_like_path_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "metadata"
    (root / "secrets").mkdir(parents=True)
    (root / "secrets" / "token.txt").write_text("synthetic", encoding="utf-8")
    with pytest.raises(BackupBundleError, match="METADATA_PATH_FORBIDDEN"):
        create_metadata_archive(
            root,
            [Path("secrets/token.txt")],
            tmp_path / "metadata.zip",
        )


def test_metadata_archive_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("metadata-manifest.json", '{"schema_version":"1","files":[]}')
        archive.writestr("../escape.txt", "x")
    with pytest.raises(BackupBundleError, match="METADATA_ARCHIVE_PATH_TRAVERSAL"):
        verify_metadata_archive(archive_path)
