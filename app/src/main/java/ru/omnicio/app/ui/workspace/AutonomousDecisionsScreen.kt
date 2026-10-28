package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator

/** Three independent views. Reading them never starts paid analysis or an order. */
@Composable
fun AutonomousDecisionsScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/automation/decisions")
    val data = resource.data
    val discovery = data?.optJSONObject("discovery")
    val views = data?.optJSONObject("views")
    val current = views?.records("current")
        ?: discovery?.records("candidates").orEmpty().filter { it.optBoolean("evidence_current", false) }
    val pending = views?.records("pending").orEmpty()
    val history = views?.records("history") ?: data?.records("events").orEmpty()
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var selectedId by rememberSaveable { mutableStateOf<String?>(null) }
    val selected = (current + pending).firstOrNull { it.text("instrument_uid", "") == selectedId }
    WorkspaceDetailPage("Решения", "Результаты, проверка данных и журнал", onBack, SpectrumSymbol.Goal) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTabs(listOf("Актуально", "Проверка", "История"), tab,
                { tab = it }, Modifier.padding(horizontal = 20.dp))
            Box(Modifier.weight(1f).fillMaxWidth()) {
                key(tab) {
                    if (tab == 2) DecisionHistory(history, data != null) { WorkspaceRequestState(resource) }
                    else DecisionCandidates(tab, if (tab == 0) current else pending,
                        data?.records("blockers").orEmpty(), discovery?.text("state", "unknown"),
                        data != null && !resource.busy, { selectedId = it }) { WorkspaceRequestState(resource) }
                }
            }
        }
    }
    if (selectedId != null) WorkspaceDialog("Проверка инструмента", { selectedId = null }) {
        if (selected != null) ResearchCandidateDetails(selected)
        else Text("Результат обновлён или больше не актуален. Откройте текущий список.")
        SpectrumSecondaryButton("К списку", { selectedId = null }, Modifier.fillMaxWidth())
    }
}

private fun decisionListModifier() = Modifier.fillMaxSize()
    .semantics { testTagsAsResourceId = true }.testTag("workspace-content")

@Composable
private fun DecisionCandidates(tab: Int, rows: List<JSONObject>, blockers: List<JSONObject>,
    state: String?, loaded: Boolean, onSelect: (String) -> Unit,
    requestState: @Composable () -> Unit) {
    LazyColumn(decisionListModifier(), contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item { requestState() }
        item {
            Text(if (tab == 0) "На текущих данных · ${rows.size}" else "Ожидают обновления · ${rows.size}",
                style = MaterialTheme.typography.titleLarge)
            Text(if (tab == 0) "Кандидаты для исследования. Покупки и продажи не выполняются."
                else "Сервер повторит проверку. Устаревшие сведения не считаются актуальным решением.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (tab == 0 && blockers.isNotEmpty()) item { DecisionBlockers(blockers) }
        if (rows.isEmpty() && loaded) item {
            SpectrumCard {
                Text(if (tab == 0) "Новых решений пока нет" else "Очередь проверок пуста",
                    style = MaterialTheme.typography.titleMedium)
                Text(discoverySummary(state), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        items(rows, key = { it.text("instrument_uid", it.toString()) }) { row ->
            SpectrumCard(onClick = { onSelect(row.text("instrument_uid", "")) }) {
                Text(row.text("name", "Инструмент"), style = MaterialTheme.typography.titleMedium)
                Text(row.text("ticker", ""), style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary)
                Text(if (tab == 0) "Открыть проверку и основания" else "Обновление данных · открыть детали",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun DecisionBlockers(blockers: List<JSONObject>) {
    val navigate = LocalWorkspaceNavigator.current
    val navigateTab = LocalAnalystTabNavigator.current
    SpectrumCard {
        Text("Для продолжения", style = MaterialTheme.typography.titleMedium)
        blockers.take(3).forEach { Text(it.text("message", "")) }
        val strategy = blockers.any { it.text("code", "") == "strategy_required" }
        SpectrumSecondaryButton(if (strategy) "Выбрать стратегию" else "Настройки",
            { if (strategy) navigate(WorkspaceRoute.Strategies) else navigateTab(AnalystTab.Profile) },
            Modifier.fillMaxWidth())
    }
}

@Composable
private fun DecisionHistory(history: List<JSONObject>, loaded: Boolean,
    requestState: @Composable () -> Unit) {
    LazyColumn(decisionListModifier(), contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item { requestState() }
        item { Text("Журнал за 30 дней", style = MaterialTheme.typography.titleLarge) }
        if (history.isEmpty() && loaded) item { Text("Событий за этот период нет.") }
        items(history, key = { it.text("id", it.toString()) }) { event ->
            SpectrumCard {
                Text(event.text("title", "Результат анализа"), style = MaterialTheme.typography.titleMedium)
                Text(event.text("summary", ""), color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(localMoment(event.text("at", "")), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ResearchCandidateDetails(candidate: JSONObject) {
    SpectrumCard {
        val ticker = candidate.text("ticker", "")
        Text(candidate.text("name", ticker.ifBlank { "Инструмент" }),
            style = MaterialTheme.typography.titleLarge)
        if (ticker.isNotBlank()) Text(ticker, color = MaterialTheme.colorScheme.primary,
            style = MaterialTheme.typography.labelLarge)
        Text(if (candidate.optBoolean("evidence_current", false))
            "Кандидат для исследования" else "Данные кандидата требуют обновления",
            style = MaterialTheme.typography.titleMedium)
        Text("Отбор по правилам ещё не означает готовую рекомендацию.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        DetailFold("Почему инструмент попал в отбор") {
            candidate.records("checks").forEach { check ->
                val prefix = when (check.text("state", "")) {
                    "passed" -> "Проверено: "
                    "blocked" -> "Ограничение: "
                    else -> "Нет подтверждения: "
                }
                check.text("message", "").takeIf(String::isNotBlank)?.let { Text(prefix + it) }
            }
            val missing = candidate.optJSONArray("missing_evidence")
            if (missing != null && missing.length() > 0) {
                Text("Осталось проверить", style = MaterialTheme.typography.titleMedium)
                for (index in 0 until missing.length()) {
                    Text(missingEvidenceLabel(missing.optString(index)),
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            candidate.text("as_of", "").takeIf(String::isNotBlank)?.let {
                Text("Данные получены " + relativeObservation(it), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

internal fun discoverySummary(state: String?): String = when (state) {
    "running" -> "Сервер проверяет инструменты по вашей стратегии."
    "partial" -> "Часть инструментов проверена. Полнота отбора указана в результатах."
    "blocked" -> "Для продолжения нужны данные или настройки."
    "failed" -> "Последняя проверка не завершилась. Причина сохранена на сервере."
    "stale" -> "Предыдущий результат устарел и требует новой проверки."
    "waiting" -> "Ожидается серверная проверка."
    else -> "Статус анализа пока не получен."
}

private fun missingEvidenceLabel(code: String): String = when (code) {
    "loss_capacity_and_full_investment_profile" -> "Допустимые потери и полный инвестиционный профиль."
    "investment_thesis_and_valuation" -> "Обоснование выбора и оценка стоимости."
    "tax_and_settlement_effects" -> "Налоги и условия расчётов."
    "credit_rating", "credit_evidence_missing" -> "Подтверждённый кредитный рейтинг."
    "fresh_price", "price_stale" -> "Актуальную рыночную цену."
    else -> "Дополнительные данные и обоснование выбора."
}
