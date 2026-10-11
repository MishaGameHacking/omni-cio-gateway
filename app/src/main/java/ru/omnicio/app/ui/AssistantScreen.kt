package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.R

internal data class AssistantActions(
    val reload: () -> Unit = {}, val create: () -> Unit = {},
    val select: (String) -> Unit = {}, val edit: (String) -> Unit = {},
    val accept: (Boolean) -> Unit = {}, val send: () -> Unit = {}, val older: () -> Unit = {},
    val retry: () -> Unit = {},
    val task: (String) -> Unit = {},
)

@Composable
internal fun AssistantScreen(
    state: AppUiState, onMarkRead: (String) -> Unit, onLoadMore: () -> Unit,
    actions: AssistantActions = AssistantActions(),
) {
    var events by remember { mutableStateOf(false) }
    val workspace = state.workspace
    val listState = rememberLazyListState()
    LaunchedEffect(events, state.assistant.conversation?.id, state.assistant.conversation?.messages?.lastOrNull()?.position) {
        if (!events && state.assistant.conversation != null) {
            withFrameNanos { }
            val count = listState.layoutInfo.totalItemsCount
            if (count > 0) listState.scrollToItem(count - 1)
        }
    }
    LazyColumn(state = listState, modifier = Modifier.imePadding(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Text("Помощник", style = MaterialTheme.typography.headlineLarge)
            Text("Ваш портфель и вопросы об инвестициях", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !events, onClick = { events = false }, label = { Text("Диалог") })
                FilterChip(selected = events, onClick = { events = true }, label = { Text("События") })
            }
        }
        when {
        !events -> chatItems(state, actions)
        workspace == null -> item { EmptyState("События не получены", "Обновите данные. Сообщения не создаются в приложении.", R.drawable.ic_assistant) }
        state.amountsHidden -> item { EmptyState("События скрыты", "Отключите скрытие сумм на Обзоре, чтобы прочитать финансовые сведения в событиях.") }
        else -> {
            if (workspace.events.isEmpty()) item { EmptyState("Пока нет событий", "Сервер ещё не передал события для этого аккаунта.", R.drawable.ic_assistant) }
            items(workspace.events, key = { it.id }) { event ->
                OmniCard {
                    Text(timestampLabel(event.at), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (event.severity in setOf("critical", "warning")) Text("Требует внимания", color = MaterialTheme.colorScheme.error)
                    SectionTitle(event.title)
                    Text(event.detail)
                    Text("Источник: ${event.source ?: "не указан сервером"}", style = MaterialTheme.typography.bodySmall)
                    if (!event.read) TextButton(onClick = { onMarkRead(event.id) }, enabled = !state.busy) { Text("Отметить прочитанным") }
                }
            }
            if (workspace.nextEventCursor != null) item {
                OutlinedButton(onClick = onLoadMore, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("Загрузить ещё") }
            }
        }
        }
    }
}


private fun LazyListScope.chatItems(state: AppUiState, actions: AssistantActions) {
    val chat = state.assistant
    if (state.amountsHidden) {
        item { EmptyState("Диалог скрыт", "Отключите скрытие сумм на Обзоре, чтобы читать и отправлять сообщения.") }
        return
    }
    item {
        Text("Помощник использует доступный серверу снимок счёта и сохранённые условия. Старые ответы относятся к данным на момент вопроса.",
            style = MaterialTheme.typography.bodySmall)
        OutlinedButton(onClick = actions.reload, enabled = !state.busy) { Text("Проверить ответ") }
    }
    if (!chat.loaded) {
        item { EmptyState("Загрузите диалог", "Проверка ответа получает историю с сервера и не отправляет вопрос ИИ повторно.") }
        return
    }
    if (!chat.available) item {
        EmptyState("ИИ ещё не подключён", "Сервер пока не готов отвечать. Историю можно читать; настройки модели выполняет OMNICIO.")
    }
    item {
        var expanded by remember { mutableStateOf(false) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f)) {
                OutlinedButton(onClick = { expanded = true }, enabled = !state.busy && chat.conversations.isNotEmpty() && chat.pendingRequest == null) {
                    Text(chat.conversation?.title ?: "История диалогов")
                }
                DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    chat.conversations.forEach { summary ->
                        DropdownMenuItem(text = { Text("${summary.title} · ${timestampLabel(summary.at)}") }, onClick = {
                            expanded = false
                            actions.select(summary.id)
                        })
                    }
                }
            }
            TextButton(onClick = actions.create, enabled = !state.busy && chat.available && chat.pendingRequest == null) {
                Text("Новый диалог")
            }
        }
    }
    val conversation = chat.conversation
    if (conversation == null) {
        item { Text("Начните новый диалог. Можно спросить о составе портфеля, концентрации или значении показателей.") }
        return
    }
    if (conversation.nextBefore != null) item {
        TextButton(onClick = actions.older, enabled = !state.busy) { Text("Ранние сообщения") }
    }
    items(conversation.messages, key = { "message-${conversation.id}-${it.position}" }) { message ->
        ChatBubble(message)
    }
    item { ChatComposer(state, actions) }
}

