"""Mesh wiring regressions; real rendering remains a separate emulator gate."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / "app/src/main/java/ru/omnicio/app"


class Android17LiveSpectrumTests(unittest.TestCase):
    def source(self, relative: str) -> str:
        return (NATIVE / relative).read_text(encoding="utf-8")

    def test_candidate_identity_and_sdk_support_android_17_plus(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        for sdk in ("compileSdk = 37", "minSdk = 37", "targetSdk = 37"):
            self.assertIn(sdk, gradle)
        self.assertIn("versionCode = 35", gradle)
        self.assertIn('versionName = "0.11.0"', gradle)

    def test_all_nine_owner_approved_live_families_are_native(self):
        source = self.source("ui/spectrum/SpectrumLiveFeatureIcon.kt")
        for enum_name in (
            "Charts",
            "Indicators",
            "Spatial",
            "RgbEffects",
            "Assistant",
            "Notifications",
            "Recommendations",
            "RiskControl",
            "WorldMarkets",
        ):
            self.assertIn(enum_name + "(", source)
        families = re.findall(r'^\s*(\w+)\("([^"]+)", "([a-z_]+)"\)', source, re.M)
        self.assertEqual(len(families), 9)
        self.assertEqual(len({description for _, description, _ in families}), 9)
        assets = ROOT / 'app/src/main/assets/spectrum3d'
        catalogue = json.loads((assets / 'catalogue.json').read_text(encoding='utf-8'))
        for _, description, asset in families:
            self.assertTrue(description.strip())
            for suffix in ('', '_low'):
                name = asset + suffix + '.glb'
                data = (assets / name).read_bytes()
                self.assertEqual(data[:4], b'glTF')
                self.assertEqual(hashlib.sha256(data).hexdigest(), catalogue['models'][asset + suffix]['sha256'])
        # Check actual APIs/imports, not explanatory comments that may name a
        # forbidden technology while documenting why it is not used.
        for forbidden in (
            "Image(",
            "painterResource",
            "AsyncImage",
            "android.webkit",
            "WebView(",
            ".gif",
            "AnimatedImageVector",
            "Canvas(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("SpatialIcon(feature.asset", source)
        self.assertIn("description = feature.description", source)

    def test_shared_scene_respects_lifecycle_system_motion_and_visible_slots(self):
        host = self.source("ui/spatial/SpatialScene.kt")
        renderer = self.source("ui/spatial/SpatialRenderer.kt")
        self.assertIn("Lifecycle.State.STARTED", host)
        self.assertIn("onDispose { active?.close() }", host)
        self.assertIn("!ValueAnimator.areAnimatorsEnabled()", renderer)
        self.assertIn("SpatialMotion.Off", renderer)
        self.assertIn("SpatialMotion.Subdued", renderer)
        self.assertIn("choreographer.removeFrameCallback(this)", renderer)
        self.assertIn("windows.forEach { it.withdrawFrameRate() }", renderer)
        self.assertIn("clipping.width<=0f||clipping.height<=0f", "".join(renderer.split()))
        self.assertEqual(renderer.count("Engine.create("), 1)
        self.assertNotIn("Engine.create(", self.source("ui/spatial/SpatialComponents.kt"))
        back = self.source("ui/spatial/SpatialInteraction.kt")
        self.assertIn("PredictiveBackHandler(enabled)", back)
        self.assertIn("finally {", back)
        self.assertIn("window?.updateLocalBackProgress(0f)", back)

    def test_home_uses_real_state_for_avatar_and_live_shortcuts(self):
        home = self.source("ui/home/HomeScreen.kt")
        shortcuts = self.source("ui/home/HomeQuickActions.kt")
        for token in (
            "SpectrumAnalystAvatar(",
            "AnalystAvatarMood.Attention",
            "AnalystAvatarMood.Waiting",
            "AnalystAvatarMood.Ready",
            "snapshot?.warnings?.isNotEmpty()",
        ):
            self.assertIn(token, home)
        for token in ("onAssets", "onPayments", "Мои активы", "Выплаты"):
            self.assertIn(token, shortcuts)
        self.assertNotIn("SpectrumLiveFeatureIcon(", shortcuts)
        for invented in ("model is running", "AI score", "guaranteed return"):
            self.assertNotIn(invented, home.lower())

    def test_required_update_has_its_own_live_background_and_alert(self):
        screen = self.source("ui/spectrum/RequiredUpdateScreen.kt")
        visuals = self.source("ui/spectrum/SpectrumUpdateVisuals.kt")
        self.assertIn("SpectrumUpdateBackdrop(", screen)
        self.assertIn("SpectrumUpdateAlert(", screen)
        self.assertIn("updateRequired = updateRequired", screen)
        self.assertIn("safeDrawingPadding()", screen)
        self.assertIn("Скачивание", screen)
        self.assertIn("Проверка", screen)
        self.assertIn("Установка", screen)
        self.assertIn("Запуск", screen)
        self.assertIn('SpatialIcon("orbit"', visuals)
        self.assertIn('SpatialIcon(if (updateRequired) "warning" else "update"', visuals)
        self.assertIn("SpatialState.Attention", visuals)
        for forbidden in (
            "PackageInstaller",
            "openConnection",
            "Image(",
            "painterResource",
            "android.webkit",
            "WebView(",
            ".gif",
            "Canvas(",
            "drawPath(",
        ):
            self.assertNotIn(forbidden, screen + visuals)

    def test_mesh_contract_documents_native_input_accuracy_and_measurement_limits(self):
        spec = self.source("ui/spatial/README.md")
        for phrase in (
            "orthographic camera",
            "same engine",
            "native field/toggle/selectable",
            "Missing observations remain absent",
            "off the UI thread",
            "does **not** measure GPU",
            "16KB",
        ):
            self.assertIn(phrase, spec)


if __name__ == "__main__":
    unittest.main()

