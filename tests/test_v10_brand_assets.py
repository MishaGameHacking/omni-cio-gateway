from __future__ import annotations

import hashlib
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
MASKABLE_PATH = "web/pwa-maskable-512.png"
ORDINARY_PWA_512_PATH = "web/pwa-icon-512.png"
BRAND_ROOT_RELATIVE = "docs/brand"
MASKABLE_SAFE_ZONE_KEY = "maskable_safe_zone"


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
        brand_root = repository_root / BRAND_ROOT_RELATIVE
        brand_root.mkdir(parents=True)
        shutil.copytree(PACKAGE, brand_root / PACKAGE.name)
        shutil.copy2(CUSTODY, brand_root / CUSTODY.name)

    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_current_repository_satisfies_brand_asset_integrity(self) -> None:
        completed = self._run_guard(ROOT)
        assert completed.returncode == 0, completed.stderr or completed.stdout
        assert "Package paths verified: 37" in completed.stdout
        assert "Maskable PWA safe-zone contract: verified" in completed.stdout
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
            ORDINARY_PWA_512_PATH,
            MASKABLE_PATH,
        ):
            assert path in paths

    def test_maskable_pwa_icon_is_distinct_and_safe_zone_pinned(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        custody = json.loads(CUSTODY.read_text(encoding="utf-8"))
        records = {record["path"]: record for record in manifest["files"]}
        maskable_record = records[MASKABLE_PATH]
        maskable_custody = custody["maskable_derivative"]

        ordinary_bytes = (PACKAGE / ORDINARY_PWA_512_PATH).read_bytes()
        maskable_bytes = (PACKAGE / MASKABLE_PATH).read_bytes()
        assert hashlib.sha256(ordinary_bytes).digest() != hashlib.sha256(
            maskable_bytes
        ).digest()
        assert maskable_record["sha256"] == hashlib.sha256(maskable_bytes).hexdigest()
        assert maskable_record["bytes"] == len(maskable_bytes)
        assert maskable_record["dimensions"] == [512, 512]
        assert maskable_record["mode"] == "RGB"
        assert (
            manifest[MASKABLE_SAFE_ZONE_KEY]
            == maskable_custody["safe_zone_contract"]
        )
        assert (
            manifest[MASKABLE_SAFE_ZONE_KEY][
                "guaranteed_visible_circle_diameter_percent"
            ]
            == 80
        )

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

    def test_stale_custody_manifest_pin_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omni-brand-custody-") as temporary:
            repository_root = Path(temporary)
            self._copy_brand_contract(repository_root)
            custody_path = repository_root / BRAND_ROOT_RELATIVE / CUSTODY.name
            custody = json.loads(custody_path.read_text(encoding="utf-8"))
            custody["repository_canonical_package"]["manifest_sha256"] = "0" * 64
            self._write_json(custody_path, custody)

            completed = self._run_guard(repository_root)
            assert completed.returncode == 1
            assert "manifest byte identity drifted from custody pin" in completed.stderr

    def test_maskable_safe_zone_semantic_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="omni-brand-maskable-") as temporary:
            repository_root = Path(temporary)
            self._copy_brand_contract(repository_root)
            brand_root = repository_root / BRAND_ROOT_RELATIVE
            manifest_path = brand_root / PACKAGE.name / MANIFEST.name
            custody_path = brand_root / CUSTODY.name

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest[MASKABLE_SAFE_ZONE_KEY][
                "guaranteed_visible_circle_diameter_percent"
            ] = 79
            self._write_json(manifest_path, manifest)

            custody = json.loads(custody_path.read_text(encoding="utf-8"))
            custody["repository_canonical_package"]["manifest_sha256"] = (
                hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            )
            self._write_json(custody_path, custody)

            completed = self._run_guard(repository_root)
            assert completed.returncode == 1
            assert "maskable PWA safe-zone contract drifted" in completed.stderr


if __name__ == "__main__":
    unittest.main()
