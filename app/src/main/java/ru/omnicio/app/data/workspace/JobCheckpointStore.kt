package ru.omnicio.app.data.workspace

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Multiple unresolved requests survive navigation, process death and an APK update. */
class JobCheckpointStore(context: Context) {
    private val storage = EncryptedWorkspaceStore(context)
    fun save(userId: String, requestId: String, path: String, jobId: String? = null): Boolean = synchronized(lock) {
        val prior = list(userId)
        val existing = prior.filterNot { it.optString("request_id") == requestId }
        if (existing.size >= 40) return false
        val checkpoint = JSONObject().put("request_id", requestId).put("path", path)
            .put("job_id", jobId ?: JSONObject.NULL).put("created_at", prior.firstOrNull { it.optString("request_id") == requestId }?.optString("created_at") ?: java.time.Instant.now().toString())
        storage.saveJson(userId, "job_checkpoints", JSONObject().put("items", JSONArray(listOf(checkpoint) + existing)))
    }
    fun list(userId: String): List<JSONObject> = synchronized(lock) {
        val items = storage.readJson(userId, "job_checkpoints")?.optJSONArray("items")
        if (items != null) (0 until items.length()).mapNotNull { items.optJSONObject(it) }
        else listOfNotNull(storage.readJson(userId, "job_checkpoint"))
    }
    fun removeJob(userId: String, jobId: String) = synchronized(lock) {
        val pending = list(userId).filterNot { it.optString("job_id") == jobId }
        storage.saveJson(userId, "job_checkpoints", JSONObject().put("items", JSONArray(pending)))
        storage.remove(userId, "job_checkpoint")
    }
    companion object { private val lock = Any() }
}
