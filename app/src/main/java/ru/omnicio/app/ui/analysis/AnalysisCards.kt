package ru.omnicio.app.ui.analysis

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import java.time.Instant
import ru.omnicio.app.data.analysis.AnalysisIdea
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.ui.workspace.PrivateValue
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumMetricPill
import ru.omnicio.app.ui.spectrum.SpectrumPageHeader
import ru.omnicio.app.ui.spectrum.SpectrumPrimaryButton
import ru.omnicio.app.ui.spectrum.SpectrumProgressBar
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

@Composable
internal fun AnalysisScaffold(
    selected: AnalystTab,
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
    showBottomBar: Boolean = true,
    content: @Composable (PaddingValues) -> Unit,
) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            topBar = {
                SpectrumPageHeader(
                    title = title,
                    subtitle = subtitle,
                    symbol = symbol,
                    modifier = Modifier
                        .fillMaxWidth()
                        .windowInsetsPadding(
                            WindowInsets.safeDrawing.only(
                                WindowInsetsSides.Top + WindowInsetsSides.Horizontal,
                            ),
                        )
                        .padding(start = 20.dp, top = 16.dp, end = 20.dp, bottom = 12.dp),
                )
            },
            bottomBar = {
                if (showBottomBar) AnalystBottomBar(
                    selected = selected,
                    onPortfolioClick = onPortfolioClick,
                    onProfileClick = onProfileClick,
                )
            },
            content = content,
        )
    }
}

@Composable
internal fun RiskOverviewCard(entries: List<InsightCard>) {
    val palette = LocalSpectrumPalette.current
    val critical = entries.count { it.severity == "critical" }
    val warning = entries.count { it.severity == "warning" }
    val watch = entries.count { it.severity == "watch" }
    val main = entries.minByOrNull { when (it.severity) { "critical" -> 0; "warning" -> 1; "watch" -> 2; else -> 3 } }
    val highest = when {
        critical > 0 -> "Критический сигнал"
        warning > 0 -> "Требует внимания"
        watch > 0 -> "Под наблюдением"
        entries.isNotEmpty() -> "Информационные сигналы"
        else -> "Нет новых сигналов"
    }
    val accent = when {
        critical > 0 -> MaterialTheme.colorScheme.error
        warning > 0 -> palette.amber
        watch > 0 -> palette.violet
        else -> palette.blue
    }
    SpectrumCard(emphasized = true) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Risk,
                modifier = Modifier.size(36.dp),
                selected = true,
                tile = true,
                motionAllowed = false,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(main?.title ?: "Состояние наблюдения", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                SpectrumBadge(highest, accent = accent)
            }
        }
        main?.let { Text(PrivateValue(it.summary), style = MaterialTheme.typography.bodyMedium) }
        Text(
            "Сигналы сервера. Отсутствие сообщений не означает отсутствие риска.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium,
        )
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            if (maxWidth < 330.dp) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SpectrumMetricPill("Критично", critical.toString(), Modifier.fillMaxWidth(), MaterialTheme.colorScheme.error)
                    SpectrumMetricPill("Внимание", warning.toString(), Modifier.fillMaxWidth(), palette.amber)
                    SpectrumMetricPill("Наблюдение", watch.toString(), Modifier.fillMaxWidth(), palette.violet)
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    SpectrumMetricPill("Критично", critical.toString(), Modifier.weight(1f), MaterialTheme.colorScheme.error)
                    SpectrumMetricPill("Внимание", warning.toString(), Modifier.weight(1f), palette.amber)
                    SpectrumMetricPill("Наблюдение", watch.toString(), Modifier.weight(1f), palette.violet)
                }
            }
        }
    }
}

@Composable
internal fun MessageOverviewCard(entries: List<InsightCard>) {
    val unread = entries.count { !it.isRead }
    SpectrumCard(emphasized = unread > 0) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Messages,
                modifier = Modifier.size(58.dp),
                selected = true,
                tile = true,
                motionAllowed = false,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Лента Analyst AI", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(
                    if (unread > 0) "$unread непрочитанных сообщений" else "Новых сообщений нет",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
internal fun InsightCardView(
    card: InsightCard,
    now: Instant,
    readEnabled: Boolean,
    onRead: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val accent = when (card.severity) {
        "critical" -> MaterialTheme.colorScheme.error
        "warning" -> palette.amber
        "watch" -> palette.violet
        else -> palette.cyan
    }
    val label = when (card.severity) {
        "critical" -> "Критично"
        "warning" -> "Внимание"
        "watch" -> "Наблюдение"
        "info" -> "Информация"
        else -> "Категория не подтверждена"
    }
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = !card.isRead) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            SpectrumBadge(label, accent = accent)
            if (!card.isRead) SpectrumBadge("Новое", accent = palette.cyan)
        }
        Text(card.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(
            "Проверка: ${analysisTime(card.createdAt) ?: "время неизвестно"}",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall,
        )
        Text(
            insightValidity(card.createdAt, card.validUntil, now),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall,
        )
        Text(PrivateValue(card.summary), style = MaterialTheme.typography.bodyLarge)
        card.actions.forEach { Text(PrivateValue("• $it"), style = MaterialTheme.typography.bodyLarge) }
        if (card.uncertainties.isNotEmpty()) {
            Text("Ограничения вывода", fontWeight = FontWeight.SemiBold)
            card.uncertainties.forEach {
                Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
            }
        }
        if (card.evidence.isEmpty()) {
            Text(
                "Источники в этом сообщении не указаны.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
            )
        } else {
            EvidenceDetails(card)
        }
        if (!card.isRead) {
            TextButton(
                onClick = onRead,
                enabled = readEnabled,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
            ) {
                Text("Отметить прочитанным")
            }
        }
    }
}

