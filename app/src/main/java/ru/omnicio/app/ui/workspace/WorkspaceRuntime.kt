package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.time.LocalDate
import java.util.UUID
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient

val LocalWorkspaceRefreshKey = staticCompositionLocalOf { 0 }
val LocalWorkspaceSnapshot = staticCompositionLocalOf<JSONObject?> { null }
val LocalWorkspaceRefresh = staticCompositionLocalOf<() -> Unit> { {} }
val LocalWorkspaceInvalidate = staticCompositionLocalOf<() -> Unit> { {} }

data class WorkspaceRuntime(val data: JSONObject?, val revision: Int, val busy: Boolean,
    val error: String?, val jobId: String?, val refresh: () -> Unit, val invalidate: () -> Unit)

/** Materialization is a deterministic data job, independent of animation and paid chat. */
@Composable
fun rememberWorkspaceRuntime(session: WorkspaceSession, connected: Boolean, currency: PortfolioCurrency,
    onExpired: () -> Unit): WorkspaceRuntime {
    val client = remember { VolumeWorkspaceClient() }
    val expired by rememberUpdatedState(onExpired)
    val foreground = workspaceForeground()
    var data by remember(session.userId, session.token, currency) { mutableStateOf<JSONObject?>(null) }
    var revision by remember(session.userId) { mutableIntStateOf(0) }
    var requested by remember(session.userId) { mutableIntStateOf(0) }
    var handled by remember(session.userId) { mutableIntStateOf(0) }
    var readRequested by remember(session.userId) { mutableIntStateOf(0) }
    var busy by remember(session.userId) { mutableStateOf(false) }
    var error by remember(session.userId) { mutableStateOf<String?>(null) }
    var jobId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var jobCurrency by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var attemptedCurrency by remember(session.userId) { mutableStateOf<String?>(null) }
    LaunchedEffect(session.token, foreground, requested, connected, currency, readRequested) {
        if (!foreground || session.token.isBlank()) return@LaunchedEffect
        busy = true
        try {
            val initial = withContext(Dispatchers.IO) { client.request(session.token, "/workspace?currency=" + currency.name) }
            if (initial.signedOut) { expired(); return@LaunchedEffect }
            initial.data?.let { if (data?.toString() != it.toString()) revision++; data = it }
            error = initial.error
            val needsRefresh = requested > handled || attemptedCurrency != currency.name && data?.isNull("snapshot_id") != false
            if (connected && needsRefresh && jobId == null) {
                attemptedCurrency = currency.name; handled = requested
                val today = LocalDate.now(java.time.ZoneId.of("Europe/Moscow"))
                val body = JSONObject().put("request_id", UUID.randomUUID().toString()).put("currency", currency.name)
                    .put("start", today.minusMonths(1).toString()).put("end", today.toString())
                val reply = withContext(Dispatchers.IO) { client.request(session.token, "/workspace/refresh", "POST", body) }
                if (reply.signedOut) { expired(); return@LaunchedEffect }
                jobId = reply.data?.optString("job_id")?.takeIf { it.isNotBlank() }
                jobCurrency = currency.name
                error = reply.error
            }
            val activeId = jobId
            if (activeId != null) {
                while (isActive) {
                    val reply = withContext(Dispatchers.IO) { client.request(session.token, "/workspace/jobs/${VolumeWorkspaceClient.encode(activeId)}") }
                    if (reply.signedOut) { expired(); return@LaunchedEffect }
                    if (reply.error != null) { error = reply.error; break }
                    val state = reply.data?.optString("state")
                    if (state in setOf("completed", "failed", "cancelled", "uncertain")) {
                        jobId = null
                        if (state == "completed") {
                            val latest = withContext(Dispatchers.IO) { client.request(session.token, "/workspace?currency=" + currency.name) }
                            latest.data?.let { data = it; revision++ }
                            error = latest.error
                            if (jobCurrency != currency.name && latest.data?.isNull("snapshot_id") != false) {
                                attemptedCurrency = null; requested++
                            }
                        } else error = "Сбор дополнительных данных завершился без нового снимка. Основной портфель доступен отдельно."
                        break
                    }
                    delay(1_500)
                }
            }
        } finally { busy = false }
    }
    return WorkspaceRuntime(data, revision, busy, error, jobId, { if (!busy) requested++ }, { readRequested++ })
}
