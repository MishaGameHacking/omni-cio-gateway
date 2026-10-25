package ru.omnicio.app.data.notifications

import android.Manifest
import android.app.*
import android.app.job.JobInfo
import android.app.job.JobParameters
import android.app.job.JobScheduler
import android.app.job.JobService
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import kotlinx.coroutines.*
import org.json.JSONObject
import ru.omnicio.app.MainActivity
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient

/** System-scheduled polling, not push delivery. No renderer, model call, exact alarm or order API. */
class WorkspaceNotificationService : JobService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var work: Job? = null
    override fun onStartJob(params: JobParameters): Boolean {
        if (!canNotify(this)) return false
        work = scope.launch {
            try { deliver() }
            finally { if (isActive) withContext(Dispatchers.Main) { jobFinished(params, false) } }
        }
        return true
    }
    override fun onStopJob(params: JobParameters): Boolean { work?.cancel(); work = null; return true }
    override fun onDestroy() { scope.cancel(); super.onDestroy() }

    private suspend fun deliver() {
        val auth = AuthSessionStore(this)
        val token = auth.loadAccessToken() ?: return
        val userId = auth.loadCachedUser()?.telegramId ?: return
        val client = VolumeWorkspaceClient()
        val preferences = client.request(token, "/workspace/notifications/preferences")
        if (preferences.signedOut) { cancel(this); return }
        if (preferences.data?.optJSONObject("preferences")?.optBoolean("enabled") != true) return
        val claimed = client.request(token, "/workspace/notifications/claim", "POST", JSONObject().put("limit", 5)).data ?: return
        val claimId = claimed.optString("claim_id").takeIf(String::isNotBlank) ?: return
        val events = claimed.optJSONArray("items") ?: return
        val manager = getSystemService(NotificationManager::class.java)
        val store = EncryptedWorkspaceStore(this)
        val receipts = store.readJson(userId, "notification_receipts") ?: JSONObject()
        for (index in 0 until events.length()) {
            currentCoroutineContext().ensureActive()
            if (!canNotify(this) || auth.loadAccessToken() != token) return
            val event = events.optJSONObject(index) ?: continue
            val id = event.optString("id").takeIf { it.isNotBlank() && it.length <= 160 } ?: continue
            if (!receipts.optBoolean(id)) {
                val pending = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java)
                    .setData(Uri.parse("analystai-internal://event/" + Uri.encode(id)))
                    .putExtra("workspace_event_id", id).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
                val hidden = Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setContentTitle("Analyst AI").setContentText("Есть новое событие в вашем портфеле").build()
                val notification = Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.ic_dialog_info)
                    .setContentTitle(event.optString("title", "Событие портфеля").take(160))
                    .setContentText(event.optString("body").take(600)).setStyle(Notification.BigTextStyle().bigText(event.optString("body").take(2000)))
                    .setContentIntent(pending).setAutoCancel(true).setOnlyAlertOnce(true)
                    .setVisibility(Notification.VISIBILITY_PRIVATE).setPublicVersion(hidden).build()
                if (runCatching { manager.notify("workspace:" + id, NOTIFICATION_ID, notification) }.isFailure) continue
                receipts.put(id, true)
                // A stable notification tag and a receipt prevent repeated alerts after an ACK timeout.
                if (receipts.length() > 500) receipts.keys().asSequence().take(receipts.length() - 500).toList().forEach(receipts::remove)
                store.saveJson(userId, "notification_receipts", receipts)
            }
            client.request(token, "/workspace/notifications/" + VolumeWorkspaceClient.encode(id) + "/ack", "POST",
                JSONObject().put("claim_id", claimId).put("state", "presented"))
        }
    }

    companion object {
        const val CHANNEL = "workspace_events"
        private const val JOB_ID = 35110
        private const val NOTIFICATION_ID = 35111
        fun canNotify(context: Context): Boolean {
            val manager = context.getSystemService(NotificationManager::class.java)
            return context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED &&
                manager.areNotificationsEnabled() && manager.getNotificationChannel(CHANNEL)?.importance != NotificationManager.IMPORTANCE_NONE
        }
        fun schedule(context: Context): Boolean = NotificationScheduling.attempt {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel(CHANNEL, "События портфеля", NotificationManager.IMPORTANCE_DEFAULT)
                .apply { description = "События по подтверждённым правилам и тихим часам"; lockscreenVisibility = Notification.VISIBILITY_PRIVATE })
            if (!canNotify(context)) return@attempt false
            val scheduler = context.getSystemService(JobScheduler::class.java)
            if (scheduler.getPendingJob(JOB_ID) != null) return@attempt true
            val job = JobInfo.Builder(JOB_ID, ComponentName(context, WorkspaceNotificationService::class.java))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true)
                .setPeriodic(15 * 60 * 1000L, 5 * 60 * 1000L).setBackoffCriteria(60_000, JobInfo.BACKOFF_POLICY_EXPONENTIAL).build()
            scheduler.schedule(job) == JobScheduler.RESULT_SUCCESS
        }
        fun cancel(context: Context) { NotificationScheduling.attempt { context.getSystemService(JobScheduler::class.java).cancel(JOB_ID); true } }
    }
}
