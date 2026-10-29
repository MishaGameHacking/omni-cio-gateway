package ru.omnicio.app.ui.auth

import org.junit.Assert.*
import org.junit.Test

class OwnerAccessGateTest {
    @Test fun restoringSessionCannotUnlockAfterBackground() {
        val gate = OwnerAccessGate(true)
        val restore = requireNotNull(gate.begin())
        gate.background()
        assertFalse(gate.complete(restore))
    }

    @Test fun returningToForegroundDoesNotReviveOldPasswordResponse() {
        val gate = OwnerAccessGate(true)
        val login = requireNotNull(gate.begin())
        gate.background()
        gate.foreground()
        assertFalse(gate.complete(login))
        assertTrue(gate.complete(requireNotNull(gate.begin())))
    }

    @Test fun lateBiometricSuccessCannotCrossStopAndResume() {
        val gate = OwnerAccessGate(true)
        val prompt = requireNotNull(gate.begin())
        gate.background()
        assertNull(gate.begin())
        gate.foreground()
        assertFalse(gate.isCurrent(prompt))
        assertFalse(gate.complete(prompt))
    }

    @Test fun duplicateOrSupersededCallbacksNeverPublishAccessTwice() {
        val gate = OwnerAccessGate(true)
        val first = requireNotNull(gate.begin())
        val next = requireNotNull(gate.begin())
        assertFalse(gate.complete(first))
        assertTrue(gate.complete(next))
        assertFalse(gate.complete(next))
    }

    @Test fun backgroundDuringPersistenceLeavesNewSessionLocked() {
        val gate = OwnerAccessGate(true)
        assertTrue(gate.complete(requireNotNull(gate.begin())))
        val persistence = requireNotNull(gate.begin())
        gate.background()
        gate.foreground()
        assertFalse(gate.complete(persistence))
    }
}
