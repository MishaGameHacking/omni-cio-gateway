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
    val refresh = LocalWorkspaceRefresh.current
    val navigate = LocalWorkspaceNavigator.current
    val openReport = LocalOpenAnalysisReport.current
    val ai = resource.data?.optJSONObject("sections")?.optJSONObject("ai")?.optJSONObject("data")
    var selectedJob by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedCheck by rememberSaveable { mutableStateOf<String?>(null) }
    var confirm by rememberSaveable { mutableStateOf(false) }
    val run = rememberWorkspaceAction { selectedJob = it.optString("job_id").takeIf(String::isNotBlank); resource.refresh() }
    WorkspaceDetailPage("Работа аналитика", "Время, причины, основания и расход", onBack, SpectrumSymbol.Analyst) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource) }
            item { PendingJobRecovery { selectedJob = it } }
            selectedJob?.let { id -> item { WorkspaceJobPanel(id, { resource.refresh() }, { selectedJob = null }) } }
            item { SpectrumCard(emphasized = true) {
                val last = ai?.optJSONObject("last_run")
                SpatialIcon("analyst", Modifier.size(56.dp), state = if (last?.text("state") == "completed") SpatialState.Success else SpatialState.Idle)
                Text("Последний анализ", style = MaterialTheme.typography.titleLarge)
                if (last == null) Text("Подтверждённых запусков ещё нет.") else {
                    Text(localMoment(last.text("created_at", "")))
                    Text("Причина: " + analysisReason(last.text("reason", "")))
                    Text("Состояние: " + analysisState(last.text("state", "")))
                    Text("Глубина: " + analysisTier(last.text("tier", "")), style = MaterialTheme.typography.bodySmall)
                    SpectrumSecondaryButton("Открыть сохранённые выводы", { openReport(last.text("card_id", "").takeIf(String::isNotBlank)) }, Modifier.fillMaxWidth())
                }
                SpectrumSecondaryButton("Обновить сведения", { resource.refresh(); refresh() }, Modifier.fillMaxWidth())
            } }
            item { SpectrumCard {
                Text("Ближайшие проверки", style = MaterialTheme.typography.titleMedium)
                val next = ai?.records("next_runs").orEmpty()
                if (next.isEmpty()) Text("Расписание ещё не получено.")
                next.forEach { slot ->
                    Text((if (slot.text("slot") == "morning") "Утро: " else "Вечер: ") + localMoment(slot.text("at", "")))
                    Text(when (slot.text("gate")) {
                        "market_closed" -> "Биржа закрыта: платный анализ не запускается"
                        "awaiting_calendar" -> "Ожидаем подтверждённый календарь"
                        "rule_disabled" -> "Плановые уведомления отключены в настройках"
                        else -> "Проверка по настроенным правилам"
                    }, style = MaterialTheme.typography.bodySmall)
                }
                SpectrumSecondaryButton("Изменить время и уведомления", { navigate(WorkspaceRoute.NotificationSettings) }, Modifier.fillMaxWidth())
            } }
            item { AnalysisSlotChecks(ai?.records("slot_checks").orEmpty()) { selectedCheck = it } }
            item { MonitorCheckCard(ai?.optJSONObject("last_check")) }
            item { AnalysisCheckHistory(ai?.records("check_history").orEmpty()) { selectedCheck = it } }
            ai?.records("monitor_jobs").orEmpty().forEach { monitor -> item(key = "monitor:" + monitor.text("job_id")) {
                DetailFold("Проверка · " + localMoment(monitor.text("created_at", ""))) {
                    Text(jobStateTitle(monitor.text("state")))
                    monitor.optJSONObject("result")?.let { result ->
                        Text("Решение: " + monitorState(result.text("state", "")))
                        Text("Причина: " + analysisReason(result.text("reason", "")))
                        if (!result.isNull("card_id")) SpectrumSecondaryButton("Открыть вывод проверки", { openReport(result.text("card_id")) }, Modifier.fillMaxWidth())
                    }
                    monitor.text("error_code", "").takeIf(String::isNotBlank)?.let { Text("Проверка завершилась с ошибкой: " + readinessLabel(it)) }
                }
            } }
            item { AnalysisComparison(ai?.optJSONObject("analysis_diff")) }
            item { SpectrumCard {
                val budget = ai?.optJSONObject("budget")
                Text("Расход на анализ", style = MaterialTheme.typography.titleMedium)
                Text(PrivateValue((budget?.text("estimated_and_reserved_rub", "Не получено") ?: "Не получено") + " RUB"), style = MaterialTheme.typography.headlineSmall)
                budget?.let {
                    Text("Учтённая оценка и резерв за " + it.text("day") + ", " + it.text("timezone"))
                    Text("Попыток, ожидающих сверки: " + it.optInt("unresolved_attempts"))
                    if (it.optBoolean("paid_calls_paused")) Text("Платные обращения приостановлены.", color = MaterialTheme.colorScheme.error)
                }
                Text("Эта сумма включает резервы запросов. Окончательный счёт провайдера здесь не подтверждается.", style = MaterialTheme.typography.bodySmall)
                val ready = ai?.optJSONObject("readiness")?.optBoolean("available") == true
                if (!ready) Text("Модель пока недоступна: " + readinessLabel(ai?.optJSONObject("readiness")?.text("reason", "")))
                SpectrumPrimaryButton("Запустить проверку портфеля", { confirm = true }, Modifier.fillMaxWidth(),
                    ready && !run.busy && selectedJob == null, SpectrumSymbol.Analyst)
                WorkspaceActionState(run)
            } }
            ai?.records("jobs").orEmpty().forEach { job -> item(key = job.text("job_id")) { SpectrumCard(onClick = { selectedJob = job.text("job_id") }) {
                Text(jobStateTitle(job.text("state")), style = MaterialTheme.typography.titleMedium)
                Text(when (job.text("kind")) { "chat" -> "Диалог"; "refresh" -> "Обновление источников"; "reconcile" -> "Сверка операций"; else -> "Анализ портфеля" })
                Text(localMoment(job.text("updated_at", "")), style = MaterialTheme.typography.bodySmall)
            } } }
        }
    }
    selectedCheck?.let { identifier -> AnalysisCheckDialog(identifier) { selectedCheck = null } }
    if (confirm) WorkspaceDialog("Запустить анализ?", { confirm = false }) {
        Text("Сервер обновит доступные факты и проверит лимиты. Обращение к модели возможно только в пределах действующих лимитов расхода. Вы сможете увидеть стадию и запросить отмену.")
        SpectrumPrimaryButton("Запустить по действующим лимитам", {
            confirm = false
            run.perform("/workspace/analysis", JSONObject().put("request_id", UUID.randomUUID().toString()).put("reason", "manual"), job = true)
        }, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Вернуться", { confirm = false }, Modifier.fillMaxWidth())
    }
}

