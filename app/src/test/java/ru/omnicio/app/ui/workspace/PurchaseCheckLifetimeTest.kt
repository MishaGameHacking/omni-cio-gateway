package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Test

class PurchaseCheckLifetimeTest {
    private val start = "2026-10-18T10:00:00Z"
    private val end = "2026-10-18T10:01:00Z"

    @Test fun responseDelayAndBackgroundTimeConsumeLifetime() {
        assertEquals(55_000L, remainingPurchaseCheckMillis(start, end, 1_000, 6_000))
        assertEquals(0L, remainingPurchaseCheckMillis(start, end, 1_000, 61_000))
        assertEquals(0L, remainingPurchaseCheckMillis(start, end, 1_000, 90_000))
    }

    @Test fun olderObservationKeepsItsShorterDeadline() {
        assertEquals(250L, remainingPurchaseCheckMillis(start, "2026-10-18T10:00:01Z", 1_000, 1_750))
    }

    @Test fun invalidDatesOrClockResetCannotPermitStaleResult() {
        assertEquals(0L, remainingPurchaseCheckMillis("", end, 1_000, 1_001))
        assertEquals(0L, remainingPurchaseCheckMillis(end, start, 1_000, 1_001))
        assertEquals(0L, remainingPurchaseCheckMillis(start, end, 1_000, 500))
    }

    @Test fun excessiveServerLifetimeCannotExceedLocalCap() {
        assertEquals(59_000L, remainingPurchaseCheckMillis(start, "2027-10-18T10:00:00Z", 1_000, 2_000))
    }
}
