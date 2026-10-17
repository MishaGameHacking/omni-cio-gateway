package ru.omnicio.app.ui.spatial

import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntSize
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

/** Supplied geographic anchor, never inferred from currency, ticker or asset name. */
data class SpatialGeoPoint(val id: String, val latitude: Double, val longitude: Double) {
    internal val valid: Boolean get() = id.isNotBlank() && latitude.isFinite() && longitude.isFinite() &&
        latitude in -90.0..90.0 && longitude in -180.0..180.0
}

object SpatialGeographyGeometry {
    data class Point(val index: Int, val x: Float, val y: Float, val forward: Float)
    fun centralLongitude(points: List<SpatialGeoPoint>, selectedIndex: Int?): Double =
        selectedIndex?.let(points::getOrNull)?.takeIf { it.valid }?.longitude ?: 0.0

    /** North remains up; back-hemisphere anchors are hidden, not put on the front. */
    fun project(points: List<SpatialGeoPoint>, selectedIndex: Int?): List<Point> {
        val centre = centralLongitude(points, selectedIndex)
        val identities = points.groupingBy { it.id }.eachCount()
        return points.mapIndexedNotNull { index, point ->
            if (!point.valid || identities[point.id] != 1) return@mapIndexedNotNull null
            val latitude = Math.toRadians(point.latitude)
            val longitude = Math.toRadians(point.longitude - centre)
            val forward = cos(latitude) * cos(longitude)
            if (forward < -1e-9) return@mapIndexedNotNull null
            Point(index, (.5 + .4 * cos(latitude) * sin(longitude)).toFloat(),
                (.5 - .4 * sin(latitude)).toFloat(), forward.coerceAtLeast(0.0).toFloat())
        }
    }
}

/**
 * Actual spherical grid and extruded anchors, orthographic and north-up. The
 * caller supplies verified coordinates, source/coverage labels and native list
 * selection. Country anchors must be described as anchors, not issuer premises.
 */
@Composable
fun SpatialGeography(points: List<SpatialGeoPoint>, selectedIndex: Int? = null, modifier: Modifier = Modifier) {
    val palette = LocalSpectrumPalette.current
    val density = LocalDensity.current.density
    var size by remember { mutableStateOf(IntSize(1, 1)) }
    val width = size.width.coerceAtLeast(1).toFloat()
    val height = size.height.coerceAtLeast(1).toFloat()
    val side = min(width, height)
    val sideDp = side / density
    val left = (width - side) / (2 * width)
    val top = (height - side) / (2 * height)
    val xScale = side / width
    val yScale = side / height
    val depth = LocalSpatialDepth.current + SpatialDepth.Icon
    val primitives = mutableListOf(SpatialPrimitive(SpatialAsset.Catalogue("globe"),
        Rect(left, top, left + xScale, top + yScale), palette.blue, depth, sideDp,
        tilt = false, motionAllowed = false, key = "geographic-grid",
        rotationY = -SpatialGeographyGeometry.centralLongitude(points, selectedIndex).toFloat()))
    SpatialGeographyGeometry.project(points, selectedIndex).forEach { point ->
        val selected = point.index == selectedIndex
        val half = (if (selected) 19f else 13f) * density
        val x = left + point.x * xScale
        val y = top + point.y * yScale
        primitives += SpatialPrimitive(SpatialAsset.Catalogue("monogram"),
            Rect(x-half/width, y-half/height, x+half/width, y+half/height),
            if (selected) palette.amber else palette.cyan,
            depth + .4f * point.forward * sideDp + if (selected) 12f else 6f,
            thickness = 10f, state = if (selected) SpatialState.Selected else SpatialState.Idle,
            tilt = false, motionAllowed = false, key = "geographic-anchor-${points[point.index].id}")
    }
    SpatialCanvas(primitives, modifier.aspectRatio(1f).onSizeChanged { size = it })
}
