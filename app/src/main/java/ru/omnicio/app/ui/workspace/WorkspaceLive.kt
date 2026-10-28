package ru.omnicio.app.ui.workspace

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.workspace.LiveCursor
import ru.omnicio.app.data.workspace.WorkspaceLiveClient
import ru.omnicio.app.data.workspace.liveRetryDelay
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

enum class LiveSyncStatus { Connecting, Online, Reconnecting, Offline, Paused }
data class WorkspaceLiveSync(val revision: Int, val status: LiveSyncStatus, val receivedAtMillis: Long?)
val LocalWorkspaceLiveSync = staticCompositionLocalOf<WorkspaceLiveSync?> { null }

/** One foreground subscription per session. A notification only rereads data; it never posts a job. */
@Composable
fun rememberWorkspaceLiveSync(session: WorkspaceSession, onChanged: () -> Unit,
    onBrokerChanged: (Boolean) -> Unit, onExpired: () -> Unit): WorkspaceLiveSync {
    val foreground = workspaceForeground()
    val client = remember(session.userId, session.token) { WorkspaceLiveClient() }
    val cursor = remember(session.userId, session.token) { LiveCursor() }
    val changed by rememberUpdatedState(onChanged)
    val brokerChanged by rememberUpdatedState(onBrokerChanged)
    val expired by rememberUpdatedState(onExpired)
    var revision by remember(session.userId, session.token) { mutableIntStateOf(0) }
    var status by remember(session.userId, session.token) { mutableStateOf(LiveSyncStatus.Connecting) }
    var received by remember(session.userId, session.token) { mutableStateOf<Long?>(null) }
    DisposableEffect(client, foreground) {
        if (!foreground) client.cancel()
        onDispose { client.cancel() }
    }
    LaunchedEffect(client, foreground) {
        if (!foreground || session.token.isBlank()) {
            status = LiveSyncStatus.Paused
            return@LaunchedEffect
        }
        status = LiveSyncStatus.Connecting
        var failures = 0
        while (isActive) {
            val reply = withContext(Dispatchers.IO) { client.poll(session.token, cursor.revision) }
            currentCoroutineContext().ensureActive()
            if (reply.status == 401 || reply.status == 403) { expired(); return@LaunchedEffect }
            val event = reply.change
            if (event != null) {
                failures = 0
                status = LiveSyncStatus.Online
                received = System.currentTimeMillis()
                val decision = cursor.accept(event)
                if (decision.changed) { revision++; changed() }
                if (decision.brokerChanged) brokerChanged(event.brokerConnected)
                // Coalesce bursts and protect both the API and the current editor.
                delay(1_000)
            } else {
                failures++
                status = if (failures < 3) LiveSyncStatus.Reconnecting else LiveSyncStatus.Offline
                delay(maxOf(liveRetryDelay(failures), reply.retryAfterMillis))
            }
        }
    }
    return WorkspaceLiveSync(revision, status, received)
}

@Composable
fun LiveSyncLabel(modifier: Modifier = Modifier) {
    val state = LocalWorkspaceLiveSync.current ?: return
    val label = when (state.status) {
        LiveSyncStatus.Online -> "Онлайн"
        LiveSyncStatus.Connecting -> "Подключаемся…"
        LiveSyncStatus.Reconnecting -> "Восстанавливаем связь…"
        LiveSyncStatus.Offline -> "Нет связи · показаны сохранённые данные"
        LiveSyncStatus.Paused -> return
    }
    Text(label, modifier.semantics { liveRegion = LiveRegionMode.Polite },
        style = MaterialTheme.typography.labelSmall,
        color = if (state.status == LiveSyncStatus.Online) LocalSpectrumPalette.current.emerald
            else MaterialTheme.colorScheme.onSurfaceVariant)
}
