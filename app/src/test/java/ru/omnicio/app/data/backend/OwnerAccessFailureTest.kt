package ru.omnicio.app.data.backend

import java.time.Instant
import org.junit.Assert.*
import org.junit.Test

class OwnerAccessFailureTest {
    @Test fun throttlingCarriesActualServerDelayWithoutEchoingHeader() {
        val failure = ownerAccessFailure(429, " 125 ")
        assertEquals(429, failure.statusCode)
        assertEquals(125, failure.retryAfterSeconds)
        assertTrue(failure.retryable)
        assertFalse(failure.message.contains("125"))
    }

    @Test fun nonThrottlingResponsesNeverStartCountdown() {
        for (status in listOf(401, 403, 404, 409, 422, 426, 500)) {
            assertNull(ownerAccessFailure(status, "900").retryAfterSeconds)
        }
    }

    @Test fun missingMalformedNegativeAndOverflowHeadersDoNotInventDuration() {
        for (header in listOf(null, "", "0", "-1", "+1", "1.5", "1e3", "86401",
            "999999999999999999999999", "not-a-date", "секрет")) {
            assertNull(header, ownerRetryAfterSeconds(header))
        }
        assertEquals(1, ownerRetryAfterSeconds("1"))
        assertEquals(900, ownerRetryAfterSeconds("900"))
    }

    @Test fun httpDateUsesServerClockInsteadOfIncorrectPhoneClock() {
        assertEquals(15, ownerRetryAfterSeconds(
            "Wed, 21 Oct 2015 07:28:15 GMT",
            "Wed, 21 Oct 2015 07:28:00 GMT",
            receivedAtMillis = Long.MIN_VALUE,
        ))
    }

    @Test fun httpDateFallsBackToReceiptTimeAndRoundsUpPartialSeconds() {
        val now = Instant.parse("2015-10-21T07:28:00.500Z").toEpochMilli()
        assertEquals(15, ownerRetryAfterSeconds("Wed, 21 Oct 2015 07:28:15 GMT", receivedAtMillis = now))
        assertNull(ownerRetryAfterSeconds("Wed, 21 Oct 2015 07:28:00 GMT", receivedAtMillis = now))
        assertNull(ownerRetryAfterSeconds("Wed, 21 Oct 2015 07:28:15 GMT", receivedAtMillis = Long.MIN_VALUE))
    }

    @Test fun malformedServerDateDoesNotCrashDateFallback() {
        val now = Instant.parse("2015-10-21T07:28:00Z").toEpochMilli()
        assertEquals(15, ownerRetryAfterSeconds(
            "Wed, 21 Oct 2015 07:28:15 GMT", "untrusted-header", now,
        ))
    }
}
