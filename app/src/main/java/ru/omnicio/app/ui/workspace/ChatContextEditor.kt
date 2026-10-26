package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import org.json.JSONObject
import java.time.LocalDate
import ru.omnicio.app.ui.spectrum.*

@Composable
fun ChatContextEditor(current: ChatContext, onClose: () -> Unit) {
    val portfolio = LocalPortfolioSnapshot.current
    val select = LocalAskAnalyst.current
    val memory = LocalWorkspaceAutoSave.current
    var restored by rememberSaveable { mutableStateOf(memory == null) }
    var mode by rememberSaveable { mutableIntStateOf(listOf("general", "portfolio", "instrument").indexOf(current.mode).coerceAtLeast(0)) }
    var accountId by rememberSaveable { mutableStateOf(current.accountId) }
    var instrument by rememberSaveable { mutableStateOf(current.instrumentUid) }
    var search by rememberSaveable { mutableStateOf("") }
    var start by rememberSaveable { mutableStateOf(current.start.orEmpty()) }
    var end by rememberSaveable { mutableStateOf(current.end.orEmpty()) }
    val contextEventId by rememberSaveable { mutableStateOf(current.eventId) }
    val contextInstrument by rememberSaveable { mutableStateOf(current.instrumentUid) }
    var keepEvent by rememberSaveable { mutableStateOf(current.eventId != null) }
    val accounts = portfolio?.accounts.orEmpty()
    val accountIndex = accounts.indexOfFirst { it.id == accountId }
    val validAccount = accountId == null || accountIndex >= 0
    val positions = accounts.filter { accountId == null || it.id == accountId }.flatMap { it.positions }.distinctBy { it.id }
    val selected = positions.firstOrNull { it.id == instrument }
    val validRange = (start.isBlank() && end.isBlank()) || runCatching { LocalDate.parse(start) <= LocalDate.parse(end) }.getOrDefault(false)
    LaunchedEffect(memory?.ready) {
        if (restored || memory?.ready == false) return@LaunchedEffect
        memory?.selection("chat_context_editor")?.takeIf {
            it.optJSONObject("context")?.let { origin -> equivalentJson(origin, current.json()) } == true
        }?.let { saved ->
            mode = saved.optInt("mode", 1).coerceIn(0, 2)
            accountId = saved.optString("account_id").takeUnless { it.isBlank() || it == "null" }
            instrument = saved.optString("instrument").takeUnless { it.isBlank() || it == "null" }
            start = saved.optString("start", ""); end = saved.optString("end", "")
            keepEvent = saved.optBoolean("keep_event")
        }
        restored = true
    }
    val valid = (mode == 0 || validAccount && validRange) && (mode != 2 || selected != null)
    LaunchedEffect(memory?.ready, restored, mode, accountId, instrument, start, end, keepEvent, valid, selected?.title) {
        if (!restored || memory?.ready == false) return@LaunchedEffect
        memory?.rememberSelection("chat_context_editor", JSONObject().put("context", current.json())
            .put("mode", mode).put("account_id", accountId ?: JSONObject.NULL)
            .put("instrument", instrument ?: JSONObject.NULL).put("start", start).put("end", end)
            .put("keep_event", keepEvent))
        if (valid) {
            val title = when (mode) {
                0 -> "Общий вопрос"
                2 -> selected?.title.orEmpty()
                else -> accounts.firstOrNull { it.id == accountId }?.name ?: "Мой портфель"
            }
            val next = editedChatContext(mode, title, instrument, accountId, start to end,
                contextEventId.takeIf { keepEvent && instrument == contextInstrument })
            if (!equivalentJson(current.json(), next.json()) || current.title != next.title) select(next)
        }
    }
    WorkspaceDialog("Контекст следующего вопроса", onClose) {
        if (!restored) {
            SpectrumLoadingIndicator(description = "Восстанавливаем ваш выбор")
            AutoSaveStatus(null) { memory?.retry(AutoSaveKind.Notifications) }
            return@WorkspaceDialog
        }
        Text(memory?.selectionError ?: if (memory != null && memory.savedSelectionRevision < memory.selectionRevision) "Запоминаем выбор…"
            else if (valid) "Выбор применяется автоматически" else
            "Дополните выбранные значения для применения.", style = MaterialTheme.typography.bodySmall)
        WorkspaceChoices("О чём говорим", listOf("Общий вопрос", "Портфель", "Инструмент"), mode) { mode = it }
        if (mode != 0) {
            WorkspaceChoicePicker("Счёт", accountId.orEmpty(), listOf(WorkspaceSuggestion("", "Все мои счета")) +
                accounts.map { WorkspaceSuggestion(it.id, it.name) }) {
                accountId = it.takeIf(String::isNotBlank); instrument = null
            }
            if (!validAccount) Text("Выбранный счёт не найден в текущем снимке. Дождитесь загрузки или выберите доступный счёт, включая «Все мои счета».")
            if (mode == 2) {
                WorkspaceChoicePicker("Инструмент", instrument.orEmpty(), positions.map {
                    WorkspaceSuggestion(it.id, it.title, listOfNotNull(it.ticker, it.isin).joinToString(" "))
                }) { instrument = it }
                if (instrument == contextInstrument && contextEventId != null) {
                    Text("Контекст включает выбранную публикацию из досье.", style = MaterialTheme.typography.bodySmall)
                    WorkspaceCheckbox("Включить эту публикацию", keepEvent) { keepEvent = it }
                }
            }
            DetailFold("Период операций", initiallyOpen = start.isNotBlank()) {
                WorkspaceTextInput(start, { start = it.take(10) }, "С · ГГГГ-ММ-ДД", Modifier.fillMaxWidth())
                WorkspaceTextInput(end, { end = it.take(10) }, "По · ГГГГ-ММ-ДД", Modifier.fillMaxWidth())
                val today = remember { LocalDate.now() }
                WorkspaceSuggestionRow("", listOf(WorkspaceSuggestion("month", "Последний месяц"),
                    WorkspaceSuggestion("year", "С начала года"), WorkspaceSuggestion("all", "Весь период"))) { period ->
                    start = when (period) { "month" -> today.minusMonths(1).toString(); "year" -> today.withDayOfYear(1).toString(); else -> "" }
                    end = if (period == "all") "" else today.toString()
                }
                Text("Период ограничивает доступные операции. Текущая оценка портфеля сохраняет фактическую дату снимка.", style = MaterialTheme.typography.bodySmall)
                if (!validRange) Text("Укажите обе даты в правильном порядке.", color = MaterialTheme.colorScheme.error)
            }
        }
        SpectrumSecondaryButton("Готово", onClose, Modifier.fillMaxWidth())
    }
}

