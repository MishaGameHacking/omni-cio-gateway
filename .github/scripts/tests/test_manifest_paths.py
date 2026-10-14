"""Real local filesystem tests; never publish or install an APK."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "manifest_paths", Path(__file__).resolve().parents[1] / "build_release_manifest.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

REPORT = "/".join((*module.ARTIFACT_PARTS, module.REPORT_NAME))
OUTPUT = "/".join((*module.ARTIFACT_PARTS, module.OUTPUT_NAME))


def report():
    return dict(version_code=23, version_name="0.6.0-preview",
                package="ru.omnicio.app.debug", min_sdk=33, sha256="a" * 64,
                certificate_sha256="b" * 64, bytes=4000, signature_v2=True,
                device_install_test="passed_on_emulators_not_a_physical_phone")


class ManifestPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        self.artifact = self.root.joinpath(*module.ARTIFACT_PARTS)
        self.artifact.mkdir(parents=True)
        self.report_path = self.artifact / module.REPORT_NAME
        self.output = self.artifact / module.OUTPUT_NAME
        self.report_path.write_text(json.dumps(report()), encoding="utf-8")

    def parse(self, source=REPORT, destination=OUTPUT):
        return module.argument_parser().parse_args(
            ["--report", source, "--output", destination, "--notes", "notes"])

    def test_documented_paths_accepted(self):
        self.assertEqual(self.parse().report, REPORT)

    def test_windows_spelling_accepted(self):
        source = REPORT.replace("/", "\\")
        destination = OUTPUT.replace("/", "\\")
        self.assertEqual(self.parse(source, destination).output, destination)

    def test_traversal_paths_rejected_before_io(self):
        for path in ("../escape", "app/build/../escape", "/tmp/escape", "C:\\escape",
                     "\\\\server\\share", OUTPUT + ":stream", "./" + OUTPUT):
            with self.subTest(path=path), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.parse(destination=path)
        self.assertFalse(self.output.exists())

    def test_arbitrary_report_cannot_be_read(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(source="/etc/passwd")

    def test_arbitrary_file_inside_checkout_is_also_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse(destination="app/build.gradle.kts")

    def test_fixed_output_written(self):
        result = module.write_preview_manifest(self.root, notes="Примечание")
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8")), result)
        self.assertEqual(result["notes"], "Примечание")

    def test_input_report_not_overwritten(self):
        previous = self.report_path.read_bytes()
        module.write_preview_manifest(self.root, notes="")
        self.assertEqual(self.report_path.read_bytes(), previous)

    def test_invalid_report_preserves_previous_output(self):
        self.output.write_text("previous", encoding="utf-8")
        self.report_path.write_text("[]", encoding="utf-8")
        with self.assertRaises(module.ManifestError):
            module.write_preview_manifest(self.root, notes="")
        self.assertEqual(self.output.read_text(), "previous")

    def test_failed_replace_preserves_output_and_removes_partial(self):
        self.output.write_text("previous", encoding="utf-8")
        with patch.object(module.os, "replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                module.write_preview_manifest(self.root, notes="")
        self.assertEqual(self.output.read_text(), "previous")
        self.assertEqual(list(self.artifact.glob("*.manifest.part")), [])

    def test_large_report_not_read_unbounded(self):
        self.report_path.write_bytes(b" " * (module.MAX_REPORT_BYTES + 1))
        with self.assertRaisesRegex(module.ManifestError, "report_too_large"):
            module.write_preview_manifest(self.root, notes="")

    @unittest.skipIf(os.name == "nt", "symlink creation requires Windows privileges")
    def test_output_link_cannot_overwrite_external_file(self):
        victim = Path(self.temp.name) / "victim"
        victim.write_text("preserve", encoding="utf-8")
        self.output.symlink_to(victim)
        with self.assertRaises(module.ManifestError):
            module.write_preview_manifest(self.root, notes="")
        self.assertEqual(victim.read_text(), "preserve")

    @unittest.skipIf(os.name == "nt", "symlink creation requires Windows privileges")
    def test_report_link_cannot_read_external_file(self):
        victim = Path(self.temp.name) / "outside"
        victim.write_text(json.dumps(report()), encoding="utf-8")
        self.report_path.unlink()
        self.report_path.symlink_to(victim)
        with self.assertRaises(module.ManifestError):
            module.write_preview_manifest(self.root, notes="")
        self.assertFalse(self.output.exists())

    def test_linked_parent_is_rejected_before_write(self):
        original = Path.is_symlink
        # Match the canonical path used by the production traversal. On Windows
        # the runner's temporary directory may use an 8.3 alias; resolve it before
        # mocking is_symlink, not inside the mock (which would recurse).
        linked = (self.root / "app" / "build").resolve(strict=True)
        with patch.object(Path, "is_symlink", lambda p: p == linked or original(p)):
            with self.assertRaises(module.ManifestError):
                module.write_preview_manifest(self.root, notes="")
        self.assertFalse(self.output.exists())

    def test_reparse_point_is_rejected(self):
        metadata = type("Stat", (), {"st_file_attributes": 0x400})()
        with patch.object(Path, "lstat", return_value=metadata):
            with patch.object(Path, "is_symlink", return_value=False):
                with self.assertRaisesRegex(module.ManifestError, "reparse_point"):
                    module._reject_link(self.output)

    def test_missing_artifact_directory_is_not_created_from_arguments(self):
        missing = Path(self.temp.name) / "other"
        missing.mkdir()
        with self.assertRaises(module.ManifestError):
            module.write_preview_manifest(missing, notes="")
        self.assertFalse((missing / "app").exists())


if __name__ == "__main__":
    unittest.main()
