package ru.omnicio.app.data.updates

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.util.Log
import java.io.File
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import ru.omnicio.app.MainActivity

/** Only called after an explicit Update tap and APK identity/signature validation. */
object UpdateInstaller {
    const val ACTION = "ru.omnicio.app.UPDATE_INSTALL_RESULT"
    const val PREFS = "analyst_update_install"
    val approval = MutableStateFlow<Intent?>(null)
    val statusText = MutableStateFlow<String?>(null)
    private val installationLock = Mutex()
    internal val sessionGuard = Any()

    internal fun owns(prefs: SharedPreferences, id: Int, nonce: String): Boolean =
        prefs.getInt("session", -1) == id && prefs.getString("nonce", null) == nonce

    suspend fun install(context: Context, file: File, release: ReleaseDescriptor) = installationLock.withLock {
        withContext(Dispatchers.IO) {
            ensureActive()
            check(context.packageManager.canRequestPackageInstalls()) { "Разрешите установку обновления для Analyst AI." }
            UpdateClient().verifyArchive(context, file, release)
            val installer = context.packageManager.packageInstaller
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val previous = prefs.getInt("session", -1)
            if (previous != -1 && installer.mySessions.any { it.sessionId == previous }) {
                installer.abandonSession(previous)
            }
            val parameters = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
                setAppPackageName(context.packageName)
                setSize(release.bytes)
                // Request the official self-update path; still handle Android's
                // mandatory confirmation rather than promise silent installation.
                setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
            }
            val id = installer.createSession(parameters)
            val nonce = UUID.randomUUID().toString()
            var committed = false
            try {
                synchronized(sessionGuard) {
                    check(prefs.edit().putInt("session", id).putString("nonce", nonce).commit())
                    approval.value = null
                    statusText.value = "Проверяем передачу APK системному установщику."
                }
                installer.openSession(id).use { session ->
                    session.openWrite("base.apk", 0, release.bytes).use { output ->
                        file.inputStream().use { input ->
                            copyVerifiedInstallStream(input, output, release.bytes, release.sha256) { ensureActive() }
                        }
                        session.fsync(output)
                    }
                    val result = Intent(context, InstallResultReceiver::class.java).apply {
                        action = ACTION
                        putExtra("nonce", nonce)
                        putExtra("expected_session", id)
                    }
                    // Mutable is required for PackageInstaller's status extras.
                    // Explicit component + nonce + session; receiver not exported.
                    val pending = PendingIntent.getBroadcast(context, id, result,
                        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
                    ensureActive()
                    synchronized(sessionGuard) {
                        check(owns(prefs, id, nonce)) { "Установочная сессия уже изменилась." }
                        // Set BEFORE commit: a fast callback must not be overwritten
                        // afterwards by an older 'submitted' state.
                        statusText.value = "APK передан Android. Подтвердите установку, если появится запрос."
                    }
                    session.commit(pending.intentSender)
                    committed = true
                }
            } catch (error: Exception) {
                if (committed) {
                    // A close failure is not an installation result. Do not
                    // abandon a committed session or erase its newer callback.
                    Log.w("AnalystUpdate", "Не удалось закрыть сессию после передачи Android.")
                } else {
                    runCatching { installer.abandonSession(id) }
                    synchronized(sessionGuard) {
                        if (owns(prefs, id, nonce)) {
                            prefs.edit().remove("session").remove("nonce").apply()
                            approval.value = null
                            statusText.value = if (error is CancellationException) "Подготовка установки отменена. Можно повторить попытку."
                                else "Не удалось передать обновление Android. Можно повторить попытку."
                        }
                    }
                    throw error
                }
            }
        }
    }

    internal fun notify(context: Context, title: String, action: Intent) {
        if (context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        runCatching {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel("updates", "Обновления Analyst AI", NotificationManager.IMPORTANCE_DEFAULT))
            val pending = PendingIntent.getActivity(context, 730, action, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            manager.notify(730, Notification.Builder(context, "updates")
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle(title).setContentText("Нажмите, чтобы продолжить")
                .setContentIntent(pending).setAutoCancel(true).build())
        }.onFailure {
            // The foreground UI still exposes approval/result. Notification
            // permission or vendor errors must not erase the install outcome.
            Log.w("AnalystUpdate", "Уведомление обновления недоступно; результат сохранён на экране.")
        }
    }
}

class InstallResultReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != UpdateInstaller.ACTION) return
        synchronized(UpdateInstaller.sessionGuard) {
            val prefs = context.getSharedPreferences(UpdateInstaller.PREFS, Context.MODE_PRIVATE)
            val session = prefs.getInt("session", -1)
            val nonce = intent.getStringExtra("nonce") ?: return
            if (session < 0 || !UpdateInstaller.owns(prefs, session, nonce) ||
                intent.getIntExtra("expected_session", -2) != session ||
                intent.getIntExtra(PackageInstaller.EXTRA_SESSION_ID, -2) != session) return
            when (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
                PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                    val confirmation = runCatching { intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java) }.getOrNull()
                    if (confirmation == null) {
                        runCatching { context.packageManager.packageInstaller.abandonSession(session) }
                        prefs.edit().remove("session").remove("nonce").apply()
                        UpdateInstaller.approval.value = null
                        UpdateInstaller.statusText.value = "Android не вернул окно подтверждения. Повторите установку обновления."
                    } else {
                        UpdateInstaller.approval.value = confirmation
                        UpdateInstaller.statusText.value = "Android ожидает подтверждение установки."
                        UpdateInstaller.notify(context, "Подтвердите обновление Analyst AI", confirmation)
                    }
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
}

/** Android may stop the process during replacement. No forbidden background launch. */
class AppReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        synchronized(UpdateInstaller.sessionGuard) {
            context.getSharedPreferences(UpdateInstaller.PREFS, Context.MODE_PRIVATE).edit().clear().apply()
            UpdateInstaller.approval.value = null
            UpdateInstaller.statusText.value = "Обновление установлено. Откройте Analyst AI."
        }
        UpdateInstaller.notify(context, "Analyst AI обновлён", Intent(context, MainActivity::class.java))
    }
}
