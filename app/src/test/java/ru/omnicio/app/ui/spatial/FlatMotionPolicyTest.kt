package ru.omnicio.app.ui.spatial

import org.junit.Assert.assertEquals
import org.junit.Test

class FlatMotionPolicyTest {
    @Test fun backgroundAndSystemAccessibilityStopEveryMotionMode() {
        SpatialMotion.entries.forEach { mode ->
            assertEquals(SpatialMotion.Off, flatMotionPolicy(mode, false, true, false))
            assertEquals(SpatialMotion.Off, flatMotionPolicy(mode, true, false, false))
        }
    }
    @Test fun severeThermalStopsAllModesUntilRecovery() {
        SpatialMotion.entries.forEach { mode ->
            assertEquals(SpatialMotion.Off, flatMotionPolicy(mode, true, true, true, true))
        }
        assertEquals(SpatialMotion.Live, flatMotionPolicy(SpatialMotion.Live, true, true, false, false))
    }
    @Test fun deviceConstraintsNeverOverrideTheUsersOffSetting() {
        assertEquals(SpatialMotion.Off, flatMotionPolicy(SpatialMotion.Off, true, true, true))
        assertEquals(SpatialMotion.Subdued, flatMotionPolicy(SpatialMotion.Live, true, true, true))
        assertEquals(SpatialMotion.Subdued, flatMotionPolicy(SpatialMotion.Subdued, true, true, false))
        assertEquals(SpatialMotion.Live, flatMotionPolicy(SpatialMotion.Live, true, true, false))
    }
}
