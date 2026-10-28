package ru.omnicio.app.data.notifications

import org.junit.Assert.*
import org.junit.Test

class NotificationSchedulingTest {
    @Test fun permissionDenialDoesNotKillForegroundSettings() {
        assertFalse(NotificationScheduling.attempt { throw SecurityException("network permission") })
    }

    @Test fun systemRefusalIsNeverReportedAsScheduled() {
        assertFalse(NotificationScheduling.attempt { false })
        assertFalse(NotificationScheduling.attempt { throw IllegalStateException("scheduler unavailable") })
        assertFalse(NotificationScheduling.attempt { throw IllegalArgumentException("job rejected") })
    }

    @Test fun successfulScheduleIsReportedOnce() {
        var calls = 0
        assertTrue(NotificationScheduling.attempt { calls++; true })
        assertEquals(1, calls)
    }

    @Test(expected = OutOfMemoryError::class)
    fun fatalVmErrorIsNotDisguisedAsDeliveryFailure() {
        NotificationScheduling.attempt { throw OutOfMemoryError() }
    }
}
