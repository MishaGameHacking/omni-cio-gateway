package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import ru.omnicio.app.data.workspace.WorkspaceTransport
import org.json.JSONObject
import java.security.MessageDigest
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.withContext

enum class AccentStyle(val title: String) { AURORA("Аврора"), OCEAN("Океан"), IRIS("Ирис") }
enum class InterfaceDensity(val title: String) { COMFORT("Свободно"), COMPACT("Компактно") }
enum class MotionLevel(val title: String) { LIVE("Живое"), SUBDUED("Сдержанное"), OFF("Без движения") }

/** Presentation values are acknowledged by the server, with a local offline cache. */
data class WorkspacePreferences(
    val accent: AccentStyle = AccentStyle.AURORA,
    val density: InterfaceDensity = InterfaceDensity.COMFORT,
    val depth: Boolean = true,
    val hideHomeBalance: Boolean = false,
    val homeStructure: Boolean = true,
    val haptics: Boolean = true,
    val motion: MotionLevel = MotionLevel.LIVE,
    val brightLight: Boolean = false,
    val screenshotsBlocked: Boolean = false,
)

data class WorkspacePreferenceController(
    val value: WorkspacePreferences = WorkspacePreferences(),
    val preview: (WorkspacePreferences) -> Unit = {},
    val cancelPreview: () -> Unit = {},
    val applyPreview: () -> Unit = {},
    val update: (WorkspacePreferences) -> Unit = {},
    val saveStatus: String = "Сохранено на устройстве",
    val saveFailed: Boolean = false,
    val retrySave: () -> Unit = {},
    val refreshRemote: () -> Unit = {},
)

val LocalWorkspacePreferences = staticCompositionLocalOf { WorkspacePreferenceController() }

private fun legacySettings(context: android.content.Context): WorkspacePreferences {
    val store = context.getSharedPreferences("workspace_appearance", 0)
    return WorkspacePreferences(
        accent = AccentStyle.entries.firstOrNull { it.name == store.getString("accent", null) } ?: AccentStyle.AURORA,
        density = InterfaceDensity.entries.firstOrNull { it.name == store.getString("density", null) } ?: InterfaceDensity.COMFORT,
        depth = store.getBoolean("depth", true), hideHomeBalance = store.getBoolean("hide_home_balance", false),
        homeStructure = store.getBoolean("home_structure", true), haptics = store.getBoolean("haptics", true),
        motion = MotionLevel.entries.firstOrNull { it.name == store.getString("motion", null) } ?: MotionLevel.LIVE,
        brightLight = store.getBoolean("bright_light", false),
        screenshotsBlocked = context.getSharedPreferences("analyst_ai_settings", 0).getBoolean("screenshots_blocked", false))
}

