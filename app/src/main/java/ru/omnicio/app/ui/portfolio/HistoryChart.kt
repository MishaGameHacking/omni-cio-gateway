package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.math.MathContext
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.delay
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.workspace.DetailFold
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences

internal data class HistoryMarker(val date: String, val label: String)

internal fun HistoryBar.title(): String {
    val format = DateTimeFormatter.ofPattern("d MMM yyyy", Russian)
    return if (start == end) start.format(format) else "${start.format(format)} — ${end.format(format)}"
}

@Composable
internal fun HistoryChart(
    points: List<HistoryPoint>, currency: String, markers: List<HistoryMarker> = emptyList(),
    selectionKey: String = currency, onSelection: (PortfolioPeriod?) -> Unit = {},
    controls: @Composable () -> Unit = {},
) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) {
        Notice("График скрыт режимом приватности."); controls(); return
    }
    val model = remember(points) { historyBars(points) }
    if (model == null) {
        Notice(if (points.isEmpty()) "За этот период пока нет сохранённых снимков стоимости." else "История содержит несовместимые значения. Повторите загрузку; пропуски не заменяются нулями.")
        controls(); return
    }
    var selectedStart by rememberSaveable(selectionKey) { mutableStateOf<String?>(null) }
    val selected = model.bars.indexOfFirst { it.start.toString() == selectedStart }
    val bar = model.bars.getOrNull(selected)
    val latest = model.source.coordinates.last().point
    val choose: (Int) -> Unit = { selectedStart = model.bars[it].start.toString() }
    val selectionCallback by rememberUpdatedState(onSelection)
    LaunchedEffect(bar?.period) {
        // Scrubbing is entirely local; request interval cash flows after selection settles.
        delay(350)
        selectionCallback(bar?.period)
    }
    Text("Стоимость портфеля", style = MaterialTheme.typography.titleMedium)
    Text("${decimalText(latest.value)} ${currencySymbol(currency)}", style = MaterialTheme.typography.headlineMedium,
        fontWeight = FontWeight.SemiBold)
    Notice("Последний снимок · ${dateText(latest.date)}")
    BarTooltip(model, selected, currency)
    BarCanvas(model, selected, currency, choose)
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(model.bars.first().start.format(DateTimeFormatter.ofPattern("dd.MM.yy")), style = MaterialTheme.typography.labelSmall)
        Text(model.bars.last().end.format(DateTimeFormatter.ofPattern("dd.MM.yy")), style = MaterialTheme.typography.labelSmall)
    }
    controls()
    BarNavigation(model, selected, choose) { selectedStart = null }
    HistoryStatistics(bar?.points ?: model.source.coordinates.map { it.point }, bar?.title(), currency)
    DetailFold("Подробнее о графике") {
        Notice("Один столбец — ${model.interval}. Высота показывает последний сохранённый баланс за интервал. Шкала начинается от нуля; отрицательные значения направлены вниз.")
        Notice("Стоимость меняется и при пополнениях или выводах. Её изменение не равно инвестиционной прибыли. Пустой интервал означает отсутствие наблюдений.")
        DataRow("Диапазон шкалы", "${decimalText(model.source.low)} — ${decimalText(model.source.high)} ${currencySymbol(currency)}")
        markers.forEach { Notice("${dateText(it.date)} · ${it.label}") }
        HistoryValues(model.source.coordinates, currency)
    }
}

