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

internal fun existingInstallBlocksNewAttempt(committed: Boolean, active: Boolean): Boolean = committed || active

/** Only called after an explicit Update tap and APK identity/signature validation. */
object UpdateInstaller {
    const val ACTION = "ru.omnicio.app.UPDATE_INSTALL_RESULT"
    const val PREFS = "analyst_update_install"
    val approval = MutableStateFlow<Intent?>(null)
    val statusText = MutableStateFlow<String?>(null)
    val pending = MutableStateFlow(false)
    private val installationLock = Mutex()
    internal val sessionGuard = Any()

    internal fun owns(prefs: SharedPreferences, id: Int, nonce: String): Boolean =
        prefs.getInt("session", -1) == id && prefs.getString("nonce", null) == nonce

    /** Rebuild process-local state without ever treating a missing callback as success. */
    fun refreshPending(context: Context): Boolean {
        val installer = context.packageManager.packageInstaller
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return synchronized(sessionGuard) {
            val id = prefs.getInt("session", -1)
            if (id < 0) return@synchronized clearTrackedSession(prefs)
            val lookup = runCatching { installer.getSessionInfo(id) }
            if (lookup.isFailure) {
                return@synchronized markPending(
                    "Не удалось проверить установочную сессию Android. Повторная установка не запущена.",
                )
            }
            val info = lookup.getOrNull()
                ?: return@synchronized clearTrackedSession(
                    prefs,
                    "Предыдущая установочная сессия завершилась или была отменена. Можно повторить обновление.",
                )
            if (existingInstallBlocksNewAttempt(info.isCommitted, info.isActive)) {
                return@synchronized markPending(
                    "Android уже обрабатывает обновление. Дождитесь результата или подтвердите установку.",
                )
            }
            abandonRestoredSession(installer, prefs, id)
        }
    }

    private fun markPending(message: String): Boolean {
        pending.value = true
        setStatusIfBlank(message)
        return true
    }

    private fun abandonRestoredSession(
        installer: PackageInstaller,
        prefs: SharedPreferences,
        id: Int,
    ): Boolean {
        val abandoned = runCatching { installer.abandonSession(id) }
        if (abandoned.isFailure) {
            return markPending(
                "Не удалось завершить незавершённую установочную сессию Android. Повторная установка остановлена.",
            )
        }
        return clearTrackedSession(
            prefs,
            "Незавершённая установочная сессия очищена. Можно повторить обновление.",
        )
    }

    private fun clearTrackedSession(prefs: SharedPreferences, message: String? = null): Boolean {
        prefs.edit().remove("session").remove("nonce").apply()
        approval.value = null
        pending.value = false
        message?.let(::setStatusIfBlank)
        return false
    }

    private fun setStatusIfBlank(message: String) {
        if (statusText.value.isNullOrBlank()) statusText.value = message
    }

    suspend fun install(context: Context, file: File, release: ReleaseDescriptor) = installationLock.withLock {
        withContext(Dispatchers.IO) {
            ensureActive()
            check(context.packageManager.canRequestPackageInstalls()) { "Разрешите установку обновления для Analyst AI." }
            UpdateClient().verifyArchive(context, file, release)
            val installer = context.packageManager.packageInstaller
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            prepareForNewSession(installer, prefs)
            val id = installer.createSession(parameters(context.packageName, release.bytes))
            val nonce = UUID.randomUUID().toString()
            submitInstallSession(
                open = {
                    register(prefs, id, nonce)
                    clearNotification(context)
                    installer.openSession(id)
                },
                stage = { session -> writeArchive(session, file, release) { ensureActive() } },
                commit = { session ->
                    val result = resultReceiver(context, id, nonce)
                    ensureActive()
                    synchronized(sessionGuard) {
                        check(owns(prefs, id, nonce)) { "Установочная сессия уже изменилась." }
                        // Set before commit: a fast callback must not be overwritten.
                        pending.value = true
                        statusText.value = "APK передан Android. Подтвердите установку, если появится запрос."
                    }
                    session.commit(result.intentSender)
                },
                uncommittedFailure = { failure -> abandonFailed(installer, prefs, id, nonce, failure) },
                committedCloseFailure = {
                    // Submission is not an installation result. Keep newer callback state.
                    Log.w("AnalystUpdate", "Не удалось закрыть сессию после передачи Android.")
                },
            )
        }
    }

    private fun prepareForNewSession(installer: PackageInstaller, prefs: SharedPreferences) {
        val previous = prefs.getInt("session", -1)
        if (previous == -1) {
            prefs.edit().remove("nonce").apply()
            pending.value = false
            return
        }
        val lookup = runCatching { installer.getSessionInfo(previous) }
        if (lookup.isFailure) {
            pending.value = true
            throw IllegalStateException("Не удалось проверить текущую установку Android. Повторная установка остановлена.")
        }
        val info = lookup.getOrNull()
        if (info != null && existingInstallBlocksNewAttempt(info.isCommitted, info.isActive)) {
            pending.value = true
            statusText.value = "Android уже обрабатывает обновление. Дождитесь результата или подтвердите установку."
            throw IllegalStateException("Установка обновления уже выполняется.")
        }
        if (info != null) {
            runCatching { installer.abandonSession(previous) }.getOrElse {
                pending.value = true
                throw IllegalStateException("Не удалось завершить старую установочную сессию Android.", it)
            }
        }
        prefs.edit().remove("session").remove("nonce").apply()
        approval.value = null
        pending.value = false
    }

