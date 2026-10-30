"""Pure administrative checks; no Android, network, credentials or personal AVDs."""
from __future__ import annotations

import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "render_owner57.py"
SPEC = importlib.util.spec_from_file_location("render_owner57", SCRIPT)
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


class PreviewInventoryTests(unittest.TestCase):
    def names(self):
        return [Path("screens") / (prefix + "_abcdef_0.png")
                for prefix in renderer.REQUIRED_PREVIEW_PREFIXES]

    def test_every_owner_case_is_required(self):
        renderer.require_preview_inventory(self.names())
        for index in range(len(self.names())):
            with self.subTest(index=index), self.assertRaises(ValueError):
                renderer.require_preview_inventory(self.names()[:index] + self.names()[index + 1:])

    def test_large_text_cannot_substitute_normal_preview(self):
        names = self.names()
        names = [path for path in names if not path.name.startswith("OwnerSetup55_owner55-setup_")]
        with self.assertRaises(ValueError):
            renderer.require_preview_inventory(names)

    def test_duplicate_case_is_rejected(self):
        with self.assertRaises(ValueError):
            renderer.require_preview_inventory(self.names() + [self.names()[0]])

    def test_unrelated_old_reference_count_cannot_pass(self):
        with self.assertRaises(ValueError):
            renderer.require_preview_inventory([Path(str(i) + ".png") for i in range(100)])


class SourcePreviewTests(unittest.TestCase):
    def source(self):
        groups = {}
        for function, preview in renderer.REQUIRED_PREVIEWS:
            groups.setdefault(function, []).append(preview)
        return "\n".join("@PreviewTest\n" + "\n".join(
            '@Preview(name = "' + name + '", widthDp = 390)'
            for name in names) + "\n@Composable\nfun " + function + "() = Unit"
            for function, names in groups.items())

    def test_required_names_belong_to_the_expected_compiled_composables(self):
        renderer.require_source_previews(self.source())
        with self.assertRaises(ValueError):
            renderer.require_source_previews(self.source().replace("fun Terminal57()", "fun OtherScreen()"))

    def test_required_annotation_cannot_be_missing_or_duplicated(self):
        with self.assertRaises(ValueError):
            renderer.require_source_previews(self.source().replace('name = "owner55-setup"', 'name = "different"'))
        with self.assertRaises(ValueError):
            renderer.require_source_previews(self.source() + "\n" + self.source())


class ReferenceRestorationTests(unittest.TestCase):
    def test_old_images_are_removed_before_render_and_restored_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory)
            before = reference / "nested" / "old.png"
            before.parent.mkdir()
            before.write_bytes(b"original-reference-bytes")
            note = reference / "README.txt"
            note.write_text("not a generated image", encoding="utf-8")
            original = renderer.snapshot_reference(reference)
            renderer.clear_reference(reference)
            self.assertEqual(list(reference.rglob("*.png")), [])
            (reference / "generated.png").write_bytes(b"new-render")
            renderer.restore_reference(reference, original)
            self.assertEqual(before.read_bytes(), b"original-reference-bytes")
            self.assertFalse((reference / "generated.png").exists())
            self.assertEqual(note.read_text(encoding="utf-8"), "not a generated image")

    def test_job_close_failure_leaves_an_explicit_failed_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            report = {"status": "rendered-awaiting-visual-review", "native_acceptance": False}
            job = mock.Mock()
            job.close.side_effect = OSError("synthetic close failure")
            output = io.StringIO()
            with redirect_stdout(output), self.assertRaises(OSError):
                renderer.finish_report(state, report, job)
            saved = json.loads((state / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(saved["cleanup_error_type"], "OSError")
            self.assertFalse(saved["native_acceptance"])
            self.assertNotIn("synthetic close failure", output.getvalue())


if __name__ == "__main__":
    unittest.main()

