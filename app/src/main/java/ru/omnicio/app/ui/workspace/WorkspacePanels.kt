package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
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
    var focused by remember { mutableStateOf(false) }
    SpatialField(modifier, focused, error, enabled) {
        TextField(value, onChange, Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused },
            label = { Text(label) }, singleLine = singleLine, maxLines = if (singleLine) 1 else 6,
            isError = error, enabled = enabled, keyboardOptions = keyboard,
            colors = TextFieldDefaults.colors(focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent,
                disabledContainerColor = Color.Transparent, errorContainerColor = Color.Transparent,
                focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent))
    }
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
fun EvidenceLinks(evidence: List<JSONObject>, highlights: List<JSONObject> = emptyList()) {
    val navigate = LocalEvidenceNavigator.current
    val workspace = LocalWorkspaceNavigator.current
    val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
    val catalogue = LocalWorkspaceSnapshot.current?.records("sources").orEmpty()
    if (evidence.isNotEmpty()) DetailFold("Основания (${evidence.size})") {
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
                SpectrumSecondaryButton("Открыть первоисточник", { runCatching { uriHandler.openUri(url) } }, Modifier.fillMaxWidth())
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

@Composable
fun WorkspaceJobPanel(jobId: String, onCompleted: () -> Unit = {}, onClose: () -> Unit = {}, onStateChanged: (String) -> Unit = {}) {
    val session = LocalWorkspaceSession.current
    val client = LocalWorkspaceTransport.current
    val foreground = workspaceForeground()
    val completed by rememberUpdatedState(onCompleted)
    val stateChanged by rememberUpdatedState(onStateChanged)
    val reauthenticate = LocalReauthenticate.current
    val context = androidx.compose.ui.platform.LocalContext.current
    val checkpoints = remember(context) { ru.omnicio.app.data.workspace.JobCheckpointStore(context) }
    val scope = rememberCoroutineScope()
    var activeId by remember(jobId, session.userId) { mutableStateOf(jobId) }
    var job by remember(activeId, session.userId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(activeId) { mutableStateOf<String?>(null) }
    var revision by remember(activeId) { mutableIntStateOf(0) }
    var notified by remember(activeId) { mutableStateOf(false) }
    val cancel = rememberWorkspaceAction { job = it; revision++ }
    val retry = rememberWorkspaceAction { result -> result.optString("job_id").takeIf(String::isNotBlank)?.let { activeId = it } }
    LaunchedEffect(activeId, session.token, foreground, revision) {
        if (!foreground || session.token.isBlank() || activeId.isBlank()) return@LaunchedEffect
        while (isActive) {
            val reply = withContext(Dispatchers.IO) { client.request(session.token, "/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}") }
            error = reply.error
            if (reply.signedOut) { reauthenticate(); return@LaunchedEffect }
            if (reply.data != null) job = reply.data
            val state = job?.text("state", "")
            if (!state.isNullOrBlank()) stateChanged(state)
            if (state == "completed" && !notified) {
                withContext(Dispatchers.IO) { checkpoints.removeJob(session.userId, activeId) }
                notified = true; completed()
            }
            if (state in terminalJobs || reply.error != null) break
            delay(1_500)
        }
    }
    val state = job?.text("state", "queued") ?: "queued"
    SpectrumCard(emphasized = true) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpatialIcon(if (state == "completed") "check" else if (state in terminalJobs) "risk" else "orbit", Modifier.size(40.dp),
                state = if (state == "completed") SpatialState.Success else if (state in terminalJobs) SpatialState.Attention else SpatialState.Loading)
            Column { Text(jobStateTitle(state), style = MaterialTheme.typography.titleMedium)
                Text(jobStageTitle(job?.text("stage", "queued") ?: "queued"), style = MaterialTheme.typography.bodySmall) }
        }
        job?.optString("updated_at")?.takeIf { it.isNotBlank() }?.let { Text(localMoment(it), style = MaterialTheme.typography.bodySmall) }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (state == "uncertain") Text("Исход запроса к модели пока не подтверждён. Автоматического повторного запроса нет.")
        if (state == "cancel_requested") Text("Отмена запрошена. Уже отправленный запрос провайдеру может завершиться и учитывается в расходе.")
        if (state !in terminalJobs && state != "cancel_requested") SpectrumSecondaryButton("Отменить задание", {
            cancel.perform("/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}/cancel", JSONObject())
        }, Modifier.fillMaxWidth(), enabled = !cancel.busy)
        SpectrumSecondaryButton("Проверить состояние", { revision++ }, Modifier.fillMaxWidth())
        WorkspaceActionState(cancel)
        if (job?.optBoolean("can_retry") == true && state in terminalJobs && state != "uncertain") {
            Text("Сервер разрешил повтор этой задачи. Повтор выполняется только по вашему нажатию.")
            SpectrumSecondaryButton("Повторить разрешённую задачу", {
                retry.perform("/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}/retry", JSONObject().put("request_id", UUID.randomUUID().toString()), job = true)
            }, Modifier.fillMaxWidth(), !retry.busy)
            WorkspaceActionState(retry)
        }
        if (state in terminalJobs) SpectrumSecondaryButton("Закрыть", {
            if (state == "cancelled" || state == "completed") scope.launch(Dispatchers.IO) { checkpoints.removeJob(session.userId, activeId) }
            onClose()
        }, Modifier.fillMaxWidth())
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
