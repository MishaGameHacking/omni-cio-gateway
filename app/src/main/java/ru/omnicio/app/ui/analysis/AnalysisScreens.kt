package ru.omnicio.app.ui.analysis

import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.saveable.rememberSaveable
import ru.omnicio.app.ui.spectrum.SpectrumTabs
import ru.omnicio.app.ui.workspace.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import java.time.Instant
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.analysis.AnalysisBackendClient
import ru.omnicio.app.data.analysis.AnalysisProfile
import ru.omnicio.app.data.analysis.AnalysisStatus
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.research.PortfolioResearchPanel
import ru.omnicio.app.ui.spectrum.SpectrumPrimaryButton
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

private data class AnalysisData<T>(
    val value: T? = null,
    val problem: String? = null,
    val loading: Boolean = true,
    val stale: Boolean = false,
)

@Composable
private fun <T> rememberAnalysisData(
    token: String,
    reload: Int,
    fetch: (String) -> BackendResult<T>,
): State<AnalysisData<T>> {
    val state = remember(token) { mutableStateOf(AnalysisData<T>()) }
    val request by rememberUpdatedState(fetch)
    LaunchedEffect(token, reload) {
        state.value = state.value.copy(loading = true)
        try {
            state.value = when (val result = withContext(Dispatchers.IO) { request(token) }) {
                is BackendResult.Success -> AnalysisData(value = result.value, loading = false)
                is BackendResult.Failure -> AnalysisData(
                    value = state.value.value.takeIf { result.retryable },
                    problem = result.message,
                    loading = false,
                    stale = result.retryable && state.value.value != null,
                )
            }
        } finally {
            state.value = state.value.copy(loading = false)
        }
    }
    return state
}

private fun <T> LazyListScope.loadStatus(state: AnalysisData<T>, onRetry: () -> Unit) {
    if (state.loading) item { LoadingCard() }
    state.problem?.let { problem ->
        item { ErrorCard(problem, onRetry, enabled = !state.loading) }
    }
    if (state.stale) {
        item {
            StatusCard(
                "Предыдущий результат",
                "Новая загрузка не выполнена. Показанные сведения могли устареть.",
            )
        }
    }
}

@Composable
fun InsightFeedScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
    initialCardId: String? = null,
) {
    key(accessToken) {
        val client = remember { AnalysisBackendClient() }
        InsightScreen(
            token = accessToken,
            selected = AnalystTab.Home,
            title = "Отчёты Analyst AI",
            subtitle = "Выводы, подтверждения и срок актуальности",
            symbol = SpectrumSymbol.Analyst,
            emptyTitle = "Отчётов пока нет",
            emptyText = "Здесь появятся сохранённые выводы после анализа данных портфеля.",
            onPortfolioClick = onPortfolioClick,
            onProfileClick = onProfileClick,
            modifier = modifier,
            client = client,
            initialCardId = initialCardId,
            fetch = { token ->
                when (val result = client.fetchFeed(token)) {
                    is BackendResult.Success -> BackendResult.Success(result.value.cards)
                    is BackendResult.Failure -> result
                }
            },
        )
    }
}

@Composable
fun PulseScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    key(accessToken) {
        val client = remember { AnalysisBackendClient() }
        InsightScreen(
            token = accessToken,
            selected = AnalystTab.Risk,
            title = "Риски",
            subtitle = "Внимание к капиталу",
            symbol = SpectrumSymbol.Risk,
            emptyTitle = "Новых сигналов риска нет",
            emptyText = "Это не означает отсутствие риска. Следующая проверка появится после существенного изменения данных.",
            onPortfolioClick = onPortfolioClick,
            onProfileClick = onProfileClick,
            modifier = modifier,
            client = client,
            fetch = client::fetchPulse,
        )
    }
}

