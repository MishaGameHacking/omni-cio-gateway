package ru.omnicio.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.R

@Composable
internal fun PortfolioScreen(state: AppUiState) {
    var search by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<String?>(null) }
    val portfolio = state.workspace?.portfolio
    val positions = portfolio?.positions.orEmpty().filter {
        it.name.contains(search, true) || it.ticker.contains(search, true) || it.uid.contains(search, true)
    }
    val detail = portfolio?.positions?.find { it.uid == selected }
    if (detail != null) {
        LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { TextButton(onClick = { selected = null }) { OmniIcon(R.drawable.ic_back); Text("Все позиции") } }
            item {
                OmniCard {
                    Text(detail.name.ifBlank { detail.ticker.ifBlank { "Инструмент" } }, style = MaterialTheme.typography.headlineMedium)
                    Text(detail.ticker, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(money(detail.value, state.amountsHidden), style = MaterialTheme.typography.headlineLarge)
                    MetricRow("Количество", if (state.amountsHidden) "••••" else detail.quantity?.toPlainString() ?: "Нет данных")
                    MetricRow("Текущая цена", if (detail.currency == null) "Нет данных" else money(detail.price, state.amountsHidden, detail.currency.uppercase()))
                    MetricRow("Доля портфеля", if (state.amountsHidden) "••••" else detail.share?.let { "$it %" } ?: "Нет данных")
                    MetricRow("Блокировка", if (detail.blocked) "Есть ограничение брокера" else "В снимке не отмечена")
                    Text("Идентификатор: ${detail.uid}", style = MaterialTheme.typography.bodySmall)
                    Text(timestampLabel(portfolio.capturedAt), style = MaterialTheme.typography.bodySmall)
                    Text(statusLabel(portfolio.freshness), style = MaterialTheme.typography.bodySmall)
                }
            }
            item { SourcesCard(portfolio.sources) }
        }
    } else LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Портфель", style = MaterialTheme.typography.headlineLarge) }
        item { OutlinedTextField(search, { search = it }, singleLine = true, label = { Text("Название, тикер или идентификатор") }, modifier = Modifier.fillMaxWidth()) }
        if (portfolio == null) item { EmptyState("Позиции не получены", "Подключите счёт или обновите данные с сервера.", R.drawable.ic_portfolio) }
        else {
            item {
                Text(statusLabel(portfolio.freshness) + " · " + timestampLabel(portfolio.capturedAt),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (positions.isEmpty()) item { Text(if (search.isBlank()) "Сервер вернул пустой список позиций." else "Совпадений нет.") }
            items(positions, key = { it.uid }) { position ->
                Card(Modifier.fillMaxWidth().clickable { selected = position.uid },
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Surface(shape = MaterialTheme.shapes.small, color = MaterialTheme.colorScheme.secondaryContainer) {
                            Box(Modifier.size(44.dp), contentAlignment = Alignment.Center) { OmniIcon(R.drawable.ic_portfolio) }
                        }
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(position.name.ifBlank { position.ticker.ifBlank { "Инструмент" } }, style = MaterialTheme.typography.titleMedium)
                            Text(position.ticker, style = MaterialTheme.typography.bodySmall)
                            Text(money(position.value, state.amountsHidden), style = MaterialTheme.typography.titleMedium)
                            Text(if (state.amountsHidden) "Количество скрыто" else "Количество: ${position.quantity?.toPlainString() ?: "нет данных"}", style = MaterialTheme.typography.bodySmall)
                            if (position.value == null) Text("Цена или оценка недоступна", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                            if (position.blocked) Text("Ограничение брокера", style = MaterialTheme.typography.bodySmall)
                        }
                        OmniIcon(R.drawable.ic_chevron)
                    }
                }
            }
        }
    }
}
