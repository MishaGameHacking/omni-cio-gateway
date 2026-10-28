package ru.omnicio.app.data.workspace

import java.net.URI
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.SessionExpiry
import ru.omnicio.app.data.updates.ClientVersion

private val liveRevisionPattern = Regex("[a-f0-9]{64}")

data class LiveChange(val revision: String, val brokerRevision: String, val brokerConnected: Boolean) {
    init {
        require(revision.matches(liveRevisionPattern))
        require(brokerRevision.matches(liveRevisionPattern))
    }
}
data class LivePoll(val change: LiveChange? = null, val status: Int = 0, val retryAfterMillis: Long = 0)
data class LiveDecision(val changed: Boolean, val brokerChanged: Boolean)

/** A cursor is scoped to one signed-in session and survives only reconnects. */
class LiveCursor {
    var revision: String? = null
        private set
    private var brokerRevision: String? = null
    fun accept(change: LiveChange): LiveDecision {
        val result = LiveDecision(revision != change.revision, brokerRevision != change.brokerRevision)
        revision = change.revision
        brokerRevision = change.brokerRevision
        return result
    }
}
fun liveRetryDelay(failures: Int): Long =
    (1_000L shl (failures - 1).coerceIn(0, 5)).coerceAtMost(30_000L)

/** Read-only authenticated long poll, using the same pinned origin policy as other API calls. */
class WorkspaceLiveClient(private val baseUrl: String = BackendConfig.BASE_URL) {
    private val generation = AtomicInteger()
    private val active = AtomicReference<HttpsURLConnection?>()

    fun cancel() {
        generation.incrementAndGet()
        runCatching { active.getAndSet(null)?.disconnect() }
    }

    fun poll(token: String, after: String?): LivePoll {
        require(after == null || after.matches(liveRevisionPattern))
        val started = generation.get()
        var connection: HttpsURLConnection? = null
        return try {
            val path = "/workspace/live?wait=20" + (after?.let { "&after=" + it } ?: "")
            connection = BackendConfig.openConnection(URI(baseUrl + path))
            active.getAndSet(connection)?.disconnect()
            if (started != generation.get()) return LivePoll()
            connection.instanceFollowRedirects = false
            connection.requestMethod = "GET"
            connection.connectTimeout = 8_000
            connection.readTimeout = 25_000
            connection.setRequestProperty("Authorization", "Bearer " + token)
            connection.setRequestProperty("Accept", "application/json")
            ClientVersion.attach(connection)
            val status = connection.responseCode
            ClientVersion.observeStatus(status)
            SessionExpiry.observe(status, token)
            if (status != 200) {
                val retry = connection.getHeaderField("Retry-After")?.toLongOrNull()
                    ?.coerceIn(1, 60)?.times(1_000) ?: 0
                return LivePoll(status = status, retryAfterMillis = retry)
            }
            if (connection.contentType?.substringBefore(';')?.trim() != "application/json") return LivePoll(status = 502)
            val bytes = connection.inputStream.use { it.readNBytes(8_193) }
            if (bytes.size > 8_192 || started != generation.get()) return LivePoll()
            val value = JSONObject(String(bytes, Charsets.UTF_8))
            val revision = value.opt("revision") as? String ?: return LivePoll(status = 502)
            val broker = value.opt("broker_revision") as? String ?: return LivePoll(status = 502)
            val connected = value.opt("broker_connected") as? Boolean ?: return LivePoll(status = 502)
            LivePoll(LiveChange(revision, broker, connected), status)
        } catch (_: Exception) {
            LivePoll()
        } finally {
            active.compareAndSet(connection, null)
            connection?.disconnect()
        }
    }
}
