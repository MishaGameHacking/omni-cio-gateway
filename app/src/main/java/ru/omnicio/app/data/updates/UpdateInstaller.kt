package ru.omnicio.app.data.updates

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import java.io.File
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.withContext
import ru.omnicio.app.MainActivity

/** Only called after an explicit Update tap and APK identity/signature validation. */
object UpdateInstaller {
    const val ACTION = "ru.omnicio.app.UPDATE_INSTALL_RESULT"
    const val PREFS = "analyst_update_install"
    val approval = MutableStateFlow<Intent?>(null)
    val statusText = MutableStateFlow<String?>(null)

    suspend fun install(context: Context, file: File, release: ReleaseDescriptor) = withContext(Dispatchers.IO) {
        check(context.packageManager.canRequestPackageInstalls()) { "Разрешите установку обновления для Analyst AI." }
        UpdateClient().verifyArchive(context, file, release)
        val installer = context.packageManager.packageInstaller
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val previous = prefs.getInt("session", -1)
        if (previous != -1 && installer.mySessions.any { it.sessionId == previous }) {
            installer.abandonSession(previous)
        }
        approval.value = null
        val parameters = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
            setAppPackageName(context.packageName)
            setSize(release.bytes)
            // Official self-update path. Android may still require explicit approval.
            setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        }
        val id = installer.createSession(parameters)
        val nonce = UUID.randomUUID().toString()
        try {
            check(prefs.edit().putInt("session", id).putString("nonce", nonce).commit())
            installer.openSession(id).use { session ->
                session.openWrite("base.apk", 0, release.bytes).use { output ->
                    file.inputStream().use { input -> input.copyTo(output, 64 * 1024) }
                    session.fsync(output)
                }
                val result = Intent(context, InstallResultReceiver::class.java).apply {
                    action = ACTION
                    putExtra("nonce", nonce)
                    putExtra("expected_session", id)
                }
                // Mutable is required for PackageInstaller's status extras. Explicit
                // component + nonce + session check; receiver is not exported.
                val pending = PendingIntent.getBroadcast(context, id, result,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
                session.commit(pending.intentSender)
            }
            statusText.value = "APK передан Android. Подтвердите установку, если появится запрос."
        } catch (error: Exception) {
            runCatching { installer.abandonSession(id) }
            prefs.edit().remove("session").remove("nonce").apply()
            throw error
        }
    }

    internal fun notify(context: Context, title: String, action: Intent) {
        if (context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val manager = context.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("updates", "Обновления Analyst AI", NotificationManager.IMPORTANCE_DEFAULT))
        val pending = PendingIntent.getActivity(context, 730, action, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        manager.notify(730, Notification.Builder(context, "updates")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(title).setContentText("Нажмите, чтобы продолжить")
            .setContentIntent(pending).setAutoCancel(true).build())
    }
}

class InstallResultReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != UpdateInstaller.ACTION) return
        val prefs = context.getSharedPreferences(UpdateInstaller.PREFS, Context.MODE_PRIVATE)
        val session = prefs.getInt("session", -1)
        if (session < 0 || intent.getIntExtra("expected_session", -2) != session ||
            intent.getStringExtra("nonce") != prefs.getString("nonce", null) ||
            intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -2) != session) return
        when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirmation = intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java) ?: return
                UpdateInstaller.approval.value = confirmation
                UpdateInstaller.statusText.value = "Android ожидает подтверждение установки."
                UpdateInstaller.notify(context, "Подтвердите обновление Analyst AI", confirmation)
            }
            PackageInstaller.STATUS_SUCCESS -> {
                prefs.edit().remove("session").remove("nonce").apply()
                UpdateInstaller.approval.value = null
                UpdateInstaller.statusText.value = "Обновление установлено. Откройте Analyst AI."
                UpdateInstaller.notify(context, "Analyst AI обновлён", Intent(context, MainActivity::class.java))
            }
            else -> {
                prefs.edit().remove("session").remove("nonce").apply()
                UpdateInstaller.approval.value = null
                // Never display unbounded/vendor status text or installer internals.
                UpdateInstaller.statusText.value = "Android не установил обновление. Оно не удалило ваши данные. Можно повторить попытку."
            }
        }
    }
}

/** Android may stop the process during replacement. No forbidden background launch. */
class AppReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        context.getSharedPreferences(UpdateInstaller.PREFS, Context.MODE_PRIVATE).edit().clear().apply()
        UpdateInstaller.notify(context, "Analyst AI обновлён", Intent(context, MainActivity::class.java))
    }
}
