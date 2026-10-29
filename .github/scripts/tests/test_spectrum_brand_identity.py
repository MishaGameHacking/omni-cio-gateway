"""Resolve the actual launcher/launch resources; runtime drawing remains a native gate."""
from pathlib import Path
import math
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "app/src/main/res"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def resource_values(night, api=37):
    folders = []
    for folder in RES.iterdir():
        match = re.fullmatch(r"values(-night)?(?:-v(\d+))?", folder.name)
        if not match or bool(match.group(1)) and not night:
            continue
        version = int(match.group(2) or 0)
        if version <= api:
            folders.append((bool(match.group(1)), version, folder))
    values = {}
    for _, _, folder in sorted(folders):
        for path in sorted(folder.glob("*.xml")):
            for element in ET.parse(path).getroot():
                if element.get("name"):
                    values[(element.tag, element.get("name"))] = element
    return values


def resolved_color(reference, night, seen=()):
    if reference.startswith("@color/"):
        name = reference.removeprefix("@color/")
        if name in seen:
            raise AssertionError("Cyclic production color reference")
        element = resource_values(night)[("color", name)]
        return resolved_color(element.text.strip(), night, (*seen, name))
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", reference):
        raise AssertionError("Launch colors must resolve to an opaque sRGB value")
    return tuple(int(reference[index:index + 2], 16) / 255 for index in (1, 3, 5))


def contrast(first, second):
    def luminance(rgb):
        linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in rgb]
        return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return (high + .05) / (low + .05)


def launcher_file(name, api):
    candidates = []
    for folder in RES.iterdir():
        match = re.fullmatch(r"mipmap-anydpi(?:-v(\d+))?", folder.name)
        if match and int(match.group(1) or 0) <= api and (folder / (name + ".xml")).is_file():
            candidates.append((int(match.group(1) or 0), folder / (name + ".xml")))
    if not candidates:
        raise AssertionError("No applicable adaptive launcher resource")
    return max(candidates)[1]


