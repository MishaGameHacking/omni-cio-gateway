package ru.omnicio.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.updates.AppRelease
import ru.omnicio.app.data.updates.AppUpdateClient
import ru.omnicio.app.data.updates.AppUpdateInstaller
import ru.omnicio.app.data.updates.AppUpdateVerifier
import ru.omnicio.app.data.updates.UpdateCheckStore
import ru.omnicio.app.data.updates.UpdateFlow
import ru.omnicio.app.data.updates.UpdateStage
import ru.omnicio.app.ui.spectrum.RequiredUpdateScreen
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.AnalystTheme

private sealed interface BootstrapState {
    data object Checking : BootstrapState
    data class Blocked(val release: AppRelease, val flow: UpdateFlow) : BootstrapState
}

class BootstrapActivity : ComponentActivity() {
    private val client = AppUpdateClient()
    private val store by lazy { UpdateCheckStore(this) }
    private val verifier by lazy { AppUpdateVerifier(this) }
    private val installer by lazy { AppUpdateInstaller(this) }
    private var state by mutableStateOf<BootstrapState>(BootstrapState.Checking)
    private var checkRunning = false
    private var downloadRunning = false
    private var awaitingInstallPermission = false
    private var resumeOnly = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        resumeOnly = intent.getBooleanExtra(EXTRA_RESUME_CHECK, false)
        onBackPressedDispatcher.addCallback(
            this,
            object : OnBackPressedCallback(true) {
                override fun handleOnBackPressed() {
                    moveTaskToBack(true)
                }
            },
        )
        setContent {
            AnalystTheme {
                when (val current = state) {
                    BootstrapState.Checking -> CheckingScreen()
                    is BootstrapState.Blocked -> RequiredUpdateScreen(
                        state = current.flow,
                        versionLabel = current.release.versionName,
                        onUpdate = ::beginUpdate,
                        onHelp = ::openUpdateHelp,
                        onSignOut = ::signOut,
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // A Telegram callback arriving while a foreground recheck is visible must
        // be forwarded to MainActivity after the policy check, not silently dropped.
        resumeOnly = intent.getBooleanExtra(EXTRA_RESUME_CHECK, false)
        checkRunning = false
        checkPolicy()
    }

    override fun onResume() {
        super.onResume()
        if (awaitingInstallPermission) {
            awaitingInstallPermission = false
            if (installer.canInstallPackages()) {
                beginUpdate()
            } else {
                failBlocked("Android не разрешил установку обновлений для Analyst AI.")
            }
            return
        }
        val expected = store.expectedVersion()
        if (store.isInstalling() && expected > 0L) {
            val installed = runCatching { verifier.installedVersionCode() }.getOrDefault(0L)
            if (installed >= expected) {
                store.markInstallFinished()
                checkRunning = false
                checkPolicy()
                return
            }
        }
        store.consumeInstallError()?.let {
            failBlocked(it)
            return
        }
        checkPolicy()
    }

    private fun checkPolicy() {
        if (checkRunning || downloadRunning) return
        checkRunning = true
        store.markAttempt()
        state = BootstrapState.Checking
        lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    val certificate = verifier.installedCertificateSha256()
                    val fresh = runCatching { client.fetchRelease() }.getOrNull()
                    val release = fresh ?: store.cachedRelease(allowExpired = store.isPolicyBlocked())
                    if (release == null) return@runCatching null
                    release.validate(packageName, certificate)
                    if (fresh != null) store.cacheRelease(release)
                    release
                }
            }
            checkRunning = false
            val release = result.getOrNull()
            if (release == null) {
                if (store.isPolicyBlocked()) {
                    failBlocked("Не удалось проверить обновление. Подключитесь к интернету и повторите.")
                } else {
                    openApplication()
                }
                return@launch
            }
            val installed = runCatching { verifier.installedVersionCode() }.getOrElse {
                state = BootstrapState.Blocked(
                    release,
                    UpdateFlow(release.minimumSupported, release.versionCode)
                        .failed("Не удалось определить установленную версию приложения."),
                )
                return@launch
            }
            val flow = UpdateFlow(release.minimumSupported, release.versionCode)
                .withInstalledVersion(installed)
            if (flow.stage == UpdateStage.Current) {
                store.setPolicyBlocked(false)
                store.markInstallFinished()
                openApplication()
            } else {
                store.setPolicyBlocked(true)
                state = BootstrapState.Blocked(release, flow)
            }
        }
    }

