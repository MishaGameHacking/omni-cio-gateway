package ru.omnicio.app.ui.home

import org.junit.Assert.*
import org.junit.Test

class DashboardOrderTest {
    private val order = listOf("a", "b", "c", "d")
    private val heights = mapOf("a" to 68f, "b" to 180f, "c" to 100f, "d" to 120f)

    @Test fun largeTextMovesOnlyAfterCrossingTheActualNeighbourCentre() {
        assertEquals(order, dragDashboardCard(order, "a", 100f, heights, 8f).order)
        val moved = dragDashboardCard(order, "a", 132f, heights, 8f)
        assertEquals(listOf("b", "a", "c", "d"), moved.order)
        assertEquals(-56f, moved.remaining, 0f)
        assertEquals(listOf("b", "a", "c", "d"), dragDashboardCard(order, "a", 250f, heights, 8f).order)
    }

    @Test fun oneFastGestureCanCrossSeveralUnequalRowsAndThenReverse() {
        val moved = dragDashboardCard(order, "a", 300f, heights, 8f)
        assertEquals(listOf("b", "c", "a", "d"), moved.order)
        assertEquals(4f, moved.remaining, 0f)
        val reversed = dragDashboardCard(moved.order, "a", -100f, heights, 8f)
        assertEquals(listOf("b", "a", "c", "d"), reversed.order)
        assertEquals(8f, reversed.remaining, 0f)
    }

    @Test fun draggingBeyondAnEdgeDoesNotAccumulateAnInvisibleDeadZone() {
        val edge = dragDashboardCard(order, "a", -1000f, heights, 8f)
        assertEquals(order, edge.order)
        assertEquals(0f, edge.remaining, 0f)
        assertEquals(listOf("b", "a", "c", "d"), dragDashboardCard(edge.order, "a", 132f, heights, 8f).order)
        assertEquals(order, dragDashboardCard(order, "missing", 1000f, heights, 8f).order)
        assertEquals(order, dragDashboardCard(order, "a", Float.NaN, heights, 8f).order)
    }
}
