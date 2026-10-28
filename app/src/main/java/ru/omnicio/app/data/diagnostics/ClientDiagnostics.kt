package ru.omnicio.app.data.diagnostics

import android.app.ActivityManager
import android.content.Context
import android.os.Build
import android.os.Process
import android.util.AtomicFile
import java.io.File
import java.net.URI
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.locks.ReentrantLock
import kotlin.system.exitProcess
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.SessionExpiry
import ru.omnicio.app.data.updates.ClientVersion

/**
 * Private bounded observations, uploaded only after authentication.
 * Never suppresses the platform crash handler and never performs network work
 * while a process is crashing. No broker/token/message/raw trace is collected.
 */
object ClientDiagnostics {
    private const val MAX_FILE_BYTES = 96 * 1024
    private const val MAX_RECORD_BYTES = 4096
    private const val MAX_QUEUE = 16
    private const val MAX_SEEN = 128
    private const val RETENTION_MS = 30L * 24 * 60 * 60 * 1000
    private val installed = AtomicBoolean(false)
    private val uploading = AtomicBoolean(false)
    private val lock = ReentrantLock()
    private val eventIdPattern = Regex("[0-9a-f]{64}")
    @Volatile private var context: Context? = null
    @Volatile private var file: AtomicFile? = null
    @Volatile private var currentStage = DiagnosticStage.UNKNOWN

    fun install(application: Context) {
        if (!installed.compareAndSet(false, true)) return
        context = application.applicationContext
        try {
            file = AtomicFile(File(application.noBackupFilesDir, "client-diagnostics-v1.json"))
            val previous = Thread.getDefaultUncaughtExceptionHandler()
            Thread.setDefaultUncaughtExceptionHandler { thread, error ->
                try {
                    val frames = JSONArray()
                    for (frame in CrashReportSanitizer.frames(error)) {
                        frames.put(JSONObject().put("class", frame.className)
                            .put("method", frame.method).put("line", frame.line))
                    }
                    enqueue(baseEvent("uncaught_exception", System.currentTimeMillis(),
                        digest("jvm|" + UUID.randomUUID())).put("process_version", BuildConfig.VERSION_CODE)
                        .put("reason", JSONObject.NULL).put("status", JSONObject.NULL)
                        .put("stage", currentStage.wire)
                        .put("exception_code", CrashReportSanitizer.exceptionCode(error))
                        .put("frames", frames))
                } catch (_: Throwable) {
                    // Diagnostics cannot replace the original exception, even on OOM.
                } finally {
                    if (previous != null) previous.uncaughtException(thread, error)
                    else {
                        Process.killProcess(Process.myPid())
                        exitProcess(10)
                    }
                }
            }
            stage(DiagnosticStage.PROCESS_START)
            Thread({ collectHistorical() }, "client-exit-diagnostics").apply {
                isDaemon = true
                start()
            }
        } catch (_: Exception) {
            // Optional diagnostics must not prevent normal application startup.
        }
    }

    /** Call only on meaningful stage transitions, never per frame/recomposition. */
    fun stage(next: DiagnosticStage) {
        if (currentStage == next) return
        currentStage = next
        val app = context ?: return
        runCatching {
            app.getSystemService(ActivityManager::class.java)
                ?.setProcessStateSummary(CrashReportSanitizer.encodeState(BuildConfig.VERSION_CODE, next))
        }
    }

    private fun baseEvent(kind: String, timestamp: Long, id: String): JSONObject =
        JSONObject().put("event_id", id).put("kind", kind).put("timestamp_ms", timestamp)
            .put("capture_version", BuildConfig.VERSION_CODE).put("capture_api", Build.VERSION.SDK_INT)

    private fun collectHistorical() {
        val app = context ?: return
        runCatching {
            val manager = app.getSystemService(ActivityManager::class.java) ?: return@runCatching
            val now = System.currentTimeMillis()
            for (exit in manager.getHistoricalProcessExitReasons(app.packageName, 0, 8)) {
                if (exit.processName != app.packageName ||
                    exit.timestamp !in (now - RETENTION_MS)..(now + 86_400_000L)) continue
                val state = CrashReportSanitizer.decodeState(exit.processStateSummary)
                val id = digest("exit|" + app.packageName + "|" + exit.timestamp + "|" +
                    exit.pid + "|" + exit.reason + "|" + exit.status)
                enqueue(baseEvent("historical_exit", exit.timestamp, id)
                    .put("process_version", state.version ?: JSONObject.NULL)
                    .put("reason", exit.reason).put("status", exit.status)
                    .put("stage", state.stage.wire).put("exception_code", JSONObject.NULL)
                    .put("frames", JSONArray()))
                // No description or traceInputStream: native traces are protobuf,
                // arbitrary raw traces can contain private application values.
            }
        }
    }

