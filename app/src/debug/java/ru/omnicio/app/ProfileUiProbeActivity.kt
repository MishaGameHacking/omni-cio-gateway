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

/** Debug-only UI fixture. No network calls or authentication bypass in preview. */
class ProfileUiProbeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Match MainActivity's coordinate system and safeDrawing insets. A
        // non-edge-to-edge fixture is not evidence for the production layout.
        enableEdgeToEdge()
        val allowedScreens = setOf("home", "portfolio", "appearance", "strategy", "assistant", "market", "ux100", "spatial") +
            businessProbeRoutes.map { "business-$it" }
        val screen = intent.getStringExtra("spectrum_screen")?.takeIf { it in allowedScreens } ?: "profile"
        val scenario = intent.getStringExtra("spectrum_scenario")?.takeIf { it in businessProbeScenarios } ?: "ready"
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
                var screenshotsBlocked by remember { mutableStateOf(false) }
                var appearanceOpen by remember { mutableStateOf(false) }
                var educationOpen by remember { mutableStateOf(false) }
                val readinessMarker = "probe-screen:$screen;probe-scenario:$scenario;probe-background:$background;probe-foreground:$foreground;probe-refresh-tests:$refreshChecks;probe-education-tests:$educationChecks;probe-update-tests:$updateChecks;probe-install-stream-tests:$installChecks;probe-protocol-tests:$protocolChecks;probe-download-tests:$downloadChecks;probe-gate-tests:$gateChecks;probe-feedback-tests:$feedbackChecks;probe-submission-tests:$submissionChecks;probe-analysis-tests:$analysisChecks;probe-release-json-tests:$releaseJsonChecks;probe-research-presentation-tests:$researchChecks;probe-edge-to-edge:true;${spatialProbeMarker()}"
                Box(
                    Modifier
                        .fillMaxSize()
                        .semantics { contentDescription = readinessMarker },
                ) {
                    CompositionLocalProvider(LocalWorkspaceNavigator provides { if (it == WorkspaceRoute.Appearance) appearanceOpen = true },
                        LocalSpectrumTabScrollTag provides "profile-tabs") {
                    if (appearanceOpen) AppearanceScreen { appearanceOpen = false }
                    else if (screen == "spatial") SpatialRendererProbe()
                    else if (screen.startsWith("business-")) BusinessWorkspaceProbe(screen, scenario, onBack = { finish() })
                    else if (screen != "profile") {
                        SpectrumDashboardProbe(screen)
                    } else if (educationOpen) {
                        EducationScreen(onBack = { educationOpen = false }, onPortfolioClick = {}, onProfileClick = { educationOpen = false })
                    } else {
                        ProfileScreen(
                            user = AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                            tApiConfigured = false, screenshotsBlocked = screenshotsBlocked,
                            onScreenshotsBlockedChange = { screenshotsBlocked = it },
                            onPortfolioClick = {}, onOpenTApi = {},
                            onOpenEducation = { educationOpen = true }, onLogout = {},
                        )
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
