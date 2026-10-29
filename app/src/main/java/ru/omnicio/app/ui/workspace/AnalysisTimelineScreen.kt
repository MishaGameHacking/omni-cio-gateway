package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

@Composable
fun AnalysisTimelineScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace")
    val ai = resource.data?.optJSONObject("sections")?.optJSONObject("ai")?.optJSONObject("data")
    val navigate = LocalWorkspaceNavigator.current
    val report = LocalOpenAnalysisReport.current
    var jobId by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedCheck by rememberSaveable { mutableStateOf<String?>(null) }
    val run = rememberWorkspaceAction { jobId = it.optString("job_id").takeIf(String::isNotBlank); resource.refresh() }
    val job = jobId?.let { rememberWorkspaceJobState(it, onCompleted = { resource.refresh() }) }
    val ready = ai?.optJSONObject("readiness")?.optBoolean("available") == true
    val check = ai?.optJSONObject("last_check")
    val checks = ai?.records("check_history").orEmpty().distinctBy { it.text("reason") + ":" + it.text("state") }.take(5)
    WorkspaceDetailPage("Работа аналитика", "Состояние портфеля и последние изменения", onBack, SpectrumSymbol.Analyst) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { WorkspaceRequestState(resource) }
            item { PendingJobRecovery { jobId = it } }
            job?.let { model -> item { WorkspaceJobPanel(model, onClose = { jobId = null }) } }
            item { AnalystStatusVisual(check, ready) }
            item { SpectrumCard {
                Text(if (ready) "ИИ доступен" else "ИИ требует подключения", style = MaterialTheme.typography.titleMedium)
                if (!ready) Text(readinessLabel(ai?.optJSONObject("readiness")?.text("reason", "")))
                val last = ai?.optJSONObject("last_run")
                if (last != null) {
                    Text("Последний анализ: " + localMoment(last.text("created_at", "")), style = MaterialTheme.typography.bodySmall)
                    Text(analysisReason(last.text("reason", "")))
                }
                SpectrumPrimaryButton("Проверить портфель", {
                    run.perform("/workspace/analysis", JSONObject().put("request_id", UUID.randomUUID().toString()).put("reason", "manual"), job = true)
                }, Modifier.fillMaxWidth(), ready && !run.busy && jobId == null, SpectrumSymbol.Analyst)
                SpectrumSecondaryButton("Открыть выводы", { report(null) }, Modifier.fillMaxWidth())
                WorkspaceActionState(run)
            } }
            item { SpectrumCard {
                Text("Последние результаты", style = MaterialTheme.typography.titleMedium)
                Text("Повторные проверки объединены. Здесь последнее состояние каждого условия.", style = MaterialTheme.typography.bodySmall)
                if (checks.isEmpty()) Text("Результатов пока нет")
                checks.forEach { item ->
                    Text(analysisReason(item.text("reason")), style = MaterialTheme.typography.titleSmall)
                    Text(monitorState(item.text("state")) + " · " + localMoment(item.text("checked_at", "")), style = MaterialTheme.typography.bodySmall)
                    SpectrumSecondaryButton("Что проверено", { selectedCheck = item.text("check_id") }, Modifier.fillMaxWidth())
                }
            } }
            item { SpectrumCard {
                Text("Расход на ИИ", style = MaterialTheme.typography.titleMedium)
                val budget = ai?.optJSONObject("budget")
                Text(PrivateValue((budget?.text("estimated_and_reserved_rub", "—") ?: "—") + " ₽ сегодня"), style = MaterialTheme.typography.headlineSmall)
                Text("Включая резерв запросов. Повторные одинаковые проверки не требуют нового ответа ИИ.", style = MaterialTheme.typography.bodySmall)
                if (budget?.optBoolean("paid_calls_paused") == true) Text("Лимит или проверка оплаты приостановили обращения", color = MaterialTheme.colorScheme.error)
                SpectrumSecondaryButton("Уведомления", { navigate(WorkspaceRoute.NotificationSettings) }, Modifier.fillMaxWidth())
            } }
        }
    }
    selectedCheck?.let { AnalysisCheckDialog(it) { selectedCheck = null } }
}

