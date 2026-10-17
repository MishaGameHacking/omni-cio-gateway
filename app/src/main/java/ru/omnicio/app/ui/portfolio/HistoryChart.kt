package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.delay
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumRangeSlider
import ru.omnicio.app.ui.spectrum.SpectrumIconButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.workspace.DetailFold
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import ru.omnicio.app.ui.spatial.SpatialBars
import ru.omnicio.app.ui.spatial.SpatialChartGuides
import java.time.LocalDate

internal data class HistoryMarker(val date: String, val label: String)

internal fun HistoryBar.title(): String {
    val format = DateTimeFormatter.ofPattern("d MMM yyyy", Russian)
    return if (start == end) start.format(format) else "${start.format(format)} — ${end.format(format)}"
}

@Composable
internal fun HistoryChart(
    points: List<HistoryPoint>, currency: String, markers: List<HistoryMarker> = emptyList(),
    selectionKey: String = currency, onSelection: (PortfolioPeriod?) -> Unit = {},
    initialSelectedDate: String? = null,
    initialSelectedInstant: String? = null,
    sourceResolution: String? = null,
    controls: @Composable () -> Unit = {},
) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) {
        Notice("График скрыт режимом приватности."); controls(); return
    }
    var grouping by rememberSaveable(selectionKey.substringBefore(':')) { mutableIntStateOf(0) }
    ChoiceRow(listOf("Авто", "Дни", "Недели", "Месяцы"), grouping) { grouping = it }
    val model = remember(points, grouping) { historyBars(points, listOf("auto", "day", "week", "month")[grouping]) }
    if (model == null) {
        Notice(if (points.isEmpty()) "За этот период пока нет сохранённых снимков стоимости." else "Для выбранного шага слишком много интервалов либо история содержит несовместимые значения. Выберите авто/месяцы или сузьте период; пропуски не заменяются нулями.")
        controls(); return
    }
    var selectedStart by rememberSaveable(selectionKey.substringBefore(':'), initialSelectedDate) { mutableStateOf(initialSelectedDate) }
    var selectedObservation by rememberSaveable(selectionKey.substringBefore(':'), initialSelectedInstant) { mutableStateOf(initialSelectedInstant) }
    val anchor = selectedStart?.let { runCatching { LocalDate.parse(it) }.getOrNull() }
    val selected = model.bars.indexOfFirst { anchor != null && !anchor.isBefore(it.start) && !anchor.isAfter(it.end) }
    val bar = model.bars.getOrNull(selected)
    var rangeStart by rememberSaveable(selectionKey) { mutableStateOf<String?>(null) }
    var rangeEnd by rememberSaveable(selectionKey) { mutableStateOf<String?>(null) }
    val selectedRange = if (rangeStart != null && rangeEnd != null) PortfolioPeriod(rangeStart, rangeEnd) else null
    val latest = model.source.coordinates.last().point
    val choose: (Int) -> Unit = { index -> model.bars.getOrNull(index)?.let {
        selectedStart = it.start.toString(); selectedObservation = null; rangeStart = null; rangeEnd = null
    } }
    val selectionCallback by rememberUpdatedState(onSelection)
    LaunchedEffect(bar?.period, selectedRange) {
        // Scrubbing is entirely local; request interval cash flows after selection settles.
        delay(350)
        selectionCallback(selectedRange ?: bar?.period)
    }
    Text("Стоимость портфеля", style = MaterialTheme.typography.titleMedium)
    Text("${decimalText(latest.value)} ${currencySymbol(currency)}", style = MaterialTheme.typography.headlineMedium,
        fontWeight = FontWeight.SemiBold)
    Notice("Последний снимок · ${dateText(latest.date)}")
    selectedObservation?.let { timestamp ->
        val exact = model.source.coordinates.firstOrNull { sameHistoryInstant(it.point.date, timestamp) }?.point
        Text("Точное наблюдение по ссылке", style = MaterialTheme.typography.titleMedium)
        Text(dateText(timestamp, "dd.MM.yyyy HH:mm:ss"), style = MaterialTheme.typography.bodyMedium)
        if (exact != null) DataRow("Зафиксированный баланс", "${exact.value.toPlainString()} ${currencySymbol(currency)}")
        else Notice("Наблюдение с этим точным моментом не найдено в полученной выборке. Другая запись этого дня не подставляется. Возможно, детальная история уже вышла из срока хранения; проверьте источник и диапазон.")
        if (sourceResolution in setOf("intraday", "hour", "day")) Notice("Частота исходного наблюдения: " + when (sourceResolution) {
            "intraday" -> "внутри дня"; "hour" -> "часовая"; else -> "дневная"
        })
        Notice("Столбик ниже показывает последнее наблюдение своего интервала; оно может отличаться от точной записи по ссылке.")
    }
    BarTooltip(model, selected, currency)
    HistoryBarPlot(model, selected, currency, choose)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(model.bars.first().start.format(DateTimeFormatter.ofPattern("dd.MM.yy")), style = MaterialTheme.typography.labelSmall)
        Text(model.bars.last().end.format(DateTimeFormatter.ofPattern("dd.MM.yy")), style = MaterialTheme.typography.labelSmall)
    }
    controls()
    BarNavigation(model, selected, choose) { selectedStart = null; selectedObservation = null; rangeStart = null; rangeEnd = null }
    if (model.bars.size > 1) HistoryRangeSelector(model, selectedRange, selectionKey) { rangeStart = it?.start; rangeEnd = it?.end }
    val visiblePoints = if (selectedRange == null) bar?.points ?: model.source.coordinates.map { it.point }
        else model.bars.filter { !it.end.isBefore(LocalDate.parse(rangeStart)) && !it.start.isAfter(LocalDate.parse(rangeEnd)) }.flatMap { it.points }
    HistoryStatistics(visiblePoints, selectedRange?.let { "${it.start} — ${it.end}" } ?: bar?.title(), currency)
    if (bar != null && model.bars.size > 35) DetailFold("Лупа выбранных дат") {
        ru.omnicio.app.ui.workspace.WorkspaceGestureHint("chart-magnifier", "Лупа графика", "Выберите дату, чтобы рассмотреть соседние наблюдения. Высоты сохраняют общую денежную шкалу; кнопки дат заменяют жест.")
        val first = (selected - 3).coerceAtLeast(0)
        val slice = model.bars.subList(first, (selected + 4).coerceAtMost(model.bars.size))
        Text("Увеличенный фрагмент. Высоты используют общую шкалу стоимости.", style = MaterialTheme.typography.bodySmall)
        SpatialBars(slice.map { it.close?.value?.toDouble() }, model.source.low.toDouble(), model.source.high.toDouble(),
            selected - first, Modifier.fillMaxWidth().height(150.dp))
        slice.forEachIndexed { offset, item -> TextButton(onClick = { choose(first + offset) }) {
            Text("${item.title()} · ${item.close?.let { decimalText(it.value) } ?: "Нет наблюдений"}")
        } }
    }
    if (markers.isNotEmpty()) DetailFold("Подтверждённые события по датам") {
        markers.forEach { marker ->
            val date = runCatching { java.time.Instant.parse(marker.date).atZone(Moscow).toLocalDate() }.getOrNull()
                ?: runCatching { LocalDate.parse(marker.date.take(10)) }.getOrNull()
            val index = model.bars.indexOfFirst { date != null && !date.isBefore(it.start) && !date.isAfter(it.end) }
            TextButton(onClick = { selectedStart = date?.toString(); selectedObservation = null; rangeStart = null; rangeEnd = null }, enabled = index >= 0) {
                Text("${dateText(marker.date)} · ${marker.label}${if (index < 0) " · вне графика" else ""}")
            }
        }
        Notice("Это события источников, а не автоматически установленные причины изменения баланса.")
    }
    DetailFold("Подробнее о графике") {
        Notice("Один столбец — ${model.interval}. Высота показывает последний сохранённый баланс за интервал. Шкала начинается от нуля; отрицательные значения направлены вниз.")
        Notice("Точки у нулевой линии отмечают нулевые и очень малые суммы. Точное значение доступно по нажатию.")
        Notice("Стоимость меняется и при пополнениях или выводах. Её изменение не равно инвестиционной прибыли. Пустой интервал означает отсутствие наблюдений.")
        DataRow("Диапазон шкалы", "${decimalText(model.source.low)} — ${decimalText(model.source.high)} ${currencySymbol(currency)}")
        markers.forEach { Notice("${dateText(it.date)} · ${it.label}") }
        HistoryValues(model.source.coordinates, currency, selectedStart, selectedObservation) { date ->
            selectedStart = java.time.Instant.parse(date).atZone(Moscow).toLocalDate().toString()
            selectedObservation = java.time.Instant.parse(date).toString(); rangeStart = null; rangeEnd = null
        }
    }
}

