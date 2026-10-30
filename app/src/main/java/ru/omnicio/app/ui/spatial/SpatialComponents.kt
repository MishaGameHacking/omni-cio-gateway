package ru.omnicio.app.ui.spatial

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import androidx.compose.material3.LocalContentColor
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import kotlin.math.max
import kotlin.math.min

enum class SpatialSurfaceKind(val asset: String) {
    Card("surface"), Button("button"), Chip("chip"), Input("input"), Dock("dock"), Heading("heading"),
}

internal val LocalSpatialDepth = staticCompositionLocalOf { 0f }
internal val LocalSpatialObjectKey = staticCompositionLocalOf<String?> { null }

/** Preserve the semantic identity of a position as its detail opens. */
@Composable
fun SpatialObject(key: String, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalSpatialObjectKey provides key, content = content)
}

/** Native layout, hit testing, text and focus remain in the caller's content. */
@Composable
fun SpatialSurface(
    modifier: Modifier = Modifier,
    kind: SpatialSurfaceKind = SpatialSurfaceKind.Card,
    color: Color = LocalSpectrumPalette.current.card,
    state: SpatialState = SpatialState.Idle,
    emphasized: Boolean = false,
    interactive: Boolean = kind == SpatialSurfaceKind.Button || kind == SpatialSurfaceKind.Input,
    content: @Composable BoxScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val highContrast = LocalFlatContrast.current
    val shape = RoundedCornerShape(if (kind == SpatialSurfaceKind.Heading) 0.dp else 4.dp)
    val resolved = spatialSurfaceColors(palette, color, state, interactive, false, highContrast)
    val fill = if (kind == SpatialSurfaceKind.Heading) Color.Transparent else resolved.fill
    val border = when {
        kind == SpatialSurfaceKind.Heading -> Color.Transparent
        state == SpatialState.Selected -> palette.colors.primary
        else -> palette.colors.outlineVariant
    }
    Box(modifier.clip(shape).background(fill).border(1.dp, border, shape)) {
        CompositionLocalProvider(LocalSpatialDepth provides 0f,
            LocalContentColor provides resolved.foreground) { content() }
    }
}

@Composable
fun SpatialField(
    modifier: Modifier = Modifier,
    focused: Boolean = false,
    error: Boolean = false,
    enabled: Boolean = true,
    content: @Composable BoxScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val state = when { !enabled -> SpatialState.Disabled; error -> SpatialState.Attention; focused -> SpatialState.Selected; else -> SpatialState.Idle }
    SpatialSurface(modifier, SpatialSurfaceKind.Input, color = palette.card,
        state = state) {
        Box(Modifier.padding(vertical = 6.dp), content = content)
    }
}

/** Original animated 2D vectors; labels and interaction stay native. */
@Composable
fun SpatialIcon(
    asset: String,
    modifier: Modifier = Modifier,
    tint: Color = Color.Unspecified,
    state: SpatialState = SpatialState.Idle,
    motionAllowed: Boolean = true,
    description: String? = null,
    colorMode: SpatialColorMode = spatialIconMode(asset),
) {
    val palette = LocalSpectrumPalette.current
    val ink = spatialIconInk(palette, asset, tint, state)
    val semantics = if (description == null) modifier else modifier.semantics { contentDescription = description }
    ru.omnicio.app.ui.terminal.TerminalGlyph(asset, semantics, ink)
}

/** Decorative only: pair with Modifier.toggleable and a native label on a 48dp row. */
@Composable
fun SpatialToggleVisual(checked: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val colors = spatialToggleColors(LocalSpectrumPalette.current, checked, enabled)
    androidx.compose.foundation.Canvas(modifier) {
        drawRect(colors.track)
        drawRect(colors.outline, style = androidx.compose.ui.graphics.drawscope.Stroke(1.dp.toPx()))
        val inset = 3.dp.toPx()
        val width = (size.width / 2 - inset * 2).coerceAtLeast(1f)
        drawRect(colors.thumb, androidx.compose.ui.geometry.Offset(if (checked) size.width / 2 + inset else inset, inset),
            androidx.compose.ui.geometry.Size(width, (size.height - inset * 2).coerceAtLeast(1f)))
    }
}

@Composable
fun SpatialChoiceVisual(selected: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val colors = spatialToggleColors(LocalSpectrumPalette.current, selected, enabled)
    Box(modifier.background(colors.track).border(1.dp, colors.outline)) {
        if (selected) ru.omnicio.app.ui.terminal.TerminalGlyph("check", Modifier.matchParentSize(), colors.thumb)
    }
}

