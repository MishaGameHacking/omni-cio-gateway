package ru.omnicio.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.tooling.preview.Preview
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.AnalystBackendClient
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.portfolio.PortfolioUiState
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.profile.TApiScreen

private enum class AppScreen {
    Portfolio,
    Profile,
    TApi,
}

private sealed interface AuthUiState {
    data object Loading : AuthUiState
    data class SignedOut(val errorMessage: String? = null) : AuthUiState
    data class SignedIn(
        val accessToken: String,
        val user: AnalystUser,
    ) : AuthUiState
}

class MainActivity : ComponentActivity() {
    private lateinit var settingsStore: AppSettingsStore
    private val pendingAuthCode = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        settingsStore = AppSettingsStore(this)
        val initialScreenshotsBlocked = settingsStore.screenshotsBlocked()
        applyScreenshotPolicy(initialScreenshotsBlocked)
        captureTelegramCallback(intent)

        setContent {
            AnalystAiApp(
                authCode = pendingAuthCode.value,
                onAuthCodeConsumed = {
                    pendingAuthCode.value = null
                },
                initialScreenshotsBlocked = initialScreenshotsBlocked,
                onScreenshotsBlockedChange = { blocked ->
                    settingsStore.setScreenshotsBlocked(blocked)
                    applyScreenshotPolicy(blocked)
                },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        captureTelegramCallback(intent)
    }

    private fun captureTelegramCallback(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme == AUTH_SCHEME && data.host == AUTH_HOST) {
            pendingAuthCode.value = data.getQueryParameter("code")
        }
    }

    private fun applyScreenshotPolicy(blocked: Boolean) {
        if (blocked) {
            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    private companion object {
        const val AUTH_SCHEME = "analystai"
        const val AUTH_HOST = "auth"
    }
}

@Composable
private fun AnalystAiApp(
    authCode: String?,
    onAuthCodeConsumed: () -> Unit,
    initialScreenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val sessionStore = remember(context) { AuthSessionStore(context) }
    val legacyTInvestStore = remember(context) { TInvestTokenStore(context) }
    val backend = remember { AnalystBackendClient() }

    var authState by remember { mutableStateOf<AuthUiState>(AuthUiState.Loading) }
    var screenName by rememberSaveable { mutableStateOf(AppScreen.Portfolio.name) }
    val screen = remember(screenName) {
        runCatching { AppScreen.valueOf(screenName) }.getOrDefault(AppScreen.Portfolio)
    }
    var tApiConfigured by remember { mutableStateOf(false) }
    var screenshotsBlocked by rememberSaveable {
        mutableStateOf(initialScreenshotsBlocked)
    }

    LaunchedEffect(Unit) {
        val storedToken = withContext(Dispatchers.IO) {
            sessionStore.loadAccessToken()
        }
        if (storedToken == null) {
            authState = AuthUiState.SignedOut()
        } else {
            when (val result = withContext(Dispatchers.IO) {
                backend.fetchMe(storedToken)
            }) {
                is BackendResult.Success -> {
                    authState = AuthUiState.SignedIn(
                        accessToken = storedToken,
                        user = result.value,
                    )
                }
                is BackendResult.Failure -> {
                    withContext(Dispatchers.IO) {
                        sessionStore.clear()
                    }
                    authState = AuthUiState.SignedOut()
                }
            }
        }
    }

    LaunchedEffect(authCode) {
        val code = authCode?.takeIf { it.isNotBlank() } ?: return@LaunchedEffect
        authState = AuthUiState.Loading
        when (val result = withContext(Dispatchers.IO) {
            backend.exchangeTelegramCode(code)
        }) {
            is BackendResult.Success -> {
                withContext(Dispatchers.IO) {
                    sessionStore.save(result.value)
                }
                authState = AuthUiState.SignedIn(
                    accessToken = result.value.accessToken,
                    user = result.value.user,
                )
            }
            is BackendResult.Failure -> {
                authState = AuthUiState.SignedOut(
                    errorMessage = result.message,
                )
            }
        }
        onAuthCodeConsumed()
    }

    val signedIn = authState as? AuthUiState.SignedIn
    LaunchedEffect(signedIn?.accessToken) {
        val session = signedIn ?: return@LaunchedEffect
        val status = withContext(Dispatchers.IO) {
            backend.fetchTInvestStatus(session.accessToken)
        }

        var connected = (status as? BackendResult.Success)?.value ?: false
        if (!connected) {
            val legacyToken = withContext(Dispatchers.IO) {
                legacyTInvestStore.load()
            }
            if (!legacyToken.isNullOrBlank()) {
                val migration = withContext(Dispatchers.IO) {
                    backend.saveTInvestToken(
                        accessToken = session.accessToken,
                        token = legacyToken,
                    )
                }
                if (migration is BackendResult.Success) {
                    withContext(Dispatchers.IO) {
                        legacyTInvestStore.clear()
                    }
                    connected = true
                }
            }
        }
        tApiConfigured = connected
    }

    MaterialTheme {
        when (val current = authState) {
            AuthUiState.Loading -> {
                TelegramLoginScreen(
                    loading = true,
                    errorMessage = null,
                )
            }

            is AuthUiState.SignedOut -> {
                TelegramLoginScreen(
                    loading = false,
                    errorMessage = current.errorMessage,
                )
            }

            is AuthUiState.SignedIn -> {
                when (screen) {
                    AppScreen.Portfolio -> {
                        PortfolioScreen(
                            state = if (tApiConfigured) {
                                PortfolioUiState.ApiConnected
                            } else {
                                PortfolioUiState.NotConnected
                            },
                            onProfileClick = {
                                screenName = AppScreen.Profile.name
                            },
                        )
                    }

                    AppScreen.Profile -> {
                        ProfileScreen(
                            user = current.user,
                            tApiConfigured = tApiConfigured,
                            screenshotsBlocked = screenshotsBlocked,
                            onScreenshotsBlockedChange = { blocked ->
                                screenshotsBlocked = blocked
                                onScreenshotsBlockedChange(blocked)
                            },
                            onPortfolioClick = {
                                screenName = AppScreen.Portfolio.name
                            },
                            onOpenTApi = {
                                screenName = AppScreen.TApi.name
                            },
                            onLogout = {
                                sessionStore.clear()
                                screenName = AppScreen.Portfolio.name
                                tApiConfigured = false
                                authState = AuthUiState.SignedOut()
                            },
                        )
                    }

                    AppScreen.TApi -> {
                        TApiScreen(
                            accessToken = current.accessToken,
                            tApiConfigured = tApiConfigured,
                            onBack = {
                                screenName = AppScreen.Profile.name
                            },
                            onConnectionChanged = { configured ->
                                tApiConfigured = configured
                            },
                        )
                    }
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun AnalystAiAppPreview() {
    MaterialTheme {
        PortfolioScreen(
            state = PortfolioUiState.NotConnected,
            onProfileClick = {},
        )
    }
}
