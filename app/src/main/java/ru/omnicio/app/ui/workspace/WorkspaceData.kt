package ru.omnicio.app.ui.workspace

import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import java.text.NumberFormat
import java.util.Locale
import java.util.UUID
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.JobCheckpointPreparation
import ru.omnicio.app.data.workspace.JobCheckpointStore
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spatial.SpatialHaptic
import ru.omnicio.app.ui.spatial.rememberSpatialHapticFeedback

val LocalReauthenticate = staticCompositionLocalOf<() -> Unit> { {} }
val LocalWorkspaceTransport = staticCompositionLocalOf<ru.omnicio.app.data.workspace.WorkspaceTransport> { VolumeWorkspaceClient() }
val LocalPortfolioRefresh = staticCompositionLocalOf<() -> Unit> { {} }
val LocalPortfolioSnapshot = staticCompositionLocalOf<ru.omnicio.app.data.portfolio.PortfolioSnapshot?> { null }
data class EvidenceTarget(val section: String, val id: String, val date: String? = null, val accountId: String? = null,
    val start: String? = null, val end: String? = null, val resolution: String? = null)
val LocalEvidenceNavigator = staticCompositionLocalOf<(EvidenceTarget) -> Unit> { {} }
val LocalOpenAnalysisReport = staticCompositionLocalOf<(String?) -> Unit> { {} }
data class ChatContext(val mode: String = "portfolio", val instrumentUid: String? = null, val title: String = "Мой портфель",
    val accountId: String? = null, val start: String? = null, val end: String? = null, val eventId: String? = null) {
    fun json(): JSONObject = JSONObject().put("mode", mode).put("instrument_uid", instrumentUid ?: JSONObject.NULL)
        .put("account_id", accountId ?: JSONObject.NULL).put("start", start ?: JSONObject.NULL).put("end", end ?: JSONObject.NULL)
        .put("event_id", eventId ?: JSONObject.NULL)
}
val LocalChatContext = staticCompositionLocalOf { ChatContext() }
val LocalAskAnalyst = staticCompositionLocalOf<(ChatContext) -> Unit> { {} }

data class WorkspaceResource(val data: JSONObject?, val busy: Boolean, val error: String?, val refresh: () -> Unit)

@Composable
fun rememberWorkspaceResource(path: String, enabled: Boolean = true): WorkspaceResource {
    val session = LocalWorkspaceSession.current
    val reauthenticate = LocalReauthenticate.current
    val client = LocalWorkspaceTransport.current
    var data by remember(session.userId, session.token, path) { mutableStateOf<JSONObject?>(null) }
    var busy by remember(session.userId, path) { mutableStateOf(false) }
    var error by remember(session.userId, path) { mutableStateOf<String?>(null) }
    var revision by remember(path) { mutableIntStateOf(0) }
    val foreground = workspaceForeground()
    val workspaceRevision = LocalWorkspaceRefreshKey.current
    LaunchedEffect(session.token, path, revision, enabled, foreground, workspaceRevision) {
        if (!enabled || !foreground || session.token.isBlank()) return@LaunchedEffect
        busy = true
        try {
            val result = withContext(Dispatchers.IO) { client.request(session.token, path) }
            if (result.signedOut) reauthenticate()
            if (result.data != null) data = result.data
            error = result.error
        } finally { busy = false }
    }
    return WorkspaceResource(data, busy, error) { revision++ }
}

@Composable
fun workspaceForeground(): Boolean {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: true }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    return active
}

class WorkspaceAction(
    val busy: Boolean,
    val error: String?,
    val ambiguous: Boolean,
    private val execute: (String, JSONObject?, String, Boolean, Boolean) -> Unit,
) {
    fun perform(path: String, body: JSONObject? = null, method: String = "POST", job: Boolean = false,
        userInitiated: Boolean = true) = execute(path, body, method, job, userInitiated)
}

data class WorkspaceRequestFailure(val reply: VolumeReply, val requestId: String?, val requiresRecovery: Boolean)
data class WorkspaceCheckpoints(val items: List<JSONObject>, val loading: Boolean, val error: String?, val revision: Long, val refresh: () -> Unit)

