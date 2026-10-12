package ru.omnicio.app.data.portfolio

import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.BackendResult

/** Refresh data, never replace an already rendered portfolio with a loading screen. */
data class LivePortfolio(
    val state: PortfolioUiState,
    val refreshing: Boolean,
    val error: String?,
    val lastSuccessMillis: Long?,
)

@Composable
fun rememberLivePortfolio(token: String?, connected: Boolean, currency: PortfolioCurrency): LivePortfolio {
    val context = LocalContext.current
    val lifecycle = (context as? ComponentActivity)?.lifecycle
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
    // A different identity must never see the previous identity's cached snapshot.
    var state by remember(token, connected) {
        mutableStateOf<PortfolioUiState>(if (connected) PortfolioUiState.Loading else PortfolioUiState.NotConnected)
    }
    var refreshing by remember(token) { mutableStateOf(false) }
    var error by remember(token) { mutableStateOf<String?>(null) }
    var successTime by remember(token) { mutableStateOf<Long?>(null) }
    val client = remember { PortfolioDataClient() }
    LaunchedEffect(token, connected, currency, foreground) {
        if (token == null || !connected || !foreground) {
            refreshing = false
            return@LaunchedEffect
        }
        var waitMillis = 15_000L
        while (isActive) {
            refreshing = true
            try {
                when (val result = withContext(Dispatchers.IO) { client.portfolio(token, currency) }) {
                    is BackendResult.Success -> {
                        state = PortfolioUiState.Ready(result.value)
                        successTime = System.currentTimeMillis()
                        error = null
                        waitMillis = 15_000L
                    }
                    is BackendResult.Failure -> {
                        error = result.message
                        if (state !is PortfolioUiState.Ready) state = PortfolioUiState.Error(result.message)
                        if (!result.retryable) return@LaunchedEffect
                        waitMillis = (waitMillis * 2).coerceAtMost(120_000L)
                    }
                }
            } finally {
                refreshing = false
            }
            delay(waitMillis)
        }
    }
    return LivePortfolio(state, refreshing, error, successTime)
}
