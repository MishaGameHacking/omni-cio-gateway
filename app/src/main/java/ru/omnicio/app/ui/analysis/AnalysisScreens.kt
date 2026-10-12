package ru.omnicio.app.ui.analysis

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.analysis.AnalysisBackendClient
import ru.omnicio.app.data.analysis.AnalysisIdea
import ru.omnicio.app.data.analysis.AnalysisProfile
import ru.omnicio.app.data.analysis.AnalysisStatus
import ru.omnicio.app.data.analysis.IdeasPayload
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.data.analysis.InsightFeed
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab

private val AnalysisBackground = Color(0xFFF4F5F7)
private val AnalysisCard = Color.White
private val Muted = Color(0xFF858B95)
private val Blue = Color(0xFF4E8EE8)
private val Positive = Color(0xFF179447)
private val Warning = Color(0xFFD17A00)
private val Critical = Color(0xFFC93636)

private sealed interface LoadingState<out T> {
    data object Loading : LoadingState<Nothing>
    data class Ready<T>(val value: T) : LoadingState<T>
    data class Error(val message: String) : LoadingState<Nothing>
}

@Composable
fun InsightFeedScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val client = remember { AnalysisBackendClient() }
    var reload by remember { mutableIntStateOf(0) }
    var state by remember { mutableStateOf<LoadingState<InsightFeed>>(LoadingState.Loading) }

    LaunchedEffect(accessToken, reload) {
        state = LoadingState.Loading
        state = when (val result = withContext(Dispatchers.IO) { client.fetchFeed(accessToken) }) {
            is BackendResult.Success -> LoadingState.Ready(result.value)
            is BackendResult.Failure -> LoadingState.Error(result.message)
        }
    }

    AnalysisScaffold(
        selected = AnalystTab.Chat,
        title = "Сообщения",
        subtitle = "Важные выводы Analyst AI без свободного чата",
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
    ) { contentPadding ->
        AnalysisListContent(
            state = state,
            padding = contentPadding,
            emptyTitle = "Важных сообщений пока нет",
            emptyText = "Система сообщит об изменении состава портфеля, риске или завершённом обзоре.",
            onRetry = { reload += 1 },
            onCardRead = { card ->
                if (!card.isRead) {
                    withContext(Dispatchers.IO) { client.markRead(accessToken, card.id) }
                    reload += 1
                }
            },
        ) { it.cards }
    }
}

@Composable
fun PulseScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val client = remember { AnalysisBackendClient() }
    var reload by remember { mutableIntStateOf(0) }
    var state by remember { mutableStateOf<LoadingState<List<InsightCard>>>(LoadingState.Loading) }

    LaunchedEffect(accessToken, reload) {
        state = LoadingState.Loading
        state = when (val result = withContext(Dispatchers.IO) { client.fetchPulse(accessToken) }) {
            is BackendResult.Success -> LoadingState.Ready(result.value)
            is BackendResult.Failure -> LoadingState.Error(result.message)
        }
    }

    AnalysisScaffold(
        selected = AnalystTab.Pulse,
        title = "Пульс",
        subtitle = "Изменения портфеля, утренние и вечерние проверки",
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
    ) { contentPadding ->
        AnalysisListContent(
            state = state,
            padding = contentPadding,
            emptyTitle = "Событий пока нет",
            emptyText = "Алгоритмы работают в фоне и добавят сюда только существенные изменения.",
            onRetry = { reload += 1 },
            onCardRead = { card ->
                if (!card.isRead) {
                    withContext(Dispatchers.IO) { client.markRead(accessToken, card.id) }
                    reload += 1
                }
            },
        ) { it }
    }
}

