package ru.omnicio.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.tooling.preview.Preview
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.portfolio.PortfolioUiState
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.profile.TApiScreen

private enum class AppScreen {
    Portfolio,
    Profile,
    TApi,
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AnalystAiApp() }
    }
}

@Composable
private fun AnalystAiApp() {
    val context = LocalContext.current
    val tokenStore = remember(context) { TInvestTokenStore(context) }

    var screenName by rememberSaveable { mutableStateOf(AppScreen.Portfolio.name) }
    val screen = remember(screenName) {
        runCatching { AppScreen.valueOf(screenName) }.getOrDefault(AppScreen.Portfolio)
    }
    var tApiConfigured by remember {
        mutableStateOf(tokenStore.hasToken())
    }

    MaterialTheme {
        when (screen) {
            AppScreen.Portfolio -> {
                PortfolioScreen(
                    state = if (tApiConfigured) {
                        PortfolioUiState.Loading
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
                    tApiConfigured = tApiConfigured,
                    onPortfolioClick = {
                        screenName = AppScreen.Portfolio.name
                    },
                    onOpenTApi = {
                        screenName = AppScreen.TApi.name
                    },
                )
            }

            AppScreen.TApi -> {
                TApiScreen(
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
