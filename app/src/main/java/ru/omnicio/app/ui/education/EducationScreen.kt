package ru.omnicio.app.ui.education

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.spectrum.SpectrumHeader
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
    var expandedLessonId by rememberSaveable { mutableStateOf<String?>(null) }
    val lessons = remember(category) {
        EducationCatalog.lessons.filter { category == null || it.category == category }
    }
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = { AnalystBottomBar(AnalystTab.Education, onPortfolioClick, onProfileClick) },
    ) { insets ->
        SpectrumBackground(Modifier.fillMaxSize().padding(insets)) {
            Column(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
                // Navigation must remain reachable while reading a long lesson.
                Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                    SpectrumHeader("Обучение", symbol = SpectrumSymbol.Education, modifier = Modifier.padding(top = 12.dp))
                    TextButton(onClick = onBack, contentPadding = PaddingValues(0.dp)) {
                        Text("‹ Назад")
                    }
                    CategoryRow(selected = category, onSelected = { category = it })
                }
                // A different category starts at its first lesson. Ordinary
                // recomposition preserves position; no scroll job races the user.
                key(category) {
                    LazyColumn(
                        state = rememberLazyListState(),
                        modifier = Modifier.fillMaxWidth().weight(1f).testTag("education-content"),
                        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        if (category == null) item(key = "hero") { EducationHero() }
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
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Analyst, Modifier.size(54.dp), selected = true, tile = true, motionAllowed = motion.enabled)
            Column(Modifier.weight(1f)) { SpectrumBadge("Для начинающих", accent = palette.cyan) }
        }
        // Text uses the full card width, including at 320dp and 200% font size.
        Text("Инвестиции простыми словами", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text("От первых шагов до понимания новостей, отчётности, кредитных рейтингов и структуры портфеля.",
            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun EducationGuardrail() {
    SpectrumCard {
        SpectrumIcon(SpectrumSymbol.Risk, Modifier.size(46.dp), tile = true, motionAllowed = false)
        Text("Обучение не заменяет проверку риска", fontWeight = FontWeight.Bold)
        Text("Уроки объясняют механику. Доходность не гарантируется, а итоговое решение зависит от ваших целей, срока, ограничений и актуальных данных.",
            color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun CategoryRow(selected: EducationCategory?, onSelected: (EducationCategory?) -> Unit) {
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilterChip(selected = selected == null, onClick = { onSelected(null) }, label = { Text("Все") })
        EducationCategory.entries.forEach { item ->
            FilterChip(selected = selected == item, onClick = { onSelected(item) }, label = { Text(item.title) })
        }
    }
}

@Composable
private fun LessonCard(lesson: EducationLesson, expanded: Boolean, onExpand: () -> Unit) {
    val motion = LocalSpectrumMotionPreference.current
    val action = if (expanded) "Свернуть урок" else "Открыть урок"
    SpectrumCard(emphasized = expanded) {
        TextButton(onClick = onExpand, modifier = Modifier.fillMaxWidth()
            .testTag("lesson-toggle-${lesson.id}")
            .semantics { contentDescription = "$action: ${lesson.title}" },
            contentPadding = PaddingValues(0.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SpectrumIcon(lesson.symbol, Modifier.size(52.dp), selected = expanded, motionAllowed = motion.enabled)
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(lesson.title, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface)
                    Text(lesson.subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
                    Text("${lesson.minutes} мин · ${lesson.category.title}", color = LocalSpectrumPalette.current.cyan,
                        style = MaterialTheme.typography.labelMedium)
                }
                Text(if (expanded) "−" else "›", color = LocalSpectrumPalette.current.cyan)
            }
        }
        if (motion.enabled) AnimatedVisibility(visible = expanded) { LessonBody(lesson) }
        else if (expanded) LessonBody(lesson)
    }
}

@Composable
private fun LessonBody(lesson: EducationLesson) {
    val uriHandler = LocalUriHandler.current
    var sourceError by remember(lesson.id) { mutableStateOf<String?>(null) }
    Column(Modifier.fillMaxWidth().padding(top = 6.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(lesson.explanation, style = MaterialTheme.typography.bodyLarge)
        lesson.checkpoints.forEach { checkpoint ->
            Text("• $checkpoint", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
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
            ) { Text("${source.organization}: ${source.title}") }
        }
        sourceError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    }
}