@Composable
private fun BarTooltip(model: HistoryBars, selected: Int, currency: String) {
    val bar = model.bars.getOrNull(selected)
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val width = minOf(maxWidth, 224.dp)
        val x = if (selected < 0) 0.dp else ((maxWidth * ((selected + .5f) / model.bars.size)) - width / 2).coerceIn(0.dp, maxWidth - width)
        Surface(Modifier.width(width).offset(x = x), shape = RoundedCornerShape(12.dp),
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
private fun BarCanvas(model: HistoryBars, selected: Int, currency: String, choose: (Int) -> Unit) {
    val palette = LocalSpectrumPalette.current
    val outline = MaterialTheme.colorScheme.outlineVariant
    val accent = palette.cyan
    val selection = model.bars.getOrNull(selected)
    val index = if (selected < 0) model.bars.lastIndex else selected
    val callback by rememberUpdatedState(choose)
    val description = selection?.let { "${it.title()}: ${it.close?.value?.let { value -> decimalText(value) } ?: "нет наблюдений"} $currency" } ?: "Выберите столбец"
    Canvas(Modifier.fillMaxWidth().height(188.dp).testTag("history-bars")
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
        val top = 8.dp.toPx()
        val plotHeight = size.height - top * 2
        val zeroY = top + model.source.zero * plotHeight
        val step = size.width / model.bars.size
        val width = minOf(step * .72f, 28.dp.toPx())
        val span = model.source.high.subtract(model.source.low)
        for (level in 0..2) {
            val y = top + plotHeight * level / 2
            drawLine(outline.copy(alpha = .35f), Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
        }
        drawLine(outline, Offset(0f, zeroY), Offset(size.width, zeroY), 1.dp.toPx())
        model.bars.forEachIndexed { i, bar ->
            val x = (i + .5f) * step
            val close = bar.close
            if (i == selected) drawLine(accent.copy(alpha = .45f), Offset(x, 0f), Offset(x, size.height), 1.dp.toPx())
            if (close == null) {
                drawLine(outline, Offset(x - width / 4, zeroY), Offset(x + width / 4, zeroY), 2.dp.toPx())
            } else {
                val fraction = if (span.signum() == 0) model.source.zero else model.source.high.subtract(close.value).divide(span, MathContext.DECIMAL64).toFloat()
                val y = top + fraction * plotHeight
                val color = if (i == selected) accent else palette.blue
                if (close.value.signum() == 0) drawCircle(color, 2.dp.toPx(), Offset(x, zeroY))
                else drawRoundRect(Brush.verticalGradient(listOf(color, palette.violet.copy(alpha = .65f))),
                    Offset(x - width / 2, minOf(y, zeroY)), Size(width, kotlin.math.abs(zeroY - y)), CornerRadius(3.dp.toPx()))
            }
        }
    }
}

@Composable
private fun BarNavigation(model: HistoryBars, selected: Int, choose: (Int) -> Unit, reset: () -> Unit) {
    val index = if (selected < 0) model.bars.lastIndex else selected
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = { choose(index - 1) }, enabled = index > 0,
            modifier = Modifier.semantics { contentDescription = "Предыдущий столбец" }) { Text("‹", style = MaterialTheme.typography.headlineSmall) }
        TextButton(onClick = reset, enabled = selected >= 0, modifier = Modifier.weight(1f)) {
            Text(if (selected < 0) "Весь период" else "Сбросить выбор")
        }
        IconButton(onClick = { choose(index + 1) }, enabled = index < model.bars.lastIndex,
            modifier = Modifier.semantics { contentDescription = "Следующий столбец" }) { Text("›", style = MaterialTheme.typography.headlineSmall) }
    }
}

@Composable
private fun HistoryStatistics(points: List<HistoryPoint>, title: String?, currency: String) {
    Text(title ?: "За показанный период", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
    if (points.isEmpty()) { Notice("За этот интервал снимков нет. Это не нулевой баланс."); return }
    val change = historyChange(points)
    DataRow("Изменение стоимости", change?.let { (if (it.signum() > 0) "+" else "") + decimalText(it) + " " + currencySymbol(currency) } ?: "Один снимок")
    DataRow("Минимум / максимум", "${decimalText(points.minOf { it.value })} / ${decimalText(points.maxOf { it.value })} ${currencySymbol(currency)}")
    Notice("По ${points.size} сохранённым наблюдениям · ${dateText(points.last().date)}")
}

@Composable
private fun HistoryValues(data: List<HistoryCoordinate>, currency: String) {
    var page by remember(currency) { mutableIntStateOf(0) }
    val window = historyWindow(data.size, page)
    for (index in window.first until window.end) {
        val point = data[index].point
        DataRow(dateText(point.date), "${decimalText(point.value)} ${currencySymbol(currency)}")
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { page = window.page - 1 }, enabled = window.page > 0, modifier = Modifier.weight(1f)) { Text("Предыдущие") }
        TextButton(onClick = { page = window.page + 1 }, enabled = window.page + 1 < window.pages, modifier = Modifier.weight(1f)) { Text("Следующие") }
    }
}
