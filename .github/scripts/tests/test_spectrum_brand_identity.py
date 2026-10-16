"""Source-bound launcher/version checks; real rendering remains an emulator gate."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "app/src/main/res"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class SpectrumBrandIdentityTests(unittest.TestCase):
    def test_launcher_shapes_use_the_same_brain_and_night_background(self):
        for name in ("ic_launcher", "ic_launcher_round"):
            with self.subTest(icon=name):
                icon = ET.parse(RES / "mipmap-anydpi-v26" / (name + ".xml")).getroot()
                self.assertEqual(icon.tag, "adaptive-icon")
                self.assertEqual(icon.find("foreground").get(ANDROID + "drawable"), "@drawable/analyst_brain_foreground")
                self.assertEqual(icon.find("background").get(ANDROID + "drawable"), "@drawable/analyst_launcher_background")
                self.assertEqual(icon.find("monochrome").get(ANDROID + "drawable"), "@drawable/analyst_brain_foreground")

    def test_brain_is_native_vector_inside_the_adaptive_safe_area(self):
        vector = ET.parse(RES / "drawable/analyst_brain_foreground.xml").getroot()
        self.assertEqual(vector.tag, "vector")
        self.assertEqual(vector.get(ANDROID + "width"), "108dp")
        self.assertEqual(vector.get(ANDROID + "height"), "108dp")
        group = vector.find("group")
        for axis in ("X", "Y"):
            self.assertGreater(float(group.get(ANDROID + "scale" + axis)), 0)
            self.assertLessEqual(float(group.get(ANDROID + "scale" + axis)), 2 / 3)
        self.assertGreaterEqual(len(group.findall("path")), 4)
        for path in group.findall("path"):
            self.assertTrue(path.get(ANDROID + "pathData"))

    def test_native_brand_background_is_not_a_broker_or_remote_bitmap(self):
        background = ET.parse(RES / "drawable/analyst_launcher_background.xml").getroot()
        self.assertEqual(background.tag, "shape")
        gradient = background.find("gradient")
        self.assertEqual(gradient.get(ANDROID + "startColor"), "#071C35")
        self.assertEqual(gradient.get(ANDROID + "endColor"), "#030C17")
        self.assertFalse(background.findall(".//bitmap"))

    def test_android_16_only_candidate_has_a_unique_upgrade_code(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        version_code = re.search(r"versionCode\s*=\s*(\d+)", gradle)
        version_name = re.search(r'versionName\s*=\s*"(0\.7\.(\d+))"', gradle)
        self.assertIsNotNone(version_code)
        self.assertIsNotNone(version_name)
        self.assertGreaterEqual(int(version_code.group(1)), 27)
        self.assertGreaterEqual(int(version_name.group(2)), 2)
        for sdk in ("compileSdk = 36", "minSdk = 36", "targetSdk = 36"):
            self.assertIn(sdk, gradle)
        self.assertIn('applicationId = "ru.omnicio.app"', gradle)
        self.assertIn('applicationIdSuffix = ".debug"', gradle)
        self.assertIn('isDebuggable = false', gradle)

    def test_about_dialog_does_not_claim_android_13_support(self):
        profile = (
            ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("только для Android 16 и новее", profile)
        self.assertNotIn("Android 13+", profile)


if __name__ == "__main__":
    unittest.main()
