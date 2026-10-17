package ru.omnicio.app.data.workspace

import android.content.Context
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.ui.workspace.LocalWorkspaceSession
import java.time.Instant
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

data class WatchEntry(val uid: String, val title: String, val reason: String, val createdAt: String)
data class SavedPortfolioFilter(val id: String, val title: String, val query: String, val accountId: String?,
    val kind: String, val sector: String?, val group: Int, val order: Int, val watchedOnly: Boolean = false,
    val exposureId: String? = null)
data class SavedResearch(val id: String, val title: String, val instrumentId: String?, val start: String?, val end: String?,
    val source: String, val observedAt: String?, val capturedAt: String, val note: String)

/** Account-specific local work; financial archives are encrypted and never treated as live data. */
class PersonalWorkspaceStore(context: Context, private val userId: String) {
    private val encrypted = EncryptedWorkspaceStore(context)
    private val mutex = locks.getOrPut(userId) { Mutex() }
    suspend fun read(): JSONObject = withContext(Dispatchers.IO) {
        readMetadata()
    }
    suspend fun change(transform: (JSONObject) -> Unit): JSONObject = mutex.withLock {
        withContext(Dispatchers.IO) {
            check(userId.isNotBlank())
            val current = readMetadata()
            transform(current)
            check(encrypted.saveJson(userId, "personal", current)) { "Не удалось сохранить изменения на устройстве." }
            current
        }
    }
    suspend fun saveArchive(id: String, payload: JSONObject): Boolean = withContext(Dispatchers.IO) {
        encrypted.saveJson(userId, "research:$id", payload)
    }
    suspend fun archive(id: String): JSONObject? = withContext(Dispatchers.IO) { encrypted.readJson(userId, "research:$id") }
    suspend fun deleteArchive(id: String): Boolean = withContext(Dispatchers.IO) { encrypted.remove(userId, "research:$id") }
    private fun readMetadata(): JSONObject {
        val value = encrypted.readJson(userId, "personal")
        check(value != null || !encrypted.hasEntry(userId, "personal")) { "Не удалось прочитать личные записи. Повторите чтение; сохранённые файлы не перезаписаны." }
        return value ?: JSONObject()
    }
    companion object { private val locks = ConcurrentHashMap<String, Mutex>() }
}

@Stable
class PersonalWorkspaceController internal constructor(
    val data: JSONObject,
    val loaded: Boolean,
    val busy: Boolean,
    val error: String?,
    private val edit: ((JSONObject) -> Unit) -> Unit,
    private val save: (SavedResearch, JSONObject) -> Unit,
    val deleteResearch: (String) -> Unit,
    val store: PersonalWorkspaceStore,
    val retry: () -> Unit,
) {
    val watches: List<WatchEntry> get() = data.rows("watchlist").mapNotNull {
        it.text("uid")?.let { uid -> WatchEntry(uid, it.optString("title", uid), it.optString("reason"), it.optString("created_at")) }
    }
    val filters: List<SavedPortfolioFilter> get() = data.rows("filters").mapNotNull {
        it.text("id")?.let { id -> SavedPortfolioFilter(id, it.optString("title"), it.optString("query"), it.text("account_id"),
            it.optString("kind", "all"), it.text("sector"), it.optInt("group").coerceIn(0, 4), it.optInt("order").coerceIn(0, 3),
            it.optBoolean("watched_only"), it.text("exposure_id")) }
    }
    val research: List<SavedResearch> get() = data.rows("research").mapNotNull {
        it.text("id")?.let { id -> SavedResearch(id, it.optString("title"), it.text("instrument_id"), it.text("start"), it.text("end"),
            it.optString("source"), it.text("observed_at"), it.optString("captured_at"), it.optString("note")) }
    }
    val dashboardOrder: List<String> get() = data.optJSONArray("dashboard_order").strings()
    val lastVisit: String? get() = data.text("previous_visit")
    val previousSnapshot: JSONObject? get() = data.optJSONObject("previous_snapshot")
    fun releaseDismissed(version: String): Boolean = version in data.optJSONArray("dismissed_releases").strings()
    fun dismissRelease(version: String) = edit {
        it.put("dismissed_releases", JSONArray((listOf(version.take(80)) + it.optJSONArray("dismissed_releases").strings()).distinct().take(20)))
    }

    fun watch(uid: String, title: String, reason: String) {
        if (uid.isBlank() || reason.isBlank()) return
        watchMany(listOf(uid to title), reason)
    }
    fun watchMany(instruments: List<Pair<String, String>>, reason: String) {
        if (reason.isBlank()) return
        edit { json ->
            val incoming = instruments.filter { it.first.isNotBlank() }.distinctBy { it.first }
            val rows = json.rows("watchlist").filter { row -> row.optString("uid") !in incoming.map { it.first } }
            check(rows.size + incoming.size <= 200) { "В наблюдении уже 200 инструментов. Удалите ненужный перед добавлением." }
            json.put("watchlist", JSONArray(incoming.map { (uid, title) -> JSONObject().put("uid", uid).put("title", title.take(180))
                .put("reason", reason.trim().take(800)).put("created_at", Instant.now().toString()) } + rows))
        }
    }
    fun unwatch(uid: String) = edit { it.put("watchlist", JSONArray(it.rows("watchlist").filter { row -> row.optString("uid") != uid })) }
    fun saveFilter(value: SavedPortfolioFilter) = edit {
        val rows = it.rows("filters").filter { row -> row.optString("id") != value.id }
        check(rows.size < 30) { "Сначала удалите ненужный фильтр." }
        it.put("filters", JSONArray(listOf(JSONObject().put("id", value.id).put("title", value.title.trim().take(100))
            .put("query", value.query.take(300)).put("account_id", value.accountId).put("kind", value.kind)
            .put("sector", value.sector).put("group", value.group).put("order", value.order)
            .put("watched_only", value.watchedOnly).put("exposure_id", value.exposureId)) + rows))
    }
    fun deleteFilter(id: String) = edit { it.put("filters", JSONArray(it.rows("filters").filter { row -> row.optString("id") != id })) }
    fun saveResearch(title: String, instrumentId: String?, start: String?, end: String?, source: String,
        observedAt: String?, note: String, payload: JSONObject) {
        if (title.isBlank()) return
        save(SavedResearch(UUID.randomUUID().toString(), title.trim().take(140), instrumentId, start, end,
            source.take(500), observedAt, Instant.now().toString(), note.take(2000)), payload)
    }
    fun saveDashboardOrder(order: List<String>) = edit { it.put("dashboard_order", JSONArray(order.distinct())) }
    fun recordVisit(snapshot: JSONObject) = edit {
        if (it.text("current_visit") == null) {
            it.put("current_visit", Instant.now().toString())
            it.put("current_snapshot", snapshot)
        }
    }
    fun checkpointVisit(snapshot: JSONObject) = edit {
        it.put("previous_visit", it.text("current_visit"))
        it.put("previous_snapshot", it.optJSONObject("current_snapshot"))
        it.put("current_visit", Instant.now().toString()).put("current_snapshot", snapshot)
    }
}

