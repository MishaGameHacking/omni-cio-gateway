package ru.omnicio.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.education.EducationScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.theme.AnalystTheme
import ru.omnicio.app.ui.workspace.*
import androidx.compose.runtime.CompositionLocalProvider
import ru.omnicio.app.ui.spectrum.LocalSpectrumTabScrollTag

private const val THEME_LIFECYCLE_SCREEN = "theme-lifecycle"

/** Debug-only UI fixture. No network calls or authentication bypass in preview. */
class ProfileUiProbeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Match MainActivity's coordinate system and safeDrawing insets. A
        // non-edge-to-edge fixture is not evidence for the production layout.
        enableEdgeToEdge()
        val allowedScreens = setOf("home", "portfolio", "appearance", "strategy", "assistant", "market", "ux100", "education", "spatial", "session-context", "balance-privacy", "goal-editor", "theme", THEME_LIFECYCLE_SCREEN) +
            businessProbeRoutes.map { "business-$it" } + portfolioProbeRoutes.map { "portfolio-$it" } + automationProbeRoutes.map { "automation-$it" }
        val screen = intent.getStringExtra("spectrum_screen")?.takeIf { it in allowedScreens } ?: "profile"
        val scenario = intent.getStringExtra("spectrum_scenario")?.takeIf { it in (if (screen.startsWith("automation-")) automationProbeScenarios else businessProbeScenarios) } ?: "ready"
        val probeRun = intent.getStringExtra("spectrum_probe_run")?.takeIf { it.matches(Regex("[a-f0-9]{32}")) }.orEmpty()
        val themeRequest = if (screen == "theme") ThemeProbeRequest.parse(
            intent.getStringExtra("theme_group"), intent.getStringExtra("theme_mode"),
            intent.getStringExtra("theme_accent"), intent.getStringExtra("theme_motion"), probeRun) else null
        val lifecycleRequest = if (screen == THEME_LIFECYCLE_SCREEN) ThemeLifecycleRequest.parse(
            intent.getStringExtra("theme_lifecycle_session"), intent.getStringExtra("theme_lifecycle_phase"), probeRun) else null
        val lifecycleSession = lifecycleRequest?.let { ThemeLifecycleSession.open(this, it) }
        if (screen == "strategy") getSharedPreferences("strategy_draft_synthetic-ui-test", 0).edit().clear().apply()
        check(runWorkspaceUxChecks() == 24)
        check(runInstrumentLinkRegressions() == 15)
        val researchChecks = runResearchPresentationChecks()
        val refreshChecks = runRefreshStateRegressionChecks()
        val educationChecks = runEducationCatalogChecks()
        val updateChecks = runUpdatePolicyChecks()
        val installChecks = runInstallStreamChecks()
        val protocolChecks = runUpdateProtocolChecks()
        val downloadChecks = runUpdateDownloadChecks()
        val gateChecks = runUpdateGateUiChecks()
        val feedbackChecks = runUpdateFeedbackChecks()
        val submissionChecks = runInstallSubmissionChecks()
        val analysisChecks = runAnalysisPresentationChecks()
        check(runPortfolioGeometryChecks() == 67)
        check(runPositionSelectionChecks() == 18)
        check(runInstrumentDetailsChecks() == 18)
        val releaseJsonChecks = runReleaseJsonChecks()
        setContent {
            AnalystTheme {
                val background = MaterialTheme.colorScheme.background.toArgb().toUInt().toString(16)
                val foreground = LocalContentColor.current.toArgb().toUInt().toString(16)
                val automationTransport = remember { AutomationProbeTransport("ready") }
                var screenshotsBlocked by remember { mutableStateOf(false) }
                var appearanceOpen by remember { mutableStateOf(false) }
                var educationOpen by remember { mutableStateOf(screen == "education") }
                val readinessMarker = "probe-screen:$screen;probe-scenario:$scenario;probe-run:$probeRun;probe-background:$background;probe-foreground:$foreground;probe-primary-foreground:${MaterialTheme.colorScheme.onPrimary.toArgb().toUInt().toString(16)};probe-refresh-tests:$refreshChecks;probe-education-tests:$educationChecks;probe-update-tests:$updateChecks;probe-install-stream-tests:$installChecks;probe-protocol-tests:$protocolChecks;probe-download-tests:$downloadChecks;probe-gate-tests:$gateChecks;probe-feedback-tests:$feedbackChecks;probe-submission-tests:$submissionChecks;probe-analysis-tests:$analysisChecks;probe-release-json-tests:$releaseJsonChecks;probe-research-presentation-tests:$researchChecks;probe-edge-to-edge:true;${spatialProbeMarker()}"
                Box(
                    Modifier
                        .fillMaxSize()
                        .semantics { contentDescription = readinessMarker },
                ) {
                    CompositionLocalProvider(LocalWorkspaceNavigator provides { if (it == WorkspaceRoute.Appearance) appearanceOpen = true },
                        LocalSpectrumTabScrollTag provides "profile-tabs") {
                    when {
                        appearanceOpen -> AppearanceScreen { appearanceOpen = false }
                        screen == "spatial" -> SpatialRendererProbe()
                        screen == "theme" -> ThemeStateProbe(requireNotNull(themeRequest))
                        screen == THEME_LIFECYCLE_SCREEN -> ThemeLifecycleProbe(requireNotNull(lifecycleSession))
                        screen == "session-context" -> SessionContextProbe()
                        screen == "balance-privacy" -> BalancePrivacyProbe()
                        screen == "goal-editor" -> GoalWorkflowProbe { finish() }
                        screen.startsWith("automation-") -> AutomationWorkspaceProbe(screen, scenario)
                        screen.startsWith("business-") -> BusinessWorkspaceProbe(screen, scenario, onBack = { finish() })
                        screen.startsWith("portfolio-") -> PortfolioWorkspaceProbe(screen, scenario, onBack = { finish() })
                        screen !in setOf("profile", "education") -> SpectrumDashboardProbe(screen)
                        educationOpen -> EducationScreen(onBack = { educationOpen = false }, onPortfolioClick = {}, onProfileClick = { educationOpen = false })
                        else -> AutomationProbeProvider(automationTransport) { ProfileScreen(
                            user = AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                            tApiConfigured = false, screenshotsBlocked = screenshotsBlocked,
                            onScreenshotsBlockedChange = { screenshotsBlocked = it },
                            onPortfolioClick = {}, onOpenTApi = {},
                            onOpenEducation = { educationOpen = true }, onLogout = {},
                        ) }
                    }

                    }
                    // Complex dashboards may contribute many accessibility nodes.
                    // Keep one tiny, independent debug-only node so readiness is
                    // not inferred from an old tree or lost by semantics merging.
                    Box(
                        Modifier
                            .align(Alignment.TopStart)
                            .size(2.dp)
                            .zIndex(100f)
                            .clearAndSetSemantics { contentDescription = readinessMarker },
                    )
                }
            }
        }
    }
}