/** The first read is gated, and durable writes refresh every mounted recovery panel. */
@Composable
fun rememberJobCheckpoints(): WorkspaceCheckpoints {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val storage = remember(context) { JobCheckpointStore(context) }
    val revision by JobCheckpointStore.revision.collectAsState()
    var retry by remember(session.userId) { mutableIntStateOf(0) }
    var items by remember(session.userId) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var loading by remember(session.userId) { mutableStateOf(true) }
    var observedRevision by remember(session.userId) { mutableLongStateOf(-1L) }
    var error by remember(session.userId) { mutableStateOf<String?>(null) }
    LaunchedEffect(session.userId, session.token, revision, retry) {
        loading = true
        try {
            items = withContext(Dispatchers.IO) { storage.list(session.userId) }
            observedRevision = revision
            error = null
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { error = "Не удалось прочитать сохранённые запросы. Отправка временно заблокирована; повторите проверку." }
        finally { loading = false }
    }
    return WorkspaceCheckpoints(items, loading || observedRevision != revision, error, observedRevision) { retry++ }
}

/** A paid request ID is persisted BEFORE dispatch; a timeout can only recover that request. */
@Composable
fun rememberWorkspaceAction(onPrepared: (String) -> Unit = {},
    onFailure: (WorkspaceRequestFailure) -> Unit = {}, onSuccess: (JSONObject) -> Unit): WorkspaceAction {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val client = LocalWorkspaceTransport.current
    val checkpoints = remember(context) { JobCheckpointStore(context) }
    val scope = rememberCoroutineScope()
    val callback by rememberUpdatedState(onSuccess)
    val preparedCallback by rememberUpdatedState(onPrepared)
    val failedCallback by rememberUpdatedState(onFailure)
    val feedback = rememberSpatialHapticFeedback()
    val reauthenticate = LocalReauthenticate.current
    var busy by remember(session.userId) { mutableStateOf(false) }
    var error by remember(session.userId) { mutableStateOf<String?>(null) }
    var ambiguous by remember(session.userId) { mutableStateOf(false) }
    val invalidate = LocalWorkspaceInvalidate.current
    return WorkspaceAction(busy, error, ambiguous) { path, body, method, tracked, userInitiated ->
        if (!busy && session.token.isNotBlank()) {
            busy = true; error = null; ambiguous = false
            scope.launch {
                var checkpoint: String? = null
                var prepared = JobCheckpointPreparation(false)
                try {
                    val requestBody = workspaceRequestBody(body, method, tracked)
                    checkpoint = requestBody?.optString("request_id")?.takeIf { tracked && it.isNotBlank() }
                    val requestId = checkpoint
                    prepared = prepareWorkspaceRequest(checkpoints, session.userId, requestId, path, requestBody)
                    if (!prepared.persisted) {
                        error = "Не удалось сохранить задание на устройстве. Сверьте сохранённые запросы; новый запрос не отправлен."
                        val failure = VolumeReply(error = error, code = "checkpoint_not_saved")
                        reportActionFeedback(failure, feedback, method, userInitiated)
                        failedCallback(WorkspaceRequestFailure(failure, requestId, false))
                        return@launch
                    }
                    requestId?.let(preparedCallback)
                    val reply = withContext(Dispatchers.IO) { client.request(session.token, path, method, requestBody) }
                    if (reply.signedOut) reauthenticate()
                    error = reply.error; ambiguous = reply.ambiguous
                    reportActionFeedback(reply, feedback, method, userInitiated)
                    val result = reply.data
                    if (result != null) {
                        if (!saveJobAcknowledgement(checkpoints, session.userId, requestId, path, result)) {
                            error = "Подтверждение задания не сохранено. Сверьте сохранённый запрос перед продолжением."
                            ambiguous = true
                            failedCallback(WorkspaceRequestFailure(reply.copy(data = null, error = error, ambiguous = true), requestId, true))
                            return@launch
                        }
                        callback(result)
                        if (method != "GET") invalidate()
                    } else {
                        val removed = discardRejectedCheckpoint(checkpoints, session.userId, requestId, path, prepared, reply)
                        failedCallback(WorkspaceRequestFailure(reply, requestId, requestId != null && !removed))
                    }
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) {
                    ambiguous = checkpoint != null && prepared.persisted
                    error = if (ambiguous) "Исход запроса не подтверждён. Сверьте сохранённое задание." else "Не удалось выполнить запрос. Попробуйте позже."
                    failedCallback(WorkspaceRequestFailure(VolumeReply(error = error, ambiguous = ambiguous), checkpoint, ambiguous))
                } finally { busy = false }
            }
        }
    }
}

private fun reportActionFeedback(reply: VolumeReply, feedback: (SpatialHaptic) -> Unit,
    method: String, userInitiated: Boolean) {
    if (!userInitiated || method == "GET") return
    when {
        reply.data != null -> feedback(SpatialHaptic.Confirmed)
        reply.error != null -> feedback(SpatialHaptic.Rejected)
    }
}

internal fun JSONObject.records(key: String): List<JSONObject> =
    (optJSONArray(key) ?: JSONArray()).let { array -> (0 until array.length()).mapNotNull { array.optJSONObject(it) } }
internal fun JSONObject.strings(key: String): List<String> =
    (optJSONArray(key) ?: JSONArray()).let { array -> (0 until array.length()).mapNotNull { array.optString(it).takeIf { text -> text.isNotBlank() && text != "null" } } }
internal fun JSONObject.text(key: String, fallback: String = "Нет сведений"): String =
    if (isNull(key)) fallback else optString(key).takeIf { it.isNotBlank() && it != "null" } ?: fallback

internal fun moneyText(value: JSONObject?): String {
    if (value == null) return "Сумма не получена"
    val amount = value.optString("amount").takeIf { it.isNotBlank() }?.toBigDecimalOrNull()
        ?: value.optJSONObject("value")?.let { decimal ->
            decimal.optString("units", "0").toBigDecimalOrNull()?.add(BigDecimal.valueOf(decimal.optLong("nano"), 9))
        } ?: return "Сумма не получена"
    val formatted = NumberFormat.getNumberInstance(Locale.forLanguageTag("ru-RU")).apply { maximumFractionDigits = 2 }.format(amount)
    return "$formatted ${value.text("currency", "")}".trim()
}

internal fun localMoment(raw: String): String = runCatching {
    java.time.Instant.parse(raw).atZone(java.time.ZoneId.systemDefault())
        .format(java.time.format.DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrDefault(raw.take(80))


private fun workspaceRequestBody(body: JSONObject?, method: String, tracked: Boolean): JSONObject? {
    val request = body?.let { JSONObject(it.toString()) }
        ?: if (method == "GET" || method == "DELETE") null else JSONObject()
    if (tracked && request?.has("request_id") != true) request?.put("request_id", UUID.randomUUID().toString())
    return request
}

private suspend fun saveJobAcknowledgement(checkpoints: JobCheckpointStore, userId: String,
    requestId: String?, path: String, result: JSONObject): Boolean {
    if (requestId == null) return true
    val jobId = result.optString("job_id").takeIf { it.isNotBlank() && it != "null" } ?: return false
    return withContext(Dispatchers.IO) { checkpoints.save(userId, requestId, path, jobId) }
}

private suspend fun prepareWorkspaceRequest(checkpoints: JobCheckpointStore, userId: String,
    requestId: String?, path: String, body: JSONObject?): JobCheckpointPreparation {
    if (requestId == null) return JobCheckpointPreparation(true)
    return withContext(Dispatchers.IO) { checkpoints.prepare(userId, requestId, path, body) }
}

private suspend fun discardRejectedCheckpoint(checkpoints: JobCheckpointStore, userId: String,
    requestId: String?, path: String, prepared: JobCheckpointPreparation, reply: VolumeReply): Boolean {
    // Discard only a fresh request with a definite pre-enqueue rejection.
    // A prior ambiguous dispatch remains recoverable even if a later retry is rejected.
    if (requestId == null || !prepared.isNew || !JobCheckpointStore.isChatPath(path) ||
        reply.ambiguous || reply.status !in 400..499 || reply.code == "request_id_payload_conflict") return false
    return withContext(Dispatchers.IO) { checkpoints.removeRequest(userId, requestId) }
}
