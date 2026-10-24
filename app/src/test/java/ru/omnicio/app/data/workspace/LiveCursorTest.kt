package ru.omnicio.app.data.workspace

import org.junit.Assert.*
import org.junit.Test

class LiveCursorTest {
    private val a = "a".repeat(64)
    private val b = "b".repeat(64)
    private val c = "c".repeat(64)

    @Test fun heartbeatsAndReconnectsDoNotRepeatRefreshOrBrokerReads() {
        val cursor = LiveCursor()
        assertEquals(LiveDecision(true, true), cursor.accept(LiveChange(a, b, true)))
        assertEquals(LiveDecision(false, false), cursor.accept(LiveChange(a, b, true)))
        assertEquals(LiveDecision(true, false), cursor.accept(LiveChange(c, b, true)))
        assertEquals(LiveDecision(true, true), cursor.accept(LiveChange(b, c, false)))
    }
    @Test fun anotherSessionStartsWithoutTheOldCursor() {
        val old = LiveCursor()
        old.accept(LiveChange(a, b, true))
        assertNull(LiveCursor().revision)
        assertEquals(a, old.revision)
    }
    @Test fun malformedOrUnboundedServerVersionsAreRejected() {
        for (invalid in listOf("", "a", "g".repeat(64), "a".repeat(65), "../private")) {
            assertThrows(IllegalArgumentException::class.java) { LiveChange(invalid, b, true) }
            assertThrows(IllegalArgumentException::class.java) { LiveChange(a, invalid, true) }
        }
    }
    @Test fun offlineRetriesGrowAndStayBounded() {
        assertEquals(listOf(1000L, 2000L, 4000L, 8000L, 16000L, 30000L),
            (1..6).map(::liveRetryDelay))
        assertEquals(30000L, liveRetryDelay(Int.MAX_VALUE))
    }
}
