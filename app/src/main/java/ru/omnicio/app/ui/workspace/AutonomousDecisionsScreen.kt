package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator

/** Server-prepared observations. Reading this screen never starts analysis or an order. */
@Composable
fun AutonomousDecisionsScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/automation/decisions")
    val navigate = LocalWorkspaceNavigator.current
    val navigateTab = LocalAnalystTabNavigator.current
    val data = resource.data
    val discovery = data?.optJSONObject("discovery")
    val candidates = discovery?.records("candidates").orEmpty()
    val events = data?.records("events").orEmpty()
    WorkspaceDetailPage("Решения", "Проверки и результаты анализа", onBack, SpectrumSymbol.Goal) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
            contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap),
        ) {
            item { WorkspaceRequestState(resource) }
            item {
                SpectrumCard(emphasized = true) {
                    Text("Автоматический отбор", style = MaterialTheme.typography.titleLarge,
                        modifier = Modifier.semantics { heading() })
                    Text(discoverySummary(discovery?.text("state", "unknown")),
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    discovery?.text("as_of", "")?.takeIf(String::isNotBlank)?.let {
                        Text("Последний результат: " + relativeObservation(it),
                            style = MaterialTheme.typography.bodyMedium)
                    }
                    val execution = data?.optJSONObject("execution")
                    Text(if (execution?.text("mode", "") == "read_only" && !execution.optBoolean("real_orders_enabled"))
                        "Режим: анализ" else "Режим исполнения не подтверждён",
                        style = MaterialTheme.typography.labelLarge)
                }
            }
            val blockers = data?.records("blockers").orEmpty()
            if (blockers.isNotEmpty()) item {
                SpectrumCard {
                    Text("Что нужно для работы", style = MaterialTheme.typography.titleMedium)
                    blockers.forEach { blocker ->
                        blocker.text("message", "").takeIf(String::isNotBlank)?.let { Text(it) }
                    }
                    val needsStrategy = blockers.any { it.text("code", "") == "strategy_required" }
                    SpectrumSecondaryButton(if (needsStrategy) "Настроить стратегию" else "Открыть настройки",
                        { if (needsStrategy) navigate(WorkspaceRoute.Strategies) else navigateTab(AnalystTab.Profile) },
                        Modifier.fillMaxWidth())
                }
            }
            if (candidates.isEmpty() && !resource.busy && data != null) item {
                SpectrumCard {
                    Text("Проверенных предложений пока нет", style = MaterialTheme.typography.titleLarge)
                    val reasons = discovery?.records("reasons").orEmpty()
                    if (reasons.isEmpty()) {
                        Text("Система покажет результат после получения данных и завершения проверок.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else {
                        reasons.take(6).forEach { reason ->
                            reason.text("message", "").takeIf(String::isNotBlank)?.let { Text(it) }
                        }
                    }
                }
            }
            items(candidates, key = { it.text("instrument_uid", it.toString()) }) { candidate ->
                ResearchCandidateCard(candidate)
            }
            if (events.isNotEmpty()) item {
                Text("Последние результаты", style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(top = 4.dp).semantics { heading() })
            }
            items(events.take(12), key = { it.text("id", it.toString()) }) { event ->
                SpectrumCard {
                    Text(event.text("title", "Результат анализа"), style = MaterialTheme.typography.titleMedium)
                    event.text("summary", "").takeIf(String::isNotBlank)?.let {
                        Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    event.text("at", "").takeIf(String::isNotBlank)?.let {
                        Text(relativeObservation(it), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }
    }
}

@Composable
private fun ResearchCandidateCard(candidate: JSONObject) {
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
