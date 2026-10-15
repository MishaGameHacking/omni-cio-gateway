package ru.omnicio.app.ui.analysis

import androidx.activity.compose.LocalActivity
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.analysis.*
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.research.PortfolioResearchPanel
import java.time.Instant

private data class AnalysisData<T>(val value: T? = null, val problem: String? = null,
    val loading: Boolean = true, val stale: Boolean = false)

@Composable
private fun <T> rememberAnalysisData(token: String, reload: Int, fetch: (String) -> BackendResult<T>): State<AnalysisData<T>> {
    val state = remember(token) { mutableStateOf(AnalysisData<T>()) }
    val request by rememberUpdatedState(fetch)
    LaunchedEffect(token, reload) {
        state.value = state.value.copy(loading = true)
        try {
            state.value = when (val result = withContext(Dispatchers.IO) { request(token) }) {
                is BackendResult.Success -> AnalysisData(value = result.value, loading = false)
                is BackendResult.Failure -> AnalysisData(
                    value = state.value.value.takeIf { result.retryable }, problem = result.message,
                    loading = false, stale = result.retryable && state.value.value != null)
            }
        } finally { state.value = state.value.copy(loading = false) }
    }
    return state
}

private fun <T> LazyListScope.loadStatus(state: AnalysisData<T>, onRetry: () -> Unit) {
    if (state.loading) item { LoadingCard() }
    state.problem?.let { problem -> item { ErrorCard(problem, onRetry, enabled = !state.loading) } }
    if (state.stale) item { StatusCard("Предыдущий результат", "Новая загрузка не выполнена. Показанные сведения могли устареть.") }
}

@Composable
fun InsightFeedScreen(accessToken: String, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    modifier: Modifier = Modifier) {
    key(accessToken) {
        val client = remember { AnalysisBackendClient() }
        InsightScreen(accessToken, AnalystTab.Chat, "Сообщения", "Выводы и уведомления Analyst AI",
            "Важных сообщений пока нет", "Система сообщит об изменении состава портфеля, риске или завершённом обзоре.",
            onPortfolioClick, onProfileClick, modifier, client) { token ->
            when (val result = client.fetchFeed(token)) {
                is BackendResult.Success -> BackendResult.Success(result.value.cards)
                is BackendResult.Failure -> result
            }
        }
    }
}

@Composable
fun PulseScreen(accessToken: String, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    modifier: Modifier = Modifier) {
    key(accessToken) {
        val client = remember { AnalysisBackendClient() }
        InsightScreen(accessToken, AnalystTab.Pulse, "События", "Проверки портфеля и важные изменения",
            "Событий пока нет", "Здесь появятся существенные изменения после серверной проверки.",
            onPortfolioClick, onProfileClick, modifier, client, client::fetchPulse)
    }
}

@Composable
private fun InsightScreen(token: String, selected: AnalystTab, title: String, subtitle: String,
    emptyTitle: String, emptyText: String, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    modifier: Modifier, client: AnalysisBackendClient, fetch: (String) -> BackendResult<List<InsightCard>>) {
    var reload by remember { mutableIntStateOf(0) }
    val state by rememberAnalysisData(token, reload, fetch)
    var pendingRead by remember { mutableStateOf<InsightCard?>(null) }
    var readError by remember { mutableStateOf<String?>(null) }
    val now = rememberAnalysisClock()
    AnalysisScaffold(selected, title, subtitle, onPortfolioClick, onProfileClick, modifier) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item { TextButton(onClick = { reload++ }, enabled = !state.loading && pendingRead == null,
                modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Обновить ленту") } }
            loadStatus(state) { reload++ }
            readError?.let { item { StatusCard("Отметка не сохранена", it) } }
            val entries = state.value
            if (entries != null) {
                when {
                    entries.isEmpty() -> item { StatusCard(emptyTitle, emptyText) }
                    entries.any { it.id.isBlank() } || entries.map { it.id }.toSet().size != entries.size ->
                        item { ErrorCard("Идентификаторы сообщений противоречивы. Лента не подменена частичным результатом.", { reload++ }) }
                    else -> items(entries, key = { it.id }) { card ->
                        InsightCardView(card, now, readEnabled = pendingRead == null) { pendingRead = card }
                    }
                }
            }
        }
    }
    LaunchedEffect(pendingRead?.id) {
        val card = pendingRead ?: return@LaunchedEffect
        readError = null
        try {
            when (val result = withContext(Dispatchers.IO) { client.markRead(token, card.id) }) {
                is BackendResult.Success -> reload++
                is BackendResult.Failure -> readError = result.message
            }
        } finally { pendingRead = null }
    }
}

