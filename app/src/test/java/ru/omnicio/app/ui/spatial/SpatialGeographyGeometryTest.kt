package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class SpatialGeographyGeometryTest {
    @Test fun northRemainsUpAndOppositeHemisphereIsHidden() {
        val points = listOf(SpatialGeoPoint("centre", 0.0, 0.0), SpatialGeoPoint("north", 90.0, 0.0),
            SpatialGeoPoint("east", 0.0, 90.0), SpatialGeoPoint("opposite", 0.0, 180.0))
        val rendered = SpatialGeographyGeometry.project(points, null)
        assertEquals(listOf(0, 1, 2), rendered.map { it.index })
        assertEquals(.5f, rendered[0].x, 1e-6f)
        assertEquals(.5f, rendered[0].y, 1e-6f)
        assertEquals(.1f, rendered[1].y, 1e-6f)
        assertEquals(.9f, rendered[2].x, 1e-6f)
    }

    @Test fun selectingAnAnchorCentersItsLongitudeWithoutChangingLatitude() {
        val points = listOf(SpatialGeoPoint("anchor", 30.0, 140.0), SpatialGeoPoint("other", 0.0, -40.0))
        val rendered = SpatialGeographyGeometry.project(points, 0)
        assertEquals(140.0, SpatialGeographyGeometry.centralLongitude(points, 0), 0.0)
        assertEquals(1, rendered.size)
        assertEquals(.5f, rendered[0].x, 1e-6f)
        assertEquals(.3f, rendered[0].y, 1e-6f)
        assertEquals(kotlin.math.sqrt(.75).toFloat(), rendered[0].forward, 1e-6f)
    }

    @Test fun unknownAndAmbiguousAnchorsDoNotInventCoordinates() {
        val points = listOf(SpatialGeoPoint("invalid", Double.NaN, 20.0), SpatialGeoPoint("range", 91.0, 20.0),
            SpatialGeoPoint("", 30.0, 20.0), SpatialGeoPoint("duplicate", 30.0, 20.0), SpatialGeoPoint("duplicate", 40.0, 30.0))
        assertTrue(SpatialGeographyGeometry.project(points, null).isEmpty())
        assertEquals(0.0, SpatialGeographyGeometry.centralLongitude(points, 0), 0.0)
    }
}
