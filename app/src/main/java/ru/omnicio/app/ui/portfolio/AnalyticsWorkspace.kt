package ru.omnicio.app.ui.portfolio

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.math.BigDecimal
import java.math.MathContext
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.SpatialBackHandler

private val AnalyticsBlue = Color(0xFF78AAFA)
private val AnalyticsPurple = Color(0xFFB49AF7)

/** All figures originate in authenticated broker responses. No fixture data on this path. */
@Composable
internal fun AnalyticsWorkspace(state: PortfolioUiState, currency: PortfolioCurrency, token: String,
    refreshing: Boolean, error: String?, connect: () -> Unit, modifier: Modifier = Modifier,
    destination: PortfolioDestination? = null, consumed: () -> Unit = {},
    initialPositionId: String? = null, initialStart: String? = null, initialEnd: String? = null) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var page by rememberSaveable { mutableStateOf("overview") }
    var positionAccount by rememberSaveable { mutableStateOf<String?>(null) }
    var positionId by rememberSaveable { mutableStateOf<String?>(null) }
    var operationId by rememberSaveable { mutableStateOf<String?>(null) }
    var operationDate by rememberSaveable { mutableStateOf<String?>(null) }
    var assetKind by rememberSaveable { mutableStateOf<String?>(null) }
    var assetSector by rememberSaveable { mutableStateOf<String?>(null) }
    var accountPicker by rememberSaveable { mutableStateOf(false) }
    var routeMessage by remember { mutableStateOf<String?>(null) }
    var start by rememberSaveable { mutableStateOf(initialStart) }
    var end by rememberSaveable { mutableStateOf(initialEnd) }
    var structureMode by rememberSaveable { mutableIntStateOf(0) }
    val period = PortfolioPeriod(start, end)
    val accounts = snapshot?.accounts.orEmpty().filter { accountId == null || it.id == accountId }
    LaunchedEffect(destination, initialPositionId, snapshot?.accounts?.map { it.id }) {
        val target = destination
        val uid = target?.query?.takeIf { it.isNotBlank() } ?: initialPositionId
        if (target != null) {
            accountId = target.accountId
            operationId = target.operationId
            operationDate = target.operationDate
            assetKind = target.kind
            assetSector = target.sector
        }
        if (uid != null && snapshot != null) {
            val matches = snapshot.accounts.filter { target?.accountId == null || it.id == target.accountId }
                .flatMap { account -> account.positions.filter { it.id == uid || it.ticker == uid }.map { account.id to it.id } }
            if (matches.size == 1) { positionAccount = matches[0].first; positionId = matches[0].second }
            else { page = "assets"; routeMessage = "Этот актив отсутствует в текущем составе счёта. Обновите данные или откройте его через поиск рынка." }
        } else if (target != null) {
            page = when { target.operationId != null -> "operations"; target.kind != null || target.sector != null -> "assets"; target.section == 2 -> "value"; target.section == 1 -> "assets"; target.section == 4 -> "payments"; else -> "overview" }
        }
        if (target != null) consumed()
    }
    SpatialBackHandler(page != "overview" || positionId != null) {
        if (positionId != null) positionId = null else page = "overview"
    }
    if (positionId != null) {
        val account = snapshot?.accounts?.firstOrNull { it.id == positionAccount }
        val position = account?.positions?.firstOrNull { it.id == positionId }
        if (position != null && account != null) InstrumentDetailsScreen(position, { positionId = null }, account.name, accountId = account.id)
        else Column(modifier.padding(20.dp)) {
            Text("Позиция больше не найдена в текущем портфеле")
            SpectrumSecondaryButton("К аналитике", { positionId = null })
        }
        return
    }
    val requests = accounts.map { account -> key(account.id) {
        rememberAccountData(token, account.id, "analytics", period.parameters() + ("currency" to currency.name), interval = 60_000)
    } }
    val payments = accounts.map { account -> key("payments:" + account.id) {
        rememberAccountData(token, account.id, "payments", interval = 60_000)
    } }
    val current = requests.size == accounts.size && accounts.isNotEmpty() && requests.all { it.json != null && !it.showingPreviousQuery && it.error == null }
    val total = if (accountId == null) snapshot?.totalValue else accounts.singleOrNull()?.totalValue
    val open: (String) -> Unit = { page = it }
    Column(modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            if (page != "overview") TextButton(onClick = { page = "overview" }) { Text("‹ Назад") }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = { accountPicker = true }, enabled = snapshot != null) {
                Text((accounts.singleOrNull()?.name ?: "Все счета") + " ▾", maxLines = 1)
            }
        }
        Text(when(page) { "value" -> "Стоимость портфеля"; "payments" -> "Будущие выплаты"; "structure" -> "Структура портфеля"; "assets" -> "Активы"; "operations" -> "Операции"; else -> "Аналитика" },
            Modifier.padding(horizontal = 20.dp, vertical = 8.dp), style = MaterialTheme.typography.headlineLarge)
        if (snapshot == null) {
            AnalyticsCard(Modifier.padding(20.dp)) {
                Text(when(state) { PortfolioUiState.Loading -> "Загружаем портфель…"; is PortfolioUiState.Error -> state.message; else -> "Подключите Т‑Инвестиции, чтобы видеть свои данные" })
                SpectrumPrimaryButton("Подключение", connect)
            }
        } else AnimatedContent(page, modifier = Modifier.weight(1f), transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "analytics-page") { visible ->
            if (visible == "operations" && accounts.size == 1) {
                AccountOperations(token, accounts.single(), onPosition = { selected ->
                    positionAccount = selected.accountId; positionId = selected.positionId
                }, initialOperationId = operationId, initialOperationDate = operationDate)
            } else LazyColumn(Modifier.fillMaxSize().testTag("portfolio-content"), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                if (error != null || refreshing) item { Text(error ?: "Обновляем данные…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                routeMessage?.let { message -> item { Text(message); TextButton(onClick = { routeMessage = null }) { Text("Понятно") } } }
                if (visible == "overview" || visible == "value") item { AnalyticsCard {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text(PrivateValue(total.moneyText()), Modifier.weight(1f), style = MaterialTheme.typography.headlineMedium)
                        CurrencyChoice(total?.currency ?: currency.name)
                    }
                    Text("Стоимость портфеля", style = MaterialTheme.typography.bodyLarge)
                    if (current) AnalyticsHistory(requests.mapNotNull { it.json }, currency.name)
                    else Text(if (requests.any { it.error != null }) "История сейчас недоступна. Текущая стоимость получена отдельно." else "Получаем историю…", style = MaterialTheme.typography.bodySmall)
                    PeriodControls(period) { start = it.start; end = it.end }
                    AnalyticsTotals(requests, current, visible == "value")
                    if (visible == "overview") AnalyticsMore { open("value") }
                    else {
                        HorizontalDivider()
                        Text("Открытые позиции", style = MaterialTheme.typography.titleLarge)
                        val daily = accounts.mapNotNull { it.dailyYieldAmount }.takeIf { it.size == accounts.size && it.all { m -> m.currency == total?.currency } }
                        AnalyticsMetric("Сегодня", daily?.sumOf { it.value.toBigDecimal() }?.let { decimalText(it) + " " + currencySymbol(total?.currency ?: currency.name) } ?: "—")
                        Text("Полная история графика накапливается с подключения приложения. Доходность недоступного периода не восстанавливается по догадке.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                } }
                if (visible == "overview" || visible == "payments") item { AnalyticsCard {
                    Text("Будущие выплаты", style = MaterialTheme.typography.titleLarge)
                    AnalyticsPayments(payments, visible == "payments")
                    if (visible == "overview") AnalyticsMore { open("payments") }
                } }
                if (visible == "overview" || visible == "structure") item { AnalyticsCard {
                    Text("Структура портфеля", style = MaterialTheme.typography.titleLarge)
                    AnalyticsChips(listOf("Активы", "Компании", "Отрасли", "Валюта"), structureMode) { structureMode = it }
                    AnalyticsStructure(accounts, total, structureMode)
                    if (visible == "overview") AnalyticsMore { open("structure") }
                    else AnalyticsMore("Открыть активы") { open("assets") }
                } }
                if (visible == "overview") item { Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(onClick = { open("assets") }, modifier = Modifier.weight(1f)) { Text("Мои активы") }
                    OutlinedButton(onClick = { if (accounts.size == 1) open("operations") else accountPicker = true }, modifier = Modifier.weight(1f)) { Text("Операции") }
                } }
                if (visible == "assets") {
                    val rows = accounts.flatMap { a -> a.positions.filter { (assetKind == null || it.instrumentType == assetKind) && (assetSector == null || it.sector == assetSector) }.map { a to it } }
                    if (rows.isEmpty()) item { Text("На выбранных счетах пока нет позиций") }
                    items(rows, key = { it.first.id + ":" + it.second.id }) { (account, position) ->
                        Row(Modifier.fillMaxWidth().clickable { positionAccount = account.id; positionId = position.id }.padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(position.title, style = MaterialTheme.typography.titleMedium)
                                Text(position.ticker ?: account.name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Text(PrivateValue(position.currentValue.moneyText()))
                        }
                    }
                }
                item { Text("Данные Т‑Инвестиций · " + relativeObservation(snapshot.asOf), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
    if (accountPicker) WorkspaceDialog("Счета", { accountPicker = false }) {
        TextButton(onClick = { accountId = null; accountPicker = false }) { Text("Все счета") }
        snapshot?.accounts.orEmpty().forEach { account ->
            TextButton(onClick = { accountId = account.id; accountPicker = false }) { Text(account.name) }
        }
    }
}

@Composable
internal fun AnalyticsCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp), content = content)
    }
}

@Composable
private fun AnalyticsMore(title: String = "Посмотреть всё", open: () -> Unit) {
    FilledTonalButton(onClick = open, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) { Text(title, color = MaterialTheme.colorScheme.primary) }
}

@Composable
private fun AnalyticsChips(labels: List<String>, selected: Int, select: (Int) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        labels.forEachIndexed { index, label -> FilterChip(selected == index, { select(index) }, label = { Text(label) }, shape = RoundedCornerShape(24.dp)) }
    }
}

/** Multi-account totals require every account at exactly the same observed instant. */
internal fun joinedAnalyticsHistory(documents: List<JSONObject>): List<HistoryPoint> {
    if (documents.isEmpty() || documents.map { it.optString("currency") }.distinct().size != 1) return emptyList()
    val maps = documents.map { data -> data.records("history").mapNotNull { row ->
        row.optString("value").toBigDecimalOrNull()?.let { row.optString("date") to it }
    }.toMap() }
    val common = maps.map { it.keys }.reduce { a, b -> a.intersect(b) }
    return common.sorted().map { date -> HistoryPoint(date, maps.sumOf { it.getValue(date) }) }
}

@Composable
private fun AnalyticsHistory(documents: List<JSONObject>, currency: String) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Text("График скрыт режимом приватности"); return }
    val points = remember(documents.map { it.toString() }) { joinedAnalyticsHistory(documents) }
    val bars = remember(points) { historyBars(points)?.bars.orEmpty() }
    var selected by remember(points) { mutableIntStateOf(-1) }
    val amounts = bars.mapNotNull { it.close?.value }
    val high = amounts.maxOrNull()?.max(BigDecimal.ZERO) ?: BigDecimal.ZERO
    val low = amounts.minOrNull()?.min(BigDecimal.ZERO) ?: BigDecimal.ZERO
    val span = high - low
    if (bars.isEmpty()) { Text("За этот период нет сохранённых наблюдений", style = MaterialTheme.typography.bodySmall); return }
    val guide = MaterialTheme.colorScheme.outlineVariant
    val chosen = bars.getOrNull(selected)?.close
    Text(chosen?.let { dateText(it.date) + " · " + decimalText(it.value) + " " + currencySymbol(currency) }
        ?: "История с " + dateText(points.first().date), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(Modifier.fillMaxWidth().height(170.dp), horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.Bottom) {
        bars.forEachIndexed { index, bar ->
            val value = bar.close?.value
            val fraction = if (value != null && span.signum() > 0) (value.abs().divide(span, MathContext.DECIMAL64)).toFloat().coerceIn(0f, 1f) else 0f
            Canvas(Modifier.weight(1f).fillMaxHeight().clickable(enabled = value != null) { selected = index }.semantics {
                contentDescription = bar.start.toString() + ": " + (value?.toPlainString() ?: "нет наблюдения")
            }) {
                val zero = if (span.signum() == 0) size.height else size.height * (high.divide(span, MathContext.DECIMAL64)).toFloat()
                drawLine(guide, Offset(0f, zero), Offset(size.width, zero), 1f)
                if (value != null && fraction > 0) {
                    val height = size.height * fraction
                    val top = if (value.signum() >= 0) zero - height else zero
                    drawRoundRect(if (index == selected) AnalyticsPurple else AnalyticsBlue, Offset(0f, top), Size(size.width, height), CornerRadius(3.dp.toPx()))
                }
            }
        }
    }
    Text("Нажмите на столбик, чтобы увидеть сумму. Пробелы означают отсутствие данных.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun AnalyticsTotals(requests: List<AccountData>, current: Boolean, full: Boolean) {
    if (!current) return
    val data = requests.mapNotNull { it.json }
    val complete = data.all { it.optBoolean("complete") }
    val summaries = data.flatMap { it.records("summary") }
    AnalyticsMetric("Общий доход", "Недостаточно истории")
    val labels = if (full) listOf("dividends" to "Дивиденды", "coupons" to "Купоны", "deposits" to "Пополнения", "withdrawals" to "Выводы", "fees" to "Комиссии", "tax" to "Налоги") else listOf("dividends" to "Дивиденды", "coupons" to "Купоны")
    labels.forEach { (category, label) ->
        val amounts = summaries.filter { it.optString("category") == category }.mapNotNull { it.money("amount") }
        if (amounts.isEmpty()) AnalyticsMetric(label, PrivateValue(if (complete) "0" else "—"))
        else amounts.groupBy { it.currency }.forEach { (currency, rows) ->
            val sum = rows.sumOf { it.value.toBigDecimal() }
            AnalyticsMetric(label + if (!complete) " · часть данных" else "", PrivateValue(decimalText(sum) + " " + currencySymbol(currency)), sum.takeIf { category in listOf("coupons", "dividends") })
        }
    }
}

@Composable
private fun AnalyticsMetric(label: String, value: String, signed: BigDecimal? = null) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Text(value, Modifier.weight(1f), textAlign = androidx.compose.ui.text.style.TextAlign.End,
            color = when { signed == null || signed.signum() == 0 -> MaterialTheme.colorScheme.onSurface; signed.signum() > 0 -> LocalSpectrumPalette.current.semantic.success; else -> MaterialTheme.colorScheme.error })
    }
}

@Composable
private fun AnalyticsPayments(requests: List<AccountData>, full: Boolean) {
    val available = requests.isNotEmpty() && requests.all { it.json != null && it.error == null }
    if (!available) { Text("Календарь выплат пока недоступен", style = MaterialTheme.typography.bodySmall); return }
    val rows = requests.flatMap { it.json?.records("items").orEmpty() }
    val complete = requests.all { it.json?.optBoolean("complete") == true }
    if (rows.isEmpty()) { Text(if (complete) "По текущим позициям объявленных выплат нет" else "Календарь получен частично. Выплаты пока не найдены"); return }
    val estimates = rows.mapNotNull { row -> row.money("estimate")?.let { row.optString("date").take(7) to it } }
    if (estimates.isEmpty()) Text("Даты объявлены, но сумма пока неизвестна")
    estimates.groupBy { it.second.currency }.forEach { (currency, values) ->
        val totals = values.groupBy { it.first }.mapValues { (_, group) -> group.sumOf { it.second.value.toBigDecimal() } }.toSortedMap()
        val max = totals.values.maxOrNull() ?: BigDecimal.ZERO
        totals.entries.take(if (full) 24 else 6).forEach { (month, amount) ->
            AnalyticsMetric(month, PrivateValue(decimalText(amount) + " " + currencySymbol(currency)))
            if (!LocalWorkspacePreferences.current.value.hideHomeBalance) SpectrumProgressBar(if (max.signum() > 0) amount.divide(max, MathContext.DECIMAL64).toFloat() else 0f, accent = AnalyticsBlue)
        }
    }
    Text("Оценка по текущему количеству бумаг. Сроки зачисления и будущие выплаты могут измениться.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    if (full) rows.take(100).forEach { row -> AnalyticsMetric(row.optString("name", row.optString("title", "Выплата")), dateText(row.optString("date"))) }
}

@Composable
private fun AnalyticsStructure(accounts: List<PortfolioAccount>, total: MoneyAmount?, mode: Int) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Text("Структура скрыта режимом приватности"); return }
    val totalAmount = total?.value?.toBigDecimal() ?: BigDecimal.ZERO
    val positions = accounts.flatMap { it.positions }
    val buckets = linkedMapOf<String, BigDecimal>()
    if (accounts.any { it.totalValue.currency != total?.currency }) {
        Text("Счета получены в разных валютах. Дождитесь обновления."); return
    }
    if (mode == 0 && totalAmount.signum() > 0) {
        accounts.forEach { a -> a.allocations.forEach { allocation ->
            val amount = a.totalValue.value.toBigDecimal().multiply(allocation.sharePercent.toBigDecimal()).divide(BigDecimal(100))
            buckets[allocation.title] = (buckets[allocation.title] ?: BigDecimal.ZERO) + amount
        } }
    } else {
        if (positions.any { it.currentValue == null || it.currentValue.currency != total?.currency }) {
            Text("Для этой группировки не хватает сопоставимых оценок. Откройте отдельные активы."); return
        }
        positions.forEach { p ->
            val title = when(mode) {
                1 -> if (p.instrumentType in listOf("cash", "currency")) "Деньги" else p.company ?: "Компания не определена"
                2 -> if (p.instrumentType in listOf("cash", "currency")) "Деньги" else p.sector ?: "Отрасль не определена"
                else -> p.currentPrice?.currency ?: p.currentValue?.currency ?: "Валюта не определена"
            }
            buckets[title] = (buckets[title] ?: BigDecimal.ZERO) + p.currentValue!!.value.toBigDecimal()
        }
    }
    if (totalAmount.signum() <= 0 || buckets.values.any { it.signum() < 0 }) { Text("Диаграмма недоступна для нулевой стоимости или отрицательных долей"); return }
    val sum = buckets.values.fold(BigDecimal.ZERO, BigDecimal::add)
    if (sum > totalAmount * BigDecimal("1.001")) { Text("Суммы ещё не согласованы. Обновите портфель."); return }
    if (totalAmount - sum > totalAmount * BigDecimal("0.001")) buckets["Не распределено API"] = totalAmount - sum
    val fractions = buckets.map { it.key to it.value.divide(totalAmount, MathContext.DECIMAL64).toFloat() }.filter { it.second > 0f }
    val colors = LocalSpectrumPalette.current.chartSeries
    Box(Modifier.fillMaxWidth().height(232.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(224.dp).semantics { contentDescription = "Структура портфеля, " + fractions.joinToString { it.first + " " + (it.second * 100).toInt() + "%" } }) {
            var angle = -90f
            fractions.forEachIndexed { index, (_, share) ->
                drawArc(colors[index % colors.size], angle, share * 360f, false, topLeft = Offset(10.dp.toPx(), 10.dp.toPx()), size = Size(size.width - 20.dp.toPx(), size.height - 20.dp.toPx()), style = Stroke(9.dp.toPx()))
                angle += share * 360f
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(PrivateValue(total.moneyText()), style = MaterialTheme.typography.titleLarge)
            Text("Групп: " + fractions.size, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
    fractions.forEachIndexed { index, (title, fraction) ->
        AnalyticsMetric(title, decimalText(BigDecimal.valueOf(fraction.toDouble() * 100)) + "%")
        SpectrumProgressBar(fraction, accent = colors[index % colors.size])
    }
}
