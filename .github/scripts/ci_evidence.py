"""Keep reproducible CI evidence on the owner's runners without Actions storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

PATTERNS = {
    "postgres": ("artifacts/postgres/*.log", "artifacts/postgres/pytest.xml"),
    "frontend": ("artifacts/frontend/*.png", "artifacts/frontend/*.json"),
    "android": ("app/build/outputs/apk/debug/*.apk",
                "app/build/outputs/apk/debug/output-metadata.json",
                "artifacts/android/*.txt"),
}
RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_FILE_BYTES = 100 * 1024 * 1024


def evidence_files(root: Path, kind: str) -> list[Path]:
    files = sorted({path for pattern in PATTERNS[kind] for path in root.glob(pattern)})
    for path in files:
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("Evidence must remain inside the checkout")
        if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Evidence is not a bounded regular file")
    return files


def require_complete(files: list[Path], kind: str) -> None:
    names = {path.name for path in files}
    required = {
        "postgres": {"pytest.xml"},
        "frontend": {"public-requests.json"} | {
            f"public-{width}.png" for width in (1440, 1363, 1024, 901, 900, 768, 390, 320)
        },
        "android": {"app-debug.apk", "output-metadata.json", "apksigner.txt"},
    }
    if not required[kind].issubset(names):
        raise ValueError(f"Successful {kind} check is missing required evidence")


def archive(root: Path, cache: Path, kind: str, identity: dict[str, str]) -> dict[str, Any]:
    for field in ("run_id", "attempt"):
        if not re.fullmatch(r"[1-9][0-9]*", identity[field]):
            raise ValueError("Invalid Actions run identity")
    for field in ("source_sha", "workflow_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", identity[field]):
            raise ValueError("Invalid source identity")
    files = evidence_files(root, kind)
    if identity["outcome"] == "success":
        require_complete(files, kind)
    destination = cache / "omnicio-ci-evidence"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{kind}-{identity['run_id']}-{identity['attempt']}.zip"
    manifest: dict[str, Any] = {"schema": 1, "kind": kind, **identity, "files": []}
    temporary = target.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for path in files:
                data = path.read_bytes()
                name = path.relative_to(root).as_posix()
                manifest["files"].append({
                    "path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                })
                output.writestr(name, data)
            output.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(temporary) as check:
            if check.testzip() is not None:
                raise ValueError("Evidence archive verification failed")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    # Only this helper's reproducible, seven-day cache is pruned, never GitHub history.
    for old in destination.glob("*.zip"):
        if (re.fullmatch(r"(postgres|frontend|android)-[0-9]+-[0-9]+\.zip", old.name)
                and not old.is_symlink() and time.time() - old.stat().st_mtime > RETENTION_SECONDS):
            old.unlink()
    manifest["archive"] = str(target)
    manifest["archive_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    return manifest


def report(manifest: dict[str, Any], root: Path) -> str:
    lines = [f"### {manifest['kind']} evidence", "",
             f"Source: `{manifest['source_sha']}`; outcome: `{manifest['outcome']}`.",
             f"Runner: `{manifest['runner']}`; local archive: `{manifest['archive']}`.",
             f"Archive SHA-256: `{manifest['archive_sha256']}`.",
             "Retained on this self-hosted runner for 7 days; no Actions artifact storage.", ""]
    junit = root / "artifacts/postgres/pytest.xml"
    if manifest["kind"] == "postgres" and junit.is_file():
        suites = ElementTree.fromstring(junit.read_bytes()).iter("testsuite")
        for suite in suites:
            counts = {key: suite.get(key, "0")
                      for key in ("tests", "failures", "errors", "skipped")}
            lines.append("Pytest: " + json.dumps(counts, sort_keys=True))
    lines.extend(["", "```json", json.dumps(manifest, indent=2), "```", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=PATTERNS)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    identity = {
        "run_id": os.environ["GITHUB_RUN_ID"], "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "source_sha": os.environ.get("SOURCE_SHA") or os.environ["GITHUB_SHA"],
        "workflow_sha": os.environ["GITHUB_SHA"], "runner": os.environ["RUNNER_NAME"],
        "outcome": os.environ["EVIDENCE_OUTCOME"],
    }
    manifest = archive(root, Path(os.environ["RUNNER_TOOL_CACHE"]), args.kind, identity)
    summary = report(manifest, root)
    print(summary)
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
        output.write(summary)


if __name__ == "__main__":
    main()