@Composable
fun IdeasScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    onOpenProfileSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val client = remember { AnalysisBackendClient() }
    var reload by remember { mutableIntStateOf(0) }
    var refreshing by remember { mutableStateOf(false) }
    var state by remember { mutableStateOf<LoadingState<IdeasPayload>>(LoadingState.Loading) }
    var refreshMessage by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(accessToken, reload) {
        state = LoadingState.Loading
        state = when (val result = withContext(Dispatchers.IO) { client.fetchIdeas(accessToken) }) {
            is BackendResult.Success -> LoadingState.Ready(result.value)
            is BackendResult.Failure -> LoadingState.Error(result.message)
        }
    }

    AnalysisScaffold(
        selected = AnalystTab.Ideas,
        title = "Что купить",
        subtitle = "Направления диверсификации, а не торговые команды",
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
    ) { contentPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(contentPadding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ActionCard(
                    title = "Обновить портфель и анализ",
                    text = refreshMessage
                        ?: "Проверка запускается вручную и автоматически утром, вечером и после существенных изменений.",
                    buttonText = if (refreshing) "Обновляем…" else "Обновить",
                    enabled = !refreshing,
                    onClick = {
                        refreshing = true
                        refreshMessage = null
                    },
                )
            }

            when (val current = state) {
                LoadingState.Loading -> item { LoadingCard() }
                is LoadingState.Error -> item {
                    ErrorCard(current.message) { reload += 1 }
                }
                is LoadingState.Ready -> {
                    val payload = current.value
                    item {
                        StatusCard(
                            title = when (payload.state) {
                                "ready" -> "Есть направления для выравнивания"
                                "balanced" -> "Структура близка к целевой"
                                "profile_required" -> "Нужен инвестиционный профиль"
                                "portfolio_required" -> "Нужен актуальный портфель"
                                "no_excess_cash" -> "Свободный резерв не превышен"
                                else -> "Проверка завершена"
                            },
                            text = payload.message,
                            accent = payload.state == "ready",
                        )
                    }
                    if (payload.state == "profile_required") {
                        item {
                            Button(
                                onClick = onOpenProfileSettings,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text("Настроить профиль риска")
                            }
                        }
                    }
                    items(payload.ideas, key = { it.assetClass }) { idea ->
                        IdeaCard(idea)
                    }
                    if (payload.ideas.isEmpty()) {
                        item {
                            EmptyCard(
                                "Конкретные бумаги не показываются, пока они не прошли проверку источников, ликвидности и ограничений профиля.",
                            )
                        }
                    }
                }
            }
        }
    }

    LaunchedEffect(refreshing) {
        if (!refreshing) return@LaunchedEffect
        when (val result = withContext(Dispatchers.IO) { client.refresh(accessToken) }) {
            is BackendResult.Success -> {
                refreshMessage = when (result.value.state) {
                    "completed" -> "Расширенный анализ выполнен моделью ${result.value.model ?: "Timeweb"}."
                    "fallback" -> "Портфель обновлён. Показан безопасный алгоритмический вывод без платного вызова."
                    else -> "Новых существенных изменений не найдено."
                }
            }
            is BackendResult.Failure -> refreshMessage = result.message
        }
        refreshing = false
        reload += 1
    }
}

