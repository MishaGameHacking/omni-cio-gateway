package ru.omnicio.app.ui.spectrum

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EditorImeHandoffTest {
    @Test fun hostRemainsIneligibleThroughTargetFocusAndTheVisibleShowCommand() = runBlocking {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val dialog = FakeWindow(SECURE)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        host.acquire() // The parent effect runs before Dialog.show().
        var ready = false
        val editor = fixture.handoff(dialog, host) { ready }
        editor.acquire()
        assertEquals(SECURE or ALT, activity.flags)
        assertEquals(SECURE or ALT, dialog.flags)
        var showCommands = 0

        val restored = restoreEditorInput(
            showKeyboard = true, readOnly = false,
            requestFocus = { ready = true; true }, awaitFocus = {},
            awaitWindowReady = {
                assertEquals(SECURE, dialog.flags)
                assertEquals(SECURE or ALT, activity.flags)
                host.windowReady()
                assertEquals(SECURE or ALT, activity.flags)
            },
            awaitFrame = {},
            input = EditorInputCommands(
                setKeyboardVisible = { visible ->
                    assertTrue(visible)
                    assertEquals(SECURE or ALT, activity.flags)
                    showCommands++
                },
                prepareInput = editor::handoff, releaseInput = editor::release,
            ),
        )
        assertTrue(restored)
        assertEquals(1, showCommands)
        assertEquals(SECURE, activity.flags)
        assertEquals(SECURE, dialog.flags)
        host.release()
        editor.release()
        assertEquals(4, fixture.writes.size)
    }

    @Test fun alreadyPreparedChildRegistersBeforeTheParentAcquiresItsLease() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val dialog = FakeWindow(0)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        val editor = fixture.handoff(dialog, host) { true }
        editor.acquire()
        host.acquire()
        assertEquals(SECURE or ALT, activity.flags)
        assertEquals(0, dialog.flags)
        assertTrue(editor.handoff())
        host.windowReady()
        assertEquals(SECURE or ALT, activity.flags)

        editor.release()
        assertEquals(SECURE, activity.flags)
        host.acquire()
        editor.acquire()
        assertEquals(SECURE, activity.flags)
        assertEquals(2, fixture.writes.size)
    }

    @Test fun aDialogWithoutARestoredEditorReleasesItsHostOnlyAfterWindowFocus() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        host.acquire()
        assertEquals(SECURE or ALT, activity.flags)
        host.windowReady()
        assertEquals(SECURE, activity.flags)
        host.release()
        host.acquire()
        assertEquals(2, fixture.writes.size)
    }

    @Test fun lateRestoredEditorReacquiresHostBeforeMakingItsWindowIneligible() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val dialog = FakeWindow(0)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        host.acquire()
        host.windowReady() // The portfolio is still loading, so the dialog has no editor yet.
        assertEquals(SECURE, activity.flags)
        var ready = false
        val editor = EditorImeHandoff(
            acquireLease = {
                assertEquals(SECURE or ALT, activity.flags)
                fixture.leases.acquire(dialog)
            },
            editorReady = { ready },
            releasePrepared = { fixture.leases.releasePrepared(dialog) },
            acquireHostLease = host::holdForEditor,
        )

        editor.acquire() // Accounts arrived and the saved quantity editor was composed.
        assertEquals(ALT, dialog.flags)
        assertEquals(SECURE or ALT, activity.flags)
        ready = true
        assertTrue(editor.handoff())
        assertEquals(0, dialog.flags)
        assertEquals(SECURE or ALT, activity.flags)
        editor.release()
        assertEquals(SECURE, activity.flags)
        host.release()
        assertEquals(6, fixture.writes.size)
    }

    @Test fun completedEditorCleanupCannotReleaseALaterHostHoldOrRearmADisposedDialog() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        host.acquire()
        host.windowReady()
        val firstEditor = host.holdForEditor()
        assertEquals(SECURE or ALT, activity.flags)
        firstEditor()
        assertEquals(SECURE, activity.flags)
        val laterEditor = host.holdForEditor()
        firstEditor()
        assertEquals(SECURE or ALT, activity.flags)

        host.release()
        laterEditor()
        host.holdForEditor()
        host.acquire()
        host.windowReady()
        assertEquals(SECURE, activity.flags)
        assertEquals(6, fixture.writes.size)
    }

    @Test fun cancellationBeforeTargetWindowFocusCleansBothStagesWhenTheDialogLeaves() = runBlocking {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val dialog = FakeWindow(0)
        val host = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        host.acquire()
        var ready = false
        val editor = fixture.handoff(dialog, host) { ready }
        editor.acquire()
        val result = runCatching {
            restoreEditorInput(
                showKeyboard = true, readOnly = false,
                requestFocus = { ready = true; true }, awaitFocus = {},
                awaitWindowReady = { throw CancellationException("Dialog left before gaining focus") },
                awaitFrame = {},
                input = EditorInputCommands(
                    setKeyboardVisible = { throw AssertionError("A canceled window cannot request IME") },
                    prepareInput = editor::handoff, releaseInput = editor::release,
                ),
            )
        }
        assertTrue(result.exceptionOrNull() is CancellationException)
        assertEquals(0, dialog.flags)
        assertEquals(SECURE or ALT, activity.flags)
        host.release()
        assertEquals(SECURE, activity.flags)
        editor.release()
        host.windowReady()
        assertEquals(4, fixture.writes.size)
    }

    @Test fun overlappingDialogsAndEditorsKeepTheirHostUntilEveryShowOrCleanupFinishes() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val first = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        val second = DialogImeHostHandoff { fixture.leases.acquire(activity, releaseWhenPrepared = false) }
        first.acquire()
        second.acquire()
        val firstEditor = first.holdForEditor()
        val secondEditor = first.holdForEditor()
        first.windowReady()
        second.windowReady()
        firstEditor()
        firstEditor()
        second.release()
        assertEquals(SECURE or ALT, activity.flags)
        secondEditor()
        assertEquals(SECURE, activity.flags)
        first.release()
        assertEquals(2, fixture.writes.size)
    }

    @Test fun anUnderlyingPreparedEditorCannotReleaseTheModalHostGuardOrANewerEditorLease() {
        val fixture = Fixture()
        val activity = FakeWindow(SECURE)
        val host = fixture.leases.acquire(activity, releaseWhenPrepared = false)
        val oldEditor = fixture.leases.acquire(activity)
        fixture.leases.releasePrepared(activity)
        assertEquals(SECURE or ALT, activity.flags)
        val currentEditor = fixture.leases.acquire(activity)
        oldEditor()
        host()
        assertEquals(SECURE or ALT, activity.flags)
        currentEditor()
        assertEquals(SECURE, activity.flags)
        assertEquals(2, fixture.writes.size)
    }

    @Test fun protectedHostCleanupPreservesOriginalAltAndUnrelatedFlagChanges() {
        for (initialAlt in listOf(0, ALT)) {
            val fixture = Fixture()
            val window = FakeWindow(SECURE or initialAlt)
            val host = DialogImeHostHandoff { fixture.leases.acquire(window, releaseWhenPrepared = false) }
            host.acquire()
            window.flags = (window.flags and SECURE.inv()) or KEEP_SCREEN_ON
            fixture.leases.releasePrepared(window)
            host.release()
            assertEquals(KEEP_SCREEN_ON or initialAlt, window.flags)
        }
    }

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

        fun handoff(window: FakeWindow, host: DialogImeHostHandoff, ready: () -> Boolean) = EditorImeHandoff(
            acquireLease = { leases.acquire(window) },
            editorReady = ready,
            releasePrepared = { leases.releasePrepared(window) },
            acquireHostLease = host::holdForEditor,
        )
    }

    private companion object {
        const val ALT = 0x00020000
        const val SECURE = 0x00002000
        const val KEEP_SCREEN_ON = 0x00000080
    }
}
