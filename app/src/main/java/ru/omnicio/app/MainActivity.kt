package ru.omnicio.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.portfolio.PortfolioUiState

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { AnalystAiApp() }
    }
}

@Composable
private fun AnalystAiApp() {
    MaterialTheme {
        PortfolioScreen(
            state = PortfolioUiState.NotConnected,
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun AnalystAiAppPreview() {
    AnalystAiApp()
}
