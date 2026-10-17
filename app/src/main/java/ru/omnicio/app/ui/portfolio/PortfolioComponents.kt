package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import ru.omnicio.app.ui.workspace.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
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
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.spectrum.SpectrumTabs

internal val Moscow: ZoneId = ZoneId.of("Europe/Moscow")
internal val Russian: Locale = Locale.forLanguageTag("ru-RU")
internal fun decimalText(number: BigDecimal, scale: Int = 2): String = NumberFormat.getNumberInstance(Russian).apply {
    maximumFractionDigits = scale
    minimumFractionDigits = if (scale == 2) 2 else 0
}.format(number)
internal fun currencySymbol(currency: String): String = when (currency.uppercase(Locale.ROOT)) {
    "RUB" -> "₽"; "USD" -> "$"; "EUR" -> "€"; else -> currency.uppercase(Locale.ROOT)
}
@Composable
internal fun MoneyAmount?.moneyText(signed: Boolean = false): String {
    if (ru.omnicio.app.ui.workspace.LocalWorkspacePreferences.current.value.hideHomeBalance) return "•••"
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
    if (ru.omnicio.app.ui.workspace.LocalWorkspacePreferences.current.value.hideHomeBalance) { Text("•••"); return }
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
                Text(ru.omnicio.app.ui.workspace.PrivateValue(value), style = MaterialTheme.typography.bodyMedium)
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                Text(title, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium)
                Text(ru.omnicio.app.ui.workspace.PrivateValue(value), modifier = Modifier.weight(1f), textAlign = TextAlign.End, style = MaterialTheme.typography.bodyMedium)
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
    SpectrumTabs(options, selected, onSelect)
}

@Composable
internal fun PositionLine(position: PortfolioPosition, total: MoneyAmount? = null, accountName: String? = null, onClick: () -> Unit) {
    val fontScale = LocalDensity.current.fontScale
    Surface(onClick = onClick, color = Color.Transparent, shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).semantics(mergeDescendants = true) {}) {
        BoxWithConstraints(Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
            val stacked = portfolioStackedLayout(maxWidth.value, fontScale)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    val symbol = when (position.instrumentType) {
                        "cash", "currency", "etf" -> SpectrumSymbol.Allocation
                        "bond" -> SpectrumSymbol.Sources
                        "share" -> SpectrumSymbol.Market
                        else -> SpectrumSymbol.Portfolio
                    }
                    SpectrumIcon(symbol, Modifier.size(30.dp), selected = false, tile = false, motionAllowed = false)
                    PositionIdentity(position, Modifier.weight(1f), stacked)
                    if (!stacked) PositionAmounts(position, Modifier.widthIn(max = 132.dp), total)
                }
                if (accountName != null) Text(accountName, style = MaterialTheme.typography.bodySmall)
                if (stacked) PositionAmounts(position, Modifier.fillMaxWidth(), total)
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
            if (position.instrumentType != "cash") position.ticker?.takeIf { it.isNotBlank() }?.let { append(it); append(" · ") }

            if (position.blocked) append(" · Заблокировано")
        }, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun PositionAmounts(position: PortfolioPosition, modifier: Modifier, total: MoneyAmount?) {
    Column(modifier, horizontalAlignment = Alignment.End) {
        Text(position.currentValue.moneyText(), fontWeight = FontWeight.Medium, style = MaterialTheme.typography.bodyMedium)
        val value = position.currentValue
        if (value != null && total != null && value.currency == total.currency && total.value.toBigDecimal().signum() > 0 && value.value.toBigDecimal().signum() >= 0) {
            val share = value.value.toBigDecimal().multiply(BigDecimal(100)).divide(total.value.toBigDecimal(), 1, java.math.RoundingMode.HALF_UP)
            Text(ru.omnicio.app.ui.workspace.PrivateValue("${decimalText(share, 1)}% портфеля"), style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
internal fun PositionDetails(position: PortfolioPosition, close: () -> Unit, accountName: String? = null) {
    InstrumentDetailsScreen(position, close, accountName)
}

@Composable
internal fun StructureChart(slices: List<ChartSlice>, center: String, caption: String) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Notice("Структура скрыта режимом приватности."); return }
    val fractions = remember(slices) { portfolioFractions(slices) }
    if (fractions == null) {
        Notice("Нет сопоставимых данных для диаграммы. Некорректные доли не исключаются молча.")
        return
    }
    val spectrum = LocalSpectrumPalette.current
    val palette = listOf(spectrum.blue, spectrum.emerald, spectrum.violet, spectrum.amber, spectrum.rose, spectrum.cyan)
    if (fractions.size > 6) {
        fractions.sortedByDescending { it.fraction }.forEachIndexed { index, item ->
            DataRow(item.title, "${decimalText(BigDecimal.valueOf(item.fraction * 100))}%")
            ru.omnicio.app.ui.spectrum.SpectrumProgressBar(item.fraction.toFloat(), accent = palette[index % palette.size])
        }
        return
    }
    val remainder = MaterialTheme.colorScheme.surfaceVariant
    val largeText = LocalDensity.current.fontScale >= 1.5f
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val diameter = minOf(maxWidth, 208.dp)
        Box(Modifier.fillMaxWidth().height(diameter + 16.dp), contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(diameter).semantics { contentDescription = "Структура: $caption. Все доли перечислены ниже." }) {
                val stroke = 18.dp.toPx()
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
            if (!largeText) StructureCaption(center, caption, Modifier.widthIn(max = diameter * 0.68f))
        }
    }
    if (largeText) StructureCaption(center, caption, Modifier.fillMaxWidth())
    fractions.forEachIndexed { index, item ->
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Box(Modifier.size(8.dp).background(palette[index % palette.size], CircleShape))
            DataRow(item.title, decimalText(BigDecimal.valueOf(item.fraction * 100)) + "%", Modifier.weight(1f))
        }
    }
}

@Composable
private fun StructureCaption(center: String, caption: String, modifier: Modifier) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(center, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
        Text(caption, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center)
    }
}

