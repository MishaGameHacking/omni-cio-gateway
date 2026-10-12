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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
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
        sign > 0 -> if (colors.background == Color(0xFF111111)) Color(0xFF42CE76) else Color(0xFF137D3B)
        sign < 0 -> colors.error
        else -> colors.onSurfaceVariant
    }
    Text(listOfNotNull(amount?.moneyText(true), percent?.percentText()).joinToString(" · ").ifBlank { "—" },
        color = tint, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.End)
}

@Composable
internal fun CompactCard(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
internal fun DataRow(title: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
        Text(title, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium)
        Text(value, modifier = Modifier.weight(1f), textAlign = TextAlign.End, style = MaterialTheme.typography.bodyMedium)
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
    Surface(onClick = onClick, color = Color.Transparent, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant, modifier = Modifier.size(38.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Text(position.ticker?.take(2) ?: "•", fontWeight = FontWeight.SemiBold, fontSize = 12.sp)
                }
            }
            Column(Modifier.weight(1f)) {
                Text(position.title, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium)
                Text(buildString {
                    position.quantity?.let { append(it.quantityText()); append(if (position.instrumentType == "cash") " ${position.ticker.orEmpty()}" else " шт.") }
                    if (position.blocked) append(" · Заблокировано")
                }, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            Column(Modifier.widthIn(max = 132.dp), horizontalAlignment = Alignment.End) {
                Text(position.currentValue.moneyText(), fontWeight = FontWeight.Medium, fontSize = 14.sp)
                position.expectedYieldAmount?.let { SignedAmount(it) }
            }
        }
    }
}

@Composable
internal fun PositionDetails(position: PortfolioPosition, close: () -> Unit) {
    AlertDialog(onDismissRequest = close, title = { Text(position.title) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                DataRow("Тикер", position.ticker ?: "—")
                DataRow("Количество, шт.", position.quantity.quantityText())
                DataRow("Стоимость позиции", position.currentValue.moneyText())
                DataRow("Текущая цена за единицу", position.currentPrice.moneyText())
                DataRow("Средняя цена", position.averagePrice.moneyText())
                DataRow("Результат позиции", position.expectedYieldAmount.moneyText(true))
                DataRow("За день", position.dailyYieldAmount.moneyText(true))
                DataRow("НКД на одну облигацию", position.currentNkd.moneyText())
                DataRow("Заблокированное количество", position.blockedQuantity.quantityText())
                DataRow("Блокировка на бирже", if (position.blocked) "Да" else "Нет")
                DataRow("ISIN", position.isin ?: "—")
                DataRow("Биржа", position.exchange ?: "—")
                DataRow("Отрасль", position.sector ?: "Не указана API")
                DataRow("Идентификатор", position.id)
                Notice("«—» означает, что значение не получено или не может быть корректно рассчитано. Цены и результаты показаны в валютах, возвращённых API. Количество не переводится в лоты.")
            }
        }, confirmButton = { TextButton(onClick = close) { Text("Закрыть") } })
}

internal data class ChartSlice(val title: String, val weight: Float)

@Composable
internal fun StructureChart(slices: List<ChartSlice>, center: String, caption: String) {
    val positive = slices.filter { it.weight > 0 && it.weight.isFinite() }
    val total = positive.sumOf { it.weight.toDouble() }.toFloat()
    val base = MaterialTheme.colorScheme.primary
    val remainder = MaterialTheme.colorScheme.surfaceVariant
    if (total <= 0f) {
        Notice("Нет сопоставимых данных для диаграммы.")
        return
    }
    val palette = listOf(base, Color(0xFF43A78E), Color(0xFFB694E2), Color(0xFFE0A95E), Color(0xFFDD778C), Color(0xFF73BDCF))
    Box(Modifier.fillMaxWidth().height(230.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(214.dp).semantics { contentDescription = caption }) {
            val stroke = 11.dp.toPx()
            val radius = size.minDimension - stroke
            val origin = Offset((size.width - radius) / 2, (size.height - radius) / 2)
            drawArc(remainder, 0f, 360f, false, origin, Size(radius, radius), style = Stroke(stroke))
            var angle = -90f
            positive.forEachIndexed { index, slice ->
                val sweep = slice.weight / total * 360f
                drawArc(palette[index % palette.size], angle, (sweep - if (positive.size > 1) 2f else 0f).coerceAtLeast(0f),
                    false, origin, Size(radius, radius), style = Stroke(stroke))
                angle += sweep
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.widthIn(max = 168.dp)) {
            Text(center, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center)
        }
    }
    positive.forEach { item -> DataRow(item.title, decimalText(BigDecimal.valueOf((item.weight / total * 100).toDouble())) + "%") }
}

internal data class HistoryPoint(val date: String, val value: BigDecimal)

@Composable
internal fun HistoryChart(points: List<HistoryPoint>, currency: String) {
    if (points.size < 2) {
        Notice(if (points.isEmpty()) "За этот период пока нет сохранённых снимков стоимости." else "Получен первый снимок. График появится после следующего измерения.")
        return
    }
    val values = points.map { it.value.toDouble() }
    val high = (values.maxOrNull() ?: 0.0).coerceAtLeast(0.0)
    val low = (values.minOrNull() ?: 0.0).coerceAtMost(0.0)
    val span = (high - low).takeIf { it > 0.0 } ?: 1.0
    val timestamps = points.map { runCatching { Instant.parse(it.date).toEpochMilli() }.getOrDefault(0L) }
    val duration = (timestamps.last() - timestamps.first()).coerceAtLeast(1L)
    val accent = MaterialTheme.colorScheme.primary
    val outline = MaterialTheme.colorScheme.outlineVariant
    Text(decimalText(points.last().value) + " " + currencySymbol(currency), fontWeight = FontWeight.Bold)
    Canvas(Modifier.fillMaxWidth().height(170.dp).semantics { contentDescription = "Стоимость портфеля по сохранённым снимкам T-Invest" }) {
        val zero = (high / span * size.height).toFloat()
        drawLine(outline, Offset(0f, zero), Offset(size.width, zero), 1.dp.toPx())
        val width = (size.width / (points.size * 1.5f)).coerceIn(1f, 22.dp.toPx())
        points.forEachIndexed { index, _ ->
            val x = ((timestamps[index] - timestamps.first()).toDouble() / duration * (size.width - width)).toFloat()
            val y = ((high - values[index]) / span * size.height).toFloat()
            drawRect(accent, Offset(x, minOf(y, zero)), Size(width, kotlin.math.abs(zero - y).coerceAtLeast(1f)))
        }
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(dateText(points.first().date, "dd.MM.yy HH:mm"), style = MaterialTheme.typography.labelSmall)
        Text(dateText(points.last().date, "dd.MM.yy HH:mm"), style = MaterialTheme.typography.labelSmall)
    }
    Notice("Это фактически сохранённые снимки, не восстановленная история до подключения. Пополнения и выводы также изменяют стоимость портфеля.")
}
