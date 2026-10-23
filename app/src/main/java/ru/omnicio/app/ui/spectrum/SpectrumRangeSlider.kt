package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.RangeSlider
import androidx.compose.material3.SliderDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** Two real mesh handles; native RangeSlider owns dragging, keyboard and progress semantics. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpectrumRangeSlider(
    value: ClosedFloatingPointRange<Float>,
    onValueChange: (ClosedFloatingPointRange<Float>) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    valueRange: ClosedFloatingPointRange<Float> = 0f..1f,
    steps: Int = 0,
    onValueChangeFinished: (() -> Unit)? = null,
    startDescription: String = "Начало периода",
    endDescription: String = "Конец периода",
) {
    val startInteraction = remember { MutableInteractionSource() }
    val endInteraction = remember { MutableInteractionSource() }
    val extent = valueRange.endInclusive - valueRange.start
    fun fraction(current: Float) = ((current - valueRange.start) / extent)
        .takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
    val start = fraction(value.start)
    val end = fraction(value.endInclusive).coerceAtLeast(start)
    val haptic = rememberSpatialHapticFeedback()
    RangeSlider(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled,
        valueRange = valueRange,
        onValueChangeFinished = { haptic(SpatialHaptic.Selection); onValueChangeFinished?.invoke() },
        colors = SliderDefaults.colors(),
        startInteractionSource = startInteraction,
        endInteractionSource = endInteraction,
        startThumb = { RangeHandle(startInteraction, enabled, startDescription) },
        endThumb = { RangeHandle(endInteraction, enabled, endDescription) },
        track = { RangeTrack(start, end, enabled) },
        steps = steps,
    )
}

@Composable
private fun RangeHandle(interaction: MutableInteractionSource, enabled: Boolean, description: String) {
    val pressed by interaction.collectIsPressedAsState()
    val dragged by interaction.collectIsDraggedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when {
        !enabled -> SpatialState.Disabled
        pressed || dragged -> SpatialState.Pressed
        focused -> SpatialState.Selected
        else -> SpatialState.Idle
    }
    Box(Modifier.size(48.dp).semantics { contentDescription = description }, contentAlignment = Alignment.Center) {
        SpatialIcon("monogram", Modifier.size(28.dp), tint = LocalSpectrumPalette.current.cyan, state = state)
    }
}

@Composable
private fun RangeTrack(start: Float, end: Float, enabled: Boolean) {
    val palette = LocalSpectrumPalette.current
    val state = if (enabled) SpatialState.Idle else SpatialState.Disabled
    BoxWithConstraints(Modifier.fillMaxWidth().height(8.dp).clearAndSetSemantics { }) {
        SpatialSurface(Modifier.fillMaxSize(), SpatialSurfaceKind.Chip, color = palette.cardStrong, state = state) { }
        if (end > start) SpatialSurface(
            Modifier.offset(x = maxWidth * start).width(maxWidth * (end - start)).fillMaxHeight(),
            SpatialSurfaceKind.Chip, color = palette.cyan, state = state,
        ) { }
    }
}
