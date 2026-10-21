"""Exercise cleanup ownership and immutable APK preservation with real files."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from release_build_intermediates import APKS, INTERMEDIATES, extended_windows_path, release_intermediates


class ReleaseIntermediatesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        for relative in APKS:
            self.write(relative, b"immutable-apk-fixture")
        for relative in INTERMEDIATES:
            self.write(relative + "/nested/generated.bin", b"regenerable")

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def assert_intermediates_preserved(self):
        for relative in INTERMEDIATES:
            self.assertEqual((self.root / relative / "nested/generated.bin").read_bytes(), b"regenerable")

    def test_removes_only_intermediates_preserving_apks_reports_and_shared_caches(self):
        preserved = [*APKS, "app/build/reports/lint.json", "app/build/outputs/mapping/release/mapping.txt",
                     "app/build/outputs/apk/preview/ui-screens/evidence.json",
                     ".gradle/cache.bin", "sdk/system.img", "another-runner/app/build/intermediates/keep.bin"]
        for relative in preserved[len(APKS):]:
            self.write(relative, b"keep")
        before = {p: (self.root / p).read_bytes() for p in preserved}
        receipt = release_intermediates(self.root)
        self.assertEqual(set(receipt["removed"]), set(INTERMEDIATES))
        self.assertEqual(set(receipt["apk_sha256"]), set(APKS))
        self.assertEqual({p: (self.root / p).read_bytes() for p in preserved}, before)
        for relative in INTERMEDIATES:
            self.assertFalse((self.root / relative).exists())
        self.assertEqual(release_intermediates(self.root)["removed"], [])

    def test_missing_or_empty_apk_prevents_any_removal(self):
        for data in (None, b""):
            with self.subTest(data=data):
                path = self.root / APKS[-1]
                if data is None:
                    path.unlink()
                else:
                    path.write_bytes(data)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    release_intermediates(self.root)
                self.assert_intermediates_preserved()

    def test_tracked_source_in_any_target_prevents_all_removal(self):
        source = INTERMEDIATES[-1] + "/tracked.txt"
        self.write(source, b"tracked")
        subprocess.run(["git", "add", source], cwd=self.root, check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, "tracked source"):
            release_intermediates(self.root)
        self.assert_intermediates_preserved()

    def test_failed_build_cleanup_preserves_partial_apks_and_reports(self):
        (self.root / APKS[-1]).unlink()
        self.write(APKS[-2], b"")
        report = self.write("app/build/reports/lint-errors.txt", b"original build failure")
        before = {p: (self.root / p).read_bytes() for p in APKS[:-1]}
        receipt = release_intermediates(self.root, allow_incomplete=True)
        self.assertEqual(set(receipt["removed"]), set(INTERMEDIATES))
        self.assertEqual(set(receipt["apk_sha256"]), set(before))
        self.assertEqual({p: (self.root / p).read_bytes() for p in before}, before)
        self.assertFalse((self.root / APKS[-1]).exists())
        self.assertEqual(report.read_bytes(), b"original build failure")

    def test_failed_build_mode_still_refuses_links_in_apk_paths(self):
        apk = self.root / APKS[-1]
        apk.unlink()
        outside = self.write("outside.apk", b"unrelated")
        try:
            apk.symlink_to(outside)
        except OSError:
            self.skipTest("Host does not permit symlink creation")
        with self.assertRaisesRegex(ValueError, "links and reparse"):
            release_intermediates(self.root, allow_incomplete=True)
        self.assert_intermediates_preserved()
        self.assertEqual(outside.read_bytes(), b"unrelated")

    def test_nested_link_prevents_all_removal_and_preserves_its_target(self):
        outside = self.write("preserved.bin", b"private-fixture")
        link = self.root / INTERMEDIATES[-1] / "link"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Host does not permit symlink creation")
        with self.assertRaisesRegex(ValueError, "links and reparse"):
            release_intermediates(self.root)
        self.assert_intermediates_preserved()
        self.assertEqual(outside.read_bytes(), b"private-fixture")

    def test_subdirectory_cannot_be_used_as_checkout_root(self):
        with self.assertRaisesRegex(ValueError, "exact checkout root"):
            release_intermediates(self.root / "app")
        self.assert_intermediates_preserved()

    def test_generated_class_path_longer_than_windows_max_path_is_removed(self):
        root = Path(extended_windows_path(str(self.root))) if os.name == "nt" else self.root
        generated = root / INTERMEDIATES[0]
        for index in range(4):
            generated /= "generated_package_" + str(index) + "_" + "x" * 60
        generated.mkdir(parents=True)
        generated /= "AccountOperationsKt$invokeSuspend$lambda$sortedByDescending$1.class"
        generated.write_bytes(b"compiled-class")
        self.assertGreater(len(str(generated)), 260)
        receipt = release_intermediates(self.root)
        self.assertEqual(set(receipt["removed"]), set(INTERMEDIATES))
        self.assertFalse(generated.exists())
        for relative in APKS:
            self.assertEqual((self.root / relative).read_bytes(), b"immutable-apk-fixture")

    def test_windows_drive_unc_and_already_extended_paths_keep_identity(self):
        self.assertEqual(extended_windows_path("C:\\runner\\checkout"), "\\\\?\\C:\\runner\\checkout")
        self.assertEqual(extended_windows_path("\\\\server\\share\\checkout"), "\\\\?\\UNC\\server\\share\\checkout")
        existing = "\\\\?\\C:\\runner\\checkout"
        self.assertEqual(extended_windows_path(existing), existing)


if __name__ == "__main__":
    unittest.main()
