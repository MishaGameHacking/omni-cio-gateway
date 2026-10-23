package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** Row-content API for existing native action call sites that also contain labels. */
@Composable
fun SpectrumActionButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentPadding: PaddingValues = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
    content: @Composable RowScope.() -> Unit,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val action = rememberSpatialHapticClick(onClick)
    SpatialSurface(modifier.heightIn(min = 48.dp).widthIn(min = 48.dp).clickable(enabled = enabled,
        interactionSource = interaction, indication = null, role = Role.Button, onClick = action),
        SpatialSurfaceKind.Button, color = LocalSpectrumPalette.current.cardStrong, state = state) {
        CompositionLocalProvider(LocalContentColor provides
            if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant) {
            Row(Modifier.align(Alignment.Center).padding(contentPadding),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                content = content)
        }
    }
}

/** Compact native action with a mesh surface; it does not consume the whole row. */
@Composable
fun SpectrumTextButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    symbol: SpectrumSymbol? = null,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val click = rememberSpatialHapticClick(onClick)
    SpatialSurface(modifier.heightIn(min = 48.dp).widthIn(min = 48.dp).clickable(enabled = enabled,
        interactionSource = interaction, indication = null, role = Role.Button, onClick = click),
        SpatialSurfaceKind.Button, color = LocalSpectrumPalette.current.cardStrong, state = state) {
        Row(Modifier.align(Alignment.CenterStart).padding(horizontal = 12.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (symbol != null) SpatialIcon(symbol.asset, Modifier.size(22.dp), state = state)
            Text(text, color = if (enabled) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** A compact toolbar target with an explicit native accessibility label. */
@Composable
fun SpectrumIconButton(
    symbol: SpectrumSymbol,
    description: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }
    val click = rememberSpatialHapticClick(onClick)
    SpatialSurface(modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)
        .semantics { contentDescription = description }
        .clickable(enabled = enabled, interactionSource = interaction, indication = null, role = Role.Button, onClick = click),
        SpatialSurfaceKind.Button, state = state, color = LocalSpectrumPalette.current.cardStrong) {
        SpatialIcon(symbol.asset, Modifier.align(Alignment.Center).size(26.dp), state = state)
    }
}
