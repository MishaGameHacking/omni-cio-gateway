package ru.omnicio.app

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.runtime.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.json.JSONArray
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.OfflinePortfolioStore
import ru.omnicio.app.ui.spectrum.*
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
    Discovery, Library, Devices, ActivityHistory, Goals, NewFeatures, AnalysisTimeline, Reports,
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
    private val pendingNotificationId = mutableStateOf<String?>(null)
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
        captureNotification(intent)

        setContent {
            MandatoryUpdateHost(blockedContent = { state, actions -> RequiredUpdateScreen(state, actions, extraContent = { OfflineSnapshotAccess(state) }) }) {
                AnalystAiApp(
                    notificationId = pendingNotificationId.value,
                    onNotificationConsumed = { pendingNotificationId.value = null },
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
        captureNotification(intent)
    }

    private fun captureNotification(incoming: Intent?) {
        incoming?.getStringExtra("workspace_event_id")?.takeIf { it.isNotBlank() && it.length <= 160 }?.let { pendingNotificationId.value = it }
        incoming?.removeExtra("workspace_event_id")
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
    notificationId: String?,
    onNotificationConsumed: () -> Unit,
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
    var backProgress by remember { mutableFloatStateOf(0f) }
    val goBack: () -> Unit = {
        screenName = backStack.lastOrNull() ?: AppScreen.Home.name
        backStack = ArrayList(backStack.dropLast(1))
    }
    PredictiveBackHandler(authState is AuthUiState.SignedIn && screenName != AppScreen.Home.name) { events ->
        try { events.collect { backProgress = it.progress }; goBack() }
        catch (_: CancellationException) { /* A cancelled gesture keeps the exact destination. */ }
        finally { backProgress = 0f }
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
                        runCatching { sessionStore.save(result.value); EncryptedWorkspaceStore(context).activateUser(result.value.user.telegramId) }.isSuccess
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
                        withContext(Dispatchers.IO) { EncryptedWorkspaceStore(context).activateUser(result.value.telegramId) }
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
    val scope = rememberCoroutineScope()
    val workspaceStore = remember(context) { EncryptedWorkspaceStore(context) }
    var knownUser by rememberSaveable { mutableStateOf<String?>(null) }
    var navigationRestored by remember(signedIn?.user?.telegramId) { mutableStateOf(false) }
    var recentNames by rememberSaveable { mutableStateOf(arrayListOf<String>()) }
    val reauthenticate: () -> Unit = {
        if (authState is AuthUiState.SignedIn) {
            authState = AuthUiState.SignedOut("Подтвердите вход через Telegram. После входа в тот же аккаунт вы вернётесь к своему разделу.")
            tApiConfigured = false; brokerConnection = BrokerConnectionState.Checking
            scope.launch(Dispatchers.IO) { signedIn?.user?.telegramId?.let { workspaceStore.deactivateUser(it) }; sessionStore.clear() }
            ru.omnicio.app.data.notifications.WorkspaceNotificationService.cancel(context)
        }
    }
    LaunchedEffect(signedIn?.user?.telegramId) {
        val id = signedIn?.user?.telegramId ?: return@LaunchedEffect
        if (knownUser != id) {
            val saved = withContext(Dispatchers.IO) { workspaceStore.readJson(id, "navigation") }
            screenName = saved?.optString("screen")?.takeIf { name -> AppScreen.entries.any { it.name == name } } ?: AppScreen.Home.name
            backStack = ArrayList(saved?.optJSONArray("back")?.let { a -> (0 until a.length()).map { a.optString(it) }.filter { name -> AppScreen.entries.any { it.name == name } } }.orEmpty())
            recentNames = ArrayList(saved?.optJSONArray("recent")?.let { a -> (0 until a.length()).map { a.optString(it) }.filter { name -> AppScreen.entries.any { it.name == name } } }.orEmpty())
        }
        knownUser = id; navigationRestored = true
    }
    LaunchedEffect(signedIn?.user?.telegramId, screenName, backStack, recentNames, navigationRestored) {
        val id = signedIn?.user?.telegramId ?: return@LaunchedEffect
        if (navigationRestored) withContext(Dispatchers.IO) {
            workspaceStore.saveJson(id, "navigation", JSONObject().put("screen", screenName).put("back", JSONArray(backStack)).put("recent", JSONArray(recentNames)))
        }
    }
    LaunchedEffect(signedIn?.accessToken) {
        val session = signedIn ?: return@LaunchedEffect
        brokerConnection = BrokerConnectionState.Checking
        val connection = restoreBrokerConnection(backend, session.accessToken, legacyTInvestStore)
        tApiConfigured = connection.first
        brokerConnection = connection.second
    }

    val livePortfolio = rememberLivePortfolio(
        signedIn?.accessToken, tApiConfigured, portfolioCurrency, userId = signedIn?.user?.telegramId,
        allowCachedOffline = brokerConnection == BrokerConnectionState.Unknown || brokerConnection == BrokerConnectionState.Checking,
        onSessionExpired = reauthenticate,
    )
    val visiblePortfolio = if (livePortfolio.state is PortfolioUiState.Ready) livePortfolio.state else when (brokerConnection) {
        BrokerConnectionState.Checking -> PortfolioUiState.Loading
        BrokerConnectionState.Unknown -> PortfolioUiState.Error("Подключение пока не подтверждено. Если снимок уже сохранён, он будет показан с датой получения.")
        else -> livePortfolio.state
    }
    val navigate: (AppScreen) -> Unit = { destination ->
        if (destination != screen) {
            backStack = nextBackStack(screen, destination, backStack)
            recentNames = ArrayList((listOf(screen.name) + recentNames.filter { it != screen.name && it != destination.name }).take(8))
            screenName = destination.name
        }
    }
    CompositionLocalProvider(LocalWorkspaceBackProgress provides backProgress, LocalReauthenticate provides reauthenticate,
        LocalPortfolioSnapshot provides (visiblePortfolio as? PortfolioUiState.Ready)?.snapshot,
        LocalWorkspaceHistory provides WorkspaceHistory(recentNames.map { RecentDestination(it, screenTitle(it)) }, { name ->
            AppScreen.entries.firstOrNull { it.name == name }?.let(navigate)
        })) {
        AnalystTheme {
            CompositionLocalProvider(LocalBrokerConnection provides brokerConnection, LocalWorkspaceBack provides goBack) {
                AnalystAppContent(
                    authState = authState, authError = authError, onStartTelegramLogin = onStartTelegramLogin,
                    notificationId = notificationId, onNotificationConsumed = onNotificationConsumed,
                    screen = screen, portfolioState = visiblePortfolio, portfolioRefreshing = livePortfolio.refreshing,
                    onPortfolioRefresh = livePortfolio.refresh, portfolioError = livePortfolio.error,
                    portfolioLastSuccessMillis = livePortfolio.lastSuccessMillis, portfolioCurrency = portfolioCurrency,
                    tApiConfigured = tApiConfigured, screenshotsBlocked = screenshotsBlocked, onScreenChange = navigate,
                    onCurrencyChange = { portfolioCurrencyName = it.name },
                    onTApiConfiguredChange = { configured ->
                        tApiConfigured = configured
                        brokerConnection = if (configured) BrokerConnectionState.Connected else BrokerConnectionState.Missing
                    },
                    onScreenshotsBlockedChange = { blocked -> screenshotsBlocked = blocked; onScreenshotsBlockedChange(blocked) },
                    onLogout = {
                        val userId = signedIn?.user?.telegramId
                        scope.launch(Dispatchers.IO) {
                            if (userId != null) workspaceStore.deactivateUser(userId)
                            sessionStore.clear()
                            if (userId != null) { OfflinePortfolioStore(context).clearSnapshots(userId); workspaceStore.remove(userId, "navigation") }
                        }
                        ru.omnicio.app.data.notifications.WorkspaceNotificationService.cancel(context)
                        backStack = arrayListOf(); recentNames = arrayListOf(); knownUser = null
                        screenName = AppScreen.Home.name; tApiConfigured = false; authState = AuthUiState.SignedOut()
                    },
                )
            }
        }
    }
}

@Composable
private fun AnalystAppContent(
    notificationId: String?,
    onNotificationConsumed: () -> Unit,
    authState: AuthUiState,
    authError: String?,
    onStartTelegramLogin: () -> Unit,
    screen: AppScreen,
    portfolioState: PortfolioUiState,
    portfolioRefreshing: Boolean,
    onPortfolioRefresh: () -> Unit,
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
            key(current.user.telegramId) { SignedInAppContent(
                notificationId = notificationId, onNotificationConsumed = onNotificationConsumed,
                session = current,
                screen = screen,
                portfolioState = portfolioState,
                portfolioRefreshing = portfolioRefreshing,
                onPortfolioRefresh = onPortfolioRefresh,
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
            ) }
        }
    }
}

@Composable
private fun SignedInAppContent(
    notificationId: String?,
    onNotificationConsumed: () -> Unit,
    session: AuthUiState.SignedIn,
    screen: AppScreen,
    portfolioState: PortfolioUiState,
    portfolioRefreshing: Boolean,
    onPortfolioRefresh: () -> Unit,
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
    var portfolioDestination by remember { mutableStateOf<PortfolioDestination?>(null) }
    var historyDate by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyStart by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyEnd by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyResolution by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var libraryId by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var reportId by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var chatJson by rememberSaveable(session.user.telegramId) { mutableStateOf(ChatContext().json().toString()) }
    var chatTitle by rememberSaveable(session.user.telegramId) { mutableStateOf("Мой портфель") }
    val json = remember(chatJson) { JSONObject(chatJson) }
    val chatContext = ChatContext(json.text("mode", "portfolio"), json.optString("instrument_uid").takeIf { it.isNotBlank() && it != "null" }, chatTitle,
        json.optString("account_id").takeIf { it.isNotBlank() && it != "null" }, json.optString("start").takeIf { it.isNotBlank() && it != "null" }, json.optString("end").takeIf { it.isNotBlank() && it != "null" },
        json.optString("event_id").takeIf { it.isNotBlank() && it != "null" })
    val reauthenticate = LocalReauthenticate.current
    val workspace = rememberWorkspaceRuntime(WorkspaceSession(session.accessToken, session.user.telegramId), tApiConfigured, portfolioCurrency, reauthenticate)
    val refresh: () -> Unit = { onPortfolioRefresh(); workspace.refresh() }
    val navigateToTab: (AnalystTab) -> Unit = { onScreenChange(it.toAppScreen()) }
    val goBack = LocalWorkspaceBack.current
    val openPortfolio = { onScreenChange(AppScreen.Portfolio) }
    val openProfile = { onScreenChange(AppScreen.Profile) }
    val navigateWorkspace: (WorkspaceRoute) -> Unit = { route ->
        if (route == WorkspaceRoute.Reports) reportId = null
        onScreenChange(AppScreen.valueOf(route.name))
    }
    val holder = rememberSaveableStateHolder()
    val motion = LocalSpectrumMotionPreference.current.enabled && android.animation.ValueAnimator.areAnimatorsEnabled()
    val appContext = LocalContext.current
    val storage = remember(appContext) { EncryptedWorkspaceStore(appContext) }
    var lastTarget by remember { mutableStateOf<JSONObject?>(null) }
    var restored by remember { mutableStateOf(false) }
    LaunchedEffect(session.user.telegramId) {
        val saved = withContext(Dispatchers.IO) { storage.readJson(session.user.telegramId, "navigation_detail") }
        if (saved != null) {
            saved.optJSONObject("portfolio")?.let { target ->
                portfolioDestination = PortfolioDestination(target.optInt("section", 1), target.optString("account_id").takeIf { it.isNotBlank() }, target.optString("query", ""),
                    operationId = target.text("operation_id", "").takeIf(String::isNotBlank),
                    operationDate = target.text("operation_date", "").takeIf(String::isNotBlank))
                historyDate = target.optString("date").takeIf { it.isNotBlank() && it != "null" }
                historyStart = target.text("start", "").takeIf(String::isNotBlank)
                historyEnd = target.text("end", "").takeIf(String::isNotBlank)
                historyResolution = target.text("resolution", "").takeIf(String::isNotBlank)
                lastTarget = target
            }
            saved.optJSONObject("chat")?.let { chatJson = it.toString() }
            chatTitle = saved.text("chat_title", "Мой портфель")
        }
        restored = true
    }
    LaunchedEffect(lastTarget, chatJson, chatTitle, restored) {
        if (restored) withContext(Dispatchers.IO) { storage.saveJson(session.user.telegramId, "navigation_detail", JSONObject()
            .put("portfolio", lastTarget ?: JSONObject.NULL).put("chat", JSONObject(chatJson)).put("chat_title", chatTitle)) }
    }
    val toPortfolio: (PortfolioDestination) -> Unit = { target ->
        portfolioDestination = target
        lastTarget = JSONObject().put("section", target.section).put("account_id", target.accountId ?: "").put("query", target.query).put("date", historyDate ?: "")
            .put("start", historyStart ?: "").put("end", historyEnd ?: "").put("resolution", historyResolution ?: "")
            .put("operation_id", target.operationId ?: "").put("operation_date", target.operationDate ?: "")
        openPortfolio()
    }
    val evidenceNavigator: (EvidenceTarget) -> Unit = { target ->
        when (target.section) {
            "capital" -> onScreenChange(AppScreen.Home)
            "risk" -> onScreenChange(AppScreen.Risk)
            "research" -> { libraryId = target.id; onScreenChange(AppScreen.Library) }
            "history" -> {
                historyDate = target.date; historyStart = target.start; historyEnd = target.end; historyResolution = target.resolution
                toPortfolio(PortfolioDestination(section = 3, accountId = target.accountId))
            }
            "operation", "operations" -> toPortfolio(PortfolioDestination(section = 1, accountId = target.accountId,
                operationId = target.id.takeIf(String::isNotBlank), operationDate = target.date))
            else -> toPortfolio(PortfolioDestination(section = 1, accountId = target.accountId, query = target.id))
        }
    }
    CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab,
        LocalWorkspaceNavigator provides navigateWorkspace, LocalWorkspaceSession provides WorkspaceSession(session.accessToken, session.user.telegramId),
        LocalCurrencyChoice provides onCurrencyChange, LocalPortfolioDestination provides toPortfolio,
        LocalPortfolioRefresh provides refresh, LocalWorkspaceRefresh provides workspace.refresh,
        LocalWorkspaceInvalidate provides workspace.invalidate,
        LocalWorkspaceRefreshKey provides workspace.revision, LocalWorkspaceSnapshot provides workspace.data,
        LocalChatContext provides chatContext, LocalAskAnalyst provides { target ->
            chatJson = target.json().toString(); chatTitle = target.title; onScreenChange(AppScreen.Assistant)
        }, LocalEvidenceNavigator provides evidenceNavigator,
        LocalOpenAnalysisReport provides { id -> reportId = id; onScreenChange(AppScreen.Reports) }) {
        SessionExpiryObserver(session.accessToken, reauthenticate)
        NotificationDeliveryRuntime()
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val wide = maxWidth >= 840.dp
            CompositionLocalProvider(LocalWideNavigation provides wide) {
                Row(Modifier.fillMaxSize()) {
                    if (wide) AnalystSideRail(when (screen) {
                        AppScreen.Home -> AnalystTab.Home; AppScreen.Portfolio, AppScreen.Market, AppScreen.Discovery -> AnalystTab.Portfolio
                        AppScreen.Recommendations -> AnalystTab.Actions; AppScreen.Risk -> AnalystTab.Risk
                        else -> AnalystTab.Profile
                    }, navigateToTab)
                    Box(Modifier.weight(1f).fillMaxHeight()) {
                        AnimatedContent(screen, transitionSpec = { workspaceTransition(initialState, targetState, motion) }, label = "workspace-navigation") { destination ->
                            holder.SaveableStateProvider(destination.name) {
                                when (destination) {
                                    AppScreen.Home -> HomeScreen(user = session.user, state = portfolioState, refreshing = portfolioRefreshing || workspace.busy,
                                        refreshError = portfolioError ?: workspace.error, lastUpdatedMillis = portfolioLastSuccessMillis, selectedCurrency = portfolioCurrency,
                                        onCurrencyClick = { onCurrencyChange(portfolioCurrency.next()) }, onOpenPortfolio = openPortfolio,
                                        onOpenRecommendations = { onScreenChange(AppScreen.Recommendations) }, onOpenRisk = { onScreenChange(AppScreen.Risk) },
                                        onOpenMessages = { onScreenChange(AppScreen.Messages) }, onOpenProfile = openProfile,
                                        onConnect = { onScreenChange(AppScreen.TApi) }, onOpenPayments = { toPortfolio(PortfolioDestination(section = 4)) })
                                    AppScreen.Portfolio -> PortfolioScreen(state = portfolioState, accessToken = session.accessToken,
                                        refreshing = portfolioRefreshing, refreshError = portfolioError, lastUpdatedMillis = portfolioLastSuccessMillis,
                                        selectedCurrency = portfolioCurrency, onProfileClick = openProfile, onConnect = { onScreenChange(AppScreen.TApi) },
                                        destination = portfolioDestination, initialHistoryDate = historyDate, initialHistoryStart = historyStart,
                                        initialHistoryEnd = historyEnd, initialHistoryResolution = historyResolution, onDestinationConsumed = { portfolioDestination = null })
                                    AppScreen.Recommendations -> PrimaryWorkspaceShell(AnalystTab.Actions, openPortfolio, openProfile) { PlansWorkspaceScreen(goBack) }
                                    AppScreen.Risk -> PrimaryWorkspaceShell(AnalystTab.Risk, openPortfolio, openProfile) { RiskWorkspaceScreen(goBack) }
                                    AppScreen.Messages -> NotificationEventsScreen(goBack)
                                    AppScreen.Reports -> InsightFeedScreen(session.accessToken, openPortfolio, openProfile, initialCardId = reportId)
                                    AppScreen.Profile -> ProfileScreen(user = session.user, tApiConfigured = tApiConfigured, screenshotsBlocked = screenshotsBlocked,
                                        onScreenshotsBlockedChange = onScreenshotsBlockedChange, onPortfolioClick = openPortfolio,
                                        onOpenTApi = { onScreenChange(AppScreen.TApi) }, onOpenEducation = { onScreenChange(AppScreen.Education) }, onLogout = onLogout)
                                    AppScreen.Education -> EducationScreen(goBack, openPortfolio, openProfile)
                                    AppScreen.AnalysisSettings -> AnalysisProfileSettingsScreen(session.accessToken, goBack, openPortfolio, openProfile)
                                    AppScreen.NotificationSettings -> NotificationSettingsScreen(goBack)
                                    AppScreen.Appearance -> AppearanceScreen(goBack)
                                    AppScreen.Assistant -> AssistantWorkspaceScreen(goBack, openPortfolio, { onScreenChange(AppScreen.Recommendations) }, { onScreenChange(AppScreen.Strategies) })
                                    AppScreen.Strategies -> LiveStrategyScreen(session.user.telegramId, goBack)
                                    AppScreen.Market -> MarketWorkspaceScreen(portfolioState, goBack, openPortfolio)
                                    AppScreen.Discovery -> DiscoveryWorkspaceScreen(portfolioState, goBack)
                                    AppScreen.Library -> ResearchLibraryScreen(portfolioState, goBack, libraryId)
                                    AppScreen.Devices -> DevicesWorkspaceScreen(goBack)
                                    AppScreen.ActivityHistory -> RecentWorkspaceScreen(goBack)
                                    AppScreen.Goals -> GoalsWorkspaceScreen(goBack)
                                    AppScreen.NewFeatures -> NewFeaturesWorkspaceScreen(goBack)
                                    AppScreen.AnalysisTimeline -> AnalysisTimelineScreen(goBack)
                                    AppScreen.TApi -> TApiScreen(accessToken = session.accessToken, tApiConfigured = tApiConfigured,
                                        onBack = goBack, onConnectionChanged = onTApiConfiguredChange, onOpenPortfolio = openPortfolio)
                                }
                            }
                        }
                    }
                }
            }
        }
        notificationId?.let { id -> NotificationEventOverlay(id, onNotificationConsumed) }
    }
}

@Composable
private fun PrimaryWorkspaceShell(selected: AnalystTab, portfolio: () -> Unit, profile: () -> Unit, content: @Composable () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Box(Modifier.weight(1f)) { content() }
        ru.omnicio.app.ui.AnalystBottomBar(selected, portfolio, profile)
    }
}

private fun screenTitle(name: String): String = when (name) {
    "Home" -> "Капитал"; "Portfolio" -> "Портфель"; "Recommendations" -> "Действия"; "Risk" -> "Риски"; "Profile" -> "Профиль"
    "Messages" -> "События"; "Reports" -> "Выводы аналитика"; "Assistant" -> "Ассистент"; "Strategies" -> "Стратегия"; "Market" -> "Рынок"
    "Appearance" -> "Оформление"; "NotificationSettings" -> "Уведомления"; "Discovery" -> "Поиск"; "Library" -> "Исследования"
    "Devices" -> "Устройства"; "ActivityHistory" -> "Недавно открыто"; "Goals" -> "Цели"; "NewFeatures" -> "Что нового"
    "AnalysisTimeline" -> "Работа аналитика"; "TApi" -> "Подключение T-API"; "Education" -> "Обучение"; else -> "Настройки анализа"
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
