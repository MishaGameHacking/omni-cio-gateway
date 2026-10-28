package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.math.BigDecimal
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.*

private const val DISPLAY_DATE_PATTERN = "dd.MM.yyyy"


@Composable
internal fun AccountAnalytics(token: String, account: PortfolioAccount, historyOnly: Boolean = false,
    initialDate: String? = null, initialStart: String? = null, initialEnd: String? = null, initialResolution: String? = null) {
    val anchor = initialDate?.let { runCatching { java.time.Instant.parse(it).atZone(Moscow).toLocalDate() }.getOrNull()
        ?: runCatching { java.time.LocalDate.parse(it.take(10)) }.getOrNull() }
    val (defaultStart, defaultEnd) = initialAnalyticsPeriod(initialStart, initialEnd, anchor, initialResolution)
    var start by rememberSaveable(account.id, initialDate, initialStart, initialEnd, initialResolution) { mutableStateOf(defaultStart?.toString()) }
    var end by rememberSaveable(account.id, initialDate, initialStart, initialEnd, initialResolution) { mutableStateOf(defaultEnd?.toString()) }
    var resolutionOverride by rememberSaveable(account.id, initialDate, initialStart, initialEnd, initialResolution) {
        mutableStateOf(initialResolution?.takeIf { it in setOf("intraday", "hour", "day") })
    }
    val period = PortfolioPeriod(start, end)
    val setPeriod: (PortfolioPeriod) -> Unit = { start = it.start; end = it.end; resolutionOverride = null }
    val sourceParameters = mapOf("currency" to account.totalValue.currency) +
        (resolutionOverride?.let { mapOf("history_resolution" to it) } ?: emptyMap())
    var selectedPeriod by remember(account.id, period) { mutableStateOf<PortfolioPeriod?>(null) }
    val request = rememberAccountData(token, account.id, "analytics",
        period.parameters() + sourceParameters, interval = 60_000)
    val selectedData = selectedPeriod?.let { scope -> rememberAccountData(token, account.id, "analytics",
        scope.parameters() + ("currency" to account.totalValue.currency), interval = 60_000) }
    val workspace = LocalWorkspaceSnapshot.current
    val askAnalyst = LocalAskAnalyst.current
    val events = workspace?.sectionData("events")?.records("items").orEmpty().filter { event ->
        event.stringList("instrument_uids").any { uid -> account.positions.any { it.id == uid } } || event.optionalText("account_id") == account.id
    }
    LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
        contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item(key = "history") {
            CompactCard {
                CurrencyChoice(account.totalValue.currency)
                if (request.error != null || request.showingPreviousQuery || request.json == null) AccountDataNotice(request)
                if (request.json == null) PeriodControls(period, setPeriod)
                request.json?.let { data ->
                    val history = data.objects("history").mapNotNull { point ->
                        point.optString("value").toBigDecimalOrNull()?.let { HistoryPoint(point.optString("date"), it) }
                    }
                    HistoryChart(history, data.optString("currency"),
                        markers = events.mapNotNull { event -> event.optionalText("occurred_at")?.let { HistoryMarker(it, event.optionalText("title") ?: "Событие источника") } },
                        selectionKey = "${account.id}:${request.displayedParameters}",
                        initialSelectedDate = anchor?.toString(),
                        initialSelectedInstant = initialDate?.let { runCatching { java.time.Instant.parse(it).toString() }.getOrNull() },
                        sourceResolution = data.optionalText("historyResolution") ?: resolutionOverride,
                        onSelection = { if (!request.showingPreviousQuery) selectedPeriod = it },
                        controls = { PeriodControls(period, setPeriod) })
                    if (data.optBoolean("historyTruncated")) Notice("Выборка графика ограничена. Выберите более короткий период.")
                }
            }
        }
        item(key = "period-comparison") { DetailFold("Сравнить два периода") { AccountPeriodComparison(token, account) } }
        if (events.isNotEmpty()) item(key = "source-events") { DetailFold("События рядом с графиком") {
            val destination = LocalPortfolioDestination.current
            Text("Связи относятся к инструментам текущего портфеля. Совпадение даты с изменением баланса не определяет его причину.")
            WorkspaceEvents(events, workspace?.records("sources").orEmpty()) { uid -> destination(PortfolioDestination(accountId = account.id, query = uid)) }
        } }
        item(key = "cashflow") {
            CompactCard {
                SectionHeading("Движение денег")
                val scope = selectedPeriod ?: period
                Notice(if (selectedPeriod == null) "За выбранный период" else "${scope.start} — ${scope.end}")
                val current = selectedData ?: request
                if (current.showingPreviousQuery || current.json == null) {
                    Notice(current.error ?: "Обновляем статистику интервала…")
                } else {
                    current.error?.let { Notice(it) }
                    CashFlowSummary(current.json)
                    TextButton(onClick = { askAnalyst(ChatContext(mode = "portfolio", accountId = account.id,
                        title = "${account.name} · ${scope.start ?: "вся история"} — ${scope.end ?: "по последний снимок"}",
                        start = scope.start, end = scope.end)) }) { Text("Обсудить выбранный период") }
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
internal fun CashFlowSummary(data: JSONObject) {
    if (!data.optBoolean("complete")) Notice("Получена часть операций. Суммы неполные; попробуйте более короткий период.")
    val rows = data.objects("summary").filter { it.money("amount")?.value?.toBigDecimal()?.signum() != 0 }
    val primary = setOf("deposits", "withdrawals", "dividends", "coupons")
    val visible = rows.filter { it.optString("category") in primary }
    visible.forEach { row -> DataRow(categoryTitle(row.optString("category")), row.money("amount").moneyText()) }
    if (rows.isEmpty()) Notice(if (data.optBoolean("complete")) "Ненулевых итоговых сумм за этот период нет." else "В полученной части нет ненулевых итоговых сумм.")
    val other = rows.filter { it.optString("category") !in primary }
    if (other.isNotEmpty()) DetailFold("Расходы, оборот и другие операции") {
        other.forEach { row -> DataRow(categoryTitle(row.optString("category")), row.money("amount").moneyText()) }
    }
    Notice("Денежные потоки в исходных валютах. Это не расчёт инвестиционной прибыли.")
}

@Composable
internal fun AccountPayments(token: String, account: PortfolioAccount) {
    val request = rememberAccountData(token, account.id, "payments", interval = 60_000)
    val payments = request.json?.objects("items") ?: emptyList()
    val user = LocalWorkspaceSession.current.userId
    var selectedKey by rememberSaveable(user, account.id) { mutableStateOf<String?>(null) }
    val matches = payments.filter { paymentSelectionKey(it, user, account.id) == selectedKey && selectedKey != null }
    val selected = matches.singleOrNull()
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
            SpectrumCard(onClick = { selectedKey = paymentSelectionKey(row, user, account.id) }) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    val uid = row.optString("instrumentUid")
                    val name = account.positions.firstOrNull { it.id == uid }?.title ?: row.optString("title")
                    Text(name, fontWeight = FontWeight.Bold)
                    val dateLabel = if (row.optBoolean("dateUnknown")) "Реестр" else "Выплата"
                    DataRow(if (row.optString("kind") == "coupon") "Купон · $dateLabel" else "Дивиденд · $dateLabel", dateText(row.nullableText("date"), DISPLAY_DATE_PATTERN))
                    DataRow("На одну бумагу", row.money("perUnit").moneyText())
                    DataRow("Оценка по текущей позиции", row.money("estimate").moneyText())
                    if (row.optBoolean("eligibilityUnknown")) Notice("Право на выплату и количество на дату реестра не подтверждены.")
                }
            }
        }
    }
    selected?.let { row -> AlertDialog(onDismissRequest = { selectedKey = null }, title = { Text("Условия выплаты") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            AccountDataNotice(request)
            Text(account.positions.firstOrNull { it.id == row.optionalText("instrumentUid") }?.title ?: row.optString("title"))
            DataRow("Дата события", dateText(row.optionalText("date"), DISPLAY_DATE_PATTERN))
            DataRow("Дата реестра", dateText(row.nullableText("recordDate"), DISPLAY_DATE_PATTERN))
            DataRow("На бумагу", row.money("perUnit").moneyText())
            Notice("Источником является календарь брокера. Будущие сделки, расчёты, изменения корпоративного события и налоги могут изменить фактическое поступление.")
        } }, confirmButton = { TextButton(onClick = { selectedKey = null }) { Text("Закрыть") } }) }
    if (selectedKey != null && selected == null) WorkspaceDialog("Условия выплаты", { selectedKey = null }) {
        when {
            request.json == null && request.error == null -> SpectrumLoadingIndicator(description = "Восстанавливаем выбранную выплату из ответа брокера")
            request.json == null -> Text(request.error ?: "Ответ календаря не получен.")
            matches.size > 1 -> Text("В ответе несколько событий с одинаковыми идентификаторами и датами. Одно из них не выбирается произвольно.")
            else -> Text("Выбранная выплата отсутствует в текущем календаре или её даты изменились. Сведения другой выплаты не подставляются.")
        }
        SpectrumSecondaryButton("К календарю", { selectedKey = null }, Modifier.fillMaxWidth())
    }
}

