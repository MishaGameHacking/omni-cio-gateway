package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.spatial.SpatialCandle
import ru.omnicio.app.ui.spatial.SpatialCandles
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*
import java.time.Instant
import java.time.LocalDate
import java.time.temporal.ChronoUnit

@Composable
internal fun InstrumentQuotesPanel(position: PortfolioPosition, accountId: String? = null, onNavigate: () -> Unit = {}) {
    val today = LocalDate.now(Moscow)
    var start by rememberSaveable(position.id) { mutableStateOf(today.minusMonths(1).toString()) }
    var end by rememberSaveable(position.id) { mutableStateOf(today.toString()) }
    var interval by rememberSaveable(position.id) { mutableStateOf("day") }
    var selectedTime by rememberSaveable(position.id) { mutableStateOf<String?>(null) }
    val askAnalyst = LocalAskAnalyst.current
    val request = rememberWorkspaceRequest("/workspace/instruments/${position.id}/candles", mapOf("start" to start, "end" to end, "interval" to interval))
    SpectrumCard {
        Text("Рыночные свечи", style = MaterialTheme.typography.titleLarge)
        PeriodControls(PortfolioPeriod(start, end)) { next ->
            start = next.start ?: today.minusYears(5).toString(); end = next.end ?: today.toString()
            if (interval == "hour" && ChronoUnit.DAYS.between(LocalDate.parse(start), LocalDate.parse(end)) > 89) interval = "day"
        }
        CompositionLocalProvider(ru.omnicio.app.ui.spectrum.LocalSpectrumTabScrollTag provides "quotes-intervals") {
            ChoiceRow(listOf("Час", "День", "Неделя", "Месяц"), listOf("hour", "day", "week", "month").indexOf(interval)) { index ->
                interval = listOf("hour", "day", "week", "month")[index]
                if (interval == "hour" && ChronoUnit.DAYS.between(LocalDate.parse(start), LocalDate.parse(end)) > 89)
                    start = LocalDate.parse(end).minusDays(89).toString()
            }
        }
        WorkspaceRequestNotice(request)
        val parsed = remember(request.json, position.id) { request.json?.let { runCatching { parseCandles(it, position.id) } } }
        if (parsed?.isFailure == true) Text("Источник вернул противоречивые свечи. График не построен; повторите запрос.")
        parsed?.getOrNull()?.let { snapshot ->
            Text("${snapshot.unitLabel} · ${snapshot.start} — ${snapshot.end}", style = MaterialTheme.typography.bodySmall)
            Text("Источник: T‑Invest · ${dateText(snapshot.asOf)}", style = MaterialTheme.typography.bodySmall)
            snapshot.reason?.let { Text(it) }
            if (LocalWorkspacePreferences.current.value.hideHomeBalance) Text("Котировки скрыты режимом приватности.")
            else if (snapshot.candles.isEmpty()) Text("В выбранном периоде свечи не получены. Пропуски не заменяются нулевой ценой.")
            else {
                val anchor = selectedTime?.let { runCatching { Instant.parse(it) }.getOrNull() }
                val selected = anchor?.let { date -> snapshot.candles.indexOfLast { !Instant.parse(it.time).isAfter(date) } } ?: -1
                val chosen = snapshot.candles.getOrNull(selected)
                if (chosen != null) CandleDetails(chosen, snapshot.unitLabel)
                else Text("Коснитесь свечи, чтобы увидеть точные значения.")
                CandleSurface(snapshot.candles, selected) { selectedTime = snapshot.candles[it].time }
                FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { selectedTime = snapshot.candles[(if (selected < 0) snapshot.candles.lastIndex else selected - 1).coerceAtLeast(0)].time }) { Text("Предыдущая") }
                    TextButton(onClick = { selectedTime = null }) { Text("Сбросить") }
                    TextButton(onClick = { selectedTime = snapshot.candles[(selected + 1).coerceIn(0, snapshot.candles.lastIndex)].time }) { Text("Следующая") }
                }
                if (chosen != null && snapshot.candles.size > 35) DetailFold("Лупа выбранного интервала") {
                    WorkspaceGestureHint("quotes-magnifier", "Лупа рыночных свечей",
                        "Выбранная свеча и соседние интервалы показаны крупнее. Здесь отдельная шкала цены; точные числа и кнопки доступны без проведения по графику.")
                    val first = (selected - 3).coerceAtLeast(0)
                    val nearby = snapshot.candles.subList(first, (selected + 4).coerceAtMost(snapshot.candles.size))
                    Text("Увеличенный фрагмент; локальная шкала цены.", style = MaterialTheme.typography.bodySmall)
                    CandleSurface(nearby, selected - first) { selectedTime = nearby[it].time }
                }
                CandleValues(snapshot.candles, selected) { selectedTime = snapshot.candles[it].time }
            }
            if (snapshot.events.isNotEmpty()) DetailFold("События за период (${snapshot.events.size})") {
                Text("Совпадение времени не доказывает причину изменения цены.", style = MaterialTheme.typography.bodySmall)
                snapshot.events.forEach { event ->
                    TextButton(onClick = { selectedTime = event.optionalText("occurred_at") ?: event.optionalText("time") }) {
                        Text("${event.optionalText("title") ?: "Событие"} · ${dateText(event.optionalText("occurred_at") ?: event.optionalText("time"))}")
                    }
                }
            }
            SourceProvenance(snapshot.sources)
            TextButton(onClick = {
                onNavigate()
                askAnalyst(ChatContext(mode = "instrument", instrumentUid = position.id,
                    title = "${position.ticker ?: position.title} · ${snapshot.start} — ${snapshot.end}",
                    accountId = accountId, start = snapshot.start, end = snapshot.end))
            }, enabled = !request.showingPreviousQuery && !request.loading) { Text("Обсудить этот период") }
            request.json?.let { SaveResearchButton(it, "Котировки ${position.ticker ?: position.title}", position.id,
                snapshot.start, snapshot.end, "T‑Invest · MarketDataService.GetCandles", snapshot.asOf) }
        }
        TextButton(onClick = request.refresh, enabled = !request.loading) { Text(if (request.loading) "Получаем свечи…" else "Обновить котировки") }
    }
}

