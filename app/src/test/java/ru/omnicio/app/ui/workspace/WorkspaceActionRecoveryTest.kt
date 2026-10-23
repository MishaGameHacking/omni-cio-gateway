package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test
import ru.omnicio.app.data.workspace.VolumeReply

class WorkspaceActionRecoveryTest {
    private val requestId = "01234567-89ab-4cde-8fab-0123456789ab"
    private val otherId = "fedcba98-7654-4321-8abc-fedcba987654"

    @Test fun confirmedRecoveryClearsTheLostReplyAndItsAmbiguityTogether() {
        val failure = WorkspaceRequestFailure(
            VolumeReply(error = "Response lost after acceptance", ambiguous = true), requestId, true,
        )
        assertNull(failure.afterRecovery(requestId))
        // A checkpoint can still require recovery after a definite rejection
        // of a replay; its older accepted request remains authoritative.
        assertNull(failure.copy(reply = VolumeReply(error = "Replay rejected")).afterRecovery(requestId))
    }

    @Test fun anotherRequestCannotDismissTheCurrentFailure() {
        val failure = WorkspaceRequestFailure(VolumeReply(error = "Response lost"), requestId, true)
        for (recovered in listOf(otherId, "", " ", "null")) {
            assertSame(failure, failure.afterRecovery(recovered))
        }
        val laterFailure = failure.copy(requestId = otherId)
        assertSame(laterFailure, laterFailure.afterRecovery(requestId))
    }

    @Test fun untrackedOrDefinitelyRejectedFailuresRemainVisible() {
        val reply = VolumeReply(error = "Request rejected")
        for (failure in listOf(
            WorkspaceRequestFailure(reply, requestId, false),
            WorkspaceRequestFailure(reply, null, true),
            WorkspaceRequestFailure(reply, "", true),
        )) {
            assertSame(failure, failure.afterRecovery(requestId))
            assertSame(failure, failure.afterRecovery(""))
        }
    }

    @Test fun recoveryUsesLiveBusyStateAndNeverDispatchesAnotherRequest() {
        var busy = false
        var posts = 0
        val recovered = mutableListOf<String>()
        val action = WorkspaceAction({ busy }, "Response lost", true, recover = { recovered.add(it) }) {
                _, _, _, _, _ -> posts++
        }

        // A queued UI callback can hold this wrapper after a new request starts.
        busy = true
        action.acknowledgeRecovery(requestId)
        assertEquals(emptyList<String>(), recovered)
        busy = false
        action.acknowledgeRecovery("")
        action.acknowledgeRecovery(" ")
        assertEquals(emptyList<String>(), recovered)
        action.acknowledgeRecovery(requestId)
        assertEquals(listOf(requestId), recovered)
        assertEquals(0, posts)
    }
}
