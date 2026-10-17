"""Source regressions for the OWNER-approved Android 16 live Spectrum UI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
NATIVE = ROOT / "app/src/main/java/ru/omnicio/app"


class Android16LiveSpectrumTests(unittest.TestCase):
    def source(self, relative: str) -> str:
        return (NATIVE / relative).read_text(encoding="utf-8")

    def test_candidate_identity_and_sdk_are_android_16_only(self):
        gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        for sdk in ("compileSdk = 36", "minSdk = 36", "targetSdk = 36"):
            self.assertIn(sdk, gradle)
        self.assertIn("versionCode = 32", gradle)
        self.assertIn('versionName = "0.8.0"', gradle)

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
        for label in (
            "Живые графики",
            "Анимированные индикаторы",
            "Двухмерные и пространственные элементы",
            "RGB-эффекты иконок",
            "Интерактивный ИИ-ассистент",
            "Умные уведомления",
            "Персональные рекомендации",
            "Контроль рисков",
            "Анализ мировых рынков",
        ):
            self.assertIn(label, source)
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
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("Canvas(", source)

    def test_live_clock_respects_activity_user_and_system_motion(self):
        source = self.source("ui/spectrum/SpectrumLiveMotion.kt")
        self.assertIn("Lifecycle.State.STARTED", source)
        self.assertIn("ValueAnimator.areAnimatorsEnabled()", source)
        self.assertIn("motionAllowed && active", source)
        self.assertIn("LaunchedEffect(enabled, durationMillis)", source)
        self.assertIn("while (true)", source)

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
        for token in (
            "SpectrumLiveFeature.Assistant",
            "SpectrumLiveFeature.Recommendations",
            "SpectrumLiveFeature.WorldMarkets",
            "SpectrumLiveFeatureIcon(",
        ):
            self.assertIn(token, shortcuts)
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
        self.assertIn("Brush.radialGradient", visuals)
        self.assertIn("drawPath(", visuals)
        for forbidden in (
            "PackageInstaller",
            "openConnection",
            "Image(",
            "painterResource",
            "android.webkit",
            "WebView(",
            ".gif",
        ):
            self.assertNotIn(forbidden, screen + visuals)

    def test_android16_live_ui_contract_is_documented(self):
        spec = (ROOT / "docs/ANDROID16_LIVE_UI_SPEC.md").read_text(encoding="utf-8")
        for phrase in (
            "Live charts",
            "Animated indicators",
            "2D/spatial elements",
            "RGB icon effects",
            "Interactive AI assistant",
            "Smart notifications",
            "Personal recommendations",
            "Risk control",
            "World-market analysis",
            "predictive-back",
            "Edge-to-edge",
        ):
            self.assertIn(phrase, spec)


if __name__ == "__main__":
    unittest.main()

