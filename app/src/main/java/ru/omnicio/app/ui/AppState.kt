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
private const val KEY_AMOUNTS_HIDDEN = "amounts_hidden"
private const val KEY_DISPLAY_CURRENCY = "display_currency"
private const val KEY_OVERVIEW_MODE = "overview_mode"
private const val KEY_PORTFOLIO_PRESENT = "portfolio_present"
private const val KEY_BROKER_CONNECTED = "broker_connected"
private const val KEY_BROKER_CREDENTIAL_PRESENT = "broker_credential_present"
private const val KEY_DEPENDENT_JOBS_RUNNING = "dependent_jobs_running"
private const val KEY_RESERVE_MINOR = "reserve_minor"
private const val KEY_GOAL_HORIZON_YEARS = "goal_horizon_years"
private const val KEY_NOTIFICATIONS_ENABLED = "notifications_enabled"
private const val KEY_FAST_ALERTS_ENABLED = "fast_alerts_enabled"
private const val KEY_DARK_THEME = "dark_theme"
private const val KEY_BROKER_REVOKED = "broker_revoked"
private const val KEY_LOCAL_SCHEMA_VERSION = "local_schema_version"

internal data class AppUiState(
    val installationId: String,
    val onboardingComplete: Boolean,
    val amountsHidden: Boolean,
    val displayCurrency: DisplayCurrency,
    val overviewMode: OverviewMode,
    val settings: LocalSettingsState,
    val migrationStatus: LocalMigrationStatus,
)

internal class OmnicioViewModel(application: Application) : AndroidViewModel(application) {
    private val store = LocalProfileStore(application.applicationContext)
    private val initialMigrationStatus = store.migrateIfNeeded()

    private val mutableUiState = MutableStateFlow(
        AppUiState(
            installationId = store.getOrCreateInstallationId(),
            onboardingComplete = store.isOnboardingComplete(),
            amountsHidden = store.areAmountsHidden(),
            displayCurrency = store.displayCurrency(),
            overviewMode = store.overviewMode(),
            settings = store.localSettings(),
            migrationStatus = initialMigrationStatus,
        ),
    )

    val uiState: StateFlow<AppUiState> = mutableUiState.asStateFlow()

    fun completeOnboarding() {
        store.setOnboardingComplete()
        mutableUiState.value = mutableUiState.value.copy(onboardingComplete = true)
    }

    fun toggleAmountsHidden() {
        val hidden = !mutableUiState.value.amountsHidden
        store.setAmountsHidden(hidden)
        mutableUiState.value = mutableUiState.value.copy(amountsHidden = hidden)
    }

    fun setDisplayCurrency(currency: DisplayCurrency) {
        store.setDisplayCurrency(currency)
        mutableUiState.value = mutableUiState.value.copy(displayCurrency = currency)
    }

    fun setOverviewMode(mode: OverviewMode) {
        store.setOverviewMode(mode)
        mutableUiState.value = mutableUiState.value.copy(overviewMode = mode)
    }

    fun connectBrokerFixture() = updateSettings(::connectBrokerFixtureState)

    fun disconnectBroker() = updateSettings(::disconnectBrokerState)

    fun revokeBrokerFixture() = updateSettings(::revokeBrokerFixtureState)

    fun retryLocalMigration() {
        mutableUiState.value = mutableUiState.value.copy(
            migrationStatus = store.migrateIfNeeded(),
        )
    }

    fun deleteLocalPortfolio() = updateSettings(::deleteLocalPortfolioState)

    fun restoreDemoPortfolio() = updateSettings(::restoreDemoPortfolioState)

    fun setReserveMinor(reserveMinor: Long) {
        updateSettings { it.copy(reserveMinor = reserveMinor) }
    }

    fun setGoalHorizonYears(years: Int) {
        updateSettings { it.copy(goalHorizonYears = years) }
    }

    fun setNotificationsEnabled(enabled: Boolean) {
        updateSettings { notificationsState(it, enabled) }
    }

    fun setFastAlertsEnabled(enabled: Boolean) {
        updateSettings { fastAlertsState(it, enabled) }
    }

    fun setDarkTheme(enabled: Boolean) {
        updateSettings { it.copy(darkTheme = enabled) }
    }

