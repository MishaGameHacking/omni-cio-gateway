"""Release only this checkout's reproducible intermediates after all APK builds.

APKs, test/lint reports, mappings, runtime evidence, SDKs, shared Gradle caches
and other runner workspaces are never cleanup targets. The runtime capacity
check remains mandatory after cleanup; this cannot manufacture a passing UI run.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
INTERMEDIATES = (
    "app/build/intermediates", "app/build/tmp",
    "ci-ui-driver/build/intermediates", "ci-ui-driver/build/tmp",
)
APKS = (
    "app/build/outputs/apk/debug/app-debug.apk",
    "app/build/outputs/apk/release/app-release-unsigned.apk",
    "app/build/outputs/apk/preview/app-preview.apk",
    "ci-ui-driver/build/outputs/apk/debug/ci-ui-driver-debug.apk",
)


def _regular_path(root: Path, relative: str) -> Path:
    path = root
    for component in Path(relative).parts:
        path /= component
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Build cleanup refuses links and reparse points")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError("Build cleanup requires regular files and directories")
    return path


def _apk_digests(root: Path) -> dict[str, str]:
    result = {}
    for relative in APKS:
        path = _regular_path(root, relative)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("All built APKs must exist before releasing intermediates")
        with path.open("rb") as source:
            result[relative] = hashlib.file_digest(source, "sha256").hexdigest()
    return result


def _validate_target(root: Path, relative: str) -> Path | None:
    target = root / relative
    # lexists semantics also reject a dangling symlink instead of skipping it.
    if not target.exists() and not target.is_symlink():
        return None
    target = _regular_path(root, relative)
    if not target.is_dir():
        raise ValueError("Build intermediate target must be a directory")
    for entry in target.rglob("*"):
        _regular_path(root, entry.relative_to(root).as_posix())
    return target


def release_intermediates(root: Path = ROOT) -> dict[str, object]:
    root = root.resolve(strict=True)
    repository = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=root,
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    if Path(repository).resolve() != root:
        raise ValueError("Build cleanup must run in its exact checkout root")
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", *INTERMEDIATES], cwd=root,
        check=True, capture_output=True, timeout=15,
    ).stdout
    if tracked:
        raise ValueError("Build cleanup refuses a target containing tracked source")
    before = _apk_digests(root)
    # Validate ALL targets before deleting any. Never follow a link to a shared
    # dependency, a neighboring runner, a source tree or an evidence directory.
    targets = [target for name in INTERMEDIATES
               if (target := _validate_target(root, name)) is not None]
    free_before = shutil.disk_usage(root).free
    removed = []
    for target in targets:
        relative = target.relative_to(root).as_posix()
        _validate_target(root, relative)
        shutil.rmtree(target)
        removed.append(relative)
    if _apk_digests(root) != before:
        raise RuntimeError("APK bytes changed while releasing build intermediates")
    return {"removed": removed, "apk_sha256": before,
            "free_bytes_before": free_before, "free_bytes_after": shutil.disk_usage(root).free}


if __name__ == "__main__":
    print("BUILD_INTERMEDIATES_RELEASED=" + json.dumps(release_intermediates(), sort_keys=True), flush=True)
