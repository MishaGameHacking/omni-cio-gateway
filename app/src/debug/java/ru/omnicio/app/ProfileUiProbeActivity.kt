package ru.omnicio.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.ui.education.EducationScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.theme.AnalystTheme

/** Debug-only UI fixture. No network calls or authentication bypass in preview. */
class ProfileUiProbeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
        check(runPortfolioGeometryChecks() == 50)
        check(runPositionSelectionChecks() == 18)
        check(runInstrumentDetailsChecks() == 18)
        val releaseJsonChecks = runReleaseJsonChecks()
        setContent {
            AnalystTheme {
                val background = MaterialTheme.colorScheme.background.toArgb().toUInt().toString(16)
                var screenshotsBlocked by remember { mutableStateOf(false) }
                var educationOpen by remember { mutableStateOf(false) }
                Box(Modifier.fillMaxSize().semantics {
                    contentDescription = "probe-background:$background;probe-refresh-tests:$refreshChecks;probe-education-tests:$educationChecks;probe-update-tests:$updateChecks;probe-install-stream-tests:$installChecks;probe-protocol-tests:$protocolChecks;probe-download-tests:$downloadChecks;probe-gate-tests:$gateChecks;probe-feedback-tests:$feedbackChecks;probe-submission-tests:$submissionChecks;probe-analysis-tests:$analysisChecks;probe-release-json-tests:$releaseJsonChecks"
                }) {
                    if (educationOpen) {
                        EducationScreen(onBack = { educationOpen = false }, onPortfolioClick = {}, onProfileClick = { educationOpen = false })
                    } else {
                        ProfileScreen(
                            user = AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                            tApiConfigured = false, screenshotsBlocked = screenshotsBlocked,
                            onScreenshotsBlockedChange = { screenshotsBlocked = it },
                            onPortfolioClick = {}, onOpenTApi = {}, onOpenAnalysisSettings = {},
                            onOpenEducation = { educationOpen = true }, onLogout = {},
                        )
                    }
                }
            }
        }
    }
}