@Composable
fun VerifiedFact(value: Any?, label: String = "Наблюдение") {
    when (value) {
        null, JSONObject.NULL -> Text(label + ": значение не получено")
        is JSONObject -> {
            if (value.has("amount") && value.has("currency")) Text(label + ": " + PrivateValue(moneyText(value))) else {
                value.optString("title").takeIf(String::isNotBlank)?.let { Text(it, style = MaterialTheme.typography.titleSmall) }
                value.keys().asSequence().filter { it !in setOf("instrument_uid", "account_id", "title", "source_ids", "id") }.forEach { key ->
                    val title = factLabel(key)
                    val field = value.opt(key)
                    if (field is JSONObject) VerifiedFact(field, title)
                    else if (field is org.json.JSONArray) {
                        for (index in 0 until field.length()) VerifiedFact(field.opt(index), title)
                    } else Text(title + ": " + if (field == null || field == JSONObject.NULL) "Не получено" else if (field is Boolean) (if (field) "Да" else "Нет") else PrivateValue(field.toString()))
                }
            }
        }
        else -> Text(label + ": " + PrivateValue(value.toString()))
    }
}

private fun factLabel(key: String) = when (key) {
    "quantity" -> "Количество"; "value" -> "Оценка"; "blocked" -> "Ограничена"; "blocked_quantity" -> "Ограниченное количество"
    "sector" -> "Отрасль"; "instrument_type" -> "Тип"; "share_percent" -> "Доля, %"; "limit_percent" -> "Лимит, %"; "breached" -> "Превышение"
    "summary" -> "Содержание"; "occurred_at" -> "Дата события"; "relationship" -> "Связь"; "complete" -> "Полнота подтверждена"
    "start" -> "Начало"; "end" -> "Конец"; "flows" -> "Денежные потоки"; "category" -> "Категория"; "amount" -> "Сумма"
    "basis" -> "Основание"; "balance" -> "Капитал"; "at", "date" -> "Дата"; else -> key.replace('_', ' ').take(100)
}


private fun editedChatContext(mode: Int, base: String, instrument: String?, accountId: String?,
    period: Pair<String, String>, eventId: String?): ChatContext {
    val (start, end) = period
    val title = base + if (mode != 0 && start.isNotBlank()) " · " + start + " — " + end else ""
    return ChatContext(listOf("general", "portfolio", "instrument")[mode], if (mode == 2) instrument else null, title,
        if (mode == 0) null else accountId, start.takeIf { mode != 0 && it.isNotBlank() },
        end.takeIf { mode != 0 && it.isNotBlank() }, eventId.takeIf { mode == 2 })
}
