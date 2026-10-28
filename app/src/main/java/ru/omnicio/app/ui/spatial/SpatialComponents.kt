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
    val layered = LocalWorkspacePreferences.current.value.depth
    val highContrast = LocalFlatContrast.current
    val shape = RoundedCornerShape(when (kind) {
        SpatialSurfaceKind.Card -> 18.dp
        SpatialSurfaceKind.Dock -> 16.dp
        SpatialSurfaceKind.Chip -> 12.dp
        SpatialSurfaceKind.Heading -> 0.dp
        else -> 12.dp
    })
    val resolved = spatialSurfaceColors(palette, color, state, interactive, emphasized && layered, highContrast)
    val fill = if (kind == SpatialSurfaceKind.Heading) Color.Transparent else resolved.fill
    val border = when {
        kind == SpatialSurfaceKind.Heading -> Color.Transparent
        state == SpatialState.Idle && !highContrast && kind != SpatialSurfaceKind.Input -> Color.Transparent
        else -> resolved.border
    }
    val borderWidth = if (state == SpatialState.Selected) 1.5.dp else 1.dp
    val tint = if (emphasized) palette.colors.secondaryContainer else palette.colors.surfaceContainerLow
    val gradient = Brush.verticalGradient(listOf(fill, fill))
    Box(modifier.shadow(if (kind == SpatialSurfaceKind.Card && layered) 1.dp else 0.dp, shape, clip = false)
        .clip(shape).background(gradient).border(borderWidth, border, shape)) {
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
        state = state, content = content)
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
    SpatialCanvas(listOf(SpatialPrimitive(SpatialAsset.Catalogue(asset), color = ink,
        depth = LocalSpatialDepth.current + if (state == SpatialState.Selected) SpatialDepth.Selected else SpatialDepth.Icon,
        thickness = 34f, state = state, motionAllowed = motionAllowed,
        sharedKey = LocalSpatialObjectKey.current?.let { "$it/$asset" }, colorMode = colorMode,
        outlineColor = if (asset == "monogram" && state == SpatialState.Selected) palette.foregroundFor(ink) else Color.Unspecified)), semantics)
}

/** Decorative only: pair with Modifier.toggleable and a native label on a 48dp row. */
@Composable
fun SpatialToggleVisual(checked: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val palette = LocalSpectrumPalette.current
    val depth = LocalSpatialDepth.current
    val state = if (!enabled) SpatialState.Disabled else if (checked) SpatialState.Selected else SpatialState.Idle
    val colors = spatialToggleColors(palette, checked, enabled)
    SpatialCanvas(listOf(
        SpatialPrimitive(SpatialAsset.Catalogue("button"), Rect(0f, .16f, 1f, .84f),
            colors.track, depth, 24f, state, false, outlineColor = colors.outline),
        SpatialPrimitive(SpatialAsset.Catalogue("button"),
            if (checked) Rect(.55f, .21f, .95f, .79f) else Rect(.05f, .21f, .45f, .79f),
            colors.thumb, depth + 6f, 36f, state, false),
    ), modifier)
}

@Composable
fun SpatialChoiceVisual(selected: Boolean, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val palette = LocalSpectrumPalette.current
    val depth = LocalSpatialDepth.current
    val colors = spatialToggleColors(palette, selected, enabled)
    val primitives = mutableListOf(SpatialPrimitive(SpatialAsset.Catalogue("monogram"), color = colors.track,
        depth = depth, thickness = 18f, tilt = false, motionAllowed = false, outlineColor = colors.outline))
    if (selected) primitives += SpatialPrimitive(SpatialAsset.Catalogue("check"), Rect(.2f,.2f,.8f,.8f),
        colors.thumb, depth + 7f, 20f, SpatialState.Idle, false, motionAllowed = false)
    SpatialCanvas(primitives, modifier)
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