@Composable
private fun BarTooltip(model: HistoryBars, selected: Int, currency: String) {
    val bar = model.bars.getOrNull(selected)
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val width = minOf(maxWidth, 224.dp)
        val x = if (selected < 0) 0.dp else ((maxWidth * ((selected + .5f) / model.bars.size)) - width / 2).coerceIn(0.dp, maxWidth - width)
        ru.omnicio.app.ui.spatial.SpatialSurface(Modifier.width(width).offset(x = x).semantics {
            contentDescription = bar?.let { "Выбранный интервал: ${it.start} — ${it.end}" } ?: "Выбор интервала"
        }, kind = ru.omnicio.app.ui.spatial.SpatialSurfaceKind.Chip,
            color = MaterialTheme.colorScheme.surfaceContainerHigh) {
            Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                Text(bar?.title() ?: "Нажмите на столбец", style = MaterialTheme.typography.bodySmall)
                Text(if (bar == null) "Детали появятся ниже" else bar.close?.let { "${decimalText(it.value)} ${currencySymbol(currency)}" } ?: "Нет наблюдений",
                    fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun HistoryBarPlot(model: HistoryBars, selected: Int, currency: String, choose: (Int) -> Unit) {
    val palette = LocalSpectrumPalette.current
    val outline = MaterialTheme.colorScheme.outlineVariant
    val accent = palette.cyan
    val selection = model.bars.getOrNull(selected)
    val index = if (selected < 0) model.bars.lastIndex else selected
    val callback by rememberUpdatedState(choose)
    val description = selection?.let { "${it.title()}: ${it.close?.value?.let { value -> decimalText(value) } ?: "нет наблюдений"} $currency" } ?: "Выберите столбец"
    Box(Modifier.fillMaxWidth().height(188.dp).testTag("history-bars")
        .semantics {
            contentDescription = "Столбчатый график стоимости. $description"
            customActions = listOf(
                CustomAccessibilityAction("Предыдущий столбец") { callback((index - 1).coerceAtLeast(0)); true },
                CustomAccessibilityAction("Следующий столбец") { callback((index + 1).coerceAtMost(model.bars.lastIndex)); true },
            )
        }
        .pointerInput(model.bars.size) { detectTapGestures { callback(historyBarIndex(it.x, size.width.toFloat(), model.bars.size)) } }
        .pointerInput(model.bars.size) { detectHorizontalDragGestures { change, _ ->
            change.consume(); callback(historyBarIndex(change.position.x, size.width.toFloat(), model.bars.size))
        } }) {
        SpatialBars(model.bars.map { it.close?.value?.toDouble() }, model.source.low.toDouble(), model.source.high.toDouble(),
            selected.takeIf { it >= 0 }, Modifier.fillMaxSize().padding(vertical = 8.dp), listOf(palette.blue))
        SpatialChartGuides(model.bars.size, model.source.zero,
            model.bars.indices.filter { model.bars[it].close == null }.toSet(), selected.takeIf { it >= 0 },
            Modifier.fillMaxSize().padding(vertical = 8.dp), gridColor = outline.copy(alpha = .35f), selectedColor = accent)
    }
}

@Composable
private fun HistoryRangeSelector(model: HistoryBars, selected: PortfolioPeriod?, selectionKey: String,
    onSelect: (PortfolioPeriod?) -> Unit) {
    var draftStart by rememberSaveable(selectionKey, selected?.start) { mutableStateOf(selected?.start ?: model.bars.first().start.toString()) }
    var draftEnd by rememberSaveable(selectionKey, selected?.end) { mutableStateOf(selected?.end ?: model.bars.last().end.toString()) }
    val indices = historyRangeIndices(model.bars, draftStart, draftEnd)
    val commit = {
        val current = historyRangeIndices(model.bars, draftStart, draftEnd)
        onSelect(PortfolioPeriod(model.bars[current.first].start.toString(), model.bars[current.last].end.toString()))
    }
    DetailFold("Выбрать две границы") {
        ru.omnicio.app.ui.workspace.WorkspaceGestureHint("history-range", "Два ограничителя периода",
            "Проведите каждый ограничитель до нужной даты. Точные границы видны над дорожкой; календарь и кнопка ниже доступны без жестов.")
        Text("${model.bars[indices.first].start} — ${model.bars[indices.last].end}", Modifier.testTag("history-range-dates"))
        SpectrumRangeSlider(value = indices.first.toFloat()..indices.last.toFloat(), onValueChange = { value ->
            val first = value.start.toInt().coerceIn(0, model.bars.lastIndex)
            val last = value.endInclusive.toInt().coerceIn(first, model.bars.lastIndex)
            draftStart = model.bars[first].start.toString(); draftEnd = model.bars[last].end.toString()
        }, valueRange = 0f..model.bars.lastIndex.toFloat(), steps = (model.bars.size - 2).coerceAtLeast(0),
            onValueChangeFinished = commit, startDescription = "Начало периода: ${model.bars[indices.first].start}",
            endDescription = "Конец периода: ${model.bars[indices.last].end}",
            modifier = Modifier.fillMaxWidth().testTag("history-range-selector").semantics { contentDescription = "Границы выбранного периода" })
        TextButton(onClick = commit) { Text("Показать статистику диапазона") }
        if (selected != null) TextButton(onClick = { onSelect(null) }) { Text("Сбросить диапазон") }
        Text("Запрос выполняется после отпускания границы. Точные даты можно выбрать в календаре периода.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun BarNavigation(model: HistoryBars, selected: Int, choose: (Int) -> Unit, reset: () -> Unit) {
    val index = if (selected < 0) model.bars.lastIndex else selected
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        SpectrumIconButton(SpectrumSymbol.Back, "Предыдущий столбец", { choose(index - 1) }, enabled = index > 0,
            modifier = Modifier.testTag("history-selection-previous"))
        TextButton(onClick = reset, enabled = selected >= 0, modifier = Modifier.weight(1f).testTag("history-selection-reset")) {
            Text(if (selected < 0) "Весь период" else "Сбросить выбор")
        }
        SpectrumIconButton(SpectrumSymbol.Forward, "Следующий столбец", { choose(index + 1) }, enabled = index < model.bars.lastIndex,
            modifier = Modifier.testTag("history-selection-next"))
    }
}

@Composable
private fun HistoryStatistics(points: List<HistoryPoint>, title: String?, currency: String) {
    Text(title ?: "За показанный период", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    if (points.isEmpty()) { Notice("За этот интервал снимков нет. Это не нулевой баланс."); return }
    if (points.size == 1) {
        Notice("Один снимок · ${dateText(points.single().date)}. Для сравнения нужен следующий снимок.")
        return
    }
    val change = historyChange(points)
    DataRow("Изменение стоимости", change?.let { (if (it.signum() > 0) "+" else "") + decimalText(it) + " " + currencySymbol(currency) } ?: "Один снимок")
    val low = points.minOf { it.value }
    val high = points.maxOf { it.value }
    if (low.compareTo(high) != 0) DataRow("Минимум / максимум", "${decimalText(low)} / ${decimalText(high)} ${currencySymbol(currency)}")
    Notice("Снимков: ${points.size} · ${dateText(points.last().date)}")
}

@Composable
private fun HistoryValues(data: List<HistoryCoordinate>, currency: String, selectedDate: String?, selectedInstant: String?, onSelect: (String) -> Unit) {
    var page by rememberSaveable(currency) { mutableIntStateOf(0) }
    LaunchedEffect(selectedDate, selectedInstant) {
        val index = if (selectedInstant != null) data.indexOfFirst { sameHistoryInstant(it.point.date, selectedInstant) }
        else data.indexOfFirst { java.time.Instant.parse(it.point.date).atZone(Moscow).toLocalDate().toString() == selectedDate }
        if (index >= 0) page = index / 10
    }
    val window = historyWindow(data.size, page)
    for (index in window.first until window.end) {
        val point = data[index].point
        val selected = selectedInstant?.let { sameHistoryInstant(point.date, it) } == true
        TextButton(onClick = { onSelect(point.date) }, modifier = Modifier.fillMaxWidth().testTag("history-observation-$index")
            .semantics { this.selected = selected }) {
            Text("${if (selected) "Выбрано · " else ""}${dateText(point.date, "dd.MM.yyyy HH:mm:ss")} · ${point.value.toPlainString()} ${currencySymbol(currency)}")
        }
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { page = window.page - 1 }, enabled = window.page > 0, modifier = Modifier.weight(1f)) { Text("Предыдущие") }
        TextButton(onClick = { page = window.page + 1 }, enabled = window.page + 1 < window.pages, modifier = Modifier.weight(1f)) { Text("Следующие") }
    }
}

internal fun sameHistoryInstant(first: String, second: String): Boolean = runCatching {
    java.time.Instant.parse(first) == java.time.Instant.parse(second)
}.getOrDefault(false)

