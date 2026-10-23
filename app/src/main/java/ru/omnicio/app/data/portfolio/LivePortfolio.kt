package ru.omnicio.app.data.portfolio

import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.workspace.OfflinePortfolioStore

/** Refresh data, never replace an already rendered portfolio with a loading screen. */
data class LivePortfolio(
    val state: PortfolioUiState,
    val refreshing: Boolean,
    val error: String?,
    val lastSuccessMillis: Long?,
    val refresh: () -> Unit = {},
    val cachedFromDisk: Boolean = false,
)

@Composable
fun rememberLivePortfolio(token: String?, connected: Boolean, currency: PortfolioCurrency,
    userId: String? = null, allowCachedOffline: Boolean = false, onSessionExpired: () -> Unit = {}): LivePortfolio {
    val context = LocalContext.current
    val offline = remember(context) { OfflinePortfolioStore(context) }
    val expired by rememberUpdatedState(onSessionExpired)
    var refreshRevision by remember(token) { mutableLongStateOf(0) }
    var fromDisk by remember(token, connected) { mutableStateOf(false) }
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var foreground by remember(lifecycle) {
        mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true)
    }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            foreground = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    // Disconnecting or changing identity clears values, errors AND their timestamps.
    var request by remember(token, connected) {
        mutableStateOf(RefreshSnapshot<PortfolioCurrency, PortfolioSnapshot>())
    }
    val client = remember { PortfolioDataClient() }
    LaunchedEffect(token, userId, currency, connected, allowCachedOffline) {
        if (token.isNullOrBlank() || userId.isNullOrBlank() || (!connected && !allowCachedOffline)) return@LaunchedEffect
        val restored = withContext(Dispatchers.IO) { offline.read(userId, currency) }
        if (restored != null && request.value == null) {
            request = request.copy(value = restored.snapshot, displayedQuery = restored.currency, receivedAtMillis = restored.receivedAtMillis)
            fromDisk = true
        }
    }
    LaunchedEffect(token, connected, currency, foreground, refreshRevision) {
        if (token.isNullOrBlank() || !connected || !foreground) return@LaunchedEffect
        val backoff = RefreshBackoff(15_000)
        while (isActive) {
            request = request.start(currency)
            val id = request.requestId
            val waitMillis: Long
            try {
                when (val result = withContext(Dispatchers.IO) { client.portfolioJson(token, currency) }) {
                    is BackendResult.Success -> {
                        val parsed = runCatching { client.parsePortfolio(result.value) }.getOrNull()
                        if (parsed == null) {
                            request = request.fail(id, "Источник вернул неполный портфель. Сохранённая оценка не заменена.")
                            waitMillis = backoff.failure()
                        } else {
                        val receivedAt = System.currentTimeMillis()
                        request = request.succeed(id, parsed, receivedAt)
                        fromDisk = false
                        if (!userId.isNullOrBlank()) withContext(Dispatchers.IO) { offline.save(userId, currency, result.value, receivedAt) }
                        waitMillis = backoff.success()
                        }
                    }
                    is BackendResult.Failure -> {
                        request = request.fail(id, result.message)
                        if (result.statusCode == 401 || result.statusCode == 403) { expired(); return@LaunchedEffect }
                        if (!result.retryable) return@LaunchedEffect
                        waitMillis = backoff.failure()
                    }
                }
            } finally {
                // An old effect must not turn off a newer request's loading state.
                request = request.cancel(id)
            }
            delay(waitMillis)
        }
    }
    val cached = request.value
    val failure = request.error
    val state = when {
        token.isNullOrBlank() || (!connected && !allowCachedOffline) -> PortfolioUiState.NotConnected
        cached != null -> PortfolioUiState.Ready(cached)
        failure != null -> PortfolioUiState.Error(failure)
        else -> PortfolioUiState.Loading
    }
    return LivePortfolio(state, request.loading && foreground, failure, request.receivedAtMillis,
        refresh = { refreshRevision++ }, cachedFromDisk = fromDisk)
}
