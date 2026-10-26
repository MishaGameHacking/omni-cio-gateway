package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.VolumeReply

/** The provider outlives individual routes; authorization remains session-scoped. */
class WorkspaceAutoSaveController {
    var ready by mutableStateOf(false); internal set
    var loadError by mutableStateOf<String?>(null); internal set
    internal var loadRevision by mutableIntStateOf(0)
    internal val records = mutableStateMapOf<AutoSaveKey, AutoSaveRecord>()
    internal val wake = Channel<Unit>(Channel.CONFLATED)
    internal val storeWake = Channel<Unit>(Channel.CONFLATED)
    internal var lastEditAt = 0L
    internal var inFlight: JSONObject? = null
    operator fun get(kind: AutoSaveKind, documentId: String = ""): AutoSaveRecord? = records[AutoSaveKey(kind, documentId)]
    fun documents(kind: AutoSaveKind): List<AutoSaveRecord> = records.values.filter { it.kind == kind }
    fun edit(kind: AutoSaveKind, baseline: JSONObject, draft: JSONObject, version: Int, valid: Boolean,
        documentId: String = "") {
        if (!ready || version < 0) return
        val key = AutoSaveKey(kind, documentId)
        val old = records[key]
        records[key] = AutoSaveRecord(kind, (old?.revision ?: 0) + 1,
            if (old != null && old.phase != AutoSavePhase.Saved) old.baseline else baseline.toString(),
            draft.toString(), maxOf(old?.version ?: 0, version), valid,
            if (valid) AutoSavePhase.Pending else AutoSavePhase.Invalid, documentId = documentId)
        lastEditAt = android.os.SystemClock.elapsedRealtime()
        storeWake.trySend(Unit)
        wake.trySend(Unit)
    }
    fun retry(kind: AutoSaveKind, documentId: String = "") {
        if (!ready) { loadRevision++; return }
        val key = AutoSaveKey(kind, documentId)
        records[key]?.let { records[key] = it.copy(phase = if (it.valid) AutoSavePhase.Pending else AutoSavePhase.Invalid, error = null) }
        storeWake.trySend(Unit)
        wake.trySend(Unit)
    }
}

val LocalWorkspaceAutoSave = staticCompositionLocalOf<WorkspaceAutoSaveController?> { null }

private fun AutoSaveRecord.json(): JSONObject = JSONObject().put("kind", kind.name).put("revision", revision)
    .put("baseline", JSONObject(baseline)).put("draft", JSONObject(draft)).put("version", version)
    .put("valid", valid).put("phase", phase.name).put("document_id", documentId)

private fun restoreAutoSaveRecord(value: JSONObject): AutoSaveRecord = AutoSaveRecord(
    AutoSaveKind.valueOf(value.getString("kind")), value.getLong("revision"),
    value.getJSONObject("baseline").toString(), value.getJSONObject("draft").toString(),
    value.getInt("version"), value.getBoolean("valid"),
    if (value.getString("phase") == AutoSavePhase.Saved.name) AutoSavePhase.Saved
    else if (!value.getBoolean("valid")) AutoSavePhase.Invalid else AutoSavePhase.Pending,
    documentId = value.optString("document_id", ""))

