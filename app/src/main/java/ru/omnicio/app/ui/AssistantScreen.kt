package ru.omnicio.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
            StatusPill("ДЕМО · UI-04 · АВТОМАТИЧЕСКАЯ ЛЕНТА")
        }
        item {
            Text(
                text = "Помощник",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.semantics { heading() },
            )
        }
        item {
            Text(
                text = "Без поля ввода, выбора модели и свободного чата. Повторное открытие этой ленты не запускает LLM и не расходует токены.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
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
                        AssistantActionKind.OPEN_SOURCE -> {
                            action.target?.let(uriHandler::openUri)
                        }
                        AssistantActionKind.OPEN_POSITION -> {
                            action.target?.let(onOpenPosition)
                        }
                        AssistantActionKind.RUN_SCENARIO -> {
                            actionNotice =
                                "Сценарий отмечен локально. UI-04 не отправляет заявку брокеру и не запускает LLM."
                        }
                        AssistantActionKind.SYNC -> {
                            actionNotice =
                                "Синхронизация появится на системном этапе. Сейчас это безопасный UI-fixture без сети."
                        }
                    }
                },
            )
        }
        item {
            Text(
                text = "Обычный push для этих событий содержит только общий безопасный текст без сумм, позиций и персональных деталей.",
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(
                text = message.type.label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = message.changed,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            AssistantField(
                label = "Почему это относится к портфелю",
                value = message.relevance,
            )
            AssistantField(
                label = "Локальный расчёт",
                value = formatAssistantImpact(message.impact),
            )
            AssistantField(
                label = "Источники",
                value = message.sources.joinToString(separator = "\n") { it.name },
            )
            AssistantField(
                label = "Время",
                value = message.occurredAt,
            )

            if (!message.sufficientData) {
                Text(
                    text = "Данных недостаточно: OMNICIO не придумывает действие.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            message.action?.let { action ->
                Button(
                    onClick = { onAction(action) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(action.label)
                }
            }
        }
    }
}

@Composable
private fun AssistantField(
    label: String,
    value: String,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
