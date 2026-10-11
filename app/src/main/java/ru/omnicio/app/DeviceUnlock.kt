package ru.omnicio.app

import android.app.KeyguardManager
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.Build
import android.os.CancellationSignal
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/** The OS verifies presence; cancelling or losing the prompt never unlocks the application. */
internal class DeviceUnlock(private val activity: ComponentActivity) {
    private var completed: ((Boolean) -> Unit)? = null
    private var cancellation: CancellationSignal? = null
    private val credential = activity.registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        finish(it.resultCode == android.app.Activity.RESULT_OK)
    }

    @Suppress("DEPRECATION")
    fun authenticate(result: (Boolean) -> Unit) {
        if (completed != null) return
        val keyguard = activity.getSystemService(KeyguardManager::class.java)
        if (!keyguard.isDeviceSecure) { result(false); return }
        completed = result
        if (Build.VERSION.SDK_INT < 29) {
            showCredential()
            return
        }
        val builder = BiometricPrompt.Builder(activity).setTitle("Разблокировать OMNICIO")
            .setSubtitle("Подтвердите личность отпечатком или кодом телефона")
        when {
            Build.VERSION.SDK_INT >= 30 -> builder.setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL)
            else -> builder.setDeviceCredentialAllowed(true)
        }
        val signal = CancellationSignal()
        cancellation = signal
        builder.build().authenticate(signal, activity.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = finish(true)
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                finish(false)
            }
        })
    }

    @Suppress("DEPRECATION")
    private fun showCredential() {
        val intent = activity.getSystemService(KeyguardManager::class.java)
            .createConfirmDeviceCredentialIntent("OMNICIO", "Подтвердите личность")
        if (intent == null) finish(false) else credential.launch(intent)
    }

    private fun finish(success: Boolean) {
        val callback = completed
        completed = null
        cancellation = null
        callback?.invoke(success)
    }

    fun cancel() { cancellation?.cancel(); finish(false) }
}