@Composable
fun WorkspaceAutoSaveProvider(content: @Composable () -> Unit) {
    val session = LocalWorkspaceSession.current
    val context = LocalContext.current
    val client = LocalWorkspaceTransport.current
    val controller = remember(session.userId, session.token) { WorkspaceAutoSaveController() }
    val storage = remember(context) { EncryptedWorkspaceStore(context) }
    val foreground by rememberUpdatedState(workspaceForeground())
    val reauthenticate by rememberUpdatedState(LocalReauthenticate.current)
    val invalidate by rememberUpdatedState(LocalWorkspaceInvalidate.current)
    LaunchedEffect(foreground) { if (foreground) controller.wake.trySend(Unit) }
    LaunchedEffect(controller, controller.loadRevision) {
        if (session.userId.isBlank() || session.token.isBlank()) return@LaunchedEffect
        val key = "automatic_settings_v1"
        val restored = withContext(Dispatchers.IO) { storage.readJson(session.userId, key) }
        if (restored == null && withContext(Dispatchers.IO) { storage.hasEntry(session.userId, key) }) {
            controller.loadError = "Не удалось прочитать сохранённые изменения. Повторите проверку."
            return@LaunchedEffect
        }
        controller.loadError = null
        restored?.optJSONArray("records")?.let { rows ->
            for (index in 0 until rows.length()) runCatching { restoreAutoSaveRecord(rows.getJSONObject(index)) }
                .getOrNull()?.let { controller.records[it.key] = it }
        }
        controller.inFlight = restored?.optJSONObject("in_flight")
        controller.ready = true
        val failures = mutableMapOf<Pair<AutoSaveKey, Long>, Int>()
        val storageMutex = Mutex()
        suspend fun persist(): Boolean = storageMutex.withLock {
            val value = JSONObject().put("records", JSONArray(controller.records.values.map { it.json() }))
                .put("in_flight", controller.inFlight ?: JSONObject.NULL)
            withContext(Dispatchers.IO) { storage.saveJson(session.userId, key, value) }
        }
        // Device writes must never wait behind HTTP, debounce, or a stalled connection.
        launch {
            for (ignored in controller.storeWake) {
                if (!persist()) {
                    val revisions = controller.records.mapValues { it.value.revision }
                    controller.records.keys.toList().forEach { kind -> controller.records[kind]?.let {
                        if (it.phase != AutoSavePhase.Saved) controller.records[kind] = it.copy(phase = AutoSavePhase.Failed,
                            error = "Не удалось сохранить изменение на устройстве.")
                    } }
                    delay(2_000)
                    revisions.forEach { (kind, revision) ->
                        val waiting = controller.records[kind]
                        if (waiting?.revision == revision && waiting.phase == AutoSavePhase.Failed)
                            controller.retry(kind.kind, kind.documentId)
                    }
                }
            }
        }
        suspend fun request(path: String, method: String = "GET", body: JSONObject? = null): VolumeReply =
            withContext(Dispatchers.IO) { client.request(session.token, path, method, body) }
        controller.wake.trySend(Unit)
        for (signal in controller.wake) {
            // Save intent before debounce, so navigation cannot discard a typed value.
            if (!persist()) {
                controller.records.keys.toList().forEach { kind -> controller.records[kind]?.let {
                    if (it.phase != AutoSavePhase.Saved) controller.records[kind] = it.copy(phase = AutoSavePhase.Failed,
                        error = "Не удалось сохранить изменение на устройстве.")
                } }
                continue
            }
            do {
                val remaining = 450L - (android.os.SystemClock.elapsedRealtime() - controller.lastEditAt)
                if (remaining > 0) delay(remaining)
            } while (android.os.SystemClock.elapsedRealtime() - controller.lastEditAt < 450L)
            if (!foreground) continue
            val recovery = controller.inFlight
            val sent = if (recovery != null) runCatching { restoreAutoSaveRecord(recovery.getJSONObject("record")) }.getOrNull()
                else controller.records.values.firstOrNull { it.phase == AutoSavePhase.Pending && it.valid }
            if (sent == null) continue
            val current = controller.records[sent.key] ?: continue
            if (current.revision == sent.revision) controller.records[sent.key] = current.copy(phase = AutoSavePhase.Saving)
            var accepted: JSONObject? = null
            var version = sent.version
            var failure: String? = null
            try {
                var command = recovery
                if (command == null) {
                    val path = when (sent.kind) {
                        AutoSaveKind.Notifications -> "/workspace/notifications/preferences"
                        AutoSaveKind.Strategy -> "/workspace/strategy"
                        AutoSaveKind.Analysis -> "/analysis/profile"
                        AutoSaveKind.Goal -> "/workspace/goals"
                    }
                    val latest = request(path)
                    if (latest.signedOut) { reauthenticate(); break }
                    val data = latest.data ?: error(latest.error ?: "Не удалось проверить сохранённые настройки.")
                    val remote = when (sent.kind) {
                        AutoSaveKind.Notifications -> data.getJSONObject("preferences")
                        AutoSaveKind.Strategy -> data.optJSONObject("active")?.optJSONObject("config") ?: JSONObject(sent.baseline)
                        AutoSaveKind.Analysis -> analysisEditableDocument(data)
                        AutoSaveKind.Goal -> {
                            val id = JSONObject(sent.draft).autoSaveId()
                            if (id == null) JSONObject(sent.baseline) else
                                data.records("items").firstOrNull { it.text("id") == id }?.let(::goalEditableDocument)
                                    ?: error("Цель больше недоступна. Новая цель вместо неё не создавалась.")
                        }
                    }
                    version = when (sent.kind) {
                        AutoSaveKind.Notifications -> data.getInt("version")
                        AutoSaveKind.Strategy -> data.optJSONObject("active")?.optInt("version") ?: 0
                        else -> 0
                    }
                    val merged = mergeAutoSaveChanges(JSONObject(sent.baseline), JSONObject(sent.draft), remote)
                    if (equivalentJson(merged, remote)) accepted = remote
                    else {
                        command = JSONObject().put("record", sent.json()).put("request_id", UUID.randomUUID().toString())
                            .put("version", version).put("config", merged)
                        if (sent.kind == AutoSaveKind.Strategy) {
                            val prepared = request("/workspace/strategy/preview", "POST",
                                JSONObject().put("expected_version", version).put("config", merged))
                            if (prepared.signedOut) { reauthenticate(); break }
                            val preview = prepared.data ?: error(prepared.error ?: "Не удалось проверить правила стратегии.")
                            check(preview.optBoolean("can_confirm")) { "Сервер пока не разрешил применить эти правила." }
                            command.put("preview_id", preview.getString("preview_id"))
                        }
                        controller.inFlight = command
                        check(persist()) { "Не удалось записать запрос на устройстве. Изменение не отправлено." }
                    }
                }
                if (accepted == null && command != null) {
                    version = command.getInt("version")
                    val reply = when (sent.kind) {
                      AutoSaveKind.Notifications ->
                        request("/workspace/notifications/preferences", "PUT", JSONObject(command.getJSONObject("config").toString())
                            .put("expected_version", version))
                      AutoSaveKind.Strategy -> request("/workspace/strategy/confirm", "POST", JSONObject()
                        .put("preview_id", command.getString("preview_id")).put("expected_version", version)
                        .put("request_id", command.getString("request_id")))
                      AutoSaveKind.Analysis -> request("/analysis/profile", "PUT", command.getJSONObject("config"))
                      AutoSaveKind.Goal -> request("/workspace/goals", "POST", JSONObject(command.getJSONObject("config").toString())
                          .put("request_id", command.getString("request_id")))
                    }
                    if (reply.signedOut) { reauthenticate(); break }
                    val data = reply.data
                    if (data != null) {
                        accepted = when (sent.kind) {
                            AutoSaveKind.Notifications -> data.getJSONObject("preferences")
                            AutoSaveKind.Strategy -> data.getJSONObject("active").getJSONObject("config")
                            AutoSaveKind.Analysis -> analysisEditableDocument(data)
                            AutoSaveKind.Goal -> goalEditableDocument(data)
                        }
                        version = when (sent.kind) {
                            AutoSaveKind.Notifications -> data.getInt("version")
                            AutoSaveKind.Strategy -> data.getJSONObject("active").getInt("version")
                            else -> 0
                        }
                    } else {
                        if (sent.kind == AutoSaveKind.Notifications && reply.status == 409) {
                            val observed = request("/workspace/notifications/preferences")
                            if (observed.signedOut) { reauthenticate(); break }
                            val actual = observed.data?.optJSONObject("preferences")
                            if (actual != null && equivalentJson(actual, command.getJSONObject("config"))) {
                                accepted = actual; version = checkNotNull(observed.data).getInt("version")
                            }
                        }
                        // A definitive rejection permits a new versioned attempt; uncertainty keeps the exact command.
                        if (!reply.ambiguous && reply.status in 400..499 && reply.code != "request_id_payload_conflict") controller.inFlight = null
                        failure = reply.error ?: "Подтверждение сохранения пока не получено."
                    }
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (problem: Exception) { failure = problem.message ?: "Не удалось сохранить настройки." }
            val latest = controller.records[sent.key]
            if (accepted != null && latest != null) {
                controller.records[sent.key] = acknowledgeAutoSave(latest, sent, accepted, version)
                controller.inFlight = null
                failures.remove(sent.key to sent.revision)
                if (persist()) invalidate()
                else controller.records[sent.key] = controller.records.getValue(sent.key).copy(phase = AutoSavePhase.Failed,
                    error = "Сервер принял настройку; запись подтверждения на устройстве не завершена.")
            } else if (latest != null) {
                controller.records[sent.key] = latest.copy(phase =
                    if (latest.revision != sent.revision && controller.inFlight == null && latest.valid) AutoSavePhase.Pending
                    else AutoSavePhase.Failed, error = failure)
                persist()
                val identity = sent.key to latest.revision
                val attempt = (failures[identity] ?: 0) + 1
                failures[identity] = attempt
                if (attempt <= 3) launch {
                    delay(5_000L * attempt)
                    val waiting = controller.records[sent.key]
                    if (foreground && waiting?.revision == latest.revision && waiting.phase == AutoSavePhase.Failed)
                        controller.retry(sent.kind, sent.documentId)
                }
            }
            if (controller.records.values.any { it.phase == AutoSavePhase.Pending && it.valid }) controller.wake.trySend(Unit)
        }
    }
    CompositionLocalProvider(LocalWorkspaceAutoSave provides controller, content = content)
}
