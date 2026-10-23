package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class StrategyEditorInitializationTest {
    @Test fun delayedFirstLoadDoesNotAcceptTextThatInitializationWouldOverwrite() {
        var draft = "36"
        var acceptedEdits = 0
        val waiting = StrategyEditorAvailability(hasEditorState = false, operationBusy = false)

        // Both a pending server response and the subsequent disk read leave the editor uninitialized.
        repeat(2) {
            assertFalse(waiting.canEdit)
            waiting.editIfAllowed { draft = "48"; acceptedEdits++ }
        }
        assertEquals("36", draft)
        assertEquals(0, acceptedEdits)

        draft = "72" // The saved draft becomes available after the delayed read.
        val ready = waiting.copy(hasEditorState = true)
        assertTrue(ready.canEdit)
        assertEquals("72", draft)
        ready.editIfAllowed { draft = "48"; acceptedEdits++ }
        assertEquals("48", draft)
        assertEquals(1, acceptedEdits)
    }

    @Test fun restoredEditorAcceptsChangesWhileServerStateReloads() {
        var draft = "48"
        val restored = StrategyEditorAvailability(hasEditorState = true, operationBusy = false)

        // Activity recreation already restored the draft; a new GET must not disable its input.
        assertTrue(restored.canEdit)
        restored.editIfAllowed { draft = "49" }
        assertEquals("49", draft)
    }

    @Test fun inFlightPreviewOrConfirmationCannotChangeItsDraftThroughAQueuedCallback() {
        var draft = "48"
        var previewBusy = false
        var confirmationBusy = false
        val preview = WorkspaceAction({ previewBusy }, null, false) { _, _, _, _, _ -> previewBusy = true }
        val confirmation = WorkspaceAction({ confirmationBusy }, null, false) { _, _, _, _, _ -> confirmationBusy = true }
        // Capture the actual action wrappers before either request starts, as the editor does.
        val queuedEdit: (String) -> Unit = { next ->
            StrategyEditorAvailability(hasEditorState = true, operationBusy = preview.busy || confirmation.busy).editIfAllowed { draft = next }
        }

        preview.perform("/workspace/strategy/preview")
        assertTrue(preview.busy)
        queuedEdit("60")
        assertEquals("48", draft)

        previewBusy = false
        confirmation.perform("/workspace/strategy/confirm")
        assertTrue(confirmation.busy)
        queuedEdit("60")
        assertEquals("48", draft)

        confirmationBusy = false
        assertFalse(preview.busy || confirmation.busy)
        queuedEdit("60")
        assertEquals("60", draft)
    }
}
