package ru.omnicio.app.data.workspace

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject

data class JobCheckpointPreparation(val persisted: Boolean, val isNew: Boolean = false)

/** Multiple unresolved requests survive navigation, process death and an APK update. */
class JobCheckpointStore(context: Context) {
    private val storage = EncryptedWorkspaceStore(context)

    /** Preparing a second chat cannot bypass an unresolved first dispatch, even after a remount. */
    fun prepare(userId: String, requestId: String, path: String, requestBody: JSONObject?): JobCheckpointPreparation = synchronized(lock) {
        runCatching {
            val prior = list(userId)
            val existing = prior.firstOrNull { it.optString("request_id") == requestId }
            if (existing == null && isChatPath(path) && prior.any(::isUnconfirmedChat)) {
                return@synchronized JobCheckpointPreparation(false)
            }
            JobCheckpointPreparation(write(userId, requestId, path, null, requestBody, prior), existing == null)
        }.getOrDefault(JobCheckpointPreparation(false))
    }

    /** An acknowledgement may add the job ID; it must retain the exact originally persisted body. */
    fun save(userId: String, requestId: String, path: String, jobId: String? = null,
        requestBody: JSONObject? = null): Boolean = synchronized(lock) {
        runCatching { write(userId, requestId, path, jobId, requestBody, list(userId)) }.getOrDefault(false)
    }

    private fun write(userId: String, requestId: String, path: String, jobId: String?, requestBody: JSONObject?,
        prior: List<JSONObject>): Boolean {
        if (requestId.isBlank() || !path.startsWith("/workspace/")) return false
        val previous = prior.firstOrNull { it.optString("request_id") == requestId }
        val previousBody = previous?.optJSONObject("request_body")
        val previousJob = previous?.optString("job_id")?.takeIf { it.isNotBlank() && it != "null" }
        if (previous != null && previous.optString("path") != path) return false
        if (requestBody != null && requestBody.optString("request_id") != requestId) return false
        if (previous != null && requestBody != null && previousBody?.toString() != requestBody.toString()) return false
        if (previousJob != null && jobId != null && previousJob != jobId) return false
        val others = prior.filterNot { it.optString("request_id") == requestId }
        if (others.size >= 40) return false
        val savedJob: Any = (jobId ?: previousJob).let { it ?: JSONObject.NULL }
        val checkpoint = JSONObject().put("request_id", requestId).put("path", path)
            .put("job_id", savedJob)
            .put("created_at", previous?.optString("created_at") ?: java.time.Instant.now().toString())
        (previousBody ?: requestBody)?.let { checkpoint.put("request_body", JSONObject(it.toString())) }
        return persist(userId, listOf(checkpoint) + others)
    }

    fun list(userId: String): List<JSONObject> = synchronized(lock) {
        val current = read(userId, "job_checkpoints")
        if (current != null) {
            val items = checkNotNull(current.optJSONArray("items")) { "Saved requests cannot be read" }
            (0 until items.length()).map { checkNotNull(items.optJSONObject(it)) { "Saved request cannot be read" } }
        } else listOfNotNull(read(userId, "job_checkpoint"))
    }

    fun removeRequest(userId: String, requestId: String): Boolean = synchronized(lock) {
        runCatching { persist(userId, list(userId).filterNot { it.optString("request_id") == requestId }) }.getOrDefault(false)
    }

    fun removeJob(userId: String, jobId: String): Boolean = synchronized(lock) {
        runCatching { persist(userId, list(userId).filterNot { it.optString("job_id") == jobId }) }.getOrDefault(false)
    }

    private fun read(userId: String, key: String): JSONObject? {
        val result = storage.readJson(userId, key)
        check(result != null || !storage.hasEntry(userId, key)) { "Saved requests cannot be decrypted" }
        return result
    }

    private fun persist(userId: String, pending: List<JSONObject>): Boolean {
        val saved = storage.saveJson(userId, "job_checkpoints", JSONObject().put("items", JSONArray(pending)))
        if (saved) {
            storage.remove(userId, "job_checkpoint")
            mutableRevision.value += 1
        }
        return saved
    }

    companion object {
        private val lock = Any()
        private val mutableRevision = MutableStateFlow(0L)
        val revision: StateFlow<Long> = mutableRevision.asStateFlow()
        private val chatPath = Regex("/workspace/chat/threads/([^/]+)/messages")
        fun isChatPath(path: String): Boolean = chatPath.matches(path)
        fun isUnconfirmedChat(point: JSONObject): Boolean = isChatPath(point.optString("path")) &&
            (point.isNull("job_id") || point.optString("job_id").isBlank())
    }
}