@Composable
fun AnalysisProfileSettingsScreen(
    accessToken: String,
    onBack: () -> Unit,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val client = remember { AnalysisBackendClient() }
    var state by remember { mutableStateOf<LoadingState<AnalysisProfile>>(LoadingState.Loading) }
    var status by remember { mutableStateOf<AnalysisStatus?>(null) }
    var draft by remember { mutableStateOf<AnalysisProfile?>(null) }
    var saving by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableIntStateOf(0) }

    LaunchedEffect(accessToken, reload) {
        state = LoadingState.Loading
        val profileResult = withContext(Dispatchers.IO) { client.fetchProfile(accessToken) }
        val statusResult = withContext(Dispatchers.IO) { client.fetchStatus(accessToken) }
        if (statusResult is BackendResult.Success) status = statusResult.value
        state = when (profileResult) {
            is BackendResult.Success -> {
                draft = profileResult.value
                LoadingState.Ready(profileResult.value)
            }
            is BackendResult.Failure -> LoadingState.Error(profileResult.message)
        }
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = AnalysisBackground,
        bottomBar = {
            AnalystBottomBar(
                selected = AnalystTab.Profile,
                onPortfolioClick = onPortfolioClick,
                onProfileClick = onProfileClick,
            )
        },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                TextButton(onClick = onBack) { Text("‹ Назад") }
                Text(
                    text = "Инвестиционный профиль",
                    fontSize = 32.sp,
                    lineHeight = 38.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "Ограничения применяются алгоритмами до обращения к ИИ.",
                    color = Muted,
                )
            }

            when (val current = state) {
                LoadingState.Loading -> item { LoadingCard() }
                is LoadingState.Error -> item { ErrorCard(current.message) { reload += 1 } }
                is LoadingState.Ready -> {
                    val profile = draft ?: current.value
                    item {
                        StatusCard(
                            title = if (status?.deterministicMonitoring == true) {
                                "Фоновый контроль включён"
                            } else {
                                "Проверяем состояние"
                            },
                            text = when {
                                status?.aiConfigured == true -> "Модельный контур подключён; пустые события отсекаются алгоритмами."
                                else -> "Алгоритмические предупреждения работают. Модель вызывается только при доступной серверной конфигурации."
                            },
                            accent = status?.deterministicMonitoring == true,
                        )
                    }
                    item {
                        ProfileChoiceCard(
                            title = "Уровень риска",
                            options = listOf(
                                "conservative" to "Консервативный",
                                "moderate" to "Умеренный",
                                "aggressive" to "Агрессивный",
                            ),
                            selected = profile.riskLevel,
                            onSelect = { draft = profile.copy(riskLevel = it) },
                        )
                    }
                    item {
                        ProfileChoiceCard(
                            title = "Горизонт",
                            options = listOf(
                                "short" to "До года",
                                "medium" to "1–3 года",
                                "long" to "Более 3 лет",
                            ),
                            selected = profile.horizon,
                            onSelect = { draft = profile.copy(horizon = it) },
                        )
                    }
                    item {
                        SliderCard(
                            title = "Максимальная доля позиции",
                            value = profile.maxPositionPercent,
                            range = 10f..50f,
                            suffix = "%",
                            onValueChange = { draft = profile.copy(maxPositionPercent = it) },
                        )
                    }
                    item {
                        SliderCard(
                            title = "Минимальный денежный резерв",
                            value = profile.minCashPercent,
                            range = 0f..30f,
                            suffix = "%",
                            onValueChange = { draft = profile.copy(minCashPercent = it) },
                        )
                    }
                    item {
                        SwitchCard(
                            title = "Критические предупреждения",
                            checked = profile.notifyCritical,
                            onCheckedChange = { draft = profile.copy(notifyCritical = it) },
                        )
                    }
                    item {
                        SwitchCard(
                            title = "Утренний и вечерний обзор",
                            checked = profile.notifyBriefs,
                            onCheckedChange = { draft = profile.copy(notifyBriefs = it) },
                        )
                    }
                    message?.let { text -> item { StatusCard("Сохранение", text, accent = true) } }
                    item {
                        Button(
                            modifier = Modifier.fillMaxWidth(),
                            enabled = !saving,
                            onClick = { saving = true },
                        ) {
                            Text(if (saving) "Сохраняем…" else "Сохранить профиль")
                        }
                    }
                }
            }
        }
    }

    LaunchedEffect(saving) {
        val profile = draft
        if (!saving || profile == null) return@LaunchedEffect
        when (val result = withContext(Dispatchers.IO) { client.saveProfile(accessToken, profile) }) {
            is BackendResult.Success -> {
                draft = result.value
                message = "Профиль сохранён и будет применён к следующим проверкам."
            }
            is BackendResult.Failure -> message = result.message
        }
        saving = false
    }
}

@Composable
private fun AnalysisScaffold(
    selected: AnalystTab,
    title: String,
    subtitle: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier,
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = AnalysisBackground,
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 20.dp, top = 18.dp, end = 20.dp, bottom = 12.dp),
            ) {
                Text(text = title, fontSize = 32.sp, fontWeight = FontWeight.Bold)
                Text(text = subtitle, color = Muted, style = MaterialTheme.typography.bodyMedium)
            }
        },
        bottomBar = {
            AnalystBottomBar(
                selected = selected,
                onPortfolioClick = onPortfolioClick,
                onProfileClick = onProfileClick,
            )
        },
        content = content,
    )
}

@Composable
private fun <T> AnalysisListContent(
    state: LoadingState<T>,
    padding: PaddingValues,
    emptyTitle: String,
    emptyText: String,
    onRetry: () -> Unit,
    onCardRead: suspend (InsightCard) -> Unit,
    cards: (T) -> List<InsightCard>,
) {
    var pendingRead by remember { mutableStateOf<InsightCard?>(null) }
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        when (state) {
            LoadingState.Loading -> item { LoadingCard() }
            is LoadingState.Error -> item { ErrorCard(state.message, onRetry) }
            is LoadingState.Ready -> {
                val entries = cards(state.value)
                if (entries.isEmpty()) {
                    item { StatusCard(emptyTitle, emptyText, accent = false) }
                } else {
                    items(entries, key = { it.id }) { card ->
                        InsightCardView(card = card, onRead = { pendingRead = card })
                    }
                }
            }
        }
    }
    LaunchedEffect(pendingRead?.id) {
        val card = pendingRead ?: return@LaunchedEffect
        onCardRead(card)
        pendingRead = null
    }
}

