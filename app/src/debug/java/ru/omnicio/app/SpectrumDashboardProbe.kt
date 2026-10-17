package ru.omnicio.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import ru.omnicio.app.ui.workspace.*
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.home.HomeScreen
import ru.omnicio.app.ui.portfolio.PortfolioScreen

/** Debug source set only: exercise real presenters, never a separate HTML mockup. */
@Composable
internal fun SpectrumDashboardProbe(screen: String) {
    require(screen in setOf("home", "portfolio", "appearance", "strategy", "assistant", "market", "ux100"))
    var destination by rememberSaveable(screen) { mutableStateOf(screen) }
    val state = remember {
        val amount = MoneyAmount(ApiDecimal(4000, 0), "RUB")
        val allocation = listOf(PortfolioAllocation("Денежные средства", ApiDecimal(100, 0)))
        val cash = PortfolioPosition(
            id = "synthetic-cash", title = "Рубль", ticker = "RUB", quantity = ApiDecimal(4000, 0),
            currentValue = amount, expectedYieldPercent = null, instrumentType = "cash",
        )
        PortfolioUiState.Ready(PortfolioSnapshot(
            totalValue = amount, expectedYieldAmount = null, expectedYieldPercent = null,
            accounts = listOf(PortfolioAccount("synthetic-account", "Тестовый счёт", amount, null, listOf(cash), allocations = allocation)),
            allocations = allocation, asOf = "2026-10-15T06:00:00Z",
        ))
    }
    // Keep the fixture disclosure visible under the same edge-to-edge window
    // as MainActivity. statusBarsPadding consumes the top inset for children.
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Surface(color = MaterialTheme.colorScheme.surface, contentColor = MaterialTheme.colorScheme.onSurface) {
            Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", Modifier.fillMaxWidth().padding(4.dp),
                style = MaterialTheme.typography.labelSmall, textAlign = TextAlign.Center)
        }
        Box(Modifier.weight(1f).semantics { testTagsAsResourceId = true }.testTag("workspace-probe")) {
            CompositionLocalProvider(LocalWorkspaceNavigator provides { route ->
                destination = when (route) {
                    WorkspaceRoute.Appearance -> "appearance"
                    WorkspaceRoute.Strategies -> "strategy"
                    WorkspaceRoute.Assistant -> "assistant"
                    WorkspaceRoute.Market -> "market"
                    else -> "home"
                }
            }) {
            when (destination) {
            "ux100" -> WorkspaceVisualProbe { destination = "home" }
            "appearance" -> AppearanceScreen { destination = "home" }
            "strategy" -> StrategyWorkspaceScreen("synthetic-ui-test", { destination = "home" }, { destination = "portfolio" })
            "assistant" -> AssistantWorkspaceScreen({ destination = "home" }, { destination = "portfolio" },
                { destination = "home" }, { destination = "strategy" })
            "market" -> MarketWorkspaceScreen(state, { destination = "home" }, { destination = "portfolio" })
            "home" -> {
                HomeScreen(
                    user = AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                    state = state, selectedCurrency = PortfolioCurrency.RUB,
                    refreshing = false, refreshError = null, lastUpdatedMillis = null,
                    onCurrencyClick = {}, onOpenPortfolio = {}, onOpenRecommendations = {},
                    onOpenRisk = {}, onOpenMessages = {}, onOpenEducation = {}, onOpenProfile = {},
                )
            }
            else -> {
                PortfolioScreen(state = state, onProfileClick = {}, accessToken = "")
            }
            }
            }
        }
    }
}

