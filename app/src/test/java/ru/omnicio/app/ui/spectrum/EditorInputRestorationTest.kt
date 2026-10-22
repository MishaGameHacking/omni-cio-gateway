package ru.omnicio.app.ui.spectrum

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EditorInputRestorationTest {
    @Test(timeout = 5000) fun hiddenIntentPreventsEvenTheFirstQueuedShow() = runBlocking {
        val ime = QueuedIme()
        var windowReady = false
        val completed = restoreEditorInput(
            showKeyboard = false,
            readOnly = false,
            requestFocus = { assertTrue(windowReady); ime.requestFocus() },
            // Any suspension after focus can let Compose process its input batch.
            awaitFocus = { ime.flushFrame(); yield() },
            awaitWindowReady = {
                assertEquals(0, ime.focusRequests)
                ime.flushFrame()
                yield()
                windowReady = true
            },
            awaitFrame = { ime.flushFrame(); yield() },
            setKeyboardVisible = ime::setKeyboardVisible,
            prepareInput = { error("Hidden restoration must not defer IME eligibility") },
        )
        ime.flushFrame()
        assertTrue(completed)
        assertEquals(listOf(false), ime.explicitRequests)
        assertEquals(0, ime.showRequests)
        assertFalse(ime.visible)
    }

    @Test(timeout = 5000) fun visibleEditorIsFocusedBeforeTheNewWindowAndShownAfterItsFrame() = runBlocking {
        val ime = QueuedIme()
        val observations = mutableListOf<String>()
        var inputHeld = true
        var cleanups = 0
        val completed = restoreEditorInput(
            showKeyboard = true,
            readOnly = false,
            requestFocus = { observations += "focus"; ime.requestFocus() },
            awaitFocus = {
                assertTrue(inputHeld)
                assertTrue(ime.explicitRequests.isEmpty())
                observations += "focused"
                ime.flushFrame()
                yield()
            },
            awaitWindowReady = {
                assertFalse(inputHeld)
                assertEquals(1, ime.focusRequests)
                assertEquals("input", observations.last())
                assertTrue(ime.explicitRequests.isEmpty())
                observations += "window"
                yield()
            },
            awaitFrame = {
                assertTrue(ime.explicitRequests.isEmpty())
                observations += "frame"
                yield()
            },
            setKeyboardVisible = { visible ->
                observations += "show"
                ime.setKeyboardVisible(visible)
            },
            prepareInput = {
                assertEquals("focused", observations.last())
                inputHeld = false
                observations += "input"
                true
            },
            releaseInput = { inputHeld = false; cleanups++ },
        )
        ime.flushFrame()
        assertTrue(completed)
        assertEquals(listOf("focus", "focused", "input", "window", "frame", "show"), observations)
        assertEquals(listOf(true), ime.explicitRequests)
        assertTrue(ime.visible)
        assertFalse(inputHeld)
        assertEquals(1, cleanups)
    }

    @Test(timeout = 5000) fun newImeObservationCannotInvertTheSavedHiddenIntent() = runBlocking {
        val ime = QueuedIme()
        var observedVisibility = false
        restoreEditorInput(
            showKeyboard = observedVisibility,
            readOnly = false,
            requestFocus = ime::requestFocus,
            awaitFocus = { ime.flushFrame(); yield() },
            awaitWindowReady = { observedVisibility = true; yield() },
            awaitFrame = { ime.flushFrame(); yield() },
            setKeyboardVisible = ime::setKeyboardVisible,
        )
        assertTrue(observedVisibility)
        assertEquals(0, ime.showRequests)
        assertFalse(ime.visible)
    }

    @Test(timeout = 5000) fun refusedFocusLeavesThePendingRestoreAndOtherEditorUntouched() = runBlocking {
        for (visible in listOf(false, true)) {
            val ime = QueuedIme()
            ime.setKeyboardVisible(true)
            ime.flushFrame()
            ime.explicitRequests.clear()
            var awaited = false
            var windowAwaited = false
            var cleanups = 0
            val completed = restoreEditorInput(
                showKeyboard = visible,
                readOnly = false,
                requestFocus = { false },
                awaitFocus = { awaited = true },
                awaitWindowReady = { windowAwaited = true },
                awaitFrame = { awaited = true },
                setKeyboardVisible = ime::setKeyboardVisible,
                prepareInput = { error("Refused focus cannot prepare native input") },
                releaseInput = { cleanups++ },
            )
            assertFalse(completed)
            assertFalse(awaited)
            assertEquals(!visible, windowAwaited)
            assertTrue(ime.explicitRequests.isEmpty())
            assertEquals(1, cleanups)
            assertTrue(ime.visible)
        }
    }

    @Test(timeout = 5000) fun readOnlyEditorRestoresFocusWithoutAnImeCommand() = runBlocking {
        for (visible in listOf(false, true)) {
            val observations = mutableListOf<String>()
            val ime = QueuedIme()
            val completed = restoreEditorInput(
                showKeyboard = visible,
                readOnly = true,
                requestFocus = { observations += "focus"; true },
                awaitFocus = { observations += "focused"; yield() },
                awaitWindowReady = { observations += "window"; yield() },
                awaitFrame = { observations += "frame"; yield() },
                setKeyboardVisible = ime::setKeyboardVisible,
                prepareInput = { error("Read-only restoration must not defer IME eligibility") },
            )
            assertTrue(completed)
            assertEquals(listOf("window", "focus", "focused", "frame"), observations)
            assertTrue(ime.explicitRequests.isEmpty())
        }
    }

    @Test(timeout = 5000) fun cancellationCannotFinishTheRestoreOrIssueALateShow() = runBlocking {
        for (visible in listOf(false, true)) {
            for (cancelAt in listOf("window", "focus", "frame")) {
                assertCancelledRestore(visible, cancelAt)
            }
        }
    }

    @Test(timeout = 5000) fun unpreparedInputReleasesTheHoldWithoutAdvancingToShow() = runBlocking {
        val ime = QueuedIme()
        var cleanups = 0
        val completed = restoreEditorInput(
            showKeyboard = true,
            readOnly = false,
            requestFocus = ime::requestFocus,
            awaitFocus = {},
            awaitWindowReady = { error("Input is not ready for a window handoff") },
            awaitFrame = { error("Input is not ready for a frame barrier") },
            setKeyboardVisible = ime::setKeyboardVisible,
            prepareInput = { false },
            releaseInput = { cleanups++ },
        )
        assertFalse(completed)
        assertEquals(1, cleanups)
        assertTrue(ime.explicitRequests.isEmpty())
    }

    @Test(timeout = 5000) fun failedInputPreparationStillReleasesTheHold() = runBlocking {
        var cleanups = 0
        val ime = QueuedIme()
        try {
            restoreEditorInput(
                showKeyboard = true,
                readOnly = false,
                requestFocus = ime::requestFocus,
                awaitFocus = {},
                awaitWindowReady = {},
                awaitFrame = {},
                setKeyboardVisible = ime::setKeyboardVisible,
                prepareInput = { error("fixture preparation failure") },
                releaseInput = { cleanups++ },
            )
            error("Expected input preparation to fail")
        } catch (expected: IllegalStateException) {
            assertEquals("fixture preparation failure", expected.message)
        }
        assertEquals(1, cleanups)
        assertTrue(ime.explicitRequests.isEmpty())
    }

    private suspend fun assertCancelledRestore(visible: Boolean, cancelAt: String) = coroutineScope {
        val ime = QueuedIme()
        val waiting = CompletableDeferred<Unit>()
        var completed = false
        var cleanups = 0
        suspend fun waitAt(stage: String) {
            if (cancelAt == stage) {
                waiting.complete(Unit)
                awaitCancellation()
            }
        }
        val restore = launch {
            completed = restoreEditorInput(
                showKeyboard = visible,
                readOnly = false,
                requestFocus = ime::requestFocus,
                awaitFocus = { waitAt("focus") },
                awaitWindowReady = { waitAt("window") },
                awaitFrame = { waitAt("frame") },
                setKeyboardVisible = ime::setKeyboardVisible,
                releaseInput = { cleanups++ },
            )
        }
        waiting.await()
        restore.cancelAndJoin()
        assertFalse(completed)
        assertEquals(1, cleanups)
        val expectedHide = !visible && cancelAt != "window"
        assertEquals(if (expectedHide) listOf(false) else emptyList<Boolean>(), ime.explicitRequests)
        assertEquals(if (visible || cancelAt != "window") 1 else 0, ime.focusRequests)
    }

    /** Compose's fresh StartInput batch implicitly shows unless a later hide replaces it. */
    private class QueuedIme {
        private val visibilityCommands = mutableListOf<Boolean>()
        val explicitRequests = mutableListOf<Boolean>()
        var visible = false
            private set
        var showRequests = 0
            private set
        var focusRequests = 0
            private set

        fun requestFocus(): Boolean {
            focusRequests += 1
            visibilityCommands += true
            return true
        }

        fun setKeyboardVisible(visible: Boolean) {
            explicitRequests += visible
            visibilityCommands += visible
        }

        fun flushFrame() {
            visibilityCommands.lastOrNull()?.let { requested ->
                visible = requested
                if (requested) showRequests += 1
            }
            visibilityCommands.clear()
        }
    }
}
