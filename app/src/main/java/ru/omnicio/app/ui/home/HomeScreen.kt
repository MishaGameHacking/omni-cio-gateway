package ru.omnicio.app.ui.home

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
    val disconnected = status?.has("broker_connected") == true && !status.optBoolean("broker_connected")
    val mode = status?.text("state", "") ?: ""
    val blockers = status?.records("blockers").orEmpty().filterNot { blocker ->
        val code = blocker.text("code", "")
        (disconnected && code in setOf("tinvest_not_connected", "broker_not_connected")) ||
            (mode == "paused" && code in setOf("automation_paused", "paused"))
    }

    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Home, onOpenPortfolio, onOpenProfile) }) { padding ->
            LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item(key = "system-header") {
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
                item(key = "portfolio-overview") {
                    HomePortfolioHero(state, selectedCurrency, refreshing, refreshError,
                        onOpenPortfolio, onConnect)
                }
                item(key = "portfolio-actions") {
                    HomePortfolioActions(onOpenRisk, { navigate(WorkspaceRoute.Strategies) },
                        { navigate(WorkspaceRoute.Assistant) })
                }
                item(key = "automation-state") {
                    HomeAutomationCard(status, resource.error, resource.busy, resource.refresh,
                        onOpenRecommendations, onConnect)
                }
                if (blockers.isNotEmpty()) item(key = "automation-blockers") {
                    SpectrumCard(modifier = Modifier.testTag("automation-blockers")) {
                        Text("Требует внимания", style = MaterialTheme.typography.titleMedium)
                        Text(blockers.first().text("message", "Проверьте настройки системы."),
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                        SpectrumTextButton(if (disconnected) "Подключение" else "Настройки",
                            if (disconnected) onConnect else onOpenProfile,
                            Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Forward)
                    }
                }
            }
        }
    }
}

@Composable
private fun HomeAutomationCard(status: JSONObject?, error: String?, busy: Boolean, refresh: () -> Unit,
    onOpenRecommendations: () -> Unit, onConnect: () -> Unit) {
    val broker = LocalBrokerConnection.current
    val disconnected = status?.has("broker_connected") == true && !status.optBoolean("broker_connected")
    val mode = status?.text("state", "") ?: ""
    val currentError = error
    val title = when {
        currentError != null -> "Связь требует проверки"
        status == null -> "Получаем состояние"
        else -> automationStateTitle(mode)
    }
    val explanation = when {
        currentError != null -> "Не удалось обновить состояние системы. Сохранённые сведения могут быть устаревшими."
        status == null -> "Проверяем подключение и работу серверного анализа."
        else -> automationStateDescription(mode)
    }
    val discovery = status?.optJSONObject("discovery")
    val candidates = discovery?.records("candidates").orEmpty()
    val observation = status?.text("last_observation_at", "").orEmpty()
    val hasObservation = observation.isNotBlank()
    val loading = busy && status == null || mode == "collecting" && currentError == null

    SpectrumCard(modifier = Modifier.testTag("automation-state")) {
        Text("Сегодня", style = MaterialTheme.typography.titleLarge)
        Text(title, style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        if (loading) SpectrumLoadingIndicator(description = title)
        if (currentError != null || mode != "current")
            Text(explanation, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val currentCount = candidates.count { it.optBoolean("evidence_current", false) }
        Text(if (currentCount > 0) "Актуальных результатов: $currentCount"
            else "Новых проверенных решений пока нет.",
            style = MaterialTheme.typography.bodyMedium)
        if (hasObservation) Text("Проверка · " + localMoment(observation),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        SpectrumTextButton("Открыть решения", onOpenRecommendations,
            Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Forward)
        if (disconnected || broker == BrokerConnectionState.Missing && status == null)
            SpectrumPrimaryButton("Подключить Т-Инвестиции", onConnect,
                Modifier.fillMaxWidth(), enabled = !busy)
        if (currentError != null) SpectrumSecondaryButton("Повторить проверку связи",
            refresh, Modifier.fillMaxWidth(), enabled = !busy)
    }
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
