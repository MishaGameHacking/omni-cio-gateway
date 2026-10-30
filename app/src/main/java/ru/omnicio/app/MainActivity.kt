package ru.omnicio.app

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.runtime.*
import kotlinx.coroutines.CancellationException
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
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
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
import ru.omnicio.app.data.diagnostics.ClientDiagnostics
import ru.omnicio.app.data.diagnostics.DiagnosticStage
import ru.omnicio.app.data.backend.AnalystBackendClient
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.backend.SessionTransitions
import ru.omnicio.app.data.backend.OwnerSessionAccess
import ru.omnicio.app.data.backend.restoreOwnerSessionAccess
import ru.omnicio.app.data.market.optionalText
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.portfolio.rememberLivePortfolio
import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.terminal.TerminalWorkspace
import ru.omnicio.app.ui.portfolio.TerminalDashboard
import androidx.compose.foundation.layout.*
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.analystDestination
import ru.omnicio.app.ui.sectionBackStack
import ru.omnicio.app.ui.LocalAnalystSectionNavigator
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.analysis.AnalysisProfileSettingsScreen
import ru.omnicio.app.ui.analysis.IdeasScreen
import ru.omnicio.app.ui.analysis.InsightFeedScreen
import ru.omnicio.app.ui.analysis.PulseScreen
import ru.omnicio.app.ui.auth.OwnerAccessScreen
import ru.omnicio.app.ui.auth.OwnerDeviceUnlock
import ru.omnicio.app.ui.auth.rememberOwnerAccessLifecycle
import ru.omnicio.app.ui.auth.OwnerAccessGate
import ru.omnicio.app.data.backend.AnalystSession
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
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

private fun savedScreenName(saved: JSONObject): String = saved.optString("screen")
    .takeIf { name -> AppScreen.entries.any { it.name == name } } ?: AppScreen.Home.name

private fun savedNavigationNames(saved: JSONObject, key: String): ArrayList<String> {
    val values = saved.optJSONArray(key) ?: return arrayListOf()
    return ArrayList((0 until values.length()).map { values.optString(it) }
        .filter { name -> AppScreen.entries.any { it.name == name } })
}

private fun endOwnerSession(context: android.content.Context, workspaceStore: EncryptedWorkspaceStore,
    sessionStore: AuthSessionStore, userId: String?, clearSnapshots: Boolean = false) {
    val appContext = context.applicationContext
    SessionTransitions.submit {
        userId?.let { workspaceStore.deactivateUser(it) }
        sessionStore.clear()
        if (clearSnapshots && userId != null) {
            OfflinePortfolioStore(appContext).clearSnapshots(userId)
            workspaceStore.remove(userId, "navigation")
            workspaceStore.remove(userId, "navigation_detail")
        }
    }
    ru.omnicio.app.data.notifications.WorkspaceNotificationService.cancel(context)
}

private sealed interface AuthUiState {
    data class Loading(val stage: String = "Проверяем сохранённый сеанс…") : AuthUiState
    data class SignedOut(val errorMessage: String? = null, val validatedAccessToken: String? = null) : AuthUiState
    data object Locked : AuthUiState
    data class Migration(val accessToken: String) : AuthUiState
    data class SignedIn(
        val accessToken: String,
        val user: AnalystUser,
    ) : AuthUiState
}

private class OwnerAuthentication(
    private val current: MutableState<AuthUiState>,
    private val backend: AnalystBackendClient,
    private val sessionStore: AuthSessionStore,
    private val context: android.content.Context,
    private val scope: CoroutineScope,
    val gate: OwnerAccessGate,
) {
    val state: AuthUiState get() = current.value

    suspend fun checkSavedAccess() {
        val ticket = gate.begin() ?: return
        val token = withContext(Dispatchers.IO) { sessionStore.loadAccessToken() }
        if (gate.complete(ticket)) current.value = if (token == null) AuthUiState.SignedOut() else AuthUiState.Locked
    }

    fun unlock() = restore(passwordRequested = false)

    // Keep a valid pre-password session available for enrollment, without
    // granting portfolio access when the owner chose password authentication.
    fun usePassword() = restore(passwordRequested = true)

    private fun restore(passwordRequested: Boolean) {
        val ticket = gate.begin() ?: return
        current.value = AuthUiState.Loading()
        scope.launch {
            val restored = restoreAnalystSession(backend, sessionStore, context, passwordRequested)
            if (gate.complete(ticket)) current.value = restored
        }
    }

    fun sessionReady(session: AnalystSession, requestTicket: Long) {
        if (!gate.complete(requestTicket)) return
        val persistenceTicket = gate.begin() ?: return
        current.value = AuthUiState.Loading("Сохраняем личный доступ…")
        scope.launch {
            val saved = persistOwnerSession(sessionStore, context, session)
            if (gate.complete(persistenceTicket)) current.value = saved
        }
    }

    fun signedOut(message: String? = null) {
        gate.begin() // Invalidate any older in-flight response before closing access.
        current.value = AuthUiState.SignedOut(message)
    }
}

