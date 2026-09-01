from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts import check_v10_brand_assets


class V10BrandAssetXmlSecurityTests(unittest.TestCase):
    def test_android_xml_rejects_declared_entities(self) -> None:
        payload = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE adaptive-icon [
  <!ENTITY forbidden "entity-expansion-must-not-run">
]>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@drawable/omni_launcher_background" />
  <foreground android:drawable="&forbidden;" />
</adaptive-icon>
"""
        with tempfile.TemporaryDirectory(prefix="omni-brand-xml-") as temporary:
            path = Path(temporary) / "ic_launcher.xml"
            path.write_text(payload, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Android XML invalid"):
                check_v10_brand_assets._verify_xml(path, "android/test/ic_launcher.xml")


if __name__ == "__main__":
    unittest.main()
