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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.URLDecoder
import java.util.UUID
import ru.omnicio.app.data.workspace.JobCheckpointStore
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

/** An estimate and any following send share these exact immutable inputs. */
private data class ChatRequestSnapshot(val threadId: String, val text: String, val context: String, val tier: String) {
    fun payload(): JSONObject = JSONObject().put("thread_id", threadId).put("text", text)
        .put("context", JSONObject(context)).put("tier", tier)
    val signature: String get() = payload().toString()
}

private fun checkpointThread(point: JSONObject): String? =
    Regex("/workspace/chat/threads/([^/]+)/messages").matchEntire(point.text("path", ""))?.groupValues?.getOrNull(1)
        ?.let { runCatching { URLDecoder.decode(it, "UTF-8") }.getOrNull() }

private fun checkpointMatches(point: JSONObject, request: ChatRequestSnapshot): Boolean {
    val body = point.optJSONObject("request_body") ?: return false
    return checkpointThread(point) == request.threadId && body.optString("text") == request.text &&
        body.optString("tier") == request.tier && body.optJSONObject("context")?.toString() == request.context
}

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
    var pendingEstimate by remember(session.userId) { mutableStateOf<ChatRequestSnapshot?>(null) }
    var pendingSend by remember(session.userId) { mutableStateOf<ChatRequestSnapshot?>(null) }
    var awaitingRequestId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var restoringJob by remember(session.userId) { mutableStateOf(false) }
    val savedRequests = rememberJobCheckpoints()
    val tiers = listOf("fast", "standard", "premium")
    val request = ChatRequestSnapshot(threadId, question.trim(), questionContext.json().toString(), tiers[tier])
    val signature = request.signature
    val pendingQuestion = savedRequests.items.any { JobCheckpointStore.isUnconfirmedChat(it) || checkpointMatches(it, request) }
    val needsRecovery = savedRequests.loading || savedRequests.error != null || awaitingRequestId != null || pendingQuestion
    var cursors by rememberSaveable(session.userId, threadId) { mutableStateOf(listOf("")) }
    var jobState by remember(jobId) { mutableStateOf("queued") }
    val cursor = cursors.last()
    val messages = rememberWorkspaceResource("/workspace/chat/threads/" + threadId + "/messages" +
        (if (cursor.isBlank()) "" else "?before=" + ru.omnicio.app.data.workspace.VolumeWorkspaceClient.encode(cursor)), threadId.isNotBlank())
    val messageItems = messages.data?.records("items").orEmpty()
    val send = rememberWorkspaceAction(onPrepared = { awaitingRequestId = it }, onFailure = { failure ->
        if (!failure.requiresRecovery && failure.requestId == awaitingRequestId) {
            awaitingRequestId = null; pendingSend = null
        }
    }) { result ->
        jobId = result.optString("job_id").takeIf { it.isNotBlank() }
        if (pendingSend?.signature == signature) question = ""
        awaitingRequestId = null; pendingSend = null; estimate = null; messages.refresh()
    }
    val create = rememberWorkspaceAction { result ->
        threadId = result.text("thread_id", ""); threads.refresh()
    }
    val startMessage: (ChatRequestSnapshot) -> Unit = { selected ->
        if (!needsRecovery && jobId == null && !restoringJob && !send.busy) {
            val body = selected.payload().apply { remove("thread_id"); put("request_id", UUID.randomUUID().toString()) }
            pendingSend = selected
            send.perform("/workspace/chat/threads/" + VolumeWorkspaceClient.encode(selected.threadId) + "/messages", body, job = true)
        }
    }
    val estimateAction = rememberWorkspaceAction { result ->
        val selected = pendingEstimate
        pendingEstimate = null
        if (selected != null) {
            estimate = result; estimateSignature = selected.signature
            if (selected.signature == signature && selected.tier != "premium" && jobId == null && !restoringJob && !needsRecovery && result.optBoolean("available")) {
                startMessage(selected)
            }
        }
    }
    val valid = question.isNotBlank() && question.length <= 4_000 && threadId.isNotBlank()
    val busy = send.busy || estimateAction.busy || jobId != null || restoringJob || needsRecovery
    LaunchedEffect(savedRequests.loading, savedRequests.error, savedRequests.items, savedRequests.revision, awaitingRequestId) {
        if (!savedRequests.loading && savedRequests.error == null && savedRequests.revision == JobCheckpointStore.revision.value && awaitingRequestId != null &&
            savedRequests.items.none { it.text("request_id", "") == awaitingRequestId }) awaitingRequestId = null
    }
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
    LaunchedEffect(messageItems.lastOrNull()?.text("id"), cursor) {
        if (messageItems.isNotEmpty() && cursor.isBlank()) listState.animateScrollToItem(messageItems.size)
    }
    LaunchedEffect(cursor) { if (cursor.isNotBlank()) listState.scrollToItem(0) }
    WorkspaceDetailPage("Ассистент", "Объяснения с проверяемыми основаниями", onBack, SpectrumSymbol.Analyst) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                state = listState, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { SpectrumCard(emphasized = true) {
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        SpatialIcon("analyst", Modifier.size(64.dp), state = when {
                            jobId != null && jobState in setOf("failed", "uncertain", "cancelled") -> SpatialState.Attention
                            send.error != null || estimateAction.error != null -> SpatialState.Attention
                            busy -> SpatialState.Loading
                            messageItems.lastOrNull()?.text("role") == "assistant" -> SpatialState.Success
                            else -> SpatialState.Idle
                        })
                        Column(Modifier.weight(1f)) {
                            Text(questionContext.title, style = MaterialTheme.typography.titleLarge)
                            Text("Контекст виден в каждом запросе. Числа и источники проверяются отдельно от объяснения.", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    SpectrumSecondaryButton("Диалоги", { showThreads = !showThreads }, Modifier.fillMaxWidth())
                    SpectrumSecondaryButton("Изменить контекст", { editingContext = true }, Modifier.fillMaxWidth(), !busy)
                    if (questionContext.eventId != null) {
                        Text("Выбрана конкретная публикация. Аналитик проверит её связь с вашими позициями и отделит возможное влияние от подтверждённых фактов.",
                            style = MaterialTheme.typography.bodySmall)
                        if (question.isBlank()) SpectrumSecondaryButton("Подставить вопрос о событии", {
                            question = eventImpactQuestion; estimate = null
                        }, Modifier.fillMaxWidth().testTag("assistant-event-question"), !busy)
                        Text("Вопрос отправляется только кнопкой «Отправить», с обычной проверкой расхода.", style = MaterialTheme.typography.bodySmall)
                    }
                    if (showThreads) {
                        threads.data?.records("items").orEmpty().forEach { item ->
                            SpectrumSecondaryButton(item.text("title", "Диалог"), { threadId = item.text("thread_id", ""); showThreads = false }, Modifier.fillMaxWidth(), !busy)
                        }
                        SpectrumSecondaryButton("Новый диалог", { create.perform("/workspace/chat/threads", JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", questionContext.title)) }, Modifier.fillMaxWidth(), !busy && !create.busy)
                    }
                } }
                item { WorkspaceRequestState(threads); WorkspaceRequestState(messages); WorkspaceActionState(create) }
                if (messages.data?.optBoolean("has_more") == true) item {
                    SpectrumSecondaryButton("Более ранние сообщения", {
                        messages.data?.text("next_before", "")?.takeIf(String::isNotBlank)?.let { cursors = cursors + it }
                    }, Modifier.fillMaxWidth(), !messages.busy)
                }
                if (cursors.size > 1) item { SpectrumCard {
                    Text("Предыдущая часть диалога · страница " + cursors.size)
                    SpectrumSecondaryButton("К более новым сообщениям", { cursors = cursors.dropLast(1) }, Modifier.fillMaxWidth(), !messages.busy)
                    SpectrumSecondaryButton("К последним сообщениям", { cursors = listOf("") }, Modifier.fillMaxWidth(), !messages.busy)
                } }
                items(messageItems, key = { it.text("id") }) { message -> AssistantMessage(message, onPortfolio, onActions, onStrategy) }
                if (messageItems.isEmpty() && !messages.busy) item { WorkspaceEmpty("С чего начнём?", "Спросите о позиции, изменениях капитала или правилах стратегии. Ответ появится после фактического запроса к модели.") }
                jobId?.let { id -> item { WorkspaceJobPanel(id, onCompleted = { cursors = listOf(""); messages.refresh(); threads.refresh(); jobId = null },
                    onClose = { jobId = null }, onStateChanged = { jobState = it }) } }
                item { WorkspaceActionState(send); WorkspaceActionState(estimateAction) }
                item { PendingJobRecovery(savedRequests, onThreadRecovered = { threadId = it }, onRequestRecovered = { point ->
                    if (checkpointMatches(point, request)) question = ""
                    if (point.text("request_id", "") == awaitingRequestId) { awaitingRequestId = null; pendingSend = null }
                    estimate = null; cursors = listOf(""); messages.refresh(); threads.refresh()
                },
                    enabled = !send.busy && !estimateAction.busy && jobId == null,
                    onBusyChanged = { restoringJob = it }) { jobId = it } }
                estimate?.let { value -> item { SpectrumCard {
                    Text(if (value.optBoolean("available")) "Оценка расхода" else "Модель пока недоступна", style = MaterialTheme.typography.titleMedium)
                    Text(PrivateValue(value.optJSONObject("estimated_upper_bound")?.let(::moneyText) ?: "Точная стоимость не подтверждена"))
                    Text("Предварительная оценка по текущему контексту; фактическое использование учитывается сервером.", style = MaterialTheme.typography.bodySmall)
                    if (estimateSignature != signature) Text("Вопрос или контекст изменился. Перед отправкой стоимость будет проверена заново.", style = MaterialTheme.typography.bodySmall)
                    value.text("context_as_of", "").takeIf(String::isNotBlank)?.let { Text("Контекст от " + localMoment(it), style = MaterialTheme.typography.bodySmall) }
                    if (!value.optBoolean("available")) Text("Проверьте готовность сервиса в истории анализов.")
                } } }
            }
            SpectrumCard(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
                if (savedRequests.loading) Text("Проверяем сохранённые запросы…", style = MaterialTheme.typography.bodySmall)
                else if (needsRecovery) Text("Сверьте сохранённый вопрос перед новой отправкой.", style = MaterialTheme.typography.bodySmall)
                DetailFold("Глубина ответа: " + listOf("Кратко", "Подробно", "Глубокий разбор")[tier]) {
                    WorkspaceChoices("Выбор модели", listOf("Кратко", "Подробно", "Глубокий разбор"), tier) { if (!busy) { tier = it; estimate = null } }
                }
                WorkspaceTextInput(question, { question = it.take(4_000); estimate = null }, "Ваш вопрос", singleLine = false,
                    modifier = Modifier.fillMaxWidth(), enabled = !busy)
                val approvedDeep = tier == 2 && estimateSignature == signature && estimate?.optBoolean("available") == true
                SpectrumPrimaryButton(if (approvedDeep) "Отправить глубокий запрос" else if (tier == 2) "Проверить стоимость" else "Отправить",
                    { if (approvedDeep) startMessage(request) else {
                        pendingEstimate = request
                        estimateAction.perform("/workspace/chat/estimate", request.payload())
                    } },
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
        message.optJSONObject("impact_hypothesis")?.let { ImpactHypothesisPanel(it) }
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
        message.strings("uncertainties").forEach { Text("Требует проверки: " + PrivateValue(it), color = MaterialTheme.colorScheme.onSurfaceVariant) }
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
fun PendingJobRecovery(checkpoints: WorkspaceCheckpoints = rememberJobCheckpoints(), onThreadRecovered: (String) -> Unit = {},
    onRequestRecovered: (JSONObject) -> Unit = {}, enabled: Boolean = true,
    onBusyChanged: (Boolean) -> Unit = {}, onRecovered: (String) -> Unit) {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val storage = remember(context) { JobCheckpointStore(context) }
    var selected by remember(session.userId) { mutableStateOf<JSONObject?>(null) }
    var notFoundId by remember(session.userId) { mutableStateOf<String?>(null) }
    var applyingRecovery by remember(session.userId) { mutableStateOf(false) }
    var storageError by remember(session.userId) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val reportRequest by rememberUpdatedState(onRequestRecovered)
    val reportThread by rememberUpdatedState(onThreadRecovered)
    val reportRecovered by rememberUpdatedState(onRecovered)
    val applyRecovered: (JSONObject) -> Unit = { result ->
        val point = selected
        val path = point?.text("path", "").orEmpty()
        val thread = point?.let(::checkpointThread)
        val recoveredJob = result.optString("job_id").takeIf { it.isNotBlank() && it != "null" }
        if (point == null || recoveredJob == null) {
            storageError = "Сервер не подтвердил идентификатор задания. Повторите сверку сохранённого запроса."
        } else {
            applyingRecovery = true; storageError = null; notFoundId = null
            scope.launch {
                try {
                    val saved = withContext(Dispatchers.IO) {
                        storage.save(session.userId, point.text("request_id"), path, recoveredJob)
                    }
                    if (!saved) {
                        storageError = "Не удалось сохранить восстановленное задание. Повторите восстановление; новый запрос не отправлен."
                        return@launch
                    }
                    reportRequest(point)
                    if (thread != null) reportThread(thread)
                    reportRecovered(recoveredJob)
                    checkpoints.refresh()
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) { storageError = "Не удалось прочитать сохранённые задания. Повторите восстановление." }
                finally { applyingRecovery = false }
            }
        }
    }
    val recovery = rememberWorkspaceAction(onFailure = { failure ->
        notFoundId = selected?.text("request_id", "")?.takeIf { failure.reply.status == 404 }
    }, onSuccess = applyRecovered)
    val retry = rememberWorkspaceAction(onSuccess = applyRecovered)
    val reportBusy by rememberUpdatedState(onBusyChanged)
    val busy = recovery.busy || retry.busy || applyingRecovery
    SideEffect { reportBusy(busy) }
    DisposableEffect(Unit) { onDispose { reportBusy(false) } }
    if (checkpoints.error != null) SpectrumCard {
        Text(checkpoints.error, color = MaterialTheme.colorScheme.error)
        SpectrumSecondaryButton("Прочитать сохранённые запросы", checkpoints.refresh, Modifier.fillMaxWidth(), enabled && !busy)
    }
    if (checkpoints.items.isNotEmpty()) SpectrumCard {
        DetailFold("Сохранённые задания · " + checkpoints.items.size,
            initiallyOpen = checkpoints.items.any(JobCheckpointStore::isUnconfirmedChat)) {
            Text("Сначала проверим прежний запрос по его идентификатору. Проверка не создаёт нового платного задания.")
            checkpoints.items.forEach { point ->
                val requestId = point.text("request_id", "")
                val path = point.text("path", "")
                val title = when { path.contains("/chat/") -> "Диалог"; path.contains("/reconcile") -> "Сверка операций"; path.contains("/refresh") -> "Источники"; else -> "Анализ" }
                Text(title + " · " + localMoment(point.text("created_at", "сохранённый запрос")), style = MaterialTheme.typography.bodySmall)
                SpectrumSecondaryButton("Сверить сохранённый запрос", {
                    selected = JSONObject(point.toString()); notFoundId = null; storageError = null
                    recovery.perform("/workspace/jobs/by-request/" + VolumeWorkspaceClient.encode(requestId), method = "GET")
                }, Modifier.fillMaxWidth().testTag("recover-request-$requestId"), enabled && !busy && !checkpoints.loading)
                if (notFoundId == requestId) {
                    val body = point.optJSONObject("request_body")
                    val canReplay = JobCheckpointStore.isChatPath(path) && body?.optString("request_id") == requestId
                    Text("Сервер пока не нашёл это задание. Потерянный ответ сам по себе не подтверждает, что вопрос не был принят.",
                        style = MaterialTheme.typography.bodySmall)
                    if (canReplay) {
                        Text("По отдельному нажатию отправим тот же вопрос с теми же параметрами и идентификатором. Сервер вернёт прежнее задание, если уже принял его.",
                            style = MaterialTheme.typography.bodySmall)
                        SpectrumSecondaryButton("Повторить тот же запрос", {
                            selected = JSONObject(point.toString()); notFoundId = null; storageError = null
                            retry.perform(path, JSONObject(checkNotNull(body).toString()), job = true)
                        }, Modifier.fillMaxWidth().testTag("retry-request-$requestId"), enabled && !busy && !checkpoints.loading)
                    } else Text("В прежней версии сохранён только идентификатор. Повторная отправка без исходных параметров недоступна; можно снова проверить сервер.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            WorkspaceActionState(recovery)
            WorkspaceActionState(retry)
            storageError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}
