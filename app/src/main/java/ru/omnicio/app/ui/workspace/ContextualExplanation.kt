package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.ui.spectrum.*

/** A local navigation intent. It never sends a request or substitutes generated prose. */
data class PendingExplanation(val id: String, val context: ChatContext, val question: String) {
    fun json(): JSONObject = JSONObject().put("id", id).put("context", context.json())
        .put("title", context.title).put("question", question)
}

val LocalPendingExplanation = staticCompositionLocalOf<PendingExplanation?> { null }
val LocalAskExplanation = staticCompositionLocalOf<(PendingExplanation) -> Unit> { {} }
val LocalApplyExplanation = staticCompositionLocalOf<(String) -> Unit> { {} }
val LocalDismissExplanation = staticCompositionLocalOf<(String) -> Unit> { {} }

fun explanationRequest(kind: String, identifier: String, title: String): PendingExplanation {
    require(kind in setOf("risk", "notification", "analysis", "candidate", "document"))
    require(identifier.isNotBlank() && identifier.length <= 200)
    val question = when (kind) {
        "risk" -> "Объясни этот риск моего инвестиционного портфеля простыми словами: что подтверждено, почему это важно и чего не хватает для решения."
        "notification" -> "Объясни это уведомление о моём инвестиционном портфеле: что произошло, на каких данных основано и что стоит проверить сейчас."
        "analysis" -> "Объясни вывод анализа моего инвестиционного портфеля по сохранённым фактам. Отдели прошлые наблюдения от текущего состояния и укажи неопределённость."
        "document" -> "Объясни эту публикацию об инвестициях: что сообщает источник, дата и период отчётности, какие выводы подтверждены текстом и что ещё нужно проверить."
        else -> "Объясни проверку этого кандидата для инвестиционного портфеля: почему он попал в отбор, какие ограничения прошёл и каких оснований ещё не хватает."
    }
    return PendingExplanation(UUID.randomUUID().toString(), ChatContext(title = title,
        explanationKind = kind, explanationId = identifier), question)
}

fun pendingExplanation(raw: String?): PendingExplanation? = runCatching {
    raw ?: return@runCatching null
    val value = JSONObject(raw)
    val target = value.getJSONObject("context").getJSONObject("explanation")
    val context = ChatContext(title = value.getString("title"),
        explanationKind = target.getString("kind"), explanationId = target.getString("id"))
    require(context.explanationKind in setOf("risk", "notification", "analysis", "candidate", "document"))
    require(!context.explanationId.isNullOrBlank() && context.explanationId.length <= 200)
    PendingExplanation(value.getString("id"), context, value.getString("question"))
}.getOrNull()

/** Context is applied with its question; declining replacement preserves both draft and context. */
@Composable
fun ApplyPendingExplanation(currentQuestion: String, canEditDraft: Boolean, onApply: (String) -> Unit) {
    val pending = LocalPendingExplanation.current ?: return
    val applyContext = LocalApplyExplanation.current
    val dismiss = LocalDismissExplanation.current
    val apply: () -> Unit = { onApply(pending.question); applyContext(pending.id) }
    LaunchedEffect(pending.id, currentQuestion.isBlank(), canEditDraft) {
        if (currentQuestion.isBlank() && canEditDraft) apply()
    }
    if (currentQuestion.isNotBlank() || !canEditDraft) WorkspaceDialog("Объяснение ИИ", { dismiss(pending.id) }) {
        Text(pending.context.title)
        Text(if (canEditDraft) "В чате уже есть ваш черновик. Заменить его вопросом об этом объекте?"
            else "Сначала дождитесь завершения текущего запроса или восстановления его состояния.")
        if (canEditDraft) SpectrumPrimaryButton("Заменить черновик", apply, Modifier.fillMaxWidth())
        SpectrumSecondaryButton("Оставить мой вопрос", { dismiss(pending.id) }, Modifier.fillMaxWidth())
    }
}

@Composable
fun ExplainWithAiButton(kind: String, identifier: String, title: String,
    enabled: Boolean = true, beforeOpen: () -> Unit = {}) {
    val ask = LocalAskExplanation.current
    SpectrumSecondaryButton("Объяснить с ИИ", {
        beforeOpen()
        ask(explanationRequest(kind, identifier, title))
    }, Modifier.fillMaxWidth().testTag("explain-$kind"), enabled && identifier.isNotBlank())
}

