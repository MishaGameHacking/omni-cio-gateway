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
        self.assertIn("versionCode = 56", gradle)
        self.assertIn('versionName = "0.20.0"', gradle)

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
        self.assertIn("Lifecycle.State.STARTED", host)
        self.assertIn("ValueAnimator.areAnimatorsEnabled()", host)
        self.assertIn("ValueAnimator.registerDurationScaleChangeListener(durationScaleListener)", host)
        self.assertIn("systemMotion = scale > 0f", host)
        self.assertIn("bounds.width > 0f && bounds.height > 0f", host)
        self.assertIn("flatMotionPolicy(motion, foreground, systemMotion, constrained, severeThermal)", host)
        for release in ("lifecycle.removeObserver(observer)", "ValueAnimator.unregisterDurationScaleChangeListener(durationScaleListener)",
                        "unregisterReceiver(receiver)", "removeThermalStatusListener(thermal)"):
            self.assertIn(release, host)
        for unused in ("SpatialOwner(context)", "TextureView(", "AndroidView(", "Engine.create("):
            self.assertNotIn(unused, host)
        self.assertIn("drawFlatPrimitive(it, if (it.motionAllowed) progress else 0f, palette)", host)
        self.assertIn("val palette = LocalSpectrumPalette.current", host)
        back = self.source("ui/spatial/SpatialInteraction.kt")
        self.assertIn("PredictiveBackHandler(enabled)", back)
        self.assertIn("finally {", back)
        self.assertIn("back?.value = 0f", back)
        self.assertIn("LocalFlatTactile.current", back)

    def test_home_uses_confirmed_analysis_and_shared_primary_destinations(self):
        home = self.source("ui/home/HomeScreen.kt")
        body = home.split("private fun automationStateTitle", 1)[0]
        for token in (
            'rememberWorkspaceResource("/automation/status")',
            'status?.records("blockers")',
            'resource.error',
            'workspaceForeground()',
            'onOpenRecommendations',
            'onOpenProfile',
            'onConnect',
            '"Система"',
            'SystemTelemetryCard(ai, observedNow)',
            '"Сегодня"',
            '"Требует внимания"',
            '"Только анализ"',
        ):
            self.assertIn(token, body)
        for duplicate_portfolio_view in ("PortfolioUiState.Ready", "InteractiveBalance(", "snapshot.totalValue"):
            self.assertNotIn(duplicate_portfolio_view, body)
        for invented in ("model is running", "AI score", "guaranteed return"):
            self.assertNotIn(invented, home.lower())
        bar = self.source("ui/AnalystBottomBar.kt")
        catalogue = self.source("ui/NavigationCatalogue.kt")
        self.assertIn('analystPrimaryDestinations.mapNotNull { it.tab }', bar)
        for destination,label in (("Home","Система"),("Portfolio","Аналитика"),
                                  ("Recommendations","Решения"),("Profile","Настройки")):
            self.assertIn('AnalystDestination("'+destination+'", "'+label+'"', catalogue)
        self.assertNotIn('showLabel = !compact',bar)
        self.assertIn('SpectrumGlyphButton(tab.symbol(), tab.label()',bar)
        self.assertIn('Modifier.size(56.dp)',bar)
        self.assertIn("role = Role.Tab", bar)
        self.assertIn(".selectableGroup()", bar)

    def test_secondary_portfolio_tools_preserve_their_existing_callbacks(self):
        shortcuts = self.source("ui/home/HomeQuickActions.kt")
        for token in ("onAssets", "onPayments", "Мои активы", "Выплаты"):
            self.assertIn(token, shortcuts)
        self.assertNotIn("SpectrumLiveFeatureIcon(", shortcuts)

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