/** Orthographic height is exactly the supplied value; selection is painted inside its bounds. */
@Composable
fun SpatialBars(
    values: List<Double?>,
    low: Double,
    high: Double,
    selectedIndex: Int? = null,
    modifier: Modifier = Modifier,
    colors: List<Color> = emptyList(),
) {
    val palette = LocalSpectrumPalette.current
    val density = LocalDensity.current.density
    var height by remember { mutableStateOf(1) }
    val marker = 2f * density / height.coerceAtLeast(1)
    val depth = LocalSpatialDepth.current
    val primitives = SpatialChartGeometry.bars(values, low, high).mapIndexedNotNull { index, bar ->
        bar ?: return@mapIndexedNotNull null
        val top = if (bar.zero) (bar.top - marker / 2).coerceIn(0f, 1f - marker.coerceAtMost(1f)) else bar.top
        val bottom = if (bar.zero) (top + marker).coerceAtMost(1f) else bar.bottom
        SpatialPrimitive(SpatialAsset.Catalogue("bar"), Rect(bar.left, top, bar.right, bottom),
            colors.getOrNull(index) ?: if (values[index]!! < 0.0) palette.rose else palette.cyan,
            depth + if (selectedIndex == index) SpatialDepth.Selected else SpatialDepth.Control,
            thickness = 8f, state = if (selectedIndex == index) SpatialState.Selected else SpatialState.Idle,
            tilt = false, motionAllowed = false, key = "bar-$index")
    }
    SpatialCanvas(primitives, modifier.onSizeChanged { height = it.height })
}

@Composable
fun SpatialCandles(
    candles: List<SpatialCandle>,
    low: Double,
    high: Double,
    selectedIndex: Int? = null,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val density = LocalDensity.current.density
    var width by remember { mutableStateOf(1) }
    var height by remember { mutableStateOf(1) }
    val primitives = mutableListOf<SpatialPrimitive>()
    val depth = LocalSpatialDepth.current
    val count = candles.size.coerceAtLeast(1).toFloat()
    candles.forEachIndexed { index, candle ->
        if (!candle.isValid) return@forEachIndexed
        val top = SpatialChartGeometry.normalized(candle.high, low, high)?.let { 1f - it } ?: return@forEachIndexed
        val bottom = SpatialChartGeometry.normalized(candle.low, low, high)?.let { 1f - it } ?: return@forEachIndexed
        val open = SpatialChartGeometry.normalized(candle.open, low, high)?.let { 1f - it } ?: return@forEachIndexed
        val close = SpatialChartGeometry.normalized(candle.close, low, high)?.let { 1f - it } ?: return@forEachIndexed
        val center = (index + .5f) / count
        val wick = min(1.5f * density / width.coerceAtLeast(1), .15f / count)
        val state = if (selectedIndex == index) SpatialState.Selected else SpatialState.Idle
        val z = depth + if (selectedIndex == index) SpatialDepth.Selected else SpatialDepth.Control
        val color = if (candle.close >= candle.open) palette.emerald else palette.rose
        if (bottom > top) primitives += SpatialPrimitive(SpatialAsset.Catalogue("bar"),
            Rect(center - wick / 2, top, center + wick / 2, bottom), color, z, 5f, state, false, false, "wick-$index")
        val marker = 1.5f * density / height.coerceAtLeast(1)
        val bodyTop = if (candle.open == candle.close) (open - marker / 2).coerceAtLeast(0f) else min(open, close)
        val bodyBottom = if (candle.open == candle.close) (bodyTop + marker).coerceAtMost(1f) else max(open, close)
        primitives += SpatialPrimitive(SpatialAsset.Catalogue("bar"),
            Rect((index + .2f) / count, bodyTop, (index + .8f) / count, bodyBottom),
            color, z + 2f, 8f, state, false, false, "body-$index")
    }
    SpatialCanvas(primitives, modifier.onSizeChanged { width = it.width; height = it.height })
}

@Composable
fun SpatialRing(
    fractions: List<Double>,
    colors: List<Color>,
    selectedIndex: Int? = null,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val depth = LocalSpatialDepth.current
    val primitives = SpatialChartGeometry.allocation(fractions).mapIndexedNotNull { index, (start, sweep) ->
        if (sweep <= 0.0) return@mapIndexedNotNull null
        SpatialPrimitive(SpatialAsset.Wedge(start, sweep), color = colors.getOrNull(index) ?: palette.blue,
            depth = depth + if (selectedIndex == index) SpatialDepth.Selected else SpatialDepth.Control,
            thickness = 25f, state = if (selectedIndex == index) SpatialState.Selected else SpatialState.Idle,
            tilt = false, motionAllowed = false, key = "slice-$index")
    }
    SpatialCanvas(primitives, modifier)
}



