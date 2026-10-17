package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.SpatialState
import ru.omnicio.app.ui.spatial.SpatialSurface
import ru.omnicio.app.ui.spatial.SpatialSurfaceKind
import ru.omnicio.app.ui.spatial.rememberSpatialHapticClick

/** Brand-owned segmented navigation: single-line labels and 48dp+ targets. */
@Composable
fun SpectrumTabs(
    labels: List<String>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    if (labels.isEmpty()) return
    val palette = LocalSpectrumPalette.current
    val density = LocalDensity.current
    val style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold)
    val measurer = rememberTextMeasurer()
    val measured = labels.map { measurer.measure(AnnotatedString(it), style, softWrap = false, maxLines = 1).size }
    val minimumWidths = measured.map { with(density) { it.width.toDp() + 16.dp }.coerceAtLeast(48.dp) }
    val height = with(density) { measured.maxOf { it.height }.toDp() + 24.dp }.coerceAtLeast(52.dp)
    val gap = 6.dp
    val scroll = rememberScrollState()
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val available = (maxWidth - gap * (labels.size - 1)).coerceAtLeast(0.dp)
        val extra = ((available - minimumWidths.reduce { total, width -> total + width }) / labels.size).coerceAtLeast(0.dp)
        val widths = minimumWidths.map { it + extra }
        val selectedOffset = with(density) {
            widths.take(selected.coerceIn(labels.indices)).fold(0.dp) { total, width -> total + width + gap }.roundToPx()
        }
        LaunchedEffect(selectedOffset, scroll.maxValue) {
            scroll.scrollTo(selectedOffset.coerceIn(0, scroll.maxValue))
        }
        Row(
            Modifier.fillMaxWidth().height(height).horizontalScroll(scroll).selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(gap),
        ) {
            labels.forEachIndexed { index, label ->
                val chosen = index == selected
                val interaction = remember { MutableInteractionSource() }
                val focused by interaction.collectIsFocusedAsState()
                val pressed by interaction.collectIsPressedAsState()
                val click = rememberSpatialHapticClick { onSelect(index) }
                SpatialSurface(
                    modifier = Modifier
                        .width(widths[index])
                        .height(height)
                        .selectable(chosen, interactionSource = interaction, indication = null, role = Role.Tab, onClick = click),
                    kind = SpatialSurfaceKind.Chip,
                    color = if (chosen) palette.cardStrong else palette.card,
                    state = when { pressed -> SpatialState.Pressed; chosen || focused -> SpatialState.Selected; else -> SpatialState.Idle },
                    emphasized = chosen,
                ) {
                    Box(Modifier.fillMaxSize().padding(horizontal = 8.dp), contentAlignment = Alignment.Center) {
                    Text(
                        label,
                        style = style,
                        maxLines = 1,
                        softWrap = false,
                        color = if (chosen) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    }
                }
            }
        }
    }
}


