package ru.omnicio.app.ui.spatial

import androidx.compose.runtime.Immutable
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/** Finite interactive motion. Android's disabled animators always override this. */
enum class SpatialMotion { Live, Subdued, Off }
enum class SpatialState { Idle, Selected, Pressed, Loading, Success, Attention, Disabled }

object SpatialDepth {
    const val Background = -12f
    const val Surface = 0f
    const val Emphasized = 4f
    const val Control = 8f
    const val Icon = 16f
    const val Selected = 22f
}

@Immutable
data class SpatialCandle(val open: Double, val high: Double, val low: Double, val close: Double) {
    val isValid: Boolean get() = open.isFinite() && high.isFinite() && low.isFinite() && close.isFinite() &&
        low <= min(open, close) && high >= max(open, close)
}

internal sealed interface SpatialAsset {
    data class Catalogue(val name: String) : SpatialAsset
    data class Glyph(val letter: Char) : SpatialAsset
    /** Geometry changes only when the input allocation changes, never each frame. */
    data class Wedge(val start: Double, val sweep: Double, val hollow: Double = .62) : SpatialAsset
}

@Immutable
internal data class SpatialPrimitive(
    val asset: SpatialAsset,
    val rect: Rect = Rect(0f, 0f, 1f, 1f),
    val color: Color,
    val depth: Float = SpatialDepth.Icon,
    val thickness: Float = 14f,
    val state: SpatialState = SpatialState.Idle,
    val tilt: Boolean = true,
    val motionAllowed: Boolean = true,
    val key: String = "mesh",
    val sharedKey: String? = null,
)

internal data class SpatialSlot(
    val id: Long,
    val bounds: Rect,
    val clip: Rect,
    val primitives: List<SpatialPrimitive>,
)

/** Pure arithmetic shared by rendering and tests; selection never alters value/scale. */
object SpatialChartGeometry {
    data class Bar(val left: Float, val top: Float, val right: Float, val bottom: Float, val zero: Boolean)

    fun normalized(value: Double, low: Double, high: Double): Float? {
        if (!value.isFinite() || !low.isFinite() || !high.isFinite() || high <= low) return null
        // Divide before subtracting for valid extreme finite doubles.
        val magnitude = max(abs(low), abs(high)).coerceAtLeast(1.0)
        val result = (value / magnitude - low / magnitude) / (high / magnitude - low / magnitude)
        return result.takeIf(Double::isFinite)?.coerceIn(0.0, 1.0)?.toFloat()
    }

    fun bars(values: List<Double?>, low: Double, high: Double): List<Bar?> {
        if (values.isEmpty()) return emptyList()
        val zero = normalized(0.0, low, high) ?: return List(values.size) { null }
        val count = values.size.toFloat()
        return values.mapIndexed { index, value ->
            val y = value?.let { normalized(it, low, high) }
            if (y == null) null else Bar(
                (index + .16f) / count, 1f - max(zero, y),
                (index + .84f) / count, 1f - min(zero, y), value == 0.0,
            )
        }
    }

    fun allocation(fractions: List<Double>): List<Pair<Double, Double>> {
        val valid = fractions.map { it.takeIf { n -> n.isFinite() && n > 0.0 } ?: 0.0 }
        val largest = valid.maxOrNull()?.takeIf { it > 0.0 } ?: return fractions.map { 0.0 to 0.0 }
        val sum = valid.sumOf { it / largest }
        var cursor = 0.0
        return valid.map { value ->
            val sweep = value / largest / sum
            (cursor to sweep).also { cursor += sweep }
        }
    }
}

/** Actual measured host statistics. Submit time is CPU time, not GPU execution time. */
data class SpatialDiagnostics(
    val engineCount: Int = 0,
    val submittedFrames: Long = 0,
    val skippedFrames: Long = 0,
    val frameIntervalP95Ms: Double = 0.0,
    val cpuSubmitP95Ms: Double = 0.0,
    val visibleMeshes: Int = 0,
    val cachedAssets: Int = 0,
    val pooledInstances: Int = 0,
    val quality: String = "standard",
    val error: String? = null,
    val catalogueVersion: Int = 1,
)
