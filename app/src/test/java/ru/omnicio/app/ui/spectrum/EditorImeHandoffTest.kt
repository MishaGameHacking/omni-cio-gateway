package ru.omnicio.app.ui.spectrum

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EditorImeHandoffTest {
    @Test fun temporarilyDisabledEditorRetainsOneHoldUntilItsSessionIsReady() {
        val fixture = Fixture()
        val window = FakeWindow(SECURE)
        var ready = false
        val handoff = fixture.handoff(window) { ready }
        handoff.acquire()
        handoff.acquire()
        assertFalse(handoff.handoff())
        assertEquals(SECURE or ALT, window.flags)
        assertEquals(listOf(ALT to ALT), fixture.writes)

        ready = true
        assertTrue(handoff.handoff())
        handoff.acquire()
        handoff.release()
        handoff.release()
        assertEquals(SECURE, window.flags)
        assertEquals(listOf(ALT to ALT, 0 to ALT), fixture.writes)
    }

    @Test fun editorReadyBeforeTheEffectDoesNotAcquireALateHold() {
        val fixture = Fixture()
        val window = FakeWindow(SECURE)
        val earlier = fixture.leases.acquire(window)
        val handoff = fixture.handoff(window) { true }
        handoff.acquire()
        earlier()
        handoff.release()

        assertEquals(SECURE, window.flags)
        assertEquals(listOf(ALT to ALT, 0 to ALT), fixture.writes)
    }

    @Test fun anotherPreparedEditorReleasesAllHoldsOnlyInItsOwnWindow() {
        val fixture = Fixture()
        val window = FakeWindow(SECURE)
        val otherWindow = FakeWindow(0)
        val first = fixture.leases.acquire(window)
        val second = fixture.leases.acquire(window)
        val other = fixture.leases.acquire(otherWindow)
        assertTrue(fixture.handoff(window) { true }.handoff())

        assertEquals(SECURE, window.flags)
        assertEquals(ALT, otherWindow.flags)
        first()
        second()
        assertEquals(ALT, otherWindow.flags)
        other()
        assertEquals(0, otherWindow.flags)
    }

    @Test fun staleReleaseCannotClearALaterGenerationInTheSameWindow() {
        val fixture = Fixture()
        val window = FakeWindow(SECURE)
        val oldHandoff = fixture.handoff(window) { false }
        oldHandoff.acquire()
        val oldPeer = fixture.leases.acquire(window)
        fixture.leases.releasePrepared(window)
        val current = fixture.leases.acquire(window)
        oldHandoff.release()
        oldPeer()
        oldHandoff.acquire()

        assertEquals(SECURE or ALT, window.flags)
        current()
        assertEquals(SECURE, window.flags)
        assertEquals(4, fixture.writes.size)
    }

    @Test fun cleanupKeepsOtherPendingOwnersUntilTheirLastReleaseInEitherOrder() {
        for (reverse in listOf(false, true)) {
            val fixture = Fixture()
            val window = FakeWindow(SECURE)
            val first = fixture.leases.acquire(window)
            val second = fixture.leases.acquire(window)
            if (reverse) second() else first()
            assertEquals(SECURE or ALT, window.flags)
            assertEquals(1, fixture.writes.size)
            if (reverse) first() else second()
            assertEquals(SECURE, window.flags)
            assertEquals(listOf(ALT to ALT, 0 to ALT), fixture.writes)
        }
    }

    @Test fun preexistingAltIsPreservedByReadinessAndByFinalCleanup() {
        for (prepared in listOf(false, true)) {
            val fixture = Fixture()
            val window = FakeWindow(SECURE or ALT)
            val first = fixture.leases.acquire(window)
            val second = fixture.leases.acquire(window)
            if (prepared) fixture.leases.releasePrepared(window)
            first()
            second()
            assertEquals(SECURE or ALT, window.flags)
            assertTrue(fixture.writes.isEmpty())
        }
    }

    @Test fun unrelatedFlagChangesSurviveReadinessAndFinalCleanup() {
        for (prepared in listOf(false, true)) {
            val fixture = Fixture()
            val window = FakeWindow(SECURE)
            val release = fixture.leases.acquire(window)
            window.flags = (window.flags and SECURE.inv()) or KEEP_SCREEN_ON
            if (prepared) fixture.leases.releasePrepared(window)
            release()
            assertEquals(KEEP_SCREEN_ON, window.flags)
            assertEquals(listOf(ALT to ALT, 0 to ALT), fixture.writes)
        }
    }

    @Test fun repeatedCleanupCannotReleaseAnotherPendingEditor() {
        val fixture = Fixture()
        val window = FakeWindow(0)
        val first = fixture.handoff(window) { false }
        first.acquire()
        val second = fixture.leases.acquire(window)
        first.release()
        first.release()
        assertEquals(ALT, window.flags)
        second()
        second()
        assertEquals(0, window.flags)
        assertEquals(2, fixture.writes.size)
    }

    @Test fun equalWindowsHaveIndependentOwnershipAndOriginalFlags() {
        val fixture = Fixture()
        val firstWindow = FakeWindow(0)
        val first = fixture.leases.acquire(firstWindow)
        val secondWindow = FakeWindow(ALT)
        assertEquals(firstWindow, secondWindow)
        val second = fixture.leases.acquire(secondWindow)
        first()
        assertEquals(0, firstWindow.flags)
        assertEquals(ALT, secondWindow.flags)
        second()
        assertEquals(ALT, secondWindow.flags)
        assertEquals(2, fixture.writes.size)
    }

    @Test fun recreationCleansTheOldWindowWithoutChangingTheReplacement() {
        val fixture = Fixture()
        val oldWindow = FakeWindow(SECURE)
        val newWindow = FakeWindow(SECURE)
        val old = fixture.handoff(oldWindow) { false }
        old.acquire()
        old.release()
        val current = fixture.leases.acquire(newWindow)
        old.release()
        assertEquals(SECURE, oldWindow.flags)
        assertEquals(SECURE or ALT, newWindow.flags)
        current()
        assertEquals(SECURE, newWindow.flags)
    }

    @Test fun aNewGenerationReadsTheCurrentBaseline() {
        val fixture = Fixture()
        val window = FakeWindow(0)
        fixture.leases.acquire(window)()
        window.flags = ALT or SECURE
        fixture.leases.acquire(window)()
        assertEquals(ALT or SECURE, window.flags)
        assertEquals(2, fixture.writes.size)
    }

    // Value equality deliberately differs from Window identity.
    private data class FakeWindow(var flags: Int)

    private class Fixture {
        val writes = mutableListOf<Pair<Int, Int>>()
        val leases = EditorWindowFlagLeases<FakeWindow>(
            flag = ALT,
            readFlags = { it.flags },
            setFlags = { window, flags, mask ->
                writes += flags to mask
                window.flags = (window.flags and mask.inv()) or (flags and mask)
            },
        )

        fun handoff(window: FakeWindow, ready: () -> Boolean) = EditorImeHandoff(
            acquireLease = { leases.acquire(window) },
            editorReady = ready,
            releasePrepared = { leases.releasePrepared(window) },
        )
    }

    private companion object {
        const val ALT = 0x00020000
        const val SECURE = 0x00002000
        const val KEEP_SCREEN_ON = 0x00000080
    }
}
