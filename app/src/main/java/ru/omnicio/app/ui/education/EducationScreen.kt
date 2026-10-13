package ru.omnicio.app.ui.education

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun EducationScreen(
    onBack: () -> Unit,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var category by rememberSaveable { mutableStateOf<EducationCategory?>(null) }
    var expandedLessonId by rememberSaveable { mutableStateOf<String?>("news-impact") }
    val lessons = remember(category) {
        EducationCatalog.lessons.filter { category == null || it.category == category }
    }
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            AnalystBottomBar(
                selected = AnalystTab.Profile,
                onPortfolioClick = onPortfolioClick,
                onProfileClick = onProfileClick,
            )
        },
    ) { insets ->
        SpectrumBackground(Modifier.fillMaxSize().padding(insets)) {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item(key = "back") {
                    TextButton(onClick = onBack, contentPadding = PaddingValues(0.dp)) {
                        Text("‹ Назад")
                    }
                }
                item(key = "hero") { EducationHero() }
                item(key = "categories") {
                    CategoryRow(selected = category, onSelected = { category = it })
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
                item(key = "guardrail") {
                    SpectrumCard {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            SpectrumIcon(
                                symbol = SpectrumSymbol.Risk,
                                modifier = Modifier.size(46.dp),
                                tile = true,
                                motionAllowed = false,
                            )
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    text = "Обучение не заменяет проверку риска",
                                    fontWeight = FontWeight.Bold,
                                )
                                Text(
                                    text = "Уроки объясняют механику. Доходность не гарантируется, а итоговое решение зависит от ваших целей, срока, ограничений и актуальных данных.",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    style = MaterialTheme.typography.bodyMedium,
                                )
                            }
                        }
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
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Analyst,
                modifier = Modifier.size(74.dp),
                selected = true,
                tile = true,
                motionAllowed = motion.enabled,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                SpectrumBadge("Для начинающих", accent = palette.cyan)
                Text(
                    text = "Инвестиции простыми словами",
                    fontSize = 28.sp,
                    lineHeight = 32.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "От первых шагов до понимания новостей, отчётности, кредитных рейтингов и структуры портфеля.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun CategoryRow(
    selected: EducationCategory?,
    onSelected: (EducationCategory?) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = selected == null,
            onClick = { onSelected(null) },
            label = { Text("Все") },
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
    val uriHandler = LocalUriHandler.current
    SpectrumCard(emphasized = lesson.id == "news-impact") {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            SpectrumIcon(
                symbol = lesson.symbol,
                modifier = Modifier.size(54.dp),
                selected = expanded,
                tile = true,
                motionAllowed = motion.enabled,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    SpectrumBadge(
                        text = lesson.category.title,
                        accent = if (lesson.category == EducationCategory.NEWS) palette.rose else palette.blue,
                    )
                    Text(
                        text = "${lesson.minutes} мин",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
                Text(
                    text = lesson.title,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleLarge,
                )
                Text(
                    text = lesson.subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
        TextButton(
            onClick = onExpand,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (expanded) "Свернуть урок" else "Открыть урок")
        }
        AnimatedVisibility(visible = expanded) {
            Column(
                modifier = Modifier.fillMaxWidth().padding(top = 6.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    text = lesson.explanation,
                    style = MaterialTheme.typography.bodyLarge,
                )
                lesson.checkpoints.forEach { checkpoint ->
                    Text(
                        text = "• $checkpoint",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                Spacer(Modifier.height(2.dp))
                Text(
                    text = "Официальные материалы",
                    fontWeight = FontWeight.SemiBold,
                )
                lesson.sources.forEach { source ->
                    TextButton(
                        onClick = { uriHandler.openUri(source.url) },
                        contentPadding = PaddingValues(horizontal = 0.dp, vertical = 2.dp),
                    ) {
                        Text("${source.organization}: ${source.title}")
                    }
                }
            }
        }
    }
}
