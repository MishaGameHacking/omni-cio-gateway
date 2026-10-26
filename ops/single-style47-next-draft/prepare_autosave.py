"""Administrative text delta: automatic persistence, verified on Windows only."""

def apply(files, base):
    ui='app/src/main/java/ru/omnicio/app/ui/'
    def get(p): return files[p] if p in files else base(p)
    def replace(p,old,new,count=1):
        s=get(p);assert s.count(old)==count,(p,old[:100],s.count(old));files[p]=s.replace(old,new)

    files[ui+'workspace/AutoSaveModel.kt']='''package ru.omnicio.app.ui.workspace

import org.json.JSONObject

enum class AutoSaveKind { Notifications, Strategy, Analysis, Goal }
enum class AutoSavePhase { Pending, Invalid, Saving, Saved, Failed }
data class AutoSaveKey(val kind: AutoSaveKind, val documentId: String = "")

data class AutoSaveRecord(val kind: AutoSaveKind, val revision: Long, val baseline: String,
    val draft: String, val version: Int, val valid: Boolean, val phase: AutoSavePhase,
    val error: String? = null, val documentId: String = "") {
    val key: AutoSaveKey get() = AutoSaveKey(kind, documentId)
}

/** Stable comparison ignores JSON key order, without coercing source values. */
internal fun equivalentJson(a: Any?, b: Any?): Boolean = when {
    a === JSONObject.NULL || b === JSONObject.NULL -> a === b
    a == null || b == null -> a == null && b == null
    a is JSONObject && b is JSONObject -> a.keys().asSequence().toSet() == b.keys().asSequence().toSet() && a.keys().asSequence().all { equivalentJson(a.opt(it), b.opt(it)) }
    a is org.json.JSONArray && b is org.json.JSONArray -> a.length() == b.length() &&
        (0 until a.length()).all { equivalentJson(a.opt(it), b.opt(it)) }
    a is Number && b is Number -> {
        val left = a.toString().toBigDecimalOrNull(); val right = b.toString().toBigDecimalOrNull()
        left != null && right != null && left.compareTo(right) == 0
    }
    else -> a == b
}

/** Carry only the user's changed leaves onto the latest server document. */
internal fun mergeAutoSaveChanges(baseline: JSONObject, draft: JSONObject, latest: JSONObject): JSONObject {
    val result = JSONObject(latest.toString())
    (baseline.keys().asSequence().toSet() + draft.keys().asSequence().toSet()).forEach { key ->
        if (!equivalentJson(baseline.opt(key), draft.opt(key))) {
            if (!draft.has(key)) result.remove(key)
            else if (baseline.opt(key) is JSONObject && draft.opt(key) is JSONObject && latest.opt(key) is JSONObject)
                result.put(key, mergeAutoSaveChanges(baseline.getJSONObject(key), draft.getJSONObject(key), latest.getJSONObject(key)))
            else result.put(key, draft.opt(key))
        }
    }
    return result
}

/** An old acknowledgement advances the base but never replaces a newer edit. */
internal fun acknowledgeAutoSave(current: AutoSaveRecord, sent: AutoSaveRecord,
    confirmed: JSONObject, version: Int): AutoSaveRecord {
    require(current.key == sent.key && version >= 0)
    val value = if (current.revision == sent.revision) confirmed else
        mergeAutoSaveChanges(JSONObject(sent.draft), JSONObject(current.draft), confirmed)
    val pending = current.revision != sent.revision
    return current.copy(baseline = confirmed.toString(), draft = value.toString(), version = version,
        phase = if (pending) { if (current.valid) AutoSavePhase.Pending else AutoSavePhase.Invalid } else AutoSavePhase.Saved,
        error = null)
}
'''

    files[ui+'workspace/WorkspaceAutoSave.kt']='''package ru.omnicio.app.ui.workspace

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
                        AutoSaveKind.Analysis -> data
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
                            AutoSaveKind.Analysis -> data
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
'''

    # Mount once around the shared navigator, including debug hosts using that navigator.
    path=ui+'AnalystNavigationPanels.kt'
    replace(path,'    var menuOpen by remember { mutableStateOf(false) }','''    if (ru.omnicio.app.ui.workspace.LocalWorkspaceAutoSave.current == null) {
        ru.omnicio.app.ui.workspace.WorkspaceAutoSaveProvider {
            AnalystNavigationPanels(selected, selectedWorkspace, wide, navigateTab, navigateWorkspace, content)
        }
        return
    }
    var menuOpen by remember { mutableStateOf(false) }''')

    files[ui+'workspace/AutoSaveStatus.kt']='''package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import ru.omnicio.app.ui.spectrum.*

@Composable
fun AutoSaveStatus(record: AutoSaveRecord?, retry: () -> Unit) {
    val loadingError = LocalWorkspaceAutoSave.current?.loadError
    val text = loadingError ?: when (record?.phase) {
        null -> "Изменения сохраняются автоматически"
        AutoSavePhase.Pending -> "Изменение ожидает сохранения"
        AutoSavePhase.Invalid -> "Некорректное значение. Применение приостановлено"
        AutoSavePhase.Saving -> "Сохраняем…"
        AutoSavePhase.Saved -> "Сохранено на сервере"
        AutoSavePhase.Failed -> record.error ?: "Сохранение не подтверждено"
    }
    Text(text, Modifier.semantics { liveRegion = LiveRegionMode.Polite }, style = MaterialTheme.typography.bodySmall,
        color = if (record?.phase == AutoSavePhase.Failed || loadingError != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
    if (record?.phase == AutoSavePhase.Failed || loadingError != null) SpectrumTextButton("Повторить сохранение", retry, symbol = SpectrumSymbol.Update)
}
'''

    # Device appearance: immediate value, serial durable commit, truthful status.
    path=ui+'workspace/WorkspacePreferences.kt'
    value=get(path)
    value=value.replace('import androidx.compose.ui.platform.LocalContext\n','''import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.withContext
''')
    value=value.replace('    val update: (WorkspacePreferences) -> Unit = {},','''    val update: (WorkspacePreferences) -> Unit = {},
    val saveStatus: String = "Сохранено на устройстве",
    val saveFailed: Boolean = false,
    val retrySave: () -> Unit = {},''')
    start=value.index('    val save: (WorkspacePreferences) -> Unit =')
    end=value.index('    val controller = WorkspacePreferenceController',start)
    value=value[:start]+'''    var revision by remember { mutableLongStateOf(0L) }
    var status by remember { mutableStateOf("Сохранено на устройстве") }
    var failed by remember { mutableStateOf(false) }
    val changes = remember { Channel<Pair<Long, WorkspacePreferences>>(Channel.CONFLATED) }
    val save: (WorkspacePreferences) -> Unit = { next ->
        value = next; preview = null; revision++
        status = "Сохраняем…"; failed = false
        changes.trySend(revision to next)
    }
    LaunchedEffect(store) {
        for ((request, next) in changes) {
            val persisted = withContext(Dispatchers.IO) { runCatching {
                store.edit().putString("accent", next.accent.name).putString("density", next.density.name)
                    .putBoolean("depth", next.depth).putBoolean("hide_home_balance", next.hideHomeBalance)
                    .putBoolean("home_structure", next.homeStructure).putBoolean("haptics", next.haptics)
                    .putString("motion", next.motion.name).putBoolean("bright_light", next.brightLight).commit()
            }.getOrDefault(false) }
            if (request == revision) {
                failed = !persisted
                status = if (persisted) "Сохранено на устройстве" else "Не удалось сохранить на устройстве"
            }
        }
    }
'''+value[end:]
    value=value.replace('        applyPreview = { preview?.let(save) }, update = save)',
        '        applyPreview = { preview?.let(save) }, update = save, saveStatus = status, saveFailed = failed, retrySave = { save(value) })')
    files[path]=value

    path=ui+'workspace/AppearanceScreen.kt'
    value=get(path)
    a=value.index('private val appearancePreferencesSaver =')
    b=value.index('    WorkspaceDetailPage(',a)
    value=value[:a]+'''@Composable
fun AppearanceScreen(onBack: () -> Unit) {
    val controller = LocalWorkspacePreferences.current
    val draft = controller.value
    val preview: (WorkspacePreferences) -> Unit = controller.update
    val requestExit: (() -> Unit) -> Unit = { proceed -> proceed() }
    val leave = onBack
    RegisterPanelExit(WorkspaceRoute.Appearance, requestExit)
    BackHandler(onBack = leave)
'''+value[b:]
    value=value.replace('Просмотр → применить или отменить','Изменения сохраняются автоматически')
    a=value.index('                    Text(if (dirty)')
    b=value.index('\n                }\n            }\n            item { SpectrumCard',a)
    value=value[:a]+'''                    Text(controller.saveStatus, style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.semantics { androidx.compose.ui.semantics.liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Polite })
                    if (controller.saveFailed) SpectrumSecondaryButton("Повторить сохранение", controller.retrySave, Modifier.fillMaxWidth())
'''+value[b:]
    value=value.replace('Возврат со страницы отменяет неприменённый просмотр. Системный размер шрифта и ограничения движения учитываются автоматически.',
        'Каждый выбор применяется автоматически. Системный размер шрифта и ограничения движения учитываются.')
    # Import the property normally rather than assigning a fully qualified extension.
    value=value.replace('import androidx.compose.ui.semantics.semantics\n','import androidx.compose.ui.semantics.semantics\nimport androidx.compose.ui.semantics.liveRegion\n')
    value=value.replace('androidx.compose.ui.semantics.liveRegion =','liveRegion =')
    files[path]=value

    path=ui+'workspace/NotificationWorkspaceScreens.kt'
    value=get(path);a=value.index('@Composable\nfun NotificationSettingsScreen');b=value.index('@Composable\nprivate fun NotificationRulesStatus',a)
    value=value[:a]+'''@Composable
fun NotificationSettingsScreen(onBack: () -> Unit) {
    val auto = LocalWorkspaceAutoSave.current
    val resource = rememberWorkspaceResource(NOTIFICATION_PREFERENCES_PATH)
    val context = LocalContext.current
    val record = auto?.get(AutoSaveKind.Notifications)
    val remote = resource.data?.optJSONObject("preferences")
    val remoteVersion = notificationPreferenceVersion(resource.data)
    val config = remember(record?.draft, record?.phase, remote?.toString(), remoteVersion) {
        if (record != null && (record.phase != AutoSavePhase.Saved || record.version >= (remoteVersion ?: -1))) JSONObject(record.draft)
        else remote
    }
    val editable = auto?.ready == true && config != null && remoteVersion != null
    var preview by remember { mutableStateOf<JSONObject?>(null) }
    val simulate = rememberWorkspaceAction { preview = it }
    var delivery by remember { mutableStateOf(WorkspaceNotificationService.canNotify(context)) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        delivery = granted && WorkspaceNotificationService.schedule(context)
    }
    val foreground = workspaceForeground()
    LaunchedEffect(foreground) { if (foreground) delivery = WorkspaceNotificationService.canNotify(context) }
    LaunchedEffect(record?.phase, record?.revision) {
        if (record?.phase == AutoSavePhase.Saved) {
            if (JSONObject(record.draft).optBoolean("enabled")) delivery = WorkspaceNotificationService.schedule(context)
            else WorkspaceNotificationService.cancel(context)
            resource.refresh()
        }
    }
    val edit: (String, Any) -> Unit = { key, input ->
        if (editable && !simulate.busy) {
            val next = JSONObject(config.toString()).put(key, input)
            auto?.edit(AutoSaveKind.Notifications, remote ?: JSONObject(), next, remoteVersion ?: -1, notificationRulesValid(next))
            preview = null
        }
    }
    WorkspaceDetailPage("Уведомления", "Ваше время и условия доставки", onBack, SpectrumSymbol.Notifications) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource); AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Notifications) } }
            config?.let { settings ->
                item { SpectrumCard {
                    WorkspaceToggle("Получать события", "Применяется автоматически", settings.optBoolean("enabled"), enabled = editable && !simulate.busy) { edit("enabled", it) }
                    WorkspaceToggle("Утренние и вечерние обзоры", "Только по заданному времени", settings.optBoolean("briefs_enabled"), enabled = editable && !simulate.busy) { edit("briefs_enabled", it) }
                    WorkspaceToggle("Критичные изменения", "По подтверждённым правилам риска", settings.optBoolean("critical_enabled"), enabled = editable && !simulate.busy) { edit("critical_enabled", it) }
                } }
                item { SpectrumCard {
                    val zone = settings.text("timezone", "Europe/Moscow")
                    val deviceZone = remember { ZoneId.systemDefault().id }
                    val zones = remember(deviceZone, zone) { notificationZoneSuggestions(deviceZone, zone) }
                    WorkspaceChoicePicker("Часовой пояс", zone, zones, editable && !simulate.busy) { edit("timezone", it) }
                    Text("Все часы относятся к выбранному поясу.", style = MaterialTheme.typography.bodySmall)
                    listOf("morning" to "Утро", "evening" to "Вечер", "quiet_start" to "Тихие часы с", "quiet_end" to "Тихие часы до").forEach { (key, title) ->
                        WorkspaceTimeChoice(title, settings.text(key, ""), editable && !simulate.busy) { edit(key, it) }
                    }
                    Text("Тихие часы могут переходить через полночь.")
                    if (!notificationRulesValid(settings)) Text("Проверьте время: утренний и вечерний обзоры должны приходить в разное время.",
                        color = MaterialTheme.colorScheme.error)
                } }
                item { SpectrumCard {
                    SpectrumSecondaryButton("Проверить на прошлых событиях", {
                        simulate.perform("/workspace/notifications/preview", JSONObject().put("preferences", settings))
                    }, Modifier.fillMaxWidth(), editable && notificationRulesValid(settings) && !simulate.busy)
                    WorkspaceActionState(simulate)
                } }
            }
            item { SpectrumCard {
                Text("Доставка на это устройство", style = MaterialTheme.typography.titleMedium)
                Text(if (delivery) "Android разрешает показ уведомлений." else "Показ уведомлений пока не разрешён на устройстве.")
                Text("Android может отложить фоновую проверку. Все события доступны в приложении.")
                if (!delivery) SpectrumPrimaryButton("Разрешить уведомления", { permission.launch(Manifest.permission.POST_NOTIFICATIONS) }, Modifier.fillMaxWidth())
                SpectrumSecondaryButton("Настройки уведомлений Android", {
                    context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                }, Modifier.fillMaxWidth())
            } }
            preview?.let { result -> item { NotificationPreview(result) } }
        }
    }
}

'''+value[b:];files[path]=value

    path=ui+'workspace/LiveStrategyScreen.kt'
    value=get(path);a=value.index('@OptIn(ExperimentalLayoutApi::class)');b=value.index('private fun defaultStrategy()',a)
    value=value[:a]+'''@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LiveStrategyScreen(userId: String, onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/strategy")
    val active = resource.data?.optJSONObject("active")
    val auto = LocalWorkspaceAutoSave.current
    val record = auto?.get(AutoSaveKind.Strategy)
    val context = LocalContext.current
    val storage = remember(context) { EncryptedWorkspaceStore(context) }
    var configText by rememberSaveable(userId) { mutableStateOf(defaultStrategy().toString()) }
    var hasEditorState by rememberSaveable(userId) { mutableStateOf(false) }
    var loaded by remember(userId) { mutableStateOf(false) }
    var tab by rememberSaveable(userId) { mutableIntStateOf(0) }
    val version = active?.optInt("version") ?: 0
    val config = remember(configText) { JSONObject(configText) }
    LaunchedEffect(resource.data, auto?.ready) {
        if (resource.data != null && auto?.ready == true && !loaded) {
            if (!hasEditorState) {
                val restored = withContext(Dispatchers.IO) { storage.readJson(userId, "strategy_editor")?.optJSONObject("config") }
                configText = record?.draft ?: (restored ?: active?.optJSONObject("config") ?: defaultStrategy()).toString()
                hasEditorState = true
            }
            loaded = true
        }
    }
    LaunchedEffect(record?.revision, record?.draft, record?.phase) {
        if (record != null) {
            configText = record.draft
            if (record.phase == AutoSavePhase.Saved) resource.refresh()
        }
    }
    val editor = StrategyEditorAvailability(hasEditorState, auto?.ready != true)
    val edit: (JSONObject) -> Unit = { next ->
        if (editor.canEdit) {
            configText = next.toString()
            auto?.edit(AutoSaveKind.Strategy, active?.optJSONObject("config") ?: defaultStrategy(), next,
                version, validStrategy(next))
        }
    }
    val restoreVersion = rememberWorkspaceAction { result -> result.optJSONObject("config")?.let(edit) }
    val requestExit: (() -> Unit) -> Unit = { proceed -> proceed() }
    RegisterPanelExit(WorkspaceRoute.Strategies, requestExit)
    SpatialBackHandler(onBack = onBack)
    WorkspaceDetailPage("Моя стратегия", "Правила сохраняются после проверки сервером", onBack, SpectrumSymbol.Strategy,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            if (!compact || !WindowInsets.isImeVisible) SpectrumTabs(listOf("Цель", "Резерв", "Лимиты", "Версии"), tab, { tab = it }, Modifier.padding(horizontal = 20.dp))
            LazyColumn(Modifier.weight(1f).fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = if (compact) 0.dp else 20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item { WorkspaceRequestState(resource); AutoSaveStatus(record) { auto?.retry(AutoSaveKind.Strategy) } }
                when (tab) {
                    0 -> item { StrategyGoalEditor(config, editor.canEdit, edit) }
                    1 -> item { StrategyReserveEditor(config, editor.canEdit, edit) }
                    2 -> limitTitles.forEach { (key, title) -> item { StrategyLimitEditor(title, key, config, editor.canEdit, edit) } }
                    else -> resource.data?.records("history").orEmpty().forEach { old -> item {
                        StrategyHistoryCard(old, active, loaded, editor, version, restoreVersion)
                    } }
                }
                item { DetailFold("Сравнить с действующими правилами") { StrategyDifference(active?.optJSONObject("config"), config) } }
                item { WorkspaceActionState(restoreVersion) }
                if (!validStrategy(config)) item { Text("Проверьте горизонт, сумму резерва и лимиты больше 0 и до 100%.", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

'''+value[b:]
    value=value.replace('"Рассчитать возврат к этой версии"','"Использовать эту версию"')
    files[path]=value

    path=ui+'workspace/WorkspaceControls.kt'
    replace(path,'fun WorkspaceToggle(title: String, detail: String, checked: Boolean, modifier: Modifier = Modifier, onChange: (Boolean) -> Unit)',
        'fun WorkspaceToggle(title: String, detail: String, checked: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true, onChange: (Boolean) -> Unit)')
    replace(path,'.toggleable(checked, role = Role.Switch, onValueChange = onChange)',
        '.toggleable(checked, enabled = enabled, role = Role.Switch, onValueChange = onChange)')
    replace(path,'SpatialToggleVisual(checked, Modifier.size(width = 52.dp, height = 32.dp))',
        'SpatialToggleVisual(checked, Modifier.size(width = 52.dp, height = 32.dp), enabled = enabled)')

    path=ui+'workspace/WorkspaceSuggestedControls.kt'
    replace(path,'''        SpectrumAlertDialog(onDismissRequest = { open = false }, title = { Text(title) },''',
        '''        var previous by remember { mutableStateOf(String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)) }
        LaunchedEffect(time.hour, time.minute, enabled) {
            val next = String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)
            if (enabled && next != previous) { previous = next; onSelect(next) }
        }
        SpectrumAlertDialog(onDismissRequest = { open = false }, title = { Text(title) },''')
    replace(path,'''                SpectrumPrimaryButton("Выбрать время", {
                    if (enabled) { onSelect(String.format(Locale.ROOT, "%02d:%02d", time.hour, time.minute)); open = false }
                }, Modifier.fillMaxWidth(), enabled)
            }, dismissButton = { SpectrumSecondaryButton("Отмена", { open = false }, Modifier.fillMaxWidth()) })''',
        '''                SpectrumPrimaryButton("Готово", { open = false }, Modifier.fillMaxWidth())
            })''')

    files['app/src/test/java/ru/omnicio/app/ui/workspace/AutoSaveModelTest.kt']='''package ru.omnicio.app.ui.workspace

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AutoSaveModelTest {
    @Test fun newerLocalEditSurvivesOlderServerAcknowledgement() {
        val sent = AutoSaveRecord(AutoSaveKind.Notifications, 1, "{\\"morning\\":\\"08:00\\"}",
            "{\\"morning\\":\\"09:00\\"}", 4, true, AutoSavePhase.Saving)
        val current = sent.copy(revision = 2, draft = "{\\"morning\\":\\"10:00\\"}")
        val next = acknowledgeAutoSave(current, sent, JSONObject(sent.draft), 5)
        assertEquals("10:00", JSONObject(next.draft).getString("morning"))
        assertEquals(5, next.version)
        assertEquals(AutoSavePhase.Pending, next.phase)
    }
    @Test fun concurrentServerFieldsAreRetainedInNestedDocument() {
        val base = JSONObject("{\\"limits\\":{\\"position\\":10,\\"sector\\":40},\\"zone\\":\\"A\\"}")
        val local = JSONObject("{\\"limits\\":{\\"position\\":15,\\"sector\\":40},\\"zone\\":\\"A\\"}")
        val server = JSONObject("{\\"limits\\":{\\"position\\":10,\\"sector\\":30},\\"zone\\":\\"B\\"}")
        val merged = mergeAutoSaveChanges(base, local, server)
        assertEquals(15, merged.getJSONObject("limits").getInt("position"))
        assertEquals(30, merged.getJSONObject("limits").getInt("sector"))
        assertEquals("B", merged.getString("zone"))
    }
    @Test fun malformedNewerDraftNeverBecomesAppliedBecauseOlderRequestSucceeded() {
        val sent = AutoSaveRecord(AutoSaveKind.Strategy, 3, "{}", "{\\"horizon_months\\":12}", 2, true, AutoSavePhase.Saving)
        val current = sent.copy(revision=4, draft="{\\"horizon_months\\":\\"\\"}", valid=false)
        val next = acknowledgeAutoSave(current, sent, JSONObject(sent.draft), 3)
        assertEquals(AutoSavePhase.Invalid, next.phase)
        assertEquals("", JSONObject(next.draft).getString("horizon_months"))
    }
    @Test fun sameRevisionRequiresAcknowledgementBeforeSavedState() {
        val sent = AutoSaveRecord(AutoSaveKind.Notifications, 1, "{}", "{\\"enabled\\":true}", 0, true, AutoSavePhase.Saving)
        val next = acknowledgeAutoSave(sent, sent, JSONObject(sent.draft), 1)
        assertEquals(AutoSavePhase.Saved, next.phase)
        assertTrue(equivalentJson(JSONObject(next.baseline), JSONObject(next.draft)))
    }
    @Test fun comparisonsIgnoreObjectOrderButPreserveArrayOrderAndNull() {
        assertTrue(equivalentJson(JSONObject("{\\"a\\":1,\\"b\\":null}"), JSONObject("{\\"b\\":null,\\"a\\":1.0}")))
        assertFalse(equivalentJson(org.json.JSONArray("[1,2]"), org.json.JSONArray("[2,1]")))
        assertFalse(equivalentJson(JSONObject("{\\"a\\":null}"), JSONObject("{}")))
    }
    @Test fun explicitNullAndDeletionRemainDifferentChanges() {
        val removed = mergeAutoSaveChanges(JSONObject("{\\"optional\\":null}"), JSONObject("{}"), JSONObject("{\\"optional\\":null,\\"other\\":4}"))
        assertFalse(removed.has("optional"))
        assertEquals(4, removed.getInt("other"))
        val added = mergeAutoSaveChanges(JSONObject("{}"), JSONObject("{\\"optional\\":null}"), JSONObject("{\\"other\\":4}"))
        assertTrue(added.has("optional")); assertTrue(added.isNull("optional"))
    }
}
'''
