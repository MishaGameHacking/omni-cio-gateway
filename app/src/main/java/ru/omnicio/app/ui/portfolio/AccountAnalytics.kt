package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.math.BigDecimal
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.*

@Composable
internal fun AccountAnalytics(token: String, account: PortfolioAccount, historyOnly: Boolean = false) {
    var start by rememberSaveable(account.id) { mutableStateOf<String?>(null) }
    var end by rememberSaveable(account.id) { mutableStateOf<String?>(null) }
    var chartMode by rememberSaveable(account.id) { mutableIntStateOf(0) }
    val period = PortfolioPeriod(start, end)
    val request = rememberAccountData(token, account.id, "analytics",
        period.parameters() + ("currency" to account.totalValue.currency), interval = 60_000)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item(key = "history") {
            CompactCard {
                SpectrumTabs(listOf("Стоимость", "Доход"), chartMode, { chartMode = it })
                CurrencyChoice(account.totalValue.currency)
                PeriodControls(period) { start = it.start; end = it.end }
                AccountDataNotice(request)
                request.json?.let { data ->
                    val history = data.objects("history").mapNotNull { point ->
                        point.optString("value").toBigDecimalOrNull()?.let { HistoryPoint(point.optString("date"), it) }
                    }
                    if (chartMode == 0) HistoryChart(history, data.optString("currency"), data.objects("cashFlowMarkers").mapNotNull { marker ->
                        val date = marker.nullableText("date"); val label = marker.nullableText("label")
                        if (date != null && label != null) HistoryMarker(date, label) else null
                    })
                    else WorkspaceEmpty("Доход за период", "Расчёт с учётом пополнений, выводов и расходов ещё не подключён. Стоимость доступна в соседней вкладке.")
                    if (data.optBoolean("historyTruncated")) Notice("Выборка графика ограничена. Выберите более короткий период.")
                }
            }
        }
        if (!historyOnly) item(key = "cashflow") {
            CompactCard {
                SectionHeading("Доходы и движение денег")
                val data = request.json
                Notice("Денежные потоки за выбранный период. Инвестиционный результат рассчитывается отдельно.")
                if (data != null) {
                    if (!data.optBoolean("complete")) Notice("Внимание: обработана только часть операций. Суммы ниже неполные; сузьте период.")
                    val rows = data.objects("summary")
                    if (rows.isEmpty()) Notice("За выбранный период учтённых денежных операций нет.")
                    val groups = listOf("Внесено / выведено" to setOf("deposits", "withdrawals"),
                        "Инвестиционные поступления" to setOf("dividends", "coupons", "redemptions"),
                        "Расходы" to setOf("fees", "tax"), "Оборот и прочее" to setOf("trades", "margin", "other"))
                    groups.forEach { (title, categories) -> DetailFold(title) {
                        val values = rows.filter { it.optString("category") in categories }
                        if (values.isEmpty()) Notice("В полученной выборке нет операций этой группы.")
                        values.forEach { row -> DataRow(categoryTitle(row.optString("category")), row.money("amount").moneyText()) }
                    } }
                    val known = groups.flatMap { it.second }.toSet()
                    rows.filter { it.optString("category") !in known }.forEach { row ->
                        DataRow("Прочие поступления / списания", row.money("amount").moneyText())
                    }
                    Notice("${data.optInt("operationCount")} операций в расчёте. Суммы в исходных валютах, без неподтверждённого пересчёта.")
                    Notice(data.optString("note"))
                }
            }
        }
        if (!historyOnly) item(key = "open-positions") {
            CompactCard {
                SectionHeading("Открытые позиции")
                DataRow("Дневной результат счёта", account.dailyYieldAmount.moneyText(true))
                DataRow("Текущая относительная доходность API", account.expectedYieldPercent.percentText())
                val grouped = account.positions.mapNotNull { it.expectedYieldAmount }.groupBy { it.currency }
                grouped.forEach { (currency, values) ->
                    val sum = values.sumOf { it.value.toBigDecimal() }
                    DataRow("Результат оценённых позиций", decimalText(sum) + " " + currencySymbol(currency))
                }
                Notice("Результат открытых позиций не равен доходу за всю историю счёта. Неоценённые позиции не включены в сумму.")
            }
        }
        if (!historyOnly) item(key = "structure") { CompactCard { SectionHeading("Структура портфеля"); AccountStructure(account) } }
    }
}

