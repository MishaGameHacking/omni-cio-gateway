package ru.omnicio.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.browser.auth.AuthTabIntent
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
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
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.analysis.AnalysisProfileSettingsScreen
import ru.omnicio.app.ui.analysis.IdeasScreen
import ru.omnicio.app.ui.analysis.InsightFeedScreen
import ru.omnicio.app.ui.analysis.PulseScreen
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.theme.AnalystTheme
import ru.omnicio.app.data.portfolio.rememberLivePortfolio
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.profile.TApiScreen

private enum class AppScreen {
    Portfolio,
    Ideas,
    Pulse,
    Chat,
    Profile,
    AnalysisSettings,
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
    private val pendingAuthError = mutableStateOf<String?>(null)
    private var redirectReceivedForCurrentLogin = false
    private var lastHandledRedirect: String? = null

    private val authTabLauncher = AuthTabIntent.registerActivityResultLauncher(this) { result ->
        val resultUri = result.resultUri
        if (result.resultCode == AuthTabIntent.RESULT_OK && resultUri != null) {
            if (!captureTelegramCallback(resultUri) && !redirectReceivedForCurrentLogin) {
                pendingAuthError.value = "Telegram вернул неизвестную ссылку. Попробуйте ещё раз."
            }
        } else if (!redirectReceivedForCurrentLogin) {
            pendingAuthError.value = when (result.resultCode) {
                AuthTabIntent.RESULT_VERIFICATION_FAILED ->
                    "Браузер не смог проверить ссылку авторизации."
                AuthTabIntent.RESULT_VERIFICATION_TIMED_OUT ->
                    "Время ожидания подтверждения истекло. Попробуйте ещё раз."
                else -> "Вход через Telegram не завершён."
            }
        }
    }

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
                authError = pendingAuthError.value,
                onStartTelegramLogin = ::launchTelegramLogin,
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

    private fun captureTelegramCallback(incoming: Intent?) {
        val data = incoming?.data ?: return
        if (captureTelegramCallback(data)) {
            // Prevent an Activity restart from consuming the same one-time code again.
            incoming.data = null
            setIntent(incoming)
        }
    }

    private fun captureTelegramCallback(data: Uri): Boolean {
        if (data.scheme != AUTH_SCHEME || data.host != AUTH_HOST) {
            return false
        }

        redirectReceivedForCurrentLogin = true
        if (data.toString() == lastHandledRedirect) {
            return true
        }
        lastHandledRedirect = data.toString()
        val code = data.getQueryParameter("code")?.takeIf { it.isNotBlank() }
        val error = data.getQueryParameter("error")
        pendingAuthCode.value = if (error == null) code else null
        pendingAuthError.value = when (error) {
            "telegram_denied" -> "Вы отменили подтверждение входа в Telegram."
            "telegram_expired" -> "Время авторизации истекло. Попробуйте войти снова."
            "telegram_unavailable" -> "Telegram временно недоступен. Попробуйте позже."
            "telegram_exchange_failed" ->
                "Telegram отклонил обмен кода. Проверьте настройки Login Widget."
            "telegram_invalid_token" -> "Не удалось подтвердить данные Telegram."
            "telegram_invalid_response" -> "Telegram вернул некорректный ответ."
            null -> if (code == null) "Не получен код входа от Telegram." else null
            else -> "Не удалось завершить вход через Telegram."
        }
        return true
    }

