"""Offline artifact rejection tests. Synthetic PNGs are not emulator evidence."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

SCRIPTS = Path(__file__).resolve().parents[1]
for directory in (SCRIPTS, SCRIPTS.parents[1]):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from backend.tests.android_runtime_fixtures import automation_report

SPEC = importlib.util.spec_from_file_location("automation_artifacts", SCRIPTS / "automation_artifacts.py")
artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(artifacts)


def synthetic_png(width=240, height=320):
    def chunk(kind, raw):
        return struct.pack(">I", len(raw)) + kind + raw + struct.pack(">I", zlib.crc32(kind + raw))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = (b"\0" + bytes((15, 23, 42)) * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class AutomationArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "synthetic-screens"
        self.source.mkdir()
        self.attempt = self.root / "attempt-1"
        self.attempt.mkdir()
        self.destination = self.attempt / "automation-ui"
        self.report = automation_report()
        raw = synthetic_png()
        for row in self.report["cases"]:
            row.update(width=240, height=320, screenshot_sha256=hashlib.sha256(raw).hexdigest())
            (self.source / row["screenshot"]).write_bytes(raw)

    def archive(self):
        artifacts.archive_automation_artifacts(self.report, self.source, self.destination)

    def test_complete_archive_rechecks_actual_bytes_and_all_case_files(self):
        self.archive()
        self.assertEqual(len(list(self.destination.iterdir())), 27)
        artifacts.verify_automation_artifacts(self.report, self.destination)
        archived = json.loads((self.destination / artifacts.REPORT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(archived, self.report)

    def test_missing_current_capture_cannot_be_replaced_by_a_receipt(self):
        (self.source / self.report["cases"][0]["screenshot"]).unlink()
        with self.assertRaises(ValueError):
            self.archive()

    def test_changed_pixels_or_mismatching_dimensions_are_rejected(self):
        row = self.report["cases"][0]
        path = self.source / row["screenshot"]
        path.write_bytes(synthetic_png(241, 321))
        with self.assertRaises(ValueError):
            self.archive()
        self.destination.rmdir()
        row["screenshot_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            self.archive()

    def test_a_matching_digest_does_not_make_invalid_png_bytes_valid(self):
        row = self.report["cases"][0]
        raw = b"not a PNG"
        (self.source / row["screenshot"]).write_bytes(raw)
        row["screenshot_sha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(AssertionError):
            self.archive()

    def test_archive_tampering_or_extra_files_remain_release_failures(self):
        self.archive()
        filename = self.report["cases"][0]["screenshot"]
        (self.destination / filename).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            artifacts.verify_automation_artifacts(self.report, self.destination)
        (self.destination / filename).write_bytes((self.source / filename).read_bytes())
        (self.destination / "unexpected.png").write_bytes(b"extra")
        with self.assertRaises(ValueError):
            artifacts.verify_automation_artifacts(self.report, self.destination)

    def test_archived_report_cannot_substitute_different_observations(self):
        self.archive()
        changed = deepcopy(self.report)
        changed["cases"][0]["after"]["requests"] += 1
        (self.destination / artifacts.REPORT_NAME).write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(ValueError):
            artifacts.verify_automation_artifacts(self.report, self.destination)

    def test_old_attempt_archive_cannot_be_reused(self):
        self.archive()
        with self.assertRaises(FileExistsError):
            self.archive()

    def test_link_metadata_cannot_escape_the_owned_attempt(self):
        # Exercise rejection on both platforms without requiring symlink privileges.
        filename = self.report["cases"][0]["screenshot"]
        for target in (self.source / filename, self.destination):
            with patch.object(Path, "is_symlink", lambda path: path == target):
                with self.assertRaises(ValueError):
                    self.archive()
            if self.destination.exists():
                self.destination.rmdir()


if __name__ == "__main__":
    unittest.main()
