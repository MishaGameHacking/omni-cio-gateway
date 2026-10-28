package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import ru.omnicio.app.data.workspace.ChatRouteQuote
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

private const val CHAT_THREADS_PATH = "/workspace/chat/threads"


/** An estimate and any following send share these exact immutable inputs. */
private data class ChatRequestSnapshot(val threadId: String, val text: String, val context: String, val tier: String) {
    fun payload(): JSONObject = JSONObject().put("thread_id", threadId).put("text", text)
        .put("context", JSONObject(context)).put("tier", tier)
    val signature: String get() = payload().toString()

    fun messagePayload(quote: ChatRouteQuote, confirmed: Boolean): JSONObject = payload().apply {
        remove("thread_id"); put("request_id", UUID.randomUUID().toString())
        put("max_cost_micro_rub", quote.ceilingMicroRub); put("expected_route_id", quote.routeId)
        if (confirmed) put("confirm_premium", true)
    }
}

private fun checkpointThread(point: JSONObject): String? =
    Regex("/workspace/chat/threads/([^/]+)/messages").matchEntire(point.text("path", ""))?.groupValues?.getOrNull(1)
        ?.let { runCatching { URLDecoder.decode(it, "UTF-8") }.getOrNull() }

private fun checkpointMatches(point: JSONObject, request: ChatRequestSnapshot): Boolean {
    val body = point.optJSONObject("request_body") ?: return false
    return checkpointThread(point) == request.threadId && body.optString("text") == request.text &&
        body.optString("tier") == request.tier && body.optJSONObject("context")?.toString() == request.context
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AssistantWorkspaceScreen(onBack: () -> Unit, onPortfolio: () -> Unit,
    onActions: () -> Unit, onStrategy: () -> Unit) {
    val session = LocalWorkspaceSession.current
    val questionContext = LocalChatContext.current
    val threads = rememberWorkspaceResource(CHAT_THREADS_PATH)
    var threadId by rememberSaveable(session.userId) { mutableStateOf("") }
    var question by rememberSaveable(session.userId) { mutableStateOf("") }
    var jobId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var tier by rememberSaveable(session.userId, "routing-auto-v1") { mutableIntStateOf(0) }
    var editingContext by rememberSaveable { mutableStateOf(false) }
    var estimate by remember { mutableStateOf<JSONObject?>(null) }
    var estimateSignature by remember { mutableStateOf("") }
    var pendingEstimate by remember(session.userId) { mutableStateOf<ChatRequestSnapshot?>(null) }
    var pendingSend by remember(session.userId) { mutableStateOf<ChatRequestSnapshot?>(null) }
    var awaitingRequestId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var restoringJob by remember(session.userId) { mutableStateOf(false) }
    val savedRequests = rememberJobCheckpoints()
    val tiers = listOf("auto", "fast", "standard", "premium")
    val request = ChatRequestSnapshot(threadId, question.trim(), questionContext.json().toString(), tiers[tier])
    val signature = request.signature
    val pendingQuestion = savedRequests.items.any { JobCheckpointStore.isUnconfirmedChat(it) || checkpointMatches(it, request) }
    val recoveryRequired = savedRequests.error != null || awaitingRequestId != null || pendingQuestion
    val needsRecovery = savedRequests.loading || recoveryRequired
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
    val startMessage: (ChatRequestSnapshot, ChatRouteQuote, Boolean) -> Unit = { selected, quote, confirmed ->
        if (quote.usable && (!quote.needsConfirmation(selected.tier) || confirmed) &&
            !needsRecovery && jobId == null && !restoringJob && !send.busy) {
            val body = selected.messagePayload(quote, confirmed)
            pendingSend = selected
            send.perform("/workspace/chat/threads/" + VolumeWorkspaceClient.encode(selected.threadId) + "/messages", body, job = true)
        }
    }
    val estimateAction = rememberWorkspaceAction { result ->
        val selected = pendingEstimate
        pendingEstimate = null
        if (selected != null) {
            estimate = result; estimateSignature = selected.signature
            val quote = routeQuote(result)
            if (selected.signature == signature && quote.usable && !quote.needsConfirmation(selected.tier) &&
                jobId == null && !restoringJob && !needsRecovery) {
                startMessage(selected, quote, false)
            }
        }
    }
    val valid = question.isNotBlank() && question.length <= 4_000 && threadId.isNotBlank()
    val composerAvailability = AssistantComposerAvailability(
        checkpointsLoading = savedRequests.loading,
        recoveryRequired = recoveryRequired,
        operationBusy = send.busy || estimateAction.busy || jobId != null || restoringJob,
    )
    val busy = !composerAvailability.canSubmit
    LaunchedEffect(savedRequests.loading, savedRequests.error, savedRequests.items, savedRequests.revision, awaitingRequestId) {
        if (!savedRequests.loading && savedRequests.error == null && savedRequests.revision == JobCheckpointStore.revision.value && awaitingRequestId != null &&
            savedRequests.items.none { it.text("request_id", "") == awaitingRequestId }) awaitingRequestId = null
    }
    InitializeChatThread(threads, threadId, session.userId, questionContext.title, create) { threadId = it }
    val hasEarlierMessages = messages.data?.optBoolean("has_more") == true
    val listState = rememberAssistantList(messageItems, cursor, hasEarlierMessages)
    val activeJob = jobId?.let { id ->
        rememberWorkspaceJobState(id,
            onCompleted = { cursors = listOf(""); messages.refresh(); threads.refresh(); jobId = null },
            onStateChanged = { jobState = it })
    }
    val emptyHistory = messages.data != null && messages.error == null && !messages.busy && messageItems.isEmpty()
    AssistantFailureReveal(listState, send.error, estimateAction.error, messageItems.size,
        (if (hasEarlierMessages) 1 else 0) + (if (cursors.size > 1) 1 else 0),
        emptyHistory, activeJob != null)
    val requestRecovered: (JSONObject) -> Unit = { point ->
                    send.acknowledgeRecovery(point.text("request_id", ""))
                    if (checkpointMatches(point, request)) question = ""
                    if (point.text("request_id", "") == awaitingRequestId) { awaitingRequestId = null; pendingSend = null }
                    estimate = null; cursors = listOf(""); messages.refresh(); threads.refresh()
                }
    val quotedRoute = routeQuote(estimate)
    val approvedDeep = estimateSignature == signature && quotedRoute.usable && quotedRoute.needsConfirmation(request.tier)
    val sendQuestion = {
        composerAvailability.submitIfAllowed(valid) {
            if (approvedDeep) startMessage(request, quotedRoute, true) else {
                pendingEstimate = request
                estimateAction.perform("/workspace/chat/estimate", request.payload())
            }
        }
    }
    // Preserve room for the native editor in portrait with large system text.
    val subtitle = if (WindowInsets.isImeVisible) "" else "Объяснения с проверяемыми основаниями"
    WorkspaceDetailPage("Ассистент", subtitle, onBack, SpectrumSymbol.Analyst, adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        AssistantConversationLayout(padding, history = { historyModifier ->
            LazyColumn(historyModifier.semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                state = listState, contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item {
                    // The compact shell yields its header height to the conversation.
                    // Keep its title in the existing first item so status indexes stay stable.
                    if (compact) WorkspacePageHeading("Ассистент", subtitle)
                    AssistantContextCard(questionContext,
                    assistantIconState(jobId, jobState, send.error != null || estimateAction.error != null,
                        busy, messageItems.lastOrNull()?.text("role")), busy, question, threads, create,
                    { question = eventImpactQuestion; estimate = null }, { threadId = it }, { editingContext = true }) }
                item { WorkspaceRequestState(threads); WorkspaceRequestState(messages); WorkspaceActionState(create) }
                assistantHistoryPages(messages, cursors) { cursors = it }
                items(messageItems, key = { it.text("id") }) { message -> AssistantMessage(message, onPortfolio, onActions, onStrategy) }
                if (emptyHistory) item {
                    WorkspaceEmpty("С чего начнём?", "Спросите о позиции, изменениях капитала или правилах стратегии. Ответ появится после фактического запроса к модели.")
                }
                activeJob?.let { model -> item { WorkspaceJobPanel(model, onClose = { jobId = null }) } }
                item(key = "assistant-request-state") { WorkspaceActionState(send); WorkspaceActionState(estimateAction) }
                item { PendingJobRecovery(savedRequests, onThreadRecovered = { threadId = it }, onRequestRecovered = requestRecovered,
                    enabled = !send.busy && !estimateAction.busy && jobId == null,
                    onBusyChanged = { restoringJob = it }) { jobId = it } }
                estimate?.let { value -> item { AssistantEstimateCard(value, estimateSignature == signature) } }
            }
        }) { composerModifier ->
            AssistantComposer(question, tier, savedRequests.loading, needsRecovery, composerAvailability, valid,
                approvedDeep,
                { tier = it; estimate = null }, { question = it.take(4_000); estimate = null },
                modifier = composerModifier) {
                sendQuestion()
            }
        }
    }
    if (editingContext) ChatContextEditor(questionContext) { editingContext = false }
}

@Composable
private fun AssistantFailureReveal(listState: LazyListState, sendError: String?, estimateError: String?,
    messageCount: Int, pageCount: Int, emptyHistory: Boolean, activeJob: Boolean) {
    // The context and resource status precede pagination/messages. A new failed
    // user action must expose its status even after a very long expanded answer.
    val statusIndex = 2 + pageCount + messageCount + (if (emptyHistory) 1 else 0) + (if (activeJob) 1 else 0)
    LaunchedEffect(sendError, estimateError) {
        if (sendError != null || estimateError != null) listState.scrollToItem(statusIndex)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AssistantConversationLayout(padding: PaddingValues,
    history: @Composable (Modifier) -> Unit, composer: @Composable (Modifier) -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).imePadding()) {
        // Unweighted children are measured before the weighted history. Reserve
        // half the reading viewport for messages when large text fills the editor.
        // With the IME open, native focus can use the remaining available height.
        val composerLimit = if (WindowInsets.isImeVisible) maxHeight else maxHeight * .5f
        Column(Modifier.fillMaxSize()) {
            history(Modifier.weight(1f).fillMaxWidth())
            composer(Modifier.heightIn(max = composerLimit))
        }
    }
}

@Composable
private fun AssistantMessage(message: JSONObject, onPortfolio: () -> Unit, onActions: () -> Unit, onStrategy: () -> Unit) {
    val assistant = message.text("role", "") == "assistant"
    val navigate = LocalEvidenceNavigator.current
    val workspace = LocalWorkspaceNavigator.current
    SpectrumCard(emphasized = assistant) {
        Text(if (assistant) "Analyst AI" else "Вы", style = MaterialTheme.typography.labelLarge)
        if (assistant) Text("Объяснение ИИ. Числа и основания проверяйте в связанных наблюдениях; выводы модели могут содержать ошибки.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(PrivateValue(message.text("text", "")),
            modifier = if (assistant) Modifier else Modifier.testTag("assistant-user-message"),
            style = MaterialTheme.typography.bodyLarge)
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

@Composable
private fun AssistantContextCard(questionContext: ChatContext, iconState: SpatialState, busy: Boolean,
    question: String, threads: WorkspaceResource, create: WorkspaceAction,
    onEventQuestion: () -> Unit, onThread: (String) -> Unit, onEditContext: () -> Unit) {
    var showThreads by rememberSaveable { mutableStateOf(false) }
    SpectrumCard(emphasized = true) {
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            SpatialIcon("analyst", Modifier.size(64.dp), state = iconState)
                            Column(Modifier.weight(1f)) {
                                Text(questionContext.title, style = MaterialTheme.typography.titleLarge)
                                Text("Контекст виден в каждом запросе. Числа и источники проверяются отдельно от объяснения.", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        SpectrumSecondaryButton("Диалоги", { showThreads = !showThreads }, Modifier.fillMaxWidth())
                        SpectrumSecondaryButton("Изменить контекст", onEditContext, Modifier.fillMaxWidth(), !busy)
                        if (questionContext.eventId != null) {
                            Text("Выбрана конкретная публикация. Аналитик проверит её связь с вашими позициями и отделит возможное влияние от подтверждённых фактов.",
                                style = MaterialTheme.typography.bodySmall)
                            if (question.isBlank()) SpectrumSecondaryButton("Подставить вопрос о событии", onEventQuestion, Modifier.fillMaxWidth().testTag("assistant-event-question"), !busy)
                            Text("Вопрос отправляется только кнопкой «Отправить», с обычной проверкой расхода.", style = MaterialTheme.typography.bodySmall)
                        }
                        if (showThreads) {
                            threads.data?.records("items").orEmpty().forEach { item ->
                                SpectrumSecondaryButton(item.text("title", "Диалог"), { onThread(item.text("thread_id", "")); showThreads = false }, Modifier.fillMaxWidth(), !busy)
                            }
                            SpectrumSecondaryButton("Новый диалог", { create.perform(CHAT_THREADS_PATH, JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", questionContext.title)) }, Modifier.fillMaxWidth(), !busy && !create.busy)
                        }
                    }
}

private fun assistantIconState(jobId: String?, jobState: String, failed: Boolean, busy: Boolean,
    lastRole: String?): SpatialState = when {
    jobId != null && jobState in setOf("failed", "uncertain", "cancelled") -> SpatialState.Attention
    failed -> SpatialState.Attention
    busy -> SpatialState.Loading
    lastRole == "assistant" -> SpatialState.Success
    else -> SpatialState.Idle
}

private fun routeQuote(value: JSONObject?): ChatRouteQuote {
    val ceiling = when (val raw = value?.opt("cost_ceiling_micro_rub")) {
        is Int -> raw.toLong()
        is Long -> raw
        else -> null
    }
    return ChatRouteQuote(value?.optBoolean("available") == true, value?.optString("selected_tier").orEmpty(),
        value?.optBoolean("requires_cost_confirmation") == true, ceiling, value?.optString("route_id").orEmpty())
}

private const val CHAT_DEPTH_BRIEF = "Кратко"
private const val CHAT_DEPTH_DETAIL = "Подробно"
private const val CHAT_DEPTH_DEEP = "Глубокий разбор"

@Composable
private fun AssistantEstimateCard(value: JSONObject, current: Boolean) {
    val quote = routeQuote(value)
    SpectrumCard {
        Text(if (quote.usable) "Оценка расхода" else "Вопрос не отправлен", style = MaterialTheme.typography.titleMedium)
        if (quote.usable) {
            Text(PrivateValue(value.optJSONObject("estimated_upper_bound")?.let(::moneyText) ?: "Стоимость не подтверждена"))
            val depth = when (quote.selectedTier) { "fast" -> CHAT_DEPTH_BRIEF; "standard" -> CHAT_DEPTH_DETAIL; else -> CHAT_DEPTH_DEEP }
            Text("Выбрано сервером: " + depth, style = MaterialTheme.typography.bodySmall)
            Text("Оценка ограничивает расход: при смене маршрута или увеличении суммы сервер запросит новую проверку.", style = MaterialTheme.typography.bodySmall)
            if (quote.needsConfirmation(quote.selectedTier)) Text("Глубокий запрос будет отправлен только после отдельного подтверждения кнопкой ниже.")
        } else {
            Text(VolumeWorkspaceClient.chatPolicyMessage(value.optString("reason")) ?:
                "Маршрут и стоимость не подтверждены. Проверьте готовность сервиса в истории анализов.")
        }
        if (!current) Text("Вопрос или контекст изменился. Перед отправкой стоимость будет проверена заново.", style = MaterialTheme.typography.bodySmall)
        value.text("context_as_of", "").takeIf(String::isNotBlank)?.let { Text("Контекст от " + localMoment(it), style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun AssistantComposer(question: String, tier: Int, loading: Boolean, needsRecovery: Boolean,
    availability: AssistantComposerAvailability, valid: Boolean, approvedDeep: Boolean, onTier: (Int) -> Unit,
    onQuestion: (String) -> Unit, modifier: Modifier = Modifier, onSend: () -> Unit) {
    // The parent consumes the page/IME insets. Keep this bounded viewport
    // scrollable so native focus can reveal the editor on short/large-font windows.
    val compact = LocalCompactWorkspaceInput.current
    val busy = !availability.canSubmit
    SpectrumCard(modifier.fillMaxWidth().padding(
        horizontal = if (compact) 0.dp else 12.dp, vertical = if (compact) 0.dp else 8.dp)
        .verticalScroll(rememberScrollState()).semantics { testTagsAsResourceId = true }
        .testTag("assistant-composer")) {
                    if (loading) Text("Проверяем сохранённые запросы…", style = MaterialTheme.typography.bodySmall)
                    else if (needsRecovery) Text("Сверьте сохранённый вопрос перед новой отправкой.", style = MaterialTheme.typography.bodySmall)
                    DetailFold("Глубина ответа: " + listOf("Авто", CHAT_DEPTH_BRIEF, CHAT_DEPTH_DETAIL, CHAT_DEPTH_DEEP)[tier]) {
                        WorkspaceChoices("Выбор модели", listOf("Авто", CHAT_DEPTH_BRIEF, CHAT_DEPTH_DETAIL, CHAT_DEPTH_DEEP), tier) { if (!busy) onTier(it) }
                    }
                    // The local checkpoint read repeats after Activity recreation. It must
                    // gate dispatch without briefly removing the restored native input session.
                    WorkspaceTextInput(question, onQuestion, "Ваш вопрос", singleLine = false,
                        modifier = Modifier.fillMaxWidth().semantics { testTagsAsResourceId = true }
                            .testTag("assistant-question"), enabled = availability.canEditDraft)
                    SpectrumPrimaryButton(if (approvedDeep) "Отправить глубокий запрос" else if (tier == 3) "Проверить стоимость" else "Отправить",
                        onSend,
                        Modifier.fillMaxWidth(), enabled = valid && !busy, symbol = SpectrumSymbol.Messages)
                }
}

@Composable
private fun InitializeChatThread(threads: WorkspaceResource, threadId: String, userId: String,
    title: String, create: WorkspaceAction, onThread: (String) -> Unit) {
    var initialized by remember(userId) { mutableStateOf(false) }
    LaunchedEffect(threads.data) {
            if (!initialized && threads.data != null) {
                initialized = true
                if (threadId.isBlank()) {
                    val first = threads.data.records("items").firstOrNull()
                    if (first != null) onThread(first.text("thread_id", ""))
                    else create.perform(CHAT_THREADS_PATH, JSONObject().put("request_id", UUID.randomUUID().toString()).put("title", title))
                }
            }
        }
}

@Composable
private fun rememberAssistantList(messageItems: List<JSONObject>, cursor: String, hasEarlierMessages: Boolean): LazyListState {
    val listState = rememberLazyListState()
    LaunchedEffect(messageItems.lastOrNull()?.text("id"), cursor) {
        // The context and request-state entries precede the messages. The
        // optional earlier-page control adds one more entry on the newest page.
        if (messageItems.isNotEmpty() && cursor.isBlank()) {
            val lastMessageIndex = 2 + (if (hasEarlierMessages) 1 else 0) + messageItems.lastIndex
            listState.animateScrollToItem(lastMessageIndex)
        }
    }
    LaunchedEffect(cursor) { if (cursor.isNotBlank()) listState.scrollToItem(0) }
    return listState
}

private fun LazyListScope.assistantHistoryPages(messages: WorkspaceResource, cursors: List<String>,
    onCursors: (List<String>) -> Unit) {
    if (messages.data?.optBoolean("has_more") == true) item {
                        SpectrumSecondaryButton("Более ранние сообщения", {
                            messages.data.text("next_before", "").takeIf(String::isNotBlank)?.let { onCursors(cursors + it) }
                        }, Modifier.fillMaxWidth(), !messages.busy)
                    }
    if (cursors.size > 1) item { SpectrumCard {
                        Text("Предыдущая часть диалога · страница " + cursors.size)
                        SpectrumSecondaryButton("К более новым сообщениям", { onCursors(cursors.dropLast(1)) }, Modifier.fillMaxWidth(), !messages.busy)
                        SpectrumSecondaryButton("К последним сообщениям", { onCursors(listOf("")) }, Modifier.fillMaxWidth(), !messages.busy)
                    } }
}
