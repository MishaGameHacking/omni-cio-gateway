package ru.omnicio.app.data.portfolio

import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.*
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
    LaunchedEffect(token, connected, currency, foreground) {
        if (token.isNullOrBlank() || !connected || !foreground) return@LaunchedEffect
        val backoff = RefreshBackoff(15_000)
        while (isActive) {
            request = request.start(currency)
            val id = request.requestId
            val waitMillis: Long
            try {
                when (val result = withContext(Dispatchers.IO) { client.portfolio(token, currency) }) {
                    is BackendResult.Success -> {
                        request = request.succeed(id, result.value, System.currentTimeMillis())
                        waitMillis = backoff.success()
                    }
                    is BackendResult.Failure -> {
                        request = request.fail(id, result.message)
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
        token.isNullOrBlank() || !connected -> PortfolioUiState.NotConnected
        cached != null -> PortfolioUiState.Ready(cached)
        failure != null -> PortfolioUiState.Error(failure)
        else -> PortfolioUiState.Loading
    }
    return LivePortfolio(state, request.loading && foreground, failure, request.receivedAtMillis)
}