@Composable
private fun InsightScreen(
    token: String,
    selected: AnalystTab,
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    emptyTitle: String,
    emptyText: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier,
    client: AnalysisBackendClient,
    fetch: (String) -> BackendResult<List<InsightCard>>,
    initialCardId: String? = null,
) {
    var reload by remember { mutableIntStateOf(0) }
    val state by rememberAnalysisData(token, reload, fetch)
    var pendingRead by remember { mutableStateOf<InsightCard?>(null) }
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    var readError by remember { mutableStateOf<String?>(null) }
    var requestedCardHandled by rememberSaveable(initialCardId) { mutableStateOf(false) }
    var requestedCardProblem by remember(initialCardId) { mutableStateOf<String?>(null) }
    LaunchedEffect(initialCardId, state.value, state.loading, state.problem) {
        val requested = initialCardId ?: return@LaunchedEffect
        if (requestedCardHandled || state.loading || state.problem != null) return@LaunchedEffect
        val loaded = state.value ?: return@LaunchedEffect
        if (requested.isBlank() || loaded.any { it.id.isBlank() } || loaded.map { it.id }.toSet().size != loaded.size) {
            requestedCardProblem = "Не удалось однозначно проверить ссылку на отчёт. Обновите список."
            return@LaunchedEffect
        }
        // Resolve against the authenticated loaded feed. An incoming identifier
        // must never create a placeholder card or mark any card as read.
        val card = loaded.singleOrNull { it.id == requested }
        if (card == null) {
            requestedCardProblem = "Этот отчёт отсутствует в загруженной части ленты. Обновите список; более ранние записи могут быть недоступны через этот экран."
        } else {
            selectedId = card.id
            requestedCardHandled = true
            requestedCardProblem = null
        }
    }
    val now = rememberAnalysisClock()
    AnalysisScaffold(
        selected = selected,
        title = title,
        subtitle = subtitle,
        symbol = symbol,
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap),
        ) {
            item(key = "filters") {
                SpectrumTabs(if (selected == AnalystTab.Risk) listOf("Обзор", "Активные", "История")
                    else listOf("Внимание", "Информация", "История"), section, { section = it })
            }
            item(key = "refresh") {
                SpectrumSecondaryButton(
                    text = if (state.loading) "Обновляем…" else "Проверить обновления",
                    onClick = { reload++ },
                    enabled = !state.loading && pendingRead == null,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            loadStatus(state) { reload++ }
            requestedCardProblem?.let {
                item(key = "requested-card-missing") { StatusCard("Отчёт не открыт", it) }
            }
            readError?.let {
                item(key = "read-error") { StatusCard("Отметка не сохранена", it) }
            }
            val entries = state.value
            if (entries != null) {
                val riskOverview = selected == AnalystTab.Risk && section == 0
                if (riskOverview) {
                    item(key = "overview") { RiskOverviewCard(entries.filter { insightActive(it, now) }) }
                    item(key = "coverage") { RiskCoverageCard() }
                    item(key = "open-signals") {
                        WorkspaceLink("Активные сигналы", "Актуальность проверяется отдельно от прочтения", SpectrumSymbol.Risk) { section = 1 }
                    }
                } else {
                    val visible = visibleInsights(entries, selected, section, now)
                    when {
                        entries.any { it.id.isBlank() } || entries.map { it.id }.toSet().size != entries.size -> {
                            item(key = "invalid") { ErrorCard("Не удалось проверить список событий.", { reload++ }) }
                        }
                        visible.isEmpty() -> item(key = "empty") { StatusCard(emptyTitle, emptyText) }
                        else -> items(visible, key = { it.id }) { card -> InsightPreview(card, now) { selectedId = card.id } }
                    }
                }
            }
        }
    }
    state.value?.firstOrNull { it.id == selectedId }?.let { card ->
        InsightDetails(card, now, pendingRead == null, { pendingRead = card }, { selectedId = null })
    }
    LaunchedEffect(pendingRead?.id) {
        val card = pendingRead ?: return@LaunchedEffect
        readError = null
        try {
            when (val result = withContext(Dispatchers.IO) { client.markRead(token, card.id) }) {
                is BackendResult.Success -> reload++
                is BackendResult.Failure -> readError = result.message
            }
        } finally {
            pendingRead = null
        }
    }
}

