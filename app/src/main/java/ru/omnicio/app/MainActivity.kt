package ru.omnicio.app

import android.os.Bundle
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import ru.omnicio.app.ui.AppUiState
import ru.omnicio.app.ui.AssistantScreen
import ru.omnicio.app.ui.AuthScreen
import ru.omnicio.app.ui.OmnicioRoot
import ru.omnicio.app.ui.OverviewScreen
import ru.omnicio.app.ui.PortfolioScreen
import ru.omnicio.app.ui.theme.OmnicioTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        enableEdgeToEdge()
        setContent {
            OmnicioRoot()
        }
    }
}

// Android Studio entry points: render real UI without a ViewModel, network or financial fixtures.
@Preview(name = "Вход · светлая тема", showSystemUi = true, locale = "ru", widthDp = 390, heightDp = 844)
@Preview(name = "Вход · тёмная тема", showSystemUi = true, locale = "ru", widthDp = 390, heightDp = 844,
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
private fun SignInPreview() {
    OmnicioTheme {
        AuthScreen(AppUiState(), onStartSocial = {}, onReloadConfig = {})
    }
}

@Preview(name = "Обзор · данные не получены", showSystemUi = true, locale = "ru", widthDp = 390, heightDp = 844)
@Composable
private fun OverviewPreview() {
    OmnicioTheme {
        Surface {
            OverviewScreen(AppUiState(), onToggleAmountsHidden = {}, onSyncPortfolio = {}, onConnect = {})
        }
    }
}

@Preview(name = "Портфель · данные не получены", showSystemUi = true, locale = "ru", widthDp = 390, heightDp = 844)
@Composable
private fun PortfolioPreview() {
    OmnicioTheme {
        Surface { PortfolioScreen(AppUiState()) }
    }
}

@Preview(name = "Помощник · данные не получены", showSystemUi = true, locale = "ru", widthDp = 390, heightDp = 844)
@Composable
private fun AssistantPreview() {
    OmnicioTheme {
        Surface { AssistantScreen(AppUiState(), onMarkRead = {}, onLoadMore = {}) }
    }
}

