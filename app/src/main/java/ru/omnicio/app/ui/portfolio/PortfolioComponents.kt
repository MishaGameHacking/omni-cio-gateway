package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.math.BigDecimal
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumCard

internal val Moscow: ZoneId = ZoneId.of("Europe/Moscow")
internal val Russian: Locale = Locale.forLanguageTag("ru-RU")
internal fun decimalText(number: BigDecimal, scale: Int = 2): String = NumberFormat.getNumberInstance(Russian).apply {
    maximumFractionDigits = scale
    minimumFractionDigits = if (scale == 2) 2 else 0
}.format(number)
internal fun currencySymbol(currency: String): String = when (currency.uppercase(Locale.ROOT)) {
    "RUB" -> "₽"; "USD" -> "$"; "EUR" -> "€"; else -> currency.uppercase(Locale.ROOT)
}
internal fun MoneyAmount?.moneyText(signed: Boolean = false): String {
    if (this == null) return "—"
    val number = value.toBigDecimal()
    return (if (signed && number.signum() > 0) "+" else "") + decimalText(number) + " " + currencySymbol(currency)
}
internal fun ApiDecimal?.quantityText(): String = this?.toBigDecimal()?.let { decimalText(it, 8) } ?: "—"
internal fun ApiDecimal?.percentText(): String = this?.toBigDecimal()?.let { decimalText(it) + "%" } ?: "—"
internal fun dateText(value: String?, pattern: String = "dd.MM.yyyy HH:mm"): String = value?.let {
    runCatching { DateTimeFormatter.ofPattern(pattern, Russian).withZone(Moscow).format(Instant.parse(it)) }
        .getOrDefault(it.take(19))
} ?: "—"
internal fun brokerMoney(json: JSONObject?): MoneyAmount? = json?.let {
    val currency = it.optString("currency")
    if (currency.isBlank()) null else MoneyAmount(parseDecimal(it), currency.uppercase(Locale.ROOT))
}

@Composable
internal fun SignedAmount(amount: MoneyAmount?, percent: ApiDecimal? = null) {
    val sign = amount?.value?.toBigDecimal()?.signum() ?: percent?.toBigDecimal()?.signum() ?: 0
    val colors = MaterialTheme.colorScheme
    val tint = when {
        sign > 0 -> if (colors.background.luminance() < 0.5f) Color(0xFF42CE76) else Color(0xFF137D3B)
        sign < 0 -> colors.error
        else -> colors.onSurfaceVariant
    }
    Text(listOfNotNull(amount?.moneyText(true), percent?.percentText()).joinToString(" · ").ifBlank { "—" },
        color = tint, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.End)
}

