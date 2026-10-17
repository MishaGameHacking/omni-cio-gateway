package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

@Composable
fun SpectrumChoiceChip(
    selected: Boolean,
    onClick: () -> Unit,
    label: @Composable () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    leadingIcon: (@Composable () -> Unit)? = null,
    trailingIcon: (@Composable () -> Unit)? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; selected || focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val click = rememberSpatialHapticClick(onClick)
    SpatialSurface(modifier.heightIn(min = 48.dp).widthIn(min = 48.dp).selectable(selected,
        interactionSource = interaction, indication = null, enabled = enabled, role = Role.Checkbox, onClick = click),
        SpatialSurfaceKind.Chip, color = if (selected) LocalSpectrumPalette.current.cardStrong else LocalSpectrumPalette.current.card,
        state = state, emphasized = selected) {
        CompositionLocalProvider(LocalContentColor provides if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant) {
            Row(Modifier.align(Alignment.Center).padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                leadingIcon?.invoke()
                if (leadingIcon == null) SpatialIcon(if (selected) "check" else "monogram", Modifier.size(20.dp), state = state)
                label()
                trailingIcon?.invoke()
            }
        }
    }
}

/** Android/Compose owns dragging, keyboard increments and set-progress semantics. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpectrumSlider(
    value: Float,
    onValueChange: (Float) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    valueRange: ClosedFloatingPointRange<Float> = 0f..1f,
    steps: Int = 0,
    onValueChangeFinished: (() -> Unit)? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val fraction = ((value-valueRange.start)/(valueRange.endInclusive-valueRange.start))
        .takeIf { it.isFinite() }?.coerceIn(0f,1f) ?: 0f
    Slider(value = value, onValueChange = onValueChange, modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled, valueRange = valueRange, steps = steps,
        onValueChangeFinished = onValueChangeFinished, interactionSource = interaction,
        thumb = {
            SpatialIcon("monogram", Modifier.size(28.dp),
                tint = LocalSpectrumPalette.current.cyan,
                state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle })
        },
        track = { SpectrumProgressBar(fraction, Modifier.fillMaxWidth().clearAndSetSemantics { }) },
    )
}
