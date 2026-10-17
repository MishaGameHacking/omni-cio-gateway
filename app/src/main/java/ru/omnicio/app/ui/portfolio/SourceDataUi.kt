package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import org.json.JSONArray
import ru.omnicio.app.data.market.*
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*

@Composable
fun SourceProvenance(sources: List<JSONObject>, sourceIds: List<String>? = null, title: String = "Источник и время данных") {
    val visible = if (sourceIds == null) sources else sources.filter { it.optString("id") in sourceIds }
    DetailFold(title) {
        if (visible.isEmpty()) Text("Источник для этого значения не передан. Подтверждение отсутствует.")
        visible.forEach { source ->
            Text(source.optionalText("provider") ?: source.optionalText("id") ?: "Источник не указан", style = MaterialTheme.typography.titleSmall)
            source.optionalText("method")?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            Text("Наблюдение: ${dateText(source.optionalText("observed_at"))}", style = MaterialTheme.typography.bodySmall)
            source.optionalText("published_at")?.let { Text("Публикация: ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
            source.optionalText("expires_at")?.let { Text("Срок актуальности: ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
            if (source.optionalText("expires_at")?.let { runCatching { java.time.Instant.parse(it).isBefore(java.time.Instant.now()) }.getOrDefault(false) } == true)
                Text("Срок актуальности источника истёк. Сверьте свежую публикацию.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            source.optionalText("subject_id")?.let { Text("Объект: $it", style = MaterialTheme.typography.bodySmall) }
            source.optionalText("unit")?.let { Text("Единица: $it", style = MaterialTheme.typography.bodySmall) }
            source.optionalText("url")?.takeIf { it.startsWith("https://") }?.let { SelectionContainer { Text(it, style = MaterialTheme.typography.bodySmall) } }
        }
    }
}

@Composable
fun WorkspaceRequestNotice(request: WorkspaceRequest) {
    if (request.loading) ru.omnicio.app.ui.spectrum.SpectrumLoadingIndicator(description = "Получаем сведения из источника")
    request.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    if (request.showingPreviousQuery) Text("Показана предыдущая выборка: ${request.displayedParameters.values.joinToString(" · ")}. Новая ещё не получена.")
    if (request.error != null || (request.json == null && !request.loading)) TextButton(onClick = request.refresh) { Text("Повторить запрос") }
}

@Composable
fun WorkspaceSectionNotice(section: JSONObject?, missing: String = "Источник ещё не передал сведения.") {
    val state = section?.optString("state")
    if (state != "available") {
        val reason = section?.optionalText("reason")
        Text(when (reason) {
            "snapshot_stale" -> "Снимок устарел. Обновите данные, чтобы получить актуальные сведения."
            "source_coverage_incomplete" -> "Доступна часть сведений. Неизвестные значения оставлены без оценки."
            "snapshot_missing", "workspace_snapshot_missing" -> "Рабочий снимок ещё не получен. Запустите обновление данных."
            "not_configured" -> missing
            else -> if (reason != null && !reason.matches(Regex("[a-z0-9_:-]+"))) reason else missing
        }, style = MaterialTheme.typography.bodyMedium)
        if (reason != null && reason.matches(Regex("[a-z0-9_:-]+"))) DetailFold("Состояние источника") { Text(reason, style = MaterialTheme.typography.bodySmall) }
    }
    section?.optionalText("as_of")?.let { Text("Данные: ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
}

@Composable
fun workspaceMoney(value: JSONObject?): String {
    if (LocalWorkspacePreferences.current.value.hideHomeBalance) return "•••"
    val amount = value?.optionalText("amount")?.toBigDecimalOrNull() ?: return "Не получено"
    return "${decimalText(amount)} ${value.optionalText("currency")?.let(::currencySymbol) ?: "единица не указана"}"
}

@Composable
fun WorkspaceEvents(events: List<JSONObject>, sources: List<JSONObject>, onInstrument: ((String) -> Unit)? = null) {
    if (events.isEmpty()) Text("В выбранной выборке событий нет.")
    deduplicateSourceEvents(events).forEach { event ->
        SpectrumCard {
            Text(event.optionalText("title") ?: event.optionalText("kind") ?: "Событие", style = MaterialTheme.typography.titleMedium)
            event.optionalText("summary")?.let { Text(PrivateValue(it)) }
            Text(dateText(event.optionalText("occurred_at") ?: event.optionalText("published_at") ?: event.optionalText("date")),
                style = MaterialTheme.typography.bodySmall)
            val relation = event.optionalText("relationship")
            Text(when (relation) { "verified" -> "Связь подтверждена источником"; "broker_link" -> "Событие инструмента у брокера"; else -> "Связь требует проверки" }, style = MaterialTheme.typography.bodySmall)
            if (onInstrument != null) event.stringList("instrument_uids").forEach { uid -> TextButton(onClick = { onInstrument(uid) }) { Text("Открыть связанную позицию") } }
            SourceProvenance(sources, event.stringList("source_ids"))
        }
    }
}

/** Only a source-provided event ID proves duplication. Anonymous events remain separate. */
internal fun deduplicateSourceEvents(events: List<JSONObject>): List<JSONObject> {
    val merged = linkedMapOf<String, JSONObject>()
    events.forEachIndexed { index, event ->
        val key = event.optionalText("id")?.let { "id:$it" } ?: "anonymous:$index"
        val previous = merged[key]
        if (previous == null) merged[key] = JSONObject(event.toString())
        else {
            previous.put("source_ids", JSONArray((previous.stringList("source_ids") + event.stringList("source_ids")).distinct()))
            val all = listOf(previous.optJSONArray("sources"), event.optJSONArray("sources")).flatMap { array ->
                if (array == null) emptyList() else (0 until array.length()).mapNotNull { array.optJSONObject(it) }
            }.distinctBy { it.optionalText("id") ?: it.toString() }
            previous.put("sources", JSONArray(all))
            previous.put("duplicate_count", previous.optInt("duplicate_count", 1) + 1)
        }
    }
    return merged.values.toList()
}
