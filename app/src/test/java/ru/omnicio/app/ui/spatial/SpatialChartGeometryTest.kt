package ru.omnicio.app.ui.spatial

import org.junit.Assert.*
import org.junit.Test

class SpatialChartGeometryTest {
    @Test fun signedBarsShareOneScaleAndMissingObservationsStayMissing() {
        val bars = SpatialChartGeometry.bars(listOf(-20.0, 0.0, 40.0, null, Double.NaN), -20.0, 40.0)
        assertEquals(1f, bars[0]!!.bottom, 0f)
        assertEquals(2f / 3f, bars[0]!!.top, .000001f)
        assertEquals(0f, bars[2]!!.top, 0f)
        assertEquals(bars[0]!!.top, bars[2]!!.bottom, .000001f)
        assertTrue(bars[1]!!.zero)
        assertEquals(bars[1]!!.top, bars[1]!!.bottom, 0f)
        assertNull(bars[3]); assertNull(bars[4])
        assertEquals(5, bars.size)
    }

    @Test fun finiteExtremeRangeDoesNotOverflowOrMoveTheZeroBaseline() {
        assertEquals(.5f, SpatialChartGeometry.normalized(0.0, -Double.MAX_VALUE, Double.MAX_VALUE)!!, 0f)
        assertEquals(1f, SpatialChartGeometry.normalized(Double.MAX_VALUE, -Double.MAX_VALUE, Double.MAX_VALUE)!!, 0f)
        assertEquals(0f, SpatialChartGeometry.normalized(-Double.MAX_VALUE, -Double.MAX_VALUE, Double.MAX_VALUE)!!, 0f)
        assertNull(SpatialChartGeometry.normalized(1.0, 2.0, 2.0))
        assertNull(SpatialChartGeometry.normalized(Double.POSITIVE_INFINITY, 0.0, 2.0))
    }

    @Test fun validExtremeAllocationsRemainProportionalAndInvalidWeightsAreAbsent() {
        val slices = SpatialChartGeometry.allocation(listOf(Double.MAX_VALUE, Double.MAX_VALUE / 2, -1.0, Double.NaN))
        assertEquals(2.0 / 3, slices[0].second, 1e-12)
        assertEquals(1.0 / 3, slices[1].second, 1e-12)
        assertEquals(1.0, slices.sumOf { it.second }, 1e-12)
        assertEquals(slices[0].second, slices[1].first, 1e-12)
        assertEquals(0.0, slices[2].second, 0.0)
        assertEquals(0.0, slices[3].second, 0.0)
        assertTrue(SpatialChartGeometry.allocation(listOf(0.0, -1.0)).all { it.second == 0.0 })
    }

    @Test fun invalidOHLCIsNotRenderedAsAMisleadingCandle() {
        assertTrue(SpatialCandle(10.0, 13.0, 9.0, 11.0).isValid)
        assertTrue(SpatialCandle(10.0, 10.0, 10.0, 10.0).isValid)
        assertFalse(SpatialCandle(10.0, 9.0, 8.0, 11.0).isValid)
        assertFalse(SpatialCandle(10.0, 12.0, 11.0, 11.0).isValid)
        assertFalse(SpatialCandle(Double.NaN, 12.0, 9.0, 11.0).isValid)
    }
}