/** The clock does not fetch data or invoke AI; expired messages change label while visible. */
@Composable
private fun rememberAnalysisClock(): Instant {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    var now by remember { mutableStateOf(Instant.now()) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(active) {
        if (!active) return@LaunchedEffect
        while (isActive) { now = Instant.now(); delay(30_000) }
    }
    return now
}

@Composable
fun IdeasScreen(accessToken: String, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    onOpenProfileSettings: () -> Unit, modifier: Modifier = Modifier) {
    key(accessToken) { IdeasContent(accessToken, onPortfolioClick, onProfileClick, onOpenProfileSettings, modifier) }
}

@Composable
private fun IdeasContent(token: String, onPortfolioClick: () -> Unit, onProfileClick: () -> Unit,
    onOpenProfileSettings: () -> Unit, modifier: Modifier) {
    val client = remember { AnalysisBackendClient() }
    var reload by remember { mutableIntStateOf(0) }
    var refreshing by remember { mutableStateOf(false) }
    var refreshMessage by remember { mutableStateOf<String?>(null) }
    val state by rememberAnalysisData(token, reload, client::fetchIdeas)
    AnalysisScaffold(AnalystTab.Ideas, "Рекомендации", "Идеи с учётом вашего портфеля и профиля",
        onPortfolioClick, onProfileClick, modifier) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item { ActionCard("Новые идеи для вас", refreshMessage
                ?: "Проверим портфель, профиль риска и доступные источники. Рекомендации появятся после завершения проверки.",
                if (refreshing) "Отправляем…" else "Обновить", !refreshing) { refreshing = true } }
            loadStatus(state) { reload++ }
            // Preserve the independently loaded, bounded research section from main.
            item(key = "portfolio-research") {
                val navigate = LocalAnalystTabNavigator.current
                SpectrumCard(onClick = { navigate(AnalystTab.Risks) }) {
                    SpectrumHeader("Проверка вашего портфеля", "Сценарии риска и исследования инструментов →", SpectrumSymbol.Risk)
                }
            }
            state.value?.let { payload ->
                item { StatusCard(ideasHeading(payload.state), payload.message, accent = payload.state == "ready") }
                if (payload.state == "profile_required") item {
                    Button(onClick = onOpenProfileSettings, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Настроить профиль риска") }
                }
                items(payload.ideas) { idea -> IdeaCard(idea) }
                if (payload.ideas.isEmpty()) item { StatusCard("Проверка источников",
                    "Конкретные бумаги не показываются, пока они не прошли проверку источников, ликвидности и ограничений профиля.") }
                item { TextButton(onClick = { reload++ }, enabled = !state.loading,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Обновить результаты") } }
            }
        }
    }
    LaunchedEffect(refreshing) {
        if (!refreshing) return@LaunchedEffect
        refreshMessage = null
        try {
            refreshMessage = when (val result = withContext(Dispatchers.IO) { client.refresh(token) }) {
                is BackendResult.Success -> refreshDescription(result.value.state, result.value.model)
                is BackendResult.Failure -> result.message
            }
            reload++
        } finally { refreshing = false }
    }
}

@Composable
fun AnalysisProfileSettingsScreen(accessToken: String, onBack: () -> Unit, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    key(accessToken) { AnalysisProfileContent(accessToken, onBack, onPortfolioClick, onProfileClick, modifier) }
}

@Composable
private fun AnalysisProfileContent(token: String, onBack: () -> Unit, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier) {
    val client = remember { AnalysisBackendClient() }
    var draft by remember { mutableStateOf<AnalysisProfile?>(null) }
    var status by remember { mutableStateOf<AnalysisStatus?>(null) }
    var pendingSave by remember { mutableStateOf<AnalysisProfile?>(null) }
    var loading by remember { mutableStateOf(true) }
    var problem by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var saveFailed by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    LaunchedEffect(reload) {
        loading = true; problem = null; status = null
        try {
            when (val result = withContext(Dispatchers.IO) { client.fetchProfile(token) }) {
                is BackendResult.Success -> draft = result.value
                is BackendResult.Failure -> { problem = result.message; draft = null }
            }
            when (val result = withContext(Dispatchers.IO) { client.fetchStatus(token) }) {
                is BackendResult.Success -> status = result.value
                is BackendResult.Failure -> status = null
            }
        } finally { loading = false }
    }
    AnalysisScaffold(AnalystTab.Profile, "Инвестиционный профиль", "Ограничения применяются алгоритмами до обращения к ИИ.",
        onPortfolioClick, onProfileClick, modifier) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item { TextButton(onClick = onBack, modifier = Modifier.heightIn(min = 48.dp)) { Text("‹ Назад") } }
            if (loading) item { LoadingCard() }
            problem?.let { item { ErrorCard(it, { reload++ }, enabled = !loading) } }
            val profile = draft
            if (profile != null && !loading) {
                item { MonitoringStatus(status) }
                profileControls(profile, enabled = pendingSave == null) { draft = it }
                message?.let { text -> item { StatusCard(if (saveFailed) "Не удалось сохранить" else "Сохранение", text) } }
                val valid = profileLimitsValid(profile.maxPositionPercent, profile.minCashPercent)
                    && profile.riskLevel in setOf("conservative", "moderate", "aggressive")
                    && profile.horizon in setOf("short", "medium", "long")
                if (!valid) item { ErrorCard("Профиль содержит неподдерживаемые настройки. Повторите загрузку.", { reload++ }, pendingSave == null) }
                item { Button(onClick = { pendingSave = profile }, enabled = pendingSave == null && valid,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                    Text(if (pendingSave != null) "Сохраняем…" else "Сохранить профиль")
                } }
            }
        }
    }
    LaunchedEffect(pendingSave) {
        val submitted = pendingSave ?: return@LaunchedEffect
        message = null; saveFailed = false
        try {
            when (val result = withContext(Dispatchers.IO) { client.saveProfile(token, submitted) }) {
                is BackendResult.Success -> { draft = result.value; message = "Профиль сохранён и будет применён к следующим проверкам." }
                is BackendResult.Failure -> { saveFailed = true; message = result.message }
            }
        } finally { pendingSave = null }
    }
}

