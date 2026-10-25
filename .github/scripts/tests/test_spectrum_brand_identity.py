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

    def test_android_17_live_ui_candidate_has_a_unique_upgrade_code(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        version = re.search(r"versionCode\s*=\s*(\d+)", gradle)
        self.assertIsNotNone(version)
        self.assertEqual(int(version.group(1)), 38)
        for sdk in ("compileSdk = 37", "minSdk = 37", "targetSdk = 37"):
            self.assertIn(sdk, gradle)
        self.assertIn('versionName = "0.13.0"', gradle)
        self.assertNotIn('versionName = "0.7.6"', gradle)
        self.assertIn('applicationId = "ru.omnicio.app"', gradle)
        self.assertIn('applicationIdSuffix = ".debug"', gradle)
        self.assertIn('isDebuggable = false', gradle)

    def test_about_dialog_uses_build_identity_and_explains_connection_limits(self):
        profile = (
            ROOT / "app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt"
        ).read_text(encoding="utf-8")
        self.assertIn('"about" ->', profile)
        self.assertIn('"logout" ->', profile)
        about = profile.partition('"about" ->')[2].partition('"logout" ->')[0]
        self.assertIn('SettingsInformation("Analyst AI"', about)
        self.assertIn("BuildConfig.VERSION_NAME", about)
        self.assertIn("BuildConfig.VERSION_CODE", about)
        self.assertIn("Независимое приложение, не официальное приложение Т-Банка.", about)
        self.assertIn("Доступность анализа зависит от подключённых источников и серверных настроек.", about)
        self.assertNotIn("Android 13+", profile)
        self.assertNotIn("Версия 0.7.1-preview", profile)


if __name__ == "__main__":
    unittest.main()

