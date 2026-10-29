package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.SpectrumBackground

private const val CashTitle = "Денежные средства"

@Composable
fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    selectedCurrency: PortfolioCurrency = PortfolioCurrency.RUB,
    modifier: Modifier = Modifier,
    accessToken: String = "",
    refreshing: Boolean = false,
    refreshError: String? = null,
    lastUpdatedMillis: Long? = null,
    onConnect: () -> Unit = onProfileClick,
    destination: PortfolioDestination? = null,
    onDestinationConsumed: () -> Unit = {},
    initialPositionId: String? = null,
    initialHistoryDate: String? = null,
    initialHistoryStart: String? = null,
    initialHistoryEnd: String? = null,
    initialHistoryResolution: String? = null,
) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Portfolio, {}, onProfileClick) }) { insets ->
            AnalyticsWorkspace(state, selectedCurrency, accessToken, refreshing, refreshError, onConnect,
                Modifier.padding(insets).consumeWindowInsets(insets), destination, onDestinationConsumed,
                initialPositionId, initialHistoryStart ?: initialHistoryDate?.take(10), initialHistoryEnd)
        }
    }
}

@Composable
internal fun AssetStructure(allocations: List<PortfolioAllocation>, total: MoneyAmount) {
    val destination = LocalPortfolioDestination.current
    var unlinked by remember { mutableStateOf<String?>(null) }
    if (total.value.toBigDecimal().signum() <= 0 || allocations.any { it.sharePercent.toBigDecimal().signum() < 0 }) {
        allocations.forEach { DataRow(it.title, it.sharePercent.percentText()) }
        Notice("Круговая диаграмма не используется для нулевой стоимости или отрицательных долей.")
        return
    }
    val slices = allocations.map { ChartSlice(it.title, it.sharePercent.toBigDecimal().toFloat()) }.toMutableList()
    val missing = 100f - slices.sumOf { it.weight.toDouble() }.toFloat()
    if (missing > 0.1f) slices += ChartSlice("Прочее / не распределено API", missing)
    if (missing < -0.1f) {
        allocations.forEach { DataRow(it.title, it.sharePercent.percentText()) }
        Notice("Сумма долей превышает 100%; показаны значения API без нормализации.")
    } else StructureChart(slices, total.moneyText(), "По классам активов") { title ->
        val kind = allocationKind(title)
        if (kind != null) destination(PortfolioDestination(kind = kind)) else unlinked = title
    }
    unlinked?.let { Notice("Категория «$it» не сопоставлена с отдельными позициями в ответе API. Её состав не выводится из остатка диаграммы.") }
}

internal fun allocationKind(title: String): String? = when (title) {
    "Акции" -> "share"; "Облигации" -> "bond"; "Фонды" -> "etf"; "Валюта и деньги", "Деньги", "Валюта" -> "cash"
    "Фьючерсы" -> "futures"; "Опционы" -> "option"; "Прочие активы" -> "other"
    else -> null
}

@Composable
internal fun AccountStructure(account: PortfolioAccount) {
    var mode by rememberSaveable(account.id) { mutableIntStateOf(0) }
    var selectedGroup by rememberSaveable(account.id, mode) { mutableStateOf<String?>(null) }
    val destination = LocalPortfolioDestination.current
    ChoiceRow(listOf("Активы", "Компании", "Отрасли", "Валюта"), mode) { mode = it }
    if (mode == 0) { AssetStructure(account.allocations, account.totalValue); return }
    val positions = account.positions
    val currencies = positions.mapNotNull { it.currentValue?.currency }.distinct()
    if (currencies.size != 1 || positions.any { it.currentValue == null || it.currentValue.value.toBigDecimal().signum() < 0 }) {
        Notice("Для общей диаграммы не хватает сопоставимой оценки всех позиций в одной валюте. Несопоставимые суммы не складываются.")
        positions.groupBy { when (mode) {
            1 -> if (it.instrumentType == "cash") CashTitle else it.company ?: it.title
            2 -> if (it.instrumentType == "cash") CashTitle else it.sector ?: "Отрасль не указана"
            else -> it.currentValue?.currency ?: "Валюта не определена"
        } }.forEach { (title, rows) ->
            Text(title, fontWeight = FontWeight.SemiBold)
            rows.forEach { DataRow(it.ticker ?: it.title, it.currentValue.moneyText()) }
        }
        return
    }
    val groups = positions.groupBy { when (mode) {
        1 -> if (it.instrumentType == "cash") CashTitle else it.company ?: it.title
        2 -> if (it.instrumentType == "cash") CashTitle else it.sector ?: "Отрасль не указана"
        else -> it.currentValue?.currency ?: "Не определена"
    } }
    val totals = groups.mapValues { (_, rows) -> rows.sumOf { it.currentValue!!.value.toBigDecimal() } }
    val total = totals.values.fold(java.math.BigDecimal.ZERO, java.math.BigDecimal::add)
    StructureChart(totals.map { ChartSlice(it.key, it.value.toFloat()) }, decimalText(total) + " " + currencySymbol(currencies.first()),
        if (mode == 3) "Валюта оценки позиций" else "По доступным данным позиций") { selectedGroup = it }
    selectedGroup?.let { group ->
        DetailFold("Состав: $group", initiallyOpen = true) {
            groups[group].orEmpty().forEach { position ->
                PositionLine(position, account.totalValue, sharedKey = "${account.id}:${position.id}") {
                    destination(PortfolioDestination(accountId = account.id, query = position.id))
                }
            }
        }
    }
    if (mode == 1) Notice("Группировка по названиям инструментов/компаний API; единая структура эмитентов для всех типов активов ещё уточняется.")
}

