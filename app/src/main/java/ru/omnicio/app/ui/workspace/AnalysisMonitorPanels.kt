package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import org.json.JSONObject
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@Composable
internal fun AnalysisSlotChecks(checks: List<JSONObject>, openCheck: (String) -> Unit) {
    SpectrumCard {
        Text("Утренний и вечерний результаты", style = MaterialTheme.typography.titleMedium)
        Text("Последнее сохранённое решение для каждого времени. Проверка условий может завершиться без нового обращения к модели.", style = MaterialTheme.typography.bodySmall)
        listOf("morning" to "Утро", "evening" to "Вечер").forEach { (slot, title) ->
            val check = checks.firstOrNull { it.text("slot") == slot }
            DetailFold(title, initiallyOpen = true) {
                if (check == null) Text("Решение ещё не наблюдалось. Пропуски до обновления приложения не восстанавливаются по догадке.")
                else AnalysisSlotResult(check, openCheck)
            }
        }
    }
}

@Composable
private fun AnalysisSlotResult(check: JSONObject, openCheck: (String) -> Unit) {
    val openReport = LocalOpenAnalysisReport.current
    val zone = check.text("timezone", "")
    Text("По расписанию: " + scheduledMoment(check.text("scheduled_at", ""), zone))
    Text("Проверено: " + localMoment(check.text("checked_at", "")))
    Text(monitorState(check.text("state", "")))
    Text("Основание: " + analysisReason(check.text("reason", "")))
    check.text("card_id", "").takeIf(String::isNotBlank)?.let { card ->
        SpectrumSecondaryButton("Открыть этот отчёт", { openReport(card) }, Modifier.fillMaxWidth())
    }
    check.text("check_id", "").takeIf(String::isNotBlank)?.let { id ->
        SpectrumSecondaryButton("Что проверялось", { openCheck(id) }, Modifier.fillMaxWidth())
    }
}

@Composable
internal fun AnalysisCheckHistory(checks: List<JSONObject>, openCheck: (String) -> Unit) {
    SpectrumCard {
        Text("История проверок условий", style = MaterialTheme.typography.titleMedium)
        if (checks.isEmpty()) Text("Сохранённых проверок пока нет.")
        else DetailFold("Последние проверки · " + checks.size) {
            checks.forEach { check ->
                val id = check.text("check_id", "")
                Text(localMoment(check.text("checked_at", "")), style = MaterialTheme.typography.titleSmall)
                Text(monitorState(check.text("state", "")) + ". " + analysisReason(check.text("reason", "")))
                Text("Наблюдений в основании: " + check.optInt("observation_count"), style = MaterialTheme.typography.bodySmall)
                if (id.isNotBlank()) SpectrumSecondaryButton("Основания этой проверки", { openCheck(id) }, Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
internal fun AnalysisCheckDialog(identifier: String, close: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/analysis/checks/" + VolumeWorkspaceClient.encode(identifier))
    WorkspaceDialog("Сохранённая проверка", close) {
        WorkspaceRequestState(resource)
        resource.data?.let { MonitorCheckCard(it) }
        SpectrumSecondaryButton("Закрыть", close, Modifier.fillMaxWidth())
    }
}

@Composable
internal fun AnalysisTriggerEvidence(trigger: JSONObject?) {
    if (trigger == null) {
        Text("Подробные наблюдения не сохранены в этой проверке.", style = MaterialTheme.typography.bodySmall)
        return
    }
    DetailFold("Наблюдения, на которых принято решение") {
        Text("Снимок получен: " + localMoment(trigger.text("as_of", "")))
        Text(if (trigger.optBoolean("first_observation")) "Это первое наблюдение: подтверждённой предыдущей точки для сравнения нет."
            else "Сопоставлено с предыдущим сохранённым наблюдением автоматического мониторинга. Изменение стоимости само по себе не означает доходность.")
        AnalysisPolicySignals(trigger.optJSONObject("policy_signals"))
        val observations = trigger.records("observations")
        val coverage = trigger.optJSONObject("coverage")
        if (coverage != null) Text("Показано наблюдений: " + coverage.optInt("included") + " из " + coverage.optInt("total"))
        if (coverage?.optBoolean("truncated") == true) Text("Объём подробностей ограничен; перечисленные наблюдения не исчерпывают весь снимок.")
        val sources = trigger.records("sources").associateBy { it.text("id", "") }
        observations.forEach { observation -> AnalysisTriggerObservation(observation, sources) }
    }
}

@Composable
private fun AnalysisPolicySignals(signals: JSONObject?) {
    if (signals == null) return
    val labels = listOf("morning_due" to "Подошло утреннее время", "evening_due" to "Подошло вечернее время",
        "portfolio_changed" to "Изменился состав портфеля", "cash_changed" to "Изменились свободные средства",
        "critical_risk" to "Обнаружено существенное основание риска", "data_recovered" to "Восстановилась доступность данных",
        "digest_changed" to "Изменился набор наблюдаемых фактов")
    val active = labels.filter { signals.optBoolean(it.first) }
    Text("Условия правила", style = MaterialTheme.typography.titleSmall)
    if (active.isEmpty()) Text("Ни одно из перечисленных условий не потребовало нового анализа.")
    active.forEach { Text(it.second) }
    if (!signals.isNull("minutes_since_last_analysis")) {
        Text("Минут с предыдущего анализа: " + signals.text("minutes_since_last_analysis"), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun AnalysisTriggerObservation(observation: JSONObject, sources: Map<String, JSONObject>) {
    DetailFold(observation.text("title", "Наблюдение")) {
        val before = observation.opt("before")
        val after = observation.opt("after")
        Text("Предыдущее наблюдение", style = MaterialTheme.typography.titleSmall)
        VerifiedFact(before, "Предыдущее наблюдение")
        Text("Новое наблюдение", style = MaterialTheme.typography.titleSmall)
        VerifiedFact(after, "Новое наблюдение")
        val account = (observation.optJSONObject("after") ?: observation.optJSONObject("before"))?.text("account_id", "")
        val highlights = observation.strings("instrument_uids").map { uid ->
            JSONObject().put("section", "instrument").put("id", uid).put("account_id", account ?: JSONObject.NULL)
                .put("label", "Показать связанную позицию")
        }
        val references = observation.strings("source_ids").map { id -> sources[id] ?: JSONObject().put("source_id", id) }
        EvidenceLinks(references, highlights)
        if (observation.text("kind").startsWith("risk_")) Text("Зафиксировано основание проверки риска. Это не подтверждение финансовой сделки.", style = MaterialTheme.typography.bodySmall)
    }
}

private fun scheduledMoment(raw: String, zone: String): String = runCatching {
    Instant.parse(raw).atZone(ZoneId.of(zone)).format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm")) + " · " + zone
}.getOrDefault(localMoment(raw))
