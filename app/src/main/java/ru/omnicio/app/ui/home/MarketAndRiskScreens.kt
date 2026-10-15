package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.research.PortfolioResearchPanel
import ru.omnicio.app.ui.spectrum.*

private data class MarketPosition(val accountId: String, val position: PortfolioPosition)

@Composable
fun MarketScreen(state: PortfolioUiState, onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    val navigate = LocalAnalystTabNavigator.current
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    var query by rememberSaveable { mutableStateOf("") }
    var selected by remember { mutableStateOf<MarketPosition?>(null) }
    val entries = remember(snapshot, query) {
        snapshot?.accounts.orEmpty().flatMap { account ->
            account.positions.filter { it.instrumentType != "cash" && (query.isBlank() || it.title.contains(query.trim(), true) || it.ticker.orEmpty().contains(query.trim(), true)) }
                .map { MarketPosition(account.id, it) }
        }
    }
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(Modifier.fillMaxSize(), containerColor = Color.Transparent, contentColor = MaterialTheme.colorScheme.onBackground,
            bottomBar = { AnalystBottomBar(AnalystTab.Market, { navigate(AnalystTab.Portfolio) }, onProfileClick) }) { insets ->
            LazyColumn(Modifier.fillMaxSize().padding(insets), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item(key = "market-header") { SpectrumHeader("Рынок", "Идеи, инструменты и события", SpectrumSymbol.Market) }
                item(key = "market-hero") {
                    SpectrumCard(emphasized = true) {
                        Row(Modifier.fillMaxWidth()) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                Text("Мир инвестиций", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                                Text("От ваших активов к обоснованным решениям.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            SpectrumGlobe(Modifier.size(118.dp))
                        }
                        SpectrumAction("Персональные рекомендации", { navigate(AnalystTab.Ideas) })
                    }
                }
                item(key = "market-events") {
                    SpectrumCard(onClick = { navigate(AnalystTab.Pulse) }) {
                        SpectrumHeader("События и обзоры", "Изменения портфеля и сообщения системы", SpectrumSymbol.Bell)
                    }
                }
                item(key = "market-search") {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        SpectrumSectionTitle("Инструменты вашего портфеля")
                        OutlinedTextField(value = query, onValueChange = { query = it.take(120) },
                            modifier = Modifier.fillMaxWidth(), singleLine = true, label = { Text("Название или тикер в портфеле") })
                    }
                }
                if (entries.isEmpty()) item(key = "market-empty") {
                    val explanation = when {
                        state is PortfolioUiState.Error -> state.message
                        snapshot == null -> "Данные инструментов появятся после подключения и загрузки портфеля."
                        query.isNotBlank() -> "В вашем портфеле совпадений не найдено. Это не поиск по всему рынку."
                        else -> "В загруженном портфеле нет неденежных инструментов. Идеи доступны отдельно, когда сервер завершит проверку."
                    }
                    SpectrumMessage("Пока нет инструментов для показа", explanation, SpectrumSymbol.Market)
                }
                items(entries, key = { "${it.accountId}:${it.position.id}" }) { item ->
                    SpectrumCard { PositionLine(item.position) { selected = item } }
                }
                item(key = "market-source") {
                    Notice("Здесь показаны ваши позиции, а не весь биржевой каталог. Цены и сведения — из подключённого брокерского счёта.")
                }
            }
        }
    }
    val selection = selected
    if (selection != null) {
        val current = snapshot?.accounts?.firstOrNull { it.id == selection.accountId }?.positions?.singleOrNull { it.id == selection.position.id }
        if (current != null) PositionDetails(current) { selected = null }
        else AlertDialog(onDismissRequest = { selected = null }, title = { Text("Позиция изменилась") },
            text = { Text("Инструмент больше не найден однозначно в текущем портфеле. Старые значения не показываем.") },
            confirmButton = { TextButton(onClick = { selected = null }) { Text("Закрыть") } })
    }
}

@Composable
fun RisksScreen(state: PortfolioUiState, accessToken: String, onProfileClick: () -> Unit,
    onAnalysisSettings: () -> Unit, modifier: Modifier = Modifier) {
    val navigate = LocalAnalystTabNavigator.current
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(Modifier.fillMaxSize(), containerColor = Color.Transparent, contentColor = MaterialTheme.colorScheme.onBackground,
            bottomBar = { AnalystBottomBar(AnalystTab.Risks, { navigate(AnalystTab.Portfolio) }, onProfileClick) }) { insets ->
            LazyColumn(Modifier.fillMaxSize().padding(insets), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item(key = "risk-header") { SpectrumHeader("Риски", "Проверяйте основания каждого вывода", SpectrumSymbol.Risk) }
                item(key = "risk-summary") { RiskOverview(snapshot) }
                item(key = "risk-profile") {
                    SpectrumCard(onClick = onAnalysisSettings) {
                        SpectrumHeader("Ваш риск-профиль", "Настроить горизонт, резерв и ограничения", SpectrumSymbol.Target)
                    }
                }
                item(key = "risk-research") { PortfolioResearchPanel(accessToken) }
                item(key = "risk-alerts") { SpectrumAction("Проверки и предупреждения", { navigate(AnalystTab.Pulse) }) }
                item(key = "risk-disclosure") { Notice("Отсутствие предупреждений или числовой оценки не подтверждает безопасность портфеля. Analyst AI не совершает сделки.") }
            }
        }
    }
}

@Composable
private fun RiskOverview(snapshot: PortfolioSnapshot?) {
    val positions = snapshot?.accounts.orEmpty().flatMap { it.positions }
    val cashOnly = positions.isNotEmpty() && positions.all { it.instrumentType == "cash" }
    SpectrumCard(emphasized = true) {
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(if (cashOnly) "Денежный портфель" else "Риск портфеля", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                SpectrumBadge("Оценка пока недоступна", accent = LocalSpectrumPalette.current.amber)
            }
            SpectrumIcon(SpectrumSymbol.Risk, Modifier.size(82.dp), selected = true)
        }
        Text(if (cashOnly) "На счёте пока только деньги. Для проверки отдельных инструментов нет позиций. Сводная оценка риска не рассчитана."
            else "Единой оценки риска пока нет. Ниже — доступные сценарии, источники и ограничения проверки.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (snapshot != null) {
            DataRow("Счета", snapshot.accounts.size.toString())
            DataRow("Неденежные позиции", positions.count { it.instrumentType != "cash" }.toString())
            DataRow("Данные на", dateText(snapshot.asOf))
        }
    }
}