@Composable
private fun rememberOwnerAuthentication(backend: AnalystBackendClient, sessionStore: AuthSessionStore): OwnerAuthentication {
    val context = LocalContext.current.applicationContext
    val state = remember { mutableStateOf<AuthUiState>(AuthUiState.Loading()) }
    val scope = rememberCoroutineScope()
    val lifecycle = rememberOwnerAccessLifecycle { state.value = AuthUiState.Locked }
    val authentication = remember(backend, sessionStore, context, scope, lifecycle.gate) {
        OwnerAuthentication(state, backend, sessionStore, context, scope, lifecycle.gate)
    }
    var initialAccessChecked by remember { mutableStateOf(false) }
    LaunchedEffect(lifecycle.foreground) {
        if (lifecycle.foreground && !initialAccessChecked) {
            initialAccessChecked = true
            authentication.checkSavedAccess()
        }
    }
    return authentication
}

class MainActivity : ComponentActivity() {
    private lateinit var settingsStore: AppSettingsStore
    private val pendingNotificationId = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        settingsStore = AppSettingsStore(this)
        val initialScreenshotsBlocked = settingsStore.screenshotsBlocked()
        applyScreenshotPolicy(true)
        captureNotification(intent)
        setContent {
            MandatoryUpdateHost(blockedContent = { state, actions ->
                RequiredUpdateScreen(state, actions, extraContent = { OfflineSnapshotAccess(state) })
            }) {
                AnalystAiApp(
                    notificationId = pendingNotificationId.value,
                    onNotificationConsumed = { pendingNotificationId.value = null },
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
        captureNotification(intent)
    }

    private fun captureNotification(incoming: Intent?) {
        incoming?.getStringExtra("workspace_event_id")?.takeIf { it.isNotBlank() && it.length <= 160 }
            ?.let { pendingNotificationId.value = it }
        incoming?.removeExtra("workspace_event_id")
    }

    private fun applyScreenshotPolicy(blocked: Boolean) {
        if (blocked) window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }
}

@Composable
private fun AnalystAiApp(
    notificationId: String?,
    onNotificationConsumed: () -> Unit,
    initialScreenshotsBlocked: Boolean,
    onScreenshotsBlockedChange: (Boolean) -> Unit,
) {
    val context = LocalContext.current
    val sessionStore = remember(context) { AuthSessionStore(context) }
    val legacyTInvestStore = remember(context) { TInvestTokenStore(context) }
    val backend = remember { AnalystBackendClient() }

    val authentication = rememberOwnerAuthentication(backend, sessionStore)
    val authState = authentication.state
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

    val signedIn = authState as? AuthUiState.SignedIn
    val appForeground = workspaceForeground()
    LaunchedEffect(signedIn?.accessToken, appForeground) {
        if (!appForeground) return@LaunchedEffect
        val token = signedIn?.accessToken
        if (token == null) ClientDiagnostics.stage(DiagnosticStage.LOGIN)
        else {
            ClientDiagnostics.stage(DiagnosticStage.WORKSPACE)
            withContext(Dispatchers.IO) { ClientDiagnostics.uploadPending(context.applicationContext, token) }
        }
    }
    val workspaceStore = remember(context) { EncryptedWorkspaceStore(context) }
    var knownUser by rememberSaveable { mutableStateOf<String?>(null) }
    var navigationRestored by remember(signedIn?.user?.telegramId) { mutableStateOf(false) }
    var recentNames by rememberSaveable { mutableStateOf(arrayListOf<String>()) }
    val reauthenticate: () -> Unit = {
        if (authState is AuthUiState.SignedIn) {
            authentication.signedOut("Войдите с паролем Analyst AI. После входа вы вернётесь к своему разделу.")
            tApiConfigured = false; brokerConnection = BrokerConnectionState.Checking
            endOwnerSession(context, workspaceStore, sessionStore, signedIn?.user?.telegramId)
        }
    }
    LaunchedEffect(signedIn?.user?.telegramId) {
        val id = signedIn?.user?.telegramId ?: return@LaunchedEffect
        val saved = withContext(Dispatchers.IO) { workspaceStore.readJson(id, "navigation") }
        if (saved?.optInt("schema_version", 0) != 3) {
            // Start the redesigned flow once; account data and editor drafts stay in their own records.
            screenName = AppScreen.Home.name
            backStack = arrayListOf()
            recentNames = arrayListOf()
        } else if (knownUser != id) {
            screenName = savedScreenName(saved)
            backStack = savedNavigationNames(saved, "back")
            recentNames = savedNavigationNames(saved, "recent")
        }
        knownUser = id; navigationRestored = true
    }
    LaunchedEffect(signedIn?.user?.telegramId, screenName, backStack, recentNames, navigationRestored) {
        val id = signedIn?.user?.telegramId ?: return@LaunchedEffect
        if (navigationRestored) withContext(Dispatchers.IO) {
            workspaceStore.saveJson(id, "navigation", JSONObject().put("schema_version", 3).put("screen", screenName).put("back", JSONArray(backStack)).put("recent", JSONArray(recentNames)))
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
        enabled = screen !in setOf(AppScreen.Recommendations, AppScreen.Profile),
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
    val selectSection: (String) -> Unit = { id ->
        val destination = AppScreen.entries.firstOrNull { it.name == id }
        val parentStack = sectionBackStack(id)
        if (destination != null && parentStack != null && destination != screen) {
            navigate(destination)
            backStack = ArrayList(parentStack)
        }
    }
    CompositionLocalProvider(LocalAnalystSectionNavigator provides selectSection,
        LocalWorkspaceSession provides WorkspaceSession(signedIn?.accessToken.orEmpty(), signedIn?.user?.telegramId.orEmpty()),
        LocalWorkspaceBackProgress provides backProgress, LocalReauthenticate provides reauthenticate,
        LocalPortfolioSnapshot provides (visiblePortfolio as? PortfolioUiState.Ready)?.snapshot,
        LocalWorkspaceHistory provides WorkspaceHistory(recentNames.map { RecentDestination(it, screenTitle(it)) }, { name ->
            AppScreen.entries.firstOrNull { it.name == name }?.let(navigate)
        })) {
        AnalystTheme {
            ServerScreenshotPolicy(signedIn != null) { blocked ->
                screenshotsBlocked = blocked
                onScreenshotsBlockedChange(blocked)
            }
            CompositionLocalProvider(LocalBrokerConnection provides brokerConnection, LocalWorkspaceBack provides goBack) {
                AnalystAppContent(
                    authState = authState, onSessionReady = authentication::sessionReady,
                    onAccessStart = authentication.gate::begin, onUnlock = authentication::unlock,
                    onUsePassword = authentication::usePassword,
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
                        endOwnerSession(context, workspaceStore, sessionStore, signedIn?.user?.telegramId, clearSnapshots = true)
                        backStack = arrayListOf(); recentNames = arrayListOf(); knownUser = null
                        screenName = AppScreen.Home.name; tApiConfigured = false; authentication.signedOut()
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
    onSessionReady: (AnalystSession, Long) -> Unit,
    onAccessStart: () -> Long?,
    onUnlock: () -> Unit,
    onUsePassword: () -> Unit,
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
    val userState = rememberUserWorkspaceState()
    when (val current = authState) {
        is AuthUiState.Loading -> OwnerAccessScreen(loading = true,
            loadingLabel = current.stage, onSessionReady = onSessionReady, onAccessStart = onAccessStart)
        is AuthUiState.SignedOut -> OwnerAccessScreen(errorMessage = current.errorMessage,
            loginAccessToken = current.validatedAccessToken,
            onSessionReady = onSessionReady, onAccessStart = onAccessStart)
        is AuthUiState.Locked -> OwnerDeviceUnlock(onUnlock, onUsePassword)
        is AuthUiState.Migration -> OwnerAccessScreen(migrationToken = current.accessToken,
            onSessionReady = onSessionReady, onAccessStart = onAccessStart)

        is AuthUiState.SignedIn -> {
            userState.Content(current.user.telegramId) { SignedInAppContent(
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
                onLogout = { userState.forget(); onLogout() },
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
    var portfolioDestination by rememberSaveable(session.user.telegramId, stateSaver = PortfolioDestinationSaver) {
        mutableStateOf<PortfolioDestination?>(null)
    }
    var historyDate by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyStart by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyEnd by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var historyResolution by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var libraryId by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var reportId by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var chatJson by rememberSaveable(session.user.telegramId) { mutableStateOf(ChatContext().json().toString()) }
    var chatTitle by rememberSaveable(session.user.telegramId) { mutableStateOf("Мой портфель") }
    var explanationJson by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    val pendingExplanationState = remember(explanationJson) { pendingExplanation(explanationJson) }
    val json = remember(chatJson) { JSONObject(chatJson) }
    val chatContext = ChatContext(json.text("mode", "portfolio"), json.optString("instrument_uid").takeIf { it.isNotBlank() && it != "null" }, chatTitle,
        json.optString("account_id").takeIf { it.isNotBlank() && it != "null" }, json.optString("start").takeIf { it.isNotBlank() && it != "null" }, json.optString("end").takeIf { it.isNotBlank() && it != "null" },
        json.optString("event_id").takeIf { it.isNotBlank() && it != "null" },
        json.optJSONObject("explanation")?.optString("kind"), json.optJSONObject("explanation")?.optString("id"))
    val reauthenticate = LocalReauthenticate.current
    val workspace = rememberWorkspaceRuntime(WorkspaceSession(session.accessToken, session.user.telegramId), tApiConfigured, portfolioCurrency, reauthenticate)
    val liveSync = rememberWorkspaceLiveSync(
        WorkspaceSession(session.accessToken, session.user.telegramId),
        onChanged = workspace.invalidate,
        onBrokerChanged = { configured -> onTApiConfiguredChange(configured); onPortfolioRefresh() },
        onExpired = reauthenticate,
    )
    val refresh: () -> Unit = { onPortfolioRefresh(); workspace.refresh() }
    val selectSection = LocalAnalystSectionNavigator.current
    val navigateToTab: (AnalystTab) -> Unit = { selectSection(it.toAppScreen().name) }
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
    var lastTargetJson by rememberSaveable(session.user.telegramId) { mutableStateOf<String?>(null) }
    var restored by rememberSaveable(session.user.telegramId) { mutableStateOf(false) }
    LaunchedEffect(session.user.telegramId) {
        if (restored) return@LaunchedEffect
        val saved = withContext(Dispatchers.IO) { storage.readJson(session.user.telegramId, "navigation_detail") }
        if (saved != null) {
            saved.optJSONObject("portfolio")?.let { target ->
                portfolioDestination = PortfolioDestination(target.optInt("section", 1), target.optString("account_id").takeIf { it.isNotBlank() }, target.optString("query", ""),
                    sector = target.optionalText("sector"), kind = target.optionalText("kind"),
                    operationId = target.text("operation_id", "").takeIf(String::isNotBlank),
                    operationDate = target.text("operation_date", "").takeIf(String::isNotBlank))
                historyDate = target.optString("date").takeIf { it.isNotBlank() && it != "null" }
                historyStart = target.text("start", "").takeIf(String::isNotBlank)
                historyEnd = target.text("end", "").takeIf(String::isNotBlank)
                historyResolution = target.text("resolution", "").takeIf(String::isNotBlank)
                lastTargetJson = target.toString()
            }
            saved.optJSONObject("chat")?.let { chatJson = it.toString() }
            chatTitle = saved.text("chat_title", "Мой портфель")
        }
        restored = true
    }
    LaunchedEffect(lastTargetJson, chatJson, chatTitle, restored) {
        if (restored) withContext(Dispatchers.IO) { storage.saveJson(session.user.telegramId, "navigation_detail", JSONObject()
            .put("portfolio", lastTargetJson?.let(::JSONObject) ?: JSONObject.NULL).put("chat", JSONObject(chatJson)).put("chat_title", chatTitle)) }
    }
    val toPortfolio: (PortfolioDestination) -> Unit = { target ->
        portfolioDestination = target
        lastTargetJson = JSONObject().put("section", target.section).put("account_id", target.accountId ?: "").put("query", target.query).put("date", historyDate ?: "")
            .put("sector", target.sector ?: JSONObject.NULL).put("kind", target.kind ?: JSONObject.NULL)
            .put("start", historyStart ?: "").put("end", historyEnd ?: "").put("resolution", historyResolution ?: "")
            .put("operation_id", target.operationId ?: "").put("operation_date", target.operationDate ?: "").toString()
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
        LocalWorkspaceRefreshKey provides (workspace.revision + liveSync.revision), LocalWorkspaceSnapshot provides workspace.data,
        LocalWorkspaceLiveSync provides liveSync,
        LocalPendingExplanation provides pendingExplanationState,
        LocalAskExplanation provides { target -> explanationJson = target.json().toString(); onScreenChange(AppScreen.Assistant) },
        LocalApplyExplanation provides { id ->
            if (pendingExplanationState?.id == id) { chatJson = pendingExplanationState.context.json().toString(); chatTitle = pendingExplanationState.context.title; explanationJson = null }
        },
        LocalDismissExplanation provides { id -> if (pendingExplanationState?.id == id) explanationJson = null },
        LocalChatContext provides chatContext, LocalAskAnalyst provides { target ->
            chatJson = target.json().toString(); chatTitle = target.title; onScreenChange(AppScreen.Assistant)
        }, LocalEvidenceNavigator provides evidenceNavigator,
        LocalOpenAnalysisReport provides { id -> reportId = id; onScreenChange(AppScreen.Reports) }) {
        val remotePresentation = LocalWorkspacePreferences.current
        LaunchedEffect(liveSync.revision) { remotePresentation.refreshRemote() }
        SessionExpiryObserver(session.accessToken, reauthenticate)
        NotificationDeliveryRuntime()
        TerminalWorkspace(visible = screen != AppScreen.Home,
            route = WorkspaceRoute.entries.firstOrNull { it.name == screen.name },
            title = screenTitle(screen.name), close = { onScreenChange(AppScreen.Home) },
            dashboard = {
                TerminalDashboard(portfolioState, portfolioCurrency, portfolioRefreshing || workspace.busy,
                    portfolioError ?: workspace.error, refresh, openProfile, { onScreenChange(AppScreen.TApi) })
            }) {
                AnimatedContent(screen, transitionSpec = { workspaceTransition(initialState, targetState, motion) }, label = "workspace-navigation") { destination ->
                    holder.SaveableStateProvider(destination.name) {
                        when (destination) {
                            AppScreen.Home -> Unit
                            AppScreen.Portfolio -> PortfolioScreen(state = portfolioState, accessToken = session.accessToken,
                                refreshing = portfolioRefreshing, refreshError = portfolioError, lastUpdatedMillis = portfolioLastSuccessMillis,
                                selectedCurrency = portfolioCurrency, onProfileClick = openProfile, onConnect = { onScreenChange(AppScreen.TApi) },
                                destination = portfolioDestination, initialHistoryDate = historyDate, initialHistoryStart = historyStart,
                                initialHistoryEnd = historyEnd, initialHistoryResolution = historyResolution, onDestinationConsumed = { portfolioDestination = null })
                            AppScreen.Recommendations -> PrimaryWorkspaceShell(AnalystTab.Actions, openPortfolio, openProfile) { AutonomousDecisionsScreen(goBack) }
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

private fun screenTitle(name: String): String = analystDestination(name)?.title ?: "Analyst AI"

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

private suspend fun persistOwnerSession(
    sessionStore: AuthSessionStore,
    context: android.content.Context,
    session: AnalystSession,
): AuthUiState = SessionTransitions.run {
    val saved = withContext(Dispatchers.IO) {
        runCatching {
            sessionStore.save(session)
            EncryptedWorkspaceStore(context).activateUser(session.user.telegramId)
        }.isSuccess
    }
    if (saved) AuthUiState.SignedIn(session.accessToken, session.user)
    else AuthUiState.SignedOut("Не удалось сохранить вход на устройстве. Повторите попытку.")
}

private suspend fun restoreAnalystSession(
    backend: AnalystBackendClient,
    sessionStore: AuthSessionStore,
    context: android.content.Context,
    passwordRequested: Boolean,
): AuthUiState = SessionTransitions.run {
    withContext(Dispatchers.IO) {
        when (val access = restoreOwnerSessionAccess(sessionStore.loadAccessToken(), passwordRequested,
            backend::fetchMe, backend::ownerAccessStatus, sessionStore::clear)) {
            is OwnerSessionAccess.Password -> AuthUiState.SignedOut(access.errorMessage, access.validatedAccessToken)
            is OwnerSessionAccess.Migration -> AuthUiState.Migration(access.accessToken)
            is OwnerSessionAccess.Restored -> {
                EncryptedWorkspaceStore(context).activateUser(access.user.telegramId)
                AuthUiState.SignedIn(access.accessToken, access.user)
            }
        }
    }
}

@Composable
private fun ServerScreenshotPolicy(signedIn: Boolean, apply: (Boolean) -> Unit) {
    val presentation = LocalWorkspacePreferences.current
    val window = androidx.activity.compose.LocalActivity.current?.window
    val applied = remember(signedIn) { arrayOf<Boolean?>(null) }
    val blocked = screenCaptureBlocked(signedIn, presentation.serverConfirmed, presentation.value.screenshotsBlocked)
    SideEffect {
        if (blocked) window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        else window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        if (signedIn && presentation.serverConfirmed && applied[0] != presentation.value.screenshotsBlocked) {
            apply(presentation.value.screenshotsBlocked)
            applied[0] = presentation.value.screenshotsBlocked
        }
    }
}