    private fun parameters(packageName: String, bytes: Long) =
        PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
            setAppPackageName(packageName)
            setSize(bytes)
            // Request the official self-update path; always handle required OS consent.
            setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
        }

    private fun register(prefs: SharedPreferences, id: Int, nonce: String) {
        synchronized(sessionGuard) {
            check(prefs.edit().putInt("session", id).putString("nonce", nonce).commit())
            approval.value = null
            pending.value = true
            statusText.value = "Проверяем передачу APK системному установщику."
        }
    }

    private fun writeArchive(session: PackageInstaller.Session, file: File, release: ReleaseDescriptor, checkActive: () -> Unit) {
        session.openWrite("base.apk", 0, release.bytes).use { output ->
            file.inputStream().use { input ->
                copyVerifiedInstallStream(input, output, release.bytes, release.sha256, checkActive)
            }
            session.fsync(output)
        }
    }

    private fun resultReceiver(context: Context, id: Int, nonce: String): PendingIntent {
        val result = Intent(context, InstallResultReceiver::class.java).apply {
            action = ACTION
            putExtra("nonce", nonce)
            putExtra("expected_session", id)
        }
        // Mutable status extras are required by PackageInstaller. Explicit,
        // non-exported component plus nonce/session binding prevents external callbacks.
        return PendingIntent.getBroadcast(context, id, result,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE)
    }

    private fun abandonFailed(installer: PackageInstaller, prefs: SharedPreferences, id: Int, nonce: String, failure: Exception) {
        runCatching { installer.abandonSession(id) }
        synchronized(sessionGuard) {
            if (owns(prefs, id, nonce)) {
                prefs.edit().remove("session").remove("nonce").apply()
                approval.value = null
                pending.value = false
                statusText.value = if (failure is CancellationException) "Подготовка установки отменена. Можно повторить попытку."
                    else "Не удалось передать обновление Android. Можно повторить попытку."
            }
        }
    }

    internal fun clearNotification(context: Context) {
        runCatching { context.getSystemService(NotificationManager::class.java)?.cancel(730) }
            .onFailure { Log.w("AnalystUpdate", "Не удалось убрать уведомление предыдущей установочной сессии.") }
    }

    internal fun notifyAppReady(context: Context) {
        // Resolve the canonical launcher in the newly installed package. Spectrum
        // must return through BootstrapActivity, not straight to private MainActivity.
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
        notify(context, "Analyst AI обновлён", launch)
    }

    internal fun notify(context: Context, title: String, action: Intent) {
        if (context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        runCatching {
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(NotificationChannel("updates", "Обновления Analyst AI", NotificationManager.IMPORTANCE_DEFAULT))
            val actionIntent = PendingIntent.getActivity(context, 730, action, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
            manager.notify(730, Notification.Builder(context, "updates")
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle(title).setContentText("Нажмите, чтобы продолжить")
                .setContentIntent(actionIntent).setAutoCancel(true).build())
        }.onFailure {
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
            when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
                PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                    val confirmation = runCatching { intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java) }.getOrNull()
                    if (confirmation == null) {
                        runCatching { context.packageManager.packageInstaller.abandonSession(session) }
                        prefs.edit().remove("session").remove("nonce").apply()
                        UpdateInstaller.approval.value = null
                        UpdateInstaller.pending.value = false
                        UpdateInstaller.clearNotification(context)
                        UpdateInstaller.statusText.value = "Android не вернул окно подтверждения. Повторите установку обновления."
                    } else {
                        UpdateInstaller.approval.value = confirmation
                        UpdateInstaller.pending.value = true
                        UpdateInstaller.statusText.value = "Android ожидает подтверждение установки."
                        UpdateInstaller.notify(context, "Подтвердите обновление Analyst AI", confirmation)
                    }
                }
                PackageInstaller.STATUS_SUCCESS -> {
                    prefs.edit().remove("session").remove("nonce").apply()
                    UpdateInstaller.approval.value = null
                    UpdateInstaller.pending.value = false
                    UpdateInstaller.statusText.value = "Обновление установлено. Откройте Analyst AI."
                    UpdateInstaller.notifyAppReady(context)
                }
                else -> terminalFailure(context, prefs, status)
            }
        }
    }

    private fun terminalFailure(context: Context, prefs: SharedPreferences, status: Int) {
        prefs.edit().remove("session").remove("nonce").apply()
        UpdateInstaller.approval.value = null
        UpdateInstaller.pending.value = false
        UpdateInstaller.clearNotification(context)
        val reason = when (status) {
            PackageInstaller.STATUS_FAILURE_ABORTED -> InstallFailureReason.ABORTED
            PackageInstaller.STATUS_FAILURE_BLOCKED -> InstallFailureReason.BLOCKED
            PackageInstaller.STATUS_FAILURE_CONFLICT -> InstallFailureReason.CONFLICT
            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> InstallFailureReason.INCOMPATIBLE
            PackageInstaller.STATUS_FAILURE_INVALID -> InstallFailureReason.INVALID
            PackageInstaller.STATUS_FAILURE_STORAGE -> InstallFailureReason.STORAGE
            else -> InstallFailureReason.OTHER
        }
        // Only the validated system status selects a predefined explanation.
        UpdateInstaller.statusText.value = installFailureMessage(reason)
    }
}

/** Android may stop the process during replacement. No forbidden background launch. */
class AppReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        synchronized(UpdateInstaller.sessionGuard) {
            context.getSharedPreferences(UpdateInstaller.PREFS, Context.MODE_PRIVATE).edit().clear().apply()
            UpdateInstaller.approval.value = null
            UpdateInstaller.pending.value = false
            UpdateInstaller.statusText.value = "Обновление установлено. Откройте Analyst AI."
        }
        UpdateInstaller.notifyAppReady(context)
    }
}
