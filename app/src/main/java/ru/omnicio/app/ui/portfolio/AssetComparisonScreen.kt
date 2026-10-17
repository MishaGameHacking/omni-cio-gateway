package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

@Composable
internal fun AssetComparisonDialog(rows: List<PortfolioRow>, observedAt: String?, close: () -> Unit) {
    val entries = rows.distinctBy(::portfolioRowKey).take(3)
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        SpectrumBackground(Modifier.fillMaxSize()) {
            Scaffold(containerColor = androidx.compose.ui.graphics.Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
                topBar = { WorkspaceHeader("Сравнение", "Одни поля · одна дата наблюдения", close) }) { padding ->
                LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
                    verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                    item { SpectrumCard {
                        Text("Источник: T‑Invest · ${dateText(observedAt)}", style = MaterialTheme.typography.bodySmall)
                        Text(entries.joinToString(" · ") { it.position.ticker ?: it.position.title }, style = MaterialTheme.typography.titleMedium)
                        val currencies = entries.map { it.position.currentPrice?.currency }.distinct()
                        val classes = entries.map { it.position.instrumentType }.distinct()
                        if (currencies.size != 1 || currencies.firstOrNull() == null || classes.size != 1)
                            Text("Классы или единицы цены различаются. Общий рейтинг и общая ценовая шкала не применяются.")
                        else Text("Цены представлены в одной валюте; сравнивается стоимость единицы инструмента, не доходность за период.")
                        if (!LocalWorkspacePreferences.current.value.hideHomeBalance) SaveResearchButton(comparisonArchive(entries), "Сравнение ${entries.joinToString(" / ") { it.position.ticker ?: it.position.title }}",
                            source = "T‑Invest · текущие позиции", observedAt = observedAt)
                    } }
                    if (entries.size < 2) item { Text("Для сравнения нужны две актуальные позиции. Состав счёта изменился.") }
                    if (entries.size >= 2) item { DetailFold("Одинаковый период по реальным котировкам") { CommonPeriodComparison(entries) } }
                    item { ComparisonMetric("Счёт", entries) { it.account.name } }
                    item { ComparisonMetric("Класс", entries) { instrumentDetailLabels(it.position.instrumentType, it.position.currentNkd != null).type } }
                    item { ComparisonMetric("Цена за единицу", entries) { it.position.currentPrice.moneyText() } }
                    item { ComparisonMetric("Стоимость позиции", entries) { it.position.currentValue.moneyText() } }
                    item { ComparisonMetric("Количество", entries) { PrivateValue(it.position.quantity.quantityText()) } }
                    item { ComparisonMetric("Средняя цена", entries) { it.position.averagePrice.moneyText() } }
                    item { ComparisonMetric("Текущий результат брокера", entries) { it.position.expectedYieldAmount.moneyText(true) } }
                    item { ComparisonMetric("Результат за день", entries) { it.position.dailyYieldAmount.moneyText(true) } }
                    item { ComparisonMetric("Отрасль", entries) { it.position.sector ?: "Не получена" } }
                    item { ComparisonMetric("Ограничения", entries) { if (it.position.blocked) "Отмечены брокером" else "Не отмечены; возможность сделки проверяется у брокера" } }
                    entries.forEach { row -> item(key = portfolioRowKey(row)) { SpectrumCard {
                        Text(row.position.title, style = MaterialTheme.typography.titleMedium)
                        WatchPositionAction(row.position)
                        Text("Нужны одинаковые даты исследования и подтверждённые источники для сравнения прогнозов, рейтингов или эффекта стратегии.", style = MaterialTheme.typography.bodySmall)
                    } } }
                }
            }
        }
    }
}

@Composable
private fun ComparisonMetric(label: String, rows: List<PortfolioRow>, value: @Composable (PortfolioRow) -> String) {
    SpectrumCard {
        Text(label, style = MaterialTheme.typography.titleMedium)
        rows.forEach { row -> DataRow(row.position.ticker ?: row.position.title, value(row)) }
    }
}

private fun rawMoney(money: MoneyAmount?): String = money?.let { "${it.value.toBigDecimal().toPlainString()} ${it.currency}" } ?: "Не получено"
internal fun comparisonArchive(rows: List<PortfolioRow>): JSONObject = JSONObject().put("comparison", JSONArray(rows.map { row ->
    JSONObject().put("title", row.position.title).put("instrument_uid", row.position.id).put("account_id", row.account.id)
        .put("values", JSONArray(listOf(
            "Счёт" to row.account.name, "Цена за единицу" to rawMoney(row.position.currentPrice),
            "Стоимость позиции" to rawMoney(row.position.currentValue), "Количество" to (row.position.quantity?.toBigDecimal()?.toPlainString() ?: "Не получено"),
            "Результат за день" to rawMoney(row.position.dailyYieldAmount), "Источник" to "T‑Invest"
        ).map { (label, value) -> JSONObject().put("label", label).put("value", value) }))
}))
