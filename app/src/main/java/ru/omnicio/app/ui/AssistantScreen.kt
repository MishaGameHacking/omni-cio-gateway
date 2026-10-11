package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.R

@Composable
internal fun AssistantScreen(state: AppUiState, model: OmnicioViewModel) {
    val workspace = state.workspace
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Text("Помощник", style = MaterialTheme.typography.headlineLarge)
            Text("События и объяснения с сервера", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (workspace == null) item { EmptyState("События не получены", "Обновите данные. Сообщения не создаются в приложении.", R.drawable.ic_assistant) }
        else if (state.amountsHidden) item { EmptyState("События скрыты", "Отключите скрытие сумм на Обзоре, чтобы прочитать финансовые сведения в событиях.") }
        else {
            if (workspace.events.isEmpty()) item { EmptyState("Пока нет событий", "Сервер ещё не передал события для этого аккаунта.", R.drawable.ic_assistant) }
            items(workspace.events, key = { it.id }) { event ->
                OmniCard {
                    Text(timestampLabel(event.at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (event.severity in setOf("critical", "warning")) Text("Требует внимания", color = MaterialTheme.colorScheme.error)
                    SectionTitle(event.title)
                    Text(event.detail)
                    Text("Источник: ${event.source ?: "не указан сервером"}", style = MaterialTheme.typography.bodySmall)
                    if (!event.read) TextButton(onClick = { model.markRead(event.id) }, enabled = !state.busy) { Text("Отметить прочитанным") }
                }
            }
            if (workspace.nextEventCursor != null) item {
                OutlinedButton(onClick = model::loadMoreEvents, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Загрузить ещё") }
            }
        }
    }
}
