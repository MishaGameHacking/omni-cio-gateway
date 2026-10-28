package ru.omnicio.app.ui.home

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import org.json.JSONObject
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.portfolio.currencySymbol
import ru.omnicio.app.ui.portfolio.decimalText
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

private data class HomeAutomationState(
    val status: JSONObject?,
    val disconnected: Boolean,
    val mode: String,
    val error: String?,
    val title: String,
    val explanation: String,
    val blockers: List<JSONObject>,
    val discovery: JSONObject?,
    val candidates: List<JSONObject>,
    val observation: String,
    val hasObservation: Boolean,
    val loading: Boolean,
)

/** Real capital first; analysis state and its blockers retain their own source/time. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun HomeScreen(user: AnalystUser, state: PortfolioUiState, selectedCurrency: PortfolioCurrency,
    refreshing: Boolean, refreshError: String?, lastUpdatedMillis: Long?, onCurrencyClick: () -> Unit,
    onOpenPortfolio: () -> Unit, onOpenRecommendations: () -> Unit, onOpenRisk: () -> Unit,
    onOpenMessages: () -> Unit, onOpenProfile: () -> Unit,
    modifier: Modifier = Modifier, onConnect: () -> Unit = onOpenProfile,
    onOpenPayments: () -> Unit = onOpenPortfolio) {
    val resource = rememberWorkspaceResource("/automation/status")
    val status = resource.data?.takeIf { it.optInt("schema_version") == 1 }
    val foreground = workspaceForeground()
    val refreshStatus by rememberUpdatedState(resource.refresh)
    LaunchedEffect(foreground) {
        if (foreground) while (isActive) { delay(20_000); refreshStatus() }
    }
    val navigate = LocalWorkspaceNavigator.current
    val broker = LocalBrokerConnection.current
    val automation = homeAutomationState(status, resource.error, resource.busy)

    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Home, onOpenPortfolio, onOpenProfile) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item(key = "system-header") { HomeHeader(onOpenMessages) }
                item(key = "portfolio-overview") {
                    HomePortfolioHero(state, selectedCurrency, refreshing, refreshError,
                        onOpenPortfolio, onConnect)
                }
                item(key = "portfolio-actions") {
                    HomePortfolioActions(onOpenRisk, { navigate(WorkspaceRoute.Strategies) },
                        { navigate(WorkspaceRoute.Assistant) })
                }
                item(key = "automation-state") {
                    HomeAutomationStateCard(automation, broker, resource.busy, resource.refresh,
                        onConnect, onOpenProfile)
                }
                automationBlockersItem(automation, onConnect, onOpenProfile)
                analysisResultsItem(automation, onOpenRecommendations)
                item(key = "system-connections") {
                    HomeSystemConnectionsCard(automation, broker)
                }
                item(key = "system-history") {
                    SpectrumSecondaryButton("История проверок", { navigate(WorkspaceRoute.AnalysisTimeline) },
                        Modifier.fillMaxWidth())
                }
            }
        }
    }
}

private fun homeAutomationState(status: JSONObject?, error: String?, busy: Boolean): HomeAutomationState {
    val disconnected = status?.has("broker_connected") == true && !status.optBoolean("broker_connected")
    val mode = status?.text("state", "") ?: ""
    val title = when {
        error != null -> "Связь требует проверки"
        status == null -> "Получаем состояние"
        else -> automationStateTitle(mode)
    }
    val explanation = when {
        error != null -> "Не удалось обновить состояние системы. Сохранённые сведения могут быть устаревшими."
        status == null -> "Проверяем подключение и работу серверного анализа."
        else -> automationStateDescription(mode)
    }
    val blockers = status?.records("blockers").orEmpty().filterNot { blocker ->
        val code = blocker.text("code", "")
        (disconnected && code in setOf("tinvest_not_connected", "broker_not_connected")) ||
            (mode == "paused" && code in setOf("automation_paused", "paused"))
    }
    val discovery = status?.optJSONObject("discovery")
    val candidates = discovery?.records("candidates").orEmpty()
    val observation = status?.text("last_observation_at", "").orEmpty()
    return HomeAutomationState(
        status = status,
        disconnected = disconnected,
        mode = mode,
        error = error,
        title = title,
        explanation = explanation,
        blockers = blockers,
        discovery = discovery,
        candidates = candidates,
        observation = observation,
        hasObservation = observation.isNotBlank(),
        loading = (busy && status == null) || (mode == "collecting" && error == null),
    )
}

@Composable
private fun HomeHeader(onOpenMessages: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        ru.omnicio.app.ui.AnalystHeaderMenu()
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Analyst AI", style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary)
            Text("Главная", style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() })
            LiveSyncLabel()
        }
        SpectrumIconButton(SpectrumSymbol.Notifications, "События", onOpenMessages)
    }
}

@Composable
private fun HomeAutomationStateCard(
    state: HomeAutomationState,
    broker: BrokerConnectionState,
    busy: Boolean,
    refresh: () -> Unit,
    onConnect: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    SpectrumCard(modifier = Modifier.testTag("automation-state"), emphasized = true) {
        SpectrumBadge(if (state.error != null) "Сведения не обновлены" else "Состояние анализа")
        Text(state.title, style = MaterialTheme.typography.titleLarge,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        Text(state.explanation, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.loading) SpectrumLoadingIndicator(description = state.title)
        if (state.hasObservation) Text("Последняя проверка · " + localMoment(state.observation),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        HomeAutomationAction(state, broker, busy, onConnect, onOpenProfile)
        state.error?.let { currentError ->
            Text(currentError, color = MaterialTheme.colorScheme.error)
            SpectrumSecondaryButton("Повторить проверку связи", refresh,
                Modifier.fillMaxWidth(), enabled = !busy)
        }
    }
}

@Composable
private fun HomeAutomationAction(
    state: HomeAutomationState,
    broker: BrokerConnectionState,
    busy: Boolean,
    onConnect: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    when {
        state.disconnected || broker == BrokerConnectionState.Missing && state.status == null ->
            SpectrumPrimaryButton("Подключить Т-Инвестиции", onConnect, Modifier.fillMaxWidth(),
                enabled = !busy)
        state.mode in setOf("paused", "disabled", "attention") ->
            SpectrumSecondaryButton("Настройки системы", onOpenProfile, Modifier.fillMaxWidth())
    }
}

private fun LazyListScope.automationBlockersItem(
    state: HomeAutomationState,
    onConnect: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    if (state.blockers.isEmpty()) return
    item(key = "automation-blockers") {
        HomeAutomationBlockersCard(state, onConnect, onOpenProfile)
    }
}

@Composable
private fun HomeAutomationBlockersCard(
    state: HomeAutomationState,
    onConnect: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    SpectrumCard(modifier = Modifier.testTag("automation-blockers")) {
        Text("Что мешает работе", style = MaterialTheme.typography.titleLarge)
        state.blockers.take(4).forEach { blocker ->
            blocker.text("message", "").takeIf(String::isNotBlank)?.let { message ->
                Text(message, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (state.blockers.size > 4)
            Text("Другие ограничения доступны в настройках.", style = MaterialTheme.typography.bodySmall)
        SpectrumSecondaryButton(if (state.disconnected) "Настроить подключение" else "Открыть настройки",
            if (state.disconnected) onConnect else onOpenProfile, Modifier.fillMaxWidth())
    }
}

private fun LazyListScope.analysisResultsItem(
    state: HomeAutomationState,
    onOpenRecommendations: () -> Unit,
) {
    if (state.disconnected && !state.hasObservation && state.candidates.isEmpty()) return
    item(key = "analysis-results") {
        HomeAnalysisResultsCard(state, onOpenRecommendations)
    }
}

@Composable
private fun HomeAnalysisResultsCard(state: HomeAutomationState, onOpenRecommendations: () -> Unit) {
    SpectrumCard {
        Text("Результаты", style = MaterialTheme.typography.titleLarge)
        Text(analysisResultMessage(state), color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.candidates.isNotEmpty())
            Text("Проверки, недостающие сведения и основания доступны в решениях.",
                style = MaterialTheme.typography.bodySmall)
        SpectrumPrimaryButton("Посмотреть решения", onOpenRecommendations, Modifier.fillMaxWidth())
    }
}

private fun analysisResultMessage(state: HomeAutomationState): String = when {
    state.status == null -> "Результаты ещё не получены."
    state.candidates.isNotEmpty() -> "Для дальнейшей проверки найдено инструментов: ${state.candidates.size}."
    !state.hasObservation -> "Первый результат появится после подключения и проверки данных."
    state.discovery == null || state.discovery.text("state", "") in setOf("waiting", "not_started", "unavailable") ->
        "Сохранённого результата отбора пока нет."
    else -> "В текущем результате нет инструментов, прошедших предварительный отбор."
}

@Composable
private fun HomeSystemConnectionsCard(state: HomeAutomationState, broker: BrokerConnectionState) {
    SpectrumCard {
        DetailFold("Подключения и режим") {
            SystemStateLine("Брокер", brokerStateText(state, broker))
            SystemStateLine("Автоматический анализ", automationSettingText(state.status))
            SystemStateLine("ИИ", aiStateText(state.status?.optJSONObject("ai")))
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            val execution = state.status?.optJSONObject("execution")
            val readOnly = execution?.text("mode", "") == "read_only" &&
                execution.optBoolean("real_orders_enabled") == false
            Text(if (readOnly) "Режим наблюдения" else "Режим исполнения не подтверждён",
                style = MaterialTheme.typography.titleMedium)
            Text(if (readOnly) "Система анализирует данные. Реальные покупки и продажи не выполняются."
                else "Сведения о режиме исполнения пока недоступны.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun brokerStateText(state: HomeAutomationState, broker: BrokerConnectionState): String = when {
    state.status?.optBoolean("broker_connected") == true -> "Доступ к данным подтверждён"
    state.disconnected -> "Не подключён"
    broker == BrokerConnectionState.Unknown -> "Статус не получен"
    else -> "Проверяем подключение"
}

private fun automationSettingText(status: JSONObject?): String = when {
    status == null -> "Статус не получен"
    !status.optBoolean("enabled") -> "На паузе"
    !status.optBoolean("scheduler_enabled") -> "Ожидает запуска на сервере"
    else -> "Включён"
}

private fun aiStateText(ai: JSONObject?): String = when {
    ai == null -> "Статус не получен"
    ai.optBoolean("available") && ai.optBoolean("live_inference_verified") -> "Последний вызов подтверждён"
    ai.optBoolean("available") -> "Настроен; работа модели ещё не подтверждена"
    else -> "Нужна настройка подключения и лимитов"
}

private fun automationStateTitle(state: String): String = when (state) {
    "paused" -> "Анализ на паузе"
    "not_connected" -> "Нужен доступ к счёту"
    "disabled" -> "Фоновая работа выключена"
    "collecting" -> "Идёт сбор данных"
    "waiting" -> "Ожидаем следующую проверку"
    "attention" -> "Нужно ваше внимание"
    "current" -> "Последний результат сохранён"
    else -> "Состояние не подтверждено"
}

private fun automationStateDescription(state: String): String = when (state) {
    "paused" -> "Автоматический анализ выключен в настройках."
    "not_connected" -> "Подключите данные Т-Инвестиций, чтобы система могла анализировать ваш счёт."
    "disabled" -> "Сервер пока не выполняет автоматический анализ."
    "collecting" -> "Выполняется серверное задание. Результат появится после завершения проверки."
    "waiting" -> "Подтверждённого нового результата пока нет."
    "attention" -> "Проверка выявила ограничение. Его причина показана ниже."
    "current" -> "Можно открыть выводы и проверить их основания."
    else -> "Ожидаем подтверждённые сведения от сервера."
}

@Composable
private fun SystemStateLine(label: String, value: String) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge)
    }
}

/** Retained for existing secondary portfolio views; never composed on the system home. */
@Composable
internal fun InteractiveBalance(amount: MoneyAmount, hidden: Boolean, onCurrency: () -> Unit) {
    HoldToRevealBalance(amount, hidden, onCurrency)
}

@Composable
internal fun HoldToRevealBalance(amount: MoneyAmount, hidden: Boolean, onCurrency: () -> Unit, modifier: Modifier = Modifier) {
    var revealed by remember { mutableStateOf(false) }
    val active = workspaceForeground()
    val select by rememberUpdatedState(onCurrency)
    LaunchedEffect(active, hidden) { revealed = false }
    val text = if (hidden && !(revealed && active)) "••• •••" else
        decimalText(amount.value.toBigDecimal()) + " " + currencySymbol(amount.currency)
    Text(text, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold,
        modifier = modifier.fillMaxWidth().heightIn(min = 56.dp).semantics {
            onClick("Следующая валюта оценки") { select(); true }
        }.pointerInput(hidden, active) {
            detectTapGestures(onTap = { select() }, onLongPress = { if (hidden && active) revealed = true },
                onPress = { try { tryAwaitRelease() } finally { revealed = false } })
        })
}
