package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class SpatialGuideGeometryTest {
    @Test fun zeroTicksAndDateCentresDoNotMoveWithPixelThickness() {
        val guides = SpatialGuideGeometry.guides(10, .3f, setOf(0, 4), 7, 400, 200, 2f)
        assertEquals(listOf(0f, .5f, 1f), guides.filter { it.kind == SpatialGuideGeometry.Kind.Grid }.map { it.rect.center.y })
        assertEquals(.3f, guides.first { it.key == "zero" }.rect.center.y, .000001f)
        assertEquals(.75f, guides.first { it.key == "selection" }.rect.center.x, .000001f)
        assertEquals(.45f, guides.first { it.key == "missing-4" }.rect.center.x, .000001f)
        assertEquals(4f, guides.first { it.key == "missing-4" }.rect.height * 200, .00001f)
    }

    @Test fun missingWidthIsCappedAndInvalidIndicesNeverInventObservations() {
        val guides = SpatialGuideGeometry.guides(2, 1f, setOf(-1, 0, 2), 2, 400, 200, 2f)
        val gaps = guides.filter { it.kind == SpatialGuideGeometry.Kind.Missing }
        assertEquals(1, gaps.size)
        assertEquals(56f, gaps.single().rect.width * 400, .00001f)
        assertFalse(guides.any { it.kind == SpatialGuideGeometry.Kind.Selection })
        for (zero in listOf(Float.NaN, Float.POSITIVE_INFINITY, -.1f, 1.1f)) {
            assertTrue(SpatialGuideGeometry.guides(2, zero, emptySet(), null, 400, 200, 2f).isEmpty())
        }
    }
}
