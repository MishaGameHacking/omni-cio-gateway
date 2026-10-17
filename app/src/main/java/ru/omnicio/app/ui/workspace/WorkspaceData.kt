package ru.omnicio.app.ui.workspace

import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
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
    val accountId: String? = null, val start: String? = null, val end: String? = null) {
    fun json(): JSONObject = JSONObject().put("mode", mode).put("instrument_uid", instrumentUid ?: JSONObject.NULL)
        .put("account_id", accountId ?: JSONObject.NULL).put("start", start ?: JSONObject.NULL).put("end", end ?: JSONObject.NULL)
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

/** A paid request ID is persisted BEFORE dispatch; a timeout can only recover that request. */
@Composable
fun rememberWorkspaceAction(onSuccess: (JSONObject) -> Unit): WorkspaceAction {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val client = LocalWorkspaceTransport.current
    val checkpoints = remember(context) { ru.omnicio.app.data.workspace.JobCheckpointStore(context) }
    val scope = rememberCoroutineScope()
    val callback by rememberUpdatedState(onSuccess)
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
                try {
                    val requestBody = body?.let { JSONObject(it.toString()) } ?: if (method == "GET" || method == "DELETE") null else JSONObject()
                    if (tracked && requestBody?.has("request_id") != true) requestBody?.put("request_id", UUID.randomUUID().toString())
                    val checkpoint = requestBody?.optString("request_id")?.takeIf { tracked && it.isNotBlank() }
                    val persisted = checkpoint == null || withContext(Dispatchers.IO) {
                        checkpoints.save(session.userId, checkpoint, path)
                    }
                    if (!persisted) {
                        error = "Не удалось сохранить задание на устройстве. Запрос не отправлен."
                        if (userInitiated) feedback(SpatialHaptic.Rejected)
                        return@launch
                    }
                    val reply = withContext(Dispatchers.IO) { client.request(session.token, path, method, requestBody) }
                    if (reply.signedOut) reauthenticate()
                    error = reply.error; ambiguous = reply.ambiguous
                    reportActionFeedback(reply, feedback, method, userInitiated)
                    reply.data?.let { result ->
                        if (checkpoint != null) withContext(Dispatchers.IO) {
                            checkpoints.save(session.userId, checkpoint, path, result.optString("job_id").takeIf(String::isNotBlank))
                        }
                        callback(result)
                        if (method != "GET") invalidate()
                    }
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