@Composable
private fun InsightCardView(card: InsightCard, onRead: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            SeverityBadge(card.severity)
            Text(card.title, fontSize = 21.sp, lineHeight = 27.sp, fontWeight = FontWeight.Bold)
            Text(card.summary, color = MaterialTheme.colorScheme.onSurface)
            card.actions.forEach { action -> Text("• $action", color = Muted) }
            if (card.evidence.isNotEmpty()) {
                Text(
                    text = "Источник: ${card.evidence.first().sourceId}",
                    color = Muted,
                    style = MaterialTheme.typography.labelSmall,
                )
            }
            if (!card.isRead) {
                TextButton(onClick = onRead) { Text("Отметить прочитанным") }
            }
        }
    }
}

@Composable
private fun SeverityBadge(severity: String) {
    val color = when (severity) {
        "critical" -> Critical
        "warning" -> Warning
        "watch" -> Blue
        else -> Positive
    }
    Surface(shape = RoundedCornerShape(999.dp), color = color.copy(alpha = 0.12f)) {
        Text(
            text = when (severity) {
                "critical" -> "Критично"
                "warning" -> "Внимание"
                "watch" -> "Наблюдение"
                else -> "Информация"
            },
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
            color = color,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
private fun IdeaCard(idea: AnalysisIdea) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(idea.assetClass, fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Text(
                "Сейчас ${formatPercent(idea.currentPercent)} · ориентир ${formatPercent(idea.targetPercent)}",
                color = Muted,
            )
            Text(
                "Допустимое направление: до ${formatPercent(idea.suggestedMaxPercent)} портфеля",
                color = Blue,
                fontWeight = FontWeight.SemiBold,
            )
            Text(idea.explanation, color = Muted)
        }
    }
}

@Composable
private fun ActionCard(
    title: String,
    text: String,
    buttonText: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Text(text, color = Muted)
            Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth()) {
                Text(buttonText)
            }
        }
    }
}

@Composable
private fun StatusCard(title: String, text: String, accent: Boolean) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold, color = if (accent) Positive else MaterialTheme.colorScheme.onSurface)
            Text(text, color = Muted)
        }
    }
}

@Composable
private fun EmptyCard(text: String) = StatusCard("Проверка источников", text, accent = false)

@Composable
private fun LoadingCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Row(modifier = Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator()
            Spacer(Modifier.width(14.dp))
            Text("Получаем актуальные данные…")
        }
    }
}

@Composable
private fun ErrorCard(message: String, onRetry: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Не удалось загрузить данные", fontWeight = FontWeight.Bold)
            Text(message, color = Critical)
            TextButton(onClick = onRetry) { Text("Повторить") }
        }
    }
}

@Composable
private fun ProfileChoiceCard(
    title: String,
    options: List<Pair<String, String>>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            options.forEach { (value, label) ->
                FilterChip(
                    selected = selected == value,
                    onClick = { onSelect(value) },
                    label = { Text(label) },
                )
            }
        }
    }
}

@Composable
private fun SliderCard(
    title: String,
    value: Double,
    range: ClosedFloatingPointRange<Float>,
    suffix: String,
    onValueChange: (Double) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Text(title, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Text("${value.toInt()}$suffix", color = Blue, fontWeight = FontWeight.Bold)
            Slider(
                value = value.toFloat(),
                onValueChange = { onValueChange(it.toDouble()) },
                valueRange = range,
                steps = ((range.endInclusive - range.start) / 5f).toInt().coerceAtLeast(0),
            )
        }
    }
}

@Composable
private fun SwitchCard(title: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(26.dp),
        colors = CardDefaults.cardColors(containerColor = AnalysisCard),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(title, modifier = Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        }
    }
}

private fun formatPercent(value: Double): String = String.format(java.util.Locale.US, "%.1f%%", value)
