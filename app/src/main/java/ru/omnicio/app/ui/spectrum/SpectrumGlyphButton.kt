package ru.omnicio.app.ui.spectrum

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** Icon-only UI retains native names, long-press hints, focus and 48dp+ targets. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpectrumGlyphButton(symbol: SpectrumSymbol, label: String, onClick: () -> Unit,
    modifier: Modifier = Modifier, active: Boolean = false, enabled: Boolean = true,
    role: Role = Role.Button) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val hovered by interaction.collectIsHoveredAsState()
    val colors = MaterialTheme.colorScheme
    val animated = LocalFlatMotion.current != SpatialMotion.Off
    val scale by animateFloatAsState(if (pressed) .93f else if (focused || hovered) 1.07f else 1f,
        tween(if (animated) 140 else 0), label = "icon-focus")
    val click = rememberSpatialHapticClick(SpatialHaptic.Selection, onClick)
    TooltipBox(positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(),
        tooltip = { PlainTooltip { Text(label) } }, state = rememberTooltipState()) {
        Box(modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)
            .semantics { contentDescription = label; selected = active }
            .clip(RoundedCornerShape(4.dp))
            .background(if (active) colors.primaryContainer else colors.surface)
            .border(if (focused) 2.dp else 1.dp,
                if (focused) colors.secondary else if (active) colors.primary else colors.outlineVariant,
                RoundedCornerShape(4.dp))
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = role, onClick = click),
            contentAlignment = Alignment.Center) {
            SpatialIcon(symbol.asset, Modifier.size(22.dp).graphicsLayer { scaleX = scale; scaleY = scale },
                tint = if (enabled) colors.onSurface else colors.onSurfaceVariant,
                state = if (pressed) SpatialState.Pressed else if (active || focused) SpatialState.Selected else SpatialState.Idle,
                motionAllowed = enabled, colorMode = SpatialColorMode.Monochrome)
        }
    }
}

