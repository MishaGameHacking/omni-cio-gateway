package ru.omnicio.app.ui.spatial

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntSize
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import kotlin.math.min

/** Exact orthographic references; native labels and date hit targets stay in the chart. */
@Composable
fun SpatialChartGuides(
    count: Int,
    zero: Float,
    missingIndices: Set<Int>,
    selectedIndex: Int? = null,
    modifier: Modifier = Modifier,
    gridColor: Color = LocalSpectrumPalette.current.semantic.chartGrid,
    selectedColor: Color = LocalSpectrumPalette.current.cyan,
    baselineColor: Color = LocalSpectrumPalette.current.semantic.chartAxis,
    missingColor: Color = LocalSpectrumPalette.current.semantic.chartAxis,
) {
    var size by remember { mutableStateOf(IntSize.Zero) }
    val density = LocalDensity.current.density
    val palette = LocalSpectrumPalette.current
    val base = LocalSpatialDepth.current
    val primitives = SpatialGuideGeometry.guides(count, zero, missingIndices, selectedIndex,
        size.width, size.height, density).map { guide ->
        val accent = when (guide.kind) {
            SpatialGuideGeometry.Kind.Grid -> gridColor
            SpatialGuideGeometry.Kind.Baseline -> baselineColor
            SpatialGuideGeometry.Kind.Selection -> selectedColor
            SpatialGuideGeometry.Kind.Missing -> missingColor
        }.compositeOver(palette.card)
        val depth = when (guide.kind) {
            SpatialGuideGeometry.Kind.Grid -> base - 2f
            SpatialGuideGeometry.Kind.Baseline -> base - 1f
            SpatialGuideGeometry.Kind.Selection -> base
            SpatialGuideGeometry.Kind.Missing -> base + 1f
        }
        SpatialPrimitive(SpatialAsset.Catalogue("bar"), guide.rect, accent,
            depth = depth, thickness = 2f, tilt = false, motionAllowed = false,
            key = guide.key)
    }
    SpatialCanvas(primitives, modifier.onSizeChanged { size = it })
}

/** Pixel thickness does not move a tick, zero baseline or observation centre. */
object SpatialGuideGeometry {
    enum class Kind { Grid, Baseline, Selection, Missing }
    data class Guide(val key: String, val kind: Kind, val rect: Rect)

    fun guides(count: Int, zero: Float, missingIndices: Set<Int>, selectedIndex: Int?,
               width: Int, height: Int, density: Float): List<Guide> {
        if (count <= 0 || width <= 0 || height <= 0 || !density.isFinite() || density <= 0f ||
            !zero.isFinite() || zero !in 0f..1f) return emptyList()
        val line = density / height
        val result = mutableListOf<Guide>()
        for (tick in listOf(0f, .5f, 1f)) {
            result += Guide("grid-$tick", Kind.Grid, Rect(0f, tick - line / 2, 1f, tick + line / 2))
        }
        result += Guide("zero", Kind.Baseline, Rect(0f, zero - line, 1f, zero + line))
        if (selectedIndex != null && selectedIndex in 0 until count) {
            val x = (selectedIndex + .5f) / count
            val half = density / width / 2
            result += Guide("selection", Kind.Selection, Rect(x - half, 0f, x + half, 1f))
        }
        val halfGap = min(.72f / count, 28f * density / width) / 2
        for (index in missingIndices.sorted()) {
            if (index !in 0 until count) continue
            val x = (index + .5f) / count
            result += Guide("missing-$index", Kind.Missing,
                Rect(x - halfGap, zero - line, x + halfGap, zero + line))
        }
        return result
    }
}
