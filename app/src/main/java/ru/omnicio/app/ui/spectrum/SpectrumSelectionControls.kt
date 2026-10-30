package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** The native Material switch shares the exact state colors of the custom switch. */
@Composable
fun SpectrumSwitch(
    checked: Boolean,
    onCheckedChange: ((Boolean) -> Unit)?,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val interaction = if (onCheckedChange == null) Modifier else
        Modifier.toggleable(checked, enabled = enabled, role = Role.Switch, onValueChange = onCheckedChange)
    Box(modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp).then(interaction), contentAlignment = Alignment.Center) {
        SpatialToggleVisual(checked, Modifier.size(40.dp, 20.dp).clearAndSetSemantics { }, enabled)
    }
}

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
    val click = rememberSpatialHapticClick(SpatialHaptic.Selection, onClick)
    val palette = LocalSpectrumPalette.current
    val ink = when { !enabled -> palette.semantic.disabledInk; selected -> palette.colors.onPrimaryContainer; else -> palette.colors.onSurface }
    SpatialSurface(modifier.heightIn(min = 48.dp).widthIn(min = 48.dp).selectable(selected,
        interactionSource = interaction, indication = null, enabled = enabled, role = Role.Checkbox, onClick = click),
        SpatialSurfaceKind.Chip, color = if (selected) palette.colors.primaryContainer else palette.card,
        state = state, emphasized = selected, interactive = true) {
        CompositionLocalProvider(LocalContentColor provides ink) {
            Row(Modifier.align(Alignment.Center).padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                leadingIcon?.invoke()
                if (leadingIcon == null) SpatialIcon(if (selected) "check" else "monogram", Modifier.size(20.dp),
                    tint = ink, state = state, colorMode = SpatialColorMode.Monochrome)
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
    val fraction = ((value-valueRange.start)/(valueRange.endInclusive-valueRange.start))
        .takeIf { it.isFinite() }?.coerceIn(0f,1f) ?: 0f
    Slider(value = value, onValueChange = onValueChange, modifier = modifier.heightIn(min = 48.dp),
        enabled = enabled, valueRange = valueRange, steps = steps,
        onValueChangeFinished = onValueChangeFinished, interactionSource = interaction,
        thumb = {
            androidx.compose.material3.Surface(Modifier.size(20.dp),
                color = if (enabled) LocalSpectrumPalette.current.cyan else LocalSpectrumPalette.current.semantic.disabledInk,
                shape = androidx.compose.foundation.shape.RoundedCornerShape(2.dp),
                border = androidx.compose.foundation.BorderStroke(2.dp, MaterialTheme.colorScheme.onPrimary)) {}
        },
        track = { SpectrumProgressBar(fraction, Modifier.fillMaxWidth().clearAndSetSemantics { }, enabled = enabled) },
    )
}

