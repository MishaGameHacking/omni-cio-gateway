package ru.omnicio.app.ui

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

private const val PREFS = "omnicio_local_nonsecret_state"
private const val KEY_INSTALLATION_ID = "installation_id"
private const val KEY_ONBOARDING_COMPLETE = "onboarding_complete"

internal data class AppUiState(
    val installationId: String,
    val onboardingComplete: Boolean,
)

internal class OmnicioViewModel(application: Application) : AndroidViewModel(application) {
    private val store = LocalProfileStore(application.applicationContext)

    private val mutableUiState = MutableStateFlow(
        AppUiState(
            installationId = store.getOrCreateInstallationId(),
            onboardingComplete = store.isOnboardingComplete(),
        ),
    )

    val uiState: StateFlow<AppUiState> = mutableUiState.asStateFlow()

    fun completeOnboarding() {
        store.setOnboardingComplete()
        mutableUiState.value = mutableUiState.value.copy(onboardingComplete = true)
    }
}

private class LocalProfileStore(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun getOrCreateInstallationId(): String {
        val saved = prefs.getString(KEY_INSTALLATION_ID, null)
        if (!saved.isNullOrBlank()) {
            return saved
        }

        val generated = UUID.randomUUID().toString()
        prefs.edit().putString(KEY_INSTALLATION_ID, generated).apply()
        return generated
    }

    fun isOnboardingComplete(): Boolean = prefs.getBoolean(KEY_ONBOARDING_COMPLETE, false)

    fun setOnboardingComplete() {
        prefs.edit().putBoolean(KEY_ONBOARDING_COMPLETE, true).apply()
    }
}

internal fun installationIdLabel(installationId: String): String {
    val prefix = installationId.take(8)
    return if (installationId.length > prefix.length) "$prefix…" else prefix
}