/** The clock does not fetch data or invoke AI; expired messages change label while visible. */
@Composable
private fun rememberAnalysisClock(): Instant {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) {
        mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false)
    }
    var now by remember { mutableStateOf(Instant.now()) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(active) {
        if (!active) return@LaunchedEffect
        while (isActive) {
            now = Instant.now()
            delay(30_000)
        }
    }
    return now
}

@Composable
fun IdeasScreen(
    accessToken: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    onOpenProfileSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    key(accessToken) {
        IdeasContent(
            token = accessToken,
            onPortfolioClick = onPortfolioClick,
            onProfileClick = onProfileClick,
            onOpenProfileSettings = onOpenProfileSettings,
            modifier = modifier,
        )
    }
}

@Composable
private fun IdeasContent(
    token: String,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    onOpenProfileSettings: () -> Unit,
    modifier: Modifier,
) {
    val client = remember { AnalysisBackendClient() }
    var reload by remember { mutableIntStateOf(1) }
    var refreshing by remember { mutableStateOf(false) }
    var refreshMessage by remember { mutableStateOf<String?>(null) }
    val state by rememberAnalysisData(token, reload, client::fetchIdeas)
    var section by rememberSaveable { mutableIntStateOf(0) }
    AnalysisScaffold(
        selected = AnalystTab.Actions,
        title = "Действия",
        subtitle = "Один понятный следующий шаг",
        symbol = SpectrumSymbol.Ideas,
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap),
        ) {
            item(key = "action-sections") {
                SpectrumTabs(listOf("План", "Анализ"), section, { section = it })
            }
            if (section == 0) {
                item(key = "execution-readiness") {
                    ActionPlan(actions = null)
                }
                item(key = "open-analysis") {
                    SpectrumPrimaryButton("Посмотреть анализ", { section = 1 }, Modifier.fillMaxWidth())
                }
            }
            if (section == 1) {
            item(key = "refresh-analysis") {
                ActionCard(
                    title = "Обновить портфель и анализ",
                    text = refreshMessage
                        ?: "Получите свежий обзор по данным вашего портфеля.",
                    buttonText = if (refreshing) "Отправляем…" else "Обновить",
                    enabled = !refreshing,
                ) {
                    refreshing = true
                }
            }
            loadStatus(state) { reload++ }
            item(key = "portfolio-research") { PortfolioResearchPanel(token, showRefresh = false, refreshKey = reload) }
            state.value?.let { payload ->
                item(key = "state") {
                    StatusCard(
                        ideasHeading(payload.state),
                        payload.message,
                        accent = payload.state == "ready",
                    )
                }
                if (payload.state == "profile_required") {
                    item(key = "profile-required") {
                        SpectrumPrimaryButton(
                            text = "Настроить профиль риска",
                            onClick = onOpenProfileSettings,
                            modifier = Modifier.fillMaxWidth(),
                            symbol = SpectrumSymbol.Profile,
                        )
                    }
                }
                items(payload.ideas) { idea -> IdeaCard(idea) }
                if (payload.ideas.isEmpty()) {
                    item(key = "source-check") {
                        StatusCard(
                            "Проверка источников",
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
        refreshMessage = null
        try {
            refreshMessage = when (val result = withContext(Dispatchers.IO) { client.refresh(token) }) {
                is BackendResult.Success -> refreshDescription(result.value.state, result.value.model)
                is BackendResult.Failure -> result.message
            }
            reload++
        } finally {
            refreshing = false
        }
    }
}

@Composable
fun AnalysisProfileSettingsScreen(
    accessToken: String,
    onBack: () -> Unit,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
    initialSection: Int = 0,
) {
    key(accessToken) {
        AnalysisProfileContent(
            token = accessToken,
            onBack = onBack,
            onPortfolioClick = onPortfolioClick,
            onProfileClick = onProfileClick,
            modifier = modifier,
            initialSection = initialSection,
        )
    }
}

@Composable
private fun AnalysisProfileContent(
    token: String,
    onBack: () -> Unit,
    onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit,
    modifier: Modifier,
    initialSection: Int,
) {
    var section by rememberSaveable { mutableIntStateOf(initialSection.coerceIn(0, 2)) }
    val client = remember { AnalysisBackendClient() }
    var baseline by remember { mutableStateOf<AnalysisProfile?>(null) }
    var leaving by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf<AnalysisProfile?>(null) }
    var status by remember { mutableStateOf<AnalysisStatus?>(null) }
    var pendingSave by remember { mutableStateOf<AnalysisProfile?>(null) }
    var loading by remember { mutableStateOf(true) }
    var problem by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var saveFailed by remember { mutableStateOf(false) }
    var reload by remember { mutableIntStateOf(0) }
    val dirty = draft != null && draft != baseline
    val leave: () -> Unit = { if (dirty) leaving = true else onBack() }
    BackHandler(onBack = leave)
    LaunchedEffect(reload) {
        loading = true
        problem = null
        status = null
        try {
            when (val result = withContext(Dispatchers.IO) { client.fetchProfile(token) }) {
                is BackendResult.Success -> { draft = result.value; baseline = result.value }
                is BackendResult.Failure -> {
                    problem = result.message
                    draft = null
                }
            }
            when (val result = withContext(Dispatchers.IO) { client.fetchStatus(token) }) {
                is BackendResult.Success -> status = result.value
                is BackendResult.Failure -> status = null
            }
        } finally {
            loading = false
        }
    }
    AnalysisScaffold(
        selected = AnalystTab.Profile,
        title = "Инвестиционный профиль",
        subtitle = "Действующие настройки анализа",
        symbol = SpectrumSymbol.Profile,
        onPortfolioClick = onPortfolioClick,
        onProfileClick = onProfileClick,
        modifier = modifier,
        showBottomBar = false,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap),
        ) {
            item(key = "back") {
                SpectrumSecondaryButton(
                    text = "Назад",
                    onClick = leave,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            if (loading) item { LoadingCard() }
            problem?.let { item { ErrorCard(it, { reload++ }, enabled = !loading) } }
            val profile = draft
            if (profile != null && !loading) {
                item { SpectrumTabs(listOf("Правила", "Уведомления", "Наблюдение"), section, { section = it }) }
                if (section == 2) item { MonitoringStatus(status) }
                if (section == 1) item { NotificationDeliverySettingsLink(enabled = !dirty && pendingSave == null) }
                profileControls(profile, section, enabled = pendingSave == null) { draft = it }
                message?.let { text ->
                    item {
                        StatusCard(
                            if (saveFailed) "Не удалось сохранить" else "Сохранение",
                            text,
                        )
                    }
                }
                val valid = supportedProfile(profile)
                if (!valid) {
                    item {
                        ErrorCard(
                            "Профиль содержит неподдерживаемые настройки. Повторите загрузку.",
                            { reload++ },
                            pendingSave == null,
                        )
                    }
                }
                if (dirty) item { Text("Есть несохранённые изменения. Они применятся к следующим проверкам после сохранения.") }
                item(key = "save") {
                    SpectrumPrimaryButton(
                        text = if (pendingSave != null) "Сохраняем…" else "Сохранить профиль",
                        onClick = { pendingSave = profile },
                        enabled = pendingSave == null && valid && dirty,
                        modifier = Modifier.fillMaxWidth(),
                        symbol = SpectrumSymbol.Analyst,
                    )
                }
            }
        }
    }
    if (leaving) WorkspaceDialog("Есть несохранённые изменения", onDismiss = { leaving = false }) {
        Text("Вернитесь к настройкам и сохраните профиль либо выйдите без изменений.")
        SpectrumSecondaryButton("Продолжить настройку", { leaving = false }, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Не сохранять", onBack, Modifier.fillMaxWidth(), enabled = pendingSave == null)
    }

    LaunchedEffect(pendingSave) {
        val submitted = pendingSave ?: return@LaunchedEffect
        message = null
        saveFailed = false
        try {
            when (val result = withContext(Dispatchers.IO) { client.saveProfile(token, submitted) }) {
                is BackendResult.Success -> {
                    draft = result.value
                    baseline = result.value
                    message = "Профиль сохранён и будет применён к следующим проверкам."
                }
                is BackendResult.Failure -> {
                    saveFailed = true
                    message = result.message
                }
            }
        } finally {
            pendingSave = null
        }
    }
}

@Composable
private fun MonitoringStatus(status: AnalysisStatus?) {
    val monitoring = status?.monitoring
    val title = when (monitoring?.state) {
        "current" -> "Сервер получает данные портфеля"
        "waiting" -> "Ожидается первая проверка"
        "delayed" -> "Проверка портфеля задерживается"
        "check_failed" -> "Последняя проверка не завершена"
        "not_connected" -> "Подключите портфель"
        "disabled" -> "Фоновая обработка отключена"
        else -> "Состояние наблюдения не получено"
    }
    val description = when (monitoring?.state) {
        "not_connected" -> "Подключите T‑API в профиле."
        "disabled" -> "Серверный планировщик отключён. Автоматические проверки не выполняются."
        "delayed", "check_failed" -> "Последние данные сохранены. Свежая проверка ещё не подтверждена."
        "current", "waiting" -> "Проверка выполняется на сервере и не зависит от открытого приложения."
        else -> "Обновите экран, чтобы получить состояние сервера."
    }
    val observed = analysisTime(monitoring?.lastSnapshotAt)
    val text = if (observed == null) description else "$description\nПоследние данные: $observed."
    StatusCard(title, text)
}

private fun LazyListScope.profileControls(
    profile: AnalysisProfile,
    section: Int,
    enabled: Boolean,
    onChange: (AnalysisProfile) -> Unit,
) {
    if (section == 0) {
    item {
        ProfileChoiceCard(
            "Уровень риска",
            listOf(
                "conservative" to "Консервативный",
                "moderate" to "Умеренный",
                "aggressive" to "Агрессивный",
            ),
            profile.riskLevel,
            enabled,
        ) {
            onChange(profile.copy(riskLevel = it))
        }
    }
    item {
        ProfileChoiceCard(
            "Горизонт",
            listOf(
                "short" to "До года",
                "medium" to "1–3 года",
                "long" to "Более 3 лет",
            ),
            profile.horizon,
            enabled,
        ) {
            onChange(profile.copy(horizon = it))
        }
    }
    item {
        SliderCard(
            "Максимальная доля позиции",
            profile.maxPositionPercent,
            5f..60f,
            enabled,
        ) {
            onChange(profile.copy(maxPositionPercent = it))
        }
    }
    item {
        SliderCard(
            "Минимальный денежный резерв",
            profile.minCashPercent,
            0f..50f,
            enabled,
        ) {
            onChange(profile.copy(minCashPercent = it))
        }
    }
    }
    if (section == 1) {
    item {
        SwitchCard("Критические предупреждения", profile.notifyCritical, enabled) {
            onChange(profile.copy(notifyCritical = it))
        }
    }
    item {
        SwitchCard("Утренний и вечерний обзор", profile.notifyBriefs, enabled) {
            onChange(profile.copy(notifyBriefs = it))
        }
    }
    }
}

internal fun visibleInsights(entries: List<InsightCard>, selected: AnalystTab, section: Int, now: Instant): List<InsightCard> =
    entries.filter { card ->
        val active = insightActive(card, now)
        if (selected == AnalystTab.Risk) { if (section == 1) active else !active }
        else when (section) {
            0 -> active && !card.isRead && card.severity in setOf("critical", "warning")
            1 -> active && !card.isRead && card.severity !in setOf("critical", "warning")
            else -> card.isRead || !active
        }
    }.sortedWith(compareBy<InsightCard> { when (it.severity) { "critical" -> 0; "warning" -> 1; else -> 2 } }.thenByDescending { it.createdAt })

private fun supportedProfile(profile: AnalysisProfile): Boolean =
    profileLimitsValid(profile.maxPositionPercent, profile.minCashPercent) &&
        profile.riskLevel in setOf("conservative", "moderate", "aggressive") &&
        profile.horizon in setOf("short", "medium", "long")
