package ru.omnicio.app.ui.education

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumPageHeader
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun EducationScreen(
    onBack: () -> Unit,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    BackHandler(onBack = onBack)
    var category by rememberSaveable { mutableStateOf<EducationCategory?>(null) }
    var expandedLessonId by rememberSaveable { mutableStateOf<String?>("news-impact") }
    val lessons = remember(category) {
        EducationCatalog.lessons.filter { category == null || it.category == category }
    }
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = {
                AnalystBottomBar(
                    selected = AnalystTab.Education,
                    onPortfolioClick = onPortfolioClick,
                    onProfileClick = onProfileClick,
                )
            },
        ) { insets ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(insets)
                    .consumeWindowInsets(insets)
                    .semantics { testTagsAsResourceId = true },
            ) {
                // Navigation must stay reachable without traversing every lesson.
                // The descriptive header scrolls with the catalog, leaving room
                // for lesson content when the system font is enlarged.
                Column(
                    Modifier.fillMaxWidth().zIndex(1f).clipToBounds()
                        .padding(horizontal = 20.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    SpectrumSecondaryButton(
                        text = "Назад",
                        onClick = onBack,
                        modifier = Modifier.fillMaxWidth().testTag("education-back"),
                    )
                    CategoryRow(selected = category, onSelected = { category = it })
                }
                key(category) {
                    LazyColumn(
                        state = rememberLazyListState(),
                        modifier = Modifier.fillMaxWidth().weight(1f)
                            .clipToBounds().testTag("education-content"),
                        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        // Filtered categories must show their first lesson without
                        // a large descriptive header hiding it at 200% font scale.
                        if (category == null) {
                            item(key = "education-header") {
                                SpectrumPageHeader(
                                    title = "Обучение",
                                    subtitle = "Понятно о деньгах и риске",
                                    symbol = SpectrumSymbol.Education,
                                )
                            }
                            item(key = "hero") { EducationHero() }
                        }
                        items(lessons, key = EducationLesson::id) { lesson ->
                            LessonCard(
                                lesson = lesson,
                                expanded = expandedLessonId == lesson.id,
                                onExpand = {
                                    expandedLessonId = if (expandedLessonId == lesson.id) null else lesson.id
                                },
                            )
                        }
                        item(key = "guardrail") { EducationGuardrail() }
                    }
                }
            }
        }
    }
}

@Composable
private fun EducationHero() {
    val palette = LocalSpectrumPalette.current
    val motion = LocalSpectrumMotionPreference.current
    SpectrumCard(emphasized = true) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                SpectrumSymbol.Analyst,
                Modifier.size(64.dp),
                selected = true,
                tile = true,
                motionAllowed = motion.enabled,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                SpectrumBadge("Для начинающих", accent = palette.cyan)
                Text("Пошаговый маршрут", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
            }
        }
        Text(
            "От первых шагов до понимания новостей, отчётности, кредитных рейтингов и структуры портфеля.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyLarge,
        )
    }
}

@Composable
private fun EducationGuardrail() {
    SpectrumCard {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                SpectrumSymbol.Risk,
                Modifier.size(50.dp),
                tile = true,
                selected = true,
                motionAllowed = false,
            )
            Text(
                "Обучение не заменяет проверку риска",
                modifier = Modifier.weight(1f),
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium,
            )
        }
        Text(
            "Уроки объясняют механику. Доходность не гарантируется, а итоговое решение зависит от ваших целей, срока, ограничений и актуальных данных.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun CategoryRow(
    selected: EducationCategory?,
    onSelected: (EducationCategory?) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = selected == null,
            onClick = { onSelected(null) },
            label = { Text("Все уроки") },
        )
        EducationCategory.entries.forEach { item ->
            FilterChip(
                selected = selected == item,
                onClick = { onSelected(item) },
                label = { Text(item.title) },
            )
        }
    }
}

@Composable
private fun LessonCard(
    lesson: EducationLesson,
    expanded: Boolean,
    onExpand: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val motion = LocalSpectrumMotionPreference.current
    SpectrumCard(emphasized = lesson.id == "news-impact") {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SpectrumIcon(
                lesson.symbol,
                Modifier.size(52.dp),
                selected = expanded,
                tile = true,
                motionAllowed = motion.enabled,
            )
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                SpectrumBadge(
                    lesson.category.title,
                    accent = if (lesson.category == EducationCategory.NEWS) palette.rose else palette.blue,
                )
                Text(
                    "${lesson.minutes} мин",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
        Text(lesson.title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
        Text(
            lesson.subtitle,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium,
        )
        val action = if (expanded) "Свернуть урок" else "Открыть урок"
        TextButton(
            onClick = onExpand,
            modifier = Modifier
                .fillMaxWidth()
                .testTag("lesson-toggle-${lesson.id}")
                .semantics { contentDescription = "$action: ${lesson.title}" },
        ) {
            Text(action)
        }
        if (motion.enabled && android.animation.ValueAnimator.areAnimatorsEnabled()) {
            AnimatedVisibility(visible = expanded) { LessonBody(lesson) }
        } else if (expanded) {
            LessonBody(lesson)
        }
    }
}

@Composable
private fun LessonBody(lesson: EducationLesson) {
    val uriHandler = LocalUriHandler.current
    var sourceError by remember(lesson.id) { mutableStateOf<String?>(null) }
    Column(
        Modifier.fillMaxWidth().padding(top = 6.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(lesson.explanation, style = MaterialTheme.typography.bodyLarge)
        lesson.checkpoints.forEach { checkpoint ->
            Text(
                "• $checkpoint",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        Spacer(Modifier.height(2.dp))
        Text("Официальные материалы", fontWeight = FontWeight.SemiBold)
        lesson.sources.forEach { source ->
            TextButton(
                onClick = {
                    sourceError = null
                    runCatching { uriHandler.openUri(source.url) }.onFailure {
                        sourceError = "Не удалось открыть ссылку. Проверьте браузер или подключение."
                    }
                },
                contentPadding = PaddingValues(horizontal = 0.dp, vertical = 2.dp),
            ) {
                Text("${source.organization}: ${source.title}")
            }
        }
        sourceError?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