    private fun digest(value: String): String =
        MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it.toInt() and 255) }

    private fun emptyState(): JSONObject = JSONObject().put("schema_version", 1)
        .put("pending", JSONArray()).put("seen", JSONArray())

    private fun readState(storage: AtomicFile): JSONObject = runCatching {
        val bytes = storage.openRead().use { it.readNBytes(MAX_FILE_BYTES + 1) }
        require(bytes.size <= MAX_FILE_BYTES)
        JSONObject(bytes.toString(Charsets.UTF_8)).also {
            require(it.optInt("schema_version") == 1)
            require((it.optJSONArray("pending")?.length() ?: Int.MAX_VALUE) <= MAX_QUEUE)
            require((it.optJSONArray("seen")?.length() ?: Int.MAX_VALUE) <= MAX_SEEN)
        }
    }.getOrElse { emptyState() }

    private fun writeState(storage: AtomicFile, state: JSONObject) {
        val bytes = state.toString().toByteArray(Charsets.UTF_8)
        require(bytes.size <= MAX_FILE_BYTES)
        val stream = storage.startWrite()
        try {
            stream.write(bytes)
            storage.finishWrite(stream)
        } catch (error: Throwable) {
            storage.failWrite(stream)
            throw error
        }
    }

    private fun <T> locked(fallback: T, action: (AtomicFile) -> T): T {
        if (!lock.tryLock(25, TimeUnit.MILLISECONDS)) return fallback
        try {
            val storage = file ?: return fallback
            return action(storage)
        } finally { lock.unlock() }
    }

    private fun pending(state: JSONObject): List<JSONObject> {
        val array = state.optJSONArray("pending") ?: return emptyList()
        val now = System.currentTimeMillis()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it) }.filter {
            it.optLong("timestamp_ms") in (now - RETENTION_MS)..(now + 86_400_000L) &&
                eventIdPattern.matches(it.optString("event_id"))
        }
    }

    private fun enqueue(event: JSONObject) {
        if (event.toString().toByteArray(Charsets.UTF_8).size > MAX_RECORD_BYTES) return
        locked(Unit) { storage ->
            val state = readState(storage)
            val array = state.optJSONArray("seen") ?: JSONArray()
            val seen = (0 until array.length()).map { array.optString(it) }
                .filter { eventIdPattern.matches(it) }.toMutableList()
            val id = event.getString("event_id")
            if (id !in seen) {
                seen.add(id)
                state.put("seen", JSONArray(seen.takeLast(MAX_SEEN)))
                    .put("pending", JSONArray((pending(state) + event).takeLast(MAX_QUEUE)))
                writeState(storage, state)
            }
        }
    }

    /**
     * Blocking bounded IO. Invoke from Dispatchers.IO after real authentication.
     * Returns false on any transport/storage failure; never reports successful
     * delivery unless every returned ID belongs to the exact submitted batch.
     */
    fun uploadPending(application: Context, accessToken: String): Boolean {
        if (accessToken.isBlank() || !uploading.compareAndSet(false, true)) return false
        try {
            val auth = AuthSessionStore(application)
            if (auth.loadAccessToken() != accessToken) return false
            collectHistorical()
            repeat(4) {
                if (auth.loadAccessToken() != accessToken) return false
                val batch = locked(emptyList<JSONObject>()) { pending(readState(it)).take(4) }
                if (batch.isEmpty()) return true
                val bytes = JSONObject().put("schema_version", 1).put("events", JSONArray(batch))
                    .toString().toByteArray(Charsets.UTF_8)
                if (bytes.size > 32 * 1024) return false
                val expected = batch.map { it.getString("event_id") }.toSet()
                val connection = BackendConfig.openConnection(URI(BackendConfig.BASE_URL + "/client/diagnostics"))
                val accepted = try {
                    connection.requestMethod = "POST"
                    connection.connectTimeout = 3000
                    connection.readTimeout = 5000
                    connection.doOutput = true
                    connection.setFixedLengthStreamingMode(bytes.size)
                    ClientVersion.attach(connection)
                    connection.setRequestProperty("Authorization", "Bearer " + accessToken)
                    connection.setRequestProperty("Content-Type", "application/json")
                    connection.setRequestProperty("Accept", "application/json")
                    connection.outputStream.use { it.write(bytes) }
                    val status = connection.responseCode
                    ClientVersion.observeStatus(status)
                    SessionExpiry.observe(status, accessToken)
                    if (status !in 200..299) return false
                    val body = connection.inputStream.use { it.readNBytes(8193) }
                    if (body.size > 8192) return false
                    val ids = JSONObject(body.toString(Charsets.UTF_8)).getJSONArray("accepted_ids")
                    if (ids.length() != expected.size) return false
                    (0 until ids.length()).map { ids.getString(it) }.toSet()
                } finally { connection.disconnect() }
                if (accepted != expected || auth.loadAccessToken() != accessToken) return false
                if (!locked(false) { storage ->
                    val state = readState(storage)
                    state.put("pending", JSONArray(pending(state).filter {
                        it.getString("event_id") !in accepted
                    }))
                    writeState(storage, state)
                    true
                }) return false
            }
            return true
        } catch (_: Exception) {
            return false
        } finally { uploading.set(false) }
    }
}
