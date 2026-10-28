package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.gestures.detectTapGestures
import ru.omnicio.app.ui.workspace.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.Role
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
import ru.omnicio.app.ui.spectrum.SpectrumAssetMark

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
        sign > 0 -> LocalSpectrumPalette.current.emerald
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
internal fun PositionLine(position: PortfolioPosition, total: MoneyAmount? = null, accountName: String? = null,
    selected: Boolean = false, onPreview: (() -> Unit)? = null, sharedKey: String = position.id, onClick: () -> Unit) {
    val fontScale = LocalDensity.current.fontScale
    var preview by rememberSaveable(sharedKey) { mutableStateOf(false) }
    val showPreview = onPreview ?: { preview = true }
    val previewClick = ru.omnicio.app.ui.spatial.rememberSpatialHapticClick(ru.omnicio.app.ui.spatial.SpatialHaptic.Selection, showPreview)
    val rowClick = ru.omnicio.app.ui.spatial.rememberSpatialHapticClick(onClick)
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    ru.omnicio.app.ui.spatial.SpatialSurface(color = LocalSpectrumPalette.current.card,
        state = when { pressed -> ru.omnicio.app.ui.spatial.SpatialState.Pressed; selected || focused -> ru.omnicio.app.ui.spatial.SpatialState.Selected; else -> ru.omnicio.app.ui.spatial.SpatialState.Idle },
        modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("position-row-$sharedKey")
            .combinedClickable(interactionSource = interaction, indication = null, role = Role.Button,
                onClick = rowClick, onLongClick = previewClick, onLongClickLabel = "Кратко о позиции", hapticFeedbackEnabled = false)
            .semantics(mergeDescendants = true) { this.selected = selected }) {
        BoxWithConstraints(Modifier.fillMaxWidth().padding(12.dp)) {
            val stacked = portfolioStackedLayout(maxWidth.value, fontScale)
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    ru.omnicio.app.ui.spatial.SpatialObject(sharedKey) {
                        SpectrumAssetMark(position.instrumentType, position.company ?: position.title, instrumentSharedModifier(sharedKey).size(36.dp))
                    }
                    PositionIdentity(position, Modifier.weight(1f), stacked)
                    if (!stacked) PositionAmounts(position, Modifier.widthIn(max = 132.dp), total)
                }
                if (accountName != null) Text(accountName, style = MaterialTheme.typography.bodySmall)
                if (stacked) PositionAmounts(position, Modifier.fillMaxWidth(), total)
                TextButton(onClick = showPreview, contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp)) { Text("Кратко и действия") }
            }
        }
    }
    if (preview) PortfolioQuickPreview(position, accountName, { preview = false }, { preview = false; onClick() })
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
internal fun StructureChart(slices: List<ChartSlice>, center: String, caption: String, onSelect: (String) -> Unit = {}) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Notice("Структура скрыта режимом приватности."); return }
    val fractions = remember(slices) { portfolioFractions(slices) }
    if (fractions == null) {
        Notice("Нет сопоставимых данных для диаграммы. Некорректные доли не исключаются молча.")
        return
    }
    val spectrum = LocalSpectrumPalette.current
    val palette = spectrum.chartSeries
    var selectedTitle by remember(caption) { mutableStateOf<String?>(null) }
    val selected = fractions.indexOfFirst { it.id == selectedTitle }
    val choose: (Int) -> Unit = { index -> fractions.getOrNull(index)?.let { selectedTitle = it.id; onSelect(it.id) } }
    if (fractions.size > 6) {
        fractions.sortedByDescending { it.fraction }.forEachIndexed { index, item ->
            TextButton(onClick = { choose(fractions.indexOf(item)) }, modifier = Modifier.fillMaxWidth()) {
                Text("${item.title} · ${decimalText(BigDecimal.valueOf(item.fraction * 100))}%")
            }
            ru.omnicio.app.ui.spectrum.SpectrumProgressBar(item.fraction.toFloat(), accent = palette[index % palette.size])
        }
        return
    }
    val remainder = MaterialTheme.colorScheme.surfaceVariant
    val largeText = LocalDensity.current.fontScale >= 1.5f
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val diameter = minOf(maxWidth, 208.dp)
        Box(Modifier.fillMaxWidth().height(diameter + 16.dp), contentAlignment = Alignment.Center) {
            ru.omnicio.app.ui.spatial.SpatialRing(fractions.map { it.fraction }, palette,
                selected.takeIf { it >= 0 }, Modifier.size(diameter)
                    .semantics { contentDescription = "Структура: $caption. Выберите сегмент или его подпись ниже." }
                    .pointerInput(fractions) { detectTapGestures { point ->
                        val x = point.x - size.width / 2f; val y = point.y - size.height / 2f
                        val radius = kotlin.math.sqrt(x * x + y * y)
                        if (radius > minOf(size.width, size.height) * .22f && radius < minOf(size.width, size.height) * .5f) {
                            val angle = (Math.toDegrees(kotlin.math.atan2(y.toDouble(), x.toDouble())) + 450.0) % 360.0
                            var accumulated = 0.0
                            val index = fractions.indexOfFirst { slice -> accumulated += slice.fraction * 360; angle < accumulated }
                            if (index >= 0) choose(index)
                        }
                    } })
            if (!largeText) StructureCaption(center, caption, Modifier.widthIn(max = diameter * 0.68f))
        }
    }
    if (largeText) StructureCaption(center, caption, Modifier.fillMaxWidth())
    fractions.forEachIndexed { index, item ->
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ru.omnicio.app.ui.spatial.SpatialIcon("monogram", Modifier.size(22.dp), tint = palette[index % palette.size])
            TextButton(onClick = { choose(index) }, modifier = Modifier.weight(1f)) {
                Text("${if (index == selected) "Выбрано · " else ""}${item.title} · ${decimalText(BigDecimal.valueOf(item.fraction * 100))}%")
            }
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


