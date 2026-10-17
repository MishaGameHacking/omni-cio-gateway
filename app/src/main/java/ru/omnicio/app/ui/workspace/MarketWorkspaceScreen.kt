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
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun MarketWorkspaceScreen(state: PortfolioUiState, onBack: () -> Unit, onPortfolio: () -> Unit) {
    var section by rememberSaveable { mutableIntStateOf(0) }
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val positions = snapshot?.accounts?.flatMap { it.positions }.orEmpty()
    val groups = positions.groupBy {
        if (section == 0) it.sector?.takeIf(String::isNotBlank) ?: "Отрасль не указана"
        else when (it.instrumentType) {
            "bond" -> "Облигации"; "share" -> "Акции"; "etf" -> "Фонды"
            "cash", "currency" -> "Деньги и валюта"; else -> "Другие инструменты"
        }
    }.toList().sortedByDescending { it.second.size }
    WorkspaceDetailPage("Обзор рынка", "Через призму вашего портфеля", onBack) { padding ->
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { SpectrumCard(emphasized = true) {
                SpectrumLiveFeatureIcon(SpectrumLiveFeature.WorldMarkets, Modifier.size(72.dp),
                    motionAllowed = LocalSpectrumMotionPreference.current.enabled)
                Text("Ваши инструменты", style = MaterialTheme.typography.headlineSmall)
                Text("Сейчас здесь состав полученного портфеля. Каталог доступных покупок ещё не подключён.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            } }
            item { SpectrumTabs(listOf("Отрасли", "Классы"), section, { section = it }) }
            groups.forEach { (title, rows) -> item(key = title) {
                WorkspaceLink(title, "Позиций в счетах: ${rows.size}", SpectrumSymbol.Market, onPortfolio)
            } }
            if (groups.isEmpty()) item { SpectrumCard { Text("Подключите счёт, чтобы увидеть состав портфеля.") } }
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
