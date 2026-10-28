package ru.omnicio.app.ui.spatial

import androidx.compose.ui.geometry.Offset
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SpatialPlacementInvalidationTest {
    @Test fun unchangedGeometryDoesNotWakeRenderer() {
        repeat(100) {
            assertFalse(spatialPlacementChanged(Offset(4f, 8f), 2f, Offset(4f, 8f), 2f))
        }
    }

    @Test fun horizontalMoveRequiresFrame() {
        assertTrue(spatialPlacementChanged(Offset.Zero, 2f, Offset(1f, 0f), 2f))
    }

    @Test fun verticalMoveRequiresFrame() {
        assertTrue(spatialPlacementChanged(Offset.Zero, 2f, Offset(0f, 1f), 2f))
    }

    @Test fun densityChangeWithoutMoveRequiresFrame() {
        assertTrue(spatialPlacementChanged(Offset.Zero, 2f, Offset.Zero, 3f))
    }

    @Test fun subpixelMoveIsNotHiddenByTolerance() {
        assertTrue(spatialPlacementChanged(Offset.Zero, 2f, Offset(0.01f, 0f), 2f))
    }
}
