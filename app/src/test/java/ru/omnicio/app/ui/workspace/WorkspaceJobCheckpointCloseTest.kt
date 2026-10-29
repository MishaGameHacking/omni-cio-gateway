package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WorkspaceJobCheckpointCloseTest {
    @Test fun confirmedFailureCanBeDismissedWithoutTrappingTheSameDraftForever() {
        assertTrue(canClearWorkspaceCheckpointOnClose("failed"))
        assertTrue(canClearWorkspaceCheckpointOnClose("completed"))
        assertTrue(canClearWorkspaceCheckpointOnClose("cancelled"))
    }

    @Test fun closingAnUncertainOrActiveJobNeverDiscardsItsRecoveryCheckpoint() {
        for (state in listOf("uncertain", "queued", "running", "cancel_requested", "", "unknown")) {
            assertFalse(state, canClearWorkspaceCheckpointOnClose(state))
        }
    }
}