class SpectrumBrandIdentityTests(unittest.TestCase):
    def test_actual_supported_api_37_and_fallback_launchers_share_the_native_silhouette(self):
        for api in (26, 33, 37):
            for name in ("ic_launcher", "ic_launcher_round"):
                with self.subTest(api=api, icon=name):
                    path = launcher_file(name, api)
                    if api == 37:
                        self.assertEqual(path.parent.name, "mipmap-anydpi-v33")
                    icon = ET.parse(path).getroot()
                    self.assertEqual(icon.tag, "adaptive-icon")
                    self.assertEqual(icon.find("foreground").get(ANDROID + "drawable"), "@drawable/omni_launcher_foreground")
                    self.assertEqual(icon.find("background").get(ANDROID + "drawable"), "@drawable/omni_launcher_background")
                    self.assertEqual(icon.find("monochrome").get(ANDROID + "drawable"), "@drawable/omni_launcher_monochrome")
                    for layer in ("foreground", "monochrome"):
                        reference = icon.find(layer).get(ANDROID + "drawable")
                        actual = ET.parse(RES / (reference[1:] + ".xml")).getroot()
                        self.assertEqual(actual.tag, "vector")
                        self.assertFalse(actual.findall(".//bitmap"))

    def test_native_foreground_preserves_mask_geometry_and_adaptive_safe_circle(self):
        foreground = ET.parse(RES / "drawable/omni_launcher_foreground.xml").getroot()
        mask = ET.parse(RES / "drawable/omni_launcher_monochrome.xml").getroot()
        for vector in (foreground, mask):
            self.assertEqual(vector.get(ANDROID + "width"), "108dp")
            self.assertEqual(vector.get(ANDROID + "height"), "108dp")
            self.assertEqual(vector.get(ANDROID + "viewportWidth"), "432")
            self.assertEqual(vector.get(ANDROID + "viewportHeight"), "432")
        colored_paths, mask_paths = foreground.findall("path"), mask.findall("path")
        self.assertEqual(len(colored_paths), len(mask_paths))
        self.assertGreater(len(colored_paths), 0)
        for colored, monochrome in zip(colored_paths, mask_paths):
            data = colored.get(ANDROID + "pathData")
            self.assertEqual(data, monochrome.get(ANDROID + "pathData"))
            self.assertEqual(colored.get(ANDROID + "fillType"), monochrome.get(ANDROID + "fillType"))
            self.assertEqual(monochrome.get(ANDROID + "fillColor"), "#FFFFFFFF")
            self.assertEqual(colored.get(ANDROID + "fillColor"), "@color/analyst_primary")
            # The retained silhouette is a polygon, so all connecting segments
            # remain inside the convex safe circle when their vertices do.
            self.assertEqual(set(re.findall(r"[A-Za-z]", data)), {"M", "L", "Z"})
            numbers = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", data)]
            self.assertEqual(len(numbers) % 2, 0)
            for x, y in zip(numbers[::2], numbers[1::2]):
                self.assertLessEqual(math.hypot(x - 216, y - 216), 144)

    def test_legacy_native_artwork_remains_inside_safe_area_and_uses_resolved_theme_inks(self):
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
            reference = path.get(ANDROID + "fillColor")
            self.assertTrue(reference.startswith("@color/"))
            for night in (False, True):
                resolved_color(reference, night)

    def test_both_launcher_backgrounds_are_native_opaque_and_contrast_the_real_foreground(self):
        for name in ("analyst_launcher_background", "omni_launcher_background"):
            background = ET.parse(RES / "drawable" / (name + ".xml")).getroot()
            self.assertEqual(background.tag, "shape")
            self.assertFalse(background.findall(".//bitmap"))
            fill = background.find("solid").get(ANDROID + "color")
            for night in (False, True):
                with self.subTest(resource=name, night=night):
                    self.assertGreaterEqual(contrast(resolved_color(fill, night), resolved_color("@color/analyst_primary", night)), 3)

    def test_actual_day_and_night_launch_styles_resolve_all_colored_surfaces(self):
        for night in (False, True):
            with self.subTest(night=night):
                style = resource_values(night)[("style", "Theme.OMNICIO")]
                expected_parent = "@android:style/Theme.Material.NoActionBar"
                self.assertEqual(style.get("parent"), expected_parent)
                items = {item.get("name"): item.text.strip() for item in style.findall("item")}
                self.assertEqual(items["android:windowSplashScreenBackground"], items["android:windowBackground"])
                self.assertEqual(items["android:windowSplashScreenAnimatedIcon"], "@drawable/omni_launcher_foreground")
                self.assertEqual(items["android:windowSplashScreenBehavior"], "icon_preferred")
                self.assertEqual(items["android:forceDarkAllowed"], "false")
                self.assertEqual(items["android:windowLightStatusBar"], "false" if night else "true")
                self.assertEqual(items["android:windowLightNavigationBar"], "false" if night else "true")
                for bar in ("statusBarColor", "navigationBarColor", "navigationBarDividerColor"):
                    self.assertEqual(items["android:" + bar], "@android:color/transparent")
                for value in items.values():
                    if value.startswith("@color/"):
                        resolved_color(value, night)
                background = resolved_color(items["android:windowBackground"], night)
                for key in ("textColorPrimary", "textColorSecondary", "textColorLink"):
                    self.assertGreaterEqual(contrast(background, resolved_color(items["android:" + key], night)), 4.5)
                self.assertGreaterEqual(contrast(background, resolved_color("@color/analyst_primary", night)), 3)
                self.assertGreaterEqual(contrast(resolved_color("@color/analyst_primary", night),
                                                 resolved_color("@color/analyst_on_primary", night)), 4.5)
        self.assertNotEqual(resolved_color("@color/analyst_background", False), resolved_color("@color/analyst_background", True))

    def test_owner56_candidate_preserves_preview_identity_and_advances_published55(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        version = re.search(r"versionCode\s*=\s*(\d+)", gradle)
        self.assertIsNotNone(version)
        self.assertEqual(int(version.group(1)), 56)
        self.assertGreater(int(version.group(1)), 55)
        for sdk in ("compileSdk = 37", "minSdk = 37", "targetSdk = 37"):
            self.assertIn(sdk, gradle)
        self.assertIn('versionName = "0.20.0"', gradle)
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






