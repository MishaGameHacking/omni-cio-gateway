package ru.omnicio.app.ui.spectrum

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
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
        val completed = restoreEditorInput(
            showKeyboard = false,
            readOnly = false,
            requestFocus = ime::requestFocus,
            // Any suspension after focus can let Compose process its input batch.
            awaitFocus = { ime.flushFrame(); yield() },
            awaitFrame = { ime.flushFrame(); yield() },
            setKeyboardVisible = ime::setKeyboardVisible,
        )
        ime.flushFrame()
        assertTrue(completed)
        assertEquals(listOf(false), ime.explicitRequests)
        assertEquals(0, ime.showRequests)
        assertFalse(ime.visible)
    }

    @Test(timeout = 5000) fun visibleIntentKeepsItsExplicitShowAfterFocusAndFrame() = runBlocking {
        val ime = QueuedIme()
        val observations = mutableListOf<String>()
        val completed = restoreEditorInput(
            showKeyboard = true,
            readOnly = false,
            requestFocus = { observations += "focus"; ime.requestFocus() },
            awaitFocus = {
                assertTrue(ime.explicitRequests.isEmpty())
                observations += "focused"
                ime.flushFrame()
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
        )
        ime.flushFrame()
        assertTrue(completed)
        assertEquals(listOf("focus", "focused", "frame", "show"), observations)
        assertEquals(listOf(true), ime.explicitRequests)
        assertTrue(ime.visible)
    }

    @Test(timeout = 5000) fun newImeObservationCannotInvertTheSavedHiddenIntent() = runBlocking {
        val ime = QueuedIme()
        var observedVisibility = false
        restoreEditorInput(
            showKeyboard = observedVisibility,
            readOnly = false,
            requestFocus = { observedVisibility = true; ime.requestFocus() },
            awaitFocus = { ime.flushFrame(); yield() },
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
            val completed = restoreEditorInput(
                showKeyboard = visible,
                readOnly = false,
                requestFocus = { false },
                awaitFocus = { awaited = true },
                awaitFrame = { awaited = true },
                setKeyboardVisible = ime::setKeyboardVisible,
            )
            assertFalse(completed)
            assertFalse(awaited)
            assertTrue(ime.explicitRequests.isEmpty())
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
                awaitFrame = { observations += "frame"; yield() },
                setKeyboardVisible = ime::setKeyboardVisible,
            )
            assertTrue(completed)
            assertEquals(listOf("focus", "focused", "frame"), observations)
            assertTrue(ime.explicitRequests.isEmpty())
        }
    }

    @Test(timeout = 5000) fun cancellationCannotFinishTheRestoreOrIssueALateShow() = runBlocking {
        for (visible in listOf(false, true)) {
            for (cancelAtFocus in listOf(false, true)) {
                val ime = QueuedIme()
                val waiting = CompletableDeferred<Unit>()
                var completed = false
                val restore = launch {
                    completed = restoreEditorInput(
                        showKeyboard = visible,
                        readOnly = false,
                        requestFocus = ime::requestFocus,
                        awaitFocus = {
                            if (cancelAtFocus) {
                                waiting.complete(Unit)
                                awaitCancellation()
                            }
                        },
                        awaitFrame = { waiting.complete(Unit); awaitCancellation() },
                        setKeyboardVisible = ime::setKeyboardVisible,
                    )
                }
                waiting.await()
                restore.cancelAndJoin()
                assertFalse(completed)
                assertEquals(if (visible) emptyList<Boolean>() else listOf(false), ime.explicitRequests)
            }
        }
    }

    /** Compose's fresh StartInput batch implicitly shows unless a later hide replaces it. */
    private class QueuedIme {
        private val visibilityCommands = mutableListOf<Boolean>()
        val explicitRequests = mutableListOf<Boolean>()
        var visible = false
            private set
        var showRequests = 0
            private set

        fun requestFocus(): Boolean {
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
