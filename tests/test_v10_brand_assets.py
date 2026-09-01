from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_v10_brand_assets.py"
PACKAGE = ROOT / "docs/brand/omni-cio-brand-assets-v1"
CUSTODY = ROOT / "docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json"
MANIFEST = PACKAGE / "asset-manifest.json"


class V10BrandAssetsTests(unittest.TestCase):
    def _run_guard(self, repository_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repository-root",
                str(repository_root),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _copy_brand_contract(self, repository_root: Path) -> None:
        brand_root = repository_root / "docs/brand"
        brand_root.mkdir(parents=True)
        shutil.copytree(PACKAGE, brand_root / PACKAGE.name)
        shutil.copy2(CUSTODY, brand_root / CUSTODY.name)

    def test_current_repository_satisfies_brand_asset_integrity(self) -> None:
        completed = self._run_guard(ROOT)
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "Package paths verified: 37" in completed.stdout
        assert "Authority expansion: none" in completed.stdout

    def test_manifest_contains_complete_web_and_android_delivery_set(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        paths = {
            record["path"]
            for record in payload["files"]
            if isinstance(record, dict) and isinstance(record.get("path"), str)
        }
        for path in (
            "android/res/drawable-nodpi/omni_launcher_foreground.png",
            "android/res/drawable-nodpi/omni_launcher_monochrome.png",
            "web/apple-touch-icon-180.png",
            "web/favicon.ico",
            "web/pwa-icon-192.png",
            "web/pwa-icon-512.png",
            "web/pwa-maskable-512.png",
        ):
            assert path in paths

    def test_tampered_binary_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omni-brand-tamper-") as temporary:
            repository_root = Path(temporary)
            self._copy_brand_contract(repository_root)
            target = (
                repository_root
                / "docs/brand/omni-cio-brand-assets-v1/raster/omni-sentinel-core-16.png"
            )
            data = bytearray(target.read_bytes())
            data[-1] ^= 0x01
            target.write_bytes(data)
            completed = self._run_guard(repository_root)
            assert completed.returncode == 1
            assert "SHA-256 mismatch" in completed.stderr

    def test_missing_android_drawable_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omni-brand-android-") as temporary:
            repository_root = Path(temporary)
            self._copy_brand_contract(repository_root)
            target = (
                repository_root
                / "docs/brand/omni-cio-brand-assets-v1/android/res/drawable-nodpi/"
                "omni_launcher_foreground.png"
            )
            target.unlink()
            completed = self._run_guard(repository_root)
            assert completed.returncode == 1
            assert "brand asset is missing" in completed.stderr


if __name__ == "__main__":
    unittest.main()
