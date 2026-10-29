package ru.omnicio.app.ui.auth

import org.junit.Assert.*
import org.junit.Test

class OwnerAccessCooldownTest {
    @Test fun remainingTimeUsesDeadlineAndNeverShowsZeroBeforeExpiry() {
        var now = 10_000L
        val cooldown = OwnerAccessCooldown { now }
        assertTrue(cooldown.start(125))
        assertEquals(125, cooldown.remainingSeconds())
        now = 10_001L
        assertEquals(125, cooldown.remainingSeconds())
        now = 11_000L
        assertEquals(124, cooldown.remainingSeconds())
        now = 134_999L
        assertEquals(1, cooldown.remainingSeconds())
        now = 135_000L
        assertEquals(0, cooldown.remainingSeconds())
    }

    @Test fun recreationRestoresDeadlineWithoutRestartingWait() {
        var now = 20_000L
        val original = OwnerAccessCooldown { now }
        original.start(900)
        val saved = original.snapshot()
        now += 120_000L
        val restored = OwnerAccessCooldown.restore(saved) { now }
        assertEquals(780, restored.remainingSeconds())
        now += 780_000L
        assertEquals(0, restored.remainingSeconds())
    }

    @Test fun backgroundTimeCountsWithoutNeedingTimerTicks() {
        var now = 1_000L
        val cooldown = OwnerAccessCooldown { now }
        cooldown.start(60)
        now += 59_999L
        assertEquals(1, cooldown.remainingSeconds())
        now += 20_000L
        assertEquals(0, cooldown.remainingSeconds())
    }

    @Test fun missingRetryHeaderAndUnrelatedFailureDoNotEraseExistingDeadline() {
        var now = 500L
        val cooldown = OwnerAccessCooldown { now }
        cooldown.start(120)
        now += 30_000L
        assertFalse(cooldown.start(null))
        assertFalse(cooldown.start(0))
        assertEquals(90, cooldown.remainingSeconds())
    }

    @Test fun monotonicClockResetDoesNotDisplayHoursAfterDeviceRestart() {
        var now = 9_000_000L
        val cooldown = OwnerAccessCooldown { now }
        cooldown.start(900)
        val saved = cooldown.snapshot()
        now = 1_000L
        assertEquals(0, cooldown.remainingSeconds())
        assertEquals(0, OwnerAccessCooldown.restore(saved) { now }.remainingSeconds())
    }

    @Test fun corruptedOrOverflowSnapshotsAreRejected() {
        val clock = { 1_000L }
        for (saved in listOf(emptyList(), listOf(1L), listOf(-1L, 500L),
            listOf(1L, Long.MAX_VALUE), listOf(500L, 400L), listOf(2_000L, 3_000L))) {
            assertEquals(0, OwnerAccessCooldown.restore(saved, clock).remainingSeconds())
        }
        val impossible = OwnerAccessCooldown { Long.MAX_VALUE }
        assertFalse(impossible.start(900))
        assertEquals(0, impossible.remainingSeconds())
    }

    @Test fun labelsShowMinutesAndSecondsWithoutRoundingMinutesUp() {
        assertEquals("15:00", ownerWaitLabel(900))
        assertEquals("02:05", ownerWaitLabel(125))
        assertEquals("01:00", ownerWaitLabel(60))
        assertEquals("00:59", ownerWaitLabel(59))
        assertEquals("00:01", ownerWaitLabel(1))
        assertEquals("00:00", ownerWaitLabel(0))
    }
}
