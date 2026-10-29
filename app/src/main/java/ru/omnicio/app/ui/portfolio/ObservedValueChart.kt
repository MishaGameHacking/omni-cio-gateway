package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import java.math.BigDecimal
import java.math.MathContext
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

/** The line connects observed bucket closes only; an empty bucket breaks it. */
@Composable
internal fun ObservedValueChart(points: List<HistoryPoint>, currency: String) {
    val bars = remember(points) { historyBars(points)?.bars.orEmpty() }
    var selected by remember(points) { mutableIntStateOf(bars.indexOfLast { it.close != null }) }
    if (bars.isEmpty()) { Text("За этот период нет сохранённых наблюдений"); return }
    val amounts = bars.mapNotNull { it.close?.value }
    val minimum = amounts.minOrNull() ?: BigDecimal.ZERO
    val maximum = amounts.maxOrNull() ?: BigDecimal.ZERO
    val margin = ((maximum - minimum) * BigDecimal("0.08")).max(maximum.abs() * BigDecimal("0.005")).max(BigDecimal.ONE)
    val low = minimum - margin
    val high = maximum + margin
    val span = high - low
    val positions = bars.map { bar -> bar.close?.let { ((high - it.value).divide(span, MathContext.DECIMAL64)).toFloat() } }
    val colors = MaterialTheme.colorScheme
    val accent = LocalSpectrumPalette.current.cyan
    val chosen = bars.getOrNull(selected)?.close
    Text(chosen?.let { dateText(it.date) + " · " + decimalText(it.value) + " " + currencySymbol(currency) }
        ?: "На выбранную дату наблюдения нет", style = MaterialTheme.typography.titleSmall)
    Row(Modifier.fillMaxWidth().height(200.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.widthIn(max = 76.dp).fillMaxHeight(), verticalArrangement = Arrangement.SpaceBetween) {
            Text(decimalText(high), style = MaterialTheme.typography.labelSmall)
            Text(currencySymbol(currency), style = MaterialTheme.typography.labelSmall)
            Text(decimalText(low), style = MaterialTheme.typography.labelSmall)
        }
        Canvas(Modifier.weight(1f).fillMaxHeight()
            .semantics { contentDescription = "Стоимость портфеля по сохранённым наблюдениям. " +
                (chosen?.let { dateText(it.date) + ": " + it.value.toPlainString() + " " + currency } ?: "Нет наблюдения") }
            .pointerInput(bars.size) {
                detectTapGestures { at -> selected = historyBarIndex(at.x, size.width.toFloat(), bars.size) }
            }
            .pointerInput(bars.size) {
                detectDragGestures(onDragStart = { at -> selected = historyBarIndex(at.x, size.width.toFloat(), bars.size) }) { change, _ ->
                    change.consume(); selected = historyBarIndex(change.position.x, size.width.toFloat(), bars.size)
                }
            }) {
            for (i in 0..4) {
                val y = size.height * i / 4f
                drawLine(colors.outlineVariant.copy(alpha = .55f), Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
            }
            val step = size.width / bars.size
            var segment = mutableListOf<Offset>()
            fun renderSegment() {
                if (segment.isEmpty()) return
                val line = Path().apply {
                    moveTo(segment.first().x, segment.first().y)
                    segment.drop(1).forEach { lineTo(it.x, it.y) }
                }
                if (segment.size > 1) {
                    val area = Path().apply {
                        addPath(line); lineTo(segment.last().x, size.height)
                        lineTo(segment.first().x, size.height); close()
                    }
                    drawPath(area, Brush.verticalGradient(listOf(accent.copy(alpha = .28f), accent.copy(alpha = .01f))))
                    drawPath(line, accent, style = Stroke(width = 2.dp.toPx()))
                }
                segment.forEach { drawCircle(accent, 2.5.dp.toPx(), it) }
                segment = mutableListOf()
            }
            positions.forEachIndexed { index, fraction ->
                if (fraction == null) renderSegment()
                else segment.add(Offset((index + .5f) * step, fraction.coerceIn(0f, 1f) * size.height))
            }
            renderSegment()
            positions.getOrNull(selected)?.let { y ->
                val x = (selected + .5f) * step
                drawLine(colors.onSurface.copy(alpha = .4f), Offset(x, 0f), Offset(x, size.height), 1.dp.toPx())
                drawCircle(colors.onSurface, 5.dp.toPx(), Offset(x, y * size.height))
                drawCircle(accent, 3.dp.toPx(), Offset(x, y * size.height))
            }
        }
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(bars.first().start.toString(), style = MaterialTheme.typography.labelSmall)
        Text(bars.last().end.toString(), style = MaterialTheme.typography.labelSmall)
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        TextButton({ selected = (selected - 1).coerceAtLeast(0) }, enabled = selected > 0) { Text("‹ Раньше") }
        TextButton({ selected = (selected + 1).coerceAtMost(bars.lastIndex) }, enabled = selected < bars.lastIndex) { Text("Позже ›") }
    }
    Text("Разрывы означают отсутствие наблюдений. Пополнения входят в стоимость, но не считаются доходом.",
        style = MaterialTheme.typography.bodySmall, color = colors.onSurfaceVariant)
}
