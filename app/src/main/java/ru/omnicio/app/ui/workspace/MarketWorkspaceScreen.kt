package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun MarketWorkspaceScreen(state: PortfolioUiState, onBack: () -> Unit, onPortfolio: () -> Unit) {
    var section by rememberSaveable { mutableIntStateOf(0) }
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }
    val openPortfolio = LocalPortfolioDestination.current
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val positions = snapshot?.accounts?.flatMap { it.positions }.orEmpty()
    val groups = positions.groupBy {
        marketGroupLabel(it, section)
    }.toList().sortedByDescending { it.second.size }
    WorkspaceDetailPage("Рынки и география", "Ваши вложения и подтверждённые сессии", onBack, SpectrumSymbol.Market,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (compact) item(key = "page-heading") {
                WorkspacePageHeading("Рынки и география", "Ваши вложения и подтверждённые сессии")
            }
            item { SpectrumCard(emphasized = true) {
                Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    SpectrumLiveFeatureIcon(SpectrumLiveFeature.WorldMarkets, Modifier.size(44.dp),
                        motionAllowed = LocalSpectrumMotionPreference.current.enabled)
                    Text("Ваши инструменты", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
                }
                Text("Распределение имеющихся позиций по данным брокера.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            } }
            item { SpectrumTabs(listOf("Отрасли", "Классы", "География", "Сессии"), section, { section = it }) }
            if (section == 2) item(key = "geography") { GeographyWorkspacePanel(snapshot?.totalValue?.currency ?: "RUB") }
            if (section == 3) item(key = "trading-calendar") { TradingCalendarPanel() }
            if (section < 2) groups.forEach { (title, rows) -> item(key = title) {
                MarketGroupCard(title, rows, expanded == title,
                    onToggle = { expanded = if (expanded == title) null else title },
                    onOpen = { openPortfolio(marketGroupDestination(rows.first(), section)) })
            } }
            if (section < 2 && groups.isEmpty()) item {
                MarketEmptyState(state, onPortfolio)
            }
            item { SpectrumCard {
                Text("Доступ к покупке", style = MaterialTheme.typography.titleMedium)
                Text("Определяется брокером для конкретного счёта и бумаги. Наличие бумаги в портфеле само по себе не подтверждает доступ к новой покупке.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("В портфеле отмечены как заблокированные: ${positions.count { it.blocked }}",
                    style = MaterialTheme.typography.bodyMedium)
            } }
        }
    }
}

@Composable
private fun MarketGroupCard(title: String, rows: List<PortfolioPosition>, expanded: Boolean,
    onToggle: () -> Unit, onOpen: () -> Unit) {
    SpectrumCard(onClick = onToggle) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text("Позиций в счетах: ${rows.size} · ${if (expanded) "свернуть" else "показать"}",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (expanded) {
            rows.take(5).forEach { Text(it.title, style = MaterialTheme.typography.bodyMedium) }
            if (rows.size > 5) Text("Ещё ${rows.size - 5} · полный список в портфеле")
            SpectrumSecondaryButton("Все позиции группы", onOpen, Modifier.fillMaxWidth())
        }
    }
}

private fun marketGroupDestination(position: PortfolioPosition, section: Int) = PortfolioDestination(
    sector = if (section == 0) position.sector?.takeIf(String::isNotBlank) ?: "__unknown__" else null,
    kind = if (section == 1) marketKind(position.instrumentType) else null,
)

@Composable
private fun MarketEmptyState(state: PortfolioUiState, onPortfolio: () -> Unit) {
                when (state) {
                    PortfolioUiState.Loading, PortfolioUiState.ApiConnected -> WorkspaceEmpty("Получаем позиции", "Данные ещё загружаются.", loading = true)
                    is PortfolioUiState.Error -> WorkspaceEmpty("Не удалось обновить", state.message, "Открыть портфель", onPortfolio)
                    PortfolioUiState.NotConnected -> WorkspaceEmpty("Подключите счёт", "После подключения здесь появится состав ваших вложений.", "Подключение", onPortfolio)
                    is PortfolioUiState.Ready -> WorkspaceEmpty("Позиций пока нет", "В полученных счетах нет позиций для группировки.")
                }
}

private fun marketKind(value: String): String = when (value) {
    "bond", "share", "etf" -> value
    "cash", "currency" -> "cash"
    else -> "other"
}


private fun marketGroupLabel(position: PortfolioPosition, section: Int): String =
    if (section == 0) position.sector?.takeIf(String::isNotBlank) ?: "Отрасль не указана"
    else when (position.instrumentType) {
        "bond" -> "Облигации"; "share" -> "Акции"; "etf" -> "Фонды"
        "cash", "currency" -> "Деньги и валюта"; else -> "Другие инструменты"
    }
