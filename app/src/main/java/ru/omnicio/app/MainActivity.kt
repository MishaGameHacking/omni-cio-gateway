package ru.omnicio.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.browser.auth.AuthTabIntent
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
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.portfolio.rememberLivePortfolio
import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.analysis.AnalysisProfileSettingsScreen
import ru.omnicio.app.ui.analysis.IdeasScreen
import ru.omnicio.app.ui.analysis.InsightFeedScreen
import ru.omnicio.app.ui.analysis.PulseScreen
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.education.EducationScreen
import ru.omnicio.app.ui.home.HomeScreen
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.profile.TApiScreen
import ru.omnicio.app.ui.spectrum.RequiredUpdateScreen
import ru.omnicio.app.ui.theme.AnalystTheme
import ru.omnicio.app.ui.updates.MandatoryUpdateHost

private enum class AppScreen {
    Home,
    Portfolio,
    Recommendations,
    Risk,
    Messages,
    Profile,
    Education,
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
            MandatoryUpdateHost(blockedContent = { state, actions -> RequiredUpdateScreen(state, actions) }) {
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
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        captureTelegramCallback(intent)
    }

    private fun captureTelegramCallback(incoming: Intent?) {
        val data = incoming?.data ?: return
        if (captureTelegramCallback(data)) {
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
private fun AnalystAiApp(
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
    var screenName by rememberSaveable { mutableStateOf(AppScreen.Home.name) }
    val screen = remember(screenName) {
        runCatching { AppScreen.valueOf(screenName) }.getOrDefault(AppScreen.Home)
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

    val livePortfolio = rememberLivePortfolio(
        signedIn?.accessToken,
        tApiConfigured,
        portfolioCurrency,
    )

    AnalystTheme {
        AnalystAppContent(
            authState = authState,
            authError = authError,
            onStartTelegramLogin = onStartTelegramLogin,
            screen = screen,
            portfolioState = livePortfolio.state,
            portfolioRefreshing = livePortfolio.refreshing,
            portfolioError = livePortfolio.error,
            portfolioLastSuccessMillis = livePortfolio.lastSuccessMillis,
            portfolioCurrency = portfolioCurrency,
            tApiConfigured = tApiConfigured,
            screenshotsBlocked = screenshotsBlocked,
            onScreenChange = { destination ->
                screenName = destination.name
            },
            onCurrencyChange = { currency ->
                portfolioCurrencyName = currency.name
            },
            onTApiConfiguredChange = { configured ->
                tApiConfigured = configured
            },
            onScreenshotsBlockedChange = { blocked ->
                screenshotsBlocked = blocked
                onScreenshotsBlockedChange(blocked)
            },
            onLogout = {
                sessionStore.clear()
                screenName = AppScreen.Home.name
                tApiConfigured = false
                authState = AuthUiState.SignedOut()
            },
        )
    }
}

@Composable
private fun AnalystAppContent(
    authState: AuthUiState,
    authError: String?,
    onStartTelegramLogin: () -> Unit,
    screen: AppScreen,
    portfolioState: PortfolioUiState,
    portfolioRefreshing: Boolean,
    portfolioError: String?,
    portfolioLastSuccessMillis: Long?,
    portfolioCurrency: PortfolioCurrency,
    tApiConfigured: Boolean,
    screenshotsBlocked: Boolean,
    onScreenChange: (AppScreen) -> Unit,
    onCurrencyChange: (PortfolioCurrency) -> Unit,
    onTApiConfiguredChange: (Boolean) -> Unit,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
    onLogout: () -> Unit,
) {
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
            SignedInAppContent(
                session = current,
                screen = screen,
                portfolioState = portfolioState,
                portfolioRefreshing = portfolioRefreshing,
                portfolioError = portfolioError,
                portfolioLastSuccessMillis = portfolioLastSuccessMillis,
                portfolioCurrency = portfolioCurrency,
                tApiConfigured = tApiConfigured,
                screenshotsBlocked = screenshotsBlocked,
                onScreenChange = onScreenChange,
                onCurrencyChange = onCurrencyChange,
                onTApiConfiguredChange = onTApiConfiguredChange,
                onScreenshotsBlockedChange = onScreenshotsBlockedChange,
                onLogout = onLogout,
            )
        }
    }
}

@Composable
private fun SignedInAppContent(
    session: AuthUiState.SignedIn,
    screen: AppScreen,
    portfolioState: PortfolioUiState,
    portfolioRefreshing: Boolean,
    portfolioError: String?,
    portfolioLastSuccessMillis: Long?,
    portfolioCurrency: PortfolioCurrency,
    tApiConfigured: Boolean,
    screenshotsBlocked: Boolean,
    onScreenChange: (AppScreen) -> Unit,
    onCurrencyChange: (PortfolioCurrency) -> Unit,
    onTApiConfiguredChange: (Boolean) -> Unit,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
    onLogout: () -> Unit,
) {
    val navigateToTab: (AnalystTab) -> Unit = { tab ->
        onScreenChange(tab.toAppScreen())
    }
    val openHome = { onScreenChange(AppScreen.Home) }
    val openPortfolio = { onScreenChange(AppScreen.Portfolio) }
    val openProfile = { onScreenChange(AppScreen.Profile) }

    CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab) {
        when (screen) {
            AppScreen.Home -> {
                HomeScreen(
                    user = session.user,
                    state = portfolioState,
                    refreshing = portfolioRefreshing,
                    refreshError = portfolioError,
                    lastUpdatedMillis = portfolioLastSuccessMillis,
                    selectedCurrency = portfolioCurrency,
                    onCurrencyClick = {
                        onCurrencyChange(portfolioCurrency.next())
                    },
                    onOpenPortfolio = openPortfolio,
                    onOpenRecommendations = {
                        onScreenChange(AppScreen.Recommendations)
                    },
                    onOpenRisk = {
                        onScreenChange(AppScreen.Risk)
                    },
                    onOpenMessages = {
                        onScreenChange(AppScreen.Messages)
                    },
                    onOpenEducation = {
                        onScreenChange(AppScreen.Education)
                    },
                    onOpenProfile = openProfile,
                )
            }

            AppScreen.Portfolio -> {
                PortfolioScreen(
                    state = portfolioState,
                    accessToken = session.accessToken,
                    refreshing = portfolioRefreshing,
                    refreshError = portfolioError,
                    lastUpdatedMillis = portfolioLastSuccessMillis,
                    selectedCurrency = portfolioCurrency,
                    onCurrencyClick = {
                        onCurrencyChange(portfolioCurrency.next())
                    },
                    onProfileClick = openProfile,
                )
            }

            AppScreen.Recommendations -> {
                IdeasScreen(
                    accessToken = session.accessToken,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                    onOpenProfileSettings = {
                        onScreenChange(AppScreen.AnalysisSettings)
                    },
                )
            }

            AppScreen.Risk -> {
                PulseScreen(
                    accessToken = session.accessToken,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.Messages -> {
                InsightFeedScreen(
                    accessToken = session.accessToken,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.Profile -> {
                ProfileScreen(
                    user = session.user,
                    tApiConfigured = tApiConfigured,
                    screenshotsBlocked = screenshotsBlocked,
                    onScreenshotsBlockedChange = onScreenshotsBlockedChange,
                    onPortfolioClick = openPortfolio,
                    onOpenTApi = {
                        onScreenChange(AppScreen.TApi)
                    },
                    onOpenAnalysisSettings = {
                        onScreenChange(AppScreen.AnalysisSettings)
                    },
                    onOpenEducation = {
                        onScreenChange(AppScreen.Education)
                    },
                    onLogout = onLogout,
                )
            }

            AppScreen.Education -> {
                EducationScreen(
                    onBack = openHome,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.AnalysisSettings -> {
                AnalysisProfileSettingsScreen(
                    accessToken = session.accessToken,
                    onBack = openProfile,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.TApi -> {
                TApiScreen(
                    accessToken = session.accessToken,
                    tApiConfigured = tApiConfigured,
                    onBack = openProfile,
                    onConnectionChanged = onTApiConfiguredChange,
                )
            }
        }
    }
}

private fun AnalystTab.toAppScreen(): AppScreen = when (this) {
    AnalystTab.Home -> AppScreen.Home
    AnalystTab.Portfolio -> AppScreen.Portfolio
    AnalystTab.Risk -> AppScreen.Risk
    AnalystTab.Education -> AppScreen.Education
    AnalystTab.Profile -> AppScreen.Profile
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
