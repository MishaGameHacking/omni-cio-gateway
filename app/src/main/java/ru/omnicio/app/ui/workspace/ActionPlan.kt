package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.time.Instant
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import ru.omnicio.app.ui.spectrum.*

/** Display contract only. Production must receive a verified plan; no order is submitted here. */
data class PlanAction(val id: String, val title: String, val account: String, val instrument: String,
    val quantity: String, val amount: String, val reason: String, val source: String,
    val observedAt: String, val validUntil: String, val before: String, val after: String,
    val limitations: List<String>, val status: PlanActionStatus = PlanActionStatus.Proposed)
enum class PlanActionStatus(val title: String) {
    Proposed("Предложено"), AwaitingBroker("Проверить у брокера"), Partial("Частично исполнено"),
    Confirmed("Исполнено · подтверждено"), Rejected("Отклонено"), Expired("Устарело")
}

@Composable
fun ActionPlan(actions: List<PlanAction>?, onOpenBroker: (PlanAction) -> Unit = {}) {
    if (actions == null) {
        WorkspaceEmpty("План действий готовится", "Расчёт точных сумм и сделок ещё не подключён. Доступный обзор находится во вкладке «Анализ».")
        return
    }
    if (actions.isEmpty()) { WorkspaceEmpty("Действий не требуется", "Последний подтверждённый план не содержит действий. Дату и источник проверки смотрите в анализе."); return }
    Text("Ваш план · ${actions.size}", style = MaterialTheme.typography.titleLarge)
    actions.forEach { action -> ActionPlanCard(action, onOpenBroker) }
}

@Composable
private fun ActionPlanCard(action: PlanAction, openBroker: (PlanAction) -> Unit) {
    var defer by remember { mutableStateOf(false) }
    var reason by rememberSaveable(action.id) { mutableStateOf<String?>(null) }
    val expires = runCatching { Instant.parse(action.validUntil) }.getOrNull()
    val now by produceState(Instant.now(), action.id) {
        while (isActive) { value = Instant.now(); delay(30_000) }
    }
    val expired = action.status == PlanActionStatus.Proposed && (expires == null || !expires.isAfter(now))
    SpectrumCard(emphasized = action.status == PlanActionStatus.Proposed && !expired) {
        SpectrumBadge(if (expired) "Срок актуальности истёк" else action.status.title)
        Text(action.title, style = MaterialTheme.typography.titleLarge)
        Text("${action.instrument} · ${action.account}")
        Text(PrivateValue("${action.quantity} · ${action.amount}"), style = MaterialTheme.typography.titleMedium)
        Text(action.reason)
        Text("Срок предложения: ${action.validUntil}", style = MaterialTheme.typography.bodySmall)
        DetailFold("Почему и что изменится") {
            Text("Сейчас: ${PrivateValue(action.before)}")
            Text("После: ${PrivateValue(action.after)}")
            Text("Источник: ${action.source} · ${action.observedAt}")
            action.limitations.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
        if (action.status == PlanActionStatus.Proposed && !expired) {
            SpectrumPrimaryButton("Проверить в приложении брокера", { if (expires?.isAfter(Instant.now()) == true) openBroker(action) }, Modifier.fillMaxWidth())
            TextButton(onClick = { defer = true }) { Text(if (reason == null) "Отложить" else "Отложено: $reason · изменить") }
            if (reason != null) TextButton(onClick = { reason = null }) { Text("Вернуть в план") }
        }
        Text("Переход к брокеру не подтверждает исполнение. Состояние сделки должно поступить от брокера.", style = MaterialTheme.typography.bodySmall)
    }
    if (defer) AlertDialog(onDismissRequest = { defer = false }, title = { Text("Почему откладываете?") },
        text = { Column { listOf("Нужно подумать", "Недостаточно средств", "Не согласен с выводом").forEach { choice ->
            TextButton(onClick = { reason = choice; defer = false }) { Text(choice) }
        }; Text("Отметка сохраняется только в интерфейсе текущего плана.", style = MaterialTheme.typography.bodySmall) } },
        confirmButton = { TextButton(onClick = { defer = false }) { Text("Отмена") } })
}
