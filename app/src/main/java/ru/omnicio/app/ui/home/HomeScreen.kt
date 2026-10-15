package ru.omnicio.app.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.spectrum.*
import java.time.Instant

@Composable
fun HomeScreen(
    state: PortfolioUiState, accessToken: String,
    selectedCurrency: PortfolioCurrency, onCurrencyClick: () -> Unit,
    onProfileClick: () -> Unit, onAnalysisSettings: () -> Unit,
    refreshing: Boolean = false, refreshError: String? = null, lastUpdatedMillis: Long? = null,
    modifier: Modifier = Modifier,
) {
    val navigate = LocalAnalystTabNavigator.current
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(Modifier.fillMaxSize(), containerColor = Color.Transparent, contentColor = MaterialTheme.colorScheme.onBackground,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Home, { navigate(AnalystTab.Portfolio) }, onProfileClick) }) { insets ->
            LazyColumn(Modifier.fillMaxSize().padding(insets), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(18.dp)) {
                item(key = "home-header") {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        SpectrumIconButton(SpectrumSymbol.Profile, "Открыть профиль", onProfileClick)
                        Column(Modifier.weight(1f).padding(start = 6.dp)) {
                            Text("Главная", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text("Analyst AI", color = LocalSpectrumPalette.current.cyan, style = MaterialTheme.typography.bodySmall)
                        }
                        SpectrumIconButton(SpectrumSymbol.Bell, "Сообщения аналитика", { navigate(AnalystTab.Chat) })
                    }
                }
                item(key = "home-balance") {
                    BalanceHero(state, snapshot, accessToken, selectedCurrency, onCurrencyClick, onProfileClick,
                        refreshing, refreshError, lastUpdatedMillis)
                }
                item(key = "home-shortcuts") { HomeShortcuts() }
                item(key = "home-assistant") {
                    SpectrumCard(emphasized = true) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpectrumRobot(Modifier.size(92.dp))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                                Text("Привет!", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                                Text("Я ваш ИИ-аналитик", style = MaterialTheme.typography.titleMedium)
                            }
                        }
                        Text("Разбирайтесь в портфеле, проверяйте риски и изучайте идеи на основе ваших данных.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        SpectrumAction("Показать рекомендации", { navigate(AnalystTab.Ideas) })
                    }
                }
                item(key = "home-goals") {
                    SpectrumCard(onClick = onAnalysisSettings) {
                        SpectrumHeader("Ваши цели", "Горизонт, допустимый риск и резерв", SpectrumSymbol.Target)
                        Text("Настроить инвестиционный профиль →", color = LocalSpectrumPalette.current.cyan,
                            style = MaterialTheme.typography.labelLarge)
                    }
                }
                item(key = "home-learning") {
                    SpectrumCard(onClick = { navigate(AnalystTab.Education) }) {
                        SpectrumHeader("Инвестиции понятным языком", "Короткие уроки и официальные источники", SpectrumSymbol.Education)
                    }
                }
                item(key = "home-disclosure") {
                    Text("Analyst AI не совершает сделки. Доступность модельных обзоров зависит от состояния сервера и источников.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun BalanceHero(state: PortfolioUiState, snapshot: PortfolioSnapshot?, token: String,
    currency: PortfolioCurrency, onCurrency: () -> Unit, onProfile: () -> Unit,
    refreshing: Boolean, error: String?, lastUpdated: Long?) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Text("Общий баланс", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            SpectrumBadge(snapshot?.totalValue?.currency ?: currency.name)
        }
        if (snapshot == null) {
            HomePortfolioState(state, onProfile)
        } else {
            Text(snapshot.totalValue.moneyText(), Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onCurrency),
                fontSize = 34.sp, lineHeight = 41.sp, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Доходность", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
            }
            Text(if (refreshing && snapshot.totalValue.currency != currency.name) "Получаем оценку в ${currency.name}…" else "Нажмите на баланс: ₽ → $ → €",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            DashboardHistory(token, snapshot)
            val observed = snapshot.asOf ?: lastUpdated?.let { Instant.ofEpochMilli(it).toString() }
            Text(error ?: "Данные на ${dateText(observed)}", color = if (error == null) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall)
            snapshot.warnings.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall) }
        }
    }
}

@Composable
private fun HomePortfolioState(state: PortfolioUiState, onProfile: () -> Unit) {
    when (state) {
        PortfolioUiState.Loading, PortfolioUiState.ApiConnected -> {
            CircularProgressIndicator(Modifier.size(28.dp), strokeWidth = 2.dp)
            Text("Получаем ваш портфель…")
        }
        is PortfolioUiState.Error -> {
            Text(state.message, color = MaterialTheme.colorScheme.error)
            Text("Повторная проверка выполняется автоматически.", style = MaterialTheme.typography.bodySmall)
        }
        else -> {
            Text("Ваши инвестиции — в одном месте", style = MaterialTheme.typography.headlineSmall)
            Text("Подключите брокерский счёт с доступом только для чтения.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            SpectrumAction("Подключить портфель", onProfile)
        }
    }
}

private data class HomeAction(val text: String, val symbol: SpectrumSymbol, val destination: AnalystTab)
private val HomeActions = listOf(
    HomeAction("Анализ\nпортфеля", SpectrumSymbol.Portfolio, AnalystTab.Portfolio),
    HomeAction("Идеи\nдля вас", SpectrumSymbol.Ideas, AnalystTab.Ideas),
    HomeAction("Риски", SpectrumSymbol.Risk, AnalystTab.Risks),
    HomeAction("События", SpectrumSymbol.Bell, AnalystTab.Pulse),
)

@Composable
private fun HomeShortcuts() {
    val navigate = LocalAnalystTabNavigator.current
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val columns = if (maxWidth < 300.dp || fontScale >= 1.4f) 2 else 4
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            HomeActions.chunked(columns).forEach { row ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    row.forEach { action ->
                        Column(Modifier.weight(1f).heightIn(min = 86.dp).clickable(role = Role.Button) { navigate(action.destination) }.padding(vertical = 3.dp),
                            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(5.dp)) {
                            SpectrumIcon(action.symbol, Modifier.size(54.dp), selected = true)
                            Text(action.text, textAlign = TextAlign.Center, style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
            }
        }
    }
}
