from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import check_v10_web_baseline as guard


ROOT = Path(__file__).resolve().parents[1]


class V10WebBaselineTests(unittest.TestCase):
    def _fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, object]]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(ROOT / "apps" / "web", root / "apps" / "web")
        baseline = json.loads(
            (ROOT / "docs" / "architecture" / "V10_TOOLCHAIN_BASELINE.json").read_text(
                encoding="utf-8"
            )
        )
        return temp, root, baseline

    def test_current_web_baseline_is_valid(self) -> None:
        failures: list[str] = []
        baseline = json.loads(guard.BASELINE_PATH.read_text(encoding="utf-8"))
        guard.validate_web(ROOT, baseline, failures)
        self.assertEqual(failures, [])

    def test_missing_lock_fails_closed(self) -> None:
        temp, root, baseline = self._fixture()
        self.addCleanup(temp.cleanup)
        (root / "apps" / "web" / "package-lock.json").unlink()
        failures: list[str] = []
        guard.validate_web(root, baseline, failures)
        self.assertTrue(any("package-lock.json" in failure for failure in failures))

    def test_floating_playwright_pin_is_rejected(self) -> None:
        temp, root, baseline = self._fixture()
        self.addCleanup(temp.cleanup)
        package_path = root / "apps" / "web" / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        package["devDependencies"]["@playwright/test"] = "^1.61.1"
        package_path.write_text(json.dumps(package), encoding="utf-8")
        failures: list[str] = []
        guard.validate_web(root, baseline, failures)
        self.assertTrue(
            any("@playwright/test" in failure for failure in failures), failures
        )

    def test_lock_root_drift_is_rejected(self) -> None:
        temp, root, baseline = self._fixture()
        self.addCleanup(temp.cleanup)
        lock_path = root / "apps" / "web" / "package-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["packages"][""]["dependencies"]["react"] = "0.0.0"
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        failures: list[str] = []
        guard.validate_web(root, baseline, failures)
        self.assertTrue(any("root dependencies" in failure for failure in failures))

    def test_unapproved_registry_is_rejected(self) -> None:
        temp, root, baseline = self._fixture()
        self.addCleanup(temp.cleanup)
        lock_path = root / "apps" / "web" / "package-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["packages"]["node_modules/react"]["resolved"] = (
            "https://example.invalid/react.tgz"
        )
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        failures: list[str] = []
        guard.validate_web(root, baseline, failures)
        self.assertTrue(any("unapproved Web npm source" in failure for failure in failures))

    def test_unapproved_license_is_rejected(self) -> None:
        temp, root, baseline = self._fixture()
        self.addCleanup(temp.cleanup)
        lock_path = root / "apps" / "web" / "package-lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["packages"]["node_modules/react"]["license"] = "GPL-3.0-only"
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        failures: list[str] = []
        guard.validate_web(root, baseline, failures)
        self.assertTrue(any("unapproved license" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
