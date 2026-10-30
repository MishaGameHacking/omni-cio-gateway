package ru.omnicio.app.ui.auth

import android.app.Activity
import android.hardware.biometrics.BiometricManager
import android.hardware.biometrics.BiometricPrompt
import android.os.CancellationSignal
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

/** OS-controlled biometric or device-credential prompt; no fingerprint or phone PIN enters the app. */
@Composable
fun OwnerDeviceUnlock(onUnlocked: () -> Unit, usePassword: () -> Unit) {
    val activity = LocalActivity.current
    var cancellation by remember { mutableStateOf<CancellationSignal?>(null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val currentUnlocked by rememberUpdatedState(onUnlocked)
    val lifecycle = rememberOwnerAccessLifecycle {
        cancellation?.cancel()
        busy = false
    }
    val gate = lifecycle.gate
    DisposableEffect(gate) { onDispose { gate.background(); cancellation?.cancel() } }
    SpectrumBackground(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing).verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.Center) {
            SpectrumCard {
                Text("Analyst AI", style = MaterialTheme.typography.headlineLarge)
                Text("Подтвердите вход отпечатком пальца или кодом блокировки телефона.")
                message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                SpectrumPrimaryButton("Разблокировать", {
                    val owner = activity
                    val ticket = gate.begin()
                    if (ticket == null) message = "Откройте приложение, чтобы подтвердить вход."
                    else if (owner == null) message = "Проверка устройства недоступна. Войдите с паролем."
                    else {
                        busy = true
                        val signal = CancellationSignal()
                        cancellation = signal
                        try {
                            showDevicePrompt(owner, signal, {
                                if (gate.complete(ticket)) { busy = false; currentUnlocked() }
                            }, { reason -> if (gate.complete(ticket)) { busy = false; message = reason } })
                        } catch (_: SecurityException) {
                            busy = false; message = "Проверка устройства недоступна. Используйте пароль Analyst AI."
                        } catch (_: IllegalStateException) {
                            busy = false; message = "Не удалось открыть проверку устройства. Повторите вход."
                        } catch (_: IllegalArgumentException) {
                            busy = false; message = "Устройство не поддерживает этот способ входа. Используйте пароль Analyst AI."
                        }
                    }
                }, Modifier.fillMaxWidth(), enabled = !busy && lifecycle.foreground)
                SpectrumSecondaryButton("Войти с паролем", { gate.background(); cancellation?.cancel(); usePassword() }, Modifier.fillMaxWidth())
            }
        }
    }
}

internal fun showDevicePrompt(activity: Activity, signal: CancellationSignal,
    success: () -> Unit, failure: (String) -> Unit) {
    val authenticators = BiometricManager.Authenticators.BIOMETRIC_STRONG or BiometricManager.Authenticators.DEVICE_CREDENTIAL
    val manager = activity.getSystemService(BiometricManager::class.java)
    if (manager == null || manager.canAuthenticate(authenticators) != BiometricManager.BIOMETRIC_SUCCESS) {
        failure("Настройте блокировку телефона или войдите с паролем Analyst AI.")
        return
    }
    BiometricPrompt.Builder(activity).setTitle("Открыть Analyst AI")
        .setSubtitle("Ваш личный доступ к системе")
        .setAllowedAuthenticators(authenticators).build()
        .authenticate(signal, activity.mainExecutor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = success()
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                failure("Вход не подтверждён. Повторите проверку или используйте пароль Analyst AI.")
            }
        })
}