    private fun updateSettings(
        transform: (LocalSettingsState) -> LocalSettingsState,
    ) {
        val next = transform(mutableUiState.value.settings)
        store.setLocalSettings(next)
        mutableUiState.value = mutableUiState.value.copy(settings = next)
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

    fun areAmountsHidden(): Boolean = prefs.getBoolean(KEY_AMOUNTS_HIDDEN, false)

    fun setAmountsHidden(hidden: Boolean) {
        prefs.edit().putBoolean(KEY_AMOUNTS_HIDDEN, hidden).apply()
    }

    fun displayCurrency(): DisplayCurrency {
        val stored = prefs.getString(KEY_DISPLAY_CURRENCY, null)
        return stored?.let { value ->
            runCatching { DisplayCurrency.valueOf(value) }.getOrNull()
        } ?: DisplayCurrency.RUB
    }

    fun setDisplayCurrency(currency: DisplayCurrency) {
        prefs.edit().putString(KEY_DISPLAY_CURRENCY, currency.name).apply()
    }

    fun overviewMode(): OverviewMode {
        val stored = prefs.getString(KEY_OVERVIEW_MODE, null)
        return stored?.let { value ->
            runCatching { OverviewMode.valueOf(value) }.getOrNull()
        } ?: OverviewMode.READY
    }

    fun setOverviewMode(mode: OverviewMode) {
        prefs.edit().putString(KEY_OVERVIEW_MODE, mode.name).apply()
    }

    fun localSettings(): LocalSettingsState {
        val defaults = LocalSettingsState()
        return LocalSettingsState(
            portfolioPresent = prefs.getBoolean(KEY_PORTFOLIO_PRESENT, defaults.portfolioPresent),
            brokerConnected = prefs.getBoolean(KEY_BROKER_CONNECTED, defaults.brokerConnected),
            brokerCredentialPresent = prefs.getBoolean(
                KEY_BROKER_CREDENTIAL_PRESENT,
                defaults.brokerCredentialPresent,
            ),
            brokerRevoked = prefs.getBoolean(
                KEY_BROKER_REVOKED,
                defaults.brokerRevoked,
            ),
            dependentJobsRunning = prefs.getBoolean(
                KEY_DEPENDENT_JOBS_RUNNING,
                defaults.dependentJobsRunning,
            ),
            reserveMinor = prefs.getLong(KEY_RESERVE_MINOR, defaults.reserveMinor),
            goalHorizonYears = prefs.getInt(
                KEY_GOAL_HORIZON_YEARS,
                defaults.goalHorizonYears,
            ),
            notificationsEnabled = prefs.getBoolean(
                KEY_NOTIFICATIONS_ENABLED,
                defaults.notificationsEnabled,
            ),
            fastAlertsEnabled = prefs.getBoolean(
                KEY_FAST_ALERTS_ENABLED,
                defaults.fastAlertsEnabled,
            ),
            darkTheme = prefs.getBoolean(
                KEY_DARK_THEME,
                defaults.darkTheme,
            ),
        )
    }

    fun migrateIfNeeded(): LocalMigrationStatus {
        val storedVersion = prefs.getInt(KEY_LOCAL_SCHEMA_VERSION, 0)
        if (storedVersion >= CURRENT_LOCAL_SCHEMA_VERSION) {
            return LocalMigrationStatus.CURRENT
        }

        val persisted = prefs.edit()
            .putInt(KEY_LOCAL_SCHEMA_VERSION, CURRENT_LOCAL_SCHEMA_VERSION)
            .commit()
        return migrationStatusFor(storedVersion, persisted)
    }

    fun setLocalSettings(state: LocalSettingsState) {
        prefs.edit()
            .putBoolean(KEY_PORTFOLIO_PRESENT, state.portfolioPresent)
            .putBoolean(KEY_BROKER_CONNECTED, state.brokerConnected)
            .putBoolean(KEY_BROKER_CREDENTIAL_PRESENT, state.brokerCredentialPresent)
            .putBoolean(KEY_BROKER_REVOKED, state.brokerRevoked)
            .putBoolean(KEY_DEPENDENT_JOBS_RUNNING, state.dependentJobsRunning)
            .putLong(KEY_RESERVE_MINOR, state.reserveMinor)
            .putInt(KEY_GOAL_HORIZON_YEARS, state.goalHorizonYears)
            .putBoolean(KEY_NOTIFICATIONS_ENABLED, state.notificationsEnabled)
            .putBoolean(KEY_FAST_ALERTS_ENABLED, state.fastAlertsEnabled)
            .putBoolean(KEY_DARK_THEME, state.darkTheme)
            .apply()
    }
}

internal fun installationIdLabel(installationId: String): String {
    val prefix = installationId.take(8)
    return if (installationId.length > prefix.length) "$prefix…" else prefix
}
