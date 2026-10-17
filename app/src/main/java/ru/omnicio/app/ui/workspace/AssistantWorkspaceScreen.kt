package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

@Composable
fun AssistantWorkspaceScreen(onBack: () -> Unit, onPortfolio: () -> Unit,
    onActions: () -> Unit, onStrategy: () -> Unit) {
    val session = LocalWorkspaceSession.current
    val questionContext = LocalChatContext.current
    val threads = rememberWorkspaceResource("/workspace/chat/threads")
    var threadId by rememberSaveable(session.userId) { mutableStateOf("") }
    var question by rememberSaveable(session.userId) { mutableStateOf("") }
    var jobId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var tier by rememberSaveable(session.userId) { mutableIntStateOf(0) }
    var showThreads by rememberSaveable { mutableStateOf(false) }
    var editingContext by rememberSaveable { mutableStateOf(false) }
    var initialized by remember(session.userId) { mutableStateOf(false) }
    var estimate by remember { mutableStateOf<JSONObject?>(null) }
    var estimateSignature by remember { mutableStateOf("") }
    val messages = rememberWorkspaceResource("/workspace/chat/threads/" + threadId + "/messages", threadId.isNotBlank())
    val messageItems = messages.data?.records("items").orEmpty()
    val send = rememberWorkspaceAction { result ->
        jobId = result.optString("job_id").takeIf { it.isNotBlank() }
        question = ""; estimate = null; messages.refresh()
    }
    val create = rememberWorkspaceAction { result ->
        threadId = result.text("thread_id", ""); threads.refresh()
    }
    val tiers = listOf("fast", "standard", "premium")
    val signature = question + "|" + questionContext.json().toString() + "|" + tiers[tier]
    val startMessage: () -> Unit = {
        send.perform("/workspace/chat/threads/" + threadId + "/messages",
            JSONObject().put("request_id", UUID.randomUUID().toString()).put("text", question.trim())
                .put("context", questionContext.json()).put("tier", tiers[tier]), job = true)
    }
    val estimateAction = rememberWorkspaceAction { result ->
        estimate = result; estimateSignature = signature
        if (tier < 2 && result.optBoolean("available")) startMessage()
    }
    val valid = question.isNotBlank() && question.length <= 4_000 && threadId.isNotBlank()
    val busy = send.busy || estimateAction.busy || jobId != null
    LaunchedEffect(threads.data) {
        if (!initialized && threads.data != null) {
            initialized = true
            if (threadId.isBlank()) {
                val first = threads.data?.records("items")?.firstOrNull()
                if (first != null) threadId = first.text("thread_id", "")
                else create.perform("/workspace/chat/threads", JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", questionContext.title))
            }
        }
    }
    val listState = rememberLazyListState()
    LaunchedEffect(messageItems.size) { if (messageItems.isNotEmpty()) listState.animateScrollToItem(messageItems.size) }
    WorkspaceDetailPage("Ассистент", "Объяснения с проверяемыми основаниями", onBack, SpectrumSymbol.Analyst) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                state = listState, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { SpectrumCard(emphasized = true) {
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        SpatialIcon("analyst", Modifier.size(64.dp), state = if (busy) SpatialState.Loading else if (send.error != null) SpatialState.Attention else SpatialState.Idle)
                        Column(Modifier.weight(1f)) {
                            Text(questionContext.title, style = MaterialTheme.typography.titleLarge)
                            Text("Контекст виден в каждом запросе. Числа и источники проверяются отдельно от объяснения.", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    SpectrumSecondaryButton("Диалоги", { showThreads = !showThreads }, Modifier.fillMaxWidth())
                    SpectrumSecondaryButton("Изменить контекст", { editingContext = true }, Modifier.fillMaxWidth(), !busy)
                    if (showThreads) {
                        threads.data?.records("items").orEmpty().forEach { item ->
                            SpectrumSecondaryButton(item.text("title", "Диалог"), { threadId = item.text("thread_id", ""); showThreads = false }, Modifier.fillMaxWidth(), !busy)
                        }
                        SpectrumSecondaryButton("Новый диалог", { create.perform("/workspace/chat/threads", JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", questionContext.title)) }, Modifier.fillMaxWidth(), !busy && !create.busy)
                    }
                } }
                item { WorkspaceRequestState(threads); WorkspaceRequestState(messages); WorkspaceActionState(create) }
                items(messageItems, key = { it.text("id") }) { message -> AssistantMessage(message, onPortfolio, onActions, onStrategy) }
                if (messageItems.isEmpty() && !messages.busy) item { WorkspaceEmpty("С чего начнём?", "Спросите о позиции, изменениях капитала или правилах стратегии. Ответ появится после фактического запроса к модели.") }
                jobId?.let { id -> item { WorkspaceJobPanel(id, onCompleted = { messages.refresh(); threads.refresh(); jobId = null }, onClose = { jobId = null }) } }
                item { WorkspaceActionState(send); WorkspaceActionState(estimateAction) }
                item { PendingJobRecovery(onThreadRecovered = { threadId = it }) { jobId = it } }
                estimate?.let { value -> item { SpectrumCard {
                    Text(if (value.optBoolean("available")) "Оценка расхода" else "Модель пока недоступна", style = MaterialTheme.typography.titleMedium)
                    Text(value.optJSONObject("estimated_upper_bound")?.let(::moneyText) ?: "Точная стоимость не подтверждена")
                    Text("Оценка ограничивает запрос; окончательный расход зависит от фактического использования.", style = MaterialTheme.typography.bodySmall)
                    if (!value.optBoolean("available")) Text("Проверьте готовность сервиса в истории анализов.")
                } } }
            }
            SpectrumCard(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
                DetailFold("Глубина ответа: " + listOf("Кратко", "Подробно", "Глубокий разбор")[tier]) {
                    WorkspaceChoices("Выбор модели", listOf("Кратко", "Подробно", "Глубокий разбор"), tier) { if (!busy) { tier = it; estimate = null } }
                }
                WorkspaceTextInput(question, { question = it.take(4_000); estimate = null }, "Ваш вопрос", singleLine = false,
                    modifier = Modifier.fillMaxWidth(), enabled = !busy)
                val approvedDeep = tier == 2 && estimateSignature == signature && estimate?.optBoolean("available") == true
                SpectrumPrimaryButton(if (approvedDeep) "Отправить глубокий запрос" else if (tier == 2) "Проверить стоимость" else "Отправить",
                    { if (approvedDeep) startMessage() else estimateAction.perform("/workspace/chat/estimate",
                        JSONObject().put("text", question.trim()).put("context", questionContext.json()).put("tier", tiers[tier])) },
                    Modifier.fillMaxWidth(), enabled = valid && !busy, symbol = SpectrumSymbol.Messages)
            }
        }
    }
    if (editingContext) ChatContextEditor(questionContext) { editingContext = false }
}

@Composable
private fun AssistantMessage(message: JSONObject, onPortfolio: () -> Unit, onActions: () -> Unit, onStrategy: () -> Unit) {
    val assistant = message.text("role", "") == "assistant"
    val navigate = LocalEvidenceNavigator.current
    val workspace = LocalWorkspaceNavigator.current
    SpectrumCard(emphasized = assistant) {
        Text(if (assistant) "Analyst AI" else "Вы", style = MaterialTheme.typography.labelLarge)
        Text(PrivateValue(message.text("text", "")), style = MaterialTheme.typography.bodyLarge)
        Text(localMoment(message.text("created_at", "")), style = MaterialTheme.typography.bodySmall)
        EvidenceLinks(message.records("evidence"), message.records("highlights"))
        message.records("claims").forEach { claim -> DetailFold("Проверить основание утверждения") {
            Text("Интерпретация аналитика", style = MaterialTheme.typography.labelMedium)
            Text(PrivateValue(claim.text("text", "")))
            val ids = claim.strings("fact_ids")
            message.records("facts").filter { it.text("id") in ids }.forEach { fact ->
                VerifiedFact(fact.opt("value"))
                Text("Наблюдение от " + localMoment(fact.text("as_of", "")), style = MaterialTheme.typography.bodySmall)
                EvidenceLinks(message.records("sources").filter { it.text("id") in fact.strings("source_ids") })
            }
            if (ids.isEmpty()) Text("Общее объяснение без отдельного наблюдения о портфеле.")
        } }
        message.strings("uncertainties").forEach { Text("Требует проверки: " + it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        message.records("actions").forEach { action ->
            val actionId = action.text("type", action.text("action", ""))
            val callback: (() -> Unit)? = when (actionId) {
                "open_portfolio" -> onPortfolio
                "open_actions" -> onActions
                "prepare_strategy", "open_strategy" -> onStrategy
                "open_instrument" -> ({ navigate(EvidenceTarget("instrument", action.text("id", ""))) })
                "open_risks" -> ({ navigate(EvidenceTarget("risk", action.text("id", ""))) })
                "open_sources" -> ({ workspace(WorkspaceRoute.Library) })
                else -> null
            }
            val label = when (actionId) { "open_instrument" -> "Показать инструмент"; "open_risks" -> "Проверить риски"; "open_strategy" -> "Показать стратегию"; "open_sources" -> "Открыть исследования"; else -> "Открыть раздел" }
            if (callback != null) SpectrumSecondaryButton(action.text("label", label), callback, Modifier.fillMaxWidth())
        }
    }
}

@Composable
fun PendingJobRecovery(onThreadRecovered: (String) -> Unit = {}, onRecovered: (String) -> Unit) {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val storage = remember(context) { ru.omnicio.app.data.workspace.JobCheckpointStore(context) }
    var checkpoints by remember(session.userId) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var selected by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(session.userId) { checkpoints = withContext(Dispatchers.IO) { storage.list(session.userId) } }
    val recovery = rememberWorkspaceAction { result ->
        val path = selected?.text("path", "").orEmpty()
        val thread = Regex("/workspace/chat/threads/([^/]+)/messages").matchEntire(path)?.groupValues?.getOrNull(1)
        if (thread != null) onThreadRecovered(thread)
        result.optString("job_id").takeIf(String::isNotBlank)?.let(onRecovered)
    }
    if (checkpoints.isNotEmpty()) SpectrumCard {
        DetailFold("Сохранённые задания · " + checkpoints.size) {
            Text("Восстановим уже отправленный запрос по его идентификатору. Новый платный запрос не создаётся.")
            checkpoints.forEach { point ->
                val path = point.text("path", "")
                val title = when { path.contains("/chat/") -> "Диалог"; path.contains("/reconcile") -> "Сверка операций"; path.contains("/refresh") -> "Источники"; else -> "Анализ" }
                SpectrumSecondaryButton(title + " · " + localMoment(point.text("created_at", "сохранённый запрос")), {
                    selected = point
                    recovery.perform("/workspace/jobs/by-request/" + ru.omnicio.app.data.workspace.VolumeWorkspaceClient.encode(point.text("request_id", "")), method = "GET")
                }, Modifier.fillMaxWidth(), !recovery.busy)
            }
            WorkspaceActionState(recovery)
        }
    }
}