@Composable
private fun AnalysisComparison(diff: JSONObject?) {
    var showFacts by remember { mutableStateOf(false) }
    SpectrumCard {
        Text("Изменения двух последних выводов", style = MaterialTheme.typography.titleMedium)
        if (diff == null || diff.isNull("previous_card_id")) Text("Для сравнения нужны два сохранённых вывода.") else {
            if (!diff.optBoolean("fact_comparison_available")) Text("Сравниваем сохранённые поля отчётов и их основания. Полного набора структурированных фактов в прежнем отчёте нет.")
            listOf("added" to "Добавилось", "removed" to "Убрано", "changed" to "Изменилось", "unchanged" to "Сохранилось").forEach { (key, label) ->
                DetailFold(label + " · " + diff.records(key).size) {
                    diff.records(key).forEach { change ->
                        Text(reportField(change.text("field")), style = MaterialTheme.typography.titleSmall)
                        if (key == "changed") { Text("Было: " + readableReportValue(change.opt("before"))); Text("Стало: " + readableReportValue(change.opt("after"))) }
                        else Text(readableReportValue(change.opt("value")))
                    }
                }
            }
            diff.optJSONObject("evidence_diff")?.let { evidence -> DetailFold("Изменения оснований") {
                listOf("added" to "Новые", "removed" to "Убраны", "unchanged" to "Сохранены").forEach { (key, label) ->
                    Text(label + ": " + (evidence.optJSONArray(key)?.length() ?: 0))
                }
            } }
            val facts = diff.optJSONObject("structured_facts")
            if (facts?.optBoolean("available") == true) {
                val counts = facts.optJSONObject("counts")
                Text("Наблюдения: новых " + (counts?.optInt("added") ?: 0) + ", изменённых " + (counts?.optInt("changed") ?: 0) + ", сохранённых " + (counts?.optInt("unchanged") ?: 0))
                SpectrumSecondaryButton("Сравнить факты портфеля", { showFacts = true }, Modifier.fillMaxWidth())
            }
        }
    }
    if (showFacts && diff != null) AnalysisFactsDialog(diff.text("current_card_id"), diff.text("previous_card_id", "")) { showFacts = false }
}