    private fun launchTelegramLogin() {
        redirectReceivedForCurrentLogin = false
        lastHandledRedirect = null
        pendingAuthError.value = null
        runCatching {
            val authTab = AuthTabIntent.Builder().build()
            authTab.launch(
                authTabLauncher,
                Uri.parse("${BackendConfig.BASE_URL}/auth/telegram/start"),
                AUTH_SCHEME,
            )
        }.onFailure {
            pendingAuthError.value = "Не удалось открыть браузер для входа через Telegram."
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
private fun AnalystAiAppContent(
    authCode: String?,
    authError: String?,
    onStartTelegramLogin: () -> Unit,
    onAuthCodeConsumed: () -> Unit,
    initialScreenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val sessionStore = remember(context) { AuthSessionStore(context) }
    val legacyTInvestStore = remember(context) { TInvestTokenStore(context) }
    val backend = remember { AnalystBackendClient() }

    var authState by remember { mutableStateOf<AuthUiState>(AuthUiState.Loading) }
    var initialSessionChecked by remember { mutableStateOf(false) }
    var screenName by rememberSaveable { mutableStateOf(AppScreen.Portfolio.name) }
    val screen = remember(screenName) {
        runCatching { AppScreen.valueOf(screenName) }.getOrDefault(AppScreen.Portfolio)
    }
    var tApiConfigured by remember { mutableStateOf(false) }
    var portfolioCurrencyName by rememberSaveable {
        mutableStateOf(PortfolioCurrency.RUB.name)
    }
    val portfolioCurrency = remember(portfolioCurrencyName) {
        runCatching { PortfolioCurrency.valueOf(portfolioCurrencyName) }
            .getOrDefault(PortfolioCurrency.RUB)
    }
    var screenshotsBlocked by rememberSaveable {
        mutableStateOf(initialScreenshotsBlocked)
    }

    // One effect owns both startup restoration and incoming login codes.
    // Cancelling startup restoration when a callback arrives prevents it from
    // overwriting a freshly authenticated session with SignedOut.
    LaunchedEffect(authCode) {
        val code = authCode?.takeIf { it.isNotBlank() }
        if (code != null) {
            initialSessionChecked = true
            authState = AuthUiState.Loading
            when (val result = withContext(Dispatchers.IO) {
                backend.exchangeTelegramCode(code)
            }) {
                is BackendResult.Success -> {
                    val saved = withContext(Dispatchers.IO) {
                        runCatching { sessionStore.save(result.value) }.isSuccess
                    }
                    authState = if (saved) {
                        AuthUiState.SignedIn(
                            accessToken = result.value.accessToken,
                            user = result.value.user,
                        )
                    } else {
                        AuthUiState.SignedOut(
                            errorMessage = "Не удалось сохранить вход на устройстве. Попробуйте ещё раз.",
                        )
                    }
                }
                is BackendResult.Failure -> {
                    authState = AuthUiState.SignedOut(
                        errorMessage = result.message,
                    )
                }
            }
            onAuthCodeConsumed()
        } else if (!initialSessionChecked) {
            val storedToken = withContext(Dispatchers.IO) {
                sessionStore.loadAccessToken()
            }
            authState = if (storedToken == null) {
                AuthUiState.SignedOut()
            } else {
                when (val result = withContext(Dispatchers.IO) {
                    backend.fetchMe(storedToken)
                }) {
                    is BackendResult.Success -> {
                        AuthUiState.SignedIn(
                            accessToken = storedToken,
                            user = result.value,
                        )
                    }
                    is BackendResult.Failure -> {
                        if (result.retryable) {
                            val cachedUser = withContext(Dispatchers.IO) {
                                sessionStore.loadCachedUser()
                            }
                            if (cachedUser != null) {
                                AuthUiState.SignedIn(
                                    accessToken = storedToken,
                                    user = cachedUser,
                                )
                            } else {
                                AuthUiState.SignedOut(errorMessage = result.message)
                            }
                        } else {
                            withContext(Dispatchers.IO) {
                                sessionStore.clear()
                            }
                            AuthUiState.SignedOut()
                        }
                    }
                }
            }
            initialSessionChecked = true
        }
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

    val livePortfolio = rememberLivePortfolio(signedIn?.accessToken, tApiConfigured, portfolioCurrency)
    val portfolioState = livePortfolio.state

    AnalystTheme {
        when (val current = authState) {
            AuthUiState.Loading -> {
                TelegramLoginScreen(
                    loading = true,
                    errorMessage = authError,
                    onLoginClick = onStartTelegramLogin,
                )
            }

            is AuthUiState.SignedOut -> {
                TelegramLoginScreen(
                    loading = false,
                    errorMessage = current.errorMessage ?: authError,
                    onLoginClick = onStartTelegramLogin,
                )
            }

            is AuthUiState.SignedIn -> {
                val navigateToTab: (AnalystTab) -> Unit = { tab ->
                    screenName = when (tab) {
                        AnalystTab.Portfolio -> AppScreen.Portfolio
                        AnalystTab.Ideas -> AppScreen.Ideas
                        AnalystTab.Pulse -> AppScreen.Pulse
                        AnalystTab.Chat -> AppScreen.Chat
                        AnalystTab.Profile -> AppScreen.Profile
                    }.name
                }

                CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab) {
                    when (screen) {
                        AppScreen.Portfolio -> {
                            PortfolioScreen(
                                state = portfolioState,
                                accessToken = current.accessToken,
                                refreshing = livePortfolio.refreshing,
                                refreshError = livePortfolio.error,
                                lastUpdatedMillis = livePortfolio.lastSuccessMillis,
                                selectedCurrency = portfolioCurrency,
                                onCurrencyClick = {
                                    portfolioCurrencyName = portfolioCurrency.next().name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

                        AppScreen.Ideas -> {
                            IdeasScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                                onOpenProfileSettings = {
                                    screenName = AppScreen.AnalysisSettings.name
                                },
                            )
                        }

                        AppScreen.Pulse -> {
                            PulseScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

                        AppScreen.Chat -> {
                            InsightFeedScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
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
                                onOpenAnalysisSettings = {
                                    screenName = AppScreen.AnalysisSettings.name
                                },
                                onLogout = {
                                    sessionStore.clear()
                                    screenName = AppScreen.Portfolio.name
                                    tApiConfigured = false
                                    authState = AuthUiState.SignedOut()
                                },
                            )
                        }

                        AppScreen.AnalysisSettings -> {
                            AnalysisProfileSettingsScreen(
                                accessToken = current.accessToken,
                                onBack = {
                                    screenName = AppScreen.Profile.name
                                },
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
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
}

@Preview(showBackground = true)
@Composable
private fun AnalystAiAppPreview() {
    AnalystTheme {
        PortfolioScreen(
            state = PortfolioUiState.NotConnected,
            onProfileClick = {},
        )
    }
}

@Composable
private fun AnalystAiApp(
    authCode: String?, authError: String?, onStartTelegramLogin: () -> Unit,
    onAuthCodeConsumed: () -> Unit, initialScreenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
) {
    ru.omnicio.app.ui.updates.MandatoryUpdateHost {
        AnalystAiAppContent(authCode, authError, onStartTelegramLogin, onAuthCodeConsumed,
            initialScreenshotsBlocked, onScreenshotsBlockedChange)
    }
}

