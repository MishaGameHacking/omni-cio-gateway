"""Pack only signed CI inputs, with exact source and per-file integrity checks."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import zipfile

from timeweb_actions_probe import MAX_BYTES, ProbeError, decode_response

MAX_ARCHIVE_BYTES = 512 * 1024**2
PREVIOUS_FILE = "previous.apk"
MANIFEST_FILE = "manifest.json"
FILES = (
    "app/build/outputs/apk/preview/app-preview.apk",
    "app/build/outputs/apk/debug/app-debug.apk",
    "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk",
    PREVIOUS_FILE,
)


def require_head() -> str:
    head = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[a-f0-9]{40}", head):
        raise ProbeError("transfer_source_identity_required")
    return head


def regular_file(root: Path, relative: str) -> Path:
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ProbeError("transfer_file_escapes_checkout")
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ProbeError("transfer_link_refused")
    return path


def pack(root: Path, previous: Path) -> bytes:
    require_head()
    buffer = io.BytesIO()
    manifest = {"head": os.environ["GITHUB_SHA"], "files": {}}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        total = 0
        for name in FILES:
            source = previous if name == PREVIOUS_FILE else regular_file(root, name)
            if source.is_symlink() or not source.is_file():
                raise ProbeError("transfer_source_missing_or_link")
            size = source.stat().st_size
            total += size
            if size <= 0 or total > MAX_ARCHIVE_BYTES - MAX_BYTES:
                raise ProbeError("transfer_payload_size_invalid")
            data = source.read_bytes()
            if len(data) != size:
                raise ProbeError("transfer_source_changed")
            manifest["files"][name] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest()}
            archive.writestr(name, data)
        archive.writestr(MANIFEST_FILE, json.dumps(manifest, sort_keys=True))
    return buffer.getvalue()


def unpack(data: bytes, root: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if (len(entries) != len(FILES) + 1 or {entry.filename for entry in entries} != {*FILES, MANIFEST_FILE}
                or sum(entry.file_size for entry in entries) > MAX_ARCHIVE_BYTES
                or archive.getinfo(MANIFEST_FILE).file_size > MAX_BYTES):
            raise ProbeError("transfer_archive_members_invalid")
        manifest = decode_response(archive.read(MANIFEST_FILE))
        if manifest.get("head") != os.environ.get("GITHUB_SHA") or set(manifest.get("files", {})) != set(FILES):
            raise ProbeError("transfer_manifest_identity_mismatch")
        payload = {}
        for name in FILES:
            content = archive.read(name)
            record = manifest["files"][name]
            if record != {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}:
                raise ProbeError("transfer_manifest_digest_mismatch")
            payload[name] = content
        # Validate all content before creating any output. No archive paths are extracted.
        for name, content in payload.items():
            destination = regular_file(root, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("pack", "unpack"))
    args = parser.parse_args()
    require_head()
    root = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    archive = Path(os.environ["RUNNER_TEMP"]) / "ci-handoff.zip"
    if archive.is_symlink():
        raise ProbeError("transfer_archive_link_refused")
    if args.command == "pack":
        data = pack(root, Path(os.environ["PREVIOUS_APK"]).resolve(strict=True))
        archive.write_bytes(data)
    else:
        size = archive.stat().st_size
        if not 0 < size <= MAX_ARCHIVE_BYTES:
            raise ProbeError("transfer_archive_size_invalid")
        unpack(archive.read_bytes(), root)
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
            output.write("PREVIOUS_APK=" + str(root / PREVIOUS_FILE) + "\n")
    print("CI_APK_ARCHIVE=" + args.command + "_exact_head_verified", flush=True)


if __name__ == "__main__":
    main()
