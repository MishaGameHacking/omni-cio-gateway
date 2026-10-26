package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class LiveIconClockTest {
    @Test fun sharedClockOwnsOnlyDistinctVisibleRegistrations() {
        val clock=LiveIconClock(); val first=Any(); val second=Any()
        clock.attach(first);clock.attach(first);clock.attach(second)
        assertEquals(2,clock.activeCount)
        clock.detach(first);clock.detach(first)
        assertEquals(1,clock.activeCount)
        clock.detach(second)
        assertEquals(0,clock.activeCount)
    }
    @Test fun phaseIsBoundedAndWrapsWithoutAccumulatingTimeOrChangingValues() {
        assertEquals(0f,decorativeLoopPhase(-1),0f)
        assertEquals(0f,decorativeLoopPhase(0),0f)
        assertEquals(.5f,decorativeLoopPhase(2_400_000_000L),.0001f)
        assertEquals(0f,decorativeLoopPhase(4_800_000_000L),0f)
        assertEquals(.5f,decorativeLoopPhase(7_200_000_000L),.0001f)
        assertTrue(decorativeLoopPhase(Long.MAX_VALUE) in 0f..1f)
    }
}
