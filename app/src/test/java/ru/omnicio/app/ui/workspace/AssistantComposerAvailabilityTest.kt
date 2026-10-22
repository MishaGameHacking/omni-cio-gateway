package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AssistantComposerAvailabilityTest {
    @Test fun checkpointReloadKeepsTheDraftEditableWithoutAllowingEarlyDispatch() {
        val loading = AssistantComposerAvailability(
            checkpointsLoading = true, recoveryRequired = false, operationBusy = false,
        )
        val ready = loading.copy(checkpointsLoading = false)
        var dispatched = 0
        assertTrue(loading.canEditDraft)
        loading.submitIfAllowed(valid = true) { dispatched++ }
        assertEquals(0, dispatched)
        assertTrue(ready.canEditDraft)
        ready.submitIfAllowed(valid = false) { dispatched++ }
        assertEquals(0, dispatched)
        ready.submitIfAllowed(valid = true) { dispatched++ }
        assertEquals(1, dispatched)
    }

    @Test fun discoveringAnUnconfirmedRequestBlocksInputAndDispatchBeforeLoadingFinishes() {
        val loading = AssistantComposerAvailability(
            checkpointsLoading = true, recoveryRequired = false, operationBusy = false,
        )
        val recoveryFound = loading.copy(recoveryRequired = true)
        val verified = recoveryFound.copy(checkpointsLoading = false)
        assertTrue(loading.canEditDraft)
        for (state in listOf(loading, recoveryFound, verified)) {
            assertFalse(state.canSubmit)
            state.submitIfAllowed(valid = true) { throw AssertionError("Dispatched before recovery") }
        }
        for (state in listOf(recoveryFound, verified)) assertFalse(state.canEditDraft)
    }

    @Test fun knownRecoveryRemainsBlockedDuringReadFailureAndRetry() {
        val blocked = AssistantComposerAvailability(
            checkpointsLoading = false, recoveryRequired = true, operationBusy = false,
        )
        for (state in listOf(blocked, blocked.copy(checkpointsLoading = true), blocked)) {
            assertFalse(state.canEditDraft)
            assertFalse(state.canSubmit)
            state.submitIfAllowed(valid = true) { throw AssertionError("Dispatched with unresolved request") }
        }
        val recovered = blocked.copy(recoveryRequired = false)
        assertTrue(recovered.canEditDraft)
        assertTrue(recovered.canSubmit)
    }

    @Test fun activeOperationRemainsBlockedEvenWhenCheckpointsAreReady() {
        val busy = AssistantComposerAvailability(
            checkpointsLoading = true, recoveryRequired = false, operationBusy = true,
        )
        for (state in listOf(busy, busy.copy(checkpointsLoading = false))) {
            assertFalse(state.canEditDraft)
            assertFalse(state.canSubmit)
            state.submitIfAllowed(valid = true) { throw AssertionError("Dispatched during active operation") }
        }
        val finished = busy.copy(operationBusy = false)
        assertTrue(finished.canEditDraft)
        assertFalse(finished.canSubmit)
    }
}