@Composable
internal fun CompactCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    SpectrumCard(modifier.fillMaxWidth()) {
        Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
internal fun DataRow(title: String, value: String, modifier: Modifier = Modifier) {
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(modifier.fillMaxWidth()) {
        if (portfolioStackedLayout(maxWidth.value, fontScale)) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                Text(value, style = MaterialTheme.typography.bodyMedium)
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                Text(title, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium)
                Text(value, modifier = Modifier.weight(1f), textAlign = TextAlign.End, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
internal fun Notice(text: String) {
    Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant,
        style = MaterialTheme.typography.bodySmall, modifier = Modifier.fillMaxWidth())
}

@Composable
internal fun SectionHeading(text: String) {
    Text(text, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
}

@Composable
internal fun ChoiceRow(options: List<String>, selected: Int, onSelect: (Int) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEachIndexed { index, text ->
            FilterChip(selected = index == selected, onClick = { onSelect(index) },
                label = { Text(text, maxLines = 1, softWrap = false) })
        }
    }
}

@Composable
internal fun PositionLine(position: PortfolioPosition, onClick: () -> Unit) {
    val fontScale = LocalDensity.current.fontScale
    Surface(onClick = onClick, color = Color.Transparent, shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
        BoxWithConstraints(Modifier.fillMaxWidth().padding(vertical = 10.dp)) {
            val stacked = portfolioStackedLayout(maxWidth.value, fontScale)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Surface(shape = CircleShape, color = LocalSpectrumPalette.current.cardStrong, modifier = Modifier.size(38.dp)) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(position.ticker?.take(2) ?: "•", fontWeight = FontWeight.SemiBold, fontSize = 12.sp,
                                color = LocalSpectrumPalette.current.cyan)
                        }
                    }
                    PositionIdentity(position, Modifier.weight(1f), stacked)
                    if (!stacked) PositionAmounts(position, Modifier.widthIn(max = 132.dp))
                }
                if (stacked) PositionAmounts(position, Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun PositionIdentity(position: PortfolioPosition, modifier: Modifier, expanded: Boolean) {
    Column(modifier) {
        Text(position.title, maxLines = if (expanded) Int.MAX_VALUE else 2, overflow = TextOverflow.Ellipsis,
            style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
        Text(buildString {
            position.quantity?.let { append(it.quantityText()); append(if (position.instrumentType == "cash") " ${position.ticker.orEmpty()}" else " шт.") }
            if (position.blocked) append(" · Заблокировано")
        }, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun PositionAmounts(position: PortfolioPosition, modifier: Modifier) {
    Column(modifier, horizontalAlignment = Alignment.End) {
        Text(position.currentValue.moneyText(), fontWeight = FontWeight.Medium, style = MaterialTheme.typography.bodyMedium)
        position.expectedYieldAmount?.let { SignedAmount(it) }
    }
}

@Composable
internal fun PositionDetails(position: PortfolioPosition, close: () -> Unit) {
    InstrumentDetailsScreen(position, close)
}

@Composable
internal fun StructureChart(slices: List<ChartSlice>, center: String, caption: String) {
    val fractions = remember(slices) { portfolioFractions(slices) }
    if (fractions == null) {
        Notice("Нет сопоставимых данных для диаграммы. Некорректные доли не исключаются молча.")
        return
    }
    val spectrum = LocalSpectrumPalette.current
    val palette = listOf(spectrum.blue, spectrum.emerald, spectrum.violet, spectrum.amber, spectrum.rose, spectrum.cyan)
    val remainder = MaterialTheme.colorScheme.surfaceVariant
    val largeText = LocalDensity.current.fontScale >= 1.5f
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val diameter = minOf(maxWidth, 214.dp)
        Box(Modifier.fillMaxWidth().height(diameter + 16.dp), contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(diameter).semantics { contentDescription = "Структура: $caption. Все доли перечислены ниже." }) {
                val stroke = 11.dp.toPx()
                val radius = size.minDimension - stroke
                if (radius <= 0f) return@Canvas
                val origin = Offset((size.width - radius) / 2, (size.height - radius) / 2)
                drawArc(remainder, 0f, 360f, false, origin, Size(radius, radius), style = Stroke(stroke))
                var angle = -90f
                fractions.forEachIndexed { index, slice ->
                    val sweep = (slice.fraction * 360).toFloat()
                    val gap = if (fractions.size > 1) minOf(2f, sweep * 0.15f) else 0f
                    drawArc(palette[index % palette.size], angle, sweep - gap,
                        false, origin, Size(radius, radius), style = Stroke(stroke))
                    angle += sweep
                }
            }
            if (!largeText) StructureCaption(center, caption, Modifier.widthIn(max = diameter * 0.72f))
        }
    }
    if (largeText) StructureCaption(center, caption, Modifier.fillMaxWidth())
    fractions.forEach { item -> DataRow(item.title, decimalText(BigDecimal.valueOf(item.fraction * 100)) + "%") }
}

@Composable
private fun StructureCaption(center: String, caption: String, modifier: Modifier) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(center, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center)
    }
}

@Composable
internal fun HistoryChart(points: List<HistoryPoint>, currency: String) {
    if (points.size < 2) {
        Notice(if (points.isEmpty()) "За этот период пока нет сохранённых снимков стоимости." else "Получен первый снимок. График появится после следующего измерения.")
        return
    }
    val geometry = remember(points) { portfolioHistory(points) }
    if (geometry == null) {
        Notice("Историю нельзя корректно отобразить: проверьте даты, повторные наблюдения и числовые данные. Пропуски не заменены нулями.")
        return
    }
    val data = geometry.coordinates
    val accent = LocalSpectrumPalette.current.blue
    val outline = MaterialTheme.colorScheme.outlineVariant
    Text(decimalText(data.last().point.value) + " " + currencySymbol(currency), fontWeight = FontWeight.Bold)
    Canvas(Modifier.fillMaxWidth().height(170.dp).semantics {
        contentDescription = "Стоимость портфеля: ${data.size} сохранённых снимков T-Invest. Значения доступны под графиком."
    }) {
        if (size.width < 1f || size.height < 1f) return@Canvas
        val zero = geometry.zero * size.height
        drawLine(outline, Offset(0f, zero), Offset(size.width, zero), 1.dp.toPx())
        val width = minOf(size.width, (size.width / (data.size * 1.5f)).coerceIn(1f, 22.dp.toPx()))
        data.forEach { coordinate ->
            val x = coordinate.x * (size.width - width)
            val y = coordinate.y * size.height
            drawRect(accent, Offset(x, minOf(y, zero)), Size(width, kotlin.math.abs(zero - y)))
        }
    }
    DataRow(dateText(data.first().point.date, "dd.MM.yy HH:mm"), dateText(data.last().point.date, "dd.MM.yy HH:mm"))
    Notice("Это фактически сохранённые снимки, не восстановленная история до подключения. Пополнения и выводы также изменяют стоимость портфеля.")
    HistoryValues(data, currency)
}

@Composable
private fun HistoryValues(data: List<HistoryCoordinate>, currency: String) {
    var expanded by remember(currency) { mutableStateOf(false) }
    var page by remember(currency) { mutableIntStateOf(0) }
    TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "Скрыть значения графика" else "Значения графика") }
    if (!expanded) return
    val window = historyWindow(data.size, page)
    for (index in window.first until window.end) {
        val point = data[index].point
        DataRow(dateText(point.date), decimalText(point.value) + " " + currencySymbol(currency))
    }
    Notice("Показаны ${window.first + 1}–${window.end} из ${data.size} снимков.")
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { page = window.page - 1 }, enabled = window.page > 0, modifier = Modifier.weight(1f)) { Text("Предыдущие") }
        TextButton(onClick = { page = window.page + 1 }, enabled = window.page + 1 < window.pages, modifier = Modifier.weight(1f)) { Text("Следующие") }
    }
}