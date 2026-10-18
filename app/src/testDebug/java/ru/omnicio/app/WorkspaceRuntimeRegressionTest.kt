package ru.omnicio.app

import org.junit.Assert.assertEquals
import org.junit.Test

/** Run the debug entry-point's pure contract assertions before installing an APK. */
class WorkspaceRuntimeRegressionTest {
    @Test fun workspaceContractsPassBeforeTheProbeActivityStarts() {
        assertEquals(24, runWorkspaceUxChecks())
    }
}
