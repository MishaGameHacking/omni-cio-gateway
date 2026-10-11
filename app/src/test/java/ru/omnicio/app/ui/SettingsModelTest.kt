package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsModelTest {
    @Test
    fun revokedCredentialStopsJobsButRemainsLocalUntilDisconnect() {
        val connected = connectBrokerFixtureState(LocalSettingsState())
        val revoked = revokeBrokerFixtureState(connected)

        assertFalse(revoked.brokerConnected)
        assertTrue(revoked.brokerCredentialPresent)
        assertTrue(revoked.brokerRevoked)
        assertFalse(revoked.dependentJobsRunning)

        val cleared = disconnectBrokerState(revoked)
        assertFalse(cleared.brokerCredentialPresent)
        assertFalse(cleared.brokerRevoked)
    }

    @Test
    fun disconnectClearsLocalCredentialAndDependentJobs() {
        val connected = connectBrokerFixtureState(LocalSettingsState())
        val disconnected = disconnectBrokerState(connected)

        assertFalse(disconnected.brokerConnected)
        assertFalse(disconnected.brokerCredentialPresent)
        assertFalse(disconnected.dependentJobsRunning)
        assertTrue(disconnected.portfolioPresent)
    }

    @Test
    fun localDeleteDoesNotNeedServerAndClearsBrokerState() {
        val connected = connectBrokerFixtureState(LocalSettingsState())
        val deleted = deleteLocalPortfolioState(connected)

        assertFalse(deleted.portfolioPresent)
        assertFalse(deleted.brokerConnected)
        assertFalse(deleted.brokerCredentialPresent)
        assertFalse(deleted.dependentJobsRunning)
    }

    @Test
    fun exportNeverContainsBrokerCredentialOrToken() {
        val connected = connectBrokerFixtureState(LocalSettingsState())
        val export = buildLocalExportSummary(connected)

        assertTrue(export.contains("broker_credential=not_exported"))
        assertFalse(export.contains("token", ignoreCase = true))
    }

    @Test
    fun disablingNotificationsAlsoStopsFastAlerts() {
        val state = LocalSettingsState(
            notificationsEnabled = true,
            fastAlertsEnabled = true,
        )
        val disabled = notificationsState(state, enabled = false)

        assertFalse(disabled.notificationsEnabled)
        assertFalse(disabled.fastAlertsEnabled)
        assertFalse(fastAlertsState(disabled, enabled = true).fastAlertsEnabled)
    }

    @Test
    fun subscriptionFixtureHasNoPurchasableOrFamilyTier() {
        val tiers = subscriptionTiers()

        assertTrue(tiers.first { it.name == "Наблюдение" }.available)
        assertTrue(tiers.none { it.purchasable })
        assertTrue(tiers.none { it.name.contains("Семей", ignoreCase = true) })
        assertFalse(tiers.first { it.name == "Персональный план" }.available)
    }

    @Test
    fun reserveAndHorizonPresetsKeepCurrentDefaults() {
        val defaults = LocalSettingsState()

        assertTrue(reservePresetsMinor().contains(defaults.reserveMinor))
        assertTrue(goalHorizonPresets().contains(defaults.goalHorizonYears))
        assertEquals(3, defaults.goalHorizonYears)
    }
    @Test
    fun darkThemeCanChangeIndependently() {
        val original = LocalSettingsState(darkTheme = false)
        val changed = original.copy(darkTheme = true)

        assertFalse(original.darkTheme)
        assertTrue(changed.darkTheme)
        assertEquals(original.reserveMinor, changed.reserveMinor)
    }
}

