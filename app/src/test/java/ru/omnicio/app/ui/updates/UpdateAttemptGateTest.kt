package ru.omnicio.app.ui.updates

import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.data.updates.ReleaseDescriptor

class UpdateAttemptGateTest {
    private val release = ReleaseDescriptor(
        packageName = "ru.omnicio.app.debug",
        versionCode = 37,
        versionName = "0.12.1-preview",
        sha256 = "a".repeat(64),
        bytes = 30_000_000,
        certificateSha256 = "b".repeat(64),
        minSdk = 37,
        notes = "Automatic foreground updates",
    )

    private fun claim(
        gate: UpdateAttemptGate,
        candidate: ReleaseDescriptor = release,
        decision: ReleaseDecision = ReleaseDecision.UPDATE_REQUIRED,
        automatic: Boolean = true,
        foreground: Boolean = true,
        permissionGranted: Boolean = true,
        busy: Boolean = false,
        installationPending: Boolean = false,
    ): Boolean = gate.claim(
        release = candidate,
        decision = decision,
        automatic = automatic,
        foreground = foreground,
        permissionGranted = permissionGranted,
        busy = busy,
        installationPending = installationPending,
    )

    @Test
    fun onlyAnUpdateRequiredDecisionCanStartAnAttempt() {
        val gate = UpdateAttemptGate()
        for (decision in ReleaseDecision.entries) {
            if (decision != ReleaseDecision.UPDATE_REQUIRED) {
                assertFalse("Unexpected start for $decision", claim(gate, decision = decision))
            }
        }
        assertTrue(claim(gate))
    }

    @Test
    fun missingPermissionDoesNotStartOrConsumeAnAttempt() {
        val gate = UpdateAttemptGate()
        assertFalse(claim(gate, permissionGranted = false))
        assertFalse(claim(gate, permissionGranted = false))
        assertTrue(claim(gate))
        assertFalse(claim(gate))
    }

    @Test
    fun aBackgroundPolicyResultCannotStartOrConsumeAnAutomaticAttempt() {
        val gate = UpdateAttemptGate()
        assertFalse(claim(gate, foreground = false))
        assertTrue(claim(gate))
    }

    @Test
    fun busyOrPendingInstallationDoesNotStartOrConsumeAnAttempt() {
        val gate = UpdateAttemptGate()
        assertFalse(claim(gate, busy = true))
        assertFalse(claim(gate, installationPending = true))
        assertTrue(claim(gate))
    }

    @Test
    fun repeatedPollingAndNotesChangesDoNotRepeatTheSameApk() {
        val gate = UpdateAttemptGate()
        assertTrue(claim(gate))
        assertFalse(claim(gate, candidate = release.copy()))
        assertFalse(claim(gate, candidate = release.copy(notes = "Corrected release notes")))
    }

    @Test
    fun aDifferentBinaryIdentityGetsItsOwnAutomaticAttempt() {
        val gate = UpdateAttemptGate()
        assertTrue(claim(gate))
        assertTrue(claim(gate, candidate = release.copy(sha256 = "c".repeat(64))))
        assertTrue(claim(gate, candidate = release.copy(versionCode = 38, versionName = "0.12.2-preview")))
        assertFalse(claim(gate))
    }

    @Test
    fun explicitRetryCanRepeatAnAttemptAndStillSuppressesAutomaticPolling() {
        val gate = UpdateAttemptGate()
        assertTrue(claim(gate))
        assertFalse(claim(gate))
        assertTrue(claim(gate, automatic = false))
        assertTrue(claim(gate, automatic = false))
        assertFalse(claim(gate))
    }

    @Test
    fun anExplicitFirstAttemptAlsoPreventsAnAutomaticRetry() {
        val gate = UpdateAttemptGate()
        assertTrue(claim(gate, automatic = false))
        assertFalse(claim(gate))
    }

    @Test
    fun explicitRetryCannotBypassPermissionOrPendingInstallation() {
        val gate = UpdateAttemptGate()
        assertFalse(claim(gate, automatic = false, permissionGranted = false))
        assertFalse(claim(gate, automatic = false, installationPending = true))
        assertFalse(claim(gate, automatic = false, busy = true))
        assertTrue(claim(gate, automatic = false))
    }

    @Test
    fun leavingAndReturningToForegroundDoesNotRepeatAnAttempt() {
        val gate = UpdateAttemptGate()
        assertTrue(claim(gate))
        assertFalse(claim(gate, foreground = false))
        assertFalse(claim(gate))
    }

    @Test(timeout = 5000)
    fun cancellationDoesNotReleaseTheAutomaticClaim() = runBlocking {
        val gate = UpdateAttemptGate()
        val operation = launch(start = CoroutineStart.UNDISPATCHED) {
            assertTrue(claim(gate))
            awaitCancellation()
        }
        operation.cancelAndJoin()
        assertFalse(claim(gate))
        assertTrue(claim(gate, automatic = false))
    }
}
