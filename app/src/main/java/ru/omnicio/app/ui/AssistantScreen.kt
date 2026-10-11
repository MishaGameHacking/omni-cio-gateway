package ru.omnicio.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import ru.omnicio.app.ui.theme.OmniSpacing

@Composable
internal fun AssistantScreen(
    onOpenPosition: (String) -> Unit,
) {
    val messages = assistantFeed()
    val uriHandler = LocalUriHandler.current
    var actionNotice by rememberSaveable { mutableStateOf<String?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs)) {
                Text(
                    text = "Ваш помощник",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    text = "Автоматически собирает важные события и локальные расчёты.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        actionNotice?.let { notice ->
            item {
                InfoCard(
                    title = "Локальное действие",
                    body = notice,
                )
            }
        }
        items(
            items = messages,
            key = { it.eventKey },
        ) { message ->
            AssistantMessageCard(
                message = message,
                onAction = { action ->
                    when (action.kind) {
                        AssistantActionKind.OPEN_SOURCE -> action.target?.let(uriHandler::openUri)
                        AssistantActionKind.OPEN_POSITION -> action.target?.let(onOpenPosition)
                        AssistantActionKind.RUN_SCENARIO -> {
                            actionNotice =
                                "Сценарий отмечен локально. Приложение не отправляет брокерскую заявку."
                        }
                        AssistantActionKind.SYNC -> {
                            actionNotice =
                                "Синхронизация пока доступна только как безопасное демо-состояние."
                        }
                    }
                },
            )
        }
        item {
            Text(
                text = "Push-уведомления не содержат сумму портфеля и персональные позиции.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun AssistantMessageCard(
    message: AssistantMessage,
    onAction: (AssistantAction) -> Unit,
) {
    val accent = assistantAccent(message.type)
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = accent.copy(alpha = 0.10f),
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = message.type.label,
                    style = MaterialTheme.typography.labelLarge,
                    color = accent,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = message.occurredAt,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = message.changed,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = message.relevance,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = formatAssistantImpact(message.impact),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
            )
            if (message.sources.isNotEmpty()) {
                Text(
                    text = message.sources.joinToString(separator = " · ") { it.name },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (!message.sufficientData) {
                Text(
                    text = "Недостаточно данных для дополнительного действия.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            message.action?.let { action ->
                Button(
                    onClick = { onAction(action) },
                ) {
                    Text(action.label)
                }
            }
        }
    }
}

@Composable
private fun assistantAccent(type: AssistantEventType): Color = when (type) {
    AssistantEventType.MATERIAL_EVENT,
    AssistantEventType.RISK_CHANGE,
    -> MaterialTheme.colorScheme.error
    AssistantEventType.PAYOUT -> MaterialTheme.colorScheme.tertiary
    AssistantEventType.CASH_CHANGE -> MaterialTheme.colorScheme.secondary
    AssistantEventType.SCENARIO_RESULT -> MaterialTheme.colorScheme.primary
    AssistantEventType.ANALYSIS_STALE,
    AssistantEventType.SYNC_REQUIRED,
    -> MaterialTheme.colorScheme.onSurfaceVariant
}
