from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "architecture" / "V10_WP10_RECOVERY_CONTRACT.json"
SAFE_BACKUP_CLASSES = {
    "POSTGRES_LOGICAL_PRIVATE_STATE",
    "POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
}
SAFE_RETENTION_CLASSES = {"RECENT"}
SAFE_POSTGRES_VERSION = re.compile(r"^18(?:\.[0-9]{1,3}){0,2}$")


class BackupBundleError(RuntimeError):
    pass


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BackupBundleError("CONTRACT_NOT_OBJECT")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackupBundleError("TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None:
        raise BackupBundleError("TIMESTAMP_NOT_TIMEZONE_AWARE")
    return parsed.astimezone(UTC)


def _is_reparse_point(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        attributes = path.stat(follow_symlinks=False).st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _require_regular_file(path: Path, code: str) -> None:
    if path.is_symlink() or _is_reparse_point(path) or not path.is_file():
        raise BackupBundleError(code)


def _require_directory(path: Path, code: str) -> None:
    if path.is_symlink() or _is_reparse_point(path) or not path.is_dir():
        raise BackupBundleError(code)


def _fsync_file(path: Path) -> None:
    with path.open("rb+") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _archive_pattern(contract: dict[str, Any]) -> re.Pattern[str]:
    return re.compile(f"^{contract['bundle']['archive_name_pattern']}$")


def _manifest_path(archive_path: Path, contract: dict[str, Any]) -> Path:
    return archive_path.with_name(
        f"{archive_path.name}{contract['bundle']['manifest_suffix']}"
    )


def _atomic_write_json(path: Path, payload: dict[str, Any], suffix: str) -> None:
    partial = path.with_name(f"{path.name}{suffix}")
    partial.unlink(missing_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
    with partial.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)
    _fsync_directory(path.parent)


def validate_manifest(manifest: dict[str, Any], contract: dict[str, Any]) -> None:
    allowed = set(contract["bundle"]["allowed_manifest_fields"])
    if set(manifest) != allowed:
        missing = sorted(allowed - set(manifest))
        extra = sorted(set(manifest) - allowed)
        if missing:
            raise BackupBundleError(f"MANIFEST_FIELD_MISSING:{missing[0]}")
        raise BackupBundleError(f"MANIFEST_FIELD_NOT_ALLOWED:{extra[0]}")

    forbidden_tokens = {
        str(item).lower() for item in contract["bundle"]["forbidden_manifest_tokens"]
    }
    for key in manifest:
        lowered = key.lower()
        if any(token in lowered for token in forbidden_tokens):
            raise BackupBundleError(f"MANIFEST_FORBIDDEN_FIELD:{key}")

    if manifest["schema_version"] != "1":
        raise BackupBundleError("MANIFEST_SCHEMA_VERSION_INVALID")
    if manifest["backup_class"] not in SAFE_BACKUP_CLASSES:
        raise BackupBundleError("MANIFEST_BACKUP_CLASS_INVALID")
    if manifest["archive_format"] != "CUSTOM":
        raise BackupBundleError("MANIFEST_ARCHIVE_FORMAT_INVALID")
    if manifest["retention_class"] not in SAFE_RETENTION_CLASSES:
        raise BackupBundleError("MANIFEST_RETENTION_CLASS_INVALID")
    if manifest["postgres_major"] != 18:
        raise BackupBundleError("MANIFEST_POSTGRES_MAJOR_INVALID")

    version = manifest["postgres_version_class"]
    if not isinstance(version, str) or not SAFE_POSTGRES_VERSION.fullmatch(version):
        raise BackupBundleError("MANIFEST_POSTGRES_VERSION_INVALID")

    archive_name = manifest["archive_name"]
    if not isinstance(archive_name, str) or Path(archive_name).name != archive_name:
        raise BackupBundleError("MANIFEST_ARCHIVE_PATH_INVALID")
    if not _archive_pattern(contract).fullmatch(archive_name):
        raise BackupBundleError("MANIFEST_ARCHIVE_NAME_INVALID")

    digest = manifest["archive_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise BackupBundleError("MANIFEST_SHA256_INVALID")
    size = manifest["archive_size_bytes"]
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise BackupBundleError("MANIFEST_ARCHIVE_SIZE_INVALID")
    _parse_utc(str(manifest["created_at_utc"]))


def build_manifest(
    archive_path: Path,
    *,
    backup_class: str,
    postgres_version_class: str,
    retention_class: str = "RECENT",
    created_at: datetime | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = contract or load_contract()
    _require_regular_file(archive_path, "ARCHIVE_NOT_REGULAR_FILE")
    if backup_class not in SAFE_BACKUP_CLASSES:
        raise BackupBundleError("BACKUP_CLASS_INVALID")
    if not SAFE_POSTGRES_VERSION.fullmatch(postgres_version_class):
        raise BackupBundleError("POSTGRES_VERSION_CLASS_INVALID")
    if retention_class not in SAFE_RETENTION_CLASSES:
        raise BackupBundleError("RETENTION_CLASS_INVALID")

    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    digest = _sha256(archive_path)
    archive_name = f"wp10-{timestamp:%Y%m%dT%H%M%SZ}-{digest[:12]}.dump"
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "backup_class": backup_class,
        "created_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "archive_name": archive_name,
        "archive_sha256": digest,
        "archive_size_bytes": archive_path.stat().st_size,
        "postgres_major": 18,
        "postgres_version_class": postgres_version_class,
        "archive_format": "CUSTOM",
        "retention_class": retention_class,
    }
    validate_manifest(manifest, policy)
    return manifest


def load_manifest(path: Path, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = contract or load_contract()
    _require_regular_file(path, "MANIFEST_NOT_REGULAR_FILE")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupBundleError("MANIFEST_READ_INVALID") from exc
    if not isinstance(payload, dict):
        raise BackupBundleError("MANIFEST_NOT_OBJECT")
    validate_manifest(payload, policy)
    return payload


def verify_bundle(
    archive_path: Path,
    manifest_path: Path,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = contract or load_contract()
    _require_regular_file(archive_path, "ARCHIVE_NOT_REGULAR_FILE")
    manifest = load_manifest(manifest_path, policy)
    if archive_path.name != manifest["archive_name"]:
        raise BackupBundleError("ARCHIVE_MANIFEST_NAME_MISMATCH")
    if archive_path.stat().st_size != manifest["archive_size_bytes"]:
        raise BackupBundleError("ARCHIVE_SIZE_MISMATCH")
    if _sha256(archive_path) != manifest["archive_sha256"]:
        raise BackupBundleError("ARCHIVE_SHA256_MISMATCH")
    return manifest


def finalize_archive(
    staging_archive: Path,
    output_dir: Path,
    *,
    backup_class: str,
    postgres_version_class: str,
    created_at: datetime | None = None,
    contract: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    policy = contract or load_contract()
    _require_regular_file(staging_archive, "STAGING_ARCHIVE_NOT_REGULAR_FILE")
    output_dir.mkdir(parents=True, exist_ok=True)
    _require_directory(output_dir, "OUTPUT_DIRECTORY_INVALID")

    manifest = build_manifest(
        staging_archive,
        backup_class=backup_class,
        postgres_version_class=postgres_version_class,
        created_at=created_at,
        contract=policy,
    )
    final_archive = output_dir / manifest["archive_name"]
    final_manifest = _manifest_path(final_archive, policy)
    if final_archive.exists() or final_manifest.exists():
        raise BackupBundleError("FINAL_BUNDLE_ALREADY_EXISTS")

    suffix = policy["bundle"]["temporary_suffix"]
    partial_archive = final_archive.with_name(f"{final_archive.name}{suffix}")
    partial_archive.unlink(missing_ok=True)
    shutil.copyfile(staging_archive, partial_archive, follow_symlinks=False)
    _fsync_file(partial_archive)
    if partial_archive.stat().st_size != manifest["archive_size_bytes"]:
        partial_archive.unlink(missing_ok=True)
        raise BackupBundleError("STAGING_COPY_SIZE_MISMATCH")
    if _sha256(partial_archive) != manifest["archive_sha256"]:
        partial_archive.unlink(missing_ok=True)
        raise BackupBundleError("STAGING_COPY_HASH_MISMATCH")
    os.replace(partial_archive, final_archive)
    _fsync_directory(output_dir)
    _atomic_write_json(final_manifest, manifest, suffix)
    verify_bundle(final_archive, final_manifest, contract=policy)
    return final_archive, final_manifest


def atomic_copy_bundle(
    archive_path: Path,
    manifest_path: Path,
    target_dir: Path,
    *,
    contract: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    policy = contract or load_contract()
    manifest = verify_bundle(archive_path, manifest_path, contract=policy)
    _require_directory(target_dir, "TARGET_DIRECTORY_INVALID")

    final_archive = target_dir / manifest["archive_name"]
    final_manifest = _manifest_path(final_archive, policy)
    if final_archive.exists() or final_manifest.exists():
        raise BackupBundleError("TARGET_BUNDLE_ALREADY_EXISTS")

    suffix = policy["bundle"]["temporary_suffix"]
    partial_archive = final_archive.with_name(f"{final_archive.name}{suffix}")
    partial_manifest = final_manifest.with_name(f"{final_manifest.name}{suffix}")
    partial_archive.unlink(missing_ok=True)
    partial_manifest.unlink(missing_ok=True)

    try:
        shutil.copyfile(archive_path, partial_archive, follow_symlinks=False)
        _fsync_file(partial_archive)
        if partial_archive.stat().st_size != manifest["archive_size_bytes"]:
            raise BackupBundleError("TARGET_COPY_SIZE_MISMATCH")
        if _sha256(partial_archive) != manifest["archive_sha256"]:
            raise BackupBundleError("TARGET_COPY_HASH_MISMATCH")

        shutil.copyfile(manifest_path, partial_manifest, follow_symlinks=False)
        _fsync_file(partial_manifest)
        copied_manifest = load_manifest(partial_manifest, policy)
        if copied_manifest != manifest:
            raise BackupBundleError("TARGET_MANIFEST_MISMATCH")

        os.replace(partial_archive, final_archive)
        os.replace(partial_manifest, final_manifest)
        _fsync_directory(target_dir)
    except Exception:
        partial_archive.unlink(missing_ok=True)
        partial_manifest.unlink(missing_ok=True)
        raise

    verify_bundle(final_archive, final_manifest, contract=policy)
    return final_archive, final_manifest


def prune_retention(
    target_dir: Path,
    *,
    now: datetime | None = None,
    contract: dict[str, Any] | None = None,
) -> list[str]:
    policy = contract or load_contract()
    _require_directory(target_dir, "TARGET_DIRECTORY_INVALID")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    max_count = int(policy["retention"]["maximum_successful_bundles_per_target"])
    max_age = timedelta(days=int(policy["retention"]["maximum_age_days"]))
    manifest_suffix = policy["bundle"]["manifest_suffix"]

    verified: list[tuple[datetime, Path, Path]] = []
    for manifest_path in target_dir.glob(f"wp10-*.dump{manifest_suffix}"):
        try:
            manifest = load_manifest(manifest_path, policy)
            archive_path = target_dir / manifest["archive_name"]
            verify_bundle(archive_path, manifest_path, contract=policy)
            verified.append(
                (_parse_utc(manifest["created_at_utc"]), archive_path, manifest_path)
            )
        except BackupBundleError:
            continue

    verified.sort(key=lambda item: item[0], reverse=True)
    if len(verified) <= 1:
        return []

    removals: list[tuple[datetime, Path, Path]] = []
    for index, item in enumerate(verified):
        created_at, _, _ = item
        if index == 0:
            continue
        if index >= max_count or current - created_at > max_age:
            removals.append(item)

    removed: list[str] = []
    for _, archive_path, manifest_path in removals:
        verify_bundle(archive_path, manifest_path, contract=policy)
        name = archive_path.name
        manifest_path.unlink()
        archive_path.unlink()
        removed.append(name)
    if removed:
        _fsync_directory(target_dir)
    return removed


def _metadata_path_is_allowed(relative_path: Path, contract: dict[str, Any]) -> bool:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return False
    forbidden = {
        str(item).lower()
        for item in contract["private_metadata"]["forbidden_path_tokens"]
    }
    components = [part.lower() for part in relative_path.parts]
    return not any(
        any(token in component for token in forbidden) for component in components
    )


def create_metadata_archive(
    source_root: Path,
    relative_paths: Iterable[Path],
    output_path: Path,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = contract or load_contract()
    _require_directory(source_root, "METADATA_SOURCE_ROOT_INVALID")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() or output_path.is_symlink():
        raise BackupBundleError("METADATA_OUTPUT_EXISTS")

    entries: list[dict[str, Any]] = []
    files: list[tuple[Path, Path]] = []
    for requested in relative_paths:
        relative = Path(requested)
        if not _metadata_path_is_allowed(relative, policy):
            raise BackupBundleError("METADATA_PATH_FORBIDDEN")
        source = source_root / relative
        _require_regular_file(source, "METADATA_SOURCE_NOT_REGULAR_FILE")
        files.append((source, relative))
        entries.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256(source),
                "size_bytes": source.stat().st_size,
            }
        )

    entries.sort(key=lambda item: item["path"])
    manifest = {"schema_version": "1", "files": entries}
    suffix = policy["bundle"]["temporary_suffix"]
    partial = output_path.with_name(f"{output_path.name}{suffix}")
    partial.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "metadata-manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            )
            for source, relative in sorted(files, key=lambda item: item[1].as_posix()):
                archive.write(source, arcname=f"payload/{relative.as_posix()}")
        _fsync_file(partial)
        os.replace(partial, output_path)
        _fsync_directory(output_path.parent)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    verify_metadata_archive(output_path, contract=policy)
    return manifest


def verify_metadata_archive(
    archive_path: Path,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = contract or load_contract()
    _require_regular_file(archive_path, "METADATA_ARCHIVE_NOT_REGULAR_FILE")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            names = archive.namelist()
            if "metadata-manifest.json" not in names:
                raise BackupBundleError("METADATA_MANIFEST_MISSING")
            for name in names:
                candidate = Path(name.replace("\\", "/"))
                if candidate.is_absolute() or ".." in candidate.parts:
                    raise BackupBundleError("METADATA_ARCHIVE_PATH_TRAVERSAL")
            manifest = json.loads(archive.read("metadata-manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != "1":
                raise BackupBundleError("METADATA_MANIFEST_INVALID")
            files = manifest.get("files")
            if not isinstance(files, list):
                raise BackupBundleError("METADATA_FILE_LIST_INVALID")
            expected_names = {"metadata-manifest.json"}
            for item in files:
                if not isinstance(item, dict) or set(item) != {
                    "path",
                    "sha256",
                    "size_bytes",
                }:
                    raise BackupBundleError("METADATA_ENTRY_INVALID")
                relative = Path(str(item["path"]))
                if not _metadata_path_is_allowed(relative, policy):
                    raise BackupBundleError("METADATA_PATH_FORBIDDEN")
                member = f"payload/{relative.as_posix()}"
                expected_names.add(member)
                payload = archive.read(member)
                if len(payload) != item["size_bytes"]:
                    raise BackupBundleError("METADATA_SIZE_MISMATCH")
                if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                    raise BackupBundleError("METADATA_HASH_MISMATCH")
            if set(names) != expected_names:
                raise BackupBundleError("METADATA_ARCHIVE_UNDECLARED_MEMBER")
            return manifest
    except zipfile.BadZipFile as exc:
        raise BackupBundleError("METADATA_ARCHIVE_INVALID") from exc


def _command_create(args: argparse.Namespace) -> int:
    archive, manifest = finalize_archive(
        args.staging_archive,
        args.output_dir,
        backup_class=args.backup_class,
        postgres_version_class=args.postgres_version_class,
    )
    print(f"WP10_BUNDLE_CREATED={archive.name}")
    print(f"WP10_MANIFEST_CREATED={manifest.name}")
    return 0


def _command_verify(args: argparse.Namespace) -> int:
    verify_bundle(args.archive, args.manifest)
    print("WP10_BUNDLE_VERIFY=PASS")
    return 0


def _command_copy(args: argparse.Namespace) -> int:
    archive, manifest = atomic_copy_bundle(args.archive, args.manifest, args.target_dir)
    print(f"WP10_OFFDEVICE_COPY={archive.name}")
    print(f"WP10_OFFDEVICE_MANIFEST={manifest.name}")
    return 0


def _command_prune(args: argparse.Namespace) -> int:
    removed = prune_retention(args.target_dir)
    print(f"WP10_RETENTION_REMOVED={len(removed)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WP10 backup bundle integrity engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--staging-archive", required=True, type=Path)
    create_parser.add_argument("--output-dir", required=True, type=Path)
    create_parser.add_argument(
        "--backup-class", required=True, choices=sorted(SAFE_BACKUP_CLASSES)
    )
    create_parser.add_argument("--postgres-version-class", required=True)
    create_parser.set_defaults(handler=_command_create)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--archive", required=True, type=Path)
    verify_parser.add_argument("--manifest", required=True, type=Path)
    verify_parser.set_defaults(handler=_command_verify)

    copy_parser = subparsers.add_parser("copy")
    copy_parser.add_argument("--archive", required=True, type=Path)
    copy_parser.add_argument("--manifest", required=True, type=Path)
    copy_parser.add_argument("--target-dir", required=True, type=Path)
    copy_parser.set_defaults(handler=_command_copy)

    prune_parser = subparsers.add_parser("prune")
    prune_parser.add_argument("--target-dir", required=True, type=Path)
    prune_parser.set_defaults(handler=_command_prune)

    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