private class PresentationState(
    initial: WorkspacePreferences,
    cachedPending: JSONObject,
    wasInitialized: Boolean,
    private val legacy: WorkspacePreferences?,
    private val persist: suspend (WorkspacePreferences, JSONObject, Boolean) -> Boolean,
) {
    var value by mutableStateOf(initial)
    var preview by mutableStateOf<WorkspacePreferences?>(null)
    var pending = cachedPending
    var initialized = wasInitialized
    var revision = 0L
    var status by mutableStateOf("Проверяем настройки на сервере…")
    var failed by mutableStateOf(false)

    fun edit(next: WorkspacePreferences) {
        pending = mergeSettings(pending, settingsDifference(value.toSettings(), next.toSettings()))
        value = next; preview = null; revision++
        status = "Сохраняем на сервере…"; failed = false
    }

    fun fail(message: String) { failed = true; status = message }

    private suspend fun cache(): Boolean =
        persist(value, JSONObject(pending.toString()), initialized)

    private fun receive(remote: PresentationSnapshot) {
        if (!initialized) {
            if (remote.version == 0L && legacy != null) pending = mergeSettings(
                settingsDifference(remote.value.toSettings(), legacy.toSettings()), pending)
            initialized = true
        }
        val merged = mergeSettings(remote.value.toSettings(), pending)
        pending = settingsDifference(remote.value.toSettings(), merged)
        value = requireNotNull(presentationSettings(merged))
    }

    private suspend fun cacheBeforeWrite(): Boolean {
        if (cache()) return true
        fail("Не удалось сохранить изменения на устройстве. Повторяем позже.")
        return false
    }

    private suspend fun send(client: WorkspaceTransport, token: String, version: Long, expired: () -> Unit): Boolean {
        val sent = JSONObject(pending.toString())
        val reply = withContext(Dispatchers.IO) {
            client.request(token, "/workspace/presentation", "PUT",
                JSONObject().put("expected_version", version).put("changes", sent))
        }
        currentCoroutineContext().ensureActive()
        if (reply.signedOut) { expired(); return false }
        val confirmed = PresentationSnapshot.parse(reply.data)
        if (confirmed == null || sent.keys().asSequence().any { confirmed.value.toSettings().opt(it) != sent.get(it) }) {
            fail("Сервер не подтвердил изменения. Они сохранены для повторной отправки.")
            return false
        }
        pending = acknowledgeSettings(pending, sent)
        value = requireNotNull(presentationSettings(mergeSettings(confirmed.value.toSettings(), pending)))
        return true
    }

    suspend fun synchronize(client: WorkspaceTransport, token: String, expired: () -> Unit) {
        if (!cacheBeforeWrite()) return
        val reply = withContext(Dispatchers.IO) { client.request(token, "/workspace/presentation") }
        currentCoroutineContext().ensureActive()
        if (reply.signedOut) { expired(); return }
        val remote = PresentationSnapshot.parse(reply.data)
        if (remote == null) {
            fail("Нет подтверждения сервера. Показаны сохранённые настройки.")
            return
        }
        receive(remote)
        if (!cacheBeforeWrite()) return
        if (pending.length() != 0 && !send(client, token, remote.version, expired)) return
        val savedRevision = revision
        val cached = cache()
        if (savedRevision != revision) return
        failed = !cached
        status = when {
            !cached -> "Настройки на сервере; не удалось обновить локальную копию."
            pending.length() != 0 -> "Сохраняем новые изменения на сервере…"
            else -> "Сохранено на сервере"
        }
    }
}

@Composable
fun WorkspacePreferencesProvider(content: @Composable () -> Unit) {
    val context = LocalContext.current.applicationContext
    val session = LocalWorkspaceSession.current
    val client = LocalWorkspaceTransport.current
    val reauthenticate by rememberUpdatedState(LocalReauthenticate.current)
    val foreground = workspaceForeground()
    val owner = remember(session.userId) {
        MessageDigest.getInstance("SHA-256").digest(session.userId.toByteArray()).joinToString("") { "%02x".format(it) }
    }
    val state = remember(owner) {
        val store = context.getSharedPreferences("server_presentation_" + owner, 0)
        val migration = context.getSharedPreferences("presentation_migration", 0)
        val priorOwner = migration.getString("owner", null)
        val legacy = if (priorOwner == null || priorOwner == owner) legacySettings(context) else null
        val cached = runCatching { JSONObject(store.getString("value", "{}") ?: "{}") }.getOrNull()
        PresentationState(presentationSettings(cached) ?: legacy ?: WorkspacePreferences(),
            restoredSettingsPatch(store.getString("pending", "{}")), store.getBoolean("initialized", false), legacy,
            persist = { value, pending, initialized ->
                withContext(Dispatchers.IO) { runCatching {
                    val saved = store.edit().putString("value", value.toSettings().toString())
                        .putString("pending", pending.toString()).putBoolean("initialized", initialized).commit()
                    if (initialized && migration.getString("owner", null) == null)
                        migration.edit().putString("owner", owner).commit()
                    saved
                }.getOrDefault(false) }
            })
    }
    val events = remember(owner) { Channel<Unit>(Channel.CONFLATED) }
    LaunchedEffect(owner, foreground) {
        if (foreground) while (isActive) { events.trySend(Unit); delay(20_000) }
    }
    LaunchedEffect(owner, session.token, foreground) {
        if (!foreground || session.token.isBlank()) return@LaunchedEffect
        events.trySend(Unit)
        for (ignored in events) {
            state.synchronize(client, session.token, reauthenticate)
            if (state.pending.length() != 0 && !state.failed) events.trySend(Unit)
        }
    }
    val save: (WorkspacePreferences) -> Unit = { next -> state.edit(next); events.trySend(Unit) }
    val controller = WorkspacePreferenceController(value = state.preview ?: state.value,
        preview = { state.preview = it }, cancelPreview = { state.preview = null },
        applyPreview = { state.preview?.let(save) }, update = save, saveStatus = state.status, saveFailed = state.failed,
        retrySave = { events.trySend(Unit) }, refreshRemote = { events.trySend(Unit) })
    CompositionLocalProvider(LocalWorkspacePreferences provides controller, content = content)
}