private object PersonalWorkspaceRevision {
    val revisions = ConcurrentHashMap<String, MutableState<Int>>()
    fun state(user: String) = revisions.getOrPut(user) { mutableIntStateOf(0) }
}

@Composable
fun rememberPersonalWorkspace(): PersonalWorkspaceController {
    val context = LocalContext.current
    val user = LocalWorkspaceSession.current.userId
    val store = remember(context, user) { PersonalWorkspaceStore(context.applicationContext, user) }
    val revision = PersonalWorkspaceRevision.state(user)
    var value by remember(user) { mutableStateOf(JSONObject()) }
    var loaded by remember(user) { mutableStateOf(false) }
    var busy by remember(user) { mutableStateOf(false) }
    var error by remember(user) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(user, revision.value) {
        loaded = false
        try {
            if (user.isNotBlank()) value = store.read()
            loaded = true
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { error = "Не удалось прочитать личные записи. Сохранённые файлы не перезаписаны. Повторите чтение." }
    }
    val edit: ((JSONObject) -> Unit) -> Unit = { transform ->
        scope.launch {
            busy = true; error = null
            try { value = store.change(transform); revision.value++ }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: IllegalStateException) { error = failure.message ?: "Не удалось сохранить изменения." }
            catch (_: Exception) { error = "Не удалось сохранить изменения. Повторите ещё раз." }
            finally { busy = false }
        }
    }
    return PersonalWorkspaceController(value, loaded, busy, error, edit, { entry, payload ->
        scope.launch {
            busy = true; error = null
            try {
                check(store.saveArchive(entry.id, payload))
                value = store.change { json ->
                    val previous = json.rows("research")
                    check(previous.size < 40) { "Сначала удалите ненужное исследование." }
                    val meta = JSONObject().put("id", entry.id).put("title", entry.title).put("instrument_id", entry.instrumentId)
                        .put("start", entry.start).put("end", entry.end).put("source", entry.source)
                        .put("observed_at", entry.observedAt).put("captured_at", entry.capturedAt).put("note", entry.note)
                    json.put("research", JSONArray(listOf(meta) + previous))
                }
                revision.value++
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { store.deleteArchive(entry.id); error = "Исследование не сохранено. Проверьте лимит 40 записей и повторите ещё раз." }
            finally { busy = false }
        }
    }, { id ->
        scope.launch {
            busy = true; error = null
            try {
                value = store.change { it.put("research", JSONArray(it.rows("research").filter { row -> row.optString("id") != id })) }
                check(store.deleteArchive(id)); revision.value++
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { error = "Не удалось удалить исследование." }
            finally { busy = false }
        }
    }, store, { error = null; revision.value++ })
}

internal fun JSONObject.rows(key: String): List<JSONObject> = optJSONArray(key)?.let { array ->
    (0 until array.length()).mapNotNull(array::optJSONObject)
} ?: emptyList()
internal fun JSONObject.text(key: String): String? = (opt(key) as? String)?.takeIf(String::isNotBlank)
private fun JSONArray?.strings(): List<String> = this?.let { a -> (0 until a.length()).mapNotNull { a.opt(it) as? String } } ?: emptyList()