@Composable
private fun CandleSurface(candles: List<MarketCandle>, selected: Int, choose: (Int) -> Unit) {
    val low = candles.minOf { it.low }.toDouble(); val high = candles.maxOf { it.high }.toDouble()
    val callback by rememberUpdatedState(choose)
    Box(Modifier.fillMaxWidth().height(220.dp).testTag("market-candles")
        .semantics {
            contentDescription = "Рыночные свечи. Точная таблица доступна ниже. Выбрано ${selected + 1} из ${candles.size}."
            customActions = listOf(CustomAccessibilityAction("Предыдущая свеча") { callback((selected - 1).coerceAtLeast(0)); true },
                CustomAccessibilityAction("Следующая свеча") { callback((selected + 1).coerceAtMost(candles.lastIndex)); true })
        }
        .pointerInput(candles.size) { detectTapGestures { callback(historyBarIndex(it.x, size.width.toFloat(), candles.size)) } }
        .pointerInput(candles.size) { detectHorizontalDragGestures { change, _ -> change.consume(); callback(historyBarIndex(change.position.x, size.width.toFloat(), candles.size)) } }) {
        SpatialCandles(candles.map { SpatialCandle(it.open.toDouble(), it.high.toDouble(), it.low.toDouble(), it.close.toDouble()) },
            low, high, selected.takeIf { it >= 0 }, Modifier.fillMaxSize())
    }
    DataRow("Шкала цены", "${candles.minOf { it.low }.toPlainString()} — ${candles.maxOf { it.high }.toPlainString()}")
}

@Composable
private fun CandleDetails(candle: MarketCandle, unit: String) {
    Text(dateText(candle.time), style = MaterialTheme.typography.titleMedium)
    DataRow("Открытие / закрытие", "${candle.open.toPlainString()} / ${candle.close.toPlainString()} $unit")
    DataRow("Минимум / максимум", "${candle.low.toPlainString()} / ${candle.high.toPlainString()} $unit")
    DataRow("Объём", "${candle.volumeLots.toPlainString()} лотов")
    Text(if (candle.isComplete) "Свеча завершена" else "Текущий интервал ещё формируется", style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun CandleValues(candles: List<MarketCandle>, selected: Int, choose: (Int) -> Unit) {
    var page by rememberSaveable { mutableIntStateOf(0) }
    LaunchedEffect(selected) { if (selected >= 0) page = selected / 10 }
    val pages = ((candles.size + 9) / 10).coerceAtLeast(1)
    DetailFold("Точная таблица свечей") {
        val safePage = page.coerceIn(0, pages - 1)
        candles.indices.drop(safePage * 10).take(10).forEach { index ->
            val row = candles[index]
            TextButton(onClick = { choose(index) }, modifier = Modifier.fillMaxWidth().semantics { this.selected = index == selected }) {
                Text("${if (index == selected) "Выбрано · " else ""}${dateText(row.time)}\nО ${row.open.toPlainString()} · В ${row.high.toPlainString()} · Н ${row.low.toPlainString()} · З ${row.close.toPlainString()}")
            }
        }
        Row { TextButton(onClick = { page = safePage - 1 }, enabled = safePage > 0) { Text("Назад") }
            TextButton(onClick = { page = safePage + 1 }, enabled = safePage + 1 < pages) { Text("Далее") } }
    }
}
