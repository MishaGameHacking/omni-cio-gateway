package ru.omnicio.app

import androidx.activity.compose.BackHandler
import androidx.compose.animation.*
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.Column
import androidx.compose.animation.core.tween
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
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
import androidx.compose.ui.Modifier
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
import ru.omnicio.app.ui.LocalWideNavigation
import ru.omnicio.app.ui.AnalystSideRail
import androidx.compose.foundation.layout.*
import androidx.compose.ui.unit.dp
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
    Appearance,
    Assistant,
    Strategies,
    Market,
    NotificationSettings,
}

private fun nextBackStack(current: AppScreen, destination: AppScreen, history: List<String>): ArrayList<String> {
    val roots = setOf(AppScreen.Home, AppScreen.Portfolio, AppScreen.Recommendations, AppScreen.Risk, AppScreen.Profile)
    return when {
        destination in roots -> arrayListOf()
        history.lastOrNull() == destination.name -> ArrayList(history.dropLast(1))
        else -> ArrayList(history + current.name)
    }
}

private sealed interface AuthUiState {
    data class Loading(val stage: String = "Проверяем сохранённый сеанс…") : AuthUiState
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
                "Не удалось завершить вход. Повторите попытку; если ошибка останется, обратитесь за помощью."
            "telegram_invalid_token" -> "Не удалось подтвердить данные Telegram."
            "telegram_invalid_response" -> "Telegram вернул некорректный ответ."
            "private_access_full" ->
                "Доступ к закрытой версии Analyst AI ограничен пятью аккаунтами. Все места уже заняты."
            null -> if (code == null) "Не получен код входа от Telegram." else null
            else -> "Не удалось завершить вход через Telegram."
        }
        return true
    }

    private fun launchTelegramLogin() {
        if (!BackendConfig.isConfigured) {
            pendingAuthError.value = BackendConfig.UNAVAILABLE_MESSAGE
            return
        }
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

    var authState by remember { mutableStateOf<AuthUiState>(AuthUiState.Loading()) }
    var initialSessionChecked by remember { mutableStateOf(false) }
    var screenName by rememberSaveable { mutableStateOf(AppScreen.Home.name) }
    var backStack by rememberSaveable { mutableStateOf(arrayListOf<String>()) }
    BackHandler(screenName != AppScreen.Home.name) {
        screenName = backStack.lastOrNull() ?: AppScreen.Home.name
        backStack = ArrayList(backStack.dropLast(1))
    }
    val screen = remember(screenName) {
        runCatching { AppScreen.valueOf(screenName) }.getOrDefault(AppScreen.Home)
    }
    var tApiConfigured by remember { mutableStateOf(false) }
    var brokerConnection by remember { mutableStateOf(BrokerConnectionState.Checking) }
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
            authState = AuthUiState.Loading("Подтверждаем вход через Telegram…")
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
                            backStack = arrayListOf()
                            screenName = AppScreen.Home.name
                            withContext(Dispatchers.IO) { sessionStore.clear() }
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
        brokerConnection = BrokerConnectionState.Checking
        val connection = restoreBrokerConnection(backend, session.accessToken, legacyTInvestStore)
        tApiConfigured = connection.first
        brokerConnection = connection.second
    }

    val livePortfolio = rememberLivePortfolio(
        signedIn?.accessToken,
        tApiConfigured,
        portfolioCurrency,
    )

    AnalystTheme {
        CompositionLocalProvider(LocalBrokerConnection provides brokerConnection, LocalWorkspaceBack provides {
            screenName = backStack.lastOrNull() ?: AppScreen.Home.name
            backStack = ArrayList(backStack.dropLast(1))
        }) {
        AnalystAppContent(
            authState = authState,
            authError = authError,
            onStartTelegramLogin = onStartTelegramLogin,
            screen = screen,
            portfolioState = when (brokerConnection) {
                BrokerConnectionState.Checking -> PortfolioUiState.Loading
                BrokerConnectionState.Unknown -> PortfolioUiState.Error("Не удалось проверить подключение. Откройте подключение в профиле и повторите проверку.")
                else -> livePortfolio.state
            },
            portfolioRefreshing = livePortfolio.refreshing,
            portfolioError = livePortfolio.error,
            portfolioLastSuccessMillis = livePortfolio.lastSuccessMillis,
            portfolioCurrency = portfolioCurrency,
            tApiConfigured = tApiConfigured,
            screenshotsBlocked = screenshotsBlocked,
            onScreenChange = { destination ->
                if (destination != screen) {
                    backStack = nextBackStack(screen, destination, backStack)
                    screenName = destination.name
                }
            },
            onCurrencyChange = { currency ->
                portfolioCurrencyName = currency.name
            },
            onTApiConfiguredChange = { configured ->
                tApiConfigured = configured
                brokerConnection = if (configured) BrokerConnectionState.Connected else BrokerConnectionState.Missing
            },
            onScreenshotsBlockedChange = { blocked ->
                screenshotsBlocked = blocked
                onScreenshotsBlockedChange(blocked)
            },
            onLogout = {
                backStack = arrayListOf()
                sessionStore.clear()
                screenName = AppScreen.Home.name
                tApiConfigured = false
                authState = AuthUiState.SignedOut()
            },
        )
        }
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
        is AuthUiState.Loading -> {
            TelegramLoginScreen(
                loading = true,
                loadingLabel = authState.stage,
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
    var currencyPicker by remember { mutableStateOf(false) }
    var portfolioDestination by remember { mutableStateOf<PortfolioDestination?>(null) }
    val navigateToTab: (AnalystTab) -> Unit = { tab ->
        onScreenChange(tab.toAppScreen())
    }
    val goBack = LocalWorkspaceBack.current
    val openPortfolio = { onScreenChange(AppScreen.Portfolio) }
    val openProfile = { onScreenChange(AppScreen.Profile) }

    val navigateWorkspace: (WorkspaceRoute) -> Unit = { route -> onScreenChange(AppScreen.valueOf(route.name)) }
    val holder = rememberSaveableStateHolder()
    val motion = LocalSpectrumMotionPreference.current.enabled && android.animation.ValueAnimator.areAnimatorsEnabled()
    CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab,
        LocalWorkspaceNavigator provides navigateWorkspace,
        LocalWorkspaceSession provides WorkspaceSession(session.accessToken, session.user.telegramId),
        LocalCurrencyChoice provides onCurrencyChange,
        LocalPortfolioDestination provides { target -> portfolioDestination = target; openPortfolio() }) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
        val wide = maxWidth >= 840.dp
        CompositionLocalProvider(LocalWideNavigation provides wide) {
        Row(Modifier.fillMaxSize()) {
        if (wide) AnalystSideRail(when (screen) {
            AppScreen.Home -> AnalystTab.Home; AppScreen.Portfolio, AppScreen.Market -> AnalystTab.Portfolio
            AppScreen.Recommendations -> AnalystTab.Actions; AppScreen.Risk -> AnalystTab.Risk
            else -> AnalystTab.Profile
        }, navigateToTab)
        Box(Modifier.weight(1f).fillMaxHeight()) {
        AnimatedContent(screen, transitionSpec = {
            workspaceTransition(initialState, targetState, motion)
        }, label = "workspace-navigation") { destination ->
        holder.SaveableStateProvider(destination.name) {
        when (destination) {
            AppScreen.Home -> {
                HomeScreen(
                    user = session.user,
                    state = portfolioState,
                    refreshing = portfolioRefreshing,
                    refreshError = portfolioError,
                    lastUpdatedMillis = portfolioLastSuccessMillis,
                    selectedCurrency = portfolioCurrency,
                    onCurrencyClick = {
                        currencyPicker = true
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
                    onOpenProfile = openProfile,
                    onConnect = { onScreenChange(AppScreen.TApi) },
                    onOpenPayments = { portfolioDestination = PortfolioDestination(section = 4); openPortfolio() },
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
                    onProfileClick = openProfile,
                    onConnect = { onScreenChange(AppScreen.TApi) },
                    destination = portfolioDestination,
                    onDestinationConsumed = { portfolioDestination = null },
                )
            }

            AppScreen.Recommendations -> {
                IdeasScreen(
                    accessToken = session.accessToken,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                    onOpenProfileSettings = {
                        onScreenChange(AppScreen.Strategies)
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
                    onOpenEducation = {
                        onScreenChange(AppScreen.Education)
                    },
                    onLogout = onLogout,
                )
            }

            AppScreen.Education -> {
                EducationScreen(
                    onBack = goBack,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.AnalysisSettings -> {
                AnalysisProfileSettingsScreen(
                    accessToken = session.accessToken,
                    onBack = goBack,
                    onPortfolioClick = openPortfolio,
                    onProfileClick = openProfile,
                )
            }

            AppScreen.NotificationSettings -> AnalysisProfileSettingsScreen(session.accessToken, goBack,
                openPortfolio, openProfile, initialSection = 1)
            AppScreen.Appearance -> AppearanceScreen(goBack)
            AppScreen.Assistant -> AssistantWorkspaceScreen(goBack, openPortfolio,
                { onScreenChange(AppScreen.Recommendations) }, { onScreenChange(AppScreen.Strategies) })
            AppScreen.Strategies -> StrategyWorkspaceScreen(session.user.telegramId, goBack,
                { onScreenChange(AppScreen.AnalysisSettings) })
            AppScreen.Market -> MarketWorkspaceScreen(portfolioState, goBack, openPortfolio)

            AppScreen.TApi -> {
                TApiScreen(
                    accessToken = session.accessToken,
                    tApiConfigured = tApiConfigured,
                    onBack = goBack,
                    onConnectionChanged = onTApiConfiguredChange,
                    onOpenPortfolio = openPortfolio,
                )
            }
        }
        }
        }
        }
        }
        }
        }
        if (currencyPicker) AlertDialog(onDismissRequest = { currencyPicker = false }, title = { Text("Валюта оценки") },
            text = { Column { PortfolioCurrency.entries.forEach { choice ->
                TextButton(onClick = { onCurrencyChange(choice); currencyPicker = false }) { Text(choice.name) }
            } } }, confirmButton = { TextButton(onClick = { currencyPicker = false }) { Text("Закрыть") } })
    }
}

private fun AnalystTab.toAppScreen(): AppScreen = when (this) {
    AnalystTab.Actions -> AppScreen.Recommendations
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


private suspend fun restoreBrokerConnection(backend: AnalystBackendClient, accessToken: String,
    legacyTInvestStore: TInvestTokenStore): Pair<Boolean, BrokerConnectionState> {
        val status = withContext(Dispatchers.IO) {
            backend.fetchTInvestStatus(accessToken)
        }

        var connected = (status as? BackendResult.Success)?.value ?: false
        if (status is BackendResult.Success && !connected) {
            val legacyToken = withContext(Dispatchers.IO) {
                legacyTInvestStore.load()
            }
            if (!legacyToken.isNullOrBlank()) {
                val migration = withContext(Dispatchers.IO) {
                    backend.saveTInvestToken(
                        accessToken = accessToken,
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
        return connected to if (connected) BrokerConnectionState.Connected else if (status is BackendResult.Failure) BrokerConnectionState.Unknown else BrokerConnectionState.Missing
}

private fun workspaceTransition(initialState: AppScreen, targetState: AppScreen, motion: Boolean): ContentTransform {
            val roots = setOf(AppScreen.Home, AppScreen.Portfolio, AppScreen.Recommendations, AppScreen.Risk, AppScreen.Profile)
            val duration = if (motion) 180 else 0
            return if (initialState in roots && targetState in roots) fadeIn(tween(duration)) togetherWith fadeOut(tween(duration))
            else {
                val direction = if (targetState in roots) -1 else 1
                (slideInHorizontally(tween(duration)) { it / 8 * direction } + fadeIn(tween(duration))) togetherWith
                    (slideOutHorizontally(tween(duration)) { -it / 8 * direction } + fadeOut(tween(duration)))
            }
}