/** The broker calendar has no universal event ID: keep its identity fields, never amounts or a stale row. */
private fun paymentSelectionKey(row: JSONObject, user: String, account: String): String? = paymentSelectionKey(
    user, account, row.optionalText("instrumentUid"), row.optionalText("kind"), row.optionalText("date"), row.optionalText("recordDate"))

internal fun paymentSelectionKey(user: String, account: String, uid: String?, kind: String?, date: String?, record: String?): String? =
    if (uid.isNullOrBlank() || kind.isNullOrBlank()) null
    else listOf(user, account, uid, kind, date.orEmpty(), record.orEmpty()).joinToString("") { "${it.length}:$it" }

@Composable
private fun PaymentBars(points: List<HistoryPoint>, currency: String) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Notice("Суммы скрыты"); return }
    val max = points.maxOf { it.value }.takeIf { it > BigDecimal.ZERO } ?: BigDecimal.ONE
    ru.omnicio.app.ui.spatial.SpatialBars(points.map { it.value.toDouble() }, 0.0, max.toDouble(), modifier = Modifier.fillMaxWidth().height(100.dp))
    DataRow(points.first().date.take(7), points.last().date.take(7))
    Notice("Оценка выплат · $currency · максимум ${decimalText(max)}")
}


private fun initialAnalyticsPeriod(
    start: String?,
    end: String?,
    anchor: java.time.LocalDate?,
    resolution: String?,
): Pair<java.time.LocalDate?, java.time.LocalDate?> {
    val today = java.time.LocalDate.now(Moscow)
    val targetStart = start?.let { runCatching { java.time.LocalDate.parse(it) }.getOrNull() }
    val targetEnd =
        end?.let { runCatching { java.time.LocalDate.parse(it) }.getOrNull() }?.coerceAtMost(today)
    if (targetStart != null && targetEnd != null && targetStart <= targetEnd)
        return targetStart to targetEnd
    if (anchor == null) return null to null
    val range =
        when (resolution) {
            "intraday" -> anchor to anchor
            "hour" -> anchor.minusDays(15) to anchor.plusDays(15)
            else -> anchor.minusMonths(1) to anchor.plusMonths(1)
        }
    return range.first to range.second.coerceAtMost(today)
}
