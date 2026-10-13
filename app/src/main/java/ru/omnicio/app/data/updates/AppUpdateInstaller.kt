package ru.omnicio.app.data.updates

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.os.Build
import java.io.File
import ru.omnicio.app.BootstrapActivity

internal class AppUpdateInstaller(private val context: Context) {
    fun canInstallPackages(): Boolean = context.packageManager.canRequestPackageInstalls()

    fun install(release: AppRelease, apk: File): Int {
        if (!canInstallPackages()) {
            throw UpdateValidationException("Разрешите Analyst AI устанавливать обновления.")
        }
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
            setAppPackageName(context.packageName)
            setSize(apk.length())
            setInstallReason(PackageManager.INSTALL_REASON_USER)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_REQUIRED)
            }
        }
        val sessionId = installer.createSession(params)
        try {
            installer.openSession(sessionId).use { session ->
                apk.inputStream().buffered().use { input ->
                    session.openWrite("base.apk", 0L, apk.length()).use { output ->
                        input.copyTo(output, 64 * 1024)
                        session.fsync(output)
                    }
                }
                val callback = Intent(context, UpdateInstallReceiver::class.java).apply {
                    action = UpdateInstallReceiver.ACTION_INSTALL_STATUS
                    putExtra(UpdateInstallReceiver.EXTRA_EXPECTED_VERSION, release.versionCode)
                }
                val pending = PendingIntent.getBroadcast(
                    context,
                    sessionId,
                    callback,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_MUTABLE,
                )
                UpdateCheckStore(context).markInstalling(release.versionCode)
                session.commit(pending.intentSender)
            }
        } catch (error: Exception) {
            runCatching { installer.abandonSession(sessionId) }
            UpdateCheckStore(context).markInstallFinished(error.message ?: "Не удалось запустить установку.")
            throw error
        } finally {
            apk.delete()
        }
        return sessionId
    }
}

class UpdateInstallReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_INSTALL_STATUS) return
        val store = UpdateCheckStore(context)
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirmation = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(Intent.EXTRA_INTENT)
                }
                if (confirmation == null) {
                    store.markInstallFinished("Android не вернул окно подтверждения установки.")
                    launchBootstrap(context)
                } else {
                    confirmation.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    runCatching { context.startActivity(confirmation) }.onFailure {
                        store.markInstallFinished("Не удалось открыть системный установщик Android.")
                        launchBootstrap(context)
                    }
                }
            }

            PackageInstaller.STATUS_SUCCESS -> {
                store.markInstallFinished()
                launchBootstrap(context)
            }

            else -> {
                val message = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
                    ?.take(300)
                    ?.takeIf { it.isNotBlank() }
                    ?: "Android отклонил обновление (код $status)."
                store.markInstallFinished(message)
                launchBootstrap(context)
            }
        }
    }

    private fun launchBootstrap(context: Context) {
        val activity = Intent(context, BootstrapActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        runCatching { context.startActivity(activity) }
    }

    companion object {
        const val ACTION_INSTALL_STATUS = "ru.omnicio.app.UPDATE_INSTALL_STATUS"
        const val EXTRA_EXPECTED_VERSION = "expected_version"
    }
}