@Composable
internal fun AccountPayments(token: String, account: PortfolioAccount) {
    val request = rememberAccountData(token, account.id, "payments", interval = 60_000)
    val payments = request.json?.objects("items") ?: emptyList()
    var selected by remember { mutableStateOf<JSONObject?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item(key = "intro") {
            CompactCard {
                SectionHeading("Будущие выплаты")
                AccountDataNotice(request)
                request.json?.let { data ->
                    Notice(data.optString("note"))
                    if (!data.optBoolean("complete")) Notice("Получен неполный календарь. Часть инструментов или событий пока недоступна.")
                }
                Notice("Выплаты по уже проданным бумагам после даты реестра здесь пока не восстанавливаются. При неизвестной дате выплаты показана дата реестра, без прогноза суммы.")
            }
        }
        if (payments.isEmpty() && request.json != null) item { Notice("Для текущих позиций календарь не содержит полученных будущих выплат. Это не гарантия отсутствия будущего дохода.") }
        if (payments.isNotEmpty()) {
            item(key = "calendar-chart") {
                CompactCard {
                    SectionHeading("Оценка по месяцам")
                    val estimates = payments.mapNotNull { row -> row.money("estimate")?.let { row.optString("date").take(7) to it } }
                    val currencies = estimates.map { it.second.currency }.distinct()
                    if (currencies.isEmpty()) Notice("Суммы нельзя оценить по имеющимся данным.")
                    currencies.forEach { currency ->
                        val totals = estimates.filter { it.second.currency == currency }.groupBy { it.first }
                            .mapValues { (_, rows) -> rows.sumOf { it.second.value.toBigDecimal() } }.toSortedMap()
                        val points = totals.map { HistoryPoint(it.key + "-01T00:00:00Z", it.value) }
                        if (points.size > 1) PaymentBars(points, currency)
                        DetailFold("Точные суммы по месяцам · $currency") { totals.forEach { (month, amount) -> DataRow(month, decimalText(amount) + " " + currencySymbol(currency)) } }
                    }
                    Notice("Только события с известной суммой и датой выплаты; это оценка по текущему количеству, а не гарантированный доход.")
                }
            }
        }
        items(payments) { row ->
            Card(onClick = { selected = row }, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    val uid = row.optString("instrumentUid")
                    val name = account.positions.firstOrNull { it.id == uid }?.title ?: row.optString("title")
                    Text(name, fontWeight = FontWeight.Bold)
                    val dateLabel = if (row.optBoolean("dateUnknown")) "Реестр" else "Выплата"
                    DataRow(if (row.optString("kind") == "coupon") "Купон · $dateLabel" else "Дивиденд · $dateLabel", dateText(row.nullableText("date"), "dd.MM.yyyy"))
                    DataRow("На одну бумагу", row.money("perUnit").moneyText())
                    DataRow("Оценка по текущей позиции", row.money("estimate").moneyText())
                    if (row.optBoolean("eligibilityUnknown")) Notice("Право на выплату и количество на дату реестра не подтверждены.")
                }
            }
        }
    }
    selected?.let { row -> AlertDialog(onDismissRequest = { selected = null }, title = { Text("Условия выплаты") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            DataRow("Дата реестра", dateText(row.nullableText("recordDate"), "dd.MM.yyyy"))
            DataRow("На бумагу", row.money("perUnit").moneyText())
            Notice("Источником является календарь брокера. Будущие сделки, расчёты, изменения корпоративного события и налоги могут изменить фактическое поступление.")
        } }, confirmButton = { TextButton(onClick = { selected = null }) { Text("Закрыть") } }) }
}

@Composable
private fun PaymentBars(points: List<HistoryPoint>, currency: String) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Notice("Суммы скрыты"); return }
    val color = MaterialTheme.colorScheme.primary
    val max = points.maxOf { it.value }.takeIf { it > BigDecimal.ZERO } ?: BigDecimal.ONE
    androidx.compose.foundation.Canvas(Modifier.fillMaxWidth().height(80.dp)) {
        val step = size.width / points.size
        points.forEachIndexed { index, point ->
            val height = (point.value.toDouble() / max.toDouble() * size.height).toFloat().coerceIn(0f, size.height)
            drawRect(color, androidx.compose.ui.geometry.Offset(index * step + 2.dp.toPx(), size.height - height),
                androidx.compose.ui.geometry.Size((step - 4.dp.toPx()).coerceAtLeast(1f), height))
        }
    }
    DataRow(points.first().date.take(7), points.last().date.take(7))
    Notice("Оценка выплат · $currency · максимум ${decimalText(max)}")
}