@Composable
private fun AnalysisFactsDialog(currentId: String, previousId: String, close: () -> Unit) {
    var offset by rememberSaveable(currentId, previousId) { mutableIntStateOf(0) }
    val query = "/workspace/analysis/diff?current_card_id=" + ru.omnicio.app.data.workspace.VolumeWorkspaceClient.encode(currentId) +
        (if (previousId.isBlank()) "" else "&previous_card_id=" + ru.omnicio.app.data.workspace.VolumeWorkspaceClient.encode(previousId)) + "&offset=" + offset + "&limit=20"
    val resource = rememberWorkspaceResource(query)
    WorkspaceDialog("Сравнение наблюдений", close) {
        WorkspaceRequestState(resource)
        Text("Каждое значение связано с сохранённым наблюдением. Изменение источника показывается отдельно от изменения числа.")
        resource.data?.records("items").orEmpty().forEach { item ->
            val title = when (item.text("state")) { "added" -> "Новое"; "removed" -> "Больше не наблюдается"; "changed" -> "Изменилось"; else -> "Значение сохранилось" }
            DetailFold(title + " · " + item.text("id").substringBefore(':')) {
                item.optJSONObject("before")?.let { before -> Text("Было", style = MaterialTheme.typography.titleSmall); VerifiedFact(before.opt("value")); Text(localMoment(before.text("as_of", ""))) }
                item.optJSONObject("after")?.let { after -> Text("Стало", style = MaterialTheme.typography.titleSmall); VerifiedFact(after.opt("value")); Text(localMoment(after.text("as_of", ""))) }
                if (item.optBoolean("provenance_changed")) Text("Время или источник наблюдения изменились.")
                val observation = item.optJSONObject("after") ?: item.optJSONObject("before")
                EvidenceLinks(item.strings("source_ids").map { JSONObject().put("source_id", it).put("as_of", observation?.text("as_of", "")) }, listOfNotNull(observation?.optJSONObject("highlight")))
            }
        }
        if (offset > 0) SpectrumSecondaryButton("Предыдущие наблюдения", { offset = (offset - 20).coerceAtLeast(0) }, Modifier.fillMaxWidth())
        if (resource.data?.optBoolean("has_more") == true) SpectrumSecondaryButton("Следующие наблюдения", { offset += 20 }, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Закрыть", close, Modifier.fillMaxWidth())
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
            Text("Причина: " + analysisReason(check.text("reason", "")))
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
private fun reportField(raw: String) = when (raw) { "title" -> "Тема"; "summary" -> "Вывод"; "actions" -> "Предложенные проверки"; else -> raw.take(100) }
private fun readableReportValue(value: Any?): String = when (value) {
    null, JSONObject.NULL -> "Нет сохранённого значения"
    is org.json.JSONArray -> (0 until value.length()).joinToString("\n") { index -> value.optJSONObject(index)?.let { it.text("title", it.text("description", "Проверка")) } ?: value.optString(index) }
    is JSONObject -> value.text("title", value.text("description", "Сохранённое основание"))
    else -> value.toString()
}