    private fun beginUpdate() {
        if (downloadRunning) return
        val blocked = state as? BootstrapState.Blocked ?: return
        if (!installer.canInstallPackages()) {
            awaitingInstallPermission = true
            val settings = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:$packageName"),
            )
            startActivity(settings)
            return
        }
        downloadRunning = true
        var flow = blocked.flow.beginDownload()
        state = blocked.copy(flow = flow)
        lifecycleScope.launch {
            val apk = File(cacheDir, "updates/${blocked.release.versionCode}-${blocked.release.sha256}.apk")
            val result = withContext(Dispatchers.IO) {
                runCatching {
                    client.download(blocked.release, apk) { received, total ->
                        runOnUiThread {
                            val current = state as? BootstrapState.Blocked ?: return@runOnUiThread
                            val updated = runCatching { current.flow.progress(received, total) }.getOrNull()
                                ?: return@runOnUiThread
                            state = current.copy(flow = updated)
                        }
                    }
                    apk
                }
            }
            val downloaded = result.getOrElse {
                downloadRunning = false
                apk.delete()
                failBlocked(it.message ?: "Не удалось скачать обновление.")
                return@launch
            }
            val current = state as? BootstrapState.Blocked ?: return@launch
            flow = current.flow.finishDownload()
            state = current.copy(flow = flow)
            val verification = withContext(Dispatchers.IO) {
                runCatching { verifier.verify(blocked.release, downloaded) }
            }
            verification.getOrElse {
                downloadRunning = false
                downloaded.delete()
                failBlocked(it.message ?: "APK не прошёл проверку безопасности.")
                return@launch
            }
            val verified = (state as BootstrapState.Blocked).flow.verified()
            state = blocked.copy(flow = verified)
            val installation = withContext(Dispatchers.IO) {
                runCatching { installer.install(blocked.release, downloaded) }
            }
            downloadRunning = false
            installation.getOrElse {
                failBlocked(it.message ?: "Не удалось запустить системный установщик.")
                return@launch
            }
            val waiting = (state as? BootstrapState.Blocked)?.flow?.userActionRequired()
                ?: blocked.flow.userActionRequired()
            state = blocked.copy(flow = waiting)
        }
    }

    private fun failBlocked(message: String) {
        val blocked = state as? BootstrapState.Blocked
        val release = blocked?.release ?: store.cachedRelease(allowExpired = true) ?: return
        val flow = blocked?.flow
            ?: UpdateFlow(release.minimumSupported, release.versionCode)
                .withInstalledVersion(runCatching { verifier.installedVersionCode() }.getOrDefault(1L))
        state = BootstrapState.Blocked(release, flow.failed(message))
    }

    private fun openUpdateHelp() {
        if (!installer.canInstallPackages()) {
            awaitingInstallPermission = true
            startActivity(
                Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:$packageName"),
                ),
            )
            return
        }
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://$UPDATE_HOST/releases/help.html")))
    }

    private fun signOut() {
        lifecycleScope.launch(Dispatchers.IO) {
            runCatching { AuthSessionStore(this@BootstrapActivity).clear() }
        }
        failBlocked("Сеанс завершён. Для работы всё равно требуется актуальная версия приложения.")
    }

    private fun openApplication() {
        if (resumeOnly) {
            finish()
            return
        }
        val next = Intent(this, MainActivity::class.java).apply {
            action = intent.action
            data = intent.data
            intent.categories?.forEach { category -> addCategory(category) }
            intent.extras?.let { extras -> putExtras(extras) }
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        startActivity(next)
        finish()
    }

    companion object {
        const val EXTRA_RESUME_CHECK = "resume_update_check"
        private const val UPDATE_HOST = "176.98.178.81.sslip.io"
    }
}

@Composable
private fun CheckingScreen() {
    SpectrumBackground(Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize().padding(28.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Update,
                modifier = Modifier.size(112.dp),
                selected = true,
                tile = true,
                motionAllowed = true,
            )
            CircularProgressIndicator(modifier = Modifier.padding(top = 24.dp))
            Text(
                text = "Проверяем версию Analyst AI",
                modifier = Modifier.padding(top = 18.dp),
                style = MaterialTheme.typography.titleLarge,
            )
        }
    }
}