@Composable
private fun EvidenceDetails(card: InsightCard) {
    var expanded by remember(card.id) { mutableStateOf(false) }
    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.heightIn(min = 48.dp)) {
        Text(if (expanded) "Скрыть источники" else "Источники и факты (${card.evidence.size})")
    }
    if (expanded) {
        card.evidence.forEach { source ->
            Text(PrivateValue(source.fact.ifBlank { "Описание факта не получено." }), style = MaterialTheme.typography.bodyMedium)
            Text(
                "Источник: ${source.sourceId.ifBlank { "не указан" }} · ${analysisTime(source.asOf) ?: "время неизвестно"}",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
internal fun IdeaCard(idea: AnalysisIdea) {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) { StatusCard("Распределение", "Финансовые подробности скрыты."); return }
    val palette = LocalSpectrumPalette.current
    val current = (idea.currentPercent / 100.0).toFloat().coerceIn(0f, 1f)
    val target = (idea.targetPercent / 100.0).toFloat().coerceIn(0f, 1f)
    SpectrumCard(Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Ideas,
                modifier = Modifier.size(52.dp),
                selected = true,
                tile = true,
                motionAllowed = false,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                SpectrumBadge("Обзор распределения", accent = palette.violet)
                Text(idea.assetClass, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            }
        }
        Text("Текущая доля · ${analysisPercent(idea.currentPercent)}", fontWeight = FontWeight.SemiBold)
        SpectrumProgressBar(current, accent = palette.blue)
        Text("Ориентир профиля · ${analysisPercent(idea.targetPercent)}", fontWeight = FontWeight.SemiBold)
        SpectrumProgressBar(target, accent = palette.emerald)
        Text(
            "Допустимое направление: до ${analysisPercent(idea.suggestedMaxPercent)} портфеля",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium,
        )
        Text(idea.explanation, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
internal fun ActionCard(
    title: String,
    text: String,
    buttonText: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Analyst, Modifier.size(58.dp), selected = true, tile = true)
            Text(title, modifier = Modifier.weight(1f), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge)
        SpectrumPrimaryButton(
            text = buttonText,
            onClick = onClick,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
            symbol = SpectrumSymbol.Update,
        )
    }
}

@Composable
internal fun StatusCard(title: String, text: String, accent: Boolean = false) {
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = accent) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyLarge)
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
        SpectrumBadge("Не удалось выполнить запрос", accent = MaterialTheme.colorScheme.error)
        Text(message, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        TextButton(onClick = onRetry, enabled = enabled, modifier = Modifier.heightIn(min = 48.dp)) {
            Text("Повторить")
        }
    }
}

@Composable
internal fun ProfileChoiceCard(
    title: String,
    options: List<Pair<String, String>>,
    selected: String,
    enabled: Boolean,
    onSelect: (String) -> Unit,
) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        options.forEach { (value, label) ->
            FilterChip(
                selected = selected == value,
                enabled = enabled,
                onClick = { onSelect(value) },
                label = { Text(label) },
                modifier = Modifier.heightIn(min = 48.dp),
            )
        }
    }
}

@Composable
internal fun SliderCard(
    title: String,
    value: Double,
    range: ClosedFloatingPointRange<Float>,
    enabled: Boolean,
    onValueChange: (Double) -> Unit,
) {
    val valid = value.isFinite() && value >= range.start && value <= range.endInclusive
    SpectrumCard(Modifier.fillMaxWidth()) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(analysisPercent(value), fontWeight = FontWeight.SemiBold)
        if (!valid) {
            Text(
                "Значение вне поддерживаемого диапазона. Повторно загрузите профиль.",
                color = MaterialTheme.colorScheme.error,
            )
        }
        Slider(
            value = if (valid) value.toFloat() else range.start,
            onValueChange = { onValueChange(selectedProfilePercent(it, range)) },
            valueRange = range,
            steps = profileSliderSteps(range),
            enabled = enabled && valid,
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).semantics {
                contentDescription = title
            },
        )
    }
}

@Composable
internal fun SwitchCard(
    title: String,
    checked: Boolean,
    enabled: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(
                value = checked,
                enabled = enabled,
                role = Role.Switch,
                onValueChange = onCheckedChange,
            ),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(title, modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
            Switch(checked = checked, enabled = enabled, onCheckedChange = null)
        }
    }
}

