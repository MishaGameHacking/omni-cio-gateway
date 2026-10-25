"""Persist and recheck the actual 26 native captures for one emulator attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

CHECKOUT = Path(__file__).resolve().parents[2]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))
from backend.automation_ui_evidence import validate_automation_report
from spatial_frame_evidence import read_screenshot

REPORT_NAME = "automation-verification.json"
MAX_REPORT_BYTES = 500_000


def _directory(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Automation evidence directory is missing or a symlink")
    return path.resolve(strict=True)


def _file(directory: Path, name: str) -> Path:
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != directory:
        raise ValueError("Automation evidence file is missing or escapes its directory")
    return path


def _bounded(path: Path, limit: int) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("Automation evidence file size is invalid")
    return raw


def _validate_report(report: dict) -> None:
    fixture = report.get("fixture_apk_sha256") if isinstance(report, dict) else None
    validate_automation_report(report, fixture)


def _check_image(directory: Path, row: dict) -> bytes:
    path = _file(directory, row["screenshot"])
    raw = _bounded(path, 2 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != row["screenshot_sha256"]:
        raise ValueError("Automation screenshot differs from the observed capture")
    image = read_screenshot(path)
    if (image.width, image.height) != (row["width"], row["height"]):
        raise ValueError("Automation screenshot dimensions differ from the native observation")
    return raw


def verify_automation_artifacts(report: dict, directory: Path) -> None:
    _validate_report(report)
    root = _directory(directory)
    expected = {REPORT_NAME, *(row["screenshot"] for row in report["cases"])}
    if {path.name for path in root.iterdir()} != expected:
        raise ValueError("Automation capture archive has missing or unexpected files")
    archived = json.loads(_bounded(_file(root, REPORT_NAME), MAX_REPORT_BYTES).decode("utf-8"))
    if archived != report:
        raise ValueError("Automation archive report differs from the installation receipt")
    for row in report["cases"]:
        _check_image(root, row)


def archive_automation_artifacts(report: dict, source: Path, destination: Path) -> None:
    _validate_report(report)
    original = _directory(source)
    parent = _directory(destination.parent)
    if destination.name != "automation-ui" or destination.is_symlink() or destination.resolve().parent != parent:
        raise ValueError("Automation archive destination is invalid")
    # Each fresh attempt owns a new archive. Never reuse a previous run's files.
    destination.mkdir(exist_ok=False)
    archive = _directory(destination)
    for row in report["cases"]:
        raw = _check_image(original, row)
        with (archive / row["screenshot"]).open("xb") as stream:
            stream.write(raw)
    with (archive / REPORT_NAME).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    verify_automation_artifacts(report, archive)