@Composable
private fun MonitoringStatus(status: AnalysisStatus?) {
    val title = when {
        status == null -> "Состояние сервера не получено"
        !status.schedulerEnabled -> "Фоновая обработка отключена"
        status.deterministicMonitoring -> "Сервер сообщает о фоновом контроле"
        else -> "Фоновый контроль не подтверждён"
    }
    val text = if (status?.aiConfigured == true)
        "Конфигурация модели присутствует. Это не доказательство выполненного вызова. Расходы ограничиваются сервером."
    else "Подключение модели не подтверждено. Не считаем настройку или отсутствие сообщений доказательством безопасности портфеля."
    StatusCard(title, text)
}

private fun LazyListScope.profileControls(profile: AnalysisProfile, enabled: Boolean, onChange: (AnalysisProfile) -> Unit) {
    item { ProfileChoiceCard("Уровень риска", listOf("conservative" to "Консервативный", "moderate" to "Умеренный", "aggressive" to "Агрессивный"),
        profile.riskLevel, enabled) { onChange(profile.copy(riskLevel = it)) } }
    item { ProfileChoiceCard("Горизонт", listOf("short" to "До года", "medium" to "1–3 года", "long" to "Более 3 лет"),
        profile.horizon, enabled) { onChange(profile.copy(horizon = it)) } }
    item { SliderCard("Максимальная доля позиции", profile.maxPositionPercent, 5f..60f, enabled) { onChange(profile.copy(maxPositionPercent = it)) } }
    item { SliderCard("Минимальный денежный резерв", profile.minCashPercent, 0f..50f, enabled) { onChange(profile.copy(minCashPercent = it)) } }
    item { SwitchCard("Критические предупреждения", profile.notifyCritical, enabled) { onChange(profile.copy(notifyCritical = it)) } }
    item { SwitchCard("Утренний и вечерний обзор", profile.notifyBriefs, enabled) { onChange(profile.copy(notifyBriefs = it)) } }
}