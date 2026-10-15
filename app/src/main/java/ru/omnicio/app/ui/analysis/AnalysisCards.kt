package ru.omnicio.app.ui.analysis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.analysis.AnalysisIdea
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import java.time.Instant

@Composable
internal fun AnalysisScaffold(
    selected: AnalystTab, title: String, subtitle: String,
    onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    modifier: Modifier = Modifier, content: @Composable (PaddingValues) -> Unit,
) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(), containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            topBar = {
                Column(Modifier.fillMaxWidth()
                    .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))
                    .padding(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 12.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    val symbol = when (selected) {
                        AnalystTab.Ideas -> SpectrumSymbol.Ideas
                        AnalystTab.Pulse, AnalystTab.Chat -> SpectrumSymbol.Bell
                        else -> SpectrumSymbol.Risk
                    }
                    SpectrumHeader(title, symbol = symbol)
                    Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodySmall)
                }
            },
            bottomBar = { AnalystBottomBar(selected = selected,
                onPortfolioClick = onPortfolioClick, onProfileClick = onProfileClick) },
            content = content,
        )
    }
}

@Composable
internal fun InsightCardView(card: InsightCard, now: Instant, readEnabled: Boolean, onRead: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = !card.isRead) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            val palette = LocalSpectrumPalette.current
            val accent = when (card.severity) {
                "critical" -> MaterialTheme.colorScheme.error
                "warning" -> palette.amber
                else -> palette.cyan
            }
            val label = when (card.severity) {
                "critical" -> "Критично"
                "warning" -> "Внимание"
                "watch" -> "Наблюдение"
                "info" -> "Информация"
                else -> "Категория не подтверждена"
            }
            SpectrumBadge(label, accent = accent)
            Text(card.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Проверка: ${analysisTime(card.createdAt) ?: "время неизвестно"}", style = MaterialTheme.typography.bodySmall)
            Text(insightValidity(card.createdAt, card.validUntil, now), style = MaterialTheme.typography.bodySmall)
            Text(card.summary, style = MaterialTheme.typography.bodyLarge)
            card.actions.forEach { Text("• $it", style = MaterialTheme.typography.bodyLarge) }
            if (card.uncertainties.isNotEmpty()) {
                Text("Ограничения вывода", fontWeight = FontWeight.SemiBold)
                card.uncertainties.forEach { Text(it, style = MaterialTheme.typography.bodyMedium) }
            }
            if (card.evidence.isEmpty()) {
                Text("Источники в этом сообщении не указаны.", style = MaterialTheme.typography.bodySmall)
            } else {
                EvidenceDetails(card)
            }
            if (!card.isRead) TextButton(onClick = onRead, enabled = readEnabled,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Отметить прочитанным") }
        }
    }
}

@Composable
private fun EvidenceDetails(card: InsightCard) {
    var expanded by remember(card.id) { mutableStateOf(false) }
    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.heightIn(min = 48.dp)) {
        Text(if (expanded) "Скрыть источники" else "Источники и факты (${card.evidence.size})")
    }
    if (expanded) card.evidence.forEach { source ->
        Text(source.fact.ifBlank { "Описание факта не получено." }, style = MaterialTheme.typography.bodyMedium)
        Text("Источник: ${source.sourceId.ifBlank { "не указан" }} · ${analysisTime(source.asOf) ?: "время неизвестно"}",
            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
internal fun IdeaCard(idea: AnalysisIdea) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            SpectrumIcon(SpectrumSymbol.Ideas, Modifier.size(54.dp), selected = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(idea.assetClass, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Сейчас ${analysisPercent(idea.currentPercent)} · ориентир ${analysisPercent(idea.targetPercent)}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
        SpectrumBadge("Идея для портфеля", accent = LocalSpectrumPalette.current.violet)
        Text(idea.explanation, style = MaterialTheme.typography.bodyMedium)
        Text("Допустимая доля: до ${analysisPercent(idea.suggestedMaxPercent)}", fontWeight = FontWeight.SemiBold)
        Text("Направление диверсификации, не торговое поручение.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
internal fun ActionCard(title: String, text: String, buttonText: String, enabled: Boolean, onClick: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(text, style = MaterialTheme.typography.bodyLarge)
            SpectrumAction(buttonText, onClick, enabled = enabled)
        }
    }
}

@Composable
internal fun StatusCard(title: String, text: String, accent: Boolean = false) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = accent) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(text, style = MaterialTheme.typography.bodyLarge)
        }
    }
}

@Composable
internal fun LoadingCard() {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            CircularProgressIndicator(Modifier.size(32.dp))
            Text("Получаем актуальные данные…", modifier = Modifier.weight(1f))
        }
    }
}

@Composable
internal fun ErrorCard(message: String, onRetry: () -> Unit, enabled: Boolean = true) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SpectrumBadge("Не удалось выполнить запрос", accent = MaterialTheme.colorScheme.error)
            Text(message, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            TextButton(onClick = onRetry, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) { Text("Повторить") }
        }
    }
}

@Composable
internal fun ProfileChoiceCard(title: String, options: List<Pair<String, String>>, selected: String,
    enabled: Boolean, onSelect: (String) -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        options.forEach { (value, label) ->
            FilterChip(selected = selected == value, enabled = enabled, onClick = { onSelect(value) },
                label = { Text(label) }, modifier = Modifier.heightIn(min = 48.dp))
        }
    }
}

@Composable
internal fun SliderCard(title: String, value: Double, range: ClosedFloatingPointRange<Float>,
    enabled: Boolean, onValueChange: (Double) -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(analysisPercent(value), fontWeight = FontWeight.SemiBold)
        val valid = value.isFinite() && value >= range.start && value <= range.endInclusive
        if (!valid) Text("Значение вне поддерживаемого диапазона. Повторно загрузите профиль.", color = MaterialTheme.colorScheme.error)
        Slider(value = if (valid) value.toFloat() else range.start,
            onValueChange = { onValueChange(selectedProfilePercent(it, range)) },
            valueRange = range, steps = profileSliderSteps(range), enabled = enabled && valid,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).semantics { contentDescription = title })
    }
}

@Composable
internal fun SwitchCard(title: String, checked: Boolean, enabled: Boolean, onCheckedChange: (Boolean) -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp)
            .toggleable(value = checked, enabled = enabled, role = Role.Switch, onValueChange = onCheckedChange),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(title, modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
            Switch(checked = checked, enabled = enabled, onCheckedChange = null)
        }
    }
}