@Composable
private fun AnalystStatusVisual(check: JSONObject?, ready: Boolean) {
    val trigger = check?.optJSONObject("trigger")
    val observations = trigger?.records("observations").orEmpty()
    val risks = observations.filter { it.text("kind").startsWith("risk_") }
    val severity = when { check == null -> "Нет свежей проверки"; risks.isNotEmpty() -> "⚠️ Есть основания для проверки риска"; check.text("state") == "failed" -> "Проверка не завершена"; else -> "🔎 Последняя проверка сохранена" }
    SpectrumCard {
        Text(severity, style = MaterialTheme.typography.titleLarge)
        Text(if (check == null) "Подключите данные и запустите проверку" else analysisReason(check.text("reason")))
        if (risks.isNotEmpty()) risks.take(3).forEach { row ->
            val after = row.optJSONObject("after")
            val share = after?.text("share_percent", "")?.toFloatOrNull()
            Text(row.text("title"), style = MaterialTheme.typography.titleSmall)
            if (share != null) {
                Text("Доля " + after.text("share_percent") + "% · лимит " + after.text("limit_percent", "не получен") + "%")
                SpectrumProgressBar((share / 100f).coerceIn(0f, 1f), accent = MaterialTheme.colorScheme.error)
            }
        }
        val coverage = trigger?.optJSONObject("coverage")
        val total = coverage?.optInt("total") ?: 0
        val included = coverage?.optInt("included") ?: 0
        if (total > 0) {
            Text("Сохранено наблюдений: $included из $total", style = MaterialTheme.typography.bodySmall)
            SpectrumProgressBar((included.toFloat() / total).coerceIn(0f, 1f))
        }
        Text(if (ready) "Расчёты → проверка фактов → объяснение ИИ" else "Расчёты доступны · объяснение ИИ пока недоступно", style = MaterialTheme.typography.bodySmall)
        Text("Проверка не означает отсутствие риска. Торговых поручений система не отправляет.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
internal fun MonitorCheckCard(check: JSONObject?) {
    val navigate = LocalWorkspaceNavigator.current
    val evidence = LocalEvidenceNavigator.current
    val openReport = LocalOpenAnalysisReport.current
    SpectrumCard {
        Text("Последняя проверка условий", style = MaterialTheme.typography.titleMedium)
        if (check == null) Text("Сохранённого решения планировщика пока нет.") else {
            Text(localMoment(check.text("checked_at", "")))
            Text(monitorState(check.text("state", "")))
            Text(analysisReasonLine(check))
            if (check.text("state") == "skipped") Text("Проверка условий не создала новый вывод модели.")
            if (check.text("state") == "fallback") Text("Сохранено объяснение алгоритмов; ответ модели не подтверждён.")
            check.text("error_code", "").takeIf(String::isNotBlank)?.let { Text("Доступность модели: " + readinessLabel(it)) }
            if (!check.isNull("card_id")) SpectrumSecondaryButton("Проверить основания вывода", { openReport(check.text("card_id")) }, Modifier.fillMaxWidth())
            if (check.text("reason") == "risk_event") SpectrumSecondaryButton("Открыть событие риска", { evidence(EvidenceTarget("risk", "")) }, Modifier.fillMaxWidth())
            if (check.text("reason") == "market_regime_changed") SpectrumSecondaryButton("Открыть связанные события", { navigate(WorkspaceRoute.Discovery) }, Modifier.fillMaxWidth())
            AnalysisTriggerEvidence(check.optJSONObject("trigger"))
        }
    }
}

internal fun monitorState(raw: String): String = when (raw) {
    "skipped" -> "Новый анализ не требовался"; "analysis_required" -> "Условия потребовали нового анализа"
    "ready" -> "Вывод сохранён"; "fallback" -> "Сохранено объяснение алгоритмов"; else -> analysisState(raw)
}

private fun analysisReasonLine(value: JSONObject) = "Причина: " + analysisReason(value.text("reason", ""))

internal fun analysisReason(raw: String): String = when (raw) {
    "manual" -> "Ваш запрос"; "morning", "scheduled_morning" -> "Утренняя проверка"; "evening", "scheduled_evening" -> "Вечерняя проверка"
    "morning_brief" -> "Утренняя проверка"; "evening_brief" -> "Вечерняя проверка"
    "material_change", "portfolio_changed" -> "Изменился состав портфеля"; "cash_changed" -> "Изменились свободные средства"
    "risk_limit", "risk_event" -> "Изменилось подтверждённое основание риска"; "initial", "first_connection" -> "Первое подключение"
    "market_regime_changed" -> "Изменились связанные рыночные события"; "data_recovery" -> "Восстановились доступные данные"
    "no_material_change" -> "Значимых изменений не найдено"; "budget_exhausted" -> "Достигнут лимит расхода"
    "cooldown" -> "С прошлого анализа прошло недостаточно времени"
    "market_closed" -> "В подтверждённом календаре нет торговой сессии"
    "awaiting_calendar" -> "Торговый календарь ещё не подтверждён"
    "rule_disabled" -> "Плановые уведомления отключены в настройках"
    "user_requested" -> "Запрос пользователя"; else -> if (raw.isBlank()) "Причина не получена" else "Серверная проверка · " + raw.take(80)
}
private fun analysisTier(raw: String): String = when (raw) { "fast" -> "Краткая"; "standard" -> "Обычная"; "premium" -> "Углублённая"; else -> "Не получена" }
private fun analysisState(raw: String): String = when (raw) { "success", "completed" -> "Вывод сохранён"; "skipped" -> "Новый вывод не требовался"; "failed", "error" -> "Ошибка проверки"; else -> jobStateTitle(raw) }
private fun readinessLabel(raw: String?): String = when (raw) { "model_key_missing", "provider_not_configured", "no_route" -> "нужен настроенный маршрут модели"; "budget_exhausted" -> "достигнут лимит расхода"; else -> "доступность пока не подтверждена" }
