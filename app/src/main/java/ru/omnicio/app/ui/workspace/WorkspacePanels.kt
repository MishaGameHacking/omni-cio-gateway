package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.spectrum.*

@Composable
fun WorkspaceTextInput(value: String, onChange: (String) -> Unit, label: String,
    modifier: Modifier = Modifier, singleLine: Boolean = true, error: Boolean = false,
    enabled: Boolean = true, keyboard: KeyboardOptions = KeyboardOptions.Default) {
    SpectrumTextField(value, onChange, modifier, enabled = enabled, label = { Text(label) },
        singleLine = singleLine, maxLines = if (singleLine) 1 else 6, isError = error, keyboardOptions = keyboard)
}

@Composable
fun WorkspaceRequestState(resource: WorkspaceResource) {
    if (resource.busy && resource.data == null) SpectrumCard {
        SpatialIcon("orbit", Modifier.size(44.dp), state = SpatialState.Loading)
        Text("Получаем подтверждённые данные…", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
    resource.error?.let { error -> WorkspaceEmpty("Не удалось обновить", error, "Повторить", resource.refresh) }
}

@Composable
fun WorkspaceActionState(action: WorkspaceAction) {
    if (action.busy) Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SpatialIcon("orbit", Modifier.size(32.dp), state = SpatialState.Loading)
        Text("Ожидаем подтверждение…", Modifier.semantics { liveRegion = LiveRegionMode.Polite })
    }
    action.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
}

@Composable
fun EvidenceLinks(evidence: List<JSONObject>, highlights: List<JSONObject> = emptyList(),
    headerModifier: Modifier = Modifier) {
    val navigate = LocalEvidenceNavigator.current
    val workspace = LocalWorkspaceNavigator.current
    val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
    val catalogue = LocalWorkspaceSnapshot.current?.records("sources").orEmpty()
    if (evidence.isNotEmpty()) DetailFold("Основания (${evidence.size})", headerModifier = headerModifier) {
        evidence.forEach { source ->
            val details = if (source.has("provider")) source else catalogue.firstOrNull { it.text("id") == source.text("source_id", source.text("id", "")) } ?: source
            Text(details.text("title", details.text("provider", "Источник наблюдения")), style = MaterialTheme.typography.titleSmall)
            if (details.has("method")) Text(details.text("method"), style = MaterialTheme.typography.bodySmall)
            if (source.has("fact")) Text(PrivateValue(source.text("fact")), style = MaterialTheme.typography.bodySmall)
            val observed = source.text("as_of", details.text("observed_at", ""))
            if (observed.isNotBlank()) Text("Получено: " + localMoment(observed), style = MaterialTheme.typography.bodySmall)
            details.text("published_at", "").takeIf(String::isNotBlank)?.let { Text("Опубликовано: " + localMoment(it), style = MaterialTheme.typography.bodySmall) }
            details.text("unit", "").takeIf(String::isNotBlank)?.let { Text("Единицы: " + it, style = MaterialTheme.typography.bodySmall) }
            details.text("currency", "").takeIf(String::isNotBlank)?.let { Text("Валюта: " + it, style = MaterialTheme.typography.bodySmall) }
            val url = details.text("url", "")
            if (runCatching { java.net.URI(url).let { it.scheme == "https" && it.host != null && it.userInfo == null } }.getOrDefault(false)) {
                SpectrumSecondaryButton("Открыть источник", { runCatching { uriHandler.openUri(url) } }, Modifier.fillMaxWidth())
            }
            if (!details.has("provider")) Text("Метаданные источника не сохранены в этом ответе. Идентификатор: " + source.text("source_id", source.text("id")), style = MaterialTheme.typography.bodySmall)
        }
    }
    highlights.filter { it.text("section", "") in setOf("instrument", "portfolio", "operation", "operations", "history", "research", "risk", "risks", "capital", "events") }
        .forEach { target -> SpectrumSecondaryButton(target.text("label", "Показать в портфеле"), {
            val section = when (target.text("section")) { "risks" -> "risk"; "capital" -> "capital"; else -> target.text("section") }
            val identifier = if (section == "operation" || section == "operations") target.text("operation_id", target.text("id", "").takeUnless { it.startsWith("operation:") }.orEmpty()) else target.text("id", "")
            if (section == "events") workspace(WorkspaceRoute.Discovery) else navigate(EvidenceTarget(section, identifier,
                target.text("date", "").takeIf(String::isNotBlank), target.text("account_id", "").takeIf(String::isNotBlank),
                target.text("start", "").takeIf(String::isNotBlank), target.text("end", "").takeIf(String::isNotBlank), target.text("resolution", "").takeIf(String::isNotBlank)))
        }, Modifier.fillMaxWidth()) }
}

private val terminalJobs = setOf("completed", "cancelled", "failed", "uncertain")

class WorkspaceJobState internal constructor(
    val job: JSONObject?, val error: String?,
    val cancellation: WorkspaceAction, val retry: WorkspaceAction,
    val cancel: () -> Unit, val retryJob: () -> Unit, val refresh: () -> Unit,
    val close: (() -> Unit) -> Unit,
) {
    val state: String get() = job?.text("state", "queued") ?: "queued"
}

/** Own the job independently of whether its LazyColumn card is on screen. */
@Composable
fun rememberWorkspaceJobState(jobId: String, onCompleted: () -> Unit = {},
    onStateChanged: (String) -> Unit = {}): WorkspaceJobState {
    val session = LocalWorkspaceSession.current
    return key(session.userId, jobId) {
        var activeId by rememberSaveable { mutableStateOf(jobId) }
        // A reply for the previous job/session must not enter a newer job's state.
        key(activeId) {
            rememberActiveWorkspaceJob(activeId, onCompleted, onStateChanged) { activeId = it }
        }
    }
}

@Composable
private fun rememberActiveWorkspaceJob(activeId: String, onCompleted: () -> Unit,
    onStateChanged: (String) -> Unit, onRetried: (String) -> Unit): WorkspaceJobState {
    val session = LocalWorkspaceSession.current
    val client = LocalWorkspaceTransport.current
    val foreground = workspaceForeground()
    val completed by rememberUpdatedState(onCompleted)
    val stateChanged by rememberUpdatedState(onStateChanged)
    val reauthenticate = LocalReauthenticate.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val checkpoints = remember(context) { ru.omnicio.app.data.workspace.JobCheckpointStore(context) }
    val scope = key(session.token, client) { rememberCoroutineScope() }
    var job by remember { mutableStateOf<JSONObject?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var revision by remember { mutableIntStateOf(0) }
    var notified by remember { mutableStateOf(false) }
    val retried by rememberUpdatedState(onRetried)
    val cancel = key(session.token, client) { rememberWorkspaceAction { job = it; revision++ } }
    val retry = key(session.token, client) {
        rememberWorkspaceAction { result -> result.optString("job_id").takeIf(String::isNotBlank)?.let(retried) }
    }
    LaunchedEffect(activeId, session.userId, session.token, client, foreground, revision) {
        if (!foreground || session.token.isBlank() || activeId.isBlank()) return@LaunchedEffect
        while (isActive) {
            val reply = withContext(Dispatchers.IO) { client.request(session.token, "/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}") }
            error = reply.error
            if (reply.signedOut) { reauthenticate(); return@LaunchedEffect }
            if (reply.data != null) job = reply.data
            val state = job?.text("state", "")
            if (!state.isNullOrBlank()) stateChanged(state)
            if (state == "completed" && !notified) {
                val removed = withContext(Dispatchers.IO) { checkpoints.removeJob(session.userId, activeId) }
                if (removed && !notified) { notified = true; completed() }
                else if (!removed) error = "Не удалось удалить сохранённое задание. Повторите проверку состояния или закрытие."
            }
            if (state in terminalJobs || reply.error != null) break
            delay(1_500)
        }
    }
    val state = job?.text("state", "queued") ?: "queued"
    return WorkspaceJobState(job, error, cancel, retry,
        cancel = { cancel.perform("/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}/cancel", JSONObject()) },
        retryJob = {
            retry.perform("/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}/retry", JSONObject().put("request_id", UUID.randomUUID().toString()), job = true)
        },
        refresh = { revision++ },
        close = { onClose ->
            if (state == "cancelled" || state == "completed") scope.launch {
                val removed = withContext(Dispatchers.IO) { checkpoints.removeJob(session.userId, activeId) }
                if (removed) {
                    if (state == "completed" && !notified) { notified = true; completed() }
                    onClose()
                }
                else error = "Не удалось удалить сохранённое задание. Повторите проверку состояния или закрытие."
            } else onClose()
        })
}

@Composable
fun WorkspaceJobPanel(jobId: String, onCompleted: () -> Unit = {}, onClose: () -> Unit = {}, onStateChanged: (String) -> Unit = {}) {
    WorkspaceJobPanel(rememberWorkspaceJobState(jobId, onCompleted, onStateChanged), onClose)
}

/** Rendering a hoisted state never starts another poller or action scope. */
@Composable
fun WorkspaceJobPanel(model: WorkspaceJobState, onClose: () -> Unit = {}) {
    val job = model.job
    val state = model.state
    val closed by rememberUpdatedState(onClose)
    SpectrumCard(emphasized = true) {
        WorkspaceJobHeading(state, job?.text("stage", "queued") ?: "queued")
        job?.optString("updated_at")?.takeIf { it.isNotBlank() }?.let { Text(localMoment(it), style = MaterialTheme.typography.bodySmall) }
        model.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (state == "uncertain") Text("Исход запроса к модели пока не подтверждён. Автоматического повторного запроса нет.")
        if (state == "cancel_requested") Text("Отмена запрошена. Уже отправленный запрос провайдеру может завершиться и учитывается в расходе.")
        if (state !in terminalJobs && state != "cancel_requested") SpectrumSecondaryButton("Отменить задание", model.cancel,
            Modifier.fillMaxWidth(), enabled = !model.cancellation.busy)
        SpectrumSecondaryButton("Проверить состояние", model.refresh, Modifier.fillMaxWidth())
        WorkspaceActionState(model.cancellation)
        if (job?.optBoolean("can_retry") == true && state in terminalJobs && state != "uncertain") {
            Text("Сервер разрешил повтор этой задачи. Повтор выполняется только по вашему нажатию.")
            SpectrumSecondaryButton("Повторить разрешённую задачу", model.retryJob, Modifier.fillMaxWidth(), !model.retry.busy)
            WorkspaceActionState(model.retry)
        }
        if (state in terminalJobs) SpectrumSecondaryButton("Закрыть", {
            model.close { closed() }
        }, Modifier.fillMaxWidth())
    }
}

@Composable
private fun WorkspaceJobHeading(state: String, stage: String) {
    val (model, visual) = when {
        state == "completed" -> "check" to SpatialState.Success
        state in terminalJobs -> "risk" to SpatialState.Attention
        else -> "orbit" to SpatialState.Loading
    }
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SpatialIcon(model, Modifier.size(40.dp), state = visual)
        Column {
            Text(jobStateTitle(state), style = MaterialTheme.typography.titleMedium)
            Text(jobStageTitle(stage), style = MaterialTheme.typography.bodySmall)
        }
    }
}

internal fun jobStateTitle(state: String): String = when (state) {
    "queued" -> "Задание в очереди"; "running" -> "Идёт работа"; "cancel_requested" -> "Ожидаем отмену"
    "cancelled" -> "Отмена подтверждена"; "completed" -> "Готово"; "failed" -> "Задание завершилось с ошибкой"
    "uncertain" -> "Исход требует сверки"; else -> "Проверяем состояние"
}
internal fun jobStageTitle(stage: String): String = when (stage) {
    "queued" -> "Ожидание запуска"; "collecting" -> "Проверяем источники"; "model_running" -> "Модель готовит объяснение"
    "validating" -> "Проверяем ответ и основания"; "persisting" -> "Сохраняем результат"; "done" -> "Результат сохранён"
    else -> "Стадия уточняется"
}
