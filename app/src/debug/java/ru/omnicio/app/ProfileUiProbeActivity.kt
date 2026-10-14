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
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.theme.AnalystTheme

/** Debug-only UI fixture. No network calls or authentication bypass in preview. */
class ProfileUiProbeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        check(runInstrumentLinkRegressions() == 15)
        val researchChecks = runResearchPresentationChecks()
        val checksPassed = runRefreshStateRegressionChecks()
        val updateChecksPassed = runUpdatePolicyChecks()
        val installChecksPassed = runInstallStreamChecks()
        val protocolChecksPassed = runUpdateProtocolChecks()
        val downloadChecksPassed = runUpdateDownloadChecks()
        val gateChecksPassed = runUpdateGateUiChecks()
        val feedbackChecksPassed = runUpdateFeedbackChecks()
        val submissionChecksPassed = runInstallSubmissionChecks()
        val releaseJsonChecks = runReleaseJsonChecks()
        setContent {
            AnalystTheme {
                val background = MaterialTheme.colorScheme.background.toArgb().toUInt().toString(16)
                var screenshotsBlocked by remember { mutableStateOf(false) }
                Box(Modifier.fillMaxSize().semantics {
                    contentDescription = "probe-background:$background;probe-refresh-tests:$checksPassed;probe-update-tests:$updateChecksPassed;probe-install-stream-tests:$installChecksPassed;probe-protocol-tests:$protocolChecksPassed;probe-download-tests:$downloadChecksPassed;probe-gate-tests:$gateChecksPassed;probe-feedback-tests:$feedbackChecksPassed;probe-submission-tests:$submissionChecksPassed;probe-release-json-tests:$releaseJsonChecks;probe-research-presentation-tests:$researchChecks"
                }) {
                    ProfileScreen(
                        user = AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                        tApiConfigured = false, screenshotsBlocked = screenshotsBlocked,
                        onScreenshotsBlockedChange = { screenshotsBlocked = it },
                        onPortfolioClick = {}, onOpenTApi = {}, onOpenAnalysisSettings = {}, onLogout = {},
                    )
                }
            }
        }
    }
}