@Composable
private fun ChatComposer(state: AppUiState, actions: AssistantActions) {
    val chat = state.assistant
    Column {
        AssistantTaskChoice(state, actions.task)
        if (chat.pendingRequest != null || chat.conversation?.requestStatus == "running") {
            Text("Ответ ещё не подтверждён. Нажмите «Проверить ответ» через некоторое время.")
            if (chat.pendingMissing) {
                Text("Сервер ещё не нашёл запрос. Можно повторить именно его: идентификатор останется прежним.")
                OutlinedButton(onClick = actions.retry, enabled = !state.busy && chat.available && chat.contextAccepted) {
                    Text("Повторить этот запрос")
                }
            }
        } else if (chat.conversation?.requestStatus in setOf("uncertain", "cancelled")) {
            Text("Предыдущий запрос не завершён. Готового ответа нет; новый вопрос отправляется только по вашему нажатию.")
        }
        Row {
            Checkbox(checked = chat.contextAccepted, onCheckedChange = actions.accept, enabled = !state.busy)
            Text("Разрешаю передавать модели ИИ мой вопрос и сведения о портфеле для ответа. Токен брокера не передаётся.",
                Modifier.padding(top = 10.dp), style = MaterialTheme.typography.bodySmall)
        }
        OutlinedTextField(value = chat.draft, onValueChange = actions.edit,
            label = { Text("Вопрос помощнику") }, modifier = Modifier.fillMaxWidth(),
            enabled = !state.busy && chat.available && chat.pendingRequest == null,
            minLines = 2, maxLines = 6, supportingText = { Text("${chat.draft.length} / 4000") })
        Button(onClick = actions.send, enabled = !state.busy && chat.canSend,
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) { Text("Отправить") }
    }
}

@Composable
private fun AssistantTaskChoice(state: AppUiState, select: (String) -> Unit) {
    val chat = state.assistant
    if (chat.availableTasks.size <= 1) return
    Column {
        mapOf("explain" to "Объяснить кратко", "analyze" to "Подробно разобрать",
            "review" to "Проверить противоречия").forEach { (task, label) ->
            if (task in chat.availableTasks) FilterChip(selected = chat.task == task,
                onClick = { select(task) }, label = { Text(label) },
                enabled = !state.busy && chat.pendingRequest == null)
        }
        Text("Подробный разбор и проверка могут занять больше времени. Источники ограничены данными, полученными сервером.",
            style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ChatBubble(message: ChatMessage) {
    val uriHandler = LocalUriHandler.current
    OmniCard {
        Text(if (message.role == "user") "Вы" else "OMNICIO", style = MaterialTheme.typography.titleSmall)
        Text(message.content)
        Text(timestampLabel(message.at), style = MaterialTheme.typography.bodySmall)
        if (message.sources.isNotEmpty()) {
            var expanded by remember { mutableStateOf(false) }
            TextButton(onClick = { expanded = !expanded }) { Text("Источники ответа") }
            if (expanded) message.sources.forEach { source ->
                Text(source.title, style = MaterialTheme.typography.bodyMedium)
                source.at?.let { Text(timestampLabel(it), style = MaterialTheme.typography.bodySmall) }
                val uri = source.url?.let { runCatching { java.net.URI(it) }.getOrNull() }
                if (uri?.scheme == "https" && uri.host != null && uri.userInfo == null) {
                    TextButton(onClick = { runCatching { uriHandler.openUri(uri.toString()) } }) { Text("Открыть источник") }
                }
            }
        }
    }
}
